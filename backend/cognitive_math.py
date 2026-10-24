"""Cognitive models of the learner (ARCHITECTURE_SPEC.md §3).

Pure functions only: no database or I/O. The orchestrator reads node rows, calls these and writes back.

- FSRS-v5 retrievability / difficulty / stability with Bjork's inverse retrieval-gain law (§3.1)
- Process-aware extended BKT and directed hyperedge belief propagation (§3.2)
- Expected-information-gain active probe selection over the prerequisite DAG (§3.3)
- Brier score, hypercorrection, Murphy (1973) Brier decomposition, cue-breadth update,
  practice priority with interleaving (§3.4 + SPEC.md science additions)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping, Optional, Sequence

# ------------------------------------------------------------------ constants
FSRS_FACTOR = 19.0 / 81.0
FSRS_DECAY = -0.5
RATING_MULTIPLIERS = {2: 0.55, 3: 1.00, 4: 1.38}
DESIRED_RETENTION = 0.90
BJORK_WINDOW = (0.70, 0.85)
HYPERCORRECTION_CONFIDENCE = 0.75
HYPERCORRECTION_BONUS = 1.25
CUE_DIMENSIONS = ("cue_symbolic", "cue_disguised_notation", "cue_geometric", "cue_computational", "cue_adversarial")
DELTA_MIN, DELTA_MAX, DELTA_STEP = 0.5, 2.5, 0.5


def clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def elapsed_days(last_reviewed_at: str, now: Optional[datetime] = None) -> float:
    now = now or utcnow()
    return max(0.0, (now - parse_ts(last_reviewed_at)).total_seconds() / 86400.0)


# ------------------------------------------------------------------ §3.1 FSRS-v5
def retrievability(t_days: float, stability: float) -> float:
    """R(t,S) = (1 + 19/81 · t / max(S, 0.05))^-0.5"""
    t = max(0.0, t_days)
    return (1.0 + FSRS_FACTOR * t / max(stability, 0.05)) ** FSRS_DECAY


def interval_for_retention(stability: float, r_target: float = DESIRED_RETENTION) -> float:
    """Invert the power curve: days until R falls to r_target.  t = (81/19)·S·(r^-2 − 1)."""
    r = clip(r_target, 0.01, 0.999)
    return (1.0 / FSRS_FACTOR) * max(stability, 0.05) * (r ** -2 - 1.0)


def next_due(last_reviewed_at: str, stability: float, r_target: float = DESIRED_RETENTION) -> datetime:
    return parse_ts(last_reviewed_at) + timedelta(days=interval_for_retention(stability, r_target))


def assign_rating(
    is_correct: int,
    outcome: str,
    max_hint_rung: str,
    trace_quality_score: float,
    hesitation_count: int = 0,
) -> int:
    """Map telemetry to the FSRS rating G ∈ {1,2,3,4} (§3.1.2)."""
    if not is_correct or outcome in ("FAILED", "HIGH_CONFIDENCE_ERROR"):
        return 1
    if max_hint_rung in ("R2", "R3", "R4"):
        return 2
    if max_hint_rung in ("R0", "R1") or trace_quality_score < 0.72 or hesitation_count >= 4:
        return 3
    return 4


def update_difficulty(difficulty: float, rating: int) -> float:
    """ΔD = −0.85(G−3); D_raw = D + ΔD·(10−D)/9; D' = clip(0.15·5 + 0.85·D_raw, 1, 10)."""
    delta = -0.85 * (rating - 3)
    d_raw = difficulty + delta * ((10.0 - difficulty) / 9.0)
    return clip(0.15 * 5.0 + 0.85 * d_raw, 1.0, 10.0)


