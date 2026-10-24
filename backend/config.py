"""Paths, environment variables and mutable runtime settings.

Environment variables use the `POLYA_` prefix; the pre-rename `LEARNHARNESS_` prefix is still accepted.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path


def env(name: str, default=None):
    """POLYA_<name>, falling back to the legacy LEARNHARNESS_<name>."""
    return os.environ.get(f"POLYA_{name}", os.environ.get(f"LEARNHARNESS_{name}", default))


ROOT = Path(env("ROOT", Path(__file__).resolve().parent.parent))
BACKEND_DIR = ROOT / "backend"
# Starter files shipped with the code (repo or app bundle); copied into the data home on first run.
SEED_WORKSPACE = ROOT / "workspace"
LEGACY_DB = ROOT / "harness.db"
FRONTEND_DIST = Path(env("FRONTEND_DIST", ROOT / "frontend" / "dist"))
APP_MODE = env("APP") == "1"

# Shared data home for the Mac app, ./start.sh and ./polya (docs/specs/mac-app/SPEC.md D2, ui-simplify D5).
LEGACY_HOME = Path.home() / "LearnHarness"
HOME_OVERRIDDEN = env("HOME") is not None
HOME = Path(env("HOME", Path.home() / "Polya"))
WORKSPACE = Path(env("WORKSPACE", HOME / "workspace"))
NOTES_DIR = WORKSPACE / "notes"
PROBLEMS_DIR = WORKSPACE / "problems"
SCRATCH_PATH = WORKSPACE / "scratch.tex"
DB_PATH = Path(env("DB", HOME / "harness.db"))
PORT_FILE = HOME / ".port"

API_PORT = int(env("API_PORT", "8000"))
CLAUDE_CLI_TIMEOUT_S = float(env("CLAUDE_TIMEOUT", "90"))
CODEX_TIMEOUT_S = float(env("CODEX_TIMEOUT", "120"))
SYMPY_TIMEOUT_S = 5
ARXIV_TIMEOUT_S = 6.0

PROVIDERS = ("auto", "anthropic", "gemini", "openai", "openrouter", "claude_cli", "codex_cli", "chatgpt_browser",
             "deterministic")

DEFAULT_MODELS = {
    "anthropic": env("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
    "gemini": env("GEMINI_MODEL", "gemini-2.5-flash"),
    "openai": env("OPENAI_MODEL", "gpt-4.1-mini"),
    "openrouter": env("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"),
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


def migrate_legacy_home(home: Path, legacy: Path) -> str | None:
    """Pre-rename data lived in ~/LearnHarness. Move it to ~/Polya once and leave a symlink at the old path.
    If both exist, ~/Polya wins and the old folder is left untouched."""
    if home.exists() or home.is_symlink() or not legacy.is_dir() or legacy.is_symlink():
        return None
    legacy.rename(home)
    legacy.symlink_to(home, target_is_directory=True)
    return f"moved {legacy} -> {home} (symlink left at old path)"


PREF_DEFAULTS = {"target_success": 0.85, "provider": None}   # provider None = POLYA_LLM or "auto"
TARGET_CHOICES = (0.80, 0.85, 0.90)


def prefs_path() -> Path:
    return HOME / "prefs.json"


def load_prefs() -> dict:
    """Non-secret preferences (docs/specs/model-eval-85 D3). Missing or corrupt file → defaults."""
    out = dict(PREF_DEFAULTS)
    try:
        data = json.loads(prefs_path().read_text())
    except (OSError, ValueError):
        return out
    if not isinstance(data, dict):
        return out
    if data.get("target_success") in TARGET_CHOICES:
        out["target_success"] = data["target_success"]
    if data.get("provider") in PROVIDERS:
        out["provider"] = data["provider"]
    return out


def save_prefs(**changes) -> dict:
    """Merge and write atomically (temp file + rename). API keys never go here."""
    prefs = {**load_prefs(), **{k: v for k, v in changes.items() if k in PREF_DEFAULTS}}
    path = prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".prefs-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(prefs, f, indent=2)
    os.replace(tmp, path)
    return prefs


class RuntimeSettings:
    """Process-wide settings, editable from the UI (PUT /api/settings). Keys never leave the process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # POLYA_LLM wins (tests force "deterministic"); otherwise the engine chosen in Settings (chatgpt-engine FR6)
        self.provider: str = env("LLM") or load_prefs()["provider"] or "auto"
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

    @staticmethod
    def codex_cli_path() -> str | None:
        return shutil.which("codex") or next((str(p) for p in (Path.home() / ".local/bin/codex",) if p.exists()), None)


settings = RuntimeSettings()
