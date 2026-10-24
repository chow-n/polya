"""Watchdog monitor for workspace/scratch.tex and workspace/{notes,problems}/ → WebSocket events."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import config, tools
from .hub import hub

DEBOUNCE_S = 0.15


class _Handler(FileSystemEventHandler):
    def __init__(self) -> None:
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self.last_scratch_sync: Optional[str] = None

    def _debounced(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last.get(key, 0.0) < DEBOUNCE_S:
                return False
            self._last[key] = now
            return True

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory or event.event_type not in ("modified", "created", "moved", "deleted"):
            return
        path = Path(getattr(event, "dest_path", "") or event.src_path).resolve()
        if path.name.startswith(".") or path.suffix in (".swp", ".swx") or path.name.endswith("~"):
            return
        if path == config.SCRATCH_PATH.resolve():
            if self._debounced("scratch"):
                data = tools.read_scratch()
                self.last_scratch_sync = data["modified_at"]
                hub.broadcast_threadsafe("scratch_update", data)
            return
        for d in (config.NOTES_DIR, config.PROBLEMS_DIR):
            try:
                rel = path.relative_to(d.resolve())
            except ValueError:
                continue
            if self._debounced(str(path)):
                hub.broadcast_threadsafe("notes_changed", {"path": str(Path(d.name) / rel), "event": event.event_type})
            return


class ScratchpadWatcher:
    def __init__(self) -> None:
        self.handler = _Handler()
        self.observer: Optional[Observer] = None

    def start(self) -> None:
        for d in (config.WORKSPACE, config.NOTES_DIR, config.PROBLEMS_DIR):
            d.mkdir(parents=True, exist_ok=True)
        if not config.SCRATCH_PATH.exists():
            config.SCRATCH_PATH.write_text("% LearnHarness scratchpad — saved edits stream live into the UI.\n")
        self.observer = Observer()
        self.observer.schedule(self.handler, str(config.WORKSPACE), recursive=True)
        self.observer.daemon = True
        self.observer.start()

    def stop(self) -> None:
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.observer = None


watcher = ScratchpadWatcher()
