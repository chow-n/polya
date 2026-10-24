"""Isolate every test run: temp database + temp copy of the workspace, deterministic engine, no network."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ["LEARNHARNESS_LLM"] = "deterministic"
os.environ["LEARNHARNESS_OFFLINE"] = "1"

from backend import config  # noqa: E402

REPO_WORKSPACE = Path(__file__).resolve().parents[2] / "workspace"


def point_config_at(tmp: Path) -> None:
    ws = tmp / "workspace"
    if not ws.exists():
        shutil.copytree(REPO_WORKSPACE, ws, ignore=shutil.ignore_patterns("session_*.md"))
    config.WORKSPACE = ws
    config.NOTES_DIR = ws / "notes"
    config.PROBLEMS_DIR = ws / "problems"
    config.SCRATCH_PATH = ws / "scratch.tex"
    config.DB_PATH = tmp / "harness.db"
    config.HOME = tmp
    config.LEGACY_DB = tmp / "no-legacy.db"   # never migrate the developer's real database into a test
    config.SEED_WORKSPACE = REPO_WORKSPACE


@pytest.fixture()
def fresh_db(tmp_path: Path):
    point_config_at(tmp_path)
    from backend import db
    db.init_db()
    return db
