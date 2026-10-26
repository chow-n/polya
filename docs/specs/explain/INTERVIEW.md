---
slug: explain
status: approved
bead: none (learn-harness is not a gc rig)
started: 2026-10-25
---
# Objective (user's words, verbatim)
"I want polya to facilitate the explanations and such too, I should be able to ask for explanations and it should offer
them when needed. Of course, think of a smart scientific way to do this"

# Recon
- Explanations today are only system-scheduled: READING steps (`orchestrator.step_reading`, after PREDICT), the
  answer explanation in PROBE/CHECK feedback (`submit`, meta.explanation), the PF canonical insight, REFEREE "Why".
- Learner-initiated help exists only in PRACTICE: R0–R4 hint ladder (`orchestrator.hint`, `prompts.HINT_PROMPT`,
  `/api/sessions/{id}/hint`), which caps the FSRS rating (max_hint_rung → G ≤ 2/3) so the model stays honest.
- No free-form question endpoint; no "stuck" detection. Frontend tracks `draft.stepShownAt` and prosody latency.
- Evidence available per step: correctness, confidence, trace quality q, miss_class, hypercorrection flag, BKT P(L),
  attempts per plan item, EWMA success (`cm.difficulty_controller`), prosody hesitation.
- Grounding available: node + premises/hyperedge reasoning chains, `_controller.notes` (topic-map), `paper_context`.
- UI: one card per step (`SessionFocus.tsx`, `stepParts.tsx` ResultBlock/Details). LLM latency ≈ 20–50 s per call.

# Decision tree
- D1 [CP] Asking before answering a graded question — ACCEPTED
- D2 [CP] When Pólya offers explanations on its own — ACCEPTED
- D3 [CP] Interaction shape — ACCEPTED
- D4 After an explanation: self-explanation prompt — ACCEPTED
- D5 Explanation style adapts to mastery (expertise reversal) — DEFAULT (not asked): yes

# Ledger
- D1 ACCEPTED: full explanation any time, no scoring penalty. Why: Nathan wants it usable as reference. Rejected:
  hold-answer + assisted cap (recommended; keeps the model honest), try-first lock. Mitigation (no penalty): the
  thread records `before_answer`, so model-eval can later measure inflation. 2026-10-25
- D2 ACCEPTED: evidence-based offers (wrong / confident-wrong refutation / right-but-weak / two misses → worked
  example / stuck ≥ 2× usual time with little typed); none at P(L) ≥ 0.85; none before a first attempt (a stuck
  offer is a setup nudge, not the answer). Rejected: wrong-only; auto-inserted steps. 2026-10-25
- D3 ACCEPTED: session side chat ("Ask Pólya") beside the card, aware of the current card. Rejected: per-card
  button + follow-ups (recommended), single button. 2026-10-25
- D4 ACCEPTED: skippable one-line say-it-back after an explanation, graded lightly, updates the learner model. 2026-10-25

# Assumptions
- ASSUMED explanations are grounded in the node, its premises' reasoning chains, the session notes and paper passage.
- ASSUMED the deterministic engine answers from node intuition/statement/proof sketch + premise chains (no LLM).

# Constraints / Non-goals
- Law 1 (no unprompted multi-step derivations) and Law 3 (epistemic lock) stay; model honesty (assisted ≠ clean).

# Reuse
- `orchestrator.hint` capping pattern, `prompts.node_context`, `topic_map.notes_context`, `orchestrator.paper_context`,
  `llm.complete_json`, ResultBlock/Details in `stepParts.tsx`.

# Open questions

# Pending question: none (approved 2026-10-26)
