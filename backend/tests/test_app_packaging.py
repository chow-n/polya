"""Mac-app prerequisites: data-home migration, single-process frontend serving, app-mode health."""
from __future__ import annotations

import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import config


def test_ensure_home_copies_once_and_never_moves(tmp_path):
    legacy = tmp_path / "repo" / "harness.db"
    legacy.parent.mkdir()
    with sqlite3.connect(legacy) as c:
        c.execute("CREATE TABLE t (x INTEGER)")
        c.execute("INSERT INTO t VALUES (42)")
    seed_ws = tmp_path / "repo" / "workspace"
    (seed_ws / "notes").mkdir(parents=True)
    (seed_ws / "scratch.tex").write_text("% seed")
    home = tmp_path / "LearnHarness"
    copied = config.ensure_home(home / "harness.db", home / "workspace", legacy, seed_ws)
    assert len(copied) == 2 and legacy.exists()
    with sqlite3.connect(home / "harness.db") as c:
        assert c.execute("SELECT x FROM t").fetchone()[0] == 42
    assert (home / "workspace" / "scratch.tex").read_text() == "% seed"
    assert (home / "workspace" / "problems").is_dir()
    (home / "workspace" / "scratch.tex").write_text("% mine")
    assert config.ensure_home(home / "harness.db", home / "workspace", legacy, seed_ws) == []
    assert (home / "workspace" / "scratch.tex").read_text() == "% mine"   # user data is never overwritten


def test_spa_serving_and_api_precedence(tmp_path):
    from backend.main import mount_frontend
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>LH</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    app = FastAPI()

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    assert mount_frontend(app, dist)
    c = TestClient(app)
    assert c.get("/api/ping").json() == {"ok": True}
    assert c.get("/").text == "<html>LH</html>"
    assert c.get("/some/client/route").text == "<html>LH</html>"   # SPA fallback
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/favicon.svg").text == "<svg/>"
    assert c.get("/api/missing").status_code == 404
    assert c.get("/../../etc/passwd").text == "<html>LH</html>"   # traversal falls back to index
    assert not mount_frontend(FastAPI(), tmp_path / "nope")


def test_frozen_verifier_command_and_entrypoint():
    import subprocess
    import sys
    from pathlib import Path

    from backend import tools
    argv, stdin = tools.verifier_command("print('VERIFIED: x')", frozen=False)
    assert argv[1:3] == ["-I", "-c"] and stdin is None
    argv, stdin = tools.verifier_command("print('VERIFIED: x')", frozen=True)
    assert argv[1:] == ["--lh-verify"] and stdin == "print('VERIFIED: x')"
    # the launcher's --lh-verify entry point runs the sandbox prelude + code from stdin, as the frozen app does
    launcher = Path(__file__).resolve().parents[2] / "macos" / "launcher.py"
    code = tools.SANDBOX_PRELUDE + "\nimport sympy as sp\nprint('VERIFIED:', sp.Integer(2) + 2)\n"
    out = subprocess.run([sys.executable, str(launcher), "--lh-verify"], input=code, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0 and "VERIFIED: 4" in out.stdout
    blocked = subprocess.run([sys.executable, str(launcher), "--lh-verify"], input=tools.SANDBOX_PRELUDE + "\nimport socket\n",
                             capture_output=True, text=True, timeout=30)
    assert blocked.returncode != 0 and "blocked" in blocked.stderr


def test_native_dictation_only_in_app_mode():
    from backend import native_speech
    assert config.APP_MODE is False
    assert native_speech.available() is False
    assert "LearnHarness.app" in native_speech.unavailable_reason()
