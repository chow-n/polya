"""Pydantic v2 schemas for the REST API, the WebSocket hub and structured LLM I/O.

Every model here is mirrored 1:1 in frontend/src/types/harness.ts.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

NodeType = Literal["AXIOM", "PROPOSITION", "MOVE", "COUNTEREXAMPLE", "INTUITION", "BUGGY_RULE"]
EdgeType = Literal["DEDUCTION", "CONTRASTIVE", "ISOMORPHISM", "CUE_TRIGGER"]
SessionMode = Literal["PROBE", "PRODUCTIVE_FAILURE", "TEACH", "PRACTICE", "REFEREE_DUEL"]
SubMode = Literal["STANDARD", "PROOF_REFEREE", "FEYNMAN_STUDENT", "PAPER"]   # PAPER: docs/specs/paper-reading
Phase = Literal["PROBE", "PRODUCTIVE_FAILURE", "PREDICT", "READING", "CHECK", "PRACTICE_CHUNK", "REFEREE"]
StepKind = Literal[
    "PROBE", "PRODUCTIVE_FAILURE", "PREDICT", "READING", "CHECK", "PRACTICE_CHUNK", "REFEREE", "FEYNMAN", "LEARN", "COMPLETE"
]
Outcome = Literal["SOLVED_CLEAN", "SOLVED_WITH_HINTS", "PARTIAL", "FAILED", "HIGH_CONFIDENCE_ERROR", "EXPLORATION_LOGGED"]
HintRung = Literal["NONE", "R0", "R1", "R2", "R3", "R4"]
MissClass = Literal[
    "NONE", "ALGEBRAIC_SLIP", "NOTATION_OBSTRUCTION", "MISSING_PREREQUISITE",
    "BOUNDARY_OMISSION", "FALSE_ANALOGY", "CUE_BLINDNESS",
]
AgentName = Literal[
    "SYMBOLIC_VERIFIER", "BUG_LIBRARY_DIAGNOSTICIAN", "COUNTEREXAMPLE_SYNTHESIZER",
    "SANDBOX_DEMO_BUILDER", "SVG_DIAGRAM_MAKER", "LOCAL_CORPUS_RAG",
    "LITERATURE_RESEARCHER", "ONTOLOGIST_EXTRACTOR",
]
ArtifactStatus = Literal["RUNNING", "COMPLETED", "FAILED"]
ContentType = Literal["sympy_log", "svg", "html_demo", "json_diagnosis", "rag_excerpt", "graph_diff"]
CueDimension = Literal["cue_symbolic", "cue_disguised_notation", "cue_geometric", "cue_computational", "cue_adversarial"]
PlanStatus = Literal["pending", "active", "done", "probed_mastered", "probed_unmastered", "skipped"]

ALL_AGENTS: list[str] = [
    "SYMBOLIC_VERIFIER", "BUG_LIBRARY_DIAGNOSTICIAN", "COUNTEREXAMPLE_SYNTHESIZER",
    "SANDBOX_DEMO_BUILDER", "SVG_DIAGRAM_MAKER", "LOCAL_CORPUS_RAG",
    "LITERATURE_RESEARCHER", "ONTOLOGIST_EXTRACTOR",
]


# ---------------------------------------------------------------- graph
class CueVector(BaseModel):
    cue_symbolic: float = 0.0
    cue_disguised_notation: float = 0.0
    cue_geometric: float = 0.0
    cue_computational: float = 0.0
    cue_adversarial: float = 0.0


class NodeOut(BaseModel):
    id: str
    title: str
    node_type: NodeType
    statement_latex: str
    intuition_summary: str
    formal_proof_sketch_latex: str
    domain_cluster: str
    logical_depth: int
    bkt_p_mastery: float
    bkt_p_transit: float
    bkt_p_slip: float
    bkt_p_guess: float
    fsrs_stability: float
    fsrs_difficulty: float
    fsrs_reps: int
    fsrs_lapses: int
    last_reviewed_at: str
    cues: CueVector
    brier_sum: float
    brier_count: int
    hypercorrection_flag: int
    last_miss_class: str
    created_in_session_id: Optional[str] = None
    updated_at: str
    # derived on read
    retrievability: float
    in_bjork_window: bool
    next_due_at: str
    days_until_due: float
    cue_mean: float
    mean_brier: Optional[float] = None


class HyperedgeOut(BaseModel):
    id: str
    edge_type: EdgeType
    premise_node_ids: list[str]
    conclusion_node_id: str
    reasoning_chain_latex: str
    discriminating_condition_latex: str
    edge_mastery: float
    session_id: Optional[str] = None
    created_at: str


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    hyperedges: list[HyperedgeOut]


class NodeDetail(BaseModel):
    node: NodeOut
    incoming: list[HyperedgeOut]       # edges whose conclusion is this node
    outgoing: list[HyperedgeOut]       # edges where this node is a premise
    contrastive_peers: list[str]
    buggy_rule_links: list[str]        # BUGGY_RULE nodes attached via CONTRASTIVE edges
    ancestors: list[str]
    descendants: list[str]
    traces: list["TraceOut"]


# ---------------------------------------------------------------- telemetry
class ProsodyMetrics(BaseModel):
    initial_latency_ms: float = 0
    total_silence_ms: float = 0
    hesitation_count: int = 0
    hedge_count: int = 0
    wpm: float = 0
    hedge_density: float = 0.0
    engine: Literal["none", "browser", "deepgram", "native"] = "none"


class ReadingNote(BaseModel):
    quote: str = ""
    thought: str
    timestamp_ms: float = 0


class TraceOut(BaseModel):
    id: str
    session_id: str
    step_index: int
    phase: Phase
    target_node_ids: list[str]
    cue_level: int
    prompt_shown_latex: str
    options: list[Any]
    raw_prediction_locked: str
    thinking_while_reading: list[ReadingNote]
    verification_thinking: str
    selected_answer: str
    confidence_slider: float
    prosody_metrics: ProsodyMetrics
    is_correct: int
    trace_quality_score: float
    outcome: Outcome
    max_hint_rung: HintRung
    miss_class: MissClass
    ai_diagnosis_markdown: str
    brier_score: float
    bkt_mastery_before: float
    bkt_mastery_after: float
    fsrs_stability_before: float
    fsrs_stability_after: float
    created_at: str


# ---------------------------------------------------------------- sessions & steps
class PlanItem(BaseModel):
    node_id: str
    title: str
    depth: int
    status: PlanStatus = "pending"
    remedial: bool = False
    spliced_reason: str = ""


class StepOption(BaseModel):
    id: str
    label_latex: str


class ProofStep(BaseModel):
    index: int
    text_latex: str


class EIGRow(BaseModel):
    node_id: str
    title: str
    p_mastery: float
    entropy: float
    unprobed_ancestors: int
    unprobed_descendants: int
    eig: float


class DuelTurn(BaseModel):
    role: Literal["student", "learner"]
    text: str
    timestamp_ms: float = 0


class LearnIdea(BaseModel):
    node_id: str
    title: str
    p_recall: float                        # P(L)(1−s) + (1−P(L))g: predicted chance of recalling it now
    status: Literal["todo", "current", "covered", "moved_on"] = "todo"


class StepPayload(BaseModel):
    step_id: str
    step_index: int
    kind: StepKind
    phase: Optional[Phase] = None
    target_node_ids: list[str] = Field(default_factory=list)
    cue_level: int = 1
    title: str = ""
    prompt_latex: str = ""                 # markdown + $..$ / $$..$$ math
    body_markdown: str = ""                # READING explanation (<=180 words)
    options: list[StepOption] = Field(default_factory=list)
    options_locked: bool = False           # Law 3
    requires_raw_prediction: bool = False
    proof_steps: list[ProofStep] = Field(default_factory=list)
    student_persona: str = ""
    buggy_rule_id: Optional[str] = None
    duel_transcript: list[DuelTurn] = Field(default_factory=list)
    boundary_conditions_total: int = 0
    boundary_conditions_met: list[str] = Field(default_factory=list)
    demo_artifact_id: Optional[str] = None
    svg_artifact_id: Optional[str] = None
    eig_table: list[EIGRow] = Field(default_factory=list)
    rationale: str = ""                    # why this step was chosen (EIG, Bjork window, remediation)
    delta: float = 1.0
    hints_unlocked: list["HintOut"] = Field(default_factory=list)
    chunks: list["ChunkEvaluation"] = Field(default_factory=list)
    contrastive_pair_node_id: Optional[str] = None
    generated_by: str = "deterministic"    # engine name
    learn_ideas: list[LearnIdea] = Field(default_factory=list)   # LEARN steps (docs/specs/learn-chat)


class SessionOut(BaseModel):
    id: str
    title: str
    mode: SessionMode
    sub_mode: SubMode
    target_goal: str
    attached_files: list[str]
    step_velocity_delta: float
    current_step_index: int
    dependency_plan: list[PlanItem]
    history_steps: list[dict[str, Any]]
    status: str
    created_at: str
    updated_at: str


class SessionState(BaseModel):
    session: SessionOut
    active_step: StepPayload
    traces: list[TraceOut]
    stuck_after_ms: int = 120_000          # docs/specs/explain FR3: offer a nudge after this long on a graded card


class CreateSessionRequest(BaseModel):
    mode: SessionMode
    sub_mode: SubMode = "STANDARD"
    target_goal: str
    title: Optional[str] = None
    attached_files: list[str] = Field(default_factory=list)
    target_node_id: Optional[str] = None
    cue_level: int = 1
    contrastive_pair: bool = False
    problem_file: Optional[str] = None


class StepSubmission(BaseModel):
    step_id: str
    raw_prediction_locked: str = ""
    raw_prediction_locked_at_ms: float = 0
    thinking_while_reading: list[ReadingNote] = Field(default_factory=list)
    verification_thinking: str = ""
    selected_answer: str = ""
    confidence: float = 0.5
    prosody: ProsodyMetrics = Field(default_factory=ProsodyMetrics)
    flagged_step_index: Optional[int] = None    # PROOF_REFEREE
    counterexample_text: str = ""               # PROOF_REFEREE
    elapsed_ms: float = 0                       # card shown → submit (docs/specs/explain FR3)


class NodeUpdate(BaseModel):
    node_id: str
    title: str
    rating: int
    bkt_before: float
    bkt_after: float
    stability_before: float
    stability_after: float
    difficulty_after: float
    retrievability_at_review: float
    hypercorrection_flag: int
    hypercorrection_bonus_applied: bool
    cue_dimension: Optional[CueDimension] = None
    propagated_to: list[str] = Field(default_factory=list)


class ControllerReadingOut(BaseModel):
    """The success-rate difficulty controller's reading after a graded answer (docs/specs/model-eval-85)."""
    action: Literal["REMEDIATE", "HARDER", "EASIER", "HOLD", "WARMING_UP"]
    summary: str
    recent_success: Optional[float] = None
    target: float
    window_n: int
    delta: float
    practice_level: int


