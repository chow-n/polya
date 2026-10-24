---
slug: chatgpt-engine
status: approved
bead: none
approved_by: Nathan
approved_at: 2026-10-24T14:32:00-05:00
---
# ChatGPT engines: your chat in a browser (private) and Codex (public)

## Goals
- G1 Let Pólya use Nathan's personal ChatGPT Plus account as its AI engine by driving chatgpt.com in a dedicated browser
  window — an experimental, opt-in engine that exists only on Nathan's machine.
- G2 Add the official Codex CLI (signed in with the same Plus account) as an engine, used first whenever the browser route
  fails, and available to everyone in the public build.
- G3 Remember the chosen engine across restarts.

## Non-goals
- No bot-detection evasion of any kind: no stealth patches, fingerprint spoofing, CAPTCHA solving or challenge bypass.
- Never read cookies, tokens or profiles from Arc, Firefox or any other browser; never read `~/.codex/auth.json`.
- No in-ChatGPT connector (Pólya as a ChatGPT app). No choosing ChatGPT models (whatever chatgpt.com defaults to).

## User-facing behaviour
- Settings → AI engine gains:
  - **ChatGPT via Codex (your Plus account)** — shown when `codex` is installed and signed in.
  - **ChatGPT in browser (experimental)** — shown only when the private module is present. Choosing it shows the risk line
    "Automating chatgpt.com breaks OpenAI's terms and can get your account flagged. Use at your own risk." and a
    **Sign in to ChatGPT** button.
- **Sign in once:** the button (or `./polya chatgpt-login`) opens a plain Chromium window on Pólya's own profile
  (`~/Polya/chatgpt-browser`). You sign in with Google as usual and close the window.
- **While learning:** a Chromium window stays in the background. Each request opens a fresh Temporary Chat, so nothing
  lands in your ChatGPT history. If ChatGPT shows a login, "verify you are human" or limit page, the window comes to the
  front, Pólya shows "ChatGPT needs you in the Pólya browser window", and that request goes to the next engine instead.
- **Fallback order** when the browser engine is selected: ChatGPT browser → Codex → Claude app → offline. The engine that
  actually answered shows in Details ("written by …"), as today.
- The engine choice persists in `~/Polya/prefs.json`. "Automatic" never picks the browser engine; its order becomes
  API keys → Claude app → Codex → offline.

