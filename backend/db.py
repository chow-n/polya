"""SQLite (WAL) hypergraph store: DDL, migrations, CRUD and row → API model conversion."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Optional

from . import config
from . import cognitive_math as cm

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN (
        'AXIOM', 'PROPOSITION', 'MOVE', 'COUNTEREXAMPLE', 'INTUITION', 'BUGGY_RULE'
    )),
    statement_latex TEXT NOT NULL,
    intuition_summary TEXT NOT NULL,
    formal_proof_sketch_latex TEXT NOT NULL DEFAULT '',
    domain_cluster TEXT NOT NULL,
    logical_depth INTEGER NOT NULL DEFAULT 0,
    bkt_p_mastery REAL NOT NULL DEFAULT 0.15,
    bkt_p_transit REAL NOT NULL DEFAULT 0.12,
    bkt_p_slip REAL NOT NULL DEFAULT 0.08,
    bkt_p_guess REAL NOT NULL DEFAULT 0.05,
    fsrs_stability REAL NOT NULL DEFAULT 1.0,
    fsrs_difficulty REAL NOT NULL DEFAULT 5.0,
    fsrs_reps INTEGER NOT NULL DEFAULT 0,
    fsrs_lapses INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT NOT NULL,
    cue_symbolic REAL NOT NULL DEFAULT 0.0,
    cue_disguised_notation REAL NOT NULL DEFAULT 0.0,
    cue_geometric REAL NOT NULL DEFAULT 0.0,
    cue_computational REAL NOT NULL DEFAULT 0.0,
    cue_adversarial REAL NOT NULL DEFAULT 0.0,
    brier_sum REAL NOT NULL DEFAULT 0.0,
    brier_count INTEGER NOT NULL DEFAULT 0,
    hypercorrection_flag INTEGER NOT NULL DEFAULT 0,
    last_miss_class TEXT NOT NULL DEFAULT 'NONE',
    created_in_session_id TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hyperedges (
    id TEXT PRIMARY KEY,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('DEDUCTION', 'CONTRASTIVE', 'ISOMORPHISM', 'CUE_TRIGGER')),
    premise_node_ids_json TEXT NOT NULL,
    conclusion_node_id TEXT NOT NULL,
    reasoning_chain_latex TEXT NOT NULL,
    discriminating_condition_latex TEXT NOT NULL DEFAULT '',
    edge_mastery REAL NOT NULL DEFAULT 0.50,
    session_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conclusion_node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('PROBE', 'PRODUCTIVE_FAILURE', 'TEACH', 'PRACTICE', 'REFEREE_DUEL')),
    sub_mode TEXT NOT NULL DEFAULT 'STANDARD',
    target_goal TEXT NOT NULL,
    attached_files_json TEXT NOT NULL DEFAULT '[]',
    step_velocity_delta REAL NOT NULL DEFAULT 1.0,
    current_step_index INTEGER NOT NULL DEFAULT 0,
    dependency_plan_json TEXT NOT NULL DEFAULT '[]',
    active_step_payload_json TEXT NOT NULL DEFAULT '{}',
    history_steps_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_traces (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN (
        'PROBE', 'PRODUCTIVE_FAILURE', 'PREDICT', 'READING', 'CHECK', 'PRACTICE_CHUNK', 'REFEREE'
    )),
    target_node_ids_json TEXT NOT NULL,
    cue_level INTEGER NOT NULL DEFAULT 1,
    prompt_shown_latex TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '[]',
    raw_prediction_locked TEXT NOT NULL DEFAULT '',
    thinking_while_reading_json TEXT NOT NULL DEFAULT '[]',
    verification_thinking TEXT NOT NULL DEFAULT '',
    selected_answer TEXT NOT NULL DEFAULT '',
    confidence_slider REAL NOT NULL DEFAULT 0.50,
    prosody_metrics_json TEXT NOT NULL DEFAULT '{"initial_latency_ms":0,"total_silence_ms":0,"hesitation_count":0,"hedge_count":0,"wpm":0}',
    is_correct INTEGER NOT NULL DEFAULT 0,
    trace_quality_score REAL NOT NULL DEFAULT 0.50,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'SOLVED_CLEAN', 'SOLVED_WITH_HINTS', 'PARTIAL', 'FAILED', 'HIGH_CONFIDENCE_ERROR', 'EXPLORATION_LOGGED'
    )),
    max_hint_rung TEXT NOT NULL DEFAULT 'NONE' CHECK (max_hint_rung IN ('NONE', 'R0', 'R1', 'R2', 'R3', 'R4')),
    miss_class TEXT NOT NULL DEFAULT 'NONE' CHECK (miss_class IN (
        'NONE', 'ALGEBRAIC_SLIP', 'NOTATION_OBSTRUCTION', 'MISSING_PREREQUISITE',
        'BOUNDARY_OMISSION', 'FALSE_ANALOGY', 'CUE_BLINDNESS'
    )),
    ai_diagnosis_markdown TEXT NOT NULL DEFAULT '',
    brier_score REAL NOT NULL DEFAULT 0.0,
    bkt_mastery_before REAL NOT NULL DEFAULT 0.0,
    bkt_mastery_after REAL NOT NULL DEFAULT 0.0,
    fsrs_stability_before REAL NOT NULL DEFAULT 0.0,
    fsrs_stability_after REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subagent_artifacts (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    agent_name TEXT NOT NULL CHECK (agent_name IN (
        'SYMBOLIC_VERIFIER', 'BUG_LIBRARY_DIAGNOSTICIAN', 'COUNTEREXAMPLE_SYNTHESIZER',
        'SANDBOX_DEMO_BUILDER', 'SVG_DIAGRAM_MAKER', 'LOCAL_CORPUS_RAG',
        'LITERATURE_RESEARCHER', 'ONTOLOGIST_EXTRACTOR'
    )),
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    payload_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Side table (docs/specs/model-eval-85 D1): what the learner model predicted for each graded answer, logged
-- before the update. Kept separate so the original telemetry_traces DDL stays exact.
CREATE TABLE IF NOT EXISTS model_predictions (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    created_at TEXT NOT NULL,
    elapsed_days REAL NOT NULL,
    r_at_review REAL NOT NULL,
    p_mastery_before REAL NOT NULL,
    p_bkt REAL NOT NULL,
    p_memory REAL NOT NULL,
    p_combined REAL NOT NULL,
    p_global_baseline REAL NOT NULL,
    p_node_baseline REAL NOT NULL,
    y INTEGER NOT NULL,
    success INTEGER NOT NULL
);

-- Side tables (docs/specs/paper-reading D5): papers you read, which ideas came from them, and their sources.
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,                 -- arxiv | pdf
    arxiv_id TEXT NOT NULL DEFAULT '',
    doi TEXT NOT NULL DEFAULT '',
    s2_id TEXT NOT NULL DEFAULT '',
    openalex_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    authors_json TEXT NOT NULL DEFAULT '[]',
    year INTEGER,
    abstract TEXT NOT NULL DEFAULT '',
    text_kind TEXT NOT NULL DEFAULT '',   -- latex | pdf_text
    status TEXT NOT NULL CHECK (status IN ('FETCHING', 'PARSED', 'MAPPED', 'FAILED')),
    status_detail TEXT NOT NULL DEFAULT '',
    map_json TEXT NOT NULL DEFAULT '{}',
    map_engine TEXT NOT NULL DEFAULT '',
    session_id TEXT,
    first_guess TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_nodes (
    paper_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('prerequisite', 'definition', 'assumption', 'claim', 'main_result')),
    anchor TEXT NOT NULL DEFAULT '',
    quote TEXT NOT NULL DEFAULT '',
    ord INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (paper_id, node_id),
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS paper_refs (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('reference', 'citation', 'explainer')),
    ref_key TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '',
    year INTEGER,
    arxiv_id TEXT NOT NULL DEFAULT '',
    doi TEXT NOT NULL DEFAULT '',
    s2_id TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    contexts_json TEXT NOT NULL DEFAULT '[]',
    sections_json TEXT NOT NULL DEFAULT '[]',
    influential INTEGER NOT NULL DEFAULT 0,
    intents_json TEXT NOT NULL DEFAULT '[]',
    cited_by_count INTEGER,
    is_survey INTEGER NOT NULL DEFAULT 0,
    for_node_id TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL DEFAULT 0,
    why TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- Side tables (docs/specs/explain, docs/specs/learn-chat): the session's explanation / learning-chat thread and the
-- numbered sources it cites.
CREATE TABLE IF NOT EXISTS explanations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    node_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('learner', 'polya', 'say_back')),
    kind TEXT NOT NULL,                   -- ASK | EXPLAIN | DIFFERENT | SIMPLER | OFFER | SAY_BACK | LEARN | LEARN_Q
    text TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT '',
    style TEXT NOT NULL DEFAULT '',
    engine TEXT NOT NULL DEFAULT '',
    before_answer INTEGER NOT NULL DEFAULT 0,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_sources (
    session_id TEXT NOT NULL,
    n INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('notes', 'paper', 'wikipedia', 'arxiv')),
    title TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    passage TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (session_id, n),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_explanations_session ON explanations(session_id);
CREATE INDEX IF NOT EXISTS idx_paper_nodes_node ON paper_nodes(node_id);
CREATE INDEX IF NOT EXISTS idx_paper_refs_paper ON paper_refs(paper_id, direction, score);
CREATE INDEX IF NOT EXISTS idx_traces_session ON telemetry_traces(session_id, step_index);
CREATE INDEX IF NOT EXISTS idx_edges_conclusion ON hyperedges(conclusion_node_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON subagent_artifacts(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_predictions_node ON model_predictions(node_id);
"""

