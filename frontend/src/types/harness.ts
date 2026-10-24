/**
 * Exact TypeScript mirrors of backend/models.py (Pydantic v2). snake_case on the wire.
 *
 * Conventions:
 *  - Response models: every field is present (Pydantic serialises defaults), `Optional[X] = None` -> `X | null`.
 *  - Request models (CreateSessionRequest, StepSubmission, HintRequest, ChunkRequest, DuelRequest,
 *    SubagentRunRequest, ScratchWrite, DemoTelemetry, SettingsUpdate): fields with a server default are optional (`?`).
 */

// ------------------------------------------------------------------ literals
export type NodeType = 'AXIOM' | 'PROPOSITION' | 'MOVE' | 'COUNTEREXAMPLE' | 'INTUITION' | 'BUGGY_RULE';
export type EdgeType = 'DEDUCTION' | 'CONTRASTIVE' | 'ISOMORPHISM' | 'CUE_TRIGGER';
export type SessionMode = 'PROBE' | 'PRODUCTIVE_FAILURE' | 'TEACH' | 'PRACTICE' | 'REFEREE_DUEL';
export type SubMode = 'STANDARD' | 'PROOF_REFEREE' | 'FEYNMAN_STUDENT' | 'PAPER';
export type Phase = 'PROBE' | 'PRODUCTIVE_FAILURE' | 'PREDICT' | 'READING' | 'CHECK' | 'PRACTICE_CHUNK' | 'REFEREE';
export type StepKind =
  | 'PROBE'
  | 'PRODUCTIVE_FAILURE'
  | 'PREDICT'
  | 'READING'
  | 'CHECK'
  | 'PRACTICE_CHUNK'
  | 'REFEREE'
  | 'FEYNMAN'
  | 'COMPLETE';
export type Outcome =
  | 'SOLVED_CLEAN'
  | 'SOLVED_WITH_HINTS'
  | 'PARTIAL'
  | 'FAILED'
  | 'HIGH_CONFIDENCE_ERROR'
  | 'EXPLORATION_LOGGED';
export type HintRung = 'NONE' | 'R0' | 'R1' | 'R2' | 'R3' | 'R4';
export type LadderRung = Exclude<HintRung, 'NONE'>;
export type MissClass =
  | 'NONE'
  | 'ALGEBRAIC_SLIP'
  | 'NOTATION_OBSTRUCTION'
  | 'MISSING_PREREQUISITE'
  | 'BOUNDARY_OMISSION'
  | 'FALSE_ANALOGY'
  | 'CUE_BLINDNESS';
export type AgentName =
  | 'SYMBOLIC_VERIFIER'
  | 'BUG_LIBRARY_DIAGNOSTICIAN'
  | 'COUNTEREXAMPLE_SYNTHESIZER'
  | 'SANDBOX_DEMO_BUILDER'
  | 'SVG_DIAGRAM_MAKER'
  | 'LOCAL_CORPUS_RAG'
  | 'LITERATURE_RESEARCHER'
  | 'ONTOLOGIST_EXTRACTOR';
export type ArtifactStatus = 'RUNNING' | 'COMPLETED' | 'FAILED';
export type ContentType = 'sympy_log' | 'svg' | 'html_demo' | 'json_diagnosis' | 'rag_excerpt' | 'graph_diff';
export type CueDimension =
  | 'cue_symbolic'
  | 'cue_disguised_notation'
  | 'cue_geometric'
  | 'cue_computational'
  | 'cue_adversarial';
export type PlanStatus = 'pending' | 'active' | 'done' | 'probed_mastered' | 'probed_unmastered' | 'skipped';

export const ALL_AGENTS: AgentName[] = [
  'SYMBOLIC_VERIFIER',
  'BUG_LIBRARY_DIAGNOSTICIAN',
  'COUNTEREXAMPLE_SYNTHESIZER',
  'SANDBOX_DEMO_BUILDER',
  'SVG_DIAGRAM_MAKER',
  'LOCAL_CORPUS_RAG',
  'LITERATURE_RESEARCHER',
  'ONTOLOGIST_EXTRACTOR',
];

export const CUE_DIMENSIONS: CueDimension[] = [
  'cue_symbolic',
  'cue_disguised_notation',
  'cue_geometric',
  'cue_computational',
  'cue_adversarial',
];

