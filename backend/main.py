"""FastAPI REST endpoints and the bi-directional WebSocket hub (see docs/API.md)."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import cognitive_math as cm
from . import config, db, llm, model_eval, native_speech, seed, tools
from .agents import orchestrator, subagents, tutor
from .config import settings
from .hub import hub
from .models import (
    ALL_AGENTS, ArtifactOut, ChunkEvaluation, ChunkRequest, CreateSessionRequest, DemoTelemetry, DuelReply, DuelRequest,
    DueItem, ExplainReply, ExplainRequest, ExplainThread, GraphOut, HintOut, HintRequest, LearnRequest, LearnTurn,
    ModelEvalOut, SayBackOut, SayBackRequest, NodeDetail, PaperCreate, PaperDetail, PaperOut, PracticeQueueItem,
    ScratchOut, ScratchWrite, SessionOut,
    SessionState, SettingsOut, SettingsUpdate, StatsOut, StepResult, StepSubmission, SubagentRunRequest, WorkspaceFile,
    WorkspaceFileContent,
)
from .papers import service as papers
from .scratchpad_watcher import watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub.loop = asyncio.get_running_loop()
    if not config.HOME_OVERRIDDEN:
        moved = config.migrate_legacy_home(config.HOME, config.LEGACY_HOME)
        if moved:
            print(f"[polya] {moved}", flush=True)
    for line in config.ensure_home(config.DB_PATH, config.WORKSPACE, config.LEGACY_DB, config.SEED_WORKSPACE):
        print(f"[polya] migrated {line}", flush=True)
    db.init_db()
    await seed.seed_if_empty()
    watcher.start()
    try:
        yield
    finally:
        watcher.stop()
        for eng in llm.LOCAL_ENGINES.values():   # e.g. close the ChatGPT browser window with the app
            if hasattr(eng, "aclose"):
                await eng.aclose()


app = FastAPI(title="Pólya", version="0.5.0", lifespan=lifespan)
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
    eng = llm.engine_status()
    return {"provider": settings.provider, "active_engine": llm.describe_engine(), "keys_present": llm.keys_present(),
            "deepgram_available": bool(settings.keys.get("deepgram")),
            "native_dictation_available": native_speech.available(), "claude_cli_available": llm.claude_cli_available(),
            "codex_available": eng["codex_available"], "chatgpt_browser": eng["chatgpt_browser"],
            "model_overrides": dict(settings.models), "target_success": config.load_prefs()["target_success"],
            "fetch_sources": config.load_prefs()["fetch_sources"]}


# ------------------------------------------------------------------ REST
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "llm_engine": llm.describe_engine(), "app_mode": config.APP_MODE,
            "data_home": str(config.HOME)}


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
    if req.target_success is not None:
        target = next((t for t in config.TARGET_CHOICES if abs(t - req.target_success) < 1e-9), None)
        if target is None:
            raise HTTPException(422, f"target_success must be one of {list(config.TARGET_CHOICES)}")
        config.save_prefs(target_success=target)
    if req.fetch_sources is not None:
        config.save_prefs(fetch_sources=req.fetch_sources)
    if req.provider is not None:
        config.save_prefs(provider=req.provider)   # the engine choice survives restarts (chatgpt-engine FR6)
    settings.update(req.provider, {"anthropic": req.anthropic_api_key, "gemini": req.gemini_api_key,
                                   "openai": req.openai_api_key, "openrouter": req.openrouter_api_key,
                                   "deepgram": req.deepgram_api_key}, req.model_overrides)
    out = _settings_out()
    await hub.broadcast("stats", compute_stats())
    return out


# ------------------------------------------------------------------ research papers (docs/specs/paper-reading)
@app.get("/api/papers", response_model=list[PaperOut])
async def list_papers() -> list[dict[str, Any]]:
    with db.ro() as conn:
        return [papers.paper_out(conn, p) for p in papers.all_papers(conn)]


@app.post("/api/papers", response_model=PaperOut)
async def create_paper(req: PaperCreate) -> dict[str, Any]:
    p = await papers.create(arxiv=req.arxiv or "", workspace_path=req.workspace_path or "")
    with db.ro() as conn:
        return papers.paper_out(conn, p)


@app.post("/api/papers/upload", response_model=PaperOut)
async def upload_paper(request: Request, filename: str = Query("paper.pdf")) -> dict[str, Any]:
    """Body = the PDF bytes (Content-Type application/pdf)."""
    data = await request.body()
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(413, "PDF larger than 60 MB")
    p = await papers.create(upload=(filename, data))
    with db.ro() as conn:
        return papers.paper_out(conn, p)


@app.get("/api/papers/{paper_id}", response_model=PaperDetail)
async def get_paper(paper_id: str) -> dict[str, Any]:
    with db.ro() as conn:
        p = papers.get(conn, paper_id)
        if not p:
            raise HTTPException(404, "paper not found")
        return papers.paper_detail(conn, p)


@app.post("/api/papers/{paper_id}/sources/refresh", response_model=PaperDetail)
async def refresh_paper_sources(paper_id: str) -> dict[str, Any]:
    with db.ro() as conn:
        if not papers.get(conn, paper_id):
            raise HTTPException(404, "paper not found")
    await papers.refresh_sources(paper_id)
    with db.ro() as conn:
        return papers.paper_detail(conn, papers.get(conn, paper_id))


@app.post("/api/papers/{paper_id}/session", response_model=SessionState)
async def start_paper_session(paper_id: str) -> dict[str, Any]:
    return await orchestrator.create_paper_session(paper_id)


@app.post("/api/engines/chatgpt-browser/login")
async def chatgpt_browser_login() -> dict[str, Any]:
    """Open the private ChatGPT browser engine's window for a manual sign-in (chatgpt-engine FR5)."""
    eng = llm.local_engine("chatgpt_browser")
    if not eng or not hasattr(eng, "login"):
        raise HTTPException(404, "The ChatGPT browser engine is not installed on this Mac.")
    return await eng.login()


