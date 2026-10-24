"""Pydantic v2 schemas for the REST API, the WebSocket hub and structured LLM I/O.

Every model here is mirrored 1:1 in frontend/src/types/harness.ts.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

NodeType = Literal["AXIOM", "PROPOSITION", "MOVE", "COUNTEREXAMPLE", "INTUITION", "BUGGY_RULE"]
EdgeType = Literal["DEDUCTION", "CONTRASTIVE", "ISOMORPHISM", "CUE_TRIGGER"]
SessionMode = Literal["PROBE", "PRODUCTIVE_FAILURE", "TEACH", "PRACTICE", "REFEREE_DUEL"]
SubMode = Literal["STANDARD", "PROOF_REFEREE", "FEYNMAN_STUDENT"]
Phase = Literal["PROBE", "PRODUCTIVE_FAILURE", "PREDICT", "READING", "CHECK", "PRACTICE_CHUNK", "REFEREE"]
StepKind = Literal[
    "PROBE", "PRODUCTIVE_FAILURE", "PREDICT", "READING", "CHECK", "PRACTICE_CHUNK", "REFEREE", "FEYNMAN", "COMPLETE"
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
    engine: Literal["none", "browser", "deepgram"] = "none"


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


class StepResult(BaseModel):
    trace: TraceOut
    feedback_markdown: str
    node_updates: list[NodeUpdate]
    delta_before: float
    delta_after: float
    remedial_spliced: Optional[str] = None
    created_nodes: list[str] = Field(default_factory=list)
    state: SessionState


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


class SettingsOut(BaseModel):
    provider: Literal["auto", "anthropic", "gemini", "openai", "openrouter", "claude_cli", "deterministic"]
    active_engine: str
    keys_present: dict[str, bool]
    deepgram_available: bool
    claude_cli_available: bool
    model_overrides: dict[str, str]


class SettingsUpdate(BaseModel):
    provider: Optional[Literal["auto", "anthropic", "gemini", "openai", "openrouter", "claude_cli", "deterministic"]] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    deepgram_api_key: Optional[str] = None
    model_overrides: Optional[dict[str, str]] = None


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