NODE_COLUMNS = [
    "id", "title", "node_type", "statement_latex", "intuition_summary", "formal_proof_sketch_latex",
    "domain_cluster", "logical_depth", "bkt_p_mastery", "bkt_p_transit", "bkt_p_slip", "bkt_p_guess",
    "fsrs_stability", "fsrs_difficulty", "fsrs_reps", "fsrs_lapses", "last_reviewed_at",
    "cue_symbolic", "cue_disguised_notation", "cue_geometric", "cue_computational", "cue_adversarial",
    "brier_sum", "brier_count", "hypercorrection_flag", "last_miss_class", "created_in_session_id", "updated_at",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH), timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """A connection inside an IMMEDIATE transaction, committed on success."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
    except BaseException:
        conn.close()
        raise
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


@contextmanager
def ro() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ro() as conn:
        conn.executescript(SCHEMA)


# ------------------------------------------------------------------ nodes
def upsert_node(conn: sqlite3.Connection, node: dict[str, Any]) -> None:
    row = {c: node.get(c) for c in NODE_COLUMNS if c in node}
    row.setdefault("last_reviewed_at", now_iso())
    row["updated_at"] = now_iso()
    cols = ", ".join(row)
    params = ", ".join(f":{c}" for c in row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in row if c != "id")
    conn.execute(f"INSERT INTO nodes ({cols}) VALUES ({params}) ON CONFLICT(id) DO UPDATE SET {updates}", row)


def update_node_fields(conn: sqlite3.Connection, node_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now_iso()
    sets = ", ".join(f"{k}=:{k}" for k in fields)
    conn.execute(f"UPDATE nodes SET {sets} WHERE id=:_id", {**fields, "_id": node_id})


def get_node(conn: sqlite3.Connection, node_id: str) -> Optional[dict[str, Any]]:
    r = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
    return dict(r) if r else None


def all_nodes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM nodes ORDER BY logical_depth, id")]


def node_exists(conn: sqlite3.Connection, node_id: str) -> bool:
    return conn.execute("SELECT 1 FROM nodes WHERE id=?", (node_id,)).fetchone() is not None


# ------------------------------------------------------------------ hyperedges
def insert_edge(conn: sqlite3.Connection, edge_type: str, premises: list[str], conclusion: str,
                reasoning: str, discriminating: str = "", session_id: Optional[str] = None,
                edge_id: Optional[str] = None, mastery: float = 0.5) -> str:
    eid = edge_id or new_id("he")
    conn.execute(
        "INSERT OR REPLACE INTO hyperedges (id, edge_type, premise_node_ids_json, conclusion_node_id, reasoning_chain_latex,"
        " discriminating_condition_latex, edge_mastery, session_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, edge_type, json.dumps(premises), conclusion, reasoning, discriminating, mastery, session_id, now_iso()),
    )
    return eid


def all_edges(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    out = []
    for r in conn.execute("SELECT * FROM hyperedges ORDER BY created_at, id"):
        d = dict(r)
        d["premise_node_ids"] = json.loads(d.pop("premise_node_ids_json"))
        out.append(d)
    return out


def deduction_pairs(edges: Iterable[dict[str, Any]]) -> list[tuple[list[str], str]]:
    return [(e["premise_node_ids"], e["conclusion_node_id"]) for e in edges if e["edge_type"] == "DEDUCTION"]


def recompute_depths(conn: sqlite3.Connection) -> dict[str, int]:
    """Topological logical depth over DEDUCTION edges.

    Only AXIOM nodes may sit at depth 0; every other node is at least depth 1. Shadow nodes
    (BUGGY_RULE / COUNTEREXAMPLE) without deductive premises take the depth of the concept they
    shadow (their CONTRASTIVE peer). Returns {node_id: new_depth} for changed nodes.
    """
    nodes = all_nodes(conn)
    edges = all_edges(conn)
    floor = {n["id"]: (0 if n["node_type"] == "AXIOM" else 1) for n in nodes}
    depth = cm.topological_depths(
        [n["id"] for n in nodes], [("DEDUCTION", e["premise_node_ids"], e["conclusion_node_id"]) for e in edges
                                   if e["edge_type"] == "DEDUCTION"], floor)
    has_premise = {e["conclusion_node_id"] for e in edges if e["edge_type"] == "DEDUCTION"}
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        if n["node_type"] in ("BUGGY_RULE", "COUNTEREXAMPLE") and n["id"] not in has_premise:
            peers = []
            for e in edges:
                if e["edge_type"] != "CONTRASTIVE":
                    continue
                members = set(e["premise_node_ids"]) | {e["conclusion_node_id"]}
                if n["id"] in members:
                    peers += [m for m in members if m != n["id"] and m in by_id
                              and by_id[m]["node_type"] not in ("BUGGY_RULE", "COUNTEREXAMPLE")]
            if peers:
                depth[n["id"]] = max(depth[p] for p in peers)
    changed = {}
    for n in nodes:
        if n["logical_depth"] != depth[n["id"]]:
            changed[n["id"]] = depth[n["id"]]
            conn.execute("UPDATE nodes SET logical_depth=? WHERE id=?", (depth[n["id"]], n["id"]))
    return changed


# ------------------------------------------------------------------ sessions
SESSION_JSON = {
    "attached_files_json": "attached_files",
    "dependency_plan_json": "dependency_plan",
    "active_step_payload_json": "active_step",
    "history_steps_json": "history_steps",
}


def insert_session(conn: sqlite3.Connection, s: dict[str, Any]) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO sessions (id, title, mode, sub_mode, target_goal, attached_files_json, step_velocity_delta,"
        " current_step_index, dependency_plan_json, active_step_payload_json, history_steps_json, status, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (s["id"], s["title"], s["mode"], s.get("sub_mode", "STANDARD"), s["target_goal"],
         json.dumps(s.get("attached_files", [])), s.get("step_velocity_delta", 1.0), s.get("current_step_index", 0),
         json.dumps(s.get("dependency_plan", [])), json.dumps(s.get("active_step", {})),
         json.dumps(s.get("history_steps", [])), s.get("status", "ACTIVE"), s.get("created_at", ts), s.get("updated_at", ts)),
    )


def load_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict[str, Any]]:
    r = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for col, key in SESSION_JSON.items():
        d[key] = json.loads(d.pop(col))
    return d


def save_session(conn: sqlite3.Connection, s: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE sessions SET title=?, step_velocity_delta=?, current_step_index=?, dependency_plan_json=?,"
        " active_step_payload_json=?, history_steps_json=?, status=?, attached_files_json=?, updated_at=? WHERE id=?",
        (s["title"], s["step_velocity_delta"], s["current_step_index"], json.dumps(s["dependency_plan"]),
         json.dumps(s["active_step"]), json.dumps(s["history_steps"]), s["status"], json.dumps(s["attached_files"]),
         now_iso(), s["id"]),
    )


def list_sessions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    out = []
    for r in conn.execute("SELECT id FROM sessions ORDER BY updated_at DESC, created_at DESC"):
        s = load_session(conn, r["id"])
        if s:
            out.append(s)
    return out


# ------------------------------------------------------------------ traces
TRACE_JSON = {
    "target_node_ids_json": "target_node_ids",
    "options_json": "options",
    "thinking_while_reading_json": "thinking_while_reading",
    "prosody_metrics_json": "prosody_metrics",
}


def insert_trace(conn: sqlite3.Connection, t: dict[str, Any]) -> str:
    tid = t.get("id") or new_id("tr")
    row = {
        "id": tid, "session_id": t["session_id"], "step_index": t["step_index"], "phase": t["phase"],
        "target_node_ids_json": json.dumps(t.get("target_node_ids", [])), "cue_level": t.get("cue_level", 1),
        "prompt_shown_latex": t.get("prompt_shown_latex", ""), "options_json": json.dumps(t.get("options", [])),
        "raw_prediction_locked": t.get("raw_prediction_locked", ""),
        "thinking_while_reading_json": json.dumps(t.get("thinking_while_reading", [])),
        "verification_thinking": t.get("verification_thinking", ""), "selected_answer": t.get("selected_answer", ""),
        "confidence_slider": t.get("confidence_slider", 0.5),
        "prosody_metrics_json": json.dumps(t.get("prosody_metrics") or {
            "initial_latency_ms": 0, "total_silence_ms": 0, "hesitation_count": 0, "hedge_count": 0, "wpm": 0}),
        "is_correct": int(t.get("is_correct", 0)), "trace_quality_score": t.get("trace_quality_score", 0.5),
        "outcome": t["outcome"], "max_hint_rung": t.get("max_hint_rung", "NONE"), "miss_class": t.get("miss_class", "NONE"),
        "ai_diagnosis_markdown": t.get("ai_diagnosis_markdown", ""), "brier_score": t.get("brier_score", 0.0),
        "bkt_mastery_before": t.get("bkt_mastery_before", 0.0), "bkt_mastery_after": t.get("bkt_mastery_after", 0.0),
        "fsrs_stability_before": t.get("fsrs_stability_before", 0.0),
        "fsrs_stability_after": t.get("fsrs_stability_after", 0.0), "created_at": t.get("created_at", now_iso()),
    }
    cols = ", ".join(row)
    conn.execute(f"INSERT INTO telemetry_traces ({cols}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    return tid


def _trace_row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    for col, key in TRACE_JSON.items():
        d[key] = json.loads(d.pop(col))
    return d


def get_trace(conn: sqlite3.Connection, trace_id: str) -> Optional[dict[str, Any]]:
    r = conn.execute("SELECT * FROM telemetry_traces WHERE id=?", (trace_id,)).fetchone()
    return _trace_row(r) if r else None


def session_traces(conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    return [_trace_row(r) for r in conn.execute(
        "SELECT * FROM telemetry_traces WHERE session_id=? ORDER BY step_index, created_at", (session_id,))]


def node_traces(conn: sqlite3.Connection, node_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM telemetry_traces WHERE target_node_ids_json LIKE ? ORDER BY created_at DESC LIMIT ?",
        (f'%"{node_id}"%', limit))
    return [_trace_row(r) for r in rows]


PREDICTION_COLUMNS = ["id", "trace_id", "session_id", "node_id", "phase", "created_at", "elapsed_days", "r_at_review",
                      "p_mastery_before", "p_bkt", "p_memory", "p_combined", "p_global_baseline", "p_node_baseline",
                      "y", "success"]


def prediction_counts(conn: sqlite3.Connection, node_id: str) -> tuple[int, int, int, int]:
    """(correct, answered) over all earlier graded answers, then the same for one node."""
    g = conn.execute("SELECT COALESCE(SUM(y), 0), COUNT(*) FROM model_predictions").fetchone()
    n = conn.execute("SELECT COALESCE(SUM(y), 0), COUNT(*) FROM model_predictions WHERE node_id=?", (node_id,)).fetchone()
    return g[0], g[1], n[0], n[1]


def insert_prediction(conn: sqlite3.Connection, p: dict[str, Any]) -> str:
    row = {c: p.get(c) for c in PREDICTION_COLUMNS}
    row["id"] = row["id"] or new_id("mp")
    row["created_at"] = row["created_at"] or now_iso()
    conn.execute(f"INSERT INTO model_predictions ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                 tuple(row.values()))
    return row["id"]


# evidence gathered right after an explanation (learn chat, say-it-back) never steers the difficulty controller
CHAT_PHASES = ("LEARN_CHAT", "SAY_BACK")


def recent_successes(conn: sqlite3.Connection, limit: int) -> list[int]:
    """success (0/1) of the last `limit` graded answers across all sessions, oldest first."""
    rows = conn.execute("SELECT success FROM model_predictions WHERE phase NOT IN (?, ?) ORDER BY rowid DESC LIMIT ?",
                        (*CHAT_PHASES, limit)).fetchall()
    return [r[0] for r in reversed(rows)]


def calibration_pairs(conn: sqlite3.Connection) -> list[tuple[float, int]]:
    rows = conn.execute(
        "SELECT confidence_slider, is_correct FROM telemetry_traces WHERE outcome != 'EXPLORATION_LOGGED'"
        " AND phase IN ('PROBE','CHECK','PRACTICE_CHUNK','REFEREE')")
    return [(r["confidence_slider"], r["is_correct"]) for r in rows]


# ------------------------------------------------------------------ artifacts
def recent_elapsed_ms(conn: sqlite3.Connection, limit: int = 20) -> list[float]:
    """Time-to-answer of the most recent graded cards across sessions (docs/specs/explain FR3, stuck nudge)."""
    out: list[float] = []
    for r in conn.execute("SELECT history_steps_json FROM sessions ORDER BY updated_at DESC LIMIT 15"):
        for h in reversed(json.loads(r[0])):
            if h.get("elapsed_ms") and h.get("kind") in ("PROBE", "CHECK", "PRACTICE_CHUNK", "REFEREE", "FEYNMAN"):
                out.append(float(h["elapsed_ms"]))
                if len(out) >= limit:
                    return out
    return out


# ------------------------------------------------------------------ explanation thread + sources
def insert_explanation(conn: sqlite3.Connection, m: dict[str, Any]) -> dict[str, Any]:
    row = {"id": m.get("id") or new_id("ex"), "session_id": m["session_id"], "step_index": int(m.get("step_index", 0)),
           "node_id": m.get("node_id", ""), "role": m["role"], "kind": m["kind"], "text": m["text"],
           "trigger": m.get("trigger", ""), "style": m.get("style", ""), "engine": m.get("engine", ""),
           "before_answer": int(bool(m.get("before_answer"))), "meta_json": json.dumps(m.get("meta") or {}),
           "created_at": now_iso()}
    conn.execute(f"INSERT INTO explanations ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    return _explanation_row(row)


def _explanation_row(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["meta"] = json.loads(d.pop("meta_json") or "{}")
    d["before_answer"] = bool(d["before_answer"])
    return d


def session_thread(conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    return [_explanation_row(r) for r in conn.execute(
        "SELECT * FROM explanations WHERE session_id=? ORDER BY rowid", (session_id,))]


def insert_source(conn: sqlite3.Connection, session_id: str, kind: str, title: str, url: str, passage: str) -> int:
    n = conn.execute("SELECT COALESCE(MAX(n), 0) + 1 FROM session_sources WHERE session_id=?", (session_id,)).fetchone()[0]
    conn.execute("INSERT INTO session_sources (session_id, n, kind, title, url, passage, fetched_at) VALUES (?,?,?,?,?,?,?)",
                 (session_id, n, kind, title, url, passage, now_iso()))
    return n


def session_sources(conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM session_sources WHERE session_id=? ORDER BY n", (session_id,))]


def insert_artifact(conn: sqlite3.Connection, agent_name: str, status: str, title: str, content_type: str,
                    payload_text: str, session_id: Optional[str] = None, artifact_id: Optional[str] = None) -> str:
    aid = artifact_id or new_id("art")
    conn.execute(
        "INSERT OR REPLACE INTO subagent_artifacts (id, session_id, agent_name, status, title, content_type, payload_text, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (aid, session_id, agent_name, status, title, content_type, payload_text, now_iso()),
    )
    return aid


def update_artifact(conn: sqlite3.Connection, artifact_id: str, status: str, payload_text: str,
                    title: Optional[str] = None, content_type: Optional[str] = None) -> None:
    conn.execute(
        "UPDATE subagent_artifacts SET status=?, payload_text=?, title=COALESCE(?, title),"
        " content_type=COALESCE(?, content_type) WHERE id=?",
        (status, payload_text, title, content_type, artifact_id))


def get_artifact(conn: sqlite3.Connection, artifact_id: str) -> Optional[dict[str, Any]]:
    r = conn.execute("SELECT * FROM subagent_artifacts WHERE id=?", (artifact_id,)).fetchone()
    return dict(r) if r else None


def list_artifacts(conn: sqlite3.Connection, session_id: Optional[str] = None, agent_name: Optional[str] = None,
                   limit: int = 100) -> list[dict[str, Any]]:
    q = "SELECT * FROM subagent_artifacts WHERE 1=1"
    args: list[Any] = []
    if session_id:
        q += " AND (session_id=? OR session_id IS NULL)"
        args.append(session_id)
    if agent_name:
        q += " AND agent_name=?"
        args.append(agent_name)
    q += " ORDER BY created_at DESC, id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(q, args)]


# ------------------------------------------------------------------ row → API dicts
def node_out(n: dict[str, Any], now: Optional[datetime] = None) -> dict[str, Any]:
    t = cm.elapsed_days(n["last_reviewed_at"], now)
    r = cm.retrievability(t, n["fsrs_stability"])
    due = cm.next_due(n["last_reviewed_at"], n["fsrs_stability"])
    now = now or cm.utcnow()
    cues = {c: n[c] for c in cm.CUE_DIMENSIONS}
    out = {k: v for k, v in n.items() if k not in cues}
    out.update(
        cues=cues,
        retrievability=r,
        in_bjork_window=cm.BJORK_WINDOW[0] <= r <= cm.BJORK_WINDOW[1],
        next_due_at=due.isoformat(timespec="seconds"),
        days_until_due=(due - now).total_seconds() / 86400.0,
        cue_mean=sum(cues.values()) / len(cues),
        mean_brier=(n["brier_sum"] / n["brier_count"]) if n["brier_count"] else None,
    )
    return out


def edge_out(e: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in e.items() if k != "premise_node_ids_json"}


def session_out(s: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in s.items() if k != "active_step"}


def artifact_out(a: dict[str, Any]) -> dict[str, Any]:
    return a
