"""SQLite hypergraph, topological depth, SymPy sandbox, workspace corpus and counterexample library."""
from __future__ import annotations

import json
import sqlite3

import pytest

from backend import config, tools


def test_schema_pragmas_and_checks(fresh_db):
    db = fresh_db
    with db.ro() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"nodes", "hyperedges", "sessions", "telemetry_traces", "subagent_artifacts"} <= tables
    with pytest.raises(sqlite3.IntegrityError):
        with db.tx() as conn:
            db.upsert_node(conn, {"id": "x", "title": "x", "node_type": "NOT_A_TYPE", "statement_latex": "", "intuition_summary": "",
                                  "domain_cluster": "d"})


def test_hypergraph_crud_and_cascade(fresh_db):
    db = fresh_db
    with db.tx() as conn:
        for nid, t in (("a", "AXIOM"), ("b", "PROPOSITION"), ("c", "PROPOSITION")):
            db.upsert_node(conn, {"id": nid, "title": nid, "node_type": t, "statement_latex": nid, "intuition_summary": "",
                                  "domain_cluster": "D"})
        eid = db.insert_edge(conn, "DEDUCTION", ["a", "b"], "c", r"a \land b \implies c")
    with db.ro() as conn:
        edges = db.all_edges(conn)
        assert edges[0]["id"] == eid and edges[0]["premise_node_ids"] == ["a", "b"]
        out = db.node_out(db.get_node(conn, "c"))
        assert 0.99 <= out["retrievability"] <= 1.0 and set(out["cues"]) == set(
            ["cue_symbolic", "cue_disguised_notation", "cue_geometric", "cue_computational", "cue_adversarial"])
    with db.tx() as conn:
        conn.execute("DELETE FROM nodes WHERE id='c'")
    with db.ro() as conn:
        assert db.all_edges(conn) == []  # ON DELETE CASCADE through conclusion_node_id


def test_seed_graph_shape_and_topological_depth(fresh_db):
    from backend import seed
    db = fresh_db
    with db.tx() as conn:
        seed.seed_graph(conn)
    with db.ro() as conn:
        nodes = {n["id"]: n for n in db.all_nodes(conn)}
        edges = db.all_edges(conn)
        demos = db.list_artifacts(conn, agent_name="SANDBOX_DEMO_BUILDER")
    assert len(nodes) == 20 and len(edges) == 16 and len(demos) == 3
    assert {e["edge_type"] for e in edges} == {"DEDUCTION", "CONTRASTIVE", "ISOMORPHISM", "CUE_TRIGGER"}
    depth = {k: v["logical_depth"] for k, v in nodes.items()}
    # axioms only at the bottom layer; every DEDUCTION flows strictly upward
    assert {k for k, d in depth.items() if d == 0} == {"ax_inner_product_bilinearity", "ax_orthogonal_matrix_preserve",
                                                       "ax_linearity_expectation"}
    for e in edges:
        if e["edge_type"] == "DEDUCTION":
            assert all(depth[p] < depth[e["conclusion_node_id"]] for p in e["premise_node_ids"])
    assert depth["prop_scaled_dot_product_variance"] == 2 and depth["prop_rope_relative_invariance"] == 2
    assert depth["prop_double_dqn_decoupling"] == depth["prop_qlearning_maximization_bias"] + 1
    # shadow nodes sit at the depth of the concept they shadow
    assert depth["bug_uncorrelated_implies_indep"] == depth["prop_var_indep_sum"]
    assert depth["cnt_unbounded_indicator_escape"] == depth["prop_dct_vs_mct"]
    with db.tx() as conn:
        assert db.recompute_depths(conn) == {}  # idempotent


def test_sympy_verifier_sandbox():
    ok = tools.verify_math_sympy("import sympy as sp\nx=sp.symbols('x')\nassert sp.simplify(sp.diff(sp.sin(x)**2,x)-sp.sin(2*x))==0\nprint('VERIFIED: d/dx sin^2 = sin 2x')")
    assert ok.verified and ok.returncode == 0 and "VERIFIED" in ok.as_log()
    bad = tools.verify_math_sympy("print('nothing verified')")
    assert bad.ok and not bad.verified
    blocked = tools.verify_math_sympy("import socket")
    assert not blocked.ok and "blocked" in blocked.stderr
    nofile = tools.verify_math_sympy("open('/etc/hosts').read()")
    assert not nofile.ok and "blocked" in nofile.stderr
    slow = tools.verify_math_sympy("while True: pass", timeout=1.5)
    assert slow.timed_out and not slow.verified
    eq = tools.verify_math_sympy(tools.check_equivalence_code("(x+y)**2", "x**2+2*x*y+y**2", "x y"))
    assert eq.verified
    neq = tools.verify_math_sympy(tools.check_equivalence_code("(x+y)**2", "x**2+y**2", "x y"))
    assert neq.ok and not neq.verified and "MISMATCH" in neq.stdout


def test_counterexample_library_all_verify():
    from backend.agents import subagents
    for ce in subagents.COUNTEREXAMPLE_LIBRARY:
        res = tools.verify_math_sympy(ce["code"])
        assert res.verified, f"{ce['id']}: {res.as_log()}"
    hit = subagents.match_counterexample("uncorrelated variables are always independent")
    assert hit and hit["id"] == "cnt_uncorrelated_not_independent"
    assert subagents.find_universal_claims("We can always swap the limit and the integral. Fine.")
    assert subagents.extract_checkable_equations("so (a+b)^2 = a^2 + 2ab + b^2 here") == [("(a+b)**2", "a**2 + 2*a*b + b**2")]


def test_workspace_corpus(fresh_db):
    files = {f["path"] for f in tools.list_workspace_files()}
    assert "notes/measure_rl_transformers.tex" in files and "problems/bellman_contraction_pset.tex" in files
    data = tools.read_tex_or_md("notes/measure_rl_transformers.tex")
    envs = [b["env"] for b in data["blocks"]]
    assert "section" in envs and "theorem" in envs and "definition" in envs
    probs = [b for b in tools.read_tex_or_md("problems/bellman_contraction_pset.tex")["blocks"] if b["env"] == "problem"]
    assert len(probs) == 3 and probs[0]["title"] == "Two-state chain"
    hits = tools.grep_workspace("Bellman")
    assert hits and all({"path", "line", "text"} <= set(h) for h in hits)
    assert tools.corpus_search("dominated convergence integrable envelope")[0]["env"] in ("theorem", "definition", "lemma")
    with pytest.raises(ValueError):
        tools.read_tex_or_md("../../etc/passwd")
    s = tools.write_scratch("% hi\n")
    assert s["content"] == "% hi\n" and config.SCRATCH_PATH.exists()


def test_offline_literature():
    entries, source = tools.search_arxiv("double dqn overestimation")
    assert source == "offline" and "Double Q-learning" in entries[0]["title"]


def test_ontologist_tex_import(fresh_db):
    from backend.agents import subagents
    db = fresh_db
    with db.tx() as conn:
        r = subagents.import_tex_blocks(conn, "notes/measure_rl_transformers.tex", None)
    assert len(r["nodes"]) >= 6 and r["edges"]
    with db.ro() as conn:
        types = {db.get_node(conn, n)["node_type"] for n in r["nodes"]}
        assert {"AXIOM", "PROPOSITION"} <= types
        e = db.all_edges(conn)[0]
        assert json.dumps(e["premise_node_ids"])
