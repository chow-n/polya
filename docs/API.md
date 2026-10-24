# Pólya API contract (backend :8000, Vite proxies `/api` and `/ws`)

All request/response bodies are the Pydantic models in `backend/models.py` (mirror them exactly in
`frontend/src/types/harness.ts`). JSON field names are snake_case on the wire.

## REST
| Method | Path | Body | Returns |
|---|---|---|---|
| GET | /api/health | – | `{status:"ok", llm_engine:string}` |
| GET | /api/graph | – | GraphOut |
| GET | /api/nodes/{id} | – | NodeDetail |
| GET | /api/stats | – | StatsOut (top-bar pills, Murphy Brier decomposition) |
| GET | /api/due | – | DueItem[] (sorted by next_due_at; desired retention 0.90) |
| GET | /api/practice/queue?limit=12 | – | PracticeQueueItem[] (interleaved priority) |
| GET | /api/sessions | – | SessionOut[] (newest first) |
| POST | /api/sessions | CreateSessionRequest | SessionState |
| GET | /api/sessions/{id} | – | SessionState |
| POST | /api/sessions/{id}/submit | StepSubmission | StepResult (step_id must equal active_step.step_id) |
| POST | /api/sessions/{id}/advance | – | SessionState (READING → next step; READING may also be "submitted" with thinking notes via /submit) |
| POST | /api/sessions/{id}/hint | HintRequest | HintOut (PRACTICE_CHUNK only; rungs unlock in order R0→R4) |
| POST | /api/sessions/{id}/chunk | ChunkRequest | ChunkEvaluation (PRACTICE_CHUNK only) |
| POST | /api/sessions/{id}/duel | DuelRequest | DuelReply (FEYNMAN only) |
| GET | /api/artifacts?session_id=&agent_name=&limit= | – | ArtifactOut[] |
| GET | /api/artifacts/{id} | – | ArtifactOut |
| POST | /api/subagents/{agent_name}/run | SubagentRunRequest | ArtifactOut (manual trigger of any of the 8 agents) |
| GET | /api/workspace/files | – | WorkspaceFile[] (notes/ and problems/) |
| GET | /api/workspace/file?path=notes/x.tex | – | WorkspaceFileContent |
| GET | /api/scratch | – | ScratchOut |
| PUT | /api/scratch | ScratchWrite | ScratchOut |
| POST | /api/demo-telemetry | DemoTelemetry | `{recorded:true, cue_updates:string[]}` |
| GET | /api/settings | – | SettingsOut |
| PUT | /api/settings | SettingsUpdate | SettingsOut (`target_success` ∈ {0.80, 0.85, 0.90}, else 422; persisted in `~/Polya/prefs.json`) |
| GET | /api/model-eval | – | ModelEvalOut (prediction scoreboard + difficulty controller state) |
| POST | /api/engines/chatgpt-browser/login | – | `{opened, message}` (404 unless the private ChatGPT browser engine is installed) |
| GET | /api/papers | – | PaperOut[] (newest first) |
| POST | /api/papers | PaperCreate `{arxiv?, workspace_path?}` | PaperOut (status FETCHING; ingest continues in the background; an arXiv paper already read is returned as is; 422 for anything else) |
| POST | /api/papers/upload?filename=x.pdf | raw PDF bytes (`application/pdf`) | PaperOut (422 if not a PDF, 413 above 60 MB) |
| GET | /api/papers/{id} | – | PaperDetail (map, ideas with roles/anchors/quotes/mastery, sources by direction, links) |
| POST | /api/papers/{id}/sources/refresh | – | PaperDetail (re-ranks references against your misses; fetches citing papers and explainers) |
| POST | /api/papers/{id}/session | – | SessionState (`mode=PROBE`, `sub_mode=PAPER`; resumes the paper's active session; 409 until MAPPED) |

Errors: FastAPI default `{detail: string}` with 4xx.

## Model scoreboard and difficulty controller (docs/specs/model-eval-85)
- Every graded answer (PROBE, CHECK, PRACTICE_CHUNK, REFEREE/FEYNMAN) writes one `model_predictions` row *before* the model
  updates: `p_bkt`, `p_memory` (= R at review), `p_combined`, and the baselines `p_global_baseline` / `p_node_baseline`
  ((k+1)/(n+2) running accuracy), with `y` and `success` (= correct and trace quality ≥ 0.45).
- `ModelEvalOut {n, enough_data (n ≥ 50), min_answers, predictors: [{name, label, baseline, n, log_loss, brier, auc,
  calibration_bins: [{lo, hi, count, mean_predicted, observed}]×5}], controller: {target, recent_success, window_n, band,
  delta, practice_level, last_action, last_summary}}`. `auc` is null when only one outcome has been seen.
- `StepResult.controller` (graded answers outside PROBE): `{action: REMEDIATE|HARDER|EASIER|HOLD|WARMING_UP, summary,
  recent_success, target, window_n, delta, practice_level}`. Recent success = EWMA (α 0.3) over the last 10 graded answers
  across sessions; outside target ± 0.07 it moves Δ ±0.5 and the practice cue level ±1. Hard failures still reset Δ to 0.5
  and splice a remedial step.

## AI engines (docs/specs/chatgpt-engine)
`SettingsOut` adds `codex_available` (Codex CLI installed and signed in) and `chatgpt_browser {available, signed_in,
last_error}`. Providers: `auto | anthropic | gemini | openai | openrouter | claude_cli | codex_cli | chatgpt_browser |
deterministic`; the choice is persisted in `~/Polya/prefs.json` (`POLYA_LLM` overrides it). Each request walks a chain and
falls through on failure; the engine label records the route (`chatgpt_browser->codex_cli`). Automatic: keys → Claude app →
Codex; Codex: Codex → Claude app; ChatGPT browser: browser → Codex → Claude app; then the offline engine.

## Research papers (docs/specs/paper-reading)
- Ingest: arXiv metadata → LaTeX source from `/e-print` (text files only, size-capped, no `..`/links) → `PaperDoc`
  (sections, theorem-like blocks, `\cite` contexts with sections, `.bbl`/`.bib`); else the PDF (pypdf). Files live in
  `~/Polya/workspace/papers/<id>/`. Then the map (AI engine; quotes verified against the paper, unverifiable ones dropped;
  offline: a partial map from theorem blocks) and the sources (Semantic Scholar references/intents/influential, OpenAlex
  citing papers and explainers). Status: FETCHING → PARSED → MAPPED (or FAILED with the reason).
- `PaperDetail.map {summary, contributions[], notation[{symbol_latex, meaning}], key_argument {claim, steps[]}|null,
  quotes_dropped}`; `ideas[{node_id, title, role: prerequisite|definition|assumption|claim|main_result, anchor, quote,
  mastery, answered}]`; `sources {reference[], citation[], explainer[]}` of PaperSourceOut `{title, year, url, arxiv_id,
  contexts[{sentence, section}], sections[], influential, intents[], cited_by_count, is_survey, for_node_id, score, why}`.
- Reference score = Σ over (≤6) citing sentences of the section weight (method/theory/proof 3, results/experiments 2,
  intro/background 1, related work 0.5, other 1.5) + 2 if influential + 3 if cited in a section anchoring an idea you
  missed (answered, P(L) < 0.5). `understanding` = mean P(L) over the paper's non-prerequisite ideas.
- Paper session: PREDICT (skim: abstract + sections; the guess is kept as `first_guess`) → PROBE on prerequisites (EIG) →
  PREDICT → READING → CHECK per idea (prompts carry the anchored passage; readings quote the paper and flag quotes not
  found in it) → REFEREE on the paper's key argument with one planted flaw → FEYNMAN on the main result's assumptions →
  COMPLETE (title "Paper complete": first guess vs contributions, understanding, read-next list). Sources re-rank in the
  background when it completes.

## Step flow by mode (StepPayload.kind)
- PROBE: PROBE×(≤4, chosen by EIG; `eig_table` filled, `options_locked=true`) → per unmastered plan node: PREDICT → READING → CHECK → … → COMPLETE
- PRODUCTIVE_FAILURE: PRODUCTIVE_FAILURE (open problem, no options) → PREDICT → READING → CHECK … → COMPLETE
- TEACH: PREDICT → READING → CHECK per plan node → COMPLETE
- PRACTICE: PRACTICE_CHUNK per queued node (chunks via /chunk, hints via /hint, final via /submit) → COMPLETE
- REFEREE_DUEL / PROOF_REFEREE: REFEREE (`proof_steps`, submit `flagged_step_index` + explanation + counterexample) → COMPLETE
- REFEREE_DUEL / FEYNMAN_STUDENT: FEYNMAN (chat via /duel until `resolved`, then /submit) → COMPLETE

Law 3: any step with `options_locked=true` must collect ≥15 chars of raw prediction before showing options;
the client sends `raw_prediction_locked` + `raw_prediction_locked_at_ms` in the submission.

## WebSocket `/ws`
Server → client `WsEvent {type, payload, ts}`:
- `hello` `{llm_engine}` · `subagent_status` SubagentStatus · `artifact` ArtifactOut · `scratch_update` ScratchOut
- `graph_updated` `{reason}` · `session_updated` `{session_id}` · `stats` StatsOut · `notes_changed` `{path}` · `pong` · `error` `{message}`
- `paper_progress` `{paper_id, status, detail}` · `engine_attention` `{engine, reason}` (an engine needs the user: sign in, a
  "verify you are human" page, a usage limit; that request already fell through to the next engine)
Client → server: `{type:"ping"}`, `{type:"scratch_write", content}`.

## WebSocket `/ws/dictation` (Deepgram relay / on-device macOS speech)
Engine priority: `DEEPGRAM_API_KEY` set → Deepgram `nova-3` relay; else inside Pólya.app
(`POLYA_APP=1`) → on-device `SFSpeechRecognizer` (asks for speech + microphone permission once);
else `{type:"unavailable", reason}` and close, and the client uses browser SpeechRecognition.
- First frame on success: `{type:"ready", engine:"deepgram"|"native"}`.
- Then `{type:"transcript", text, is_final, words:[{word,start,end}]}`; interim frames replace the current
  segment, final frames commit it.
- Client → server: binary audio chunks (MediaRecorder; Deepgram only, ignored by the native engine), or `"close"`.
- `GET /api/settings` reports `deepgram_available` and `native_dictation_available`.