@app.get("/api/model-eval", response_model=ModelEvalOut)
async def get_model_eval() -> dict[str, Any]:
    with db.ro() as conn:
        return model_eval.scoreboard(conn, config.load_prefs()["target_success"])


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
    """Dictation: Deepgram nova-3 relay when DEEPGRAM_API_KEY is set, else on-device macOS speech in the app,
    else `unavailable` (the browser then uses its own SpeechRecognition)."""
    await ws.accept()
    key = settings.keys.get("deepgram")
    if not key:
        if native_speech.available():
            await _native_dictation(ws)
            return
        await ws.send_text(json.dumps({"type": "unavailable",
                                       "reason": "DEEPGRAM_API_KEY not configured; " + native_speech.unavailable_reason()}))
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

    await ws.send_text(json.dumps({"type": "ready", "engine": "deepgram"}))

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


async def _native_dictation(ws: WebSocket) -> None:
    ok, reason = await native_speech.ensure_authorized()
    if not ok:
        await ws.send_text(json.dumps({"type": "unavailable", "reason": reason}))
        await ws.close()
        return
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    dictation = native_speech.NativeDictation(lambda m: loop.call_soon_threadsafe(queue.put_nowait, m))
    try:
        dictation.start()
    except Exception as e:
        await ws.send_text(json.dumps({"type": "unavailable", "reason": str(e)}))
        await ws.close()
        return
    await ws.send_text(json.dumps({"type": "ready", "engine": "native"}))

    async def downstream() -> None:
        while True:
            await ws.send_text(json.dumps(await queue.get()))

    async def upstream() -> None:   # the client's audio frames are not needed: the mic is captured natively
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect" or msg.get("text") == "close":
                return

    down = asyncio.create_task(downstream())
    try:
        await upstream()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        down.cancel()
        dictation.stop()


# ------------------------------------------------------------------ explanations (docs/specs/explain, docs/specs/learn-chat)
@app.get("/api/sessions/{session_id}/explain", response_model=ExplainThread)
async def explain_thread(session_id: str) -> dict[str, Any]:
    return tutor.get_thread(session_id)


@app.post("/api/sessions/{session_id}/explain", response_model=ExplainReply)
async def explain_ask(session_id: str, req: ExplainRequest) -> dict[str, Any]:
    return await tutor.ask(session_id, req.action, req.message, req.trigger, req.step_index, req.attempt)


@app.post("/api/sessions/{session_id}/say-back", response_model=SayBackOut)
async def explain_say_back(session_id: str, req: SayBackRequest) -> dict[str, Any]:
    out = await tutor.say_back(session_id, req.text, req.confidence, req.message_id)
    await hub.broadcast("graph_updated", {"reason": "say_back"})
    return out


@app.post("/api/sessions/{session_id}/learn", response_model=LearnTurn)
async def learn_chat(session_id: str, req: LearnRequest) -> dict[str, Any]:
    out = await tutor.learn_turn(session_id, req.action, req.message)
    await hub.broadcast("graph_updated", {"reason": "learn_chat"})
    return out



# ------------------------------------------------------------------ built frontend (single-process / app mode)
def mount_frontend(application: FastAPI, dist) -> bool:
    """Serve frontend/dist at / with SPA fallback; /api and /ws routes registered above take precedence."""
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    index = dist / "index.html"
    if not index.exists():
        return False
    if (dist / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    root = dist.resolve()

    @application.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith(("api/", "ws")):
            raise HTTPException(404, "not found")
        candidate = (dist / full_path).resolve()
        if full_path and str(candidate).startswith(str(root)) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    return True


mount_frontend(app, config.FRONTEND_DIST)

