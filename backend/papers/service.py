"""The research loop's backbone (docs/specs/paper-reading): ingest a paper, map it into the graph, rank its sources,
measure how much of it you understand. Files live in ~/Polya/workspace/papers/<paper_id>/ (source/, paper.pdf,
paper.json); rows in the papers / paper_nodes / paper_refs side tables.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from .. import config, db
from ..agents import subagents
from ..hub import hub
from . import fetch, latex, mapper, scholar

ROLE_ORDER = {"prerequisite": 0, "definition": 1, "assumption": 2, "claim": 3, "main_result": 4}
MISSED_BELOW = 0.5
_tasks: set[asyncio.Task] = set()


def papers_dir() -> Path:
    return config.WORKSPACE / "papers"


def paper_dir(paper_id: str) -> Path:
    return papers_dir() / paper_id


# ------------------------------------------------------------------ rows
def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["authors"] = json.loads(d.pop("authors_json") or "[]")
    d["map"] = json.loads(d.pop("map_json") or "{}")
    return d


def get(conn, paper_id: str) -> Optional[dict[str, Any]]:
    r = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    return _row(r) if r else None


def all_papers(conn) -> list[dict[str, Any]]:
    return [_row(r) for r in conn.execute("SELECT * FROM papers ORDER BY updated_at DESC").fetchall()]


def by_arxiv(conn, arxiv_id: str) -> Optional[dict[str, Any]]:
    base = re.sub(r"v\d+$", "", arxiv_id)
    r = conn.execute("SELECT * FROM papers WHERE arxiv_id=? OR arxiv_id LIKE ?", (base, base + "v%")).fetchone()
    return _row(r) if r else None


def update(conn, paper_id: str, **fields: Any) -> None:
    if "authors" in fields:
        fields["authors_json"] = json.dumps(fields.pop("authors"))
    if "map" in fields:
        fields["map_json"] = json.dumps(fields.pop("map"))
    fields["updated_at"] = db.now_iso()
    conn.execute(f"UPDATE papers SET {', '.join(f'{k}=:{k}' for k in fields)} WHERE id=:_id", {**fields, "_id": paper_id})


def links(conn, paper_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT pn.*, n.title, n.node_type, n.bkt_p_mastery, n.fsrs_reps FROM paper_nodes pn "
                        "JOIN nodes n ON n.id = pn.node_id WHERE pn.paper_id=? ORDER BY pn.ord", (paper_id,)).fetchall()
    return [dict(r) for r in rows]


def paper_for_node(conn, node_id: str) -> Optional[dict[str, Any]]:
    """The non-prerequisite paper link of a node (its role, anchor and quote), with the paper."""
    r = conn.execute("SELECT * FROM paper_nodes WHERE node_id=? AND role != 'prerequisite' LIMIT 1", (node_id,)).fetchone()
    if not r:
        return None
    p = get(conn, r["paper_id"])
    return {**dict(r), "paper": p} if p else None


def load_doc(paper_id: str) -> Optional[latex.PaperDoc]:
    f = paper_dir(paper_id) / "paper.json"
    if not f.exists():
        return None
    return latex.PaperDoc.from_json(json.loads(f.read_text()))


def understanding(conn, paper_id: str) -> Optional[float]:
    """Mean mastery over the paper's own ideas (FR7); None before it is mapped."""
    ls = [l for l in links(conn, paper_id) if l["role"] != "prerequisite"]
    return sum(l["bkt_p_mastery"] for l in ls) / len(ls) if ls else None


def missed_nodes(conn, paper_id: str) -> list[dict[str, Any]]:
    """Ideas of this paper (prerequisites included) you have answered on and are still below 50%."""
    return [l for l in links(conn, paper_id) if l["fsrs_reps"] > 0 and l["bkt_p_mastery"] < MISSED_BELOW]


async def _progress(paper_id: str, status: str, detail: str) -> None:
    with db.tx() as conn:
        update(conn, paper_id, status=status, status_detail=detail)
    await hub.broadcast("paper_progress", {"paper_id": paper_id, "status": status, "detail": detail})


