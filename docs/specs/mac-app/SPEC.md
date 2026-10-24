---
slug: mac-app
status: approved
bead: none
approved_by: nathan
approved_at: 2026-10-24T01:00:13Z
---
# LearnHarness as a Mac app + public GitHub repo

## Goals
- G1 Publish the project to a public GitHub repo (`chow-n/learn-harness`) with a README and license.
- G2 Stage A: double-clickable `LearnHarness.app` running this repo's code in a native window. One process, no terminal.
- G3 Stage B: a self-contained `LearnHarness.app` (embedded Python, built frontend) that runs from /Applications without the repo.
- G4 Zero-key voice dictation inside the app window via on-device macOS speech recognition.

## Non-goals
- Notarization, Developer ID signing, App Store, auto-update, Intel/Windows/Linux builds, multi-user, cloud sync.

## User-facing behaviour
- Double-click LearnHarness.app → native window titled "LearnHarness" opens on the same UI as today. No Vite, no ports to manage.
- The first launch copies the existing repo `harness.db` + `workspace/` to `~/LearnHarness/` (if it doesn't exist yet). Afterwards the app, `./start.sh` and `./harness-cli` all read/write `~/LearnHarness/`.
- App menu: *Open Workspace Folder*, *Edit scratch.tex* (opens in $EDITOR via Terminal), *Open in Browser*, *Reveal Data Folder*, Quit (stops the server).
- Mic button: the first use asks for microphone + speech-recognition permission; then dictation streams on-device transcripts into the focused field, with prosody metrics as today.
- `claude` CLI fallback works from the app (PATH resolved from the login shell).

## Architecture and integration decisions
- D1 Two stages (repo-backed app → self-contained bundle). Rejected: bundle-only (slower iteration).
- D2 Shared data home `~/LearnHarness` (env `LEARNHARNESS_HOME`), one-time migration from the repo. Rejected: App Support split (two diverging graphs).
- D3 Native speech: `SFSpeechRecognizer` + `AVAudioEngine` via PyObjC inside the backend process, exposed through the existing `/ws/dictation` protocol (`{type:"transcript", text, is_final, words}`), so the frontend is unchanged except for an engine label. Enabled only in app mode (`LEARNHARNESS_APP=1`), so `./start.sh` in a browser never grabs the mic from Python. Rejected: Deepgram-only, open-in-browser.
- D4 Ad-hoc codesign (`codesign -s -`), this Mac only.
- D5 GitHub: public repo `chow-n/learn-harness`, MIT license (ASSUMED), publish the current tested state first as `v0.1.0`, then push the Mac-app work. Pre-push scan for secrets/keys and personal paths.
- Shell: pywebview (WKWebView) over a single uvicorn server on a random free localhost port; FastAPI serves `frontend/dist` with SPA fallback.

## Existing components to reuse (do not rebuild)
- `backend/main.py:app` (all routes, `/ws`, `/ws/dictation` relay), `backend/config.py` (env overrides), `backend/seed.py:seed_if_empty`.
- `frontend/src/utils/prosodyAudioEngine.ts` dictation client (already speaks the `/ws/dictation` protocol and falls back on `unavailable`).
- `start.sh` health-check pattern, `harness-cli` (point at `~/LearnHarness/harness.db`).

## Interfaces and data contracts
- `config.HOME = Path(env LEARNHARNESS_HOME or ~/LearnHarness)`; `DB_PATH = HOME/harness.db`; `WORKSPACE = HOME/workspace`. Existing `LEARNHARNESS_DB`/`LEARNHARNESS_WORKSPACE` overrides still win (tests rely on them).
- `/ws/dictation` priority: Deepgram key → native speech (app mode + permission granted) → `{type:"unavailable"}`. New first frame `{type:"ready", engine:"deepgram"|"native"}`.
- `GET /api/health` adds `app_mode: bool`. Launcher writes the chosen port to `HOME/.port`, and `harness-cli` reads it.
- Frozen builds: `tools.verify_math_sympy` runs `[sys.executable, "--lh-verify"]` with code on stdin when `sys.frozen`, because a PyInstaller binary cannot run `python -c`.

## Functional requirements
- FR1 FastAPI serves `frontend/dist` at `/` (SPA fallback to index.html) when present; `/api` and `/ws` unchanged.
- FR2 Data home + one-time migration (copies, never moves; skipped if `~/LearnHarness` exists).
- FR3 `macos/launcher.py`: resolves login-shell PATH, starts uvicorn in a thread on a free port, waits for `/api/health` 200, opens the pywebview window plus app menu, stops the server cleanly on quit.
- FR4 `make app` builds the frontend and creates `~/Applications/LearnHarness.app` (Info.plist with `NSMicrophoneUsageDescription` and `NSSpeechRecognitionUsageDescription`, generated `.icns`, ad-hoc signed). Its executable runs the repo venv's launcher.
- FR5 Native speech backend (PyObjC Speech + AVFoundation) streaming partial and final transcripts over `/ws/dictation`; graceful `unavailable` when permission is denied.
- FR6 `make bundle` builds the self-contained app with PyInstaller into `dist/LearnHarness.app` (all backend data files, the content bank, demos, `frontend/dist`, the starter workspace) and installs it to `/Applications`.
- FR7 The frozen SymPy verifier path (`--lh-verify`) works inside the bundle.
- FR8 GitHub: README (what it is, the science with honest caveats, quick start, app build, screenshots), LICENSE, `.gitignore` audited, the repo created, `v0.1.0` tag pushed; the Mac-app work pushed after it passes.

## Non-functional requirements
- App cold start to window under 5 s (stage A) / under 8 s (stage B) on this Mac. The bundle is likely 250–400 MB (scipy/sympy); acceptable.
- No API keys or personal data in the repo; keys stay in memory or environment only.

## Edge cases and failure behaviour
- Port collision → retry with another free port. Server fails to boot → native alert with the last 30 log lines and the log path.
- Mic or speech permission denied → dictation reports `unavailable`, and the prosody meter still runs if mic access exists.
- Two app instances → second launch focuses the first (lock file `HOME/.lock` with pid).
- `claude` missing → deterministic engine (existing behaviour).

## Acceptance and verification
- `make test` green, plus new tests: data-home resolution/migration (tmp HOME), SPA static serving, frozen-verifier argv path (simulated), `/ws/dictation` reports `ready`/`unavailable` correctly by mode.
- Stage A: `open ~/Applications/LearnHarness.app` → `curl localhost:$(cat ~/LearnHarness/.port)/api/health` returns 200 with `app_mode:true`; window screenshot via `screencapture -l`; quit via the menu leaves no python process listening.
- Stage B: the same checks with `/Applications/LearnHarness.app`, with the repo venv unreachable (PATH stripped); `POST /api/subagents/SYMBOLIC_VERIFIER/run` returns VERIFIED.
- Voice: a manual check by Nathan (permission prompts need a human click); the server log shows native transcripts.
- GitHub: `gh repo view chow-n/learn-harness` is public, README renders, a secret scan (`git grep -iE "sk-|api_key=|token"`) is clean, and a fresh clone passes `make install && make test && make build`.

## Decomposition sketch
1. GitHub v0.1.0 (README, LICENSE, scan, create repo, push, tag). Independent; first.
2. Prefactor: data home + migration + SPA static serving + health `app_mode` (backend, tests).
3. Stage A: launcher + `make app` bundle script + icon (depends on 2).
4. Native speech in `/ws/dictation` (depends on 2; parallel with 3).
5. Stage B: PyInstaller spec, `--lh-verify` frozen path, `make bundle` (depends on 3, 4).
6. Push Mac-app work + README update.

## Risks, assumptions, deferred decisions
- ASSUMED MIT license; repo name `learn-harness`; public visibility (your instruction).
- Risk: TCC permission attribution for a repo-backed app whose executable execs the venv Python. Mitigation: launcher runs inside the bundle's own executable stub; verify the prompts name LearnHarness.
- Risk: PyObjC Speech availability on macOS 26 / Python 3.12 wheels. Fallback: Deepgram-only plus a note.
- Risk: PyInstaller with scipy/sympy hidden imports. Mitigation: collect-all hooks, smoke test.
- Deferred: fitting FSRS/BKT parameters to your history (separate spec).