class StepResult(BaseModel):
    trace: TraceOut
    feedback_markdown: str
    node_updates: list[NodeUpdate]
    delta_before: float
    delta_after: float
    remedial_spliced: Optional[str] = None
    created_nodes: list[str] = Field(default_factory=list)
    state: SessionState
    controller: Optional[ControllerReadingOut] = None
    offer: Optional["Offer"] = None             # docs/specs/explain FR3


class HintRequest(BaseModel):
    rung: Literal["R0", "R1", "R2", "R3", "R4"]
    current_thinking: str = ""


class HintOut(BaseModel):
    rung: Literal["R0", "R1", "R2", "R3", "R4"]
    label: str
    hint_markdown: str
    fsrs_rating_cap: int            # best FSRS rating still reachable after this rung
    stability_multiplier: float     # m_G of that rating cap


class ChunkRequest(BaseModel):
    text: str
    confidence: float = 0.5


class ChunkEvaluation(BaseModel):
    chunk_index: int
    text: str
    demand_satisfied: bool
    slip_detected: bool
    quality_estimate: float
    feedback_markdown: str
    matched_concepts: list[str]
    missing_concepts: list[str]
    verifier_summary: str = ""


class DuelRequest(BaseModel):
    message: str


class DuelReply(BaseModel):
    student_message: str
    boundary_conditions_met: list[str]
    boundary_conditions_remaining: int
    resolved: bool


