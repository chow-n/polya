"""The research loop (docs/specs/paper-reading): arXiv refs, LaTeX parsing, safe extraction, quote grounding, reference
ranking, the partial map, and a full paper session end-to-end. No network: fetchers and scholarly APIs are faked."""
from __future__ import annotations

import io
import shutil
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import llm
from backend.papers import fetch, latex, mapper, scholar
from backend.papers import service as papers
from backend.tests.conftest import point_config_at

FIXTURE = Path(__file__).parent / "fixtures" / "paper_src"


def test_arxiv_reference_forms():
    assert fetch.parse_arxiv_ref("1706.03762") == "1706.03762"
    assert fetch.parse_arxiv_ref("arXiv:2401.01234v2") == "2401.01234v2"
    assert fetch.parse_arxiv_ref("https://arxiv.org/pdf/1706.03762v7.pdf") == "1706.03762v7"
    assert fetch.parse_arxiv_ref("https://arxiv.org/abs/math/0211159") == "math/0211159"
    assert fetch.parse_arxiv_ref("why attention divides by sqrt d") is None
    assert fetch.parse_arxiv_ref("") is None


def test_latex_parsing_of_a_source_tree():
    doc = latex.parse_source(FIXTURE)
    assert doc.title == "A Toy Paper on Contractions" and doc.abstract.startswith("We show that every contraction")
    assert [s.title for s in doc.sections] == ["Introduction", "Related Work", "Method"]     # \input inlined
    kinds = [(b.kind, b.label) for b in doc.blocks]
    assert ("definition", "def:contraction") in kinds
    assert ("assump", "as:complete") in kinds or ("assumption", "as:complete") in kinds
    thm = next(b for b in doc.blocks if b.label == "thm:main")
    assert thm.kind == "theorem" and thm.title == "Banach" and "Cauchy" in thm.proof     # \newtheorem alias + proof
    assert r"\mathbb{R}" in thm.body                                                     # zero-arg macro expanded
    assert set(doc.citations) == {"bellman1957", "sutton2018", "banach1922"}             # the commented \cite is gone
    assert {c.section for c in doc.citations["bellman1957"]} == {"Introduction", "Method"}
    assert doc.bib["sutton2018"].title == "Reinforcement Learning: An Introduction"
    assert doc.bib["sutton2018"].arxiv_id == "1234.56789" and doc.bib["banach1922"].year == "1922"
    again = latex.PaperDoc.from_json(doc.to_json())
    assert again.citations["banach1922"][0].section == doc.citations["banach1922"][0].section


