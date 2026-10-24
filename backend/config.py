"""Paths, environment variables and mutable runtime settings."""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

ROOT = Path(os.environ.get("LEARNHARNESS_ROOT", Path(__file__).resolve().parent.parent))
BACKEND_DIR = ROOT / "backend"
# Starter files shipped with the code (repo or app bundle); copied into the data home on first run.
SEED_WORKSPACE = ROOT / "workspace"
LEGACY_DB = ROOT / "harness.db"
FRONTEND_DIST = Path(os.environ.get("LEARNHARNESS_FRONTEND_DIST", ROOT / "frontend" / "dist"))
APP_MODE = os.environ.get("LEARNHARNESS_APP") == "1"

# Shared data home for the Mac app, ./start.sh and ./harness-cli (docs/specs/mac-app/SPEC.md D2).
HOME = Path(os.environ.get("LEARNHARNESS_HOME", Path.home() / "LearnHarness"))
WORKSPACE = Path(os.environ.get("LEARNHARNESS_WORKSPACE", HOME / "workspace"))
NOTES_DIR = WORKSPACE / "notes"
PROBLEMS_DIR = WORKSPACE / "problems"
SCRATCH_PATH = WORKSPACE / "scratch.tex"
DB_PATH = Path(os.environ.get("LEARNHARNESS_DB", HOME / "harness.db"))
PORT_FILE = HOME / ".port"

API_PORT = int(os.environ.get("LEARNHARNESS_API_PORT", "8000"))
CLAUDE_CLI_TIMEOUT_S = float(os.environ.get("LEARNHARNESS_CLAUDE_TIMEOUT", "90"))
SYMPY_TIMEOUT_S = 5
ARXIV_TIMEOUT_S = 6.0

PROVIDERS = ("auto", "anthropic", "gemini", "openai", "openrouter", "claude_cli", "deterministic")

DEFAULT_MODELS = {
    "anthropic": os.environ.get("LEARNHARNESS_ANTHROPIC_MODEL", "claude-sonnet-5-5"),
    "gemini": os.environ.get("LEARNHARNESS_GEMINI_MODEL", "gemini-2.5-flash"),
    "openai": os.environ.get("LEARNHARNESS_OPENAI_MODEL", "gpt-4.1-mini"),
    "openrouter": os.environ.get("LEARNHARNESS_OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"),
}


def ensure_home(db_path: Path, workspace: Path, seed_db: Path, seed_workspace: Path) -> list[str]:
    """One-time migration into the data home: copy (never move) the legacy repo database and the starter
    workspace when the targets do not exist yet. Returns a list of what was copied."""
    import sqlite3

    copied = []
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists() and seed_db.exists() and seed_db.resolve() != db_path.resolve():
        src = sqlite3.connect(str(seed_db))
        dst = sqlite3.connect(str(db_path))
        with dst:
            src.backup(dst)   # consistent copy even with a live WAL
        src.close()
        dst.close()
        copied.append(f"database {seed_db} -> {db_path}")
    if not workspace.exists() and seed_workspace.exists() and seed_workspace.resolve() != workspace.resolve():
        shutil.copytree(seed_workspace, workspace)
        copied.append(f"workspace {seed_workspace} -> {workspace}")
    for d in (workspace / "notes", workspace / "problems"):
        d.mkdir(parents=True, exist_ok=True)
    return copied


class RuntimeSettings:
    """Process-wide settings, editable from the UI (PUT /api/settings). Keys never leave the process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.provider: str = os.environ.get("LEARNHARNESS_LLM", "auto")
        if self.provider not in PROVIDERS:
            self.provider = "auto"
        self.keys: dict[str, str] = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
            "gemini": os.environ.get("GEMINI_API_KEY", ""),
            "openai": os.environ.get("OPENAI_API_KEY", ""),
            "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
            "deepgram": os.environ.get("DEEPGRAM_API_KEY", ""),
        }
        self.models: dict[str, str] = dict(DEFAULT_MODELS)

    def update(self, provider: str | None = None, keys: dict[str, str | None] | None = None,
               models: dict[str, str] | None = None) -> None:
        with self._lock:
            if provider and provider in PROVIDERS:
                self.provider = provider
            for k, v in (keys or {}).items():
                if v is not None and k in self.keys:
                    self.keys[k] = v.strip()
            for k, v in (models or {}).items():
                if k in self.models and v:
                    self.models[k] = v

    @staticmethod
    def claude_cli_path() -> str | None:
        return shutil.which("claude")


settings = RuntimeSettings()
