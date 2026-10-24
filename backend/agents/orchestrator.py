"""The 6-mode pedagogical state machine and the Δ step-size controller (ARCHITECTURE_SPEC.md §4.2).

Modes: PROBE, PRODUCTIVE_FAILURE, TEACH, PRACTICE, REFEREE_DUEL/PROOF_REFEREE, REFEREE_DUEL/FEYNMAN_STUDENT.

The session row is the POMDP controller state: `dependency_plan` (ordered plan items with statuses and
session-local beliefs), `history_steps` (one summary per finished step) and `active_step` (the StepPayload
shown to the learner plus a hidden `_meta` with answer keys, never sent to the client).
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from fastapi import HTTPException

from .. import cognitive_math as cm
from .. import config, db, demos, llm, tools
from ..hub import hub
from ..models import LLMStepContent
from ..papers import mapper as paper_mapper
from ..papers import service as papers
from . import prompts, subagents
from .content_bank import CONTENT

MAX_PROBES = 4
MAX_PLAN = 7
TEACH_MODES = ("PROBE", "PRODUCTIVE_FAILURE", "TEACH")
RUNG_LABELS = {"R0": "Dimensional / Type-Shape Check", "R1": "Attention Pointer", "R2": "Cue Prime",
               "R3": "Scalar / 2D Base Case", "R4": "Worked Isomorphic Analog"}
RUNG_ORDER = ["R0", "R1", "R2", "R3", "R4"]
DEMO_TARGETS = {d["id"]: d["target_node_ids"] for d in demos.DEMO_SEED}


# ------------------------------------------------------------------ content resolution
def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())} - {"with", "that", "this", "from", "when", "then", "have",
                                                                   "which", "where", "their", "into", "under", "text"}


def _stable_order(seq: list[Any], key: str) -> list[Any]:
    return sorted(seq, key=lambda x: hashlib.md5((key + json.dumps(x, sort_keys=True, default=str)).encode()).hexdigest())


def generic_content(node: dict[str, Any], conn) -> dict[str, Any]:
    """Deterministic content for nodes without a hand-written bank entry (imported or LLM-extracted nodes)."""
    others = [n for n in db.all_nodes(conn) if n["id"] != node["id"] and n["node_type"] != "BUGGY_RULE"]
    same = [n for n in others if n["domain_cluster"] == node["domain_cluster"]] or others
    distractors = _stable_order(same, node["id"])[:3]
    opts = [{"id": "x", "label": node["statement_latex"][:400], "correct": True}] + \
           [{"id": "x", "label": d["statement_latex"][:400], "correct": False} for d in distractors]
    opts = _stable_order(opts, node["id"] + "probe")
    letters = "ABCD"
    options = [{"id": letters[i], "label": o["label"]} for i, o in enumerate(opts)]
    correct = letters[[i for i, o in enumerate(opts) if o["correct"]][0]]
    key_terms = sorted(_words(node["statement_latex"] + " " + node["title"]), key=len, reverse=True)[:4]
    groups = [[t] for t in key_terms[:3]] or [[node["title"].lower()[:12]]]
    sketch = node["formal_proof_sketch_latex"] or "Trace each hypothesis to the step where it is used."
    reading = (f"**Start concrete.** {node['intuition_summary']}\n\n$$ {node['statement_latex'][:500]} $$\n\n"
               f"**Why.** {sketch[:500]}\n\n*Self-explanation:* which single hypothesis, if dropped, breaks the statement?")
    reading = " ".join(reading.split(" ")[:178])
    practice = {}
    for lvl in (1, 2, 3, 4):
        frame = {1: "State and justify", 2: "Recognise, in renamed notation,", 3: "Contrast with its nearest neighbour and apply",
                 4: "Find the silently violated hypothesis in a situation that misuses"}[lvl]
        practice[lvl] = {
            "prompt": f"{frame} the principle behind this situation: {node['intuition_summary'][:300]}",
            "answer_summary": node["statement_latex"][:500], "concept_groups": groups, "verify_code": "",
            "hints": {"R0": "Before anything else: what are the types/shapes of every object involved, and what happens in the limiting cases?",
                      "R1": "Look again at this part of your reasoning: “{quote}”. Which assumption does it rely on?",
                      "R2": f"Which earlier idea about *{(distractors[0]['title'] if distractors else node['title'])}* is relevant here?",
                      "R3": "Reduce to the smallest instance (one dimension, two elements). What does the claim say there?",
                      "R4": f"Worked analog: {node['intuition_summary'][:200]} — now transfer the same move to the problem."},
        }
    return {
        "probe": {"prompt": f"Which statement precisely captures **{node['title']}**? Write your own version first.",
                  "options": options, "correct": correct, "explanation": node["statement_latex"]},
        "predict": {"prompt": f"Before reading: pick the simplest concrete case of “{node['title']}” and predict what happens there."},
        "reading": reading,
        "check": {"prompt": f"Transfer check: which of these is exactly the content of “{node['title']}” (as opposed to a neighbouring fact)?",
                  "options": options, "correct": correct, "explanation": node["statement_latex"]},
        "productive_failure": {"prompt": f"Without any instruction: {node['intuition_summary']} Try to explain why, and list every approach you attempt.",
                               "canonical_insight": node["statement_latex"]},
        "practice": practice, "referee": None, "feynman": None, "misconceptions": [],
    }


def content_for(node: dict[str, Any], conn) -> tuple[dict[str, Any], str]:
    c = CONTENT.get(node["id"])
    if c:
        return c, node["id"]
    return generic_content(node, conn), node["id"]


def nearest_bank_node(node: dict[str, Any], conn, need: str) -> str:
    """Closest node (same domain, word overlap) that has bank content with a non-empty `need` section."""
    if CONTENT.get(node["id"], {}).get(need):
        return node["id"]
    w = _words(node["statement_latex"] + node["title"])
    best, score = None, -1.0
    for nid, c in CONTENT.items():
        if not c.get(need):
            continue
        other = db.get_node(conn, nid)
        if not other:
            continue
        s = len(w & _words(other["statement_latex"] + other["title"])) + (3 if other["domain_cluster"] == node["domain_cluster"] else 0)
        if s > score:
            best, score = nid, s
    return best or next(iter(CONTENT))


def match_goal_node(conn, goal: str) -> Optional[dict[str, Any]]:
    gw = _words(goal)
    best, score = None, 0
    for n in db.all_nodes(conn):
        if n["node_type"] == "BUGGY_RULE":
            continue
        s = len(gw & _words(n["title"] + " " + n["id"].replace("_", " "))) * 2 + len(gw & _words(n["statement_latex"]))
        if s > score:
            best, score = n, s
    return best if score >= 2 else None


# ------------------------------------------------------------------ plan
def build_plan(conn, target_id: str) -> list[dict[str, Any]]:
    edges = db.all_edges(conn)
    parents: dict[str, set[str]] = {}
    for e in edges:
        if e["edge_type"] == "DEDUCTION":
            parents.setdefault(e["conclusion_node_id"], set()).update(e["premise_node_ids"])
    seen, frontier = {target_id}, [target_id]
    while frontier:
        nxt = []
        for v in frontier:
            for p in parents.get(v, ()):
                if p not in seen:
                    seen.add(p)
                    nxt.append(p)
        frontier = nxt
    nodes = [db.get_node(conn, i) for i in seen]
    nodes = [n for n in nodes if n]
    target = db.get_node(conn, target_id)
    ancestors = sorted([n for n in nodes if n["id"] != target_id], key=lambda n: (-n["logical_depth"], n["id"]))
    ancestors = ancestors[:MAX_PLAN - 1]
    ordered = sorted(ancestors, key=lambda n: (n["logical_depth"], n["id"])) + [target]
    return [{"node_id": n["id"], "title": n["title"], "depth": n["logical_depth"], "status": "pending", "remedial": False,
             "spliced_reason": "", "belief": n["bkt_p_mastery"], "attempts": 0} for n in ordered]


def plan_edges(conn, plan: list[dict[str, Any]]) -> list[tuple[list[str], str]]:
    ids = {p["node_id"] for p in plan}
    return [(e["premise_node_ids"], e["conclusion_node_id"]) for e in db.all_edges(conn)
            if e["edge_type"] == "DEDUCTION" and e["conclusion_node_id"] in ids]


# ------------------------------------------------------------------ step construction
def _payload(session: dict[str, Any], kind: str, phase: Optional[str], node: Optional[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    idx = session["current_step_index"]
    p = {
        "step_id": f"{session['id']}:{idx}:{kind}", "step_index": idx, "kind": kind, "phase": phase,
        "target_node_ids": [node["id"]] if node else [], "cue_level": 1, "title": "", "prompt_latex": "",
        "body_markdown": "", "options": [], "options_locked": False, "requires_raw_prediction": False,
        "proof_steps": [], "student_persona": "", "buggy_rule_id": None, "duel_transcript": [],
        "boundary_conditions_total": 0, "boundary_conditions_met": [], "demo_artifact_id": None, "svg_artifact_id": None,
        "eig_table": [], "rationale": "", "delta": session["step_velocity_delta"], "hints_unlocked": [], "chunks": [],
        "contrastive_pair_node_id": None, "generated_by": "deterministic", "_meta": {},
    }
    p.update(kw)
    return p


# ------------------------------------------------------------------ paper grounding (docs/specs/paper-reading FR5)
_paper_norm_cache: dict[str, str] = {}


def paper_link(node_id: str) -> Optional[dict[str, Any]]:
    with db.ro() as conn:
        return papers.paper_for_node(conn, node_id)


def paper_context(node: dict[str, Any]) -> str:
    """For an idea that came from a paper: the anchored passage, the verbatim quote and the paper's notation."""
    link = paper_link(node["id"])
    if not link:
        return ""
    doc = papers.load_doc(link["paper_id"])
    passage = paper_mapper.passage_for(doc, link["anchor"], link["quote"]) if doc else ""
    return prompts.paper_grounding(link["paper"]["title"], link["anchor"], link["quote"], passage,
                                   link["paper"]["map"].get("notation"))


