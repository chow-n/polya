---
slug: mac-app
status: approved
bead: none (learn-harness is not a rig in ~/hodge-city)
started: 2026-10-23
---
# Objective (user's words, verbatim)
"yes, maybe make a mac app for now then add the packaging"

# Recon
- Today: two dev servers via ./start.sh (uvicorn :8000 + Vite :5173/5174), browser tab.
- backend/main.py does not serve frontend/dist; Vite proxies /api and /ws in dev only.
- backend/config.py:9-15 paths default to the repo root; LEARNHARNESS_DB / LEARNHARNESS_WORKSPACE env overrides exist.
- macOS 26.5.2 arm64; no codesigning identities (ad-hoc signing only); pywebview not installed.
- frontend/src/utils/prosodyAudioEngine.ts:77 uses webkitSpeechRecognition — absent in WKWebView
  (pywebview/Tauri window), so zero-key dictation breaks inside an app window; getUserMedia prosody works
  with NSMicrophoneUsageDescription.
- GUI apps don't inherit the shell PATH → `claude` (~/.local/bin) not found unless resolved via login shell.

# Decision tree
- D1 [CP] Staging: repo-backed .app first, then self-contained bundle — ACCEPTED
- D2 [CP] Where data lives for app + dev — ACCEPTED
- D3 Voice dictation inside the app window — ACCEPTED
- D4 Signing / distribution — ACCEPTED

# Ledger
- D1 ACCEPTED: two stages — (a) repo-backed LearnHarness.app, (b) self-contained PyInstaller bundle. Why: fast first win, edits visible on relaunch; bundle later. Rejected: bundle-only (slower feedback). 2026-10-23
- D2 ACCEPTED: shared data home ~/LearnHarness (harness.db + workspace/) for app and ./start.sh, one-time copy from repo. Why: one source of truth, visible scratchpad path. Rejected: App Support split (two diverging graphs). 2026-10-23
- D3 ACCEPTED: native on-device macOS speech (SFSpeechRecognizer) behind /ws/dictation. Why: zero-key voice survives WKWebView. Rejected: Deepgram-only, open-in-browser. 2026-10-23
- D4 ACCEPTED: ad-hoc signed, this Mac only. Why: no Developer ID on this Mac; local build avoids Gatekeeper. Rejected: notarized. 2026-10-23

# Assumptions
- One process: FastAPI serves the built frontend; the app picks a free localhost port (no 5173 clash).
- Python-native shell: pywebview (WKWebView) + PyInstaller; no Node needed at runtime.
- claude CLI located via `zsh -lc 'command -v claude'` at startup.

# Constraints / Non-goals
- macOS arm64 only; no auto-update, no App Store, no multi-user.

# Reuse
- backend/main.py app, backend/config.py env overrides, start.sh health-check logic, frontend build.

# Open questions

# Build notes (2026-10-23)
- Stage A built with py2app 0.28 alias mode; NSBundle.mainBundle() = io.github.chow-n.learnharness (TCC-safe).
- pywebview `closed` does not fire on Cmd+Q; shutdown hooked on `closing` too (applicationShouldTerminate_).
- Stage B PyInstaller 6.22: sympy/numpy/scipy must be hidden imports (used only in verifier child code). 102 MB, cold start 1.3 s.
- Frozen app seeds from the bundle and never reads the repo DB (LEGACY_DB is inside the bundle) — by design.
- Not verified by agent: mic + speech permission prompts and live transcription (need a human click).

# Pending question: none (approved 2026-10-24T01:00:13Z)
