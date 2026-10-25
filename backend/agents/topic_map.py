"""Topic maps for new goals (docs/specs/topic-map).

FR1 `match_goal`: a typed goal matches an existing idea only on distinctive words, weighted by rarity across the graph.
FR2 `build`: with an AI engine, a new goal becomes 4–8 connected ideas (reusing existing ones) before teaching starts.
FR3 `notes_passages`: the learner's attached notes, else the best-matching passages from the notes folder.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from .. import db, llm, tools
from . import prompts, subagents

MAP_TIMEOUT_S = 150.0
COVERAGE = 0.6
NOTES_CHARS = 3000
NODE_TYPES = ("AXIOM", "PROPOSITION", "MOVE", "COUNTEREXAMPLE", "INTUITION")

STOP = {
    "the", "and", "for", "how", "why", "are", "its", "via", "use", "can", "not", "all", "any", "one", "two", "you",
    "what", "does", "with", "that", "this", "from", "when", "then", "have", "which", "where", "their", "into", "under",
    "about", "need", "want", "understand", "learn", "explain", "work", "works", "between", "some", "more", "over", "text",
}
# words that name a field or a kind of result rather than the idea itself ("imitation learning" is not Q-learning)
GENERIC = {
    "learning", "theory", "theorem", "theorems", "proof", "proofs", "model", "models", "method", "methods", "deep",
    "network", "networks", "neural", "analysis", "basic", "basics", "introduction", "intro", "machine", "algorithm",
    "algorithms", "problem", "problems", "function", "functions", "property", "properties", "concept", "general",
    "applied", "using", "based", "simple", "lemma", "definition", "result", "results", "math", "mathematics",
}


def _stem(w: str) -> str:
    w = re.sub(r"ices$", "ix", w)
    if w.endswith("s") and not w.endswith("ss") and len(w) > 4:
        w = w[:-1]
    return w[:6]


def goal_terms(text: str) -> set[str]:
    """Distinctive word stems of a goal (≥3 letters, no stop or field words)."""
    return {_stem(w) for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP and w not in GENERIC}


def _node_terms(n: dict[str, Any]) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]{3,}", f"{n['title']} {n['id'].replace('_', ' ')} {n['statement_latex']} {n.get('intuition_summary', '')}".lower())}


def match_goal(nodes: list[dict[str, Any]], goal: str) -> Optional[dict[str, Any]]:
    terms = goal_terms(goal)
    pool = [n for n in nodes if n["node_type"] != "BUGGY_RULE"]
    if not terms or not pool:
        return None
    node_terms = {n["id"]: _node_terms(n) for n in pool}
    df = {t: sum(t in ts for ts in node_terms.values()) for t in terms}
    weight = {t: math.log((len(pool) + 1) / (df[t] + 1)) + 1.0 for t in terms}
    total = sum(weight.values())
    best, best_key = None, (0.0, 0)
    for n in pool:
        shared = terms & node_terms[n["id"]]
        cover = sum(weight[t] for t in shared) / total
        in_title = len(shared & {_stem(w) for w in re.findall(r"[a-z]{3,}", (n["title"] + " " + n["id"]).lower())})
        if cover >= COVERAGE and (cover, in_title) > best_key:
            best, best_key = n, (cover, in_title)
    return best


def premise_candidates(nodes: list[dict[str, Any]], goal: str, own_id: str, k: int = 2) -> list[str]:
    """FR4: provisional premises for a goal node made without an engine — at least one shared distinctive term."""
    terms = goal_terms(goal)
    scored = sorted(((len(terms & _node_terms(n)), n["id"]) for n in nodes
                     if n["id"] != own_id and n["node_type"] not in ("BUGGY_RULE", "COUNTEREXAMPLE")), reverse=True)
    return [i for s, i in scored[:k] if s >= 1]


# ------------------------------------------------------------------ FR3 notes grounding
def notes_passages(goal: str, attached: list[str]) -> list[dict[str, str]]:
    """[{label, text}]: attached files' best blocks (else their opening), otherwise the 3 best workspace blocks."""
    terms = goal_terms(goal)

    def score(b: dict[str, Any]) -> int:
        hay = (b["title"] + " " + b["body"]).lower()
        return sum(hay.count(t) for t in terms)

    out: list[dict[str, str]] = []
    if attached:
        blocks: list[tuple[int, dict[str, str]]] = []
        for rel in attached:
            try:
                data = tools.read_workspace_file(rel)
            except Exception:
                continue
            if data["blocks"]:
                blocks += [(score(b), {"label": f"{rel}:{b['line']}", "text": f"[{b['env']}] {b['title']}\n{b['body']}"})
                           for b in data["blocks"]]
            else:
                blocks.append((1, {"label": rel, "text": data["content"][:2500]}))
        blocks.sort(key=lambda x: -x[0])
        out = [b for _, b in blocks[:3]]
    elif terms:
        out = [{"label": f"{b['path']}:{b['line']}", "text": f"[{b['env']}] {b['title']}\n{b['body']}"}
               for b in tools.corpus_search(" ".join(sorted(terms)), max_blocks=6) if score(b) >= 2][:3]
    budget = NOTES_CHARS // max(1, len(out))
    return [{"label": p["label"], "text": p["text"][:budget]} for p in out]


