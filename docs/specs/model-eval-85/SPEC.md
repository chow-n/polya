---
slug: model-eval-85
status: approved
bead: none
approved_by: Nathan
approved_at: 2026-10-24T02:56:17-05:00
---
# Model scoreboard + 85% difficulty controller

## Goals
- G1 Measure how well Pólya's learner model predicts your next answer, against simple baselines, so every later
  tuning step (fitting FSRS/BKT, scheduling changes) can be judged by evidence.
- G2 Keep your recent success rate near a target (default 85%) by adapting the teaching step size and the
  practice difficulty.

## Non-goals
- No parameter fitting (later work, once you have about 300 answers). No change to the main screens beyond copy under Details.

## User-facing behaviour
- Learning feels steadier: when you are succeeding much more than the target the steps get bigger (Learn) and
  practice gets harder (Review: plain → disguised notation → mixed → trick question); when you are below it, steps and
  problems get easier. A hard failure still inserts a prerequisite review, as today.
- Settings gains **Difficulty target: 80% · 85% · 90%** (default 85%).
- Settings → Advanced gains **"How well Pólya predicts you"**: for each predictor, the number of answers, log-loss,
  Brier score, AUC and a calibration strip, compared with the baselines. Below 50 answers it says "Not enough answers
  yet" and shows the numbers greyed out.
- `./polya eval` prints the same scoreboard in the terminal.
- Each card's Details shows the controller's reading, e.g. "Recent success 78% (target 85%) → smaller steps".

## Architecture and integration decisions
- D1 (DELEGATED, technical) predictions go to a new side table `model_predictions`, one row per graded answer, written
  *before* the model updates. This keeps the original `telemetry_traces` DDL exact. Rejected: altering telemetry_traces.
- D2 The controller adjusts both the teaching step size Δ and the practice cue level. Rejected: step size only.
- D3 Target 85% by default, adjustable to 80/85/90, persisted in `~/Polya/prefs.json` (non-secret preferences only;
  API keys stay in memory). Rejected: fixed.
- D4 Scoreboard via `./polya eval` plus the Advanced panel. Rejected: CLI only.
- Supersedes ARCHITECTURE_SPEC §4.2's "two clean answers → Δ+0.5" rule. The hard-failure rule (Δ→0.5 + remedial splice)
  is kept.

## Existing components to reuse
- `backend/cognitive_math.py`: `retrievability`, `elapsed_days`, `murphy_decomposition`, `update_step_delta` (replaced).
- `backend/agents/orchestrator.py:apply_assessment` (the single place every graded answer passes through), `_controller.cue_level`.
- `frontend/src/components/SettingsSheet.tsx`, `kit.tsx` Details; `./polya`.

## Interfaces and data contracts
- Table `model_predictions(id, trace_id, session_id, node_id, phase, created_at, elapsed_days, r_at_review,
  p_mastery_before, p_bkt, p_memory, p_combined, p_global_baseline, p_node_baseline, y, success)`.
  - `p_bkt` = P(L)(1−s) + (1−P(L))·g, using the node's slip s and guess g.
  - `p_memory` = R(t, S) at review time.
  - `p_combined` = (P(L)·R)(1−s) + (1 − P(L)·R)·g.
  - `p_global_baseline` = (k+1)/(n+2) over all your earlier graded answers.
  - `p_node_baseline` = the same, for this idea only.
  - `y` = is_correct; `success` = y AND trace quality ≥ 0.45.
- `GET /api/model-eval` → `{n, enough_data, predictors: [{name, n, log_loss, brier, auc, calibration_bins}],
  controller: {target, recent_success, window_n, delta, practice_level, last_action}}`.
- `PUT /api/settings` accepts `target_success ∈ {0.80, 0.85, 0.90}`; `GET /api/settings` returns it.

## Functional requirements
- FR1 Every graded answer (PROBE, CHECK, PRACTICE_CHUNK, REFEREE) writes one `model_predictions` row before any
  update.
- FR2 Scoreboard metrics: log-loss (probabilities clipped to [1e−4, 1−1e−4]), Brier, AUC (rank-based, with ties
  handled), and calibration in 5 bins. The `enough_data` flag means n ≥ 50.
- FR3 Controller: recent success = exponentially weighted (α = 0.3) over your last 10 graded answers across all
  sessions. It does nothing until there are 3 answers.
  - If recent success > target + 0.07: one notch harder.
  - If recent success < target − 0.07: one notch easier.
  - At most one notch per answer.
  - A hard failure (FAILED, HIGH_CONFIDENCE_ERROR or MISSING_PREREQUISITE) → Δ = 0.5 plus a remedial splice, as today.
- FR4 A notch: Δ ±0.5 within [0.5, 2.5] for teaching; practice cue level ±1 within [1, 4] for the next practice item.
- FR5 Settings target selector (persisted); the Advanced scoreboard panel; the controller line in Details; `./polya eval`.
- FR6 A simulation harness (`backend/simulate.py`) generates answers from a synthetic learner with known parameters, so
  the scoreboard and controller can be tested before real data exists.

## Non-functional requirements
- No new primary-UI controls besides the one target setting; scoreboard numbers only under Advanced.
- The scoreboard query stays under 100 ms for 10k answers.

## Edge cases and failure behaviour
- AUC is undefined when all outcomes are the same → shown as "—". Zero answers → "No answers yet".
- An idea's first answer → its per-idea baseline is 0.5.
- Missing or corrupt prefs.json → defaults; it is written atomically.

## Acceptance and verification
- Unit tests:
  - the metric functions against hand-computed values;
  - AUC with ties;
  - the controller bands, and that it waits for 3 answers;
  - the hard-failure path is unchanged.
- Simulation test: on a synthetic BKT learner (300 answers), `p_bkt`/`p_combined` beat the global baseline on log-loss.
  A synthetic learner with a fixed difficulty-to-success curve ends with recent success within ±0.08 of the target.
- API test: graded answers create prediction rows; `/api/model-eval` shape; the target setting round-trips and persists.
- `./polya eval` output on the seeded DB shows "Not enough answers yet".
- WebKit check: Settings target selector and the Advanced panel render with no console errors and no jargon added to
  the primary screens. `make test`, `npm run build` and `make bundle` all pass.

## Decomposition sketch
1. Backend: metrics + controller in cognitive_math; table + logging in apply_assessment; prefs; endpoint; simulate.py; tests.
2. Frontend: target selector, Advanced panel, Details line (depends on the endpoint shape).
3. CLI `polya eval`; README "How it adapts" paragraph; rebuild the app; push v0.4.0.

## Risks, assumptions, deferred decisions
- The 85% target is derived for machine learners (Wilson et al. 2019); for humans it is a reasonable, tunable
  heuristic. The scoreboard is how you'll find out whether it helps.
- The baselines are deliberately simple; beating them is the minimum bar, not proof of a good model.
- Deferred: fitting parameters (A2), successive relearning (C8), per-topic calibration feedback (C12).
