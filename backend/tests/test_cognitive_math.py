"""Unit tests for FSRS-v5, extended BKT, active probing, Brier/Murphy, hypercorrection, Δ-controller."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from backend import cognitive_math as cm


# ------------------------------------------------------------------ §3.1 FSRS / Bjork
def test_fsrs_bjork_disuse():
    # retrievability: R(0)=1, monotone decay, R(S·81/19·(1/0.81−1)) = 0.9 by construction of the curve
    S = 5.0
    assert cm.retrievability(0, S) == pytest.approx(1.0)
    rs = [cm.retrievability(t, S) for t in (0, 1, 3, 10, 30, 100)]
    assert all(a > b for a, b in zip(rs, rs[1:]))
    assert cm.retrievability(cm.interval_for_retention(S, 0.9), S) == pytest.approx(0.9, abs=1e-9)
    assert cm.retrievability(10, 0.0) > 0  # S clamped at 0.05, no division by zero

    # Bjork's inverse retrieval-gain law: recall at R≈0.78 grows S more than cramming at R≈0.99
    t_78 = (0.78 ** -2 - 1) * S * 81 / 19
    t_99 = (0.99 ** -2 - 1) * S * 81 / 19
    assert cm.retrievability(t_78, S) == pytest.approx(0.78, abs=1e-6)
    gain_78 = cm.fsrs_review(S, 5.0, t_78, rating=3).stability_after - S
    gain_99 = cm.fsrs_review(S, 5.0, t_99, rating=3).stability_after - S
    assert gain_78 > gain_99 > 0
    assert gain_99 >= 0.15  # visible floor S + 0.15·m_G


def test_fsrs_rating_assignment_and_difficulty():
    assert cm.assign_rating(0, "FAILED", "NONE", 0.9) == 1
    assert cm.assign_rating(1, "HIGH_CONFIDENCE_ERROR", "NONE", 0.9) == 1
    assert cm.assign_rating(1, "SOLVED_WITH_HINTS", "R3", 0.9) == 2
    assert cm.assign_rating(1, "SOLVED_WITH_HINTS", "R1", 0.9) == 3
    assert cm.assign_rating(1, "SOLVED_CLEAN", "NONE", 0.5) == 3
    assert cm.assign_rating(1, "SOLVED_CLEAN", "NONE", 0.9, hesitation_count=5) == 3
    assert cm.assign_rating(1, "SOLVED_CLEAN", "NONE", 0.9) == 4
    # easy lowers difficulty, again raises it, everything stays in [1, 10]
    assert cm.update_difficulty(5.0, 4) < 5.0 < cm.update_difficulty(5.0, 1)
    for d in (1.0, 5.0, 10.0):
        for g in (1, 2, 3, 4):
            assert 1.0 <= cm.update_difficulty(d, g) <= 10.0
    # mean reversion: repeated Good converges towards the anchor region
    d = 9.5
    for _ in range(40):
        d = cm.update_difficulty(d, 3)
    assert d == pytest.approx(5.0, abs=0.05)


def test_fsrs_lapse_and_easy_ordering():
    S, D, t = 8.0, 5.0, 8.0
    s = {g: cm.fsrs_review(S, D, t, g).stability_after for g in (1, 2, 3, 4)}
    assert s[1] < S and s[1] >= 0.20 and s[1] <= 0.65 * S
    assert s[2] < s[3] < s[4]


# ------------------------------------------------------------------ §3.2 BKT
def test_bkt_trace_quality_and_propagation():
    p = 0.30
    lucky = cm.bkt_update(p, 1, q=0.20)
    understood = cm.bkt_update(p, 1, q=0.90)
    plain_bkt = cm.bkt_posterior(p, 1, 0.08, 0.05)
    # a lucky guess with low trace quality barely moves the posterior; full credit needs structure
    assert lucky - p < 0.15
    assert understood > 0.80 and understood > lucky + 0.4
    assert lucky < plain_bkt
    # NOTATION_OBSTRUCTION softens the slip penalty relative to a structural miss
    soft = cm.bkt_update(0.7, 0, q=0.5, miss_class="NOTATION_OBSTRUCTION")
    hard = cm.bkt_update(0.7, 0, q=0.5, miss_class="FALSE_ANALOGY")
    slip = cm.bkt_update(0.7, 0, q=0.5, miss_class="ALGEBRAIC_SLIP")
    assert soft > slip > hard
    # clip bounds
    assert cm.bkt_update(0.999, 1, 1.0) <= 0.995 and cm.bkt_update(0.001, 0, 0.0) >= 0.01

    # upward confirmation into premises A, B of {A, B} ⇒ C
    m = {"A": 0.40, "B": 0.60, "C": 0.50, "X": 0.5}
    edges = [(["A", "B"], "C")]
    up = cm.propagate_hyperedge_beliefs(m, edges, "C", y=1, q=0.9, miss_class="NONE")
    assert set(up) == {"A", "B"}
    assert up["A"] == pytest.approx(0.40 + 0.08 * 0.9 * 0.60)
    assert up["B"] > 0.60
    # no propagation on a non-clean solve
    assert cm.propagate_hyperedge_beliefs(m, edges, "C", 1, 0.5, "NONE") == {}
    # downward diagnostic decay on MISSING_PREREQUISITE: P ← 0.9P + 0.05
    down = cm.propagate_hyperedge_beliefs(m, edges, "C", 0, 0.4, "MISSING_PREREQUISITE")
    assert down["A"] == pytest.approx(0.9 * 0.40 + 0.05)
    assert down["B"] == pytest.approx(0.9 * 0.60 + 0.05)


# ------------------------------------------------------------------ §3.3 active probe
def test_active_probe_mutual_information():
    # two roots → mid → two leaves: the midpoint splits the DAG and has the highest leverage
    m = {"r1": 0.5, "r2": 0.5, "mid": 0.5, "l1": 0.5, "l2": 0.5}
    edges = [(["r1", "r2"], "mid"), (["mid"], "l1"), (["mid"], "l2")]
    best, table = cm.select_next_probe_node(m, edges, probed=[])
    assert best == "mid"
    row = {e.node_id: e for e in table}
    assert row["mid"].unprobed_ancestors == 2 and row["mid"].unprobed_descendants == 2
    assert row["mid"].eig == pytest.approx(1.0 * (1 + 0.4 * 0.5 * 2 + 0.4 * 0.5 * 2))
    assert [e.eig for e in table] == sorted((e.eig for e in table), reverse=True)
    # already-certain nodes carry no entropy; probed nodes are excluded
    best2, table2 = cm.select_next_probe_node({**m, "mid": 0.999}, edges, probed=["r1"])
    assert best2 != "mid" and "r1" not in {e.node_id for e in table2}
    assert cm.binary_entropy(0.5) == pytest.approx(1.0)
    # probe outcome propagation along the Markov blanket
    lifted = cm.apply_probe_result(m, edges, "mid", mastered=True)
    assert set(lifted) == {"r1", "r2"} and all(v > 0.5 for v in lifted.values())
    lowered = cm.apply_probe_result(m, edges, "mid", mastered=False)
    assert set(lowered) == {"l1", "l2"} and all(v < 0.5 for v in lowered.values())


# ------------------------------------------------------------------ §3.4 calibration / scheduling
def test_hypercorrection_trigger():
    assert cm.classify_outcome(0, 0.85, "NONE", 0.6) == "HIGH_CONFIDENCE_ERROR"
    assert cm.classify_outcome(0, 0.60, "NONE", 0.6) == "FAILED"
    flag, resolved = cm.hypercorrection_transition(0, 0, 0.85, 0.6)
    assert flag == 1 and not resolved
    flag, resolved = cm.hypercorrection_transition(1, 1, 0.9, 0.8)
    assert flag == 0 and resolved
    flag, resolved = cm.hypercorrection_transition(1, 1, 0.9, 0.5)  # sloppy resolution does not clear
    assert flag == 1 and not resolved
    plain = cm.fsrs_review(4.0, 5.0, 4.0, 4).stability_after
    bonus = cm.fsrs_review(4.0, 5.0, 4.0, 4, hypercorrection_resolved=True)
    assert bonus.hypercorrection_bonus_applied and bonus.stability_after == pytest.approx(1.25 * plain)
    assert cm.brier_score(0.85, 0) == pytest.approx(0.7225)


def test_murphy_decomposition_identity():
    pairs = [(0.9, 1), (0.9, 1), (0.9, 0), (0.3, 0), (0.3, 1), (0.3, 0), (0.6, 1), (0.6, 0)]
    d = cm.murphy_decomposition(pairs)
    # with forecasts constant inside each bin the identity BS = REL − RES + UNC is exact
    assert d.brier == pytest.approx(d.reliability - d.resolution + d.uncertainty, abs=1e-12)
    assert d.accuracy == pytest.approx(4 / 8)
    over = cm.murphy_decomposition([(0.95, 0)] * 5 + [(0.95, 1)] * 5)
    assert over.label == "OVERCONFIDENT"
    assert cm.murphy_decomposition([]).label == "NO_DATA"


def test_cue_update_and_practice_priority():
    assert cm.update_cue(0.0) == pytest.approx(0.35)
    assert cm.update_cue(1.0) == 1.0
    in_window = cm.practice_priority(0.78, 0.5, 0).score
    fresh = cm.practice_priority(0.99, 0.5, 0).score
    assert in_window > fresh
    assert cm.practice_priority(0.78, 0.5, 1).score == pytest.approx(in_window + 0.20)
    now = datetime.now(timezone.utc)

    def mk(i, dom):
        return {"id": f"n{i}", "domain_cluster": dom, "fsrs_stability": 3.0, "hypercorrection_flag": 0,
                "last_reviewed_at": (now - timedelta(days=2.0 + 0.01 * i)).isoformat(),
                **{c: 0.2 for c in cm.CUE_DIMENSIONS}}
    ranked = cm.rank_nodes_for_practice([mk(0, "A"), mk(1, "A"), mk(2, "A"), mk(-1, "B")], now)
    doms = [n["domain_cluster"] for n, _ in ranked]
    assert doms[0] == "A" and doms[1] == "B"  # B scores lowest, but interleaving pulls it forward


def test_step_delta_controller():
    clean = {"outcome": "SOLVED_CLEAN", "trace_quality_score": 0.85, "confidence_slider": 0.8, "miss_class": "NONE"}
    assert cm.update_step_delta(1.0, [clean]) == (1.0, "HOLD")
    assert cm.update_step_delta(1.0, [clean, clean]) == (1.5, "ACCELERATE")
    assert cm.update_step_delta(2.5, [clean, clean]) == (2.5, "ACCELERATE")
    fail = {"outcome": "FAILED", "trace_quality_score": 0.3, "confidence_slider": 0.4, "miss_class": "FALSE_ANALOGY"}
    assert cm.update_step_delta(2.0, [clean, fail]) == (0.5, "REMEDIATE")
    prereq = {**clean, "outcome": "PARTIAL", "miss_class": "MISSING_PREREQUISITE"}
    assert cm.update_step_delta(1.5, [prereq]) == (0.5, "REMEDIATE")


def test_topological_depths():
    edges = [("DEDUCTION", ["a"], "b"), ("DEDUCTION", ["b", "c"], "d"), ("CONTRASTIVE", ["d"], "e"),
             ("DEDUCTION", ["d"], "a")]  # back-edge cycle must not hang
    depth = cm.topological_depths(["a", "b", "c", "d", "e"], edges)
    assert depth["c"] == 0 and depth["e"] == 0
    assert depth["d"] >= 1 and all(isinstance(v, int) for v in depth.values())
    assert math.isfinite(sum(depth.values()))
