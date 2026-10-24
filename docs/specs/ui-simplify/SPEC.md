---
slug: ui-simplify
status: approved
bead: none
approved_by: nathan
approved_at: 2026-10-24T02:00:09Z
---
# Pólya: a minimalist, self-explanatory UI and a new name

## Goals
- G1 A first-time user can go from opening the app to answering their first question with no instructions: type a topic, press Start.
- G2 Every screen shows one primary action; the science runs underneath without asking the learner to understand it.
- G3 Rename the product to **Pólya** (after George Pólya, *How to Solve It*: guess first, try the simple case, look back).
- G4 Calm visual design that follows the macOS light/dark appearance.

## Non-goals
- No change to the cognitive models, the orchestrator or the API contract (docs/API.md). Nothing is deleted: advanced telemetry moves behind "Details" and an "Advanced" setting.

## User-facing behaviour
**Header (all screens):** wordmark `Pólya` · `Learn` `Review` `Map` · a quiet activity indicator while helpers run ("Checking your math…") · ⚙ settings. Nothing else.

**Learn (home)**
- One large field "What do you want to understand?" and a **Start** button (Cmd+Enter). Start creates a probe-then-teach session automatically.
- Below: "Review · N due →" (when N > 0) and up to 3 "Continue …" rows for active sessions.
- First run only: a dismissible three-line "How Pólya works" (1. Guess before you see answers. 2. Read a short explanation, then check yourself. 3. Pólya brings ideas back right before you'd forget them.)
- Small secondary link: "Use my notes…" (attach workspace files).

**Session (focus mode):** a thin top strip with the topic, a row of progress dots (one per idea in the plan; remedial ideas appear as they are inserted) and "Exit". Below, one centered card:
- *Question* (probe / predict / check): the question → field "Your guess, in your own words" → **Lock in guess**. The answer options then fade in → pick one → choose confidence from four chips (Guessing · Unsure · Fairly sure · Certain) → **Check**. The result appears inline (✓/✗ + explanation) → **Continue**.
- *Explanation* (reading): short text with the diagram/demo. Selecting text offers "Add a thought". **Continue**.
- *Practice*: the problem, then a single "Think out loud" thread (Shift+Enter sends a chunk; feedback appears under it). **Hint** reveals one rung at a time, labelled in plain words. **I'm done** + confidence chips.
- *Proof check* (referee): the steps as cards; click the wrong one, explain why, **Submit**.
- *Explain it* (Feynman): a chat with the confused student.
- Voice: a mic button inside each text field; while listening, a subtle level ring. Prosody numbers only appear in Details.
- Math: a live preview appears under a field only when it contains LaTeX (`$` or `\`); the snippet toolbar sits behind a "∑" button.
- **Details** (collapsed, at the bottom of each card): why this step was chosen (EIG table), the diagnosis, the scoring data, helper (sub-agent) artifacts, prosody.

**Review:** a big **Start review (N due)** button that runs interleaved practice. Below it, the due list with a simple "memory" bar per idea, and "Challenge me": *Find the flaw in a proof* · *Explain it to a confused student*. One plain sentence on calibration ("You tend to be overconfident: you say 81% sure and you're right 75% of the time"), with the Brier decomposition under Details.

**Map:** the graph with a minimal toolbar: search, colour by (Topic · Mastery · Due), and Graph | List. Layering and edge-type filters sit in a "View" menu; the legend is collapsed by default. Clicking a node opens a simple panel with the statement, the intuition, "Memory: strong/fading" and **Practice this**, plus Details for the numbers. List view = the reasoning-chains table and your notes files.

**Settings (⚙):** AI engine and API keys · appearance (System / Light / Dark) · workspace folder (open, and edit scratch.tex) · **Advanced telemetry** toggle, which restores the helper activity panel, status pills and raw metrics for power users.

## Architecture and integration decisions
- D1 Focus layout with 3 destinations (Learn / Review / Map); side panels removed. Rejected: declutter in place.
- D2 The system picks the mode (new topic → PROBE; review → PRACTICE on the queue; duels under "Challenge me"). Rejected: an explicit mode picker.
- D3 Name **Pólya**; ASCII "polya" in identifiers. Rejected: Tao (a living person: implied affiliation), Noether, Euler.
- D4 Theme follows the system (light + dark tokens) with a manual override. Rejected: dark-only, light-only.
- D5 (ASSUMED, confirm on approval) Full rename:
  - GitHub repo `chow-n/learn-harness` → `chow-n/polya` (GitHub redirects the old URL).
  - App `Pólya.app`, bundle id `io.github.chow-n.polya`.
  - Data home `~/LearnHarness` → `~/Polya`, moved on first launch with the old path left as a symlink.
  - CLI `./polya` (the `harness-cli` name stays as a shim for one release).
  - Env vars `POLYA_*`, with `LEARNHARNESS_*` still accepted.
  - Not renamed: the local repo folder and the internal Python package `backend`.

## Existing components to reuse (do not rebuild)
- Store and API client: `frontend/src/store/useHarnessStore.ts`. Math rendering: `utils/katexRenderer.tsx`. Voice: `utils/prosodyAudioEngine.ts`.
- Step logic in `EpistemicLockBox`, `ReadingStreamBox`, `PracticeArena`, `RefereeDuelArena`, `TelemetryInputDock`: recompose and restyle; keep the submission payloads byte-identical.
- `HypergraphCanvas` renderer (simplify the toolbar; keep the layout engine). `ReasoningChainsTable` becomes Map → List.

## Interfaces and data contracts
- Backend API unchanged. Rename touch points:
  - `backend/config.py` HOME default and env aliases.
  - `macos/setup_app.py` PLIST, `macos/LearnHarness.spec` → `macos/Polya.spec`.
  - `start.sh`, `harness-cli` → `polya`, README, the app menu and window title.
- Frontend-only settings (theme override, advanced toggle, first-run dismissed) live in `localStorage`, with a safe fallback when unavailable.

## Functional requirements
- FR1 Header with exactly: wordmark, 3 nav items, activity indicator, settings.
- FR2 Learn home: topic field + Start (creates PROBE), review entry, continue rows, first-run explainer.
- FR3 Session focus view with progress dots and a single step card per kind as described; payloads unchanged.
- FR4 Details disclosure per card holding all advanced telemetry.
- FR5 Confidence chips map to 0.15 / 0.4 / 0.7 / 0.9 (≥ 0.75 "Certain" still triggers the hypercorrection logic).
- FR6 Review screen: start review, due list, Challenge me, a plain-language calibration sentence.
- FR7 Map: simplified toolbar, colour by Topic / Mastery / Due, Graph | List, simplified node panel.
- FR8 Settings with an appearance override and an Advanced telemetry toggle that restores the legacy panels.
- FR9 Light and dark themes via CSS custom properties; `prefers-color-scheme` plus the override.
- FR10 Rename per D5 across UI, app bundle, data home (with migration), CLI, README, repo.

## Non-functional requirements
- At most 6 interactive controls visible on Learn home before the first session; primary button contrast ≥ 4.5:1 in both themes.
- No jargon in primary UI. The words Bjork, Brier, EIG, Epistemic, hypercorrection, Δ, cue level, miss class, sub-agent appear only inside Details, Settings → Advanced, or tooltips.
- Keyboard: Cmd+Enter = the card's primary action everywhere; Esc closes Details or panels; 1/2/3 switch destinations when not typing.
- No layout shift when options unlock or feedback appears (reserved space or animation).

## Edge cases and failure behaviour
- The slow `claude` CLI (10–40 s): the card shows a calm "Preparing your next step…" placeholder with a skeleton, never a frozen button.
- No due items: the Review shows "Nothing due. Start something new" and a link to Learn.
- Migration: if both `~/LearnHarness` and `~/Polya` exist, use `~/Polya` and leave the old folder untouched.

## Acceptance and verification
- `make test` green, plus a migration test (`~/LearnHarness` → `~/Polya`).
- `npm run build` exits 0.
- WebKit flow script: Home → type topic → Start → lock guess → pick option → confidence chip → Check → Continue through a full session, with zero console/HTTP errors. Screenshots of Home, question (before and after lock), explanation, practice, review and map, in light and dark, reviewed against this spec.
- Rendered-text jargon check on Home, Session (Details closed), Review and Map.
- The control count on Home is ≤ 6.
- `make bundle` produces `/Applications/Pólya.app`; it launches and is healthy.
- `gh repo view chow-n/polya` works and the old URL redirects.

## Decomposition sketch
1. Theme tokens (light/dark) + new shell/header/nav + settings sheet (foundation, frontend).
2. Learn home + session focus view with all step cards (depends on 1; largest slice).
3. Review screen + simplified Map/List (depends on 1; parallel with 2).
4. Rename: backend config/migration, CLI, app bundle, README, repo (independent; parallel).
5. Verification pass: WebKit flow, screenshots, jargon/control checks, bundle.

## Risks, assumptions, deferred decisions
- Risk: the restyle touches 3.4k lines of CSS. Mitigation: a new token-based stylesheet for the new shell; legacy classes are only kept for the Advanced panels.
- Risk: renaming the GitHub repo breaks clones until remotes update (GitHub redirects git operations too).
- ASSUMED: the app name keeps the diacritic ("Pólya"); identifiers use "polya".
- Deferred: a guided tour, mobile layout, onboarding analytics.
