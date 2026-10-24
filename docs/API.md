# LearnHarness API contract (backend :8000, Vite proxies `/api` and `/ws`)

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
| PUT | /api/settings | SettingsUpdate | SettingsOut |

Errors: FastAPI default `{detail: string}` with 4xx.

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
Client → server: `{type:"ping"}`, `{type:"scratch_write", content}`.

## WebSocket `/ws/dictation` (Deepgram relay / on-device macOS speech)
Engine priority: `DEEPGRAM_API_KEY` set → Deepgram `nova-3` relay; else inside LearnHarness.app
(`LEARNHARNESS_APP=1`) → on-device `SFSpeechRecognizer` (asks for speech + microphone permission once);
else `{type:"unavailable", reason}` and close, and the client uses browser SpeechRecognition.
- First frame on success: `{type:"ready", engine:"deepgram"|"native"}`.
- Then `{type:"transcript", text, is_final, words:[{word,start,end}]}`; interim frames replace the current
  segment, final frames commit it.
- Client → server: binary audio chunks (MediaRecorder; Deepgram only, ignored by the native engine), or `"close"`.
- `GET /api/settings` reports `deepgram_available` and `native_dictation_available`.
