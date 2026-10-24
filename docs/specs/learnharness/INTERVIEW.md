---
slug: learnharness
status: approved
bead: none (learn-harness is not a rig in ~/hodge-city; bead skipped)
started: 2026-10-23
---
# Objective (user's words, verbatim)
"autonomously architect, implement, test, and launch Maximal LearnHarness—a complete, local-first AI
cognitive learning harness that models the human learner's brain as a POMDP" — full pasted spec
(sections 0–8) is persisted verbatim to ARCHITECTURE_SPEC.md once building starts.

# Recon
- Repo directory was empty and not a git repo. Greenfield.
- Tooling: python3 3.14 (no sympy/numpy/fastapi installed globally), uv present, node 26, npm,
  claude CLI 2.1.309, rg present.
- Spec inconsistencies found:
  - "6 modes" but sessions.mode CHECK lists 5 (PROBE, PRODUCTIVE_FAILURE, TEACH, PRACTICE, REFEREE_DUEL).
  - FSRS success: prose says floor "+0.15·m_G days", formula uses max(0.06, …) multiplier floor.
  - phase CHECK lacks 'TEACH' (uses READING/PREDICT/CHECK) — fine as is.

# Decision tree
- D1 [CP] Interview depth: fast-track with recorded assumptions vs full interview — ACCEPTED
- D2 [CP] Zero-key LLM default: claude CLI first vs deterministic engine first — ACCEPTED
- D3 Meaning of "6 modes" — ACCEPTED

# Ledger
- D1 ACCEPTED: fast-track. Why: spec exhaustive, user said no halting. Rejected: full interview. 2026-10-23
- D2 ACCEPTED: claude CLI first, deterministic fallback. Rejected: deterministic-first. 2026-10-23
- D3 ACCEPTED: split REFEREE_DUEL via sub_mode. Rejected: 6th DB value. 2026-10-23
- User added: "further improve it ... be creative and grounded in science" -> see SPEC.md additions.

# Assumptions
- Python deps in backend/.venv via uv; git init the repo locally (no remote, no push).
- FSRS success: apply both — multiplier floor 0.06 AND S' >= S + 0.15·m_G.
- Tests force the deterministic LLM engine and mock arXiv (no network in pytest).
- Graph canvas: hand-written HTML5 Canvas 2D (no WebGL library).

# Constraints / Non-goals
- Local-first; no deploy. Servers on 8000 / 5173.

# Reuse
- none (greenfield)

# Open questions

# Pending question: none