# ------------------------------------------------------------------ ingest
async def create(arxiv: str = "", workspace_path: str = "", upload: Optional[tuple[str, bytes]] = None,
                 background: bool = True) -> dict[str, Any]:
    """Register a paper and start fetching → parsing → mapping → sources. Returns the paper row at once
    (status FETCHING) unless background=False. An arXiv paper already ingested is returned as it is."""
    arxiv_id = ""
    if arxiv:
        arxiv_id = fetch.parse_arxiv_ref(arxiv) or ""
        if not arxiv_id:
            raise HTTPException(422, "That doesn't look like an arXiv link or id (for example 1706.03762).")
        with db.ro() as conn:
            existing = by_arxiv(conn, arxiv_id)
        if existing and existing["status"] != "FAILED":
            return existing
    elif not workspace_path and not upload:
        raise HTTPException(422, "Give an arXiv link, a PDF in your notes, or upload a PDF.")
    pid = db.new_id("paper")
    pdir = paper_dir(pid)
    pdir.mkdir(parents=True, exist_ok=True)
    title = ""
    if workspace_path:
        from .. import tools
        src = tools._safe_path(workspace_path)
        if src.suffix.lower() != ".pdf" or not src.is_file():
            raise HTTPException(422, "Pick a PDF file.")
        shutil.copyfile(src, pdir / "paper.pdf")
        title = src.stem
    if upload:
        name, data = upload
        if data[:4] != b"%PDF":
            raise HTTPException(422, "That file is not a PDF.")
        (pdir / "paper.pdf").write_bytes(data)
        title = Path(name).stem
    now = db.now_iso()
    with db.tx() as conn:
        if arxiv_id:
            stale = by_arxiv(conn, arxiv_id)
            if stale:
                conn.execute("DELETE FROM papers WHERE id=?", (stale["id"],))
        conn.execute("INSERT INTO papers (id, source, arxiv_id, title, status, status_detail, created_at, updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?)", (pid, "arxiv" if arxiv_id else "pdf", re.sub(r"v\d+$", "", arxiv_id),
                                                  title, "FETCHING", "Fetching the paper…", now, now))
    if background:
        t = asyncio.create_task(ingest(pid, arxiv_id))
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)
    else:
        await ingest(pid, arxiv_id)
    with db.ro() as conn:
        return get(conn, pid)


async def ingest(paper_id: str, arxiv_id: str = "") -> None:
    pdir = paper_dir(paper_id)
    try:
        meta: dict[str, Any] = {}
        if arxiv_id:
            await hub.broadcast("paper_progress", {"paper_id": paper_id, "status": "FETCHING", "detail": "Fetching from arXiv…"})
            meta = await asyncio.to_thread(fetch.arxiv_metadata, arxiv_id)
            with db.tx() as conn:
                update(conn, paper_id, title=meta["title"], authors=meta["authors"], year=meta["year"],
                       abstract=meta["abstract"], doi=meta.get("doi", ""))
            kind = await asyncio.to_thread(fetch.fetch_arxiv_source, arxiv_id, pdir)
        else:
            kind = "pdf"
        await _progress(paper_id, "FETCHING", "Reading the paper…")
        doc: Optional[latex.PaperDoc] = None
        if kind == "latex":
            doc = await asyncio.to_thread(latex.parse_source, pdir / "source")
            if doc is None and arxiv_id:
                kind = await asyncio.to_thread(fetch.fetch_arxiv_pdf, arxiv_id, pdir)
        if doc is None:
            pages = await asyncio.to_thread(fetch.pdf_pages, pdir / "paper.pdf")
            doc = latex.parse_pdf_text(pages)
        if meta:
            doc.title = meta["title"] or doc.title
            doc.abstract = doc.abstract or meta["abstract"]
        (pdir / "paper.json").write_text(json.dumps(doc.to_json()))
        with db.tx() as conn:
            p = get(conn, paper_id)
            update(conn, paper_id, text_kind=doc.text_kind, title=p["title"] or doc.title, abstract=p["abstract"] or doc.abstract)
        await _progress(paper_id, "PARSED", f"Read {len(doc.sections)} sections and {len(doc.bib)} references. Mapping…")
        await build_map(paper_id, doc)
        await refresh_sources(paper_id, doc, explainers=True)
    except Exception as e:   # every failure ends in a visible FAILED state with the reason
        await _progress(paper_id, "FAILED", f"{type(e).__name__}: {e}"[:400])


