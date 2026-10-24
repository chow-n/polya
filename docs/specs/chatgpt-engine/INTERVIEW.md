---
slug: chatgpt-engine
status: approved
bead: none (learn-harness is not a gc rig)
started: 2026-10-24
---
# Objective (user's words, verbatim)
"Also, maybe you can connect polya to chatgpt chat (not work). Is this possible" → "why cant polya open a browser and
talk to chat there with my account" → "yes do the browser version"

# Recon
- backend/llm.py: chain API keys (anthropic/openai/gemini/openrouter) → `claude -p --output-format json` → deterministic;
  10-min circuit breaker on CLI failure; provider list config.PROVIDERS; Settings engine dropdown (SettingsSheet.tsx).
- codex-cli 0.162.1 at ~/.local/bin/codex, auth_mode=chatgpt, plan=plus (personal), default model in ~/.codex/config.toml.
- Verified: `codex exec --ephemeral --skip-git-repo-check -s read-only -C <tmp> --output-schema s.json -o out.json "<prompt>"
  </dev/null` → valid JSON in 8 s, ~16k tokens/call (Plus Codex allowance). Without </dev/null it hangs reading stdin.
  User's codex hooks (Stop) fire unless --ignore-user-config.
- Browsers: no Google Chrome; Arc + Firefox installed. Playwright Chromium 1243 cached in ~/Library/Caches/ms-playwright
  (from the MCP server); python `playwright` not in backend/.venv. Pólya.app is PyInstaller (macos/Polya.spec).
- Told the user (2026-10-24): OpenAI Terms forbid automated extraction of output; account-flag risk; fragile UI; slower;
  history clutter. User chose the browser route anyway.
- ChatGPT-side connector (MCP in Developer Mode): needs a public HTTPS server (tunnel to this Mac); sources disagree whether
  Plus custom connectors may write (needed to record answers). Local stdio servers unsupported.

# Decision tree
- E1 [CP] Route: drive chatgpt.com in a browser with the user's account — ACCEPTED
- B1 [CP] Sign-in: Google (fact) → sign in through a plain, non-automated launch of the dedicated profile — ACCEPTED
- B2 [CP] Chat history: Temporary Chat per request — ACCEPTED
- B3 Fallback: Codex → Claude app → offline — ACCEPTED
- B4 Distribution: browser engine is private to Nathan (not in the public repo/app) — ACCEPTED
- B5 Engine selection: opt-in only ("Automatic" never picks it) — DELEGATED (non-negotiable for account safety)
- B6 Dedicated Chromium profile in ~/Polya/chatgpt-browser, window kept in background, comes forward only when ChatGPT
  needs you; calls serialized (one tab) — DELEGATED (technical)

# Ledger
- B1 ACCEPTED (fact): user signs in to ChatGPT with Google. Google often refuses sign-in inside automation-controlled
  browsers, so the one-time sign-in uses a plain launch of the same dedicated profile (no automation attached); the
  session cookie then serves automated use. If Google still refuses: add a password to the OpenAI account, or use Codex.
- B2 ACCEPTED: fresh Temporary Chat per request. Rejected: one visible conversation per session. 2026-10-24
- B3 ACCEPTED: on failure fall back Codex → Claude app → offline (adds the official Codex engine). Rejected: Claude → offline.
- B4 ACCEPTED (answer "browser optionm only for me"): the browser engine lives in a git-ignored local module; the public
  repo and other people's builds never contain it; Nathan's own `make bundle` includes it when present. Codex engine is
  public. Rejected: ship to everyone; ./start.sh-only. 2026-10-24
- E1 ACCEPTED: browser route on chatgpt.com with the user's Plus account, as an experimental opt-in engine. Why: user's
  explicit choice after being told the ToS/account/fragility risks. Rejected: Codex engine (recommended; user preferred
  the chat itself), in-ChatGPT connector. 2026-10-24

# Assumptions
- Usage counts against the Plus Codex allowance; a 20-step session ≈ 20 calls ≈ 300k tokens. Shown in Settings copy.
- Same circuit breaker as the claude CLI; limit-reached errors fall through to the next engine.

# Constraints / Non-goals
- NO bot-detection evasion: no stealth patches, fingerprint spoofing, CAPTCHA solving or challenge bypass. On any login
  or challenge page, Pólya brings the window forward, asks the user, and otherwise falls back to the next engine.
- Never read cookies/tokens from Arc/Firefox or other browser profiles.
- Never read or copy ~/.codex/auth.json tokens; codex handles auth. No ChatGPT web scraping or unofficial APIs.

# Reuse
- llm._claude_cli pattern (subprocess, timeout, breaker), llm.extract_json, config.PROVIDERS, SettingsSheet engine list.

# Open questions

# Pending question: none — APPROVED by Nathan ("Approve the chatgpt") 2026-10-24; spec approval covers the B4
  reading as written in SPEC.md B4. Build with one worker.
