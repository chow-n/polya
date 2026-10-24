"""WebSocket broadcast hub shared by the API, the sub-agents and the scratchpad watcher."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket

from .db import now_iso


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, type_: str, payload: dict[str, Any] | None = None) -> None:
        msg = json.dumps({"type": type_, "payload": payload or {}, "ts": now_iso()}, default=str)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def broadcast_threadsafe(self, type_: str, payload: dict[str, Any] | None = None) -> None:
        """For callers on non-event-loop threads (the watchdog observer)."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(type_, payload), self.loop)


hub = Hub()
