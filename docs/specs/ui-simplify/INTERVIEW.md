---
slug: ui-simplify
status: approved
bead: none
started: 2026-10-23
---
# Objective (user's words, verbatim)
"streamline the UI/UX, it feels cluttered. It should be minimalist and easy to use (I dont really know how to use it
right now). Furthermore, change the name, maybe name it after a famous scientist or something, not feynman or einstein.
Maybe like a famous mathematician. i like tao."

# Recon
- frontend/src/App.tsx: 4 tabs (Session / Hypergraph / Arena / Vault) + 3-column session layout.
- Clutter sources (screenshots in docs/screenshots/):
  - TopTelemetryBar.tsx: 4 tabs + 6 jargon pills (scratch.tex, Bjork, Due, Hypercorrection, Brier, LLM).
  - SidebarSubagentDock.tsx: 6 mode buttons, target dropdown, file checkboxes, session list, 8 sub-agent cards.
  - DependencyMiniMap.tsx: right pane with plan tree + Δ meter + outcome timeline.
  - Step views: EIG table, "why this step", lock overlay with a citations paragraph, a 12-button LaTeX snippet bar,
    a mic meter showing 5 metrics, a 5-tick confidence slider, and an assessment JSON card.
- Jargon in primary UI: Epistemic Lock, Bjork window, Brier, EIG, Δ, cue level, hypercorrection, miss class.
- No onboarding; the user must pick one of 6 modes before anything happens.
- Backend API is sufficient as-is (docs/API.md); the redesign is frontend-only plus a rename.
- Name appears in: app bundle (macos/setup_app.py PLIST, LearnHarness.spec), ~/LearnHarness data home, README,
  repo name chow-n/learn-harness, harness-cli, window title, frontend brand.

# Decision tree
- D1 [CP] Navigation / layout model — ACCEPTED
- D2 [CP] How a session starts (mode choice) — ACCEPTED
- D3 [CP] New name — ACCEPTED
- D4 Visual theme — ACCEPTED
- D5 Rename depth: repo, data folder, CLI — ACCEPTED (full rename, approved with spec)

# Ledger
- D1 ACCEPTED: Focus layout, Learn/Review/Map, one card, Details disclosures. Rejected: declutter in place. 2026-10-23
- D2 ACCEPTED: system picks the mode; duels under "Challenge me". Rejected: explicit mode picker. 2026-10-23
- D3 ACCEPTED: Pólya. Rejected: Tao (living person, implied affiliation), Noether, Euler. 2026-10-23
- D4 ACCEPTED: follow system light/dark, one accent. Rejected: dark-only, light-only. 2026-10-23

# Assumptions
- Nothing is deleted: advanced telemetry (EIG table, sub-agent swarm, calibration decomposition, assessment JSON)
  moves behind "Details" disclosures or a separate Insights view.
- Plain-language copy replaces jargon in primary UI; jargon remains in tooltips and docs.
- Inline first-run guidance (one-line hints in empty states) rather than a modal tour.

# Constraints / Non-goals
- No backend behaviour change beyond the rename; API contract unchanged.

# Reuse
- All step components' logic and the store; restyle and recompose, not rewrite.

# Open questions

# Pending question: none (approved 2026-10-24T02:00:09Z)
