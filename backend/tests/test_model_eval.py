"""Model scoreboard metrics, the 85% difficulty controller and the synthetic-learner simulation
(docs/specs/model-eval-85)."""
from __future__ import annotations

import math

import pytest

from backend import cognitive_math as cm
from backend import simulate

CLEAN = {"outcome": "SOLVED_CLEAN", "miss_class": "NONE"}


def test_metrics_against_hand_computed_values():
    pairs = [(0.8, 1), (0.4, 0)]
    assert cm.log_loss(pairs) == pytest.approx(-(math.log(0.8) + math.log(0.6)) / 2)
    assert cm.mean_brier(pairs) == pytest.approx((0.04 + 0.16) / 2)
    assert cm.log_loss([(1.0, 0)]) == pytest.approx(-math.log(cm.P_CLIP))   # clipped, never infinite
    assert cm.log_loss([]) is None and cm.mean_brier([]) is None
    bins = cm.calibration_bins([(0.1, 0), (0.15, 1), (0.95, 1)])
    assert len(bins) == 5 and bins[0]["count"] == 2 and bins[0]["observed"] == 0.5 and bins[4]["count"] == 1
    assert bins[2]["mean_predicted"] is None


def test_auc_with_ties_and_degenerate_cases():
    # positives 0.9, 0.5; negatives 0.5, 0.1 → pairs won 1 + 1 + ½ (tie) + 1 = 3.5 of 4
    assert cm.auc([(0.9, 1), (0.5, 1), (0.5, 0), (0.1, 0)]) == pytest.approx(0.875)
    assert cm.auc([(0.3, 1), (0.3, 0)]) == pytest.approx(0.5)
    assert cm.auc([(0.2, 1), (0.9, 1)]) is None   # one class only → undefined, shown as "—"


def test_predictions_and_baselines():
    p = cm.predict_correct(0.6, 0.1, 0.2, 0.5)
    assert p["p_bkt"] == pytest.approx(0.6 * 0.9 + 0.4 * 0.2)
    assert p["p_memory"] == 0.5
    assert p["p_combined"] == pytest.approx(0.3 * 0.9 + 0.7 * 0.2)
    assert cm.laplace_rate(0, 0) == 0.5 and cm.laplace_rate(3, 4) == pytest.approx(4 / 6)


def test_recent_success_ewma():
    assert cm.recent_success([]) is None
    assert cm.recent_success([1]) == 1.0
    assert cm.recent_success([0, 1]) == pytest.approx(1 / 1.7)          # newest weighs 1, previous 0.7
    assert cm.recent_success([0] * 30 + [1] * 10) == 1.0                 # only the last 10 count


def test_controller_waits_for_three_answers_then_uses_bands():
    r = cm.difficulty_controller(1.0, 1, [1, 1], CLEAN)
    assert (r.action, r.delta, r.cue_level) == ("WARMING_UP", 1.0, 1)
    assert "2/3" in r.summary
    up = cm.difficulty_controller(1.0, 1, [1] * 10, CLEAN)
    assert (up.action, up.delta, up.cue_level) == ("HARDER", 1.5, 2)
    assert "bigger steps" in up.summary and "100%" in up.summary
    top = cm.difficulty_controller(2.5, 4, [1] * 10, CLEAN)
    assert (top.delta, top.cue_level) == (2.5, 4)
    partial = {"outcome": "PARTIAL", "miss_class": "NONE"}
    down = cm.difficulty_controller(1.5, 3, [1, 0, 0, 1, 0], partial)
    assert (down.action, down.delta, down.cue_level) == ("EASIER", 1.0, 2)
    floor = cm.difficulty_controller(0.5, 1, [0, 0, 0], partial)
    assert (floor.delta, floor.cue_level) == (0.5, 1)
    # one older miss: ≈ 0.89, inside 0.85 ± 0.07
    hold = cm.difficulty_controller(1.5, 2, [1, 1, 1, 1, 1, 1, 0, 1, 1, 1], CLEAN)
    assert hold.action == "HOLD" and (hold.delta, hold.cue_level) == (1.5, 2)
    # the same history is above 0.80 + 0.07, so an 80% target asks for harder work
    assert cm.difficulty_controller(1.5, 2, [1, 1, 1, 1, 1, 1, 0, 1, 1, 1], CLEAN, target=0.80).action == "HARDER"


def test_simulated_bkt_learner_beats_baselines():
    sb = simulate.scoreboard_for(simulate.simulate_bkt_learner(300, seed=0))
    ll = {p["name"]: p["log_loss"] for p in sb["predictors"]}
    assert sb["n"] == 300 and sb["enough_data"]
    assert ll["p_bkt"] < ll["p_global_baseline"]
    assert ll["p_combined"] < ll["p_global_baseline"]


@pytest.mark.parametrize("target", [0.80, 0.85, 0.90])
def test_simulated_controller_tracks_target(target):
    run = simulate.simulate_controller(300, target, seed=1)
    assert abs(run["settled_success"] - target) <= 0.08


def test_lower_target_means_harder_practice():
    easy = simulate.simulate_controller(600, 0.90, seed=2)["mean_level"]
    hard = simulate.simulate_controller(600, 0.80, seed=2)["mean_level"]
    assert hard > easy