# ---------------------------------------------------------------- practice / stats
class PracticeQueueItem(BaseModel):
    node_id: str
    title: str
    domain_cluster: str
    score: float
    retrievability: float
    bjork_component: float
    forgetting_component: float
    cue_gap_component: float
    hypercorrection_component: float
    interleave_penalty: float


class CalibrationBin(BaseModel):
    confidence_mid: float
    mean_confidence: float
    accuracy: float
    count: int


class CalibrationOut(BaseModel):
    n: int
    mean_brier: Optional[float]
    reliability: float
    resolution: float
    uncertainty: float
    mean_confidence: float
    accuracy: float
    overconfidence: float           # mean confidence - accuracy (>0 overconfident)
    label: Literal["NO_DATA", "WELL_CALIBRATED", "OVERCONFIDENT", "UNDERCONFIDENT"]
    bins: list[CalibrationBin]


class StatsOut(BaseModel):
    total_nodes: int
    total_hyperedges: int
    bjork_window_count: int
    hypercorrection_count: int
    due_count: int
    mean_mastery: float
    calibration: CalibrationOut
    llm_engine: str
    scratch_synced_at: Optional[str] = None


class DueItem(BaseModel):
    node_id: str
    title: str
    retrievability: float
    stability: float
    next_due_at: str
    days_until_due: float