def update_stability(stability: float, difficulty_new: float, r: float, rating: int) -> float:
    """Stability update (§3.1.4).

    Success: S' = S·(1 + e^1.75·(11−D')·max(S,.5)^−.22·max(.06, e^{.95(1−R)}−1)·m_G), floored at S + 0.15·m_G.
    Lapse:   S' = max(0.2, min(0.65·S, 0.38·D'^−.28·(S+1)^.22·e^{.45(1−R)})).
    """
    s = max(stability, 0.05)
    r = clip(r, 0.0, 1.0)
    if rating == 1:
        return max(0.20, min(s * 0.65, 0.38 * difficulty_new ** -0.28 * (s + 1.0) ** 0.22 * math.exp(0.45 * (1.0 - r))))
    m = RATING_MULTIPLIERS[rating]
    spacing_gain = max(0.06, math.exp(0.95 * (1.0 - r)) - 1.0)
    s_new = s * (1.0 + math.exp(1.75) * (11.0 - difficulty_new) * max(s, 0.5) ** -0.22 * spacing_gain * m)
    return max(s_new, s + 0.15 * m)


@dataclass
class FSRSResult:
    rating: int
    r_at_review: float
    stability_before: float
    stability_after: float
    difficulty_after: float
    hypercorrection_bonus_applied: bool


def fsrs_review(
    stability: float,
    difficulty: float,
    t_days: float,
    rating: int,
    hypercorrection_resolved: bool = False,
) -> FSRSResult:
    r = retrievability(t_days, stability)
    d_new = update_difficulty(difficulty, rating)
    s_new = update_stability(stability, d_new, r, rating)
    bonus = bool(hypercorrection_resolved and rating >= 2)
    if bonus:
        s_new *= HYPERCORRECTION_BONUS
    return FSRSResult(rating, r, stability, s_new, d_new, bonus)


# ------------------------------------------------------------------ §3.2 extended BKT
def effective_slip_guess(slip: float, guess: float, y: int, q: float, miss_class: str) -> tuple[float, float]:
    if miss_class == "NOTATION_OBSTRUCTION":
        s_eff = 0.48
    elif miss_class == "ALGEBRAIC_SLIP":
        s_eff = 0.35
    else:
        s_eff = slip
    if y == 1 and q < 0.45:
        g_eff = 0.65
    else:
        g_eff = guess * (1.2 - 0.8 * q)
    return s_eff, g_eff


def bkt_posterior(p: float, y: int, s_eff: float, g_eff: float) -> float:
    p = clip(p, 1e-6, 1 - 1e-6)
    if y == 1:
        num = p * (1.0 - s_eff)
        den = num + (1.0 - p) * g_eff
    else:
        num = p * s_eff
        den = num + (1.0 - p) * (1.0 - g_eff)
    return num / den if den > 1e-12 else p


def bkt_update(
    p: float,
    y: int,
    q: float,
    miss_class: str = "NONE",
    slip: float = 0.08,
    guess: float = 0.05,
    transit: float = 0.12,
) -> float:
    """Process-aware BKT: trace quality q modulates guess and the learning transition (§3.2.1)."""
    q = clip(q, 0.0, 1.0)
    s_eff, g_eff = effective_slip_guess(slip, guess, y, q, miss_class)
    post = bkt_posterior(p, y, s_eff, g_eff)
    return clip(post + (1.0 - post) * transit * (0.4 + 0.6 * q), 0.01, 0.995)


def propagate_hyperedge_beliefs(
    masteries: Mapping[str, float],
    deduction_edges: Iterable[tuple[Sequence[str], str]],
    node_id: str,
    y: int,
    q: float,
    miss_class: str,
) -> dict[str, float]:
    """Directed message passing along DEDUCTION hyperedges into `node_id` (§3.2.2).

    Returns {premise_id: new_mastery} for every premise that changed.
    """
    updates: dict[str, float] = {}
    upward = y == 1 and q >= 0.75
    downward = y == 0 and miss_class == "MISSING_PREREQUISITE"
    if not (upward or downward):
        return updates
    for premises, conclusion in deduction_edges:
        if conclusion != node_id:
            continue
        for a in premises:
            if a not in masteries or a == node_id:
                continue
            p = updates.get(a, masteries[a])
            if upward:
                updates[a] = min(0.99, p + 0.08 * q * (1.0 - p))
            else:
                updates[a] = 0.90 * p + 0.05
    return updates