## Architecture and integration decisions
- E1 Browser route on chatgpt.com, opt-in only (user's explicit choice after the ToS/account risks were laid out).
  Rejected: Codex-only (recommended), in-ChatGPT connector.
- B1 Google sign-in through a plain (non-automated) launch of the dedicated profile; automation attaches only afterwards.
- B2 A fresh Temporary Chat (`https://chatgpt.com/?temporary-chat=true`) per request. Rejected: one conversation per session.
- B3 Fallback Codex → Claude app → offline. Rejected: Claude → offline.
- B4 Private distribution: the browser engine lives in `backend/local_engines/` (git-ignored). `llm.py` loads it only if
  it is importable. Nathan's local `make bundle` includes it; the public repo and anyone else's build never do. The
  Codex engine and the generic optional-engine hook are public.
- B5 One browser, one tab and one request at a time (an asyncio lock), plus a minimum 3 s gap between requests.

## Existing components to reuse
- `backend/llm.py`: `_claude_cli` (subprocess, timeout, circuit breaker), `extract_json`, `complete_json`,
  `resolve_engine`, `describe_engine`, `keys_present`.
- `backend/config.py`: `PROVIDERS`, `load_prefs` / `save_prefs` (model-eval-85).
- `frontend/src/components/SettingsSheet.tsx` (engine select), `kit.tsx` toasts, the `/ws` hub `error` event.
- `macos/Polya.spec` (PyInstaller) for the local bundle.

## Interfaces and data contracts
- `config.PROVIDERS` += `"codex_cli"`, `"chatgpt_browser"`. `SettingsOut` += `codex_available: bool`,
  `chatgpt_browser: {available: bool, signed_in: bool | null, last_error: str | null}`. Prefs: `provider`.
- Codex call (owned by `llm.py`):
  - `codex exec --ephemeral --skip-git-repo-check -s read-only -C <empty temp dir> -o <tmp>/last.txt "<system + user>"`
    with stdin `/dev/null` and a 120 s timeout.
  - Its JSON is parsed by `extract_json`.
  - The user's Codex hooks are skipped (`--ignore-user-config`) if auth and model still resolve; this is verified in
    the build, and the hooks stay if they don't.
- Optional engine hook (public): `backend/local_engines/__init__.py` may expose
  `ENGINES: dict[str, Engine]`. `Engine` has `available()`, `async complete(system, user) -> str` and `status() -> dict`.
  `llm.py` imports it in a `try/except ImportError`.
- Browser engine (private): `chatgpt_browser.py`.
  - Uses Playwright `launch_persistent_context(~/Polya/chatgpt-browser, headless=False)` on Playwright's Chromium.
  - Raises `NeedsUser(reason)` for login/challenge/limit pages, and `EngineError` for timeouts and layout changes.
  - `complete()` returns the last assistant message's text.
- WebSocket: a new `engine_attention` event `{engine, reason}` → the UI toast.

## Functional requirements
- FR1 The Codex engine passes the same LLM contract as the other engines. Missing codex, logged out, timeout or limit
  each trip the 10-minute circuit breaker, and the request falls through.
- FR2 Engine resolution:
  - With `chatgpt_browser` selected, the order is browser → codex → claude_cli → deterministic.
  - With `auto`, the order is keys → claude_cli → codex → deterministic, and auto never picks the browser.
  - A fallback inside one request is recorded in the engine label.
- FR3 Browser request: open a Temporary Chat; paste the prompt (system + user + "Reply with JSON only"); send; wait until
  the reply stops streaming (stop button gone, or 3 s with no text change); read the last assistant message; close the
  tab. Timeout 150 s.
- FR4 Login, challenge and limit detection: login buttons or `auth.openai.com` in the URL, a challenge iframe or title,
  or a usage-limit banner each → `NeedsUser`. Pólya raises the window, broadcasts `engine_attention`, trips a 2-minute
  breaker and falls back. Nothing tries to solve the page.
- FR5 Sign-in flow: `./polya chatgpt-login` and `POST /api/engines/chatgpt-browser/login` launch the Chromium binary
  directly (no automation) on the profile. They refuse while the automated context is open, and close it first.
- FR6 The engine choice persists in prefs.json. Settings shows availability and sign-in state, plus the risk line for the
  browser engine.
- FR7 Privacy and safety: the profile directory is `0700`; prompts and replies are never logged beyond today's artifacts;
  no other browser's data is touched.

## Non-functional requirements
- Requests are serialized. Expect about 10–40 s per request on the browser route. The Codex route is about 8 s per call
  plus ~16k tokens of Plus allowance.
- The public test suite never needs Playwright, a browser or a network: the private engine is tested against a local
  fake chat page.

## Edge cases and failure behaviour
- Google refuses sign-in even in the plain window → Settings says so and suggests adding a password to the OpenAI account,
  or choosing Codex.
- ChatGPT changes its page → `EngineError("layout changed")`, a breaker trips, Codex answers, and Details shows the fallback.
- The window is closed by hand → the next request relaunches it in the background.
- A reply is not JSON → one retry in the same chat ("Return only the JSON object"), then fallback.
- Pólya.app quits → the browser context closes with it.

## Acceptance and verification
- Unit (public):
  - the Codex command line and parsing, using a fake `codex` script on PATH;
  - the resolution order for both modes;
  - fallback after a breaker trips;
  - the provider persisting through prefs.json.
- Private tests, kept in the git-ignored module: the engine against a local fake chat page served by the tests. They
  cover temporary-chat URL handling, streaming completion, login, challenge and limit detection → `NeedsUser`, and the
  layout-change error.
- Live checks (manual, with Nathan):
  - sign in with Google once;
  - a full Learn session on "imitation learning" answered by ChatGPT, with Details showing "chatgpt_browser";
  - nothing new in the ChatGPT sidebar;
  - logging out mid-session → the window comes forward, the request falls back to Codex.
- `make test` and `npm run build` pass. `make bundle` on Nathan's Mac includes the module. `git ls-files` shows no
  `local_engines/chatgpt_browser.py`.

## Decomposition sketch
1. Public: the Codex engine + resolution order + provider persistence + Settings entries + tests (one slice).
2. Public: the optional-engine hook, `engine_attention` event, and toast (small).
3. Private: the browser engine + sign-in command + fake-page tests + local bundle inclusion. Depends on 2.
4. Live check with Nathan (sign-in needs him at the keyboard).
Built by one worker, in order.

## Risks, assumptions, deferred decisions
- **Account risk is the user's, accepted knowingly.** OpenAI's terms forbid automated extraction of output.
- Google may block the sign-in regardless. The workaround is a password on the OpenAI account.
- Temporary Chat availability, the selectors and the limit banners change without notice. Expect maintenance.
- Assumed: Playwright's Chromium (already cached, build 1243) is acceptable to chatgpt.com.
- Deferred: model choice on chatgpt.com, running multiple tabs at once, and the in-ChatGPT connector.
- Also pending: topic-map D1–D3 (docs/specs/topic-map/INTERVIEW.md), needed before the "imitation learning" live check
  is meaningful.
