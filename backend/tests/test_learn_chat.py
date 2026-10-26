"""Learn chat (docs/specs/learn-chat): never-studied ideas are taught as a sourced conversation until recall is likely."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import llm, sources
from backend.agents import explain, prompts
from backend.tests.conftest import point_config_at
from backend.tests.test_topic_map import FAKE_TOPIC

TURN = {"reply_markdown": "A demonstration is a list of state–action pairs [1]. Not [9].", "question": "Why pairs?",
        "concepts": [["state"], ["action"]]}
# a topic of four brand-new ideas, so one conversation covers them all
LEARN_TOPIC = {
    "goal": "il",
    "ideas": [{"key": "demo", "title": "Expert demonstrations", "statement_latex": r"Pairs $(s_i, a_i)$."},
              {"key": "bc", "title": "Behavioural cloning", "statement_latex": r"Fit $\pi_\theta(a\mid s)$ to the pairs."},
              {"key": "shift", "title": "Compounding errors", "statement_latex": r"Errors grow as $O(\epsilon T^2)$."},
              {"key": "il", "title": "Imitation learning", "statement_latex": r"Learn $\pi$ from demonstrations."}],
    "edges": [{"premises": ["demo"], "conclusion": "bc"}, {"premises": ["bc"], "conclusion": "shift"},
              {"premises": ["shift"], "conclusion": "il"}],
}
NEXT = {"reply_markdown": "Cloning fits a policy to the pairs.", "question": "What is the loss?", "concepts": [["loss"]]}


@pytest.fixture()
def client(tmp_path):
    point_config_at(tmp_path)
    from backend.main import app
    with TestClient(app) as c:
        yield c


def scripted(monkeypatch, verdicts=None, topic=None):
    """TOPIC_MAPPER → FAKE_TOPIC; tutor turns scripted; replies graded by the next verdict in `verdicts`."""
    seen: list[tuple[str, str]] = []
    queue = list(verdicts or [])

    async def fake(system, user, max_tokens=2500, timeout=None):
        seen.append((system, user))
        if system == prompts.TOPIC_MAPPER:
            return llm.LLMResult(topic or FAKE_TOPIC, "scripted")
        if system == prompts.LEARN_TUTOR_TURN:
            return llm.LLMResult(TURN, "scripted")
        if system == prompts.LEARN_TUTOR_REPLY:
            verdict, quality = queue.pop(0) if queue else ("partial", 0.5)
            return llm.LLMResult({"verdict": verdict, "quality": quality, "feedback_markdown": f"Graded {verdict}.",
                                  "continue": TURN, "next": NEXT}, "scripted")
        return llm.LLMResult(None, "deterministic")
    monkeypatch.setattr(llm, "complete_json", fake)
    monkeypatch.setattr(llm, "engine_chain", lambda: ["scripted"])
    return seen


def fake_fetchers(monkeypatch, calls: list):
    def wiki(q):
        calls.append(("wikipedia", q))
        return {"kind": "wikipedia", "title": f"Wiki: {q}", "url": f"https://en.wikipedia.org/wiki/{q.replace(' ', '_')}",
                "passage": f"{q}. A learner copies expert demonstrations, pairs of states and actions, by behavioural "
                           "cloning; compounding errors follow from distribution shift."}

    def arxiv(q, k=3):
        calls.append(("arxiv", q))
        return [{"kind": "arxiv", "title": "A survey of imitation learning", "url": "https://arxiv.org/abs/2000.00001",
                 "passage": "Abstract: imitation learning from expert demonstrations."}]
    monkeypatch.setattr(sources, "wikipedia_article", wiki)
    monkeypatch.setattr(sources, "arxiv_abstracts", arxiv)


def _submit(client, sid, step, answer=None):
    body = {"step_id": step["step_id"], "confidence": 0.6, "raw_prediction_locked": "My guess before the options: pairs."}
    if step["options"]:
        body["selected_answer"] = answer or step["options"][0]["id"]
    return client.post(f"/api/sessions/{sid}/submit", json=body).json()


def _to_learn(client, st):
    """Answer probes (which must be about ideas with history) until the learn chat opens."""
    sid, step = st["session"]["id"], st["active_step"]
    from backend import db
    while step["kind"] != "LEARN":
        assert step["kind"] in ("PROBE", "PREDICT", "READING", "CHECK"), step["kind"]
        with db.ro() as conn:
            assert not explain.is_new(db.get_node(conn, step["target_node_ids"][0]))
        step = _submit(client, sid, step)["state"]["active_step"]
    return sid, step


def _first_new_run(plan, conn):
    from backend import db
    run, started = [], False
    for p in plan:
        new = explain.is_new(db.get_node(conn, p["node_id"]))
        if new:
            run.append(p["node_id"])
            started = True
        elif started:
            break
    return run


def test_new_ideas_open_a_sourced_learn_chat(client, monkeypatch):
    seen = scripted(monkeypatch)
    calls: list = []
    fake_fetchers(monkeypatch, calls)
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "imitation learning"}).json()
    from backend import db
    with db.ro() as conn:
        expected = _first_new_run(st["session"]["dependency_plan"], conn)
    sid, step = _to_learn(client, st)
    assert [i["node_id"] for i in step["learn_ideas"]] == expected and len(expected) >= 1
    assert step["learn_ideas"][0]["status"] == "current" and "already know" in step["prompt_latex"]
    srcs = client.get(f"/api/sessions/{sid}/explain").json()["sources"]
    kinds = [s["kind"] for s in srcs]
    assert kinds == sorted(kinds, key=lambda k: sources.KIND_ORDER[k]) and "wikipedia" in kinds and "arxiv" in kinds
    assert [s["n"] for s in srcs] == list(range(1, len(srcs) + 1))
    assert ("wikipedia", "imitation learning") in calls
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "OPEN_REPLY", "message": "I know supervised learning."}).json()
    first = r["thread"][-1]
    assert first["role"] == "polya" and "[1]" in first["text"] and "[9]" not in first["text"] and first["meta"]["cited"] == [1]
    tutor_prompt = next(u for s, u in seen if s == prompts.LEARN_TUTOR_TURN)
    assert "I know supervised learning." in tutor_prompt and "[1] (wikipedia" in tutor_prompt


def test_readiness_moves_on_and_recall_starts_with_the_earliest_idea(client, monkeypatch):
    scripted(monkeypatch, verdicts=[("correct", 0.9), ("incorrect", 0.2)], topic=LEARN_TOPIC)
    fake_fetchers(monkeypatch, [])
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "imitation learning"}).json()
    sid, step = _to_learn(client, st)
    ideas = [i["node_id"] for i in step["learn_ideas"]]
    assert ideas == ["t_expert_demonstrations", "t_behavioural_cloning", "t_compounding_errors", "t_imitation_learning"]
    from backend import db
    with db.ro() as conn:
        window_before = db.recent_successes(conn, 10)
    client.post(f"/api/sessions/{sid}/learn", json={"action": "SKIP"})
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "REPLY", "message": "Because the state and action go together."}).json()
    li = {i["node_id"]: i for i in r["learn_ideas"]}
    assert li[ideas[0]]["status"] == "covered" and li[ideas[0]]["p_recall"] >= explain.READY_RECALL
    assert li[ideas[1]]["status"] == "current" and "Cloning fits" in r["thread"][-1]["text"]
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "REPLY", "message": "no idea"}).json()
    li = {i["node_id"]: i for i in r["learn_ideas"]}
    assert li[ideas[1]]["status"] == "current" and li[ideas[1]]["p_recall"] < explain.READY_RECALL
    for _ in range(explain.MAX_EXCHANGES - 1):
        r = client.post(f"/api/sessions/{sid}/learn", json={"action": "GO_ON"}).json()
    li = {i["node_id"]: i for i in r["learn_ideas"]}
    assert li[ideas[1]]["status"] == "moved_on" and li[ideas[2]]["status"] == "current" and not r["ready"]
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "QUIZ_ME"}).json()
    assert r["ready"] and "Start recall" in r["thread"][-1]["text"]
    assert [i["status"] for i in r["learn_ideas"]] == ["covered", "moved_on", "moved_on", "moved_on"]
    with db.ro() as conn:
        assert db.recent_successes(conn, 10) == window_before                     # chat evidence never steers pacing
        assert conn.execute("SELECT COUNT(*) FROM model_predictions WHERE phase='LEARN_CHAT'").fetchone()[0] >= 1
    traces = client.get(f"/api/sessions/{sid}").json()["traces"]
    chat = [t for t in traces if t["prompt_shown_latex"].startswith("Learn chat:")]
    assert chat and all(t["max_hint_rung"] == "R2" and t["phase"] == "READING" for t in chat)
    # start recall: earliest covered idea first, moved-on ideas after
    res = _submit(client, sid, client.get(f"/api/sessions/{sid}").json()["active_step"])
    nxt = res["state"]["active_step"]
    assert nxt["kind"] == "CHECK" and nxt["target_node_ids"] == [ideas[0]] and "lag" in nxt["rationale"]
    for want in ideas[1:]:
        res = _submit(client, sid, nxt)
        nxt = res["state"]["active_step"]
        assert nxt["kind"] == "CHECK" and nxt["target_node_ids"] == [want], (want, nxt["kind"], nxt["target_node_ids"])


def test_quiz_me_and_reload_restore_the_chat(client, monkeypatch):
    scripted(monkeypatch, topic=LEARN_TOPIC)
    fake_fetchers(monkeypatch, [])
    st = client.post("/api/sessions", json={"mode": "TEACH", "target_goal": "imitation learning"}).json()
    sid, step = _to_learn(client, st)
    client.post(f"/api/sessions/{sid}/learn", json={"action": "SKIP"})
    client.post(f"/api/sessions/{sid}/learn", json={"action": "ASK", "message": "What is a policy?"})
    again = client.get(f"/api/sessions/{sid}").json()["active_step"]               # reload
    assert again["kind"] == "LEARN" and [i["status"] for i in again["learn_ideas"]] == ["current", "todo", "todo", "todo"]
    thread = client.get(f"/api/sessions/{sid}/explain").json()["thread"]
    assert [m["role"] for m in thread] == ["polya", "learner", "polya"] and thread[1]["text"] == "What is a policy?"
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "QUIZ_ME"}).json()
    assert r["ready"] and all(i["status"] == "moved_on" for i in r["learn_ideas"])
    assert client.post(f"/api/sessions/{sid}/learn", json={"action": "REPLY", "message": "late"}).json()["ready"]
    nxt = _submit(client, sid, client.get(f"/api/sessions/{sid}").json()["active_step"])["state"]["active_step"]
    assert nxt["kind"] == "CHECK" and nxt["target_node_ids"] == [r["learn_ideas"][0]["node_id"]]


def test_sources_respect_the_preference_and_put_notes_first(client, monkeypatch):
    scripted(monkeypatch)
    calls: list = []
    fake_fetchers(monkeypatch, calls)
    client.put("/api/settings", json={"fetch_sources": False})
    assert client.get("/api/settings").json()["fetch_sources"] is False
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "imitation learning",
                                            "attached_files": ["notes/measure_rl_transformers.tex"]}).json()
    assert calls == []
    srcs = client.get(f"/api/sessions/{st['session']['id']}/explain").json()["sources"]
    assert srcs and {s["kind"] for s in srcs} == {"notes"}
    client.put("/api/settings", json={"fetch_sources": True})
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "behavioural cloning robots",
                                            "attached_files": ["notes/measure_rl_transformers.tex"]}).json()
    kinds = [s["kind"] for s in client.get(f"/api/sessions/{st['session']['id']}/explain").json()["sources"]]
    assert kinds[0] == "notes" and "wikipedia" in kinds and kinds.index("wikipedia") < kinds.index("arxiv")


def test_offline_turns_are_labelled_as_ai_knowledge(client, monkeypatch):
    scripted(monkeypatch)                     # POLYA_OFFLINE=1: the real fetchers return nothing
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "imitation learning"}).json()
    sid, _ = _to_learn(client, st)
    assert client.get(f"/api/sessions/{sid}/explain").json()["sources"] == []
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "SKIP"}).json()
    msg = r["thread"][-1]
    assert msg["meta"]["engine_note"] == "from the AI's own knowledge" and "[1]" not in msg["text"]


def test_deterministic_chat_without_an_engine(client):
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "imitation learning for robots"}).json()
    sid, step = _to_learn(client, st)
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "SKIP"}).json()
    assert r["engine"] == "deterministic" and r["thread"][-1]["meta"]["question"]
    good = ("Imitation learning for robots means the robot learns a policy from expert demonstrations, because it copies "
            "the expert's action in each state.")
    r = client.post(f"/api/sessions/{sid}/learn", json={"action": "REPLY", "message": good}).json()
    assert r["learn_ideas"][0]["status"] == "covered" and r["ready"] == (len(r["learn_ideas"]) == 1)


def test_ideas_with_history_keep_the_old_flow(client):
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "Double DQN"}).json()
    assert st["active_step"]["kind"] == "PROBE"                                       # seed ideas have reviews
    st = client.post("/api/sessions", json={"mode": "PRACTICE", "target_goal": "Practice: Double DQN",
                                            "target_node_id": "prop_double_dqn_decoupling"}).json()
    assert st["active_step"]["kind"] == "PRACTICE_CHUNK"