# ------------------------------------------------------------------ §3.3 active probe
def binary_entropy(p: float) -> float:
    p = clip(p, 1e-9, 1 - 1e-9)
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def _closure(start: str, adj: Mapping[str, Iterable[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(adj.get(start, ()))
    while stack:
        v = stack.pop()
        if v in seen:
            continue
        seen.add(v)
        stack.extend(adj.get(v, ()))
    seen.discard(start)
    return seen


def dag_adjacency(nodes: Iterable[str], edges: Iterable[tuple[Sequence[str], str]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (parents, children) maps from (premises, conclusion) hyperedges restricted to `nodes`."""
    node_set = set(nodes)
    parents: dict[str, set[str]] = {v: set() for v in node_set}
    children: dict[str, set[str]] = {v: set() for v in node_set}
    for premises, conclusion in edges:
        if conclusion not in node_set:
            continue
        for a in premises:
            if a in node_set and a != conclusion:
                parents[conclusion].add(a)
                children[a].add(conclusion)
    return parents, children


@dataclass
class EIGEntry:
    node_id: str
    p_mastery: float
    entropy: float
    unprobed_ancestors: int
    unprobed_descendants: int
    eig: float


def select_next_probe_node(
    masteries: Mapping[str, float],
    edges: Iterable[tuple[Sequence[str], str]],
    probed: Iterable[str],
) -> tuple[Optional[str], list[EIGEntry]]:
    """EIG(v) = H(v)·(1 + 0.4·P(L_v)·|UnprobedAnc(v)| + 0.4·(1−P(L_v))·|UnprobedDesc(v)|); argmax over unprobed."""
    probed_set = set(probed)
    parents, children = dag_adjacency(masteries.keys(), edges)
    table: list[EIGEntry] = []
    for v, p in masteries.items():
        if v in probed_set:
            continue
        anc = _closure(v, parents) - probed_set
        desc = _closure(v, children) - probed_set
        h = binary_entropy(p)
        eig = h * (1.0 + 0.40 * p * len(anc) + 0.40 * (1.0 - p) * len(desc))
        table.append(EIGEntry(v, p, h, len(anc), len(desc), eig))
    table.sort(key=lambda e: (-e.eig, e.node_id))
    return (table[0].node_id if table else None), table


def apply_probe_result(
    masteries: Mapping[str, float],
    edges: Iterable[tuple[Sequence[str], str]],
    node_id: str,
    mastered: bool,
) -> dict[str, float]:
    """Markov-blanket reachability propagation after a probe: mastery of v lifts ancestors,
    non-mastery of v lowers the reachability of descendants. Returns changed masteries."""
    parents, children = dag_adjacency(masteries.keys(), edges)
    out: dict[str, float] = {}
    if mastered:
        for a in _closure(node_id, parents):
            out[a] = min(0.97, masteries[a] + 0.5 * (1.0 - masteries[a]))
    else:
        for d in _closure(node_id, children):
            out[d] = max(0.02, masteries[d] * 0.5)
    return out


# ------------------------------------------------------------------ §3.4 calibration & scheduling
def brier_score(confidence: float, y: int) -> float:
    return (clip(confidence, 0.0, 1.0) - y) ** 2


def classify_outcome(
    is_correct: int,
    confidence: float,
    max_hint_rung: str,
    trace_quality_score: float,
    partial: bool = False,
) -> str:
    if not is_correct:
        if confidence >= HYPERCORRECTION_CONFIDENCE:
            return "HIGH_CONFIDENCE_ERROR"
        return "PARTIAL" if partial else "FAILED"
    if max_hint_rung != "NONE":
        return "SOLVED_WITH_HINTS"
    if trace_quality_score < 0.45:
        return "PARTIAL"
    return "SOLVED_CLEAN"


def hypercorrection_transition(flag: int, is_correct: int, confidence: float, q: float) -> tuple[int, bool]:
    """Return (new_flag, resolved_now). Sets on confident error; clears (with bonus) on clean resolution."""
    if not is_correct and confidence >= HYPERCORRECTION_CONFIDENCE:
        return 1, False
    if flag == 1 and is_correct and q >= 0.75:
        return 0, True
    return flag, False


def cue_dimension_for(cue_level: int, mode: str, sub_mode: str = "STANDARD", step_kind: str = "", has_demo: bool = False,
                      computational: bool = False) -> str:
    if cue_level >= 4 or mode == "REFEREE_DUEL":
        return "cue_adversarial"
    if has_demo:
        return "cue_geometric"
    if computational:
        return "cue_computational"
    if cue_level == 2:
        return "cue_disguised_notation"
    if cue_level == 3:
        return "cue_computational"
    return "cue_symbolic"


def update_cue(value: float) -> float:
    return min(1.0, value + 0.35 * (1.0 - value))


@dataclass
class PriorityBreakdown:
    score: float
    bjork: float
    forgetting: float
    cue_gap: float
    hypercorrection: float
    interleave_penalty: float = 0.0


def practice_priority(r: float, cue_mean: float, hypercorrection_flag: int) -> PriorityBreakdown:
    bjork = 0.35 * math.exp(-((r - 0.78) ** 2) / (2 * 0.12 ** 2))
    forgetting = 0.25 * (1.0 - r)
    cue_gap = 0.20 * (1.0 - cue_mean)
    hyper = 0.20 * (1.0 if hypercorrection_flag == 1 else 0.0)
    return PriorityBreakdown(bjork + forgetting + cue_gap + hyper, bjork, forgetting, cue_gap, hyper)


def rank_nodes_for_practice(nodes: Sequence[Mapping], now: Optional[datetime] = None,
                            interleave_penalty: float = 0.12) -> list[tuple[Mapping, PriorityBreakdown]]:
    """Score every node (§3.4.3), then greedily reorder so consecutive picks avoid the same domain
    cluster (interleaving, Rohrer & Taylor 2007): each pick pays `interleave_penalty` if it
    repeats the previous pick's cluster."""
    scored = []
    for n in nodes:
        r = retrievability(elapsed_days(n["last_reviewed_at"], now), n["fsrs_stability"])
        cue_mean = sum(n[c] for c in CUE_DIMENSIONS) / len(CUE_DIMENSIONS)
        scored.append((n, practice_priority(r, cue_mean, n["hypercorrection_flag"])))
    remaining = sorted(scored, key=lambda x: -x[1].score)
    ordered: list[tuple[Mapping, PriorityBreakdown]] = []
    last_cluster = None
    while remaining:
        best_i, best_val = 0, -1e9
        for i, (n, pb) in enumerate(remaining):
            pen = interleave_penalty if n["domain_cluster"] == last_cluster else 0.0
            if pb.score - pen > best_val:
                best_i, best_val = i, pb.score - pen
        n, pb = remaining.pop(best_i)
        pen = interleave_penalty if n["domain_cluster"] == last_cluster else 0.0
        ordered.append((n, PriorityBreakdown(pb.score - pen, pb.bjork, pb.forgetting, pb.cue_gap, pb.hypercorrection, pen)))
        last_cluster = n["domain_cluster"]
    return ordered


@dataclass
class BrierDecomposition:
    n: int
    brier: Optional[float]
    reliability: float
    resolution: float
    uncertainty: float
    mean_confidence: float
    accuracy: float
    bins: list[dict] = field(default_factory=list)

    @property
    def overconfidence(self) -> float:
        return self.mean_confidence - self.accuracy

    @property
    def label(self) -> str:
        if self.n == 0:
            return "NO_DATA"
        if self.overconfidence > 0.10:
            return "OVERCONFIDENT"
        if self.overconfidence < -0.10:
            return "UNDERCONFIDENT"
        return "WELL_CALIBRATED"


def murphy_decomposition(pairs: Sequence[tuple[float, int]], n_bins: int = 10) -> BrierDecomposition:
    """Murphy (1973): BS = REL − RES + UNC, with forecasts binned into n_bins equal-width bins.

    REL = Σ_k n_k (f̄_k − ō_k)² / N,  RES = Σ_k n_k (ō_k − ō)² / N,  UNC = ō(1 − ō).
    The identity is exact when forecasts within a bin are equal; with binning REL uses bin means.
    """
    n = len(pairs)
    if n == 0:
        return BrierDecomposition(0, None, 0.0, 0.0, 0.0, 0.0, 0.0, [])
    o_bar = sum(y for _, y in pairs) / n
    bins: dict[int, list[tuple[float, int]]] = {}
    for c, y in pairs:
        k = min(n_bins - 1, int(clip(c, 0.0, 1.0) * n_bins))
        bins.setdefault(k, []).append((c, y))
    rel = res = 0.0
    out_bins = []
    for k in sorted(bins):
        b = bins[k]
        nk = len(b)
        f_k = sum(c for c, _ in b) / nk
        o_k = sum(y for _, y in b) / nk
        rel += nk * (f_k - o_k) ** 2
        res += nk * (o_k - o_bar) ** 2
        out_bins.append({"confidence_mid": (k + 0.5) / n_bins, "mean_confidence": f_k, "accuracy": o_k, "count": nk})
    brier = sum(brier_score(c, y) for c, y in pairs) / n
    return BrierDecomposition(
        n=n, brier=brier, reliability=rel / n, resolution=res / n, uncertainty=o_bar * (1 - o_bar),
        mean_confidence=sum(c for c, _ in pairs) / n, accuracy=o_bar, bins=out_bins,
    )


# ------------------------------------------------------------------ §4.2 Δ-controller
def update_step_delta(delta: float, recent: Sequence[Mapping]) -> tuple[float, str]:
    """Return (new_delta, action) given the most recent step traces (newest last).

    action ∈ {"ACCELERATE", "REMEDIATE", "HOLD"}.
    """
    if not recent:
        return delta, "HOLD"
    last = recent[-1]
    if last["outcome"] in ("FAILED", "HIGH_CONFIDENCE_ERROR") or last.get("miss_class") == "MISSING_PREREQUISITE":
        return DELTA_MIN, "REMEDIATE"
    if len(recent) >= 2 and all(
        t["outcome"] == "SOLVED_CLEAN" and t["trace_quality_score"] >= 0.80 and t["confidence_slider"] >= 0.75
        for t in recent[-2:]
    ):
        return min(DELTA_MAX, delta + DELTA_STEP), "ACCELERATE"
    return delta, "HOLD"


# ------------------------------------------------------------------ graph depth
def topological_depths(node_ids: Iterable[str], edges: Iterable[tuple[str, Sequence[str], str]],
                       floor: Optional[Mapping[str, int]] = None) -> dict[str, int]:
    """Longest-path depth over DEDUCTION/CUE_TRIGGER edges (edge_type, premises, conclusion).

    CONTRASTIVE and ISOMORPHISM are symmetric relations and do not add depth. Cycles are broken by
    ignoring back-edges discovered during DFS. `floor` gives per-node minimum depths that propagate upward.
    """
    ids = list(node_ids)
    parents: dict[str, set[str]] = {v: set() for v in ids}
    for etype, premises, conclusion in edges:
        if etype not in ("DEDUCTION", "CUE_TRIGGER") or conclusion not in parents:
            continue
        for a in premises:
            if a in parents and a != conclusion:
                parents[conclusion].add(a)
    depth: dict[str, int] = {}
    visiting: set[str] = set()

    def visit(v: str) -> int:
        if v in depth:
            return depth[v]
        if v in visiting:
            return 0
        visiting.add(v)
        d = (floor or {}).get(v, 0)
        for p in parents[v]:
            if p in visiting:
                continue
            d = max(d, visit(p) + 1)
        visiting.discard(v)
        depth[v] = d
        return d

    for v in ids:
        visit(v)
    return depth
