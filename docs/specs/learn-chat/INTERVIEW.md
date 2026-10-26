---
slug: learn-chat
status: approved
bead: none (learn-harness is not a gc rig)
started: 2026-10-26
---
# Objective (user's words, verbatim)
"when I first learn a topic, it should learn it with explanations (like a normal chat) drawing from sources until it
feels I am ready to recall"

# Recon
- Learn home always starts mode PROBE (`LearnHome.tsx:172`): up to 4 MC probes by EIG, then per idea
  PREDICT → READING → CHECK (`orchestrator.decide_next`). A brand-new topic (topic map, P(L)=0.15 everywhere) is
  therefore quizzed before anything is explained.
- READING = one ≤180-word card (`step_reading`), grounded in paper passages (`paper_link`) and `_controller.notes`.
- Approved `docs/specs/explain` adds an `explanations` thread table, `explain.py` (style by P(L), grounding,
  deterministic explainer) and the Ask Pólya side chat; its non-goal "no new step kinds" is superseded here.
- Sources available: workspace notes (`tools.corpus_search`), papers (`backend/papers`, arXiv fetch/OpenAlex),
  `subagents.literature` → `tools.search_arxiv` (offline fallback). No Wikipedia/web fetch yet. Tests never use network.
- Readiness signals: BKT P(L) per idea, recall prediction P(correct) = P(L)(1−s)+(1−P(L))g (`model_predictions`),
  difficulty-controller target (prefs `target_success`, default 0.85).

# Decision tree
- D1 [CP] Which ideas/sessions start in learn-chat — ACCEPTED
- D2 [CP] Sources the chat draws from — ACCEPTED
- D3 [CP] Readiness-to-recall rule — ACCEPTED
- D4 What recall looks like after the chat — ACCEPTED
- D5 Chat opens with "what do you already know about X?" (prior-knowledge activation, a cheap pretest) — DEFAULT yes

# Ledger
- D1 ACCEPTED: automatic for never-studied ideas (fsrs_reps 0 and no graded answers); ideas with history keep
  probe → predict → read → check. Rejected: every session; separate Learn mode. 2026-10-26
- D2 ACCEPTED: notes/papers first, then fetched open sources (Wikipedia sections, arXiv abstracts), cited [n] with a
  Sources list; offline → notes + AI knowledge, marked. Rejected: no fetching; AI only. 2026-10-26
- D3 ACCEPTED: model-based readiness — predicted recall ≥ 0.70 per idea from chat replies; "Quiz me" any time; ≤ 4
  exchanges per idea. Rejected: AI judgement; learner-only. 2026-10-26
- D4 ACCEPTED: delayed, interleaved recall, earliest-learned idea first, then the normal check flow. Rejected: check
  after each idea. 2026-10-26

# Assumptions
- ASSUMED the learn chat reuses the explain thread table/explainer and becomes the main card (step kind LEARN).

# Constraints / Non-goals
- Retrieval practice, FSRS and the 85% controller stay; this only changes first exposure.

# Reuse
- explain spec components; `topic_map.notes_passages`; `papers` fetch; `subagents.literature`; `subagents.diagnose`.

# Pending question: none (approved 2026-10-26)
