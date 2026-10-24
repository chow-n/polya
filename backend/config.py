"""Paths, environment variables and mutable runtime settings."""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
WORKSPACE = Path(os.environ.get("LEARNHARNESS_WORKSPACE", ROOT / "workspace"))
NOTES_DIR = WORKSPACE / "notes"
PROBLEMS_DIR = WORKSPACE / "problems"
SCRATCH_PATH = WORKSPACE / "scratch.tex"
DB_PATH = Path(os.environ.get("LEARNHARNESS_DB", ROOT / "harness.db"))

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
