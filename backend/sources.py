"""Sources for learning chats (docs/specs/learn-chat D2, FR5).

The learner's notes come first, then open sources fetched for a new topic (Wikipedia sections, arXiv abstracts). Every
source gets a citation number that stays fixed for the session, so a reply can cite [n] and the Sources list matches.
Fetchers are blocking and run in threads under a total time budget; offline (POLYA_OFFLINE=1) they return nothing.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Optional
from urllib.parse import quote

import httpx

from . import db, tools
from .agents import topic_map
from .papers import fetch

WIKI_API = "https://en.wikipedia.org/w/api.php"
REQUEST_TIMEOUT_S = 8.0
TOTAL_BUDGET_S = 20.0
ARTICLE_CHARS = 6000
CHUNK_CHARS = 900
PASSAGE_BUDGET = 3000
MAX_IDEA_LOOKUPS = 4
KIND_ORDER = {"notes": 0, "paper": 1, "wikipedia": 2, "arxiv": 3}
DROP_SECTIONS = {"see also", "references", "external links", "further reading", "notes", "bibliography", "citations"}


# ------------------------------------------------------------------ fetchers (blocking)
def _http_json(params: dict[str, Any]) -> dict[str, Any]:
    fetch._offline()
    with httpx.Client(timeout=REQUEST_TIMEOUT_S, headers={"User-Agent": fetch.USER_AGENT}) as c:
        r = c.get(WIKI_API, params={**params, "format": "json"})
        r.raise_for_status()
        return r.json()


def _trim_article(text: str) -> str:
    """Plain-text article without its reference sections, capped."""
    out, keep = [], True
    for line in text.splitlines():
        m = re.match(r"^\s*(=+)\s*(.*?)\s*\1\s*$", line)
        if m:
            keep = m.group(2).strip().lower() not in DROP_SECTIONS
        if keep:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()[:ARTICLE_CHARS]


def search_text(title: str) -> str:
    """An idea title as plain words: no LaTeX, formulas or symbols ("Covariate shift: train on $d_{\\pi^*}$…" → words)."""
    t = re.sub(r"\$[^$]*\$", " ", title)
    t = re.sub(r"\\[a-zA-Z]+|[^A-Za-z0-9' -]", " ", t)
    return " ".join(t.split())


def wikipedia_article(query: str) -> Optional[dict[str, str]]:
    """Best article for a query that shares at least one distinctive word with it; disambiguation pages are skipped."""
    query = search_text(query)
    if not query:
        return None
    hits = _http_json({"action": "query", "list": "search", "srsearch": query, "srlimit": 3, "srprop": ""})
    terms = topic_map.goal_terms(query)
    for h in hits.get("query", {}).get("search", []):
        title = h.get("title", "")
        if terms and not terms & topic_map.goal_terms(title):
            continue
        page = _http_json({"action": "query", "prop": "extracts|pageprops|info", "inprop": "url", "explaintext": 1,
                           "exsectionformat": "wiki", "titles": title, "redirects": 1})
        pg = next(iter(page.get("query", {}).get("pages", {}).values()), {})
        if "disambiguation" in pg.get("pageprops", {}) or not pg.get("extract"):
            continue
        return {"kind": "wikipedia", "title": pg.get("title", title),
                "url": pg.get("fullurl") or f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                "passage": _trim_article(pg["extract"])}
    return None


def arxiv_abstracts(query: str, k: int = 3) -> list[dict[str, str]]:
    """Surveys and tutorials first (they teach), else the plain search."""
    query = search_text(query)
    entries, source = tools.search_arxiv(f"{query} survey", max_results=k, timeout=REQUEST_TIMEOUT_S)
    if source != "arxiv":
        entries, source = tools.search_arxiv(query, max_results=k, timeout=REQUEST_TIMEOUT_S)
    if source != "arxiv":      # the offline knowledge base is not a fetched source
        return []
    return [{"kind": "arxiv", "title": e["title"], "url": f"https://arxiv.org/abs/{e['id']}",
             "passage": f"{e['title']} ({e.get('authors', '')}, {e.get('year', '')}). Abstract: {e['statement']}"}
            for e in entries if e.get("id")]


async def fetch_open(goal: Optional[str], idea_titles: list[str]) -> list[dict[str, str]]:
    """Wikipedia for the goal and up to 4 ideas, arXiv for the goal, in parallel under one budget. Failures are dropped."""
    jobs: list[tuple[str, Any]] = []
    if goal:
        jobs.append(("wiki", asyncio.to_thread(wikipedia_article, goal)))
    jobs += [("wiki", asyncio.to_thread(wikipedia_article, t)) for t in idea_titles[:MAX_IDEA_LOOKUPS]]
    if goal:
        jobs.append(("arxiv", asyncio.to_thread(arxiv_abstracts, goal)))
    if not jobs:
        return []
    tasks = [asyncio.ensure_future(j) for _, j in jobs]
    done, pending = await asyncio.wait(tasks, timeout=TOTAL_BUDGET_S)
    for t in pending:
        t.cancel()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for t in tasks:
        if t not in done or t.cancelled() or t.exception():
            continue
        res = t.result()
        for s in (res if isinstance(res, list) else [res] if res else []):
            if s["url"] not in seen and s["passage"].strip():
                seen.add(s["url"])
                out.append(s)
    out.sort(key=lambda s: KIND_ORDER[s["kind"]])
    return out


# ------------------------------------------------------------------ storage
def store(session_id: str, notes: list[dict[str, str]], fetched: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Number the notes first, then fetched sources. Idempotent: a session that has sources keeps them."""
    with db.tx() as conn:
        if not db.session_sources(conn, session_id):
            for p in notes:
                db.insert_source(conn, session_id, "notes", p["label"], "", p["text"])
            for s in fetched:
                db.insert_source(conn, session_id, s["kind"], s["title"], s["url"], s["passage"])
        return db.session_sources(conn, session_id)