async def build_map(paper_id: str, doc: latex.PaperDoc) -> dict[str, Any]:
    with db.ro() as conn:
        nodes = db.all_nodes(conn)
    m, engine = await mapper.build(doc, nodes)
    created: list[str] = []
    with db.tx() as conn:
        key_to_node: dict[str, str] = {}
        conn.execute("DELETE FROM paper_nodes WHERE paper_id=?", (paper_id,))
        for i, idea in enumerate(m.ideas):
            nid = idea.existing_node_id
            if not nid:
                base = f"{paper_id.replace('paper_', 'p')}_{subagents._slug(idea.title, 28)}"
                nid, k = base, 2
                while db.node_exists(conn, nid) and nid not in created:
                    nid, k = f"{base}_{k}", k + 1
                db.upsert_node(conn, {
                    "id": nid, "title": idea.title[:120], "node_type": idea.node_type, "statement_latex": idea.statement_latex,
                    "intuition_summary": idea.intuition_summary, "formal_proof_sketch_latex": idea.quote,
                    "domain_cluster": subagents.guess_domain(f"{idea.title} {idea.statement_latex} {doc.title}"),
                    "logical_depth": 0, "last_reviewed_at": db.now_iso(), "created_in_session_id": None,
                })
                created.append(nid)
            key_to_node[idea.key] = nid
            conn.execute("INSERT OR REPLACE INTO paper_nodes (paper_id, node_id, role, anchor, quote, ord) VALUES (?,?,?,?,?,?)",
                         (paper_id, nid, idea.role, idea.anchor, idea.quote, i))
        for e in m.edges:
            prem = [key_to_node[p] for p in e.premises if p in key_to_node]
            concl = key_to_node.get(e.conclusion)
            if prem and concl and concl not in prem:
                eid = f"he_{paper_id}_{hashlib.md5(json.dumps([prem, concl]).encode()).hexdigest()[:10]}"
                db.insert_edge(conn, "DEDUCTION", prem, concl, e.reasoning or f"From “{doc.title}”.", "", None, edge_id=eid)
        db.recompute_depths(conn)
        stored = m.model_dump()
        stored["key_to_node"] = key_to_node
        detail = (f"Mapped {len(m.ideas)} ideas" + (" from the paper's own theorem blocks — connect an AI engine for a full map"
                                                    if m.partial else "") +
                  (f"; dropped {m.quotes_dropped} quote(s) not found in the paper" if m.quotes_dropped else "") + ".")
        update(conn, paper_id, map=stored, map_engine=engine, status="MAPPED", status_detail=detail)
    await hub.broadcast("paper_progress", {"paper_id": paper_id, "status": "MAPPED", "detail": detail})
    await hub.broadcast("graph_updated", {"reason": "paper_mapped"})
    return stored


# ------------------------------------------------------------------ sources
SECTION_WEIGHTS = [
    (re.compile(r"related|prior work|literature", re.I), 0.5),
    (re.compile(r"method|model|approach|theor|analysis|proof|algorithm|architecture|preliminar|framework|main result|"
                r"setup|formulation|derivation|lemma", re.I), 3.0),
    (re.compile(r"experiment|result|evaluation|training|empirical|ablation", re.I), 2.0),
    (re.compile(r"intro|background|motivation|abstract|conclusion|discussion", re.I), 1.0),
]


def section_weight(section: str) -> float:
    top = section.split(" › ")
    for rx, w in SECTION_WEIGHTS:
        if any(rx.search(t) for t in top):
            return w
    return 1.5


def _norm_title(t: str) -> str:
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())


def _url(arxiv_id: str, doi: str, s2_id: str, title: str) -> str:
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    if doi:
        return f"https://doi.org/{doi}"
    if s2_id:
        return f"https://www.semanticscholar.org/paper/{s2_id}"
    return "https://scholar.google.com/scholar?q=" + re.sub(r"\s+", "+", title.strip())


