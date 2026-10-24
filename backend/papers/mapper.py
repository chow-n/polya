"""Turn a parsed paper into a learning map (docs/specs/paper-reading FR4): ideas with roles, how they connect, the
paper's notation, its key argument and the assumptions its main result needs.

With an AI engine: one PAPER_MAPPER call over a capped excerpt, then strict validation — every quote must occur in the
paper (unverifiable quotes are dropped and counted), anchors must name real sections, existing node ids must exist.
Without one: an honest partial map from the paper's own theorem/definition/assumption blocks (or its abstract).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from .. import llm
from ..agents import prompts
from .latex import PaperDoc, plain

ROLES = ("prerequisite", "definition", "assumption", "claim", "main_result")
NODE_TYPES = ("AXIOM", "PROPOSITION", "MOVE", "INTUITION", "COUNTEREXAMPLE")
ROLE_TYPE = {"prerequisite": "PROPOSITION", "definition": "AXIOM", "assumption": "AXIOM", "claim": "PROPOSITION",
             "main_result": "PROPOSITION"}
BLOCK_ROLE = {"definition": "definition", "assumption": "assumption", "hypothesis": "assumption", "condition": "assumption",
              "theorem": "claim", "proposition": "claim", "lemma": "claim", "corollary": "claim", "claim": "claim"}
EXCERPT_CHARS = 24000
QUOTE_MAX = 300
MAP_TIMEOUT_S = 300.0


class MapIdea(BaseModel):
    key: str
    title: str
    role: str = "claim"
    node_type: str = ""
    statement_latex: str = ""
    intuition_summary: str = ""
    anchor: str = ""
    quote: str = ""
    existing_node_id: str = ""
    concept: str = ""        # the 1–4 word name a textbook would index it under (used to find explainers)


class MapEdge(BaseModel):
    premises: list[str] = Field(default_factory=list)
    conclusion: str
    reasoning: str = ""


class MapNotation(BaseModel):
    symbol_latex: str
    meaning: str
    existing_node_id: str = ""


class MapAssumption(BaseModel):
    label: str
    keywords: list[str] = Field(default_factory=list)
    challenge: str = ""


class KeyArgument(BaseModel):
    claim: str = ""
    steps: list[str] = Field(default_factory=list)


class LLMPaperMap(BaseModel):
    summary: str = ""
    contributions: list[str] = Field(default_factory=list)
    ideas: list[MapIdea] = Field(default_factory=list)
    edges: list[MapEdge] = Field(default_factory=list)
    notation: list[MapNotation] = Field(default_factory=list)
    key_argument: Optional[KeyArgument] = None
    assumptions_for_main: list[MapAssumption] = Field(default_factory=list)
    partial: bool = False              # deterministic map: blocks only
    quotes_dropped: int = 0


# ------------------------------------------------------------------ grounding checks
def _norm(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    s = re.sub(r"[{}$\\_^~`'\"“”‘’()\[\],.;:!?\-–—]", " ", s.lower())
    return " ".join(s.split())


def quote_in_text(quote: str, norm_text: str) -> bool:
    """Verbatim up to whitespace, punctuation and LaTeX markup; long quotes may differ in ≤10% of 5-word shingles."""
    q = _norm(quote)
    if len(q) < 12:
        return False
    if q in norm_text:
        return True
    words = q.split()
    if len(words) < 10:
        return False
    shingles = [" ".join(words[i:i + 5]) for i in range(len(words) - 4)]
    return sum(1 for sh in shingles if sh in norm_text) >= 0.9 * len(shingles)


def best_section(doc: PaperDoc, anchor: str, probe: str) -> str:
    titles = doc.section_titles()
    a = anchor.strip().lower().lstrip("§ ").strip()
    if a:
        exact = [t for t in titles if t.lower() == a]
        inside = sorted((t for t in titles if t.lower() in a), key=len, reverse=True)   # most specific first
        around = [t for t in titles if a in t.lower()]
        for group in (exact, inside, around):
            if group:
                return group[0]
    pw = set(_norm(probe).split())
    best, score = (titles[0] if titles else "Abstract"), 0
    for s in doc.sections:
        sc = len(pw & set(_norm(s.text[:6000]).split()))
        if sc > score:
            best, score = s.title, sc
    return best


def passage_for(doc: PaperDoc, anchor: str, quote: str = "", chars: int = 3500) -> str:
    """The paper text around a quote (or the start of the anchored section)."""
    sec = next((s for s in doc.sections if s.title == anchor), None)
    text = sec.text if sec else doc.abstract
    if quote:
        i = text.find(quote[:60])
        if i >= 0:
            start = max(0, i - chars // 2)
            return text[start:start + chars]
    return text[:chars]


# ------------------------------------------------------------------ excerpt for the engine
def excerpt(doc: PaperDoc, budget: int = EXCERPT_CHARS) -> str:
    parts = [f"Title: {doc.title}", f"Abstract: {doc.abstract}",
             "Sections: " + " | ".join(f"{'  ' * (s.level - 1)}{s.title}" for s in doc.sections)]
    blocks = [b for b in doc.blocks if b.kind != "equation"][:24]
    if blocks:
        parts.append("Theorem-like blocks:\n" + "\n".join(
            f"[{b.kind}{' ' + b.title if b.title else ''} · {b.section}] {b.body[:700]}"
            + (f"\n  proof: {b.proof[:500]}" if b.proof else "") for b in blocks))
    used = sum(len(p) for p in parts)
    skip = re.compile(r"related work|acknowledg|appendix|broader impact|limitations|ethics|reproducib", re.I)
    secs = [s for s in doc.sections if s.text.strip() and not skip.search(s.title)]
    intro = [s for s in secs if re.search(r"intro", s.title, re.I)][:1]
    rest = sorted((s for s in secs if s not in intro), key=lambda s: -len(s.text))
    order = intro + sorted(rest[:8], key=lambda s: doc.sections.index(s))
    for s in order:
        room = budget - used
        if room < 400:
            break
        take = s.text[:min(len(s.text), max(400, room // 2), 6000)]
        parts.append(f"## {s.title}\n{take}")
        used += len(take) + len(s.title) + 4
    return "\n\n".join(parts)[:budget]


def known_ideas(nodes: list[dict[str, Any]], doc: PaperDoc, k: int = 50) -> str:
    words = set(_norm(doc.title + " " + doc.abstract).split())
    scored = sorted(nodes, key=lambda n: -len(words & set(_norm(n["title"] + " " + n["statement_latex"][:300]).split())))
    return "\n".join(f"- `{n['id']}`: {n['title']}" for n in scored[:k] if n["node_type"] != "BUGGY_RULE")


# ------------------------------------------------------------------ validation
def validate(m: LLMPaperMap, doc: PaperDoc, node_ids: set[str]) -> LLMPaperMap:
    norm_text = _norm(doc.full_text() + " " + " ".join(b.body + " " + b.proof for b in doc.blocks))
    seen: set[str] = set()
    ideas: list[MapIdea] = []
    for i, idea in enumerate(m.ideas[:12]):
        key = re.sub(r"\W+", "_", idea.key or f"i{i + 1}") or f"i{i + 1}"
        if key in seen or not idea.title.strip():
            continue
        seen.add(key)
        idea.key = key
        idea.role = idea.role if idea.role in ROLES else "claim"
        idea.node_type = idea.node_type if idea.node_type in NODE_TYPES else ROLE_TYPE[idea.role]
        idea.existing_node_id = idea.existing_node_id if idea.existing_node_id in node_ids else ""
        idea.quote = idea.quote.strip().strip("“”\"")[:QUOTE_MAX]
        if idea.quote and not quote_in_text(idea.quote, norm_text):
            idea.quote = ""
            m.quotes_dropped += 1
        if idea.role != "prerequisite":
            idea.anchor = best_section(doc, idea.anchor, idea.quote or idea.statement_latex)
        idea.statement_latex = idea.statement_latex or idea.title
        idea.intuition_summary = idea.intuition_summary or idea.statement_latex[:300]
        idea.concept = " ".join(idea.concept.split()[:5]) or " ".join(idea.title.split()[:4])
        ideas.append(idea)
    if ideas and not any(i.role == "main_result" for i in ideas):
        claims = [i for i in ideas if i.role == "claim"] or [ideas[-1]]
        claims[-1].role = "main_result"
    m.ideas = ideas
    keys = {i.key for i in ideas}
    m.edges = [MapEdge(premises=[p for p in dict.fromkeys(e.premises) if p in keys and p != e.conclusion],
                       conclusion=e.conclusion, reasoning=e.reasoning[:600])
               for e in m.edges if e.conclusion in keys]
    m.edges = [e for e in m.edges if e.premises]
    m.notation = [n for n in m.notation[:20] if n.symbol_latex.strip() and n.meaning.strip()]
    for n in m.notation:
        n.existing_node_id = n.existing_node_id if n.existing_node_id in node_ids else ""
    if m.key_argument and len([s for s in m.key_argument.steps if s.strip()]) < 3:
        m.key_argument = None
    elif m.key_argument:
        steps = [s for s in m.key_argument.steps if s.strip()][:5]
        m.key_argument.steps = steps
    m.assumptions_for_main = [a for a in m.assumptions_for_main[:5] if a.label.strip() and a.keywords]
    for a in m.assumptions_for_main:
        a.keywords = [k.lower().strip() for k in a.keywords if k.strip()][:4]
        a.challenge = a.challenge or f"Does it still hold if we drop this: {a.label}?"
    return m


# ------------------------------------------------------------------ deterministic partial map
def partial_map(doc: PaperDoc) -> LLMPaperMap:
    m = LLMPaperMap(partial=True, summary=(doc.abstract.split(". ")[0] + ".") if doc.abstract else doc.title)
    by_section: dict[str, list[str]] = {}
    for b in doc.blocks:
        role = BLOCK_ROLE.get(b.kind)
        if not role or len(m.ideas) >= 10:
            continue
        key = f"b{len(m.ideas) + 1}"
        first = re.split(r"(?<=[.!?])\s", b.body.strip())[0]
        m.ideas.append(MapIdea(key=key, title=(b.title or f"{b.kind.title()} ({b.section})")[:120], role=role,
                               node_type=ROLE_TYPE[role], statement_latex=b.body[:1200],
                               intuition_summary=f"From “{doc.title}”, {b.section}.", anchor=b.section,
                               quote=plain(first)[:QUOTE_MAX] if len(first) <= QUOTE_MAX else ""))
        by_section.setdefault(b.section.split(" › ")[0], []).append(key)
    if not m.ideas:
        first = (doc.abstract.split(". ")[0] + ".") if doc.abstract else doc.title
        m.ideas.append(MapIdea(key="main", title=doc.title[:120] or "Main result", role="main_result",
                               node_type="PROPOSITION", statement_latex=first, intuition_summary=doc.abstract[:300],
                               anchor="Abstract", quote=first[:QUOTE_MAX] if len(first) <= QUOTE_MAX else ""))
    for sec, keys in by_section.items():
        prem = [k for k in keys if next(i for i in m.ideas if i.key == k).role in ("definition", "assumption")]
        for k in keys:
            if next(i for i in m.ideas if i.key == k).role in ("claim", "main_result") and prem:
                m.edges.append(MapEdge(premises=prem, conclusion=k, reasoning=f"Stated in {sec} from its definitions/assumptions."))
    return m


async def build(doc: PaperDoc, nodes: list[dict[str, Any]]) -> tuple[LLMPaperMap, str]:
    """(map, engine label). Falls back to the partial map when no engine answers with a valid map."""
    node_ids = {n["id"] for n in nodes}
    user = (excerpt(doc) + "\n\nIdeas already in the learner's graph (reuse these ids where they match):\n" +
            known_ideas(nodes, doc))
    engine = "deterministic"
    for _ in range(2):
        res = await llm.complete_json(prompts.PAPER_MAPPER, user, max_tokens=6000, timeout=MAP_TIMEOUT_S)
        engine = res.engine
        if not res.data:
            break
        try:
            m = validate(LLMPaperMap.model_validate(res.data), doc, node_ids)
        except Exception:
            continue
        if len(m.ideas) >= 3:
            return m, engine
    pm = validate(partial_map(doc), doc, node_ids)
    pm.partial = True
    return pm, engine
