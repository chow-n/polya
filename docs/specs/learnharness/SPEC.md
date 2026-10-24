---
slug: learnharness
status: approved-fasttrack
bead: none
approved_by: nathan (fast-track, 2026-10-23)
approved_at: 2026-10-23
---
# Maximal LearnHarness — fast-track spec
Objective: build, test and launch the system in ARCHITECTURE_SPEC.md (verbatim user spec, §0–§8). That file is authoritative; this one records decisions and assumptions only.
## Decisions (user-accepted 2026-10-23)
- D1 Fast-track, build straight through without halting.
- D2 Zero-key default: `claude -p --output-format json` (90s timeout) → deterministic SymPy/graph engine on failure, nesting lock or missing CLI.
- D3 Six modes = PROBE, PRODUCTIVE_FAILURE, TEACH, PRACTICE, REFEREE_DUEL/PROOF_REFEREE, REFEREE_DUEL/FEYNMAN_STUDENT (sub_mode). DB CHECK kept exactly as specified.
## Assumptions
- ASSUMED backend deps live in backend/.venv (uv); repo gets a local `git init`, no remote.
- ASSUMED FSRS success applies both the 0.06 multiplier floor and S' ≥ S + 0.15·m_G.
- ASSUMED pytest forces the deterministic engine (`LEARNHARNESS_LLM=deterministic`) and mocks arXiv.
- ASSUMED hypergraph uses a hand-written Canvas 2D renderer (no WebGL dependency).
## Science-grounded additions (user invited improvements)
- Murphy (1973) Brier decomposition: reliability − resolution + uncertainty, shown in the calibration badge.
- Desired-retention scheduling: next interval I = (81/19)·S·(r⁻² − 1) at r = 0.90 → `harness-cli due`.
- Interleaving (Rohrer & Taylor 2007): practice queue penalises consecutive picks from one domain cluster.
- Pretesting effect (Richland/Kornell 2009) cited in the Epistemic Lock copy; it is the rationale for Law 3.
## Acceptance
- `make test` (pytest backend/tests) green; `npm run build` exit 0; seed = 20 nodes / 16 hyperedges / 3 demos / 3 sessions;
  `./start.sh` brings up :8000/health and :5173 with 200; `./harness-cli status|due|graph|scratch` work.