def notes_context(passages: list[dict[str, str]]) -> str:
    if not passages:
        return ""
    return "\n\nFrom the learner's notes (prefer their notation; cite the label when you use one):\n" + "\n\n".join(
        f"[{p['label']}]\n{p['text']}" for p in passages)


# ------------------------------------------------------------------ FR2 decomposition
class TopicIdea(BaseModel):
    key: str
    title: str
    node_type: str = "PROPOSITION"
    statement_latex: str = ""
    intuition_summary: str = ""
    existing_node_id: str = ""


class TopicEdge(BaseModel):
    premises: list[str] = Field(default_factory=list)
    conclusion: str
    reasoning: str = ""


class LLMTopicMap(BaseModel):
    goal: str
    ideas: list[TopicIdea] = Field(default_factory=list)
    edges: list[TopicEdge] = Field(default_factory=list)


def validate(m: LLMTopicMap, node_ids: set[str]) -> Optional[LLMTopicMap]:
    seen: set[str] = set()
    ideas: list[TopicIdea] = []
    for i, idea in enumerate(m.ideas[:8]):
        key = re.sub(r"\W+", "_", idea.key or f"i{i + 1}") or f"i{i + 1}"
        if key in seen or not idea.title.strip():
            continue
        seen.add(key)
        idea.key = key
        idea.node_type = idea.node_type if idea.node_type in NODE_TYPES else "PROPOSITION"
        idea.existing_node_id = idea.existing_node_id if idea.existing_node_id in node_ids else ""
        idea.statement_latex = idea.statement_latex or idea.title
        idea.intuition_summary = idea.intuition_summary or idea.statement_latex[:300]
        ideas.append(idea)
    m.goal = re.sub(r"\W+", "_", m.goal)
    if len(ideas) < 3 or m.goal not in seen:
        return None
    m.ideas = ideas
    # existing ideas keep their own derivations: new edges may only conclude in new ideas, and never close a cycle
    new_keys = {i.key for i in ideas if not i.existing_node_id}
    parents: dict[str, set[str]] = {}

    def reaches(a: str, b: str) -> bool:   # is b an ancestor of a (or a itself)?
        stack, seen_ = [a], set()
        while stack:
            v = stack.pop()
            if v == b:
                return True
            if v not in seen_:
                seen_.add(v)
                stack += parents.get(v, ())
        return False

    edges: list[TopicEdge] = []
    for e in m.edges:
        if e.conclusion not in new_keys:
            continue
        prem = [p for p in dict.fromkeys(e.premises) if p in seen and not reaches(p, e.conclusion)]
        if prem:
            parents.setdefault(e.conclusion, set()).update(prem)
            edges.append(TopicEdge(premises=prem, conclusion=e.conclusion, reasoning=e.reasoning[:600]))
    if m.goal in new_keys and m.goal not in parents:   # the plan walks the goal's ancestors, so it needs some
        prem = [i.key for i in ideas if i.key != m.goal and not reaches(i.key, m.goal)]
        if prem:
            edges.append(TopicEdge(premises=prem, conclusion=m.goal, reasoning=r"\text{Topic map}"))
    m.edges = edges
    return m