# ---------------------------------------------------------------- artifacts, workspace, settings
class ArtifactOut(BaseModel):
    id: str
    session_id: Optional[str] = None
    agent_name: AgentName
    status: ArtifactStatus
    title: str
    content_type: ContentType
    payload_text: str
    created_at: str


class SubagentRunRequest(BaseModel):
    session_id: Optional[str] = None
    topic: str = ""
    node_id: Optional[str] = None
    pattern: str = ""
    filename: str = ""
    code: str = ""


class WorkspaceFile(BaseModel):
    path: str            # relative to workspace/
    kind: Literal["tex", "md", "pdf", "other"]
    size: int
    modified_at: str


class TexBlock(BaseModel):
    env: str             # section | theorem | definition | problem | lemma | proof
    title: str
    body: str
    line: int


class WorkspaceFileContent(BaseModel):
    path: str
    content: str
    blocks: list[TexBlock]


class ScratchOut(BaseModel):
    content: str
    modified_at: Optional[str]
    path: str


class ScratchWrite(BaseModel):
    content: str


class DemoTelemetry(BaseModel):
    demo_id: str
    session_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    challenge_solved: bool = False
    summary: str = ""


class ChatGPTBrowserStatus(BaseModel):
    available: bool                    # the private local engine is installed on this Mac
    signed_in: Optional[bool] = None   # None = not checked yet
    last_error: Optional[str] = None


class SettingsOut(BaseModel):
    provider: Literal["auto", "anthropic", "gemini", "openai", "openrouter", "claude_cli", "codex_cli", "chatgpt_browser", "deterministic"]
    active_engine: str
    keys_present: dict[str, bool]
    deepgram_available: bool
    native_dictation_available: bool   # on-device macOS speech, Pólya.app only
    claude_cli_available: bool
    codex_available: bool              # `codex` installed and signed in (ChatGPT plan)
    chatgpt_browser: ChatGPTBrowserStatus
    model_overrides: dict[str, str]
    target_success: float              # difficulty target, persisted in ~/Polya/prefs.json
    fetch_sources: bool = True         # learn-chat: look up Wikipedia and arXiv for new topics


class SettingsUpdate(BaseModel):
    provider: Optional[Literal["auto", "anthropic", "gemini", "openai", "openrouter", "claude_cli", "codex_cli", "chatgpt_browser", "deterministic"]] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    deepgram_api_key: Optional[str] = None
    model_overrides: Optional[dict[str, str]] = None
    target_success: Optional[float] = None   # one of 0.80 / 0.85 / 0.90
    fetch_sources: Optional[bool] = None


class CalibrationBinOut(BaseModel):
    lo: float
    hi: float
    count: int
    mean_predicted: Optional[float] = None
    observed: Optional[float] = None


class PredictorScoreOut(BaseModel):
    name: str
    label: str
    baseline: bool
    n: int
    log_loss: Optional[float] = None
    brier: Optional[float] = None
    auc: Optional[float] = None
    calibration_bins: list[CalibrationBinOut]


class ControllerStateOut(BaseModel):
    target: float
    recent_success: Optional[float] = None
    window_n: int
    band: float
    delta: Optional[float] = None
    practice_level: Optional[int] = None
    last_action: Optional[str] = None
    last_summary: Optional[str] = None


class ModelEvalOut(BaseModel):
    n: int
    enough_data: bool
    min_answers: int
    predictors: list[PredictorScoreOut]
    controller: ControllerStateOut


# ---------------------------------------------------------------- websocket
WsEventType = Literal[
    "hello", "subagent_status", "artifact", "scratch_update", "graph_updated",
    "session_updated", "stats", "notes_changed", "pong", "error",
]


class WsEvent(BaseModel):
    type: WsEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str


class SubagentStatus(BaseModel):
    agent_name: AgentName
    state: Literal["IDLE", "RUNNING", "COMPLETED", "FAILED"]
    message: str
    artifact_id: Optional[str] = None
    session_id: Optional[str] = None


# ---------------------------------------------------------------- structured LLM I/O
class LLMStepContent(BaseModel):
    """Shape the LLM must return when generating a step (validated; falls back to deterministic)."""
    title: str
    prompt_latex: str
    body_markdown: str = ""
    options: list[StepOption] = Field(default_factory=list)
    correct_option_id: str = ""
    rationale: str = ""


class LLMDiagnosis(BaseModel):
    is_correct: bool
    trace_quality_score: float
    miss_class: MissClass
    right_for_wrong_reason: bool
    diagnosis_markdown: str
    buggy_rule_statement: str = ""