def ground_check(body: str, paper_id: str) -> str:
    """Flag quoted lines (> …) that do not occur in the paper, so a paraphrase is never presented as the paper's words."""
    if paper_id not in _paper_norm_cache:
        doc = papers.load_doc(paper_id)
        _paper_norm_cache[paper_id] = paper_mapper._norm(doc.full_text() + " " + " ".join(b.body for b in doc.blocks)) if doc else ""
    norm = _paper_norm_cache[paper_id]
    quoted = [re.sub(r"\(?§[^)]*\)\s*$|—.*$", "", ln.lstrip("> ").strip()) for ln in body.splitlines() if ln.lstrip().startswith(">")]
    bad = [q for q in quoted if len(q) > 25 and norm and not paper_mapper.quote_in_text(q, norm)]
    if bad:
        body += "\n\n*One quoted line above could not be found in the paper; read it as a paraphrase.*"
    return body


async def _llm_step(mode_key: str, node: dict[str, Any], session: dict[str, Any], extra: str = "") -> Optional[LLMStepContent]:
    res = await llm.complete_json(
        prompts.MODE_PROMPTS[mode_key],
        prompts.node_context(node) + "\n" + prompts.delta_instruction(session["step_velocity_delta"]) +
        f"\nSession goal: {session['target_goal']}\n{extra}" + paper_context(node), max_tokens=1800)
    if not res.data:
        return None
    try:
        c = LLMStepContent.model_validate(res.data)
    except Exception:
        return None
    if mode_key in ("PROBE", "CHECK"):
        if len(c.options) < 3 or c.correct_option_id not in {o.id for o in c.options}:
            return None
    c.rationale = (c.rationale + f" [engine: {res.engine}]").strip()
    return c


def _mc_options(raw: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"id": o["id"], "label_latex": o.get("label") or o.get("label_latex", "")} for o in raw]


async def step_probe(session: dict[str, Any], node: dict[str, Any], eig_rows: list[dict[str, Any]], conn) -> dict[str, Any]:
    c, _ = content_for(node, conn)
    top = eig_rows[0] if eig_rows else None
    rationale = (f"Chosen by expected information gain: EIG={top['eig']:.3f} (H={top['entropy']:.2f} bits, "
                 f"{top['unprobed_ancestors']} unprobed ancestors, {top['unprobed_descendants']} unprobed descendants).") if top else ""
    llm_c = await _llm_step("PROBE", node, session, f"Why this node: {rationale}")
    if llm_c:
        return _payload(session, "PROBE", "PROBE", node, title=llm_c.title, prompt_latex=llm_c.prompt_latex,
                        options=[o.model_dump() for o in llm_c.options], options_locked=True, requires_raw_prediction=True,
                        eig_table=eig_rows, rationale=rationale + " " + llm_c.rationale, generated_by="llm",
                        _meta={"correct": llm_c.correct_option_id, "explanation": llm_c.rationale})
    return _payload(session, "PROBE", "PROBE", node, title=f"Probe · {node['title']}", prompt_latex=c["probe"]["prompt"],
                    options=_mc_options(c["probe"]["options"]), options_locked=True, requires_raw_prediction=True,
                    eig_table=eig_rows, rationale=rationale,
                    _meta={"correct": c["probe"]["correct"], "explanation": c["probe"]["explanation"]})


async def step_productive_failure(session: dict[str, Any], node: dict[str, Any], conn) -> dict[str, Any]:
    c, _ = content_for(node, conn)
    llm_c = await _llm_step("PRODUCTIVE_FAILURE", node, session)
    prompt = llm_c.prompt_latex if llm_c else c["productive_failure"]["prompt"]
    insight = llm_c.rationale if llm_c else c["productive_failure"]["canonical_insight"]
    return _payload(session, "PRODUCTIVE_FAILURE", "PRODUCTIVE_FAILURE", node, title=f"Productive failure · {node['title']}",
                    prompt_latex=prompt, requires_raw_prediction=True, generated_by="llm" if llm_c else "deterministic",
                    rationale="Kapur (2008): generating (even failed) solutions before instruction primes the structure the "
                              "canonical solution will fill. Write every approach you try — dead ends are data.",
                    _meta={"insight": insight})


async def step_predict(session: dict[str, Any], node: dict[str, Any], conn, rationale: str = "") -> dict[str, Any]:
    c, _ = content_for(node, conn)
    llm_c = await _llm_step("PREDICT", node, session)
    return _payload(session, "PREDICT", "PREDICT", node, title=f"Predict · {node['title']}",
                    prompt_latex=llm_c.prompt_latex if llm_c else c["predict"]["prompt"], requires_raw_prediction=True,
                    options_locked=False, generated_by="llm" if llm_c else "deterministic",
                    rationale=rationale or "Law 2/3: commit to a prediction about the concrete base case before reading.")


async def _visual_for(session: dict[str, Any], node: dict[str, Any], conn) -> tuple[Optional[str], Optional[str]]:
    for demo_id, targets in DEMO_TARGETS.items():
        if node["id"] in targets and db.get_artifact(conn, demo_id):
            return demo_id, None
    for a in db.list_artifacts(conn, agent_name="SVG_DIAGRAM_MAKER", limit=200):
        if a["status"] == "COMPLETED" and a["title"] == f"Diagram · {node['title']}":
            return None, a["id"]
    art = await subagents.make_svg(session["id"], node)
    return None, art["id"]


async def step_reading(session: dict[str, Any], node: dict[str, Any], conn, compressed: bool = False) -> dict[str, Any]:
    c, _ = content_for(node, conn)
    llm_c = await _llm_step("READING", node, session)
    body = llm_c.body_markdown if (llm_c and llm_c.body_markdown) else c["reading"]
    link = paper_link(node["id"])
    if link and llm_c and llm_c.body_markdown:
        body = ground_check(body, link["paper_id"])
    elif link and link["quote"]:
        body = f"> {link['quote']}\n>\n> — *{link['paper']['title']}*, § {link['anchor']}\n\n{body}"
    demo_id, svg_id = await _visual_for(session, node, conn)
    note = ("Δ ≥ 1.5: trivial algebraic bridges compressed — the prediction step was skipped." if compressed else
            "Highlight any sentence or click any equation to attach a thinking-while-reading note.")
    return _payload(session, "READING", "READING", node, title=f"Read · {node['title']}", body_markdown=body,
                    prompt_latex="", demo_artifact_id=demo_id, svg_artifact_id=svg_id, rationale=note,
                    generated_by="llm" if llm_c else "deterministic")


async def step_check(session: dict[str, Any], node: dict[str, Any], conn, cue_level: int = 2, rationale: str = "") -> dict[str, Any]:
    c, _ = content_for(node, conn)
    llm_c = await _llm_step("CHECK", node, session, f"Cue level: {cue_level}")
    if llm_c:
        return _payload(session, "CHECK", "CHECK", node, title=llm_c.title, prompt_latex=llm_c.prompt_latex,
                        options=[o.model_dump() for o in llm_c.options], options_locked=True, requires_raw_prediction=True,
                        cue_level=cue_level, rationale=rationale, generated_by="llm",
                        _meta={"correct": llm_c.correct_option_id, "explanation": llm_c.rationale})
    if cue_level >= 3:
        lvl = c["practice"][3]
        prompt = c["check"]["prompt"] + "\n\n*Synthesis leap (Δ = 2.5):* before choosing, connect this to: " + lvl["prompt"][:300]
    else:
        prompt = c["check"]["prompt"]
    return _payload(session, "CHECK", "CHECK", node, title=f"Check · {node['title']}", prompt_latex=prompt,
                    options=_mc_options(c["check"]["options"]), options_locked=True, requires_raw_prediction=True,
                    cue_level=cue_level, rationale=rationale or "Disguised-notation transfer check (cue level 2).",
                    _meta={"correct": c["check"]["correct"], "explanation": c["check"]["explanation"]})