def rank_references(doc: latex.PaperDoc, s2_refs: list[dict[str, Any]], anchors_missed: dict[str, str]) -> list[dict[str, Any]]:
    """FR6: Σ contexts × section weight (capped at 6 contexts) + 2·influential + 3 when cited in a section anchoring an
    idea you missed. Each row carries a one-line `why`."""
    s2_by_arxiv = {r["arxiv_id"]: r for r in s2_refs if r.get("arxiv_id")}
    s2_by_title = {_norm_title(r["title"]): r for r in s2_refs}
    rows = []
    keys = set(doc.bib) | set(doc.citations)
    for key in keys:
        b = doc.bib.get(key) or latex.BibEntry(key=key)
        ctxs = doc.citations.get(key, [])
        s2 = s2_by_arxiv.get(b.arxiv_id) or s2_by_title.get(_norm_title(b.title)) if (b.arxiv_id or b.title) else None
        title = b.title or (s2 or {}).get("title") or ""
        if not title or (not ctxs and not s2):
            continue
        sections: dict[str, int] = {}
        for c in ctxs:
            sections[c.section.split(" › ")[0]] = sections.get(c.section.split(" › ")[0], 0) + 1
        score = sum(section_weight(c.section) for c in ctxs[:6])
        if not ctxs and s2:
            score = len(s2.get("contexts") or [])
        influential = bool(s2 and s2.get("influential"))
        score += 2.0 if influential else 0.0
        missed_hit = next((name for sec, name in anchors_missed.items() if sec and sec in {c.section.split(" › ")[0] for c in ctxs}), "")
        if missed_hit:
            score += 3.0
        top_sec = max(sections, key=sections.get) if sections else ""
        why = []
        if sections:
            why.append(f"cited {sum(sections.values())}× " + ", ".join(f"in {s}" for s in sorted(sections, key=lambda s: -sections[s])[:2]))
        if missed_hit:
            why.append(f"where you missed ‘{missed_hit}’")
        if influential:
            why.append("marked influential by Semantic Scholar")
        if s2 and s2.get("intents"):
            why.append("used for " + "/".join(sorted(set(s2["intents"]))))
        arxiv_id = b.arxiv_id or (s2 or {}).get("arxiv_id") or ""
        doi = b.doi or (s2 or {}).get("doi") or ""
        rows.append({"direction": "reference", "ref_key": key, "title": title, "authors": b.authors[:300],
                     "year": int(b.year) if str(b.year).isdigit() else (s2 or {}).get("year"), "arxiv_id": arxiv_id,
                     "doi": doi, "s2_id": (s2 or {}).get("s2_id", ""), "url": _url(arxiv_id, doi, (s2 or {}).get("s2_id", ""), title),
                     "contexts": [{"sentence": c.sentence, "section": c.section} for c in ctxs[:4]] or
                                 [{"sentence": s, "section": ""} for s in (s2 or {}).get("contexts", [])[:3]],
                     "sections": sorted(sections, key=lambda s: -sections[s]), "influential": influential,
                     "intents": (s2 or {}).get("intents", []), "cited_by_count": (s2 or {}).get("cited_by_count"),
                     "is_survey": False, "for_node_id": "", "score": round(score + (0.01 if top_sec else 0), 3),
                     "why": "; ".join(why) or "listed in the references"})
    rows.sort(key=lambda r: -r["score"])
    return rows


def _store_refs(conn, paper_id: str, direction: str, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM paper_refs WHERE paper_id=? AND direction=?", (paper_id, direction))
    for r in rows:
        conn.execute(
            "INSERT INTO paper_refs (id, paper_id, direction, ref_key, title, authors, year, arxiv_id, doi, s2_id, url,"
            " contexts_json, sections_json, influential, intents_json, cited_by_count, is_survey, for_node_id, score, why)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (db.new_id("ref"), paper_id, direction, r.get("ref_key", ""), r["title"][:400], r.get("authors", ""),
             r.get("year"), r.get("arxiv_id", ""), r.get("doi", ""), r.get("s2_id", ""), r.get("url", ""),
             json.dumps(r.get("contexts", [])), json.dumps(r.get("sections", [])), int(bool(r.get("influential"))),
             json.dumps(r.get("intents", [])), r.get("cited_by_count"), int(bool(r.get("is_survey"))),
             r.get("for_node_id", ""), float(r.get("score", 0)), r.get("why", "")))


def refs(conn, paper_id: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"reference": [], "citation": [], "explainer": []}
    for r in conn.execute("SELECT * FROM paper_refs WHERE paper_id=? ORDER BY score DESC", (paper_id,)).fetchall():
        d = dict(r)
        d["contexts"] = json.loads(d.pop("contexts_json"))
        d["sections"] = json.loads(d.pop("sections_json"))
        d["intents"] = json.loads(d.pop("intents_json"))
        d["influential"] = bool(d["influential"])
        d["is_survey"] = bool(d["is_survey"])
        out[d["direction"]].append(d)
    return out