class LLMOntology(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    hyperedges: list[dict[str, Any]] = Field(default_factory=list)


NodeDetail.model_rebuild()
StepPayload.model_rebuild()


# ------------------------------------------------------------------ research papers (docs/specs/paper-reading)
PaperStatus = Literal["FETCHING", "PARSED", "MAPPED", "FAILED"]
PaperRole = Literal["prerequisite", "definition", "assumption", "claim", "main_result"]


class PaperCreate(BaseModel):
    arxiv: Optional[str] = None            # an arXiv link or id
    workspace_path: Optional[str] = None   # a PDF already in your notes


class PaperOut(BaseModel):
    id: str
    source: str
    arxiv_id: str
    doi: str
    title: str
    authors: list[str]
    year: Optional[int] = None
    abstract: str
    text_kind: str
    status: PaperStatus
    status_detail: str
    map_engine: str
    session_id: Optional[str] = None
    first_guess: str
    understanding: Optional[float] = None  # mean mastery over the paper's own ideas
    idea_count: int
    partial_map: bool
    created_at: str
    updated_at: str


class PaperIdeaOut(BaseModel):
    node_id: str
    title: str
    role: PaperRole
    anchor: str
    quote: str
    mastery: float
    answered: bool
    node_type: str


class PaperSourceOut(BaseModel):
    id: str
    direction: Literal["reference", "citation", "explainer"]
    ref_key: str
    title: str
    authors: str
    year: Optional[int] = None
    arxiv_id: str
    doi: str
    s2_id: str
    url: str
    contexts: list[dict[str, str]]
    sections: list[str]
    influential: bool
    intents: list[str]
    cited_by_count: Optional[int] = None
    is_survey: bool
    for_node_id: str
    score: float
    why: str


class PaperMapOut(BaseModel):
    summary: str
    contributions: list[str]
    notation: list[dict[str, str]]
    key_argument: Optional[dict[str, Any]] = None
    quotes_dropped: int


class PaperSourcesOut(BaseModel):
    reference: list[PaperSourceOut]
    citation: list[PaperSourceOut]
    explainer: list[PaperSourceOut]


class PaperDetail(PaperOut):
    map: PaperMapOut
    ideas: list[PaperIdeaOut]
    sources: PaperSourcesOut
    links: dict[str, Optional[str]]


# ------------------------------------------------------------------ explanations (docs/specs/explain, docs/specs/learn-chat)
class Offer(BaseModel):
    trigger: Literal["CONFIDENT_WRONG", "WHEEL_SPINNING", "WRONG", "WEAK_REASONING", "STUCK"]
    label: str
    action: Literal["OFFER"] = "OFFER"
    step_index: int
    node_id: str


class ExplainMsg(BaseModel):
    id: str
    step_index: int
    node_id: str
    role: Literal["learner", "polya", "say_back"]
    kind: str
    text: str
    trigger: str = ""
    style: str = ""
    engine: str = ""
    before_answer: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SourceOut(BaseModel):
    n: int
    kind: Literal["notes", "paper", "wikipedia", "arxiv"]
    title: str
    url: str = ""


class ExplainRequest(BaseModel):
    action: Literal["ASK", "EXPLAIN", "DIFFERENT", "SIMPLER", "OFFER"]
    message: str = ""
    trigger: str = ""
    step_index: Optional[int] = None       # the card being looked at (default: the active step)
    attempt: str = ""                      # what the learner has typed on that card so far


class ExplainReply(BaseModel):
    reply_markdown: str
    style: str
    engine: str
    node_id: str
    say_back_prompt: Optional[str] = None
    thread: list[ExplainMsg]


class ExplainThread(BaseModel):
    thread: list[ExplainMsg]
    offer: Optional[Offer] = None
    sources: list[SourceOut] = Field(default_factory=list)


class SayBackRequest(BaseModel):
    text: str
    confidence: float = 0.5
    message_id: Optional[str] = None       # the explanation whose prompt is being answered (default: the latest)


class SayBackOut(BaseModel):
    verdict_markdown: str
    is_correct: bool
    trace_quality_score: float
    node_update: NodeUpdate
    thread: list[ExplainMsg]


class LearnRequest(BaseModel):
    action: Literal["OPEN_REPLY", "SKIP", "REPLY", "ASK", "GO_ON", "QUIZ_ME"]
    message: str = ""


class LearnTurn(BaseModel):
    thread: list[ExplainMsg]
    learn_ideas: list[LearnIdea]
    ready: bool
    sources: list[SourceOut]
    engine: str


StepResult.model_rebuild()