def listing(session_id: str) -> list[dict[str, Any]]:
    with db.ro() as conn:
        return [{"n": s["n"], "kind": s["kind"], "title": s["title"], "url": s["url"]}
                for s in db.session_sources(conn, session_id)]


# ------------------------------------------------------------------ retrieval
def _chunks(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?==+ )", text) if p.strip()]
    out: list[str] = []
    cur = ""
    for p in paras:
        if cur and len(cur) + len(p) > CHUNK_CHARS:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{p}".strip()
    if cur:
        out.append(cur)
    return [c[:CHUNK_CHARS * 2] for c in out]


def passages_for(session_id: str, node: dict[str, Any], extra: str = "") -> list[dict[str, Any]]:
    """The 3 passages that best match an idea (notes count 1.5×), ≤ 3,000 characters, each with its [n]."""
    terms = topic_map.goal_terms(f"{node['title']} {node.get('intuition_summary', '')} {extra}")
    if not terms:
        return []
    with db.ro() as conn:
        rows = db.session_sources(conn, session_id)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for s in rows:
        best, best_chunk = 0.0, ""
        for c in _chunks(s["passage"]):
            words = {topic_map._stem(w) for w in re.findall(r"[a-z]{3,}", c.lower())}
            sc = len(terms & words) * (1.5 if s["kind"] == "notes" else 1.0)
            if sc > best:
                best, best_chunk = sc, c
        if best >= 1:
            scored.append((best, s["n"], {"n": s["n"], "kind": s["kind"], "title": s["title"], "url": s["url"],
                                          "text": best_chunk}))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = [p for _, _, p in scored[:3]]
    budget = PASSAGE_BUDGET // max(1, len(picked))
    for p in picked:
        p["text"] = p["text"][:budget]
    return sorted(picked, key=lambda p: p["n"])


def context(passages: list[dict[str, Any]]) -> str:
    if not passages:
        return ("\n\nNo sources were found for this idea: answer from your own knowledge, keep to well-established facts, "
                "and do not cite anything.")
    return ("\n\nSources (cite one as [n] right after the sentence that uses it; cite only these numbers; prefer the "
            "learner's notes and their notation):\n" + "\n\n".join(
                f"[{p['n']}] ({p['kind']} · {p['title']})\n{p['text']}" for p in passages))


def strip_unknown_citations(text: str, allowed: set[int]) -> tuple[str, list[int]]:
    """Remove [n] markers the reply was not given; returns (text, cited numbers in order)."""
    cited: list[int] = []

    def fix(m: re.Match[str]) -> str:
        n = int(m.group(1))
        if n in allowed:
            if n not in cited:
                cited.append(n)
            return m.group(0)
        return ""
    return re.sub(r"\s?\[(\d{1,2})\](?!\()", fix, text), cited