async def step_practice(session: dict[str, Any], node: dict[str, Any], conn, cue_level: int,
                        problem: Optional[dict[str, Any]] = None, pair_id: Optional[str] = None,
                        rationale: str = "") -> dict[str, Any]:
    c, _ = content_for(node, conn)
    lvl = c["practice"][max(1, min(4, cue_level))]
    prompt = lvl["prompt"]
    groups, verify_code, answer = lvl["concept_groups"], lvl["verify_code"], lvl["answer_summary"]
    gen = "deterministic"
    if problem:
        prompt = f"**{problem['title'] or 'Imported problem'}** (from `{problem['path']}`:{problem['line']})\n\n{problem['body']}"
    else:
        res = await llm.complete_json(prompts.MODE_PROMPTS["PRACTICE"], prompts.node_context(node) +
                                      f"\nCue level: {cue_level}\n" + prompts.delta_instruction(session["step_velocity_delta"]) +
                                      paper_context(node), max_tokens=1800)
        d = res.data or {}
        if isinstance(d.get("prompt_latex"), str) and isinstance(d.get("concept_groups"), list) and d["concept_groups"]:
            prompt, answer = d["prompt_latex"], str(d.get("answer_summary", answer))
            groups = [[str(s) for s in g] for g in d["concept_groups"] if isinstance(g, list) and g] or groups
            verify_code = str(d.get("verify_code", "")) or verify_code
            gen = "llm"
    if pair_id:
        peer = db.get_node(conn, pair_id)
        if peer:
            pc, _ = content_for(peer, conn)
            prompt += (f"\n\n---\n**Contrastive pair.** Now the sibling situation: {pc['practice'][max(1, min(4, cue_level))]['prompt']}\n\n"
                       "Say which principle governs *each* situation and name the exact condition that discriminates them.")
            groups = groups + pc["practice"][max(1, min(4, cue_level))]["concept_groups"][:2]
    return _payload(session, "PRACTICE_CHUNK", "PRACTICE_CHUNK", node, title=f"Practice · cue level {cue_level}",
                    prompt_latex=prompt, cue_level=cue_level, contrastive_pair_node_id=pair_id, generated_by=gen,
                    rationale=rationale or "Submit raw thinking in chunks (Shift+Enter). Hints unlock one rung at a time.",
                    _meta={"concept_groups": groups, "verify_code": verify_code, "answer_summary": answer,
                           "hints": lvl["hints"], "bank_node": node["id"], "cue_level": cue_level})


async def step_referee(session: dict[str, Any], node: dict[str, Any], conn) -> dict[str, Any]:
    src_id = nearest_bank_node(node, conn, "referee")
    ref = CONTENT[src_id]["referee"]
    gen = "deterministic"
    res = await llm.complete_json(prompts.MODE_PROMPTS["PROOF_REFEREE"], prompts.node_context(node), max_tokens=2000)
    d = res.data or {}
    if isinstance(d.get("steps"), list) and len(d["steps"]) == 5 and isinstance(d.get("flawed_index"), int) and 1 <= d["flawed_index"] <= 5:
        ref = {"claim": str(d.get("claim", "")), "steps": [str(s) for s in d["steps"]], "flawed_index": d["flawed_index"],
               "violated_keywords": [str(k) for k in d.get("violated_keywords", [])] or ["hypothesis"],
               "explanation": str(d.get("explanation", "")), "counterexample": str(d.get("counterexample", ""))}
        gen = "llm"
    target = db.get_node(conn, src_id) if src_id != node["id"] and gen == "deterministic" else node
    return _payload(session, "REFEREE", "REFEREE", target, title=f"Proof referee · {target['title']}",
                    prompt_latex=f"**Claim.** {ref['claim']}\n\nExactly one step below hides a fallacy. Click it, name the violated "
                                 "hypothesis, and give a minimal counterexample.",
                    proof_steps=[{"index": i + 1, "text_latex": s} for i, s in enumerate(ref["steps"])],
                    cue_level=4, generated_by=gen, rationale="Adversarial cue (level 4): find the silently violated premise.",
                    _meta={"flawed_index": ref["flawed_index"], "violated_keywords": ref["violated_keywords"],
                           "explanation": ref["explanation"], "counterexample": ref["counterexample"]})


async def step_feynman(session: dict[str, Any], node: dict[str, Any], conn) -> dict[str, Any]:
    src_id = nearest_bank_node(node, conn, "feynman")
    f = CONTENT[src_id]["feynman"]
    target = db.get_node(conn, src_id) or node
    return _payload(session, "FEYNMAN", "REFEREE", target, title=f"Feynman duel · {target['title']}",
                    prompt_latex=f"Explain **{target['title']}** to the student until they cannot find an edge case.",
                    student_persona=f["persona"], buggy_rule_id=f.get("buggy_rule_id"),
                    duel_transcript=[{"role": "student", "text": f["opening"], "timestamp_ms": 0}],
                    boundary_conditions_total=len(f["boundary_conditions"]), boundary_conditions_met=[], cue_level=4,
                    rationale="Teaching a misconception-holder forces you to state the exact boundary conditions.",
                    _meta={"conditions": f["boundary_conditions"], "persona": f["persona"]})


def step_complete(session: dict[str, Any]) -> dict[str, Any]:
    done = sum(1 for p in session["dependency_plan"] if p["status"] in ("done", "probed_mastered"))
    return _payload(session, "COMPLETE", None, None, title="Session complete",
                    body_markdown=f"All {len(session['dependency_plan'])} plan nodes handled ({done} mastered or completed). "
                                  "The ontologist has exported a session note to `workspace/notes/`.",
                    rationale="Spaced retrieval will bring these nodes back when they enter the Bjork window.")


# ------------------------------------------------------------------ paper sessions (docs/specs/paper-reading FR5)
def _paper(conn, session: dict[str, Any]) -> dict[str, Any]:
    p = papers.get(conn, session.get("_controller", {}).get("paper_id", ""))
    if not p:
        raise HTTPException(404, "paper not found")
    return p


def _main_node_id(conn, paper: dict[str, Any], plan: list[dict[str, Any]]) -> str:
    return next((l["node_id"] for l in papers.links(conn, paper["id"]) if l["role"] == "main_result"), plan[-1]["node_id"])


