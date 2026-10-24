"""The model scoreboard (docs/specs/model-eval-85): how well each predictor anticipated your graded answers.

Stdlib + cognitive_math only, so `./polya eval` can run it against harness.db without the server.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import cognitive_math as cm

PREDICTORS = (
    ("p_combined", "Mastery × memory"),
    ("p_bkt", "Mastery only"),
    ("p_memory", "Memory only"),
    ("p_node_baseline", "Your accuracy on this idea"),
    ("p_global_baseline", "Your overall accuracy"),
)


def _controller_state(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT step_velocity_delta, active_step_payload_json FROM sessions "
                       "ORDER BY updated_at DESC, rowid DESC LIMIT 1").fetchone()
    if not row:
        return {"delta": None, "practice_level": None, "last_action": None, "last_summary": None}
    try:
        ctl = json.loads(row[1]).get("_meta", {}).get("_controller", {})
    except ValueError:
        ctl = {}
    last = ctl.get("last_reading") or {}
    return {"delta": row[0], "practice_level": ctl.get("cue_level"), "last_action": last.get("action"),
            "last_summary": last.get("summary")}


def scoreboard(conn: sqlite3.Connection, target: float) -> dict[str, Any]:
    cols = ", ".join(name for name, _ in PREDICTORS)
    rows = conn.execute(f"SELECT {cols}, y, success FROM model_predictions ORDER BY rowid").fetchall()
    n = len(rows)
    predictors = []
    for i, (name, label) in enumerate(PREDICTORS):
        scored = cm.score_predictor(name, [(r[i], r[len(PREDICTORS)]) for r in rows])
        predictors.append({**scored, "label": label, "baseline": name.endswith("_baseline")})
    successes = [r[len(PREDICTORS) + 1] for r in rows]
    window = successes[-cm.SUCCESS_WINDOW:]
    return {
        "n": n, "enough_data": n >= cm.ENOUGH_ANSWERS, "min_answers": cm.ENOUGH_ANSWERS, "predictors": predictors,
        "controller": {"target": target, "recent_success": cm.recent_success(successes), "window_n": len(window),
                       "band": cm.SUCCESS_BAND, **_controller_state(conn)},
    }


def format_text(sb: dict[str, Any]) -> str:
    """Terminal rendering shared by `./polya eval`."""
    def f(x: Any, fmt: str) -> str:
        return "—" if x is None else format(x, fmt)

    lines = [f"How well Pólya predicts you · {sb['n']} graded answer{'s' if sb['n'] != 1 else ''}"]
    if sb["n"] == 0:
        lines.append(f"  No answers yet. Not enough answers yet to score the model (it needs {sb['min_answers']}).")
    elif not sb["enough_data"]:
        lines.append(f"  Not enough answers yet (need {sb['min_answers']}); numbers below are noisy.")
    if sb["n"]:
        lines.append(f"  {'predictor':<38}{'log-loss':>9}{'Brier':>8}{'AUC':>7}   calibration (predicted→observed)")
        for p in sb["predictors"]:
            cal = "  ".join(f"{b['mean_predicted']:.2f}→{b['observed']:.2f}({b['count']})"
                            for b in p["calibration_bins"] if b["count"])
            tag = " (baseline)" if p["baseline"] else ""
            lines.append(f"  {p['label'] + tag:<38}{f(p['log_loss'], '.3f'):>9}{f(p['brier'], '.3f'):>8}"
                         f"{f(p['auc'], '.2f'):>7}   {cal}")
        lines.append("  Lower log-loss and Brier are better; AUC 0.5 = chance, 1.0 = perfect ranking.")
    c = sb["controller"]
    rs = "— (no answers yet)" if c["recent_success"] is None else f"{c['recent_success']:.0%} over the last {c['window_n']}"
    lines.append(f"Difficulty target {c['target']:.0%} · recent success {rs}"
                 + (f" · step size Δ {c['delta']:.1f}" if c["delta"] is not None else "")
                 + (f" · practice level {c['practice_level']}" if c["practice_level"] else ""))
    if c.get("last_summary"):
        lines.append(f"  last adjustment: {c['last_summary']}")
    return "\n".join(lines)