// ------------------------------------------------------------------ graph
export interface CueVector {
  cue_symbolic: number;
  cue_disguised_notation: number;
  cue_geometric: number;
  cue_computational: number;
  cue_adversarial: number;
}

export interface NodeOut {
  id: string;
  title: string;
  node_type: NodeType;
  statement_latex: string;
  intuition_summary: string;
  formal_proof_sketch_latex: string;
  domain_cluster: string;
  logical_depth: number;
  bkt_p_mastery: number;
  bkt_p_transit: number;
  bkt_p_slip: number;
  bkt_p_guess: number;
  fsrs_stability: number;
  fsrs_difficulty: number;
  fsrs_reps: number;
  fsrs_lapses: number;
  last_reviewed_at: string;
  cues: CueVector;
  brier_sum: number;
  brier_count: number;
  hypercorrection_flag: number;
  last_miss_class: string;
  created_in_session_id: string | null;
  updated_at: string;
  // derived on read
  retrievability: number;
  in_bjork_window: boolean;
  next_due_at: string;
  days_until_due: number;
  cue_mean: number;
  mean_brier: number | null;
}

export interface HyperedgeOut {
  id: string;
  edge_type: EdgeType;
  premise_node_ids: string[];
  conclusion_node_id: string;
  reasoning_chain_latex: string;
  discriminating_condition_latex: string;
  edge_mastery: number;
  session_id: string | null;
  created_at: string;
}

export interface GraphOut {
  nodes: NodeOut[];
  hyperedges: HyperedgeOut[];
}

export interface NodeDetail {
  node: NodeOut;
  incoming: HyperedgeOut[];
  outgoing: HyperedgeOut[];
  contrastive_peers: string[];
  buggy_rule_links: string[];
  ancestors: string[];
  descendants: string[];
  traces: TraceOut[];
}

// ------------------------------------------------------------------ telemetry
export interface ProsodyMetrics {
  initial_latency_ms: number;
  total_silence_ms: number;
  hesitation_count: number;
  hedge_count: number;
  wpm: number;
  hedge_density: number;
  engine: 'none' | 'browser' | 'deepgram' | 'native';
}

export interface ReadingNote {
  quote: string;
  thought: string;
  timestamp_ms: number;
}

export interface TraceOut {
  id: string;
  session_id: string;
  step_index: number;
  phase: Phase;
  target_node_ids: string[];
  cue_level: number;
  prompt_shown_latex: string;
  options: unknown[];
  raw_prediction_locked: string;
  thinking_while_reading: ReadingNote[];
  verification_thinking: string;
  selected_answer: string;
  confidence_slider: number;
  prosody_metrics: ProsodyMetrics;
  is_correct: number;
  trace_quality_score: number;
  outcome: Outcome;
  max_hint_rung: HintRung;
  miss_class: MissClass;
  ai_diagnosis_markdown: string;
  brier_score: number;
  bkt_mastery_before: number;
  bkt_mastery_after: number;
  fsrs_stability_before: number;
  fsrs_stability_after: number;
  created_at: string;
}

// ------------------------------------------------------------------ sessions & steps
export interface PlanItem {
  node_id: string;
  title: string;
  depth: number;
  status: PlanStatus;
  remedial: boolean;
  spliced_reason: string;
}

export interface StepOption {
  id: string;
  label_latex: string;
}

export interface ProofStep {
  index: number;
  text_latex: string;
}

export interface EIGRow {
  node_id: string;
  title: string;
  p_mastery: number;
  entropy: number;
  unprobed_ancestors: number;
  unprobed_descendants: number;
  eig: number;
}

export interface DuelTurn {
  role: 'student' | 'learner';
  text: string;
  timestamp_ms: number;
}

export interface StepPayload {
  step_id: string;
  step_index: number;
  kind: StepKind;
  phase: Phase | null;
  target_node_ids: string[];
  cue_level: number;
  title: string;
  prompt_latex: string;
  body_markdown: string;
  options: StepOption[];
  options_locked: boolean;
  requires_raw_prediction: boolean;
  proof_steps: ProofStep[];
  student_persona: string;
  buggy_rule_id: string | null;
  duel_transcript: DuelTurn[];
  boundary_conditions_total: number;
  boundary_conditions_met: string[];
  demo_artifact_id: string | null;
  svg_artifact_id: string | null;
  eig_table: EIGRow[];
  rationale: string;
  delta: number;
  hints_unlocked: HintOut[];
  chunks: ChunkEvaluation[];
  contrastive_pair_node_id: string | null;
  generated_by: string;
}

