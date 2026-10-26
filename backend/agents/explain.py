"""Explanation policy (docs/specs/explain, docs/specs/learn-chat): pure functions, no I/O.

- `offer_for`: when Pólya offers an explanation unprompted (assistance dilemma: after an attempt, never for mastered ideas).
- `style_for` / `next_representation`: how deep and through which representation (expertise reversal, dual coding).
- `stuck_after_ms`: when a learner who has typed little has been on a card long enough to be offered a nudge.
- `p_recall` / readiness constants for the learn chat.
"""
from __future__ import annotations

import re
import statistics
from typing import Any, Optional

from .. import cognitive_math as cm

GRADED_KINDS = ("PROBE", "CHECK", "PRACTICE_CHUNK", "REFEREE", "FEYNMAN")
NOVICE_BELOW = 0.40          # P(L) below this → worked example (Kalyuga 2003: novices need the steps)
MASTERED_AT = 0.85           # P(L) at or above this → terse, and no unprompted offers
READY_RECALL = 0.70          # learn chat: predicted recall at which an idea is ready (Rowland 2014)
MAX_EXCHANGES = 4            # learn chat: exchanges per idea before moving on
WEAK_REASONING_Q = 0.45      # = cm.SUCCESS_MIN_QUALITY: right answer, weak reasoning
STUCK_FLOOR_MS = 90_000
STUCK_COLD_MS = 120_000
STUCK_MIN_SAMPLES = 5
STUCK_TYPED_CHARS = 40
REPRESENTATIONS = ("concrete", "geometric", "symbolic", "computational")

OFFER_LABELS = {
    "CONFIDENT_WRONG": "You were sure of that one. Want to see exactly where it breaks?",
    "WHEEL_SPINNING": "This one keeps slipping. Want a worked example?",
    "WRONG": "Want to see why?",
    "WEAK_REASONING": "Right answer. Want to see why it's right?",
    "STUCK": "Stuck? Ask for a nudge (not the answer).",
}


def offer_for(kind: str, outcome: str, is_correct: int, q: float, p_after: float, failed_attempts: int,
              consecutive_fails: int, explained_this_step: bool) -> Optional[dict[str, str]]:
    """The first trigger that applies after a graded answer, or None (FR3)."""
    if kind not in GRADED_KINDS or explained_this_step or p_after >= MASTERED_AT:
        return None
    if outcome == "HIGH_CONFIDENCE_ERROR":
        trigger = "CONFIDENT_WRONG"
    elif not is_correct and (failed_attempts >= 2 or consecutive_fails >= 2):
        trigger = "WHEEL_SPINNING"
    elif not is_correct:
        trigger = "WRONG"
    elif q < WEAK_REASONING_Q:
        trigger = "WEAK_REASONING"
    else:
        return None
    return {"trigger": trigger, "label": OFFER_LABELS[trigger], "action": "OFFER"}


def style_for(p_mastery: float, action: str, trigger: str = "", has_attempt: bool = False) -> str:
    """FR2: the explanation style from mastery, the request and what prompted it."""
    if trigger == "STUCK":
        return "NUDGE"
    if trigger == "CONFIDENT_WRONG":
        return "REFUTATION"
    if action == "SIMPLER" or trigger == "WHEEL_SPINNING":
        return "WORKED_EXAMPLE"
    if p_mastery >= MASTERED_AT:
        return "TERSE"
    if p_mastery < NOVICE_BELOW:
        return "WORKED_EXAMPLE"
    return "CONTRAST" if has_attempt else "EXPLAIN"


def next_representation(used: list[str]) -> str:
    """Rotate concrete → geometric → symbolic → computational, skipping the last one used."""
    last = used[-1] if used else ""
    if last not in REPRESENTATIONS:
        return REPRESENTATIONS[0]
    return REPRESENTATIONS[(REPRESENTATIONS.index(last) + 1) % len(REPRESENTATIONS)]


def stuck_after_ms(samples: list[float]) -> int:
    """max(90 s, 2 × median time to answer a graded card), or 120 s until there are 5 samples."""
    xs = [x for x in samples if x and x > 0]
    if len(xs) < STUCK_MIN_SAMPLES:
        return STUCK_COLD_MS
    return int(max(STUCK_FLOOR_MS, 2 * statistics.median(xs)))


def p_recall(node: dict[str, Any]) -> float:
    """Predicted chance of answering correctly from mastery alone: P(L)(1−s) + (1−P(L))g."""
    return cm.predict_correct(node["bkt_p_mastery"], node["bkt_p_slip"], node["bkt_p_guess"], 1.0)["p_bkt"]


def is_new(node: dict[str, Any]) -> bool:
    """learn-chat FR1: never reviewed and never answered."""
    return int(node.get("fsrs_reps", 0)) == 0 and int(node.get("brier_count", 0)) == 0


def coverage(text: str, groups: list[list[str]]) -> float:
    """Share of concept groups (synonym lists) that the text touches."""
    groups = [g for g in groups if g]
    if not groups:
        return 0.0
    low = text.lower()
    return sum(1 for g in groups if any(s.lower() in low for s in g if s)) / len(groups)


def key_term_groups(node: dict[str, Any], k: int = 3) -> list[list[str]]:
    """Fallback concept groups: the longest distinctive words of the idea's title and statement."""
    words = sorted({w for w in re.findall(r"[a-z]{5,}", f"{node['title']} {node['statement_latex']}".lower())
                    if not w.startswith(("text", "mathbb", "frac", "begin", "mathrm"))}, key=len, reverse=True)
    return [[w[:7]] for w in words[:k]] or [[node["title"].lower()[:10]]]


def mentioned_idea(question: str, plan_nodes: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """A plan idea whose title words all appear in a free-text question (most title words wins)."""
    from .topic_map import goal_terms
    q = goal_terms(question)
    best, best_n = None, 0
    for n in plan_nodes:
        t = goal_terms(n["title"])
        if t and t <= q and len(t) > best_n:
            best, best_n = n, len(t)
    return best