def _known(nodes: list[dict[str, Any]], goal: str, k: int = 40) -> str:
    terms = goal_terms(goal)
    ranked = sorted((n for n in nodes if n["node_type"] != "BUGGY_RULE"), key=lambda n: -len(terms & _node_terms(n)))
    return "\n".join(f"- `{n['id']}`: {n['title']}" for n in ranked[:k])


async def build(session_id: str, goal: str, passages: list[dict[str, str]],
                nodes: list[dict[str, Any]]) -> tuple[Optional[LLMTopicMap], str]:
    """(validated map or None, engine label). Logged as an ONTOLOGIST_EXTRACTOR artifact."""
    node_ids = {n["id"] for n in nodes}
    user = (f"Learner's goal: {goal}\n\nIdeas already in the learner's graph (reuse these ids where they match):\n"
            f"{_known(nodes, goal)}{notes_context(passages)}")
    out: dict[str, Any] = {"map": None, "engine": "deterministic"}

    async def work() -> tuple[str, str]:
        for _ in range(2):
            res = await llm.complete_json(prompts.TOPIC_MAPPER, user, max_tokens=3500, timeout=MAP_TIMEOUT_S)
            out["engine"] = res.engine
            if not res.data:
                break
            try:
                m = validate(LLMTopicMap.model_validate(res.data), node_ids)
            except Exception:
                continue
            if m:
                out["map"] = m
                return json.dumps(m.model_dump(), indent=1), f"Topic map · {len(m.ideas)} ideas · {goal[:40]}"
        return f"No map (engine: {out['engine']}); using a single goal idea.", f"Topic map unavailable · {goal[:40]}"

    await subagents.run_agent("ONTOLOGIST_EXTRACTOR", session_id, f"Mapping topic: {goal[:50]}", "graph_diff", work)
    return out["map"], out["engine"]


def insert(conn, m: LLMTopicMap, session_id: str) -> tuple[str, list[str]]:
    """Write the map's new ideas and edges; returns (goal node id, created node ids)."""
    key_to_node: dict[str, str] = {}
    created: list[str] = []
    for idea in m.ideas:
        nid = idea.existing_node_id
        if not nid:
            base = f"t_{subagents._slug(idea.title, 36)}"
            nid, k = base, 2
            while db.node_exists(conn, nid):
                nid, k = f"{base}_{k}", k + 1
            db.upsert_node(conn, {
                "id": nid, "title": idea.title[:120], "node_type": idea.node_type, "statement_latex": idea.statement_latex,
                "intuition_summary": idea.intuition_summary, "formal_proof_sketch_latex": "",
                "domain_cluster": subagents.guess_domain(f"{idea.title} {idea.statement_latex}"),
                "logical_depth": 0, "last_reviewed_at": db.now_iso(), "created_in_session_id": session_id,
            })
            created.append(nid)
        key_to_node[idea.key] = nid
    for e in m.edges:
        prem = [key_to_node[p] for p in e.premises]
        concl = key_to_node[e.conclusion]
        if concl not in prem:
            eid = f"he_topic_{hashlib.md5(json.dumps([prem, concl]).encode()).hexdigest()[:10]}"
            db.insert_edge(conn, "DEDUCTION", prem, concl, e.reasoning or r"\text{Topic map}", "", session_id, edge_id=eid)
    db.recompute_depths(conn)
    return key_to_node[m.goal], created