export interface SessionOut {
  id: string;
  title: string;
  mode: SessionMode;
  sub_mode: SubMode;
  target_goal: string;
  attached_files: string[];
  step_velocity_delta: number;
  current_step_index: number;
  dependency_plan: PlanItem[];
  history_steps: Record<string, unknown>[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SessionState {
  session: SessionOut;
  active_step: StepPayload;
  traces: TraceOut[];
}

export interface CreateSessionRequest {
  mode: SessionMode;
  sub_mode?: SubMode;
  target_goal: string;
  title?: string | null;
  attached_files?: string[];
  target_node_id?: string | null;
  cue_level?: number;
  contrastive_pair?: boolean;
  problem_file?: string | null;
}

export interface StepSubmission {
  step_id: string;
  raw_prediction_locked?: string;
  raw_prediction_locked_at_ms?: number;
  thinking_while_reading?: ReadingNote[];
  verification_thinking?: string;
  selected_answer?: string;
  confidence?: number;
  prosody?: ProsodyMetrics;
  flagged_step_index?: number | null;
  counterexample_text?: string;
}

export interface NodeUpdate {
  node_id: string;
  title: string;
  rating: number;
  bkt_before: number;
  bkt_after: number;
  stability_before: number;
  stability_after: number;
  difficulty_after: number;
  retrievability_at_review: number;
  hypercorrection_flag: number;
  hypercorrection_bonus_applied: boolean;
  cue_dimension: CueDimension | null;
  propagated_to: string[];
}

export interface StepResult {
  trace: TraceOut;
  feedback_markdown: string;
  node_updates: NodeUpdate[];
  delta_before: number;
  delta_after: number;
  remedial_spliced: string | null;
  created_nodes: string[];
  state: SessionState;
  controller?: ControllerReading | null;
}

/** The success-rate difficulty controller's reading after a graded answer (docs/specs/model-eval-85). */
export interface ControllerReading {
  action: 'REMEDIATE' | 'HARDER' | 'EASIER' | 'HOLD' | 'WARMING_UP';
  summary: string;
  recent_success: number | null;
  target: number;
  window_n: number;
  delta: number;
  practice_level: number;
}

export interface CalibrationBin {
  lo: number;
  hi: number;
  count: number;
  mean_predicted: number | null;
  observed: number | null;
}

export interface PredictorScore {
  name: string;
  label: string;
  baseline: boolean;
  n: number;
  log_loss: number | null;
  brier: number | null;
  auc: number | null;
  calibration_bins: CalibrationBin[];
}

export interface ModelEvalOut {
  n: number;
  enough_data: boolean;
  min_answers: number;
  predictors: PredictorScore[];
  controller: {
    target: number;
    recent_success: number | null;
    window_n: number;
    band: number;
    delta: number | null;
    practice_level: number | null;
    last_action: string | null;
    last_summary: string | null;
  };
}

export interface HintRequest {
  rung: LadderRung;
  current_thinking?: string;
}

export interface HintOut {
  rung: LadderRung;
  label: string;
  hint_markdown: string;
  fsrs_rating_cap: number;
  stability_multiplier: number;
}

export interface ChunkRequest {
  text: string;
  confidence?: number;
}

export interface ChunkEvaluation {
  chunk_index: number;
  text: string;
  demand_satisfied: boolean;
  slip_detected: boolean;
  quality_estimate: number;
  feedback_markdown: string;
  matched_concepts: string[];
  missing_concepts: string[];
  verifier_summary: string;
}

export interface DuelRequest {
  message: string;
}

export interface DuelReply {
  student_message: string;
  boundary_conditions_met: string[];
  boundary_conditions_remaining: number;
  resolved: boolean;
}

// ------------------------------------------------------------------ practice / stats
export interface PracticeQueueItem {
  node_id: string;
  title: string;
  domain_cluster: string;
  score: number;
  retrievability: number;
  bjork_component: number;
  forgetting_component: number;
  cue_gap_component: number;
  hypercorrection_component: number;
  interleave_penalty: number;
}

export interface CalibrationBin {
  confidence_mid: number;
  mean_confidence: number;
  accuracy: number;
  count: number;
}

export interface CalibrationOut {
  n: number;
  mean_brier: number | null;
  reliability: number;
  resolution: number;
  uncertainty: number;
  mean_confidence: number;
  accuracy: number;
  overconfidence: number;
  label: 'NO_DATA' | 'WELL_CALIBRATED' | 'OVERCONFIDENT' | 'UNDERCONFIDENT';
  bins: CalibrationBin[];
}

export interface StatsOut {
  total_nodes: number;
  total_hyperedges: number;
  bjork_window_count: number;
  hypercorrection_count: number;
  due_count: number;
  mean_mastery: number;
  calibration: CalibrationOut;
  llm_engine: string;
  scratch_synced_at: string | null;
}

export interface DueItem {
  node_id: string;
  title: string;
  retrievability: number;
  stability: number;
  next_due_at: string;
  days_until_due: number;
}

// ------------------------------------------------------------------ artifacts, workspace, settings
export interface ArtifactOut {
  id: string;
  session_id: string | null;
  agent_name: AgentName;
  status: ArtifactStatus;
  title: string;
  content_type: ContentType;
  payload_text: string;
  created_at: string;
}

export interface SubagentRunRequest {
  session_id?: string | null;
  topic?: string;
  node_id?: string | null;
  pattern?: string;
  filename?: string;
  code?: string;
}

export interface WorkspaceFile {
  path: string;
  kind: 'tex' | 'md' | 'pdf' | 'other';
  size: number;
  modified_at: string;
}

export interface TexBlock {
  env: string;
  title: string;
  body: string;
  line: number;
}

export interface WorkspaceFileContent {
  path: string;
  content: string;
  blocks: TexBlock[];
}

export interface ScratchOut {
  content: string;
  modified_at: string | null;
  path: string;
}

export interface ScratchWrite {
  content: string;
}

export interface DemoTelemetry {
  demo_id: string;
  session_id?: string | null;
  params?: Record<string, unknown>;
  challenge_solved?: boolean;
  summary?: string;
}

export interface DemoTelemetryAck {
  recorded: boolean;
  cue_updates: string[];
}

export type LLMProvider =
  | 'auto'
  | 'anthropic'
  | 'gemini'
  | 'openai'
  | 'openrouter'
  | 'claude_cli'
  | 'codex_cli'
  | 'chatgpt_browser'
  | 'deterministic';

export const LLM_PROVIDERS: LLMProvider[] = [
  'auto',
  'anthropic',
  'gemini',
  'openai',
  'openrouter',
  'claude_cli',
  'codex_cli',
  'chatgpt_browser',
  'deterministic',
];

/** The private ChatGPT browser engine (present only on its owner's Mac). */
export interface ChatGPTBrowserStatus {
  available: boolean;
  signed_in: boolean | null;
  last_error: string | null;
}

export interface SettingsOut {
  provider: LLMProvider;
  active_engine: string;
  keys_present: Record<string, boolean>;
  deepgram_available: boolean;
  native_dictation_available: boolean; // on-device macOS speech, Pólya.app only
  claude_cli_available: boolean;
  codex_available: boolean; // `codex` installed and signed in with a ChatGPT plan
  chatgpt_browser: ChatGPTBrowserStatus;
  model_overrides: Record<string, string>;
  target_success: number; // difficulty target, persisted in ~/Polya/prefs.json
}

export const TARGET_CHOICES = [0.8, 0.85, 0.9] as const;

export interface SettingsUpdate {
  provider?: LLMProvider | null;
  anthropic_api_key?: string | null;
  gemini_api_key?: string | null;
  openai_api_key?: string | null;
  openrouter_api_key?: string | null;
  deepgram_api_key?: string | null;
  model_overrides?: Record<string, string> | null;
  target_success?: number | null;
}

export interface HealthOut {
  status: string;
  llm_engine: string;
}

// ------------------------------------------------------------------ websocket
export type WsEventType =
  | 'hello'
  | 'subagent_status'
  | 'artifact'
  | 'scratch_update'
  | 'graph_updated'
  | 'session_updated'
  | 'stats'
  | 'notes_changed'
  | 'pong'
  | 'engine_attention'
  | 'paper_progress'
  | 'error';

export interface WsEvent {
  type: WsEventType;
  payload: Record<string, unknown>;
  ts: string;
}

export interface SubagentStatus {
  agent_name: AgentName;
  state: 'IDLE' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  message: string;
  artifact_id: string | null;
  session_id: string | null;
}

/** Typed payloads for each server -> client WsEvent (API.md). */
export interface WsPayloads {
  hello: { llm_engine: string };
  subagent_status: SubagentStatus;
  artifact: ArtifactOut;
  scratch_update: ScratchOut;
  graph_updated: { reason: string };
  session_updated: { session_id: string };
  stats: StatsOut;
  notes_changed: { path: string };
  pong: Record<string, unknown>;
  engine_attention: { engine: string; reason: string };
  paper_progress: { paper_id: string; status: PaperStatus; detail: string };
  error: { message: string };
}

/** Client -> server WebSocket messages. */
export type WsClientMessage = { type: 'ping' } | { type: 'scratch_write'; content: string };

/** /ws/dictation server messages. */
export type DictationMessage =
  | { type: 'transcript'; text: string; is_final: boolean; words: { word: string; start: number; end: number }[] }
  | { type: 'ready'; engine: 'deepgram' | 'native' }
  | { type: 'unavailable'; reason?: string };

// ------------------------------------------------------------------ structured LLM I/O (mirrored for completeness)
export interface LLMStepContent {
  title: string;
  prompt_latex: string;
  body_markdown: string;
  options: StepOption[];
  correct_option_id: string;
  rationale: string;
}

export interface LLMDiagnosis {
  is_correct: boolean;
  trace_quality_score: number;
  miss_class: MissClass;
  right_for_wrong_reason: boolean;
  diagnosis_markdown: string;
  buggy_rule_statement: string;
}

export interface LLMOntology {
  nodes: Record<string, unknown>[];
  hyperedges: Record<string, unknown>[];
}

// ------------------------------------------------------------------ research papers (docs/specs/paper-reading)
export type PaperStatus = 'FETCHING' | 'PARSED' | 'MAPPED' | 'FAILED';
export type PaperRole = 'prerequisite' | 'definition' | 'assumption' | 'claim' | 'main_result';

export interface PaperCreate {
  arxiv?: string | null; // an arXiv link or id
  workspace_path?: string | null; // a PDF already in your notes
}

export interface PaperOut {
  id: string;
  source: string;
  arxiv_id: string;
  doi: string;
  title: string;
  authors: string[];
  year: number | null;
  abstract: string;
  text_kind: string;
  status: PaperStatus;
  status_detail: string;
  map_engine: string;
  session_id: string | null;
  first_guess: string;
  understanding: number | null; // mean mastery over the paper's own ideas
  idea_count: number;
  partial_map: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaperIdeaOut {
  node_id: string;
  title: string;
  role: PaperRole;
  anchor: string;
  quote: string;
  mastery: number;
  answered: boolean;
  node_type: NodeType;
}

export interface PaperSourceOut {
  id: string;
  direction: 'reference' | 'citation' | 'explainer';
  ref_key: string;
  title: string;
  authors: string;
  year: number | null;
  arxiv_id: string;
  doi: string;
  s2_id: string;
  url: string;
  contexts: { sentence: string; section: string }[];
  sections: string[];
  influential: boolean;
  intents: string[];
  cited_by_count: number | null;
  is_survey: boolean;
  for_node_id: string;
  score: number;
  why: string;
}

export interface PaperDetail extends PaperOut {
  map: {
    summary: string;
    contributions: string[];
    notation: { symbol_latex: string; meaning: string; existing_node_id?: string }[];
    key_argument: { claim: string; steps: string[] } | null;
    quotes_dropped: number;
  };
  ideas: PaperIdeaOut[];
  sources: { reference: PaperSourceOut[]; citation: PaperSourceOut[]; explainer: PaperSourceOut[] };
  links: { arxiv: string | null; pdf: string | null; code: string | null; semantic_scholar: string | null };
}
