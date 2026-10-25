---
slug: topic-map
status: approved
bead: none (learn-harness is not a gc rig)
started: 2026-10-24
---
# Objective (user's words, verbatim)
"yes" — to: "Match goals on meaningful words only, and confirm the match with you. When an AI engine is available, map a
new goal into 4–8 ideas and how they connect before teaching starts. This could also pull from your notes".

# Recon
- match_goal_node (backend/agents/orchestrator.py:113): word overlap (≥4 letters, tiny stopword list), score ≥ 2.
  Verified: "imitation learning" → prop_qlearning_maximization_bias (shared word "learning"), plan = Q-learning ancestors.
- No match → _create_goal_node (orchestrator.py:538): one node + ≤2 lexical "provisional premises"; no decomposition.
- build_plan (orchestrator.py:126) = DEDUCTION ancestors of target (MAX_PLAN cap).
- Per-step AI content: _llm_step (orchestrator.py:173) sends node context + goal only; notes never reach prompts.
- corpus_rag (subagents.py:482) already finds matching \begin{theorem|definition|problem} blocks + grep hits; only logged.
- ontologist (subagents.py:580) extracts nodes/edges AFTER a session (LLMOntology model), imports .tex blocks.
- Offline content: content_bank (20 nodes) else generic_content (orchestrator.py:44) — weak for new topics.

# Decision tree
- D1 [CP] Goal matching when unsure: silent stricter matching vs a "Did you mean…?" choice — ACCEPTED
- D2 [CP] Show/edit the proposed topic map before teaching vs start straight away — ACCEPTED
- D3 Notes grounding: attached + automatic best passages vs attached only — ACCEPTED
- D4 No AI engine + new topic: today's single-node fallback with a clear message — DEFERRED (default)

# Ledger
- D1 ACCEPTED: stricter automatic matching, no prompt. 2026-10-25
- D2 ACCEPTED: start teaching straight away. 2026-10-25
- D3 ACCEPTED: attached notes, else 3 best passages. 2026-10-25
- Spec approved by Nathan ("Yes, build all three") 2026-10-25.

# Assumptions
- Decomposition = one AI call returning 4–8 ideas (type, statement, intuition) + DEDUCTION edges, reusing existing node ids
  where they fit (e.g. MDPs/Bellman for imitation learning); validated by a Pydantic model, inserted as normal nodes.
- AI-made ideas are taught with AI-written steps; offline later they fall back to generic content.

# Constraints / Non-goals
- No new primary-UI controls beyond what D1/D2 decide. Original 20-node seed and content bank unchanged.

# Reuse
- orchestrator.match_goal_node/_create_goal_node/build_plan/_llm_step; subagents.corpus_rag/ontologist; tools.corpus_search;
  models.LLMOntology; db.insert_edge/recompute_depths.

# Open questions

# Pending question: D1, D2, D3 (asked together with chatgpt-engine E1)
D1 — When your goal might match an existing idea: Recommend stricter automatic matching (only distinctive words count;
"learning" alone never matches) and no extra prompt; the plan shows in the first card's Details. Alt: a "Did you mean X,
or start a new topic?" choice on Home.
D2 — Recommend start teaching straight away; the new topic's map appears on the Map and in Details. Alt: show the proposed
4–8 ideas first so you can remove/add before teaching.
D3 — Recommend ground lessons in notes you attach, and when none are attached, in the 3 best-matching passages from your
notes folder (named in Details). Alt: attached notes only.