def _tar(members: dict[str, bytes], links: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        for name, target in (links or {}).items():
            ti = tarfile.TarInfo(name)
            ti.type = tarfile.SYMTYPE
            ti.linkname = target
            tf.addfile(ti)
    return buf.getvalue()


def test_safe_extraction_refuses_escapes_links_and_binaries(tmp_path):
    data = _tar({"main.tex": b"\\begin{document}x\\end{document}", "../evil.tex": b"x", "/abs.tex": b"x",
                 "fig.png": b"\x89PNG", "sub/refs.bbl": b"\\bibitem{a} A."}, links={"link.tex": "/etc/passwd"})
    written = fetch.safe_extract(data, tmp_path / "src")
    names = sorted(str(p.relative_to((tmp_path / "src").resolve())) for p in written)
    assert names == ["main.tex", "sub/refs.bbl"]
    assert not (tmp_path / "evil.tex").exists()
    single = fetch.safe_extract(__import__("gzip").compress(b"\\documentclass{article}"), tmp_path / "one")
    assert [p.name for p in single] == ["main.tex"]


def test_quotes_must_occur_in_the_paper():
    doc = latex.parse_source(FIXTURE)
    norm = mapper._norm(doc.full_text() + " " + " ".join(b.body for b in doc.blocks))
    assert mapper.quote_in_text("The metric space $(X, d)$ is complete.", norm)
    assert mapper.quote_in_text("we use the operator view of [bellman1957] throughout the proof", norm)
    assert not mapper.quote_in_text("Every contraction is differentiable everywhere on the real line.", norm)
    assert not mapper.quote_in_text("short", norm)


def test_reference_ranking_prefers_method_citations_and_your_misses():
    doc = latex.parse_source(FIXTURE)
    rows = papers.rank_references(doc, [], {})
    order = [r["ref_key"] for r in rows]
    assert order[0] == "bellman1957"                          # intro (1) + method (3) beats related work (0.5) + method
    assert "cited 2× in Introduction, in Method" in rows[0]["why"] or "cited 2×" in rows[0]["why"]
    boosted = papers.rank_references(doc, [{"title": "Sur les opérations dans les ensembles abstraits", "arxiv_id": "",
                                            "influential": True, "intents": ["methodology"], "contexts": []}],
                                     {"Method": "Contraction"})
    top = boosted[0]
    assert top["ref_key"] == "banach1922" and "where you missed ‘Contraction’" in top["why"]
    assert next(r for r in rows if r["ref_key"] == "sutton2018")["url"] == "https://arxiv.org/abs/1234.56789"


def test_partial_map_from_theorem_blocks():
    doc = latex.parse_source(FIXTURE)
    m = mapper.validate(mapper.partial_map(doc), doc, set())
    roles = {i.role for i in m.ideas}
    assert {"definition", "assumption"} <= roles and "main_result" in roles and m.partial
    assert m.edges and all(i.anchor == "Method" for i in m.ideas)


# ------------------------------------------------------------------ end to end
MAIN_QUOTE = "Under the assumption above, every $\\gamma$-contraction has a unique fixed point"
FAKE_MAP = {
    "summary": "Contractions on complete spaces have unique fixed points.", "contributions": ["Banach's theorem, re-proved"],
    "ideas": [
        {"key": "pre", "title": "Banach fixed point theorem", "role": "prerequisite", "existing_node_id": "prop_banach_contraction"},
        {"key": "def", "title": "Contraction", "role": "definition", "anchor": "Method",
         "statement_latex": r"$d(Tx,Ty)\le\gamma d(x,y)$", "quote": "A map $T: X \\to X$ is a $\\gamma$-contraction if"},
        {"key": "ass", "title": "Completeness", "role": "assumption", "anchor": "§ Method",
         "statement_latex": "$(X,d)$ complete", "quote": "The metric space $(X, d)$ is complete."},
        {"key": "main", "title": "Unique fixed point", "role": "main_result", "anchor": "Method",
         "statement_latex": "unique $x^*$", "quote": MAIN_QUOTE, "concept": "fixed point theorem"},
        {"key": "fake", "title": "Invented claim", "role": "claim", "anchor": "Nowhere",
         "statement_latex": "x", "quote": "This sentence does not appear anywhere in the paper at all."},
    ],
    "edges": [{"premises": ["def", "ass"], "conclusion": "main", "reasoning": "Cauchy + completeness"},
              {"premises": ["ghost"], "conclusion": "main"}],
    "notation": [{"symbol_latex": r"\gamma", "meaning": "contraction modulus"}],
    "key_argument": {"claim": "Contractions have unique fixed points.",
                     "steps": ["Iterate T.", "Distances shrink by gamma.", "The sequence is Cauchy.",
                               "Completeness gives a limit.", "Contraction gives uniqueness."]},
    "assumptions_for_main": [{"label": "The space is complete", "keywords": ["complete", "cauchy"], "challenge": "Why complete?"},
                             {"label": "gamma < 1", "keywords": ["gamma", "less than one"], "challenge": "What if gamma = 1?"}],
}
FAKE_REFEREE = {"claim": "Contractions have unique fixed points.",
                "steps": ["Iterate T.", "Distances shrink.", "Every sequence converges.", "Take the limit.", "Unique."],
                "flawed_index": 3, "violated_keywords": ["cauchy", "complete"], "explanation": "Only Cauchy sequences in a complete space converge.",
                "counterexample": "x_n = n"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    point_config_at(tmp_path)

    def fake_source(arxiv_id, dest):
        shutil.copytree(FIXTURE, dest / "source")
        return "latex"
    monkeypatch.setattr(fetch, "arxiv_metadata", lambda i: {"arxiv_id": i, "title": "A Toy Paper on Contractions",
                                                             "authors": ["S. Banach"], "year": 1922, "abstract": "", "doi": ""})
    monkeypatch.setattr(fetch, "fetch_arxiv_source", fake_source)
    monkeypatch.setattr(scholar, "s2_references", lambda *a, **k: [])
    monkeypatch.setattr(scholar, "openalex_work", lambda *a, **k: {"openalex_id": "W1", "title": "t", "arxiv_id": "", "doi": "",
                                                                    "year": 1922, "cited_by_count": 1, "is_survey": False})
    monkeypatch.setattr(scholar, "openalex_citing", lambda *a, **k: [{"title": "A survey of fixed points", "year": 2001,
                                                                       "arxiv_id": "", "doi": "10.1/x", "openalex_id": "W2",
                                                                       "cited_by_count": 50, "is_survey": True}])
    searched = []
    monkeypatch.setattr(scholar, "openalex_explainers", lambda c, n=2: searched.append(c) or [])
    from backend.main import app
    with TestClient(app) as c:
        c.searched = searched
        yield c


def scripted_engine(monkeypatch):
    real = llm.complete_json

    async def fake(system, user, max_tokens=2500, timeout=None):
        from backend.agents import prompts
        if system == prompts.PAPER_MAPPER:
            return llm.LLMResult(FAKE_MAP, "scripted")
        if system == prompts.PAPER_REFEREE:
            return llm.LLMResult(FAKE_REFEREE, "scripted")
        return await real(system, user, max_tokens)   # everything else: deterministic engine
    monkeypatch.setattr(llm, "complete_json", fake)


def wait_ready(client, pid: str) -> dict:
    import time
    for _ in range(200):
        d = client.get(f"/api/papers/{pid}").json()
        if d["status"] in ("MAPPED", "FAILED") and d["status_detail"] == "Sources updated.":
            return d
        time.sleep(0.05)
    return d


def test_ingest_without_engine_gives_partial_map(client):
    r = client.post("/api/papers", json={"arxiv": "https://arxiv.org/abs/2101.00001v1"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["status"] == "FETCHING"                                               # ingest runs in the background
    d = wait_ready(client, pid)
    assert d["status"] == "MAPPED" and d["partial_map"] and d["idea_count"] >= 3, d["status_detail"]
    assert "connect an AI engine" in d["status_detail"]
    assert d["sources"]["reference"][0]["ref_key"] == "bellman1957"
    assert d["sources"]["citation"][0]["is_survey"] and d["links"]["arxiv"].endswith("2101.00001")
    assert client.post("/api/papers", json={"arxiv": "2101.00001"}).json()["id"] == pid      # no duplicate ingest
    assert client.post("/api/papers", json={"arxiv": "not a paper"}).status_code == 422
    assert client.post("/api/papers/upload?filename=x.pdf", content=b"hello").status_code == 422


def test_full_paper_session(client, monkeypatch):
    scripted_engine(monkeypatch)
    from backend import db
    with db.tx() as conn:   # a prerequisite you are weak on → explainers are looked up for it
        db.update_node_fields(conn, "prop_banach_contraction", bkt_p_mastery=0.2)
    pid = client.post("/api/papers", json={"arxiv": "2101.00002"}).json()["id"]
    d = wait_ready(client, pid)
    assert d["status"] == "MAPPED" and not d["partial_map"] and d["map"]["quotes_dropped"] == 1
    roles = {i["title"]: i for i in d["ideas"]}
    assert roles["Invented claim"]["quote"] == "" and roles["Completeness"]["anchor"] == "Method"
    assert any(i["node_id"] == "prop_banach_contraction" and i["role"] == "prerequisite" for i in d["ideas"])
    assert client.searched[:1] == ["Banach fixed point theorem"]

    st = client.post(f"/api/papers/{pid}/session").json()
    sid = st["session"]["id"]
    assert st["session"]["sub_mode"] == "PAPER" and st["active_step"]["title"].startswith("Skim")
    assert client.post(f"/api/papers/{pid}/session").json()["session"]["id"] == sid             # resumes, no duplicate
    from backend.tests.test_api_and_modes import hidden_meta
    quotes = {i["node_id"]: i["quote"] for i in d["ideas"]}
    seen = []
    for _ in range(40):
        step = st["active_step"]
        seen.append(step["kind"])
        if step["kind"] == "COMPLETE":
            break
        meta = hidden_meta(sid)
        guess = "I think the main result is a unique fixed point, needing completeness and gamma below one."
        sub = {"step_id": step["step_id"], "raw_prediction_locked": guess, "verification_thinking": guess, "confidence": 0.7}
        if step["kind"] in ("PROBE", "CHECK"):
            sub["selected_answer"] = meta["correct"]
        if step["kind"] == "REFEREE":
            sub.update(flagged_step_index=3, counterexample_text="Cauchy sequences need a complete space; x_n = n diverges.")
        if step["kind"] == "READING" and quotes.get(step["target_node_ids"][0]):
            assert step["body_markdown"].startswith("> " + quotes[step["target_node_ids"][0]])  # taught from the paper's words
        r = client.post(f"/api/sessions/{sid}/submit", json=sub)
        assert r.status_code == 200, r.text
        st = r.json()["state"]
    assert seen[0] == "PREDICT" and "REFEREE" in seen and "FEYNMAN" in seen and seen[-1] == "COMPLETE"
    assert seen.index("REFEREE") > seen.index("READING")
    body = st["active_step"]["body_markdown"]
    assert "Your first guess" in body and "unique fixed point" in body and "Read next" in body
    p = client.get(f"/api/papers/{pid}").json()
    assert p["first_guess"].startswith("I think") and p["understanding"] is not None and p["session_id"] == sid
