"""AI engine chain: Codex CLI, resolution order, in-request fallback, circuit breakers, the optional local-engine hook
and the persisted engine choice (docs/specs/chatgpt-engine). A fake `codex` script stands in for the real CLI."""
from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

import pytest

from backend import config, llm
from backend.config import settings


@pytest.fixture()
def engines(monkeypatch, tmp_path: Path):
    """Real routing (no forced deterministic engine), no API keys, clean breakers, a fake codex on PATH."""
    from backend.tests.conftest import point_config_at
    point_config_at(tmp_path)
    monkeypatch.delenv("POLYA_LLM", raising=False)
    monkeypatch.delenv("LEARNHARNESS_LLM", raising=False)
    monkeypatch.setattr(settings, "keys", {k: "" for k in settings.keys})
    monkeypatch.setattr(settings, "provider", "auto")
    monkeypatch.setattr(llm, "_disabled_until", {})
    monkeypatch.setattr(llm, "_last_error", {})
    monkeypatch.setattr(llm, "_codex_login", (0.0, False))
    monkeypatch.setattr(llm, "LOCAL_ENGINES", {})
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "codex_calls.jsonl"

    def fake_codex(body: str) -> Path:
        script = bin_dir / "codex"
        script.write_text(f"""#!/bin/sh
if [ "$1" = "login" ]; then echo "Logged in using ChatGPT"; exit 0; fi
out=""
prev=""
for a in "$@"; do
  if [ "$prev" = "-o" ]; then out="$a"; fi
  prev="$a"
done
prompt=$(cat)
printf '%s\\n' "$*" >> "{log}"
{body}
""")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return script

    monkeypatch.setattr(config.RuntimeSettings, "codex_cli_path", staticmethod(lambda: str(bin_dir / "codex") if (bin_dir / "codex").exists() else None))
    monkeypatch.setattr(config.RuntimeSettings, "claude_cli_path", staticmethod(lambda: None))
    return {"fake_codex": fake_codex, "log": log}


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_codex_engine_command_line_and_parsing(engines):
    engines["fake_codex"]("""printf '%s' 'Sure: {"answer": "ok", "n": 2}' > "$out"; exit 0""")
    assert llm.engine_chain() == ["codex_cli"]
    res = run(llm.complete_json("sys", "user"))
    assert res.data == {"answer": "ok", "n": 2} and res.engine == "codex_cli"
    args = engines["log"].read_text()
    for flag in ("exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules", "-s read-only", " -"):
        assert flag in args


def test_codex_failure_trips_breaker_and_falls_back(engines):
    engines["fake_codex"]("""echo "usage limit reached" >&2; exit 1""")
    res = run(llm.complete_json("sys", "user"))
    assert res.data is None and res.engine == "codex_cli->deterministic" and "usage limit" in res.error
    assert not llm.codex_available() and llm.engine_chain() == []     # breaker: no 120 s stall on the next step
    assert llm.resolve_engine() == "deterministic"


def test_resolution_orders(engines, monkeypatch):
    engines["fake_codex"]("exit 0")
    monkeypatch.setattr(config.RuntimeSettings, "claude_cli_path", staticmethod(lambda: "/usr/bin/true"))
    monkeypatch.setattr(settings, "keys", {**{k: "" for k in settings.keys}, "openai": "sk-test"})
    assert llm.engine_chain() == ["openai", "claude_cli", "codex_cli"]            # auto: keys → Claude → Codex
    monkeypatch.setattr(settings, "provider", "codex_cli")
    assert llm.engine_chain() == ["codex_cli", "claude_cli"]
    monkeypatch.setattr(settings, "provider", "chatgpt_browser")
    assert llm.engine_chain() == ["codex_cli", "claude_cli"]                       # private engine absent

    class FakeBrowser:
        def available(self) -> bool:
            return True

        async def complete(self, system: str, user: str) -> str:
            raise llm.NeedsUser("login page")

        def status(self) -> dict:
            return {"signed_in": False}

    monkeypatch.setattr(llm, "LOCAL_ENGINES", {"chatgpt_browser": FakeBrowser()})
    assert llm.engine_chain() == ["chatgpt_browser", "codex_cli", "claude_cli"]
    monkeypatch.setattr(settings, "provider", "auto")
    assert "chatgpt_browser" not in llm.engine_chain()                              # Automatic never picks it
    monkeypatch.setattr(settings, "provider", "deterministic")
    assert llm.engine_chain() == []


def test_local_engine_needs_user_falls_through_to_codex(engines, monkeypatch):
    engines["fake_codex"]("""printf '%s' '{"answer": "from codex"}' > "$out"; exit 0""")
    events = []

    async def capture(type_, payload=None):
        events.append((type_, payload))

    from backend.hub import hub
    monkeypatch.setattr(hub, "broadcast", capture)

    class FakeBrowser:
        def available(self) -> bool:
            return True

        async def complete(self, system: str, user: str) -> str:
            raise llm.NeedsUser("verify you are human")

        def status(self) -> dict:
            return {"signed_in": True}

    monkeypatch.setattr(llm, "LOCAL_ENGINES", {"chatgpt_browser": FakeBrowser()})
    monkeypatch.setattr(settings, "provider", "chatgpt_browser")
    res = run(llm.complete_json("sys", "user"))
    assert res.data == {"answer": "from codex"} and res.engine == "chatgpt_browser->codex_cli"
    assert events == [("engine_attention", {"engine": "chatgpt_browser", "reason": "verify you are human"})]
    assert llm.engine_chain()[0] == "codex_cli"                                     # 2-minute attention breaker
    st = llm.engine_status()["chatgpt_browser"]
    assert st["available"] and st["signed_in"] is True and "human" in st["last_error"]


def test_engine_choice_persists_in_prefs(engines):
    from fastapi.testclient import TestClient

    from backend import db
    from backend.main import app
    db.init_db()
    with TestClient(app) as c:
        r = c.put("/api/settings", json={"provider": "codex_cli"})
        assert r.status_code == 200 and r.json()["provider"] == "codex_cli"
        assert "codex_available" in r.json() and r.json()["chatgpt_browser"]["available"] is False
        assert c.post("/api/engines/chatgpt-browser/login").status_code == 404
    assert json.loads(config.prefs_path().read_text())["provider"] == "codex_cli"
    assert config.RuntimeSettings().provider == "codex_cli"                         # survives a restart
    os.environ["POLYA_LLM"] = "deterministic"
    try:
        assert config.RuntimeSettings().provider == "deterministic"                 # the environment still wins
    finally:
        del os.environ["POLYA_LLM"]
