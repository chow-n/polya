---
slug: model-eval-85
status: approved
bead: none
started: 2026-10-23
---
# Objective (user's words, verbatim)
"yes do that" — re: "do A1 [scoreboard: how well the learner model predicts your next answer] and C7 [85% rule
controller] now, they are small and need no data".

# Recon
- Δ rule: backend/cognitive_math.py:update_step_delta (2 clean+confident → +0.5; fail/HCE/MISSING_PREREQUISITE → 0.5
  + remedial splice in backend/agents/orchestrator.py:submit). Practice cue level is fixed per session (create_session).
- Graded answers: telemetry_traces (phase PROBE/CHECK/PRACTICE_CHUNK/REFEREE) store bkt_mastery_before,
  fsrs_stability_before, is_correct, trace_quality_score, confidence — but NOT elapsed time / R at review, and no
  model prediction. Schema of telemetry_traces is the original spec's exact DDL.
- Only 4 graded answers exist today (all scripted seed) → scoreboard needs a simulation path to be testable now.
- Wilson et al. 2019 "85% rule" is derived for gradient learners on binary tasks; human evidence is indirect
  (desirable difficulty, zone of proximal development). Treat 85% as a tunable target, not a law.

# Decision tree
- D1 [CP] Where predictions are recorded — DELEGATED (technical): new side table `model_predictions`
  (keeps original telemetry schema exact). Alt: ALTER telemetry_traces.
- D2 [CP] What the 85% controller adjusts — ACCEPTED
- D3 Target: fixed 85% vs adjustable in Settings — ACCEPTED
- D4 Where the scoreboard shows — ACCEPTED

# Ledger
- D1 DELEGATED: side table model_predictions (original telemetry DDL untouched). 2026-10-23
- D2 ACCEPTED: adjust teaching Δ and practice cue level. Rejected: Δ only. 2026-10-23
- D3 ACCEPTED: 85% default, 80/85/90 in Settings, persisted. Rejected: fixed. 2026-10-23
- D4 ACCEPTED: ./polya eval + Settings → Advanced panel. Rejected: CLI only. 2026-10-23

# Assumptions
- Prediction logged BEFORE the update for every graded answer: P(correct) from mastery alone, from memory alone,
  and combined; plus baselines (your overall accuracy; per-idea running accuracy).
- Metrics: log-loss, Brier, AUC, calibration bins; shown with n and a "not enough data yet" state below ~50 answers.
- "Success" for the controller = correct AND not right-for-the-wrong-reason (q ≥ 0.45).
- Hard-failure remediation (remedial step splice) stays as is.

# Constraints / Non-goals
- No parameter fitting yet (that is A2, later, once data exists). No primary-UI clutter.

# Reuse
- cognitive_math (bkt_posterior, retrievability, murphy_decomposition), orchestrator.apply_assessment, ./polya CLI.

# Build notes (2026-10-24)
- Shipped v0.4.0 (11822aa). FR3 simulation check reads "settled success" = mean success over answers after the first
  third, since a single 10-answer EWMA reading is too noisy (sd ≈ 0.15) to assert ±0.08 on.
- Observed: hard-failure resets (kept per spec) fire on most misses in teaching, so Δ spends much time at 0.5; the
  practice cue level is unaffected by resets and does the real tracking. EWMA over 10 makes the level swing L1↔L4.

# Open questions

# Pending question: none — APPROVED by Nathan ("go") 2026-10-24; build with one worker
