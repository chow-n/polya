"""Topic maps for new goals (docs/specs/topic-map): strict goal matching, AI decomposition, notes grounding, fallback."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import llm
from backend.agents import topic_map
from backend.tests.conftest import point_config_at

FAKE_TOPIC = {
    "goal": "il",
    "ideas": [
        {"key": "mdp", "title": "Bellman optimality", "existing_node_id": "prop_bellman_sup_norm_contraction"},
        {"key": "demo", "title": "Expert demonstrations", "node_type": "AXIOM",
         "statement_latex": r"A dataset $\{(s_i, a_i)\}$ of states and the expert's actions."},
        {"key": "bc", "title": "Behavioural cloning", "node_type": "PROPOSITION",
         "statement_latex": r"Fit $\pi_\theta(a\mid s)$ to the expert pairs by supervised learning."},
        {"key": "shift", "title": "Compounding errors under distribution shift",
         "statement_latex": r"Errors of $\epsilon$ per step compound to $O(\epsilon T^2)$."},
        {"key": "il", "title": "Imitation learning", "statement_latex": r"Learn $\pi$ from demonstrations without a reward."},
        {"key": "il", "title": "duplicate key is dropped"},
        {"key": "ghost", "title": "Unknown reuse", "existing_node_id": "no_such_node"},
    ],
    "edges": [
        {"premises": ["demo"], "conclusion": "bc", "reasoning": "Supervised learning on the pairs."},
        {"premises": ["bc", "mdp"], "conclusion": "shift"},
        {"premises": ["shift", "bc"], "conclusion": "il"},
        {"premises": ["il"], "conclusion": "demo"},                   # would close a cycle → dropped
        {"premises": ["demo"], "conclusion": "mdp"},                  # concludes in an existing idea → dropped
    ],
}


@pytest.fixture()
def client(tmp_path):
    point_config_at(tmp_path)
    from backend.main import app
    with TestClient(app) as c:
        yield c


def scripted(monkeypatch, topic=FAKE_TOPIC):
    seen: list[tuple[str, str]] = []

    async def fake(system, user, max_tokens=2500, timeout=None):
        from backend.agents import prompts
        seen.append((system, user))
        if system == prompts.TOPIC_MAPPER:
            return llm.LLMResult(topic, "scripted")
        return llm.LLMResult(None, "deterministic")
    monkeypatch.setattr(llm, "complete_json", fake)
    monkeypatch.setattr(llm, "engine_chain", lambda: ["scripted"])
    return seen


def test_goal_matching_uses_distinctive_words(fresh_db):
    from backend import seed
    with fresh_db.tx() as conn:
        seed.seed_graph(conn)
        nodes = fresh_db.all_nodes(conn)
    assert topic_map.match_goal(nodes, "imitation learning") is None              # "learning" alone never matches
    assert topic_map.match_goal(nodes, "learning") is None
    assert topic_map.match_goal(nodes, "Double DQN")["id"] == "prop_double_dqn_decoupling"
    assert topic_map.match_goal(nodes, "RoPE relative position")["id"] == "prop_rope_relative_invariance"
    assert topic_map.match_goal(nodes, "Bellman contraction")["id"] == "prop_bellman_sup_norm_contraction"
    assert topic_map.match_goal(nodes, "Q-learning maximization bias")["id"] == "prop_qlearning_maximization_bias"
    assert "prop_qlearning_maximization_bias" not in topic_map.premise_candidates(nodes, "imitation learning", "x")


def test_new_goal_is_mapped_before_teaching(client, monkeypatch):
    seen = scripted(monkeypatch)
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "imitation learning"}).json()
    plan = [p["node_id"] for p in st["session"]["dependency_plan"]]
    assert plan[-1] == "t_imitation_learning"
    assert {"t_expert_demonstrations", "t_behavioural_cloning", "prop_bellman_sup_norm_contraction"} <= set(plan)
    assert not any("qlearning" in p for p in plan)
    assert "mapped into 6 ideas (5 new) by scripted" in st["active_step"]["rationale"]
    mapper_prompt = next(u for s, u in seen if "TOPIC_MAPPER" in s)
    assert "`prop_bellman_sup_norm_contraction`" in mapper_prompt
    from backend import db
    with db.ro() as conn:
        edges = [e for e in db.all_edges(conn) if e["id"].startswith("he_topic_")]
        assert not any(e["conclusion_node_id"] in ("prop_bellman_sup_norm_contraction", "t_expert_demonstrations") for e in edges)
        assert db.node_exists(conn, "t_unknown_reuse")                         # an unknown reuse id becomes a new idea
        hist = db.load_session(conn, st["session"]["id"])["history_steps"]
        assert hist[0]["kind"] == "TOPIC_MAPPED" and hist[0]["engine"] == "scripted"
    # the same goal later matches the mapped idea instead of mapping again
    st2 = client.post("/api/sessions", json={"mode": "TEACH", "target_goal": "Imitation learning"}).json()
    assert st2["session"]["dependency_plan"][-1]["node_id"] == "t_imitation_learning"
    assert sum("TOPIC_MAPPER" in s for s, _ in seen) == 1


def test_attached_notes_ground_the_map_and_every_step(client, monkeypatch):
    seen = scripted(monkeypatch)
    st = client.post("/api/sessions", json={"mode": "TEACH", "target_goal": "imitation learning",
                                            "attached_files": ["notes/measure_rl_transformers.tex"]}).json()
    assert "Grounded in your notes: `notes/measure_rl_transformers.tex:" in st["active_step"]["rationale"]
    assert "From the learner's notes" in next(u for s, u in seen if "TOPIC_MAPPER" in s)
    steps = [u for s, u in seen if "TOPIC_MAPPER" not in s]
    assert steps and all("From the learner's notes" in u for u in steps)


def test_notes_folder_passages_need_a_real_match(fresh_db):
    hits = topic_map.notes_passages("escaping mass and the integrable envelope", [])
    assert hits and all(h["label"].startswith("notes/measure_rl_transformers.tex:") for h in hits) and len(hits) <= 3
    assert topic_map.notes_passages("imitation learning for robots", []) == []


def test_invalid_map_falls_back_to_a_single_goal(client, monkeypatch):
    scripted(monkeypatch, topic={"goal": "x", "ideas": [{"key": "x", "title": "Only one"}], "edges": []})
    st = client.post("/api/sessions", json={"mode": "TEACH", "target_goal": "imitation learning"}).json()
    plan = [p["node_id"] for p in st["session"]["dependency_plan"]]
    assert plan[-1].startswith("goal_imitation") and not any("qlearning" in p for p in plan)


def test_probe_details_do_not_reveal_the_answer(client, monkeypatch):
    async def fake(system, user, max_tokens=2500, timeout=None):
        from backend.agents import prompts
        if system == prompts.MODE_PROMPTS["PROBE"]:
            return llm.LLMResult({"title": "Probe", "prompt_latex": "Which?", "body_markdown": "",
                                  "options": [{"id": k, "label_latex": k} for k in "ABCD"], "correct_option_id": "C",
                                  "rationale": "Correct (C): because of the secret."}, "scripted")
        return llm.LLMResult(None, "deterministic")
    monkeypatch.setattr(llm, "complete_json", fake)
    st = client.post("/api/sessions", json={"mode": "PROBE", "target_goal": "Double DQN"}).json()
    assert st["active_step"]["kind"] == "PROBE" and st["active_step"]["generated_by"] == "llm"
    assert "secret" not in st["active_step"]["rationale"] and "[engine: scripted]" in st["active_step"]["rationale"]