def step_skim(session: dict[str, Any], paper: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    doc = papers.load_doc(paper["id"])
    secs = [x.title for x in doc.sections if x.level == 1][:14] if doc else []
    abstract = paper["abstract"] or (doc.abstract if doc else "")
    prompt = ("**Pass 1 · skim.** From the abstract and the section list alone: what do you think the main result is, "
              "and what would have to be true for it to hold? Write your own guess; you'll see it again at the end.\n\n"
              f"> {abstract}\n\n" + ("**Sections:** " + " · ".join(secs) if secs else ""))
    return _payload(session, "PREDICT", "PREDICT", node, title=f"Skim · {paper['title'][:90]}", prompt_latex=prompt,
                    requires_raw_prediction=True, generated_by="deterministic",
                    rationale="Three-pass reading (Keshav 2007), pass 1: commit to a guess about the contribution before "
                              "reading the details. Pretesting improves what you take from the reading.",
                    _meta={"paper_skim": True, "hist_kind": "SKIM"})


async def step_paper_referee(session: dict[str, Any], node: dict[str, Any], paper: dict[str, Any]) -> Optional[dict[str, Any]]:
    ka = paper["map"].get("key_argument") or {}
    if not ka.get("steps"):
        return None
    assumptions = "; ".join(a["label"] for a in paper["map"].get("assumptions_for_main", []))
    res = await llm.complete_json(prompts.PAPER_REFEREE,
                                  f"Paper: {paper['title']}\nCentral claim: {ka.get('claim', '')}\nArgument steps:\n" +
                                  "\n".join(f"{i + 1}. {st}" for i, st in enumerate(ka["steps"])) +
                                  f"\nAssumptions the result needs: {assumptions}", max_tokens=2000)
    d = res.data or {}
    if not (isinstance(d.get("steps"), list) and len(d["steps"]) == 5 and isinstance(d.get("flawed_index"), int)
            and 1 <= d["flawed_index"] <= 5):
        return None
    return _payload(session, "REFEREE", "REFEREE", node, title=f"Find the flaw · {paper['title'][:80]}",
                    prompt_latex=f"**The paper's argument, with one step altered.** {d.get('claim') or ka.get('claim', '')}\n\n"
                                 "Exactly one step below no longer follows. Click it, name what it breaks, and give a case "
                                 "where it fails.",
                    proof_steps=[{"index": i + 1, "text_latex": str(st)} for i, st in enumerate(d["steps"])],
                    cue_level=4, generated_by="llm",
                    rationale="Pass 3 · critical reading: re-derive the paper's key argument well enough to spot a planted flaw.",
                    _meta={"flawed_index": d["flawed_index"], "violated_keywords": [str(k) for k in d.get("violated_keywords", [])] or ["assumption"],
                           "explanation": str(d.get("explanation", "")), "counterexample": str(d.get("counterexample", ""))})


def step_paper_feynman(session: dict[str, Any], node: dict[str, Any], paper: dict[str, Any]) -> Optional[dict[str, Any]]:
    assumptions = paper["map"].get("assumptions_for_main") or []
    if not assumptions:
        return None
    conds = [{"id": f"a{i + 1}", "label": a["label"], "keywords": a["keywords"], "challenge": a["challenge"]}
             for i, a in enumerate(assumptions)]
    claim = (paper["map"].get("key_argument") or {}).get("claim") or node["title"]
    persona = ("A student who only read the abstract and believes the paper's main result holds with no conditions at all; "
               "they push on every edge case until you state each assumption precisely.")
    opening = f"I skimmed it: {claim} So that just always works, right? Why would anyone need conditions?"
    return _payload(session, "FEYNMAN", "REFEREE", node, title=f"Explain it · {paper['title'][:80]}",
                    prompt_latex=f"Explain the paper's main result to a sceptical student until they run out of edge cases.",
                    student_persona=persona, duel_transcript=[{"role": "student", "text": opening, "timestamp_ms": 0}],
                    boundary_conditions_total=len(conds), boundary_conditions_met=[], cue_level=4, generated_by="llm",
                    rationale="Pass 3 · explaining the result forces you to state every assumption it needs.",
                    _meta={"conditions": conds, "persona": persona})


def step_paper_complete(session: dict[str, Any], paper: dict[str, Any], conn) -> dict[str, Any]:
    u = papers.understanding(conn, paper["id"])
    contributions = paper["map"].get("contributions") or [paper["map"].get("summary", "")]
    top = papers.refs(conn, paper["id"])["reference"][:3]
    parts = []
    if paper["first_guess"]:
        parts.append(f"**Your first guess**\n\n> {paper['first_guess']}")
    parts.append("**What the paper shows**\n\n" + "\n".join(f"- {c}" for c in contributions if c))
    if u is not None:
        parts.append(f"**You now understand about {round(u * 100)}% of this paper's ideas.** Its key claims join your reviews.")
    if top:
        parts.append("**Read next**\n\n" + "\n".join(f"{i + 1}. {r['title']} — {r['why']}" for i, r in enumerate(top)))
    return _payload(session, "COMPLETE", None, None, title="Paper complete", body_markdown="\n\n".join(parts),
                    rationale="Sources are re-ranked against what you missed; open the paper for the full list.")


async def _paper_next(session: dict[str, Any], conn, meta: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Skim first, then probe the prerequisites; teaching then follows the normal predict → read → check loop."""
    paper = _paper(conn, session)
    plan, hist = session["dependency_plan"], session["history_steps"]
    if not meta.get("skim_done"):
        meta["skim_done"] = True
        return step_skim(session, paper, _node(conn, _main_node_id(conn, paper, plan)))
    if not meta.get("probing_done"):
        prereq = {l["node_id"] for l in papers.links(conn, paper["id"]) if l["role"] == "prerequisite"}
        sub = [p for p in plan if p["node_id"] in prereq]
        probed = [p["node_id"] for p in sub if p["status"] != "pending"]
        if sub and sum(1 for h in hist if h["kind"] == "PROBE") < MAX_PROBES:
            v, table = cm.select_next_probe_node({p["node_id"]: p["belief"] for p in sub}, plan_edges(conn, sub), probed)
            if v and table and table[0].eig >= 0.25:
                rows = [{"node_id": e.node_id, "title": next(p["title"] for p in sub if p["node_id"] == e.node_id),
                         "p_mastery": e.p_mastery, "entropy": e.entropy, "unprobed_ancestors": e.unprobed_ancestors,
                         "unprobed_descendants": e.unprobed_descendants, "eig": e.eig} for e in table]
                return await step_probe(session, _node(conn, v), rows, conn)
        meta["probing_done"] = True
        for p in sub:
            if p["status"] == "pending" and p["belief"] >= 0.85:
                p["status"] = "probed_mastered"
    return None


async def _paper_finale(session: dict[str, Any], conn, meta: dict[str, Any]) -> dict[str, Any]:
    paper = _paper(conn, session)
    node = _node(conn, _main_node_id(conn, paper, session["dependency_plan"]))
    if not meta.get("referee_done"):
        meta["referee_done"] = True
        st = await step_paper_referee(session, node, paper)
        if st:
            return st
    if not meta.get("feynman_done"):
        meta["feynman_done"] = True
        st = step_paper_feynman(session, node, paper)
        if st:
            return st
    return step_paper_complete(session, paper, conn)


async def create_paper_session(paper_id: str) -> dict[str, Any]:
    """Start (or resume) reading a mapped paper: prerequisites first, then its ideas in dependency order."""
    with db.ro() as conn:
        paper = papers.get(conn, paper_id)
        if not paper:
            raise HTTPException(404, "paper not found")
        if paper["status"] != "MAPPED":
            raise HTTPException(409, f"the paper is not ready yet ({paper['status'].lower()})")
        if paper["session_id"]:
            old = db.load_session(conn, paper["session_id"])
            if old and old["status"] == "ACTIVE":
                return session_state(conn, old)
        ls = papers.links(conn, paper_id)
        nodes = {l["node_id"]: _node(conn, l["node_id"]) for l in ls}
    prereq = [l for l in ls if l["role"] == "prerequisite"][:5]
    ideas = sorted((l for l in ls if l["role"] != "prerequisite"),
                   key=lambda l: (papers.ROLE_ORDER[l["role"]], nodes[l["node_id"]]["logical_depth"], l["ord"]))[:10]
    plan = [{"node_id": l["node_id"], "title": nodes[l["node_id"]]["title"], "depth": nodes[l["node_id"]]["logical_depth"],
             "status": "pending", "remedial": False, "spliced_reason": "", "belief": nodes[l["node_id"]]["bkt_p_mastery"],
             "attempts": 0} for l in prereq + ideas]
    sid = db.new_id("sess")
    session = {"id": sid, "title": f"Read: {paper['title'][:70]}", "mode": "PROBE", "sub_mode": "PAPER",
               "target_goal": paper["title"], "attached_files": [], "step_velocity_delta": 1.0, "current_step_index": 0,
               "dependency_plan": plan, "active_step": {}, "history_steps": [], "status": "ACTIVE",
               "_controller": {"cue_level": 1, "pair_for": {}, "paper_id": paper_id}}
    with db.tx() as conn:
        db.insert_session(conn, session)
        papers.update(conn, paper_id, session_id=sid)
    with db.ro() as conn:
        session["active_step"] = await decide_next(session, conn)
    with db.tx() as conn:
        _persist(conn, session)
        state = session_state(conn, session)
    await hub.broadcast("session_updated", {"session_id": sid})
    return state


# ------------------------------------------------------------------ decide next step
def _node(conn, nid: str) -> dict[str, Any]:
    n = db.get_node(conn, nid)
    if not n:
        raise HTTPException(404, f"node {nid} not found")
    return n


async def decide_next(session: dict[str, Any], conn) -> dict[str, Any]:
    mode, sub = session["mode"], session["sub_mode"]
    plan, hist = session["dependency_plan"], session["history_steps"]
    last = hist[-1] if hist else None
    meta = session.setdefault("_controller", {})

    if mode == "PRACTICE":
        item = next((p for p in plan if p["status"] == "pending"), None)
        if not item:
            return step_complete(session)
        item["status"] = "active"
        node = _node(conn, item["node_id"])
        problem = None
        for pf in meta.get("problems", []):
            if not pf.get("used"):
                pf["used"] = True
                problem = pf
                break
        return await step_practice(session, node, conn, meta.get("cue_level", 1), problem,
                                   meta.get("pair_for", {}).get(item["node_id"]), item.get("spliced_reason", ""))

    if mode == "REFEREE_DUEL":
        item = next((p for p in plan if p["status"] == "pending"), None)
        if not item:
            return step_complete(session)
        item["status"] = "active"
        node = _node(conn, item["node_id"])
        return await (step_feynman(session, node, conn) if sub == "FEYNMAN_STUDENT" else step_referee(session, node, conn))

    # teaching modes
    if sub == "PAPER":
        st = await _paper_next(session, conn, meta)
        if st:
            return st
    if mode == "PRODUCTIVE_FAILURE" and not any(h["kind"] == "PRODUCTIVE_FAILURE" for h in hist):
        return await step_productive_failure(session, _node(conn, plan[-1]["node_id"]), conn)

    if mode == "PROBE" and not meta.get("probing_done"):
        probes = sum(1 for h in hist if h["kind"] == "PROBE")
        beliefs = {p["node_id"]: p["belief"] for p in plan}
        probed = [p["node_id"] for p in plan if p["status"] != "pending"]
        v, table = cm.select_next_probe_node(beliefs, plan_edges(conn, plan), probed)
        if probes < MAX_PROBES and v and table[0].eig >= 0.25:
            rows = [{"node_id": e.node_id, "title": next(p["title"] for p in plan if p["node_id"] == e.node_id),
                     "p_mastery": e.p_mastery, "entropy": e.entropy, "unprobed_ancestors": e.unprobed_ancestors,
                     "unprobed_descendants": e.unprobed_descendants, "eig": e.eig} for e in table]
            return await step_probe(session, _node(conn, v), rows, conn)
        meta["probing_done"] = True
        for p in plan:   # nodes inferred mastered by belief propagation are skipped by teaching
            if p["status"] == "pending" and p["belief"] >= 0.85:
                p["status"] = "probed_mastered"

    if last and last["kind"] == "PREDICT":
        return await step_reading(session, _node(conn, last["node_id"]), conn)
    if last and last["kind"] == "READING":
        return await step_check(session, _node(conn, last["node_id"]), conn, cue_level=2)

    item = next((p for p in plan if p["status"] in ("pending", "probed_unmastered", "active")), None)
    if not item:
        return await _paper_finale(session, conn, meta) if sub == "PAPER" else step_complete(session)
    item["status"] = "active"
    node = _node(conn, item["node_id"])
    delta = session["step_velocity_delta"]
    why = item.get("spliced_reason") or ""
    if delta >= 2.5 and not item.get("remedial"):
        return await step_check(session, node, conn, cue_level=3,
                                rationale="Δ = 2.5: maximal leap — straight to a synthesis check, no reading.")
    if delta >= 1.5 and not item.get("remedial"):
        return await step_reading(session, node, conn, compressed=True)
    return await step_predict(session, node, conn, rationale=why)


# ------------------------------------------------------------------ session lifecycle
def public_step(active: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in active.items() if k != "_meta"}


def session_state(conn, session: dict[str, Any]) -> dict[str, Any]:
    """Public view of a session as persisted (re-read so timestamps and JSON round-trips are authoritative)."""
    fresh = db.load_session(conn, session["id"]) or session
    return {"session": db.session_out({k: v for k, v in fresh.items() if k != "_controller"}),
            "active_step": public_step(fresh["active_step"]),
            "traces": db.session_traces(conn, session["id"])}


def _persist(conn, session: dict[str, Any]) -> None:
    # controller scratch state rides inside active_step._meta so the session schema stays exactly as specified
    session["active_step"].setdefault("_meta", {})["_controller"] = session.get("_controller", {})
    db.save_session(conn, session)


def _load(conn, session_id: str) -> dict[str, Any]:
    s = db.load_session(conn, session_id)
    if not s:
        raise HTTPException(404, "session not found")
    s["_controller"] = s["active_step"].get("_meta", {}).get("_controller", {})
    return s


async def create_session(req: dict[str, Any]) -> dict[str, Any]:
    mode, sub = req["mode"], req.get("sub_mode", "STANDARD")
    if mode == "REFEREE_DUEL" and sub == "STANDARD":
        sub = "PROOF_REFEREE"
    sid = db.new_id("sess")
    goal = req["target_goal"].strip() or "Untitled goal"
    attached = list(req.get("attached_files") or [])
    for rel in attached:
        if rel.endswith(".tex"):
            await subagents.ontologist(sid, None, import_file=rel)
    with db.tx() as conn:
        target = db.get_node(conn, req["target_node_id"]) if req.get("target_node_id") else match_goal_node(conn, goal)
        created_goal = False
        if not target and mode != "PRACTICE":
            target = _create_goal_node(conn, goal, sid)
            created_goal = True
        controller: dict[str, Any] = {"cue_level": int(req.get("cue_level", 1)), "pair_for": {}}
        if mode == "PRACTICE":
            if target:
                ids = [target["id"]]
            else:
                ranked = cm.rank_nodes_for_practice([n for n in db.all_nodes(conn) if n["node_type"] != "BUGGY_RULE"])
                ids = [n["id"] for n, _ in ranked[:5]]
            if req.get("contrastive_pair"):
                for nid in ids:
                    peer = _contrastive_peer(conn, nid)
                    if peer:
                        controller["pair_for"][nid] = peer
            plan = [{"node_id": i, "title": _node(conn, i)["title"], "depth": _node(conn, i)["logical_depth"], "status": "pending",
                     "remedial": False, "spliced_reason": "", "belief": _node(conn, i)["bkt_p_mastery"], "attempts": 0} for i in ids]
            if req.get("problem_file"):
                probs = [b for b in tools.read_tex_or_md(req["problem_file"])["blocks"] if b["env"] == "problem"]
                controller["problems"] = [{**b, "path": req["problem_file"], "used": False} for b in probs]
                if probs and not req.get("target_node_id"):
                    m = match_goal_node(conn, " ".join(b["body"] for b in probs[:3]))
                    if m:
                        plan = [{"node_id": m["id"], "title": m["title"], "depth": m["logical_depth"], "status": "pending",
                                 "remedial": False, "spliced_reason": "", "belief": m["bkt_p_mastery"], "attempts": 0}
                                for _ in probs[:4]]
        elif mode == "REFEREE_DUEL":
            plan = [{"node_id": target["id"], "title": target["title"], "depth": target["logical_depth"], "status": "pending",
                     "remedial": False, "spliced_reason": "", "belief": target["bkt_p_mastery"], "attempts": 0}]
        else:
            plan = build_plan(conn, target["id"])
            if mode == "TEACH":
                for p in plan[:-1]:
                    if p["belief"] >= 0.85:
                        p["status"] = "probed_mastered"
        title = req.get("title") or {
            "PROBE": "Probe → Teach", "PRODUCTIVE_FAILURE": "Productive Failure → Teach", "TEACH": "Teach",
            "PRACTICE": "Adaptive Practice", "REFEREE_DUEL": "Proof-Referee Duel" if sub == "PROOF_REFEREE" else "Feynman Student Duel",
        }[mode] + f": {goal[:60]}"
        session = {"id": sid, "title": title, "mode": mode, "sub_mode": sub, "target_goal": goal, "attached_files": attached,
                   "step_velocity_delta": 1.0, "current_step_index": 0, "dependency_plan": plan, "active_step": {},
                   "history_steps": [], "status": "ACTIVE", "_controller": controller}
        if created_goal:
            session["history_steps"].append({"kind": "GOAL_NODE_CREATED", "node_id": target["id"], "step_index": -1})
        db.insert_session(conn, session)
    if attached or mode in TEACH_MODES:
        await subagents.corpus_rag(sid, goal, attached)
    # decide_next may run sub-agents that open their own write transactions, so it only gets a read connection
    with db.ro() as conn:
        session["active_step"] = await decide_next(session, conn)
    with db.tx() as conn:
        _persist(conn, session)
        state = session_state(conn, session)
    await hub.broadcast("session_updated", {"session_id": sid})
    await hub.broadcast("graph_updated", {"reason": "session_created"})
    return state


def _contrastive_peer(conn, nid: str) -> Optional[str]:
    for e in db.all_edges(conn):
        if e["edge_type"] != "CONTRASTIVE":
            continue
        members = set(e["premise_node_ids"]) | {e["conclusion_node_id"]}
        if nid in members:
            for m in members:
                n = db.get_node(conn, m)
                if m != nid and n and n["node_type"] != "BUGGY_RULE":
                    return m
    return None


def _create_goal_node(conn, goal: str, sid: str) -> dict[str, Any]:
    nid = "goal_" + re.sub(r"[^a-z0-9]+", "_", goal.lower()).strip("_")[:40]
    if not db.node_exists(conn, nid):
        db.upsert_node(conn, {
            "id": nid, "title": goal[:120], "node_type": "PROPOSITION", "statement_latex": rf"\text{{{subagents._latex_text(goal[:300])}}}",
            "intuition_summary": f"Learner-defined goal: {goal[:300]}", "formal_proof_sketch_latex": "",
            "domain_cluster": subagents.guess_domain(goal), "logical_depth": 1, "last_reviewed_at": db.now_iso(),
            "created_in_session_id": sid,
        })
        gw = _words(goal)
        scored = sorted(((len(gw & _words(n["title"] + " " + n["statement_latex"])), n["id"]) for n in db.all_nodes(conn)
                         if n["id"] != nid and n["node_type"] not in ("BUGGY_RULE", "COUNTEREXAMPLE")), reverse=True)
        premises = [i for s, i in scored[:2] if s >= 1]
        if premises:
            db.insert_edge(conn, "DEDUCTION", premises, nid, r"\text{Closest existing propositions (lexical match) as provisional premises}", "", sid)
        db.recompute_depths(conn)
    return db.get_node(conn, nid)


async def get_state(session_id: str) -> dict[str, Any]:
    with db.ro() as conn:
        return session_state(conn, _load(conn, session_id))


# ------------------------------------------------------------------ assessment core
def log_prediction(conn, n: dict[str, Any], trace_id: str, session_id: str, phase: str, y: int, q: float) -> dict[str, Any]:
    """Record what the model expected for this answer, from the node state before it is updated (model-eval-85 FR1)."""
    t = cm.elapsed_days(n["last_reviewed_at"])
    r = cm.retrievability(t, n["fsrs_stability"])
    k_all, n_all, k_node, n_node = db.prediction_counts(conn, n["id"])
    row = {"trace_id": trace_id, "session_id": session_id, "node_id": n["id"], "phase": phase, "elapsed_days": t,
           "r_at_review": r, "p_mastery_before": n["bkt_p_mastery"],
           **cm.predict_correct(n["bkt_p_mastery"], n["bkt_p_slip"], n["bkt_p_guess"], r),
           "p_global_baseline": cm.laplace_rate(k_all, n_all), "p_node_baseline": cm.laplace_rate(k_node, n_node),
           "y": y, "success": int(bool(y) and q >= cm.SUCCESS_MIN_QUALITY)}
    db.insert_prediction(conn, row)
    return row


def apply_assessment(conn, session: dict[str, Any], node_id: str, y: int, q: float, miss: str, confidence: float,
                     hint: str, partial: bool, cue_dim: Optional[str], prosody: dict[str, Any],
                     trace_id: str, phase: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Log the model's prediction, then update BKT, FSRS, Brier, hypercorrection, cue breadth and propagate beliefs.
    Returns (node_update, trace_fields)."""
    n = _node(conn, node_id)
    log_prediction(conn, n, trace_id, session["id"], phase, y, q)
    outcome = cm.classify_outcome(y, confidence, hint, q, partial)
    brier = cm.brier_score(confidence, y)
    new_flag, resolved = cm.hypercorrection_transition(n["hypercorrection_flag"], y, confidence, q)
    rating = cm.assign_rating(y, outcome, hint, q, int(prosody.get("hesitation_count", 0)))
    t = cm.elapsed_days(n["last_reviewed_at"])
    fs = cm.fsrs_review(n["fsrs_stability"], n["fsrs_difficulty"], t, rating, hypercorrection_resolved=resolved)
    p_after = cm.bkt_update(n["bkt_p_mastery"], y, q, miss, n["bkt_p_slip"], n["bkt_p_guess"], n["bkt_p_transit"])
    fields: dict[str, Any] = {
        "bkt_p_mastery": p_after, "fsrs_stability": fs.stability_after, "fsrs_difficulty": fs.difficulty_after,
        "fsrs_reps": n["fsrs_reps"] + 1, "fsrs_lapses": n["fsrs_lapses"] + (1 if rating == 1 else 0),
        "last_reviewed_at": db.now_iso(), "brier_sum": n["brier_sum"] + brier, "brier_count": n["brier_count"] + 1,
        "hypercorrection_flag": new_flag, "last_miss_class": miss,
    }
    clean = outcome == "SOLVED_CLEAN" and q >= 0.75
    if clean and cue_dim:
        fields[cue_dim] = cm.update_cue(n[cue_dim])
    db.update_node_fields(conn, node_id, **fields)
    masteries = {m["id"]: m["bkt_p_mastery"] for m in db.all_nodes(conn)}
    prop = cm.propagate_hyperedge_beliefs(masteries, db.deduction_pairs(db.all_edges(conn)), node_id, y, q, miss)
    for pid, val in prop.items():
        db.update_node_fields(conn, pid, bkt_p_mastery=val)
    for e in db.all_edges(conn):
        if e["edge_type"] == "DEDUCTION" and e["conclusion_node_id"] == node_id:
            conn.execute("UPDATE hyperedges SET edge_mastery=? WHERE id=?",
                         (cm.clip(0.7 * e["edge_mastery"] + 0.3 * (q if y else 0.1), 0.01, 0.99), e["id"]))
    upd = {"node_id": node_id, "title": n["title"], "rating": rating, "bkt_before": n["bkt_p_mastery"], "bkt_after": p_after,
           "stability_before": n["fsrs_stability"], "stability_after": fs.stability_after,
           "difficulty_after": fs.difficulty_after, "retrievability_at_review": fs.r_at_review,
           "hypercorrection_flag": new_flag, "hypercorrection_bonus_applied": fs.hypercorrection_bonus_applied,
           "cue_dimension": cue_dim if clean else None, "propagated_to": sorted(prop)}
    trace = {"is_correct": y, "trace_quality_score": q, "outcome": outcome, "max_hint_rung": hint, "miss_class": miss,
             "brier_score": brier, "bkt_mastery_before": n["bkt_p_mastery"], "bkt_mastery_after": p_after,
             "fsrs_stability_before": n["fsrs_stability"], "fsrs_stability_after": fs.stability_after}
    return upd, trace


def _splice_remedial(conn, session: dict[str, Any], node_id: str, reason: str) -> Optional[str]:
    plan = session["dependency_plan"]
    idx = next((i for i, p in enumerate(plan) if p["node_id"] == node_id and not p.get("remedial")), None)
    if idx is None or plan[idx].get("remedial_spliced"):
        return None
    plan[idx]["remedial_spliced"] = True
    done_ids = {p["node_id"] for p in plan if p["status"] in ("done", "probed_mastered")}
    premises = []
    for e in db.all_edges(conn):
        if e["edge_type"] == "DEDUCTION" and e["conclusion_node_id"] == node_id:
            premises += [p for p in e["premise_node_ids"] if p not in done_ids]
    cand = sorted({p for p in premises if db.get_node(conn, p)}, key=lambda p: db.get_node(conn, p)["bkt_p_mastery"])
    rid = cand[0] if cand else node_id
    rn = _node(conn, rid)
    plan.insert(idx, {"node_id": rid, "title": (rn["title"] if rid != node_id else f"Base case: {rn['title']}"),
                      "depth": rn["logical_depth"], "status": "pending", "remedial": True,
                      "spliced_reason": f"Remedial (Δ→0.5): {reason}", "belief": rn["bkt_p_mastery"], "attempts": 0})
    return rid


def _plan_item(session: dict[str, Any], node_id: str) -> Optional[dict[str, Any]]:
    for p in session["dependency_plan"]:
        if p["node_id"] == node_id and p["status"] == "active":
            return p
    return next((p for p in session["dependency_plan"] if p["node_id"] == node_id and p["status"] != "done"), None)


async def submit(session_id: str, sub: dict[str, Any]) -> dict[str, Any]:
    with db.ro() as conn:
        session = _load(conn, session_id)
    active = session["active_step"]
    if sub["step_id"] != active.get("step_id"):
        raise HTTPException(409, f"stale step: active step is {active.get('step_id')}")
    kind = active["kind"]
    if kind == "COMPLETE":
        raise HTTPException(400, "session is complete")
    meta = active.get("_meta", {})
    node_id = active["target_node_ids"][0]
    with db.ro() as conn:
        node = _node(conn, node_id)
    prosody = sub.get("prosody") or {}
    confidence = float(sub.get("confidence", 0.5))
    text_all = " ".join([sub.get("raw_prediction_locked", ""), sub.get("verification_thinking", ""),
                         " ".join(n.get("thought", "") for n in sub.get("thinking_while_reading", []))])
    if active.get("options_locked") and len(sub.get("raw_prediction_locked", "").strip()) < 15:
        raise HTTPException(422, "Epistemic lock: a raw prediction of at least 15 characters is required before answering.")

    feedback: list[str] = []
    node_updates: list[dict[str, Any]] = []
    created: list[str] = []
    delta_before = session["step_velocity_delta"]
    remedial = None
    reading: Optional[cm.ControllerReading] = None
    trace_id = db.new_id("tr")
    trace_fields: dict[str, Any] = {"is_correct": 0, "trace_quality_score": 0.5, "outcome": "EXPLORATION_LOGGED",
                                    "max_hint_rung": "NONE", "miss_class": "NONE", "brier_score": 0.0,
                                    "bkt_mastery_before": node["bkt_p_mastery"], "bkt_mastery_after": node["bkt_p_mastery"],
                                    "fsrs_stability_before": node["fsrs_stability"], "fsrs_stability_after": node["fsrs_stability"]}
    diag_md = ""
    hist_entry: dict[str, Any] = {"kind": meta.get("hist_kind", kind), "node_id": node_id, "step_index": active["step_index"]}

    if kind in ("PREDICT", "READING", "PRODUCTIVE_FAILURE"):
        if kind == "PRODUCTIVE_FAILURE":
            feedback.append(f"**Your attempts are logged.** Canonical insight to compare against:\n\n{meta.get('insight', '')}")
        elif meta.get("paper_skim"):
            with db.tx() as conn:
                papers.update(conn, session["_controller"]["paper_id"], first_guess=sub.get("raw_prediction_locked", "")[:2000])
            feedback.append("Guess kept. You'll compare it with what the paper actually shows at the end.")
        elif kind == "PREDICT":
            feedback.append("Prediction locked. Read the next step and check it against what you predicted.")
        else:
            feedback.append(f"{len(sub.get('thinking_while_reading', []))} reading note(s) captured.")
        ce = await subagents.synthesize_counterexample(session_id, text_all, node) if text_all.strip() else None
        if ce:
            created.append(ce["node_id"])
            feedback.append(f"🧪 Your claim “{ce['claim'][:120]}” drops a hypothesis ({ce['missing']}). Verified counterexample: "
                            f"${ce['latex']}$")
    else:
        hint = "NONE"
        partial = False
        ctx = {"raw_prediction_locked": sub.get("raw_prediction_locked", ""),
               "thinking_while_reading": sub.get("thinking_while_reading", []),
               "verification_thinking": sub.get("verification_thinking", ""), "prosody": prosody,
               "confidence": confidence, "selected_answer": sub.get("selected_answer", "")}
        cue_dim = None
        if kind in ("PROBE", "CHECK"):
            correct = meta.get("correct", "")
            y = int(sub.get("selected_answer", "") == correct)
            ctx.update(is_correct=y, correct_answer=correct)
            cue_dim = cm.cue_dimension_for(active["cue_level"], session["mode"], session["sub_mode"])
            feedback.append(("✅ Correct." if y else f"❌ Not quite — the answer was **{correct}**.") +
                            f"\n\n{meta.get('explanation', '')}")
        elif kind == "PRACTICE_CHUNK":
            chunks = active.get("chunks", [])
            combined = " ".join(c["text"] for c in chunks) + " " + sub.get("verification_thinking", "")
            groups = meta.get("concept_groups", [])
            low = combined.lower()
            covered = [g for g in groups if any(s.lower() in low for s in g)]
            coverage = len(covered) / max(1, len(groups))
            slip = any(c.get("slip_detected") for c in chunks)
            y = int(coverage >= 0.75 or any(c.get("demand_satisfied") for c in chunks))
            partial = not y and coverage >= 0.4
            unlocked = [h["rung"] for h in active.get("hints_unlocked", [])]
            hint = max(unlocked, key=RUNG_ORDER.index) if unlocked else "NONE"
            ctx.update(is_correct=y, correct_answer=meta.get("answer_summary", ""), concept_groups=groups, extra_text=combined)
            if slip and not y:
                ctx["extra_text"] += " arithmetic"
            cue_dim = cm.cue_dimension_for(meta.get("cue_level", 1), "PRACTICE",
                                           computational=meta.get("cue_level") == 3)
            if meta.get("verify_code"):
                res, art = await subagents.symbolic_verify(session_id, meta["verify_code"], f"Reference answer · {node['title']}")
                feedback.append(f"Symbolic verifier on the reference answer: {'✓ VERIFIED' if res.verified else '✗ not verified'} "
                                f"(artifact `{art['id']}`).")
            feedback.append(f"Concept coverage {len(covered)}/{len(groups)}. Reference answer: {meta.get('answer_summary', '')}")
        elif kind == "REFEREE":
            flagged = sub.get("flagged_step_index")
            y = int(flagged == meta.get("flawed_index"))
            expl = (sub.get("verification_thinking", "") + " " + sub.get("counterexample_text", "")).lower()
            kw = meta.get("violated_keywords", [])
            hit = sum(1 for k in kw if k.lower() in expl)
            ce_match = subagents.match_counterexample(expl + " always")
            ctx.update(is_correct=y, correct_answer=str(meta.get("flawed_index")),
                       concept_groups=[[k] for k in kw] or None, extra_text=sub.get("counterexample_text", ""))
            cue_dim = "cue_adversarial"
            feedback.append(("✅ You found the flawed step." if y else f"❌ The flawed step was **Step {meta.get('flawed_index')}**.") +
                            f"\n\n**Why:** {meta.get('explanation', '')}\n\n**Minimal counterexample:** {meta.get('counterexample', '')}")
            feedback.append(f"Violated-hypothesis keywords named: {hit}/{len(kw)}." +
                            (f" Your counterexample matches the verified library entry “{ce_match['claim']}”." if ce_match else ""))
            if ce_match:
                res, _ = await subagents.symbolic_verify(session_id, ce_match["code"], f"Learner counterexample · {ce_match['claim']}")
                if res.verified:
                    ctx["extra_text"] += " " + " ".join(kw)
        else:  # FEYNMAN
            conds = meta.get("conditions", [])
            met = active.get("boundary_conditions_met", [])
            y = int(len(met) == len(conds) and len(conds) > 0)
            partial = not y and len(met) >= max(1, len(conds) // 2)
            transcript = " ".join(t["text"] for t in active.get("duel_transcript", []) if t["role"] == "learner")
            ctx.update(is_correct=y, correct_answer="; ".join(c["label"] for c in conds),
                       concept_groups=[c["keywords"] for c in conds], extra_text=transcript)
            cue_dim = "cue_adversarial"
            feedback.append(f"Boundary conditions stated: {len(met)}/{len(conds)}. " +
                            ("The student is convinced." if y else "Missing: " + ", ".join(c["label"] for c in conds if c["id"] not in met)))
        diag = await subagents.diagnose(session_id, ctx, node)
        q, miss = diag["trace_quality_score"], diag["miss_class"]
        diag_md = diag["diagnosis_markdown"]
        if diag.get("buggy_rule_id"):
            created.append(diag["buggy_rule_id"])
        with db.tx() as conn:
            upd, trace_fields = apply_assessment(conn, session, node_id, y, q, miss, confidence, hint, partial, cue_dim,
                                                   prosody, trace_id, active["phase"] or kind)
        node_updates.append(upd)
        hist_entry.update(outcome=trace_fields["outcome"], is_correct=y, q=q)
        if trace_fields["outcome"] == "HIGH_CONFIDENCE_ERROR":
            feedback.append("🔥 **Hypercorrection flag set** — this node will be prioritised; resolving it cleanly earns a 1.25× stability bonus.")
        if upd["hypercorrection_bonus_applied"]:
            feedback.append("🎯 Hypercorrection resolved: 1.25× stability bonus applied.")
        if kind in ("PROBE", "CHECK") and not y:
            ce = await subagents.synthesize_counterexample(session_id, text_all, node)
            if ce:
                created.append(ce["node_id"])
                feedback.append(f"🧪 Verified counterexample to “{ce['claim'][:100]}”: ${ce['latex']}$")

    # ---- controller updates (plan statuses, beliefs, Δ, remediation)
    with db.tx() as conn:
        db.insert_trace(conn, {
            "id": trace_id, "session_id": session_id, "step_index": active["step_index"], "phase": active["phase"] or "READING",
            "target_node_ids": active["target_node_ids"], "cue_level": active["cue_level"],
            "prompt_shown_latex": (active.get("prompt_latex") or active.get("body_markdown") or "")[:4000],
            "options": active.get("options", []) or active.get("proof_steps", []),
            "raw_prediction_locked": sub.get("raw_prediction_locked", ""),
            "thinking_while_reading": sub.get("thinking_while_reading", []),
            "verification_thinking": (sub.get("verification_thinking", "") +
                                      (f"\n[flagged step {sub.get('flagged_step_index')}] {sub.get('counterexample_text', '')}"
                                       if kind == "REFEREE" else "")),
            "selected_answer": sub.get("selected_answer", "") or (str(sub.get("flagged_step_index") or "")),
            "confidence_slider": confidence, "prosody_metrics": prosody, "ai_diagnosis_markdown": diag_md,
            **trace_fields,
        })
        session = _load(conn, session_id)
        plan = session["dependency_plan"]
        item = _plan_item(session, node_id)
        if kind == "PROBE":
            y = trace_fields["is_correct"]
            q = trace_fields["trace_quality_score"]
            mastered = bool(y and q >= 0.5)
            beliefs = {p["node_id"]: p["belief"] for p in plan}
            beliefs[node_id] = trace_fields["bkt_mastery_after"] if not mastered else max(0.9, trace_fields["bkt_mastery_after"])
            beliefs.update(cm.apply_probe_result(beliefs, plan_edges(conn, plan), node_id, mastered))
            for p in plan:
                p["belief"] = beliefs.get(p["node_id"], p["belief"])
                if p["node_id"] == node_id:
                    p["status"] = "probed_mastered" if mastered else "probed_unmastered"
            feedback.append(f"Belief update over the plan DAG: {'ancestors gain belief mass' if mastered else 'descendants lose reachability'}.")
        elif kind in ("CHECK", "PRACTICE_CHUNK", "REFEREE", "FEYNMAN") and item:
            item["attempts"] = item.get("attempts", 0) + 1
            solved = bool(trace_fields["is_correct"])
            if solved or item["attempts"] >= 2 or session["mode"] in ("PRACTICE", "REFEREE_DUEL"):
                item["status"] = "done"
            else:
                item["status"] = "pending"
            item["belief"] = trace_fields["bkt_mastery_after"]
            ctl = session.setdefault("_controller", {})
            reading = cm.difficulty_controller(session["step_velocity_delta"], int(ctl.get("cue_level", 1)),
                                               db.recent_successes(conn, cm.SUCCESS_WINDOW), trace_fields,
                                               config.load_prefs()["target_success"])
            session["step_velocity_delta"] = reading.delta
            ctl["cue_level"] = reading.cue_level
            ctl["last_reading"] = {"action": reading.action, "summary": reading.summary,
                                   "recent_success": reading.recent_success, "target": reading.target}
            if reading.action == "REMEDIATE" and session["mode"] in TEACH_MODES + ("PRACTICE",):
                reason = trace_fields["miss_class"] if trace_fields["miss_class"] != "NONE" else trace_fields["outcome"]
                remedial = _splice_remedial(conn, session, node_id, reason)
                if remedial:
                    feedback.append(f"↩︎ Δ dropped to 0.5 — spliced a remedial step on `{remedial}` before revisiting this node.")
            elif reading.action in ("HARDER", "EASIER"):
                feedback.append(f"{'⏩' if reading.action == 'HARDER' else '⏪'} {reading.summary} "
                                f"(step size Δ {reading.delta:.1f}, practice level {reading.cue_level}).")
        elif kind in ("PREDICT", "READING", "PRODUCTIVE_FAILURE"):
            pass
        session["history_steps"].append(hist_entry)
        session["current_step_index"] += 1
    with db.ro() as conn:
        session["active_step"] = await decide_next(session, conn)
    if session["active_step"]["kind"] == "COMPLETE":
        session["status"] = "COMPLETED"
    with db.tx() as conn:
        _persist(conn, session)
        state = session_state(conn, session)
        trace = db.get_trace(conn, trace_id)
    if session["status"] == "COMPLETED":
        if session["sub_mode"] == "PAPER":
            papers.refresh_in_background(session["_controller"]["paper_id"])   # re-rank sources against your misses
        await subagents.ontologist(session_id, session)
        with db.ro() as conn:
            state = session_state(conn, _load(conn, session_id))
    await hub.broadcast("session_updated", {"session_id": session_id})
    await hub.broadcast("graph_updated", {"reason": "assessment"})
    return {"trace": trace, "feedback_markdown": "\n\n".join(feedback + ([diag_md] if diag_md else [])),
            "node_updates": node_updates, "delta_before": delta_before, "delta_after": session["step_velocity_delta"],
            "remedial_spliced": remedial, "created_nodes": created, "state": state,
            "controller": ({"action": reading.action, "summary": reading.summary, "recent_success": reading.recent_success,
                            "target": reading.target, "window_n": reading.window_n, "delta": reading.delta,
                            "practice_level": reading.cue_level} if reading else None)}


async def advance(session_id: str) -> dict[str, Any]:
    """Skip-forward for READING steps without notes (records an EXPLORATION_LOGGED trace)."""
    with db.ro() as conn:
        s = _load(conn, session_id)
    if s["active_step"].get("kind") != "READING":
        raise HTTPException(400, "advance is only valid on READING steps; use /submit")
    res = await submit(session_id, {"step_id": s["active_step"]["step_id"], "confidence": 0.5})
    return res["state"]


# ------------------------------------------------------------------ practice: hints and chunks
def _quote_from(text: str) -> str:
    sents = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", text) if s.strip()]
    for s in reversed(sents):
        if "=" in s or "\\" in s:
            return s[:160]
    return (sents[-1] if sents else text)[:160] or "(your reasoning so far)"


async def hint(session_id: str, rung: str, current_thinking: str) -> dict[str, Any]:
    with db.ro() as conn:
        session = _load(conn, session_id)
    active = session["active_step"]
    if active.get("kind") != "PRACTICE_CHUNK":
        raise HTTPException(400, "hints are only available on practice steps")
    unlocked = [h["rung"] for h in active.get("hints_unlocked", [])]
    if rung in unlocked:
        return next(h for h in active["hints_unlocked"] if h["rung"] == rung)
    expected = RUNG_ORDER[len(unlocked)] if len(unlocked) < 5 else None
    if rung != expected:
        raise HTTPException(409, f"hint rungs unlock in order; next is {expected}")
    meta = active["_meta"]
    thinking = current_thinking or " ".join(c["text"] for c in active.get("chunks", []))
    text = meta["hints"][rung].replace("{quote}", _quote_from(thinking))
    with db.ro() as conn:
        node = _node(conn, active["target_node_ids"][0])
    res = await llm.complete_json(prompts.HINT_PROMPT, prompts.node_context(node) +
                                  f"\nProblem: {active['prompt_latex']}\nRequested rung: {rung} ({RUNG_LABELS[rung]})\n"
                                  f"Learner thinking so far:\n{thinking[:2500]}", max_tokens=600)
    if res.data and isinstance(res.data.get("hint_markdown"), str) and res.data["hint_markdown"].strip():
        text = res.data["hint_markdown"]
    cap = 3 if rung in ("R0", "R1") else 2
    out = {"rung": rung, "label": RUNG_LABELS[rung], "hint_markdown": text, "fsrs_rating_cap": cap,
           "stability_multiplier": cm.RATING_MULTIPLIERS[cap]}
    with db.tx() as conn:
        session = _load(conn, session_id)
        session["active_step"].setdefault("hints_unlocked", []).append(out)
        _persist(conn, session)
    await hub.broadcast("session_updated", {"session_id": session_id})
    return out


async def chunk(session_id: str, text: str, confidence: float) -> dict[str, Any]:
    with db.ro() as conn:
        session = _load(conn, session_id)
    active = session["active_step"]
    if active.get("kind") != "PRACTICE_CHUNK":
        raise HTTPException(400, "chunks are only accepted on practice steps")
    meta = active["_meta"]
    groups = meta.get("concept_groups", [])
    prior = " ".join(c["text"] for c in active.get("chunks", []))
    low = (prior + " " + text).lower()
    matched = [g[0] for g in groups if any(s.lower() in low for s in g)]
    missing = [g[0] for g in groups if g[0] not in matched]
    eq = await subagents.verify_learner_equations(session_id, text)
    wrong_eq = [e for e in eq if e["ok"] and not e["verified"]]
    with db.ro() as conn:
        node = _node(conn, active["target_node_ids"][0])
    mis_hit = None
    for mis in (CONTENT.get(meta.get("bank_node", ""), {}) or {}).get("misconceptions", []):
        if any(k.lower() in text.lower() for k in mis["trigger_keywords"]):
            mis_hit = mis
            break
    satisfied = bool(groups) and len(matched) == len(groups) and not wrong_eq and not mis_hit
    q_est, _ = subagents.trace_quality({"verification_thinking": prior + " " + text, "concept_groups": groups}, node)
    fb: list[str] = []
    if wrong_eq:
        fb.append("The symbolic verifier could not confirm " + ", ".join(f"`{e['lhs']} = {e['rhs']}`" for e in wrong_eq) +
                  " — re-derive that line (check signs, factors and transpose order).")
    elif eq:
        fb.append("Verified: " + ", ".join(f"`{e['lhs']} = {e['rhs']}`" for e in eq if e["verified"]) + ".")
    if mis_hit:
        fb.append(f"Careful — this sounds like a known trap ({mis_hit['buggy_title']}). Which hypothesis are you assuming?")
    if satisfied:
        fb.append("This covers the core demand. Write your final verification reasoning, set your confidence and submit.")
    elif matched:
        fb.append(f"Good: you've engaged {len(matched)}/{len(groups)} required ideas. Keep going — what's still unjustified?")
    else:
        fb.append("Not yet engaging the core structure. Try the R0 shape/limit check if you're stuck.")
    res = await llm.complete_json(prompts.CHUNK_EVAL_PROMPT, prompts.node_context(node) +
                                  f"\nProblem: {active['prompt_latex']}\nReference: {meta.get('answer_summary', '')}\n"
                                  f"Earlier chunks: {prior[:2000]}\nNew chunk: {text[:2000]}", max_tokens=600)
    if res.data and isinstance(res.data.get("feedback_markdown"), str):
        fb = [res.data["feedback_markdown"]] + [f for f in fb if f.startswith("The symbolic verifier")]
        satisfied = bool(res.data.get("demand_satisfied", satisfied)) and not wrong_eq
        q_est = cm.clip(0.5 * q_est + 0.5 * float(res.data.get("quality_estimate", q_est)), 0.0, 1.0)
    ev = {"chunk_index": len(active.get("chunks", [])), "text": text, "demand_satisfied": satisfied,
          "slip_detected": bool(wrong_eq or mis_hit), "quality_estimate": round(q_est, 3), "feedback_markdown": " ".join(fb),
          "matched_concepts": matched, "missing_concepts": missing,
          "verifier_summary": "; ".join(f"{e['lhs']}={e['rhs']}: {'✓' if e['verified'] else '✗'}" for e in eq)}
    with db.tx() as conn:
        session = _load(conn, session_id)
        session["active_step"].setdefault("chunks", []).append(ev)
        _persist(conn, session)
    await hub.broadcast("session_updated", {"session_id": session_id})
    return ev


# ------------------------------------------------------------------ Feynman duel
async def duel(session_id: str, message: str) -> dict[str, Any]:
    with db.ro() as conn:
        session = _load(conn, session_id)
    active = session["active_step"]
    if active.get("kind") != "FEYNMAN":
        raise HTTPException(400, "duel messages are only accepted on Feynman steps")
    conds = active["_meta"]["conditions"]
    met = list(active.get("boundary_conditions_met", []))
    low = message.lower()
    for c in conds:
        if c["id"] not in met and any(k.lower() in low for k in c["keywords"]):
            met.append(c["id"])
    remaining = [c for c in conds if c["id"] not in met]
    resolved = not remaining
    if resolved:
        reply = ("Okay… I'm convinced. So it only works when " + "; ".join(c["label"] for c in conds) +
                 ". My rule was missing exactly those conditions — thanks!")
    else:
        newly = [c["label"] for c in conds if c["id"] in met and c["id"] not in active.get("boundary_conditions_met", [])]
        ack = (f"Hm, fair — {newly[0].lower()}. " if newly else "I'm not sure that settles it. ")
        reply = ack + remaining[0]["challenge"]
    with db.ro() as conn:
        node = _node(conn, active["target_node_ids"][0])
    history = "\n".join(f"{t['role']}: {t['text']}" for t in active.get("duel_transcript", []))
    res = await llm.complete_json(prompts.MODE_PROMPTS["FEYNMAN_STUDENT"],
                                  prompts.node_context(node) + f"\nYour misconception persona: {active['_meta']['persona']}\n"
                                  f"Boundary conditions (id: label): " + "; ".join(f"{c['id']}: {c['label']}" for c in conds) +
                                  f"\nAlready met: {met}\nConversation:\n{history}\nlearner: {message}", max_tokens=500)
    if res.data and isinstance(res.data.get("student_message"), str):
        reply = res.data["student_message"]
        for cid in res.data.get("conditions_now_met", []) or []:
            if cid in {c["id"] for c in conds} and cid not in met:
                met.append(cid)
        resolved = len(met) == len(conds)
    now_ms = float(len(active.get("duel_transcript", [])))
    with db.tx() as conn:
        session = _load(conn, session_id)
        a = session["active_step"]
        a.setdefault("duel_transcript", []).extend([{"role": "learner", "text": message, "timestamp_ms": now_ms},
                                                     {"role": "student", "text": reply, "timestamp_ms": now_ms + 1}])
        a["boundary_conditions_met"] = met
        _persist(conn, session)
    await hub.broadcast("session_updated", {"session_id": session_id})
    return {"student_message": reply, "boundary_conditions_met": met,
            "boundary_conditions_remaining": len(conds) - len(met), "resolved": resolved}
