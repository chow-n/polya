"""Ask Pólya (docs/specs/explain): offer policy, styles, grounding, the deterministic explainer, say-it-back, threads."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import llm
from backend.agents import explain
from backend.tests.conftest import point_config_at


@pytest.fixture()
def client(tmp_path):
    point_config_at(tmp_path)
    from backend.main import app
    with TestClient(app) as c:
        yield c


def _probe_session(client, goal="Double DQN", **kw):
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": goal, **kw}).json()
    assert st["active_step"]["kind"] == "PROBE"
    return st


def _submit(client, st, answer, confidence=0.5, elapsed_ms=0):
    step = st["active_step"]
    return client.post(f"/api/sessions/{st['session']['id']}/submit", json={
        "step_id": step["step_id"], "raw_prediction_locked": "I think it is about decoupling selection from evaluation.",
        "selected_answer": answer, "confidence": confidence, "elapsed_ms": elapsed_ms}).json()


def _wrong_answer(client, st):
    """An option that is not the key (read from the server's hidden meta via a dry run is impossible, so try options)."""
    from backend import db
    with db.ro() as conn:
        meta = db.load_session(conn, st["session"]["id"])["active_step"]["_meta"]
    return next(o["id"] for o in st["active_step"]["options"] if o["id"] != meta["correct"]), meta["correct"]


# ------------------------------------------------------------------ pure policy (FR2, FR3)
def test_offer_policy_truth_table():
    f = explain.offer_for
    assert f("CHECK", "HIGH_CONFIDENCE_ERROR", 0, 0.3, 0.2, 0, 0, False)["trigger"] == "CONFIDENT_WRONG"
    assert f("CHECK", "FAILED", 0, 0.3, 0.2, 2, 0, False)["trigger"] == "WHEEL_SPINNING"
    assert f("PROBE", "FAILED", 0, 0.3, 0.2, 0, 2, False)["trigger"] == "WHEEL_SPINNING"
    assert f("CHECK", "FAILED", 0, 0.3, 0.2, 1, 1, False)["trigger"] == "WRONG"
    assert f("CHECK", "SOLVED_CLEAN", 1, 0.3, 0.5, 0, 0, False)["trigger"] == "WEAK_REASONING"
    assert f("CHECK", "SOLVED_CLEAN", 1, 0.8, 0.5, 0, 0, False) is None
    assert f("CHECK", "FAILED", 0, 0.3, 0.9, 0, 0, False) is None                 # mastered: no unprompted offers
    assert f("CHECK", "FAILED", 0, 0.3, 0.2, 0, 0, True) is None                  # already explained on this card
    assert f("READING", "FAILED", 0, 0.3, 0.2, 0, 0, False) is None
    assert f("PREDICT", "FAILED", 0, 0.3, 0.2, 0, 0, False) is None


def test_style_and_representation_and_stuck_threshold():
    assert explain.style_for(0.2, "EXPLAIN") == "WORKED_EXAMPLE"
    assert explain.style_for(0.6, "EXPLAIN", has_attempt=True) == "CONTRAST"
    assert explain.style_for(0.6, "EXPLAIN") == "EXPLAIN"
    assert explain.style_for(0.9, "EXPLAIN") == "TERSE"
    assert explain.style_for(0.9, "SIMPLER") == "WORKED_EXAMPLE"
    assert explain.style_for(0.6, "OFFER", "CONFIDENT_WRONG") == "REFUTATION"
    assert explain.style_for(0.6, "OFFER", "STUCK") == "NUDGE"
    assert explain.next_representation([]) == "concrete"
    assert explain.next_representation(["concrete", "geometric"]) == "symbolic"
    assert explain.next_representation(["computational"]) == "concrete"
    assert explain.stuck_after_ms([30_000] * 4) == 120_000                         # cold: fewer than 5 samples
    assert explain.stuck_after_ms([30_000] * 6) == 90_000                          # floor
    assert explain.stuck_after_ms([80_000] * 6) == 160_000                         # 2 × median


# ------------------------------------------------------------------ API
def test_ask_before_answering_does_not_change_scoring(tmp_path):
    results = []
    for ask in (False, True):
        point_config_at(tmp_path / ("ask" if ask else "plain"))
        from backend.main import app
        with TestClient(app) as c:
            st = _probe_session(c)
            sid = st["session"]["id"]
            if ask:
                r = c.post(f"/api/sessions/{sid}/explain", json={"action": "EXPLAIN"}).json()
                assert r["reply_markdown"].strip() and r["engine"] == "deterministic"
                thread = c.get(f"/api/sessions/{sid}/explain").json()["thread"]
                assert [m["role"] for m in thread] == ["learner", "polya"] and all(m["before_answer"] for m in thread)
            wrong, _ = _wrong_answer(c, st)
            res = _submit(c, st, wrong)
            results.append((res["trace"]["outcome"], round(res["trace"]["bkt_mastery_after"], 6),
                            round(res["trace"]["fsrs_stability_after"], 4)))   # elapsed seconds differ between runs
    assert results[0] == results[1]


def test_confident_error_offers_a_refutation(client, monkeypatch):
    st = _probe_session(client)
    sid = st["session"]["id"]
    wrong, _ = _wrong_answer(client, st)
    res = _submit(client, st, wrong, confidence=0.9)
    assert res["trace"]["outcome"] == "HIGH_CONFIDENCE_ERROR"
    offer = res["offer"]
    assert offer and offer["trigger"] == "CONFIDENT_WRONG" and offer["step_index"] == st["active_step"]["step_index"]
    assert client.get(f"/api/sessions/{sid}/explain").json()["offer"]["trigger"] == "CONFIDENT_WRONG"
    seen = []

    async def fake(system, user, max_tokens=2500, timeout=None):
        seen.append((system, user))
        return llm.LLMResult({"reply_markdown": "You believed X; it breaks at step 2.", "say_back_prompt": "Why?",
                              "say_back_concepts": [["decouple"]]}, "scripted")
    monkeypatch.setattr(llm, "complete_json", fake)
    body = {"action": "OFFER", "trigger": "CONFIDENT_WRONG", "step_index": offer["step_index"]}
    r = client.post(f"/api/sessions/{sid}/explain", json=body).json()
    assert r["style"] == "REFUTATION" and r["engine"] == "scripted"
    user = seen[-1][1]
    from backend.agents import prompts
    assert prompts.EXPLAIN_STYLES["REFUTATION"] in user and "decoupling selection" in user and "Result: incorrect" in user
    again = client.post(f"/api/sessions/{sid}/explain", json=body).json()            # idempotent per (step, trigger)
    assert len(again["thread"]) == len(r["thread"]) and len(seen) == 1
    assert client.get(f"/api/sessions/{sid}/explain").json()["offer"] is None        # accepted offers disappear


def test_explainer_prompt_is_grounded_in_premises_and_notes(client, monkeypatch):
    seen = []

    async def fake(system, user, max_tokens=2500, timeout=None):
        from backend.agents import prompts
        if system == prompts.EXPLAINER:
            seen.append(user)
            return llm.LLMResult({"reply_markdown": "Grounded [1] and [7].", "say_back_prompt": "Say it."}, "scripted")
        return llm.LLMResult(None, "deterministic")
    st = client.post("/api/sessions", json={"mode": "TEACH", "target_goal": "Double DQN",
                                            "attached_files": ["notes/measure_rl_transformers.tex"]}).json()
    monkeypatch.setattr(llm, "complete_json", fake)
    goal_title = st["session"]["dependency_plan"][-1]["title"]                    # an idea with premises, named in the question
    r = client.post(f"/api/sessions/{st['session']['id']}/explain",
                    json={"action": "ASK", "message": f"why does {goal_title} work?"}).json()
    assert r["node_id"] == st["session"]["dependency_plan"][-1]["node_id"]
    assert "Premises of this idea" in seen[-1] and "From the learner's notes" in seen[-1]
    assert "[7]" not in r["reply_markdown"] and "[1]" not in r["reply_markdown"]    # no numbered sources here → stripped


def test_deterministic_explainer_answers_every_action(client):
    st = _probe_session(client)
    sid = st["session"]["id"]
    for body in ({"action": "EXPLAIN"}, {"action": "DIFFERENT"}, {"action": "DIFFERENT"}, {"action": "SIMPLER"},
                 {"action": "ASK", "message": "what is the maximization bias?"},
                 {"action": "OFFER", "trigger": "STUCK"}):
        r = client.post(f"/api/sessions/{sid}/explain", json=body).json()
        assert r["reply_markdown"].strip() and r["engine"] == "deterministic", body
    thread = client.get(f"/api/sessions/{sid}/explain").json()["thread"]
    reps = [m["meta"]["representation"] for m in thread if m["role"] == "polya" and m["kind"] == "DIFFERENT"]
    assert reps == ["concrete", "geometric"]
    nudge = [m for m in thread if m["trigger"] == "STUCK" and m["role"] == "polya"][0]
    assert nudge["style"] == "NUDGE" and not nudge["meta"]["say_back_prompt"]
    assert client.post(f"/api/sessions/{sid}/explain", json={"action": "ASK", "message": " "}).status_code == 422


def test_say_back_updates_the_model_without_steering_pacing(client):
    st = _probe_session(client)
    sid = st["session"]["id"]
    client.post(f"/api/sessions/{sid}/explain", json={"action": "EXPLAIN"})
    before = client.get(f"/api/sessions/{sid}").json()
    from backend import db
    with db.ro() as conn:
        window_before = db.recent_successes(conn, 10)
    assert client.post(f"/api/sessions/{sid}/say-back", json={"text": "short"}).status_code == 422
    r = client.post(f"/api/sessions/{sid}/say-back",
                    json={"text": "Double DQN selects the action with the online network and evaluates it with the target "
                                  "network, so the max no longer overestimates."}).json()
    assert r["verdict_markdown"] and r["node_update"]["bkt_after"] != r["node_update"]["bkt_before"]
    after = client.get(f"/api/sessions/{sid}").json()
    new = [t for t in after["traces"] if t["id"] not in {x["id"] for x in before["traces"]}]
    assert len(new) == 1 and new[0]["max_hint_rung"] == "R2" and new[0]["phase"] == "READING"
    assert after["session"]["step_velocity_delta"] == before["session"]["step_velocity_delta"]
    assert after["session"]["dependency_plan"] == before["session"]["dependency_plan"]
    assert after["active_step"]["step_id"] == before["active_step"]["step_id"]
    with db.ro() as conn:
        assert db.recent_successes(conn, 10) == window_before                         # never feeds the controller
        assert conn.execute("SELECT COUNT(*) FROM model_predictions WHERE phase='SAY_BACK'").fetchone()[0] == 1
    thread = client.get(f"/api/sessions/{sid}/explain").json()["thread"]            # survives a reload
    assert thread[-1]["role"] == "say_back" and thread[-1]["meta"]["verdict"] == r["verdict_markdown"]


def test_elapsed_time_is_kept_for_the_stuck_threshold(client):
    st = _probe_session(client)
    wrong, _ = _wrong_answer(client, st)
    res = _submit(client, st, wrong, elapsed_ms=42_000)
    hist = res["state"]["session"]["history_steps"]
    assert hist[-1]["elapsed_ms"] == 42_000 and hist[-1]["answer"]
    assert res["state"]["stuck_after_ms"] == explain.STUCK_COLD_MS
