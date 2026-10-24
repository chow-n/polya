"""Synthetic learners for the model scoreboard and the difficulty controller (docs/specs/model-eval-85 FR6).

Lets both be exercised before real answers exist. Stdlib + cognitive_math only.

  python -m backend.simulate            scoreboard for a synthetic BKT learner + a controller run, printed
  python -m backend.simulate --answers 600 --seed 3 --target 0.8
"""
from __future__ import annotations

import argparse
import random
import sqlite3
from dataclasses import dataclass, field

from . import cognitive_math as cm
from . import model_eval

PREDICTION_DDL = """CREATE TABLE model_predictions (
    p_combined REAL, p_bkt REAL, p_memory REAL, p_node_baseline REAL, p_global_baseline REAL, y INTEGER, success INTEGER)"""
SESSION_DDL = """CREATE TABLE sessions (step_velocity_delta REAL, active_step_payload_json TEXT, updated_at TEXT)"""


@dataclass
class SyntheticLearner:
    """A learner who really follows BKT + forgetting: mastered ideas are answered right with probability
    R·(1 − slip) + (1 − R)·guess, unmastered ones with probability guess; each answer may teach the idea."""
    n_ideas: int = 12
    p_init: float = 0.15
    transit: float = 0.12
    slip: float = 0.08
    guess: float = 0.05
    quality: float = 0.75          # reasoning quality the diagnostician would assign
    mean_gap_days: float = 1.5
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        self.known = [self.rng.random() < self.p_init for _ in range(self.n_ideas)]


def simulate_bkt_learner(answers: int = 300, seed: int = 0, learner: SyntheticLearner | None = None) -> list[dict]:
    """Run the real model update (cm.bkt_update, cm.fsrs_review) against a synthetic learner and log the same
    predictions `orchestrator.log_prediction` logs. Returns one dict per graded answer."""
    rng = random.Random(seed)
    lr = learner or SyntheticLearner(rng=rng)
    # what Pólya believes, starting from the node defaults (backend/db.py)
    p_mastery = [0.15] * lr.n_ideas
    stability = [1.0] * lr.n_ideas
    difficulty = [5.0] * lr.n_ideas
    last_seen = [0.0] * lr.n_ideas
    k_node = [0] * lr.n_ideas
    n_node = [0] * lr.n_ideas
    k_all = n_all = 0
    true_s = [1.0] * lr.n_ideas   # the learner's actual memory stability
    clock = 0.0
    rows = []
    # the effective guess/transit the model applies at this reasoning quality, so the learner matches the model
    _, g_eff = cm.effective_slip_guess(lr.slip, lr.guess, 1, lr.quality, "NONE")
    t_eff = lr.transit * (0.4 + 0.6 * lr.quality)
    for _ in range(answers):
        i = rng.randrange(lr.n_ideas)
        clock += rng.expovariate(1 / lr.mean_gap_days) / lr.n_ideas
        t = clock - last_seen[i]
        r_model = cm.retrievability(t, stability[i])
        r_true = cm.retrievability(t, true_s[i])
        p_true = (r_true * (1 - lr.slip) + (1 - r_true) * g_eff) if lr.known[i] else g_eff
        y = int(rng.random() < p_true)
        pred = cm.predict_correct(p_mastery[i], lr.slip, g_eff, r_model)
        rows.append({**pred, "p_global_baseline": cm.laplace_rate(k_all, n_all),
                     "p_node_baseline": cm.laplace_rate(k_node[i], n_node[i]), "y": y,
                     "success": int(bool(y) and lr.quality >= cm.SUCCESS_MIN_QUALITY)})
        # model update, exactly as apply_assessment does it
        rating = cm.assign_rating(y, "SOLVED_CLEAN" if y else "FAILED", "NONE", lr.quality, 0)
        fs = cm.fsrs_review(stability[i], difficulty[i], t, rating)
        stability[i], difficulty[i] = fs.stability_after, fs.difficulty_after
        p_mastery[i] = cm.bkt_update(p_mastery[i], y, lr.quality, "NONE", lr.slip, lr.guess, lr.transit)
        # the learner's true memory follows the same law; learning happens with probability T_eff
        true_s[i] = cm.update_stability(true_s[i], difficulty[i], r_true, rating)
        if not lr.known[i] and rng.random() < t_eff:
            lr.known[i] = True
        last_seen[i] = clock
        k_all, n_all = k_all + y, n_all + 1
        k_node[i], n_node[i] = k_node[i] + y, n_node[i] + 1
    return rows


def scoreboard_for(rows: list[dict], target: float = cm.DEFAULT_TARGET) -> dict:
    conn = sqlite3.connect(":memory:")
    conn.execute(PREDICTION_DDL)
    conn.execute(SESSION_DDL)
    cols = [name for name, _ in model_eval.PREDICTORS] + ["y", "success"]
    conn.executemany(f"INSERT INTO model_predictions ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     [tuple(r[c] for c in cols) for r in rows])
    return model_eval.scoreboard(conn, target)


# Success probability at practice level 1..4 for a learner of fixed ability: harder cues, fewer successes.
DEFAULT_CURVE = {1: 0.97, 2: 0.90, 3: 0.80, 4: 0.62}


def simulate_controller(answers: int = 300, target: float = cm.DEFAULT_TARGET, seed: int = 0,
                        curve: dict[int, float] | None = None, start_level: int = 1) -> dict:
    """Drive cm.difficulty_controller with a learner whose success depends only on the practice level.
    Misses are logged as PARTIAL so only the success-rate rule acts (hard failures reset Δ, not the level)."""
    rng = random.Random(seed)
    curve = curve or DEFAULT_CURVE
    level, delta = start_level, 1.0
    successes: list[int] = []
    levels: list[int] = []
    for _ in range(answers):
        y = int(rng.random() < curve[level])
        successes.append(y)
        levels.append(level)
        reading = cm.difficulty_controller(delta, level, successes[-cm.SUCCESS_WINDOW:],
                                           {"outcome": "SOLVED_CLEAN" if y else "PARTIAL", "miss_class": "NONE"}, target)
        level, delta = reading.cue_level, reading.delta
    settled = successes[answers // 3:]
    return {"target": target, "answers": answers, "settled_success": sum(settled) / len(settled),
            "final_recent_success": cm.recent_success(successes), "mean_level": sum(levels[answers // 3:]) / len(settled),
            "level_share": {lv: levels[answers // 3:].count(lv) / len(settled) for lv in sorted(curve)}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--answers", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--target", type=float, default=cm.DEFAULT_TARGET)
    a = ap.parse_args()
    print("Synthetic BKT learner\n" + model_eval.format_text(scoreboard_for(simulate_bkt_learner(a.answers, a.seed), a.target)))
    c = simulate_controller(a.answers, a.target, a.seed)
    print(f"\nController on a fixed-ability learner (levels 1–4 succeed {list(DEFAULT_CURVE.values())}):")
    print(f"  success after settling {c['settled_success']:.0%} (target {c['target']:.0%}), mean practice level "
          f"{c['mean_level']:.2f}, time at each level " +
          ", ".join(f"L{k} {v:.0%}" for k, v in c["level_share"].items()))


if __name__ == "__main__":
    main()
