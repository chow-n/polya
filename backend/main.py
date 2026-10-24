"""FastAPI REST endpoints and the bi-directional WebSocket hub (see docs/API.md)."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import cognitive_math as cm
from . import db, llm, seed, tools
from .agents import orchestrator, subagents
from .config import settings
from .hub import hub
from .models import (
    ALL_AGENTS, ArtifactOut, ChunkEvaluation, ChunkRequest, CreateSessionRequest, DemoTelemetry, DuelReply, DuelRequest,
    DueItem, GraphOut, HintOut, HintRequest, NodeDetail, PracticeQueueItem, ScratchOut, ScratchWrite, SessionOut,
    SessionState, SettingsOut, SettingsUpdate, StatsOut, StepResult, StepSubmission, SubagentRunRequest, WorkspaceFile,
    WorkspaceFileContent,
)
from .scratchpad_watcher import watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub.loop = asyncio.get_running_loop()
    db.init_db()
    await seed.seed_if_empty()
    watcher.start()
    try:
        yield
    finally:
        watcher.stop()


app = FastAPI(title="LearnHarness", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ helpers
def _graph() -> dict[str, Any]:
    with db.ro() as conn:
        now = cm.utcnow()
        return {"nodes": [db.node_out(n, now) for n in db.all_nodes(conn)],
                "hyperedges": [db.edge_out(e) for e in db.all_edges(conn)]}


def compute_stats() -> dict[str, Any]:
    with db.ro() as conn:
        now = cm.utcnow()
        nodes = [db.node_out(n, now) for n in db.all_nodes(conn)]
        learnable = [n for n in nodes if n["node_type"] != "BUGGY_RULE"]
        dec = cm.murphy_decomposition(db.calibration_pairs(conn))
        n_edges = conn.execute("SELECT COUNT(*) c FROM hyperedges").fetchone()["c"]
    return {
        "total_nodes": len(nodes), "total_hyperedges": n_edges,
        "bjork_window_count": sum(1 for n in learnable if n["in_bjork_window"]),
        "hypercorrection_count": sum(1 for n in nodes if n["hypercorrection_flag"] == 1),
        "due_count": sum(1 for n in learnable if n["days_until_due"] <= 0),
        "mean_mastery": sum(n["bkt_p_mastery"] for n in learnable) / max(1, len(learnable)),
        "calibration": {"n": dec.n, "mean_brier": dec.brier, "reliability": dec.reliability, "resolution": dec.resolution,
                        "uncertainty": dec.uncertainty, "mean_confidence": dec.mean_confidence, "accuracy": dec.accuracy,
                        "overconfidence": dec.overconfidence, "label": dec.label, "bins": dec.bins},
        "llm_engine": llm.describe_engine(),
        "scratch_synced_at": watcher.handler.last_scratch_sync or tools.read_scratch()["modified_at"],
    }


def _settings_out() -> dict[str, Any]:
    return {"provider": settings.provider, "active_engine": llm.describe_engine(), "keys_present": llm.keys_present(),
            "deepgram_available": bool(settings.keys.get("deepgram")), "claude_cli_available": llm.claude_cli_available(),
            "model_overrides": dict(settings.models)}


# ------------------------------------------------------------------ REST
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "llm_engine": llm.describe_engine()}


@app.get("/api/graph", response_model=GraphOut)
async def graph() -> dict[str, Any]:
    return _graph()


@app.get("/api/nodes/{node_id}", response_model=NodeDetail)
async def node_detail(node_id: str) -> dict[str, Any]:
    with db.ro() as conn:
        n = db.get_node(conn, node_id)
        if not n:
            raise HTTPException(404, "node not found")
        edges = db.all_edges(conn)
        incoming = [e for e in edges if e["conclusion_node_id"] == node_id]
        outgoing = [e for e in edges if node_id in e["premise_node_ids"]]
        peers, bugs = [], []
        for e in edges:
            if e["edge_type"] != "CONTRASTIVE":
                continue
            members = set(e["premise_node_ids"]) | {e["conclusion_node_id"]}
            if node_id in members:
                for m in members - {node_id}:
                    mn = db.get_node(conn, m)
                    (bugs if mn and mn["node_type"] == "BUGGY_RULE" else peers).append(m)
        ids = [x["id"] for x in db.all_nodes(conn)]
        parents, children = cm.dag_adjacency(ids, db.deduction_pairs(edges))
        return {"node": db.node_out(n), "incoming": [db.edge_out(e) for e in incoming],
                "outgoing": [db.edge_out(e) for e in outgoing], "contrastive_peers": sorted(set(peers)),
                "buggy_rule_links": sorted(set(bugs)), "ancestors": sorted(cm._closure(node_id, parents)),
                "descendants": sorted(cm._closure(node_id, children)), "traces": db.node_traces(conn, node_id, 20)}


@app.get("/api/stats", response_model=StatsOut)
async def stats() -> dict[str, Any]:
    return compute_stats()


@app.get("/api/due", response_model=list[DueItem])
async def due() -> list[dict[str, Any]]:
    with db.ro() as conn:
        now = cm.utcnow()
        out = [db.node_out(n, now) for n in db.all_nodes(conn) if n["node_type"] != "BUGGY_RULE"]
    out.sort(key=lambda n: n["next_due_at"])
    return [{"node_id": n["id"], "title": n["title"], "retrievability": n["retrievability"], "stability": n["fsrs_stability"],
             "next_due_at": n["next_due_at"], "days_until_due": n["days_until_due"]} for n in out]


@app.get("/api/practice/queue", response_model=list[PracticeQueueItem])
async def practice_queue(limit: int = 12) -> list[dict[str, Any]]:
    with db.ro() as conn:
        nodes = [n for n in db.all_nodes(conn) if n["node_type"] != "BUGGY_RULE"]
    ranked = cm.rank_nodes_for_practice(nodes)[:limit]
    return [{"node_id": n["id"], "title": n["title"], "domain_cluster": n["domain_cluster"], "score": pb.score,
             "retrievability": cm.retrievability(cm.elapsed_days(n["last_reviewed_at"]), n["fsrs_stability"]),
             "bjork_component": pb.bjork, "forgetting_component": pb.forgetting, "cue_gap_component": pb.cue_gap,
             "hypercorrection_component": pb.hypercorrection, "interleave_penalty": pb.interleave_penalty}
            for n, pb in ranked]


@app.get("/api/sessions", response_model=list[SessionOut])
async def sessions() -> list[dict[str, Any]]:
    with db.ro() as conn:
        return [db.session_out(s) for s in db.list_sessions(conn)]


@app.post("/api/sessions", response_model=SessionState)
async def create_session(req: CreateSessionRequest) -> dict[str, Any]:
    return await orchestrator.create_session(req.model_dump())


@app.get("/api/sessions/{session_id}", response_model=SessionState)
async def get_session(session_id: str) -> dict[str, Any]:
    return await orchestrator.get_state(session_id)


@app.post("/api/sessions/{session_id}/submit", response_model=StepResult)
async def submit(session_id: str, sub: StepSubmission) -> dict[str, Any]:
    return await orchestrator.submit(session_id, sub.model_dump())


@app.post("/api/sessions/{session_id}/advance", response_model=SessionState)
async def advance(session_id: str) -> dict[str, Any]:
    return await orchestrator.advance(session_id)


@app.post("/api/sessions/{session_id}/hint", response_model=HintOut)
async def hint(session_id: str, req: HintRequest) -> dict[str, Any]:
    return await orchestrator.hint(session_id, req.rung, req.current_thinking)


@app.post("/api/sessions/{session_id}/chunk", response_model=ChunkEvaluation)
async def chunk(session_id: str, req: ChunkRequest) -> dict[str, Any]:
    if not req.text.strip():
        raise HTTPException(422, "empty chunk")
    return await orchestrator.chunk(session_id, req.text, req.confidence)


@app.post("/api/sessions/{session_id}/duel", response_model=DuelReply)
async def duel(session_id: str, req: DuelRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(422, "empty message")
    return await orchestrator.duel(session_id, req.message)


@app.get("/api/artifacts", response_model=list[ArtifactOut])
async def artifacts(session_id: Optional[str] = None, agent_name: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
    with db.ro() as conn:
        return db.list_artifacts(conn, session_id, agent_name, limit)


@app.get("/api/artifacts/{artifact_id}", response_model=ArtifactOut)
async def artifact(artifact_id: str) -> dict[str, Any]:
    with db.ro() as conn:
        a = db.get_artifact(conn, artifact_id)
    if not a:
        raise HTTPException(404, "artifact not found")
    return a


@app.post("/api/subagents/{agent_name}/run", response_model=ArtifactOut)
async def run_subagent(agent_name: str, req: SubagentRunRequest) -> dict[str, Any]:
    if agent_name not in ALL_AGENTS:
        raise HTTPException(404, f"unknown agent {agent_name}")
    node = None
    if req.node_id:
        with db.ro() as conn:
            node = db.get_node(conn, req.node_id)
        if not node:
            raise HTTPException(404, "node not found")
    topic = req.topic or (node["title"] if node else "")
    sid = req.session_id
    if agent_name == "SYMBOLIC_VERIFIER":
        code = req.code or (tools.check_equivalence_code(*req.topic.split("=", 1)) if "=" in req.topic else "")
        if not code:
            raise HTTPException(422, "provide `code`, or `topic` as an equation lhs = rhs")
        _, art = await subagents.symbolic_verify(sid, code, req.topic or "Manual verification")
        return art
    if agent_name == "SANDBOX_DEMO_BUILDER":
        return await subagents.build_demo(sid, topic or "gradient descent", node)
    if agent_name == "SVG_DIAGRAM_MAKER":
        if not node:
            raise HTTPException(422, "node_id required")
        return await subagents.make_svg(sid, node)
    if agent_name == "LOCAL_CORPUS_RAG":
        return await subagents.corpus_rag(sid, topic or req.pattern or "theorem", [req.filename] if req.filename else [], req.pattern)
    if agent_name == "LITERATURE_RESEARCHER":
        return await subagents.literature(sid, topic or "attention")
    if agent_name == "COUNTEREXAMPLE_SYNTHESIZER":
        if not node:
            raise HTTPException(422, "node_id required")
        await subagents.synthesize_counterexample(sid, req.topic or req.code, node)
    elif agent_name == "BUG_LIBRARY_DIAGNOSTICIAN":
        if not node:
            raise HTTPException(422, "node_id required")
        await subagents.diagnose(sid, {"raw_prediction_locked": req.topic, "verification_thinking": req.code,
                                       "is_correct": 0, "confidence": 0.5}, node)
    elif agent_name == "ONTOLOGIST_EXTRACTOR":
        session = None
        if sid:
            with db.ro() as conn:
                session = db.load_session(conn, sid)
        await subagents.ontologist(sid, session, import_file=req.filename or None)
    with db.ro() as conn:
        latest = db.list_artifacts(conn, None, agent_name, 1)
    if not latest:
        raise HTTPException(500, "agent produced no artifact")
    return latest[0]


@app.get("/api/workspace/files", response_model=list[WorkspaceFile])
async def workspace_files() -> list[dict[str, Any]]:
    return tools.list_workspace_files()


@app.get("/api/workspace/file", response_model=WorkspaceFileContent)
async def workspace_file(path: str = Query(...)) -> dict[str, Any]:
    try:
        d = tools.read_workspace_file(path)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(404, str(e))
    return {"path": d["path"], "content": d["content"], "blocks": d["blocks"]}


@app.get("/api/scratch", response_model=ScratchOut)
async def get_scratch() -> dict[str, Any]:
    return tools.read_scratch()


@app.put("/api/scratch", response_model=ScratchOut)
async def put_scratch(req: ScratchWrite) -> dict[str, Any]:
    return tools.write_scratch(req.content)


@app.post("/api/demo-telemetry")
async def demo_telemetry(t: DemoTelemetry) -> dict[str, Any]:
    updates: list[str] = []
    with db.tx() as conn:
        art = db.get_artifact(conn, t.demo_id)
        targets = subagents.demo_targets(art["payload_text"]) if art else []
        if t.challenge_solved:
            for nid in targets:
                n = db.get_node(conn, nid)
                if n:
                    db.update_node_fields(conn, nid, cue_geometric=cm.update_cue(n["cue_geometric"]))
                    updates.append(nid)
        if t.session_id and db.load_session(conn, t.session_id):
            s = db.load_session(conn, t.session_id)
            s["history_steps"].append({"kind": "DEMO_TELEMETRY", "node_id": targets[0] if targets else None,
                                       "step_index": s["current_step_index"], "demo_id": t.demo_id, "params": t.params,
                                       "challenge_solved": t.challenge_solved, "summary": t.summary})
            db.save_session(conn, s)
    if updates:
        await hub.broadcast("graph_updated", {"reason": "demo_challenge_solved"})
    return {"recorded": True, "cue_updates": updates}


@app.get("/api/settings", response_model=SettingsOut)
async def get_settings() -> dict[str, Any]:
    return _settings_out()


@app.put("/api/settings", response_model=SettingsOut)
async def put_settings(req: SettingsUpdate) -> dict[str, Any]:
    settings.update(req.provider, {"anthropic": req.anthropic_api_key, "gemini": req.gemini_api_key,
                                   "openai": req.openai_api_key, "openrouter": req.openrouter_api_key,
                                   "deepgram": req.deepgram_api_key}, req.model_overrides)
    out = _settings_out()
    await hub.broadcast("stats", compute_stats())
    return out


# ------------------------------------------------------------------ WebSockets
@app.websocket("/ws")
async def ws_main(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "payload": {"llm_engine": llm.describe_engine()}, "ts": db.now_iso()}))
        await ws.send_text(json.dumps({"type": "stats", "payload": compute_stats(), "ts": db.now_iso()}, default=str))
        while True:
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong", "payload": {}, "ts": db.now_iso()}))
            elif msg.get("type") == "scratch_write":
                data = tools.write_scratch(str(msg.get("content", "")))
                await hub.broadcast("scratch_update", data)
    except (WebSocketDisconnect, RuntimeError, json.JSONDecodeError):
        pass
    finally:
        hub.disconnect(ws)


@app.websocket("/ws/dictation")
async def ws_dictation(ws: WebSocket) -> None:
    """Relay browser audio to Deepgram nova-3 when DEEPGRAM_API_KEY is configured."""
    await ws.accept()
    key = settings.keys.get("deepgram")
    if not key:
        await ws.send_text(json.dumps({"type": "unavailable", "reason": "DEEPGRAM_API_KEY not configured"}))
        await ws.close()
        return
    import websockets
    url = ("wss://api.deepgram.com/v1/listen?model=nova-3&punctuate=true&smart_format=true&interim_results=true"
           "&filler_words=true")
    headers = {"Authorization": f"Token {key}"}
    try:
        try:
            dg = await websockets.connect(url, additional_headers=headers)
        except TypeError:
            dg = await websockets.connect(url, extra_headers=headers)
    except Exception as e:
        await ws.send_text(json.dumps({"type": "unavailable", "reason": f"Deepgram connection failed: {e}"}))
        await ws.close()
        return

    async def upstream() -> None:
        try:
            while True:
                msg = await ws.receive()
                if msg.get("bytes"):
                    await dg.send(msg["bytes"])
                elif msg.get("text") == "close" or msg.get("type") == "websocket.disconnect":
                    break
        finally:
            await dg.send(json.dumps({"type": "CloseStream"}))

    async def downstream() -> None:
        async for raw in dg:
            data = json.loads(raw)
            alt = (data.get("channel") or {}).get("alternatives") or [{}]
            text = alt[0].get("transcript", "")
            if text:
                await ws.send_text(json.dumps({"type": "transcript", "text": text, "is_final": bool(data.get("is_final")),
                                               "words": [{"word": w.get("word"), "start": w.get("start"), "end": w.get("end")}
                                                         for w in alt[0].get("words", [])]}))

    try:
        await asyncio.gather(upstream(), downstream())
    except Exception:
        pass
    finally:
        await dg.close()
        try:
            await ws.close()
        except RuntimeError:
            pass
