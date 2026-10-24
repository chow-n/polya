"""Integration tests: every REST endpoint, the WebSocket hub, and all 6 pedagogical modes end-to-end."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.tests.conftest import point_config_at

GOOD = ("Each term q_i k_i has variance one, the terms are uncorrelated so the variance of the sum adds up to d_k; "
        "scaling by 1/sqrt(d_k) multiplies variance by 1/d_k (quadratic scaling) so it is back to one.")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    point_config_at(tmp_path_factory.mktemp("api"))
    from backend.main import app
    with TestClient(app) as c:
        yield c


def hidden_meta(session_id: str) -> dict:
    from backend import db
    with db.ro() as conn:
        return db.load_session(conn, session_id)["active_step"].get("_meta", {})


def answer(client, state: dict, good: bool = True, confidence: float = 0.8, text: str = GOOD) -> dict:
    step = state["active_step"]
    sid = state["session"]["id"]
    meta = hidden_meta(sid)
    sub = {"step_id": step["step_id"], "raw_prediction_locked": text, "verification_thinking": text, "confidence": confidence}
    if step["kind"] in ("PROBE", "CHECK"):
        ids = [o["id"] for o in step["options"]]
        sub["selected_answer"] = meta["correct"] if good else next(i for i in ids if i != meta["correct"])
    r = client.post(f"/api/sessions/{sid}/submit", json=sub)
    assert r.status_code == 200, r.text
    return r.json()


def test_seeded_read_endpoints(client):
    assert client.get("/api/health").json()["status"] == "ok"
    g = client.get("/api/graph").json()
    assert len(g["nodes"]) >= 20 and len(g["hyperedges"]) >= 16
    s = client.get("/api/stats").json()
    assert s["llm_engine"] == "deterministic" and s["calibration"]["n"] > 0
    assert s["bjork_window_count"] >= 1 and s["hypercorrection_count"] >= 1
    assert abs(s["calibration"]["mean_brier"] - (s["calibration"]["reliability"] - s["calibration"]["resolution"]
                                                 + s["calibration"]["uncertainty"])) < 0.05
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 3 and {x["mode"] for x in sessions} == {"PROBE", "PRACTICE", "REFEREE_DUEL"}
    assert any(x["status"] == "COMPLETED" for x in sessions)
    due = client.get("/api/due").json()
    assert due == sorted(due, key=lambda d: d["next_due_at"])
    q = client.get("/api/practice/queue?limit=5").json()
    assert len(q) == 5 and all(0 <= x["retrievability"] <= 1 for x in q)
    detail = client.get("/api/nodes/prop_scaled_dot_product_variance").json()
    assert "prop_var_indep_sum" in detail["ancestors"] and detail["incoming"]
    assert client.get("/api/nodes/prop_var_indep_sum").json()["buggy_rule_links"] == ["bug_uncorrelated_implies_indep"]
    assert client.get("/api/nodes/nope").status_code == 404
    arts = client.get("/api/artifacts?limit=200").json()
    agents = {a["agent_name"] for a in arts}
    assert {"SANDBOX_DEMO_BUILDER", "SYMBOLIC_VERIFIER", "BUG_LIBRARY_DIAGNOSTICIAN", "ONTOLOGIST_EXTRACTOR"} <= agents
    demo = client.get("/api/artifacts/demo_attention_softmax").json()
    assert demo["content_type"] == "html_demo" and "HARNESS_DEMO_TELEMETRY" in demo["payload_text"]


def test_workspace_scratch_settings_and_demo_telemetry(client):
    files = client.get("/api/workspace/files").json()
    assert any(f["path"].startswith("notes/session_") for f in files)  # ontologist export from the seeded session
    f = client.get("/api/workspace/file", params={"path": "problems/bellman_contraction_pset.tex"}).json()
    assert sum(b["env"] == "problem" for b in f["blocks"]) == 3
    assert client.put("/api/scratch", json={"content": "x^2"}).json()["content"] == "x^2"
    assert client.get("/api/scratch").json()["content"] == "x^2"
    st = client.get("/api/settings").json()
    assert st["provider"] in ("auto", "deterministic") and "anthropic" in st["keys_present"]
    st2 = client.put("/api/settings", json={"provider": "deterministic"}).json()
    assert st2["provider"] == "deterministic" and st2["active_engine"] == "deterministic"
    before = client.get("/api/nodes/prop_scaled_dot_product_variance").json()["node"]["cues"]["cue_geometric"]
    r = client.post("/api/demo-telemetry", json={"demo_id": "demo_attention_softmax", "params": {"d_k": 256, "tau": 16},
                                                 "challenge_solved": True, "summary": "tau=16"}).json()
    assert "prop_scaled_dot_product_variance" in r["cue_updates"]
    after = client.get("/api/nodes/prop_scaled_dot_product_variance").json()["node"]["cues"]["cue_geometric"]
    assert after > before


def test_websocket_hub(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        assert ws.receive_json()["type"] == "stats"
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"
        ws.send_json({"type": "scratch_write", "content": "% from ws"})
        msg = ws.receive_json()
        while msg["type"] != "scratch_update":
            msg = ws.receive_json()
        assert msg["payload"]["content"] == "% from ws"
    with client.websocket_connect("/ws/dictation") as ws:
        assert ws.receive_json()["type"] == "unavailable"


def test_subagent_manual_runs(client):
    v = client.post("/api/subagents/SYMBOLIC_VERIFIER/run", json={"topic": "(x+1)**2 = x**2+2*x+1"}).json()
    assert v["status"] == "COMPLETED" and "VERIFIED" in v["payload_text"]
    lit = client.post("/api/subagents/LITERATURE_RESEARCHER/run", json={"topic": "rotary position embedding"}).json()
    assert "RoFormer" in lit["payload_text"]
    rag = client.post("/api/subagents/LOCAL_CORPUS_RAG/run", json={"topic": "dominated convergence envelope"}).json()
    assert "measure_rl_transformers.tex" in rag["payload_text"]
    svg = client.post("/api/subagents/SVG_DIAGRAM_MAKER/run", json={"node_id": "prop_rope_relative_invariance"}).json()
    assert svg["payload_text"].lstrip().startswith("<svg") and 'viewBox="0 0 720 340"' in svg["payload_text"]
    demo = client.post("/api/subagents/SANDBOX_DEMO_BUILDER/run", json={"node_id": "prop_banach_contraction"}).json()
    assert demo["payload_text"].startswith("<!DOCTYPE html") and "harness-targets" in demo["payload_text"]
    ce = client.post("/api/subagents/COUNTEREXAMPLE_SYNTHESIZER/run",
                     json={"node_id": "prop_dct_vs_mct", "topic": "You can always swap a pointwise limit and an integral."}).json()
    assert ce["agent_name"] == "COUNTEREXAMPLE_SYNTHESIZER" and ce["status"] == "COMPLETED"
    onto = client.post("/api/subagents/ONTOLOGIST_EXTRACTOR/run", json={"filename": "notes/measure_rl_transformers.tex"}).json()
    assert onto["content_type"] == "graph_diff"
    assert client.post("/api/subagents/NOPE/run", json={}).status_code == 404


def test_mode_probe_then_teach(client):
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "RoPE relative position",
                                            "target_node_id": "prop_rope_relative_invariance"}).json()
    step = st["active_step"]
    assert step["kind"] == "PROBE" and step["options_locked"] and step["eig_table"]
    assert step["eig_table"][0]["eig"] == max(r["eig"] for r in step["eig_table"])
    assert "_meta" not in step and "correct" not in str(step["options"])
    # epistemic lock is enforced server-side
    r = client.post(f"/api/sessions/{st['session']['id']}/submit", json={"step_id": step["step_id"], "selected_answer": "A"})
    assert r.status_code == 422
    kinds = []
    for _ in range(40):
        # miss the first probe (low confidence) so the plan keeps an unmastered node to teach
        res = answer(client, st, good=bool(kinds), confidence=0.8 if kinds else 0.3)
        st = res["state"]
        kinds.append(st["active_step"]["kind"])
        if st["active_step"]["kind"] == "COMPLETE":
            break
    assert kinds[-1] == "COMPLETE" and st["session"]["status"] == "COMPLETED"
    assert "CHECK" in kinds  # the missed node was taught and checked
    assert any(t["outcome"] == "FAILED" for t in st["traces"] if t["phase"] == "PROBE")


def test_mode_productive_failure_and_teach_with_remediation(client):
    st = client.post("/api/sessions", json={"mode": "PRODUCTIVE_FAILURE", "target_goal": "Why does attention divide by sqrt dk",
                                            "target_node_id": "prop_scaled_dot_product_variance"}).json()
    assert st["active_step"]["kind"] == "PRODUCTIVE_FAILURE"
    res = answer(client, st, text="I tried dividing by d_k like an average, and every variance always adds.")
    assert res["trace"]["outcome"] == "EXPLORATION_LOGGED" and "insight" in res["feedback_markdown"].lower()
    st = res["state"]
    # TEACH: walk to the first CHECK and fail it confidently → hypercorrection + Δ remediation
    st = client.post("/api/sessions", json={"mode": "TEACH", "target_goal": "Double DQN",
                                            "target_node_id": "prop_double_dqn_decoupling"}).json()
    for _ in range(10):
        if st["active_step"]["kind"] == "CHECK":
            break
        st = answer(client, st)["state"]
    assert st["active_step"]["kind"] == "CHECK"
    nid = st["active_step"]["target_node_ids"][0]
    res = answer(client, st, good=False, confidence=0.85, text="I think it is always like averaging, just a guess honestly.")
    assert res["trace"]["outcome"] == "HIGH_CONFIDENCE_ERROR"
    assert res["delta_after"] == 0.5
    node = client.get(f"/api/nodes/{nid}").json()["node"]
    assert node["hypercorrection_flag"] == 1
    plan = res["state"]["session"]["dependency_plan"]
    assert any(p["remedial"] for p in plan), "a remedial sub-node must be spliced into the plan"
    idx = next(i for i, p in enumerate(plan) if p["remedial"])
    assert plan[idx + 1]["node_id"] == nid or any(p["node_id"] == nid for p in plan[idx + 1:])


def test_mode_practice_chunks_hints_and_submit(client):
    st = client.post("/api/sessions", json={"mode": "PRACTICE", "target_goal": "practice",
                                            "target_node_id": "prop_var_indep_sum", "cue_level": 2}).json()
    step = st["active_step"]
    sid = st["session"]["id"]
    assert step["kind"] == "PRACTICE_CHUNK" and step["cue_level"] == 2
    assert client.post(f"/api/sessions/{sid}/hint", json={"rung": "R2"}).status_code == 409  # ladder order enforced
    h0 = client.post(f"/api/sessions/{sid}/hint", json={"rung": "R0"}).json()
    assert h0["rung"] == "R0" and h0["fsrs_rating_cap"] == 3 and h0["stability_multiplier"] == 1.0
    h1 = client.post(f"/api/sessions/{sid}/hint", json={"rung": "R1", "current_thinking": "so Var = 2 here."}).json()
    assert h1["hint_markdown"]
    groups = hidden_meta(sid)["concept_groups"]
    ev = client.post(f"/api/sessions/{sid}/chunk", json={"text": "(a+b)^2 = a^2 + b^2", "confidence": 0.5}).json()
    assert ev["slip_detected"] and "verifier" in ev["feedback_markdown"].lower()
    ev2 = client.post(f"/api/sessions/{sid}/chunk", json={"text": " ".join(g[0] for g in groups)}).json()
    assert ev2["chunk_index"] == 1 and len(ev2["matched_concepts"]) == len(groups)
    res = answer(client, client.get(f"/api/sessions/{sid}").json(), confidence=0.7)
    assert res["trace"]["max_hint_rung"] == "R1" and res["trace"]["phase"] == "PRACTICE_CHUNK"
    assert res["trace"]["outcome"] in ("SOLVED_WITH_HINTS", "PARTIAL")
    assert res["node_updates"][0]["rating"] <= 3


def test_practice_problem_import_and_contrastive_pair(client):
    st = client.post("/api/sessions", json={"mode": "PRACTICE", "target_goal": "pset",
                                            "problem_file": "problems/bellman_contraction_pset.tex"}).json()
    assert "Two-state chain" in st["active_step"]["prompt_latex"]
    st2 = client.post("/api/sessions", json={"mode": "PRACTICE", "target_goal": "pair", "contrastive_pair": True,
                                             "target_node_id": "prop_double_dqn_decoupling"}).json()
    assert st2["active_step"]["contrastive_pair_node_id"] == "prop_qlearning_maximization_bias"


def test_mode_proof_referee(client):
    st = client.post("/api/sessions", json={"mode": "REFEREE_DUEL", "sub_mode": "PROOF_REFEREE",
                                            "target_goal": "lim int", "target_node_id": "prop_dct_vs_mct"}).json()
    step = st["active_step"]
    assert step["kind"] == "REFEREE" and len(step["proof_steps"]) == 5
    meta = hidden_meta(st["session"]["id"])
    r = client.post(f"/api/sessions/{st['session']['id']}/submit", json={
        "step_id": step["step_id"], "flagged_step_index": meta["flawed_index"], "confidence": 0.9,
        "verification_thinking": " ".join(meta["violated_keywords"]) + " the hypothesis is violated",
        "counterexample_text": meta["counterexample"]}).json()
    assert r["trace"]["is_correct"] == 1 and r["trace"]["phase"] == "REFEREE"
    assert r["node_updates"][0]["bkt_after"] > r["node_updates"][0]["bkt_before"]
    assert r["state"]["active_step"]["kind"] == "COMPLETE"


def test_mode_feynman_student(client):
    st = client.post("/api/sessions", json={"mode": "REFEREE_DUEL", "sub_mode": "FEYNMAN_STUDENT",
                                            "target_goal": "variance", "target_node_id": "prop_var_indep_sum"}).json()
    step = st["active_step"]
    sid = st["session"]["id"]
    assert step["kind"] == "FEYNMAN" and step["duel_transcript"][0]["role"] == "student"
    conds = hidden_meta(sid)["conditions"]
    first = client.post(f"/api/sessions/{sid}/duel", json={"message": "It's just true."}).json()
    assert not first["resolved"] and first["boundary_conditions_remaining"] == len(conds)
    for c in conds:
        rep = client.post(f"/api/sessions/{sid}/duel", json={"message": f"Precisely: {c['keywords'][0]}."}).json()
    assert rep["resolved"] and rep["boundary_conditions_remaining"] == 0
    res = answer(client, client.get(f"/api/sessions/{sid}").json(), confidence=0.8)
    assert res["trace"]["is_correct"] == 1 and res["state"]["session"]["status"] == "COMPLETED"


def test_stale_step_and_custom_goal(client):
    st = client.post("/api/sessions", json={"mode": "TEACH", "target_goal": "Spectral theorem for symmetric matrices over the reals"}).json()
    assert st["session"]["dependency_plan"][-1]["node_id"].startswith("goal_") or st["active_step"]["kind"] in ("PREDICT", "READING")
    r = client.post(f"/api/sessions/{st['session']['id']}/submit", json={"step_id": "bogus"})
    assert r.status_code == 409


def test_sympy_verifier_and_api(client):
    """Spec §8.1: the verifier subprocess plus the REST surface used by every mode."""
    from backend import tools
    res = tools.verify_math_sympy("import sympy as sp\nk=sp.symbols('d_k',positive=True)\n"
                                  "assert sp.simplify(k*(1/sp.sqrt(k))**2-1)==0\nprint('VERIFIED: Var(q.k/sqrt(d_k)) = 1')")
    assert res.verified
    for path in ("/api/health", "/api/graph", "/api/stats", "/api/due", "/api/practice/queue", "/api/sessions",
                 "/api/artifacts", "/api/workspace/files", "/api/scratch", "/api/settings"):
        assert client.get(path).status_code == 200, path
    for mode, sub in (("PROBE", "STANDARD"), ("PRODUCTIVE_FAILURE", "STANDARD"), ("TEACH", "STANDARD"),
                      ("PRACTICE", "STANDARD"), ("REFEREE_DUEL", "PROOF_REFEREE"), ("REFEREE_DUEL", "FEYNMAN_STUDENT")):
        st = client.post("/api/sessions", json={"mode": mode, "sub_mode": sub, "target_goal": "variance of a sum",
                                                "target_node_id": "prop_var_indep_sum"})
        assert st.status_code == 200, (mode, sub, st.text)
        assert st.json()["active_step"]["kind"] != "COMPLETE"