async def refresh_sources(paper_id: str, doc: Optional[latex.PaperDoc] = None, explainers: bool = True) -> None:
    """Re-rank references against what you have missed so far; fetch citing papers and explainers for your gaps."""
    doc = doc or load_doc(paper_id)
    if doc is None:
        return
    with db.ro() as conn:
        p = get(conn, paper_id)
        missed = missed_nodes(conn, paper_id)
        ls = links(conn, paper_id)
    anchors_missed = {l["anchor"].split(" › ")[0]: l["title"] for l in missed if l["anchor"]}
    s2_refs = await asyncio.to_thread(scholar.s2_references, p["arxiv_id"], p["doi"]) if (p["arxiv_id"] or p["doi"]) else []
    ranked = rank_references(doc, s2_refs, anchors_missed)
    with db.tx() as conn:
        _store_refs(conn, paper_id, "reference", ranked[:40])
    work = await asyncio.to_thread(scholar.openalex_work, p["arxiv_id"], p["doi"]) if (p["arxiv_id"] or p["doi"]) else None
    if work:
        citing = await asyncio.to_thread(scholar.openalex_citing, work["openalex_id"])
        rows = [{**c, "url": _url(c["arxiv_id"], c["doi"], "", c["title"]), "score": math.log1p(c["cited_by_count"] or 0),
                 "why": f"{c['cited_by_count'] or 0:,} citations" + (" · survey" if c["is_survey"] else "")} for c in citing]
        with db.tx() as conn:
            update(conn, paper_id, openalex_id=work["openalex_id"])
            _store_refs(conn, paper_id, "citation", rows)
    if explainers:
        gaps = missed or [l for l in ls if l["role"] == "prerequisite" and l["bkt_p_mastery"] < MISSED_BELOW]
        concept = {(p["map"].get("key_to_node") or {}).get(i.get("key"), ""): i.get("concept", "") for i in p["map"].get("ideas", [])}
        rows = []
        for g in gaps[:3]:
            found = await asyncio.to_thread(scholar.openalex_explainers, concept.get(g["node_id"]) or g["title"])
            if not found and concept.get(g["node_id"]):
                found = await asyncio.to_thread(scholar.openalex_explainers, " ".join(g["title"].split()[:3]))
            for e in found:
                rows.append({**e, "url": _url(e["arxiv_id"], e["doi"], "", e["title"]), "for_node_id": g["node_id"],
                             "score": math.log1p(e["cited_by_count"] or 0),
                             "why": f"on ‘{g['title']}’, " + ("which you missed" if g in missed else "which the paper assumes")})
        if rows or missed:
            with db.tx() as conn:
                _store_refs(conn, paper_id, "explainer", rows)
    await hub.broadcast("paper_progress", {"paper_id": paper_id, "status": p["status"], "detail": "Sources updated."})


def refresh_in_background(paper_id: str) -> None:
    t = asyncio.create_task(refresh_sources(paper_id))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


# ------------------------------------------------------------------ API views
def paper_out(conn, p: dict[str, Any]) -> dict[str, Any]:
    u = understanding(conn, p["id"])
    n = conn.execute("SELECT COUNT(*) c FROM paper_nodes WHERE paper_id=? AND role != 'prerequisite'", (p["id"],)).fetchone()["c"]
    return {k: p[k] for k in ("id", "source", "arxiv_id", "doi", "title", "authors", "year", "abstract", "text_kind",
                              "status", "status_detail", "map_engine", "session_id", "first_guess", "created_at", "updated_at")} | \
        {"understanding": u, "idea_count": n, "partial_map": bool(p["map"].get("partial"))}


def paper_detail(conn, p: dict[str, Any]) -> dict[str, Any]:
    m = p["map"]
    out = paper_out(conn, p)
    out["map"] = {"summary": m.get("summary", ""), "contributions": m.get("contributions", []),
                  "notation": m.get("notation", []), "key_argument": m.get("key_argument"),
                  "quotes_dropped": m.get("quotes_dropped", 0)}
    out["ideas"] = [{"node_id": l["node_id"], "title": l["title"], "role": l["role"], "anchor": l["anchor"], "quote": l["quote"],
                     "mastery": l["bkt_p_mastery"], "answered": l["fsrs_reps"] > 0, "node_type": l["node_type"]}
                    for l in links(conn, p["id"])]
    out["sources"] = refs(conn, p["id"])
    ax = p["arxiv_id"]
    out["links"] = {"arxiv": f"https://arxiv.org/abs/{ax}" if ax else None, "pdf": f"https://arxiv.org/pdf/{ax}" if ax else None,
                    "code": f"https://huggingface.co/papers/{ax}" if ax else None,
                    "semantic_scholar": f"https://www.semanticscholar.org/arxiv/{ax}" if ax else None}
    return out
