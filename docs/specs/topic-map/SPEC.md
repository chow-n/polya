---
slug: topic-map
status: approved
bead: none (learn-harness is not a gc rig)
approved_by: Nathan ("Yes, build all three", 2026-10-25)
approved_at: 2026-10-25
---
# Topic map: strict goal matching, AI decomposition, notes grounding

## Goals
1. A typed goal matches an existing idea only on distinctive words ("imitation learning" no longer opens Q-learning).
2. A new goal, when an AI engine is available, becomes a 4–8 idea prerequisite map (reusing existing ideas) before
   the first step, so Probe/Teach has a real plan to walk.
3. Lessons for that session are grounded in the learner's notes: attached files, else the 3 best-matching passages.

## Non-goals
- No "Did you mean…?" prompt and no map editor before teaching (D1, D2). No new primary-UI controls.
- No change to the 20-node seed, the content bank, paper sessions or practice-file matching semantics.
- No-engine fallback for new topics stays today's single goal node (D4, deferred).

## Architecture and integration decisions
- D1 ACCEPTED: stricter automatic matching, no prompt. Rejected: a "Did you mean" choice (extra click on every goal).
- D2 ACCEPTED: start teaching straight away; the map shows on Map and in the first card's Details. Rejected: preview/edit.
- D3 ACCEPTED: attached notes, else the 3 best-matching passages from the notes folder (named in Details).
  Rejected: attached only (notes would rarely be used).
- D4 DEFERRED (default): no engine → single goal node, provisional premises now chosen by the same strict scorer.

## Existing components to reuse (do not rebuild)
- `backend/agents/orchestrator.py`: `match_goal_node`, `_create_goal_node`, `build_plan`, `_llm_step`, `create_session`.
- `backend/papers/service.py:build_map` pattern (existing_node_id reuse, slugged ids, md5 edge ids, `recompute_depths`).
- `backend/tools.py:corpus_search`, `read_workspace_file`; `backend/agents/subagents.py:run_agent` (live sub-agent status).
- `backend/llm.py:complete_json` (engine chain, fallback, `deterministic` label when nothing answers).

## Functional requirements
- FR1 Distinctive-word matching (`orchestrator.goal_terms` / `match_goal_node`): goal words of ≥3 letters minus a
  generic list (learning, theory, theorem, model, method, deep, network, analysis, …). Each term is weighted by its
  inverse document frequency over non-buggy nodes. A node matches when shared terms cover ≥ 60% of the goal's term
  weight. Ties → the higher score; no distinctive terms → no match.
- FR2 Topic decomposition (`backend/agents/topic_map.py`): when no node matches and the mode is a teaching mode, one
  `complete_json(TOPIC_MAPPER, …)` call (timeout 150 s) returns 4–8 ideas {key, title, node_type, statement_latex,
  intuition_summary, existing_node_id} + DEDUCTION edges + `goal` key. Validated by Pydantic; unknown existing ids are
  dropped; < 3 ideas or no goal → fallback (FR4). Ideas become nodes `t_<slug>`; edges `he_topic_<md5>`; depths
  recomputed; the session target is the goal idea; the plan is `build_plan(goal)`. Runs as an ONTOLOGIST_EXTRACTOR
  sub-agent so the dock shows "Mapping topic…".
- FR3 Notes grounding: attached files' blocks matching the goal (else their first 2,500 chars), otherwise
  `corpus_search` on the distinctive terms (top 3, score ≥ 2). The passages go into the TOPIC_MAPPER prompt and into
  every `_llm_step` of that session ("From the learner's notes"), capped at 3,000 chars. Their `path:line` labels are
  listed in the first step's rationale (Details) and in a `TOPIC_MAPPED` history entry.
- FR4 Fallback: engine label `deterministic` / invalid map → `_create_goal_node` as today, but provisional premises use
  the FR1 scorer (a premise needs ≥ 1 shared distinctive term).

## Edge cases
- Goal equals an existing node title or id → match (FR1 coverage 100%).
- Re-entering the same goal later → FR1 matches the earlier `t_` goal node; no second map.
- PRACTICE / REFEREE modes never decompose (they need an existing node, as today).

## Acceptance and verification
- Tests (`backend/tests/test_topic_map.py`, deterministic engine, fake LLM via monkeypatch):
  "imitation learning" → no match; "double DQN", "RoPE relative position", "Bellman contraction" → their seed nodes;
  a fake TOPIC_MAPPER answer creates nodes/edges, reuses an existing id, and the plan ends at the goal;
  notes passages reach the prompt and the rationale; invalid answer → single goal node without Q-learning premises.
- `make test` green; `cd frontend && npm run build` (no frontend change expected).
- Live: "imitation learning" with claude_cli builds a map that reuses MDP/Bellman ideas.

## Risks / assumptions
- ASSUMED: one decomposition call takes 20–90 s via the claude CLI; session creation waits for it (status shown).
- ASSUMED: AI-made ideas get AI-written steps; offline later they fall back to generic content.
