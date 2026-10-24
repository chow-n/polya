"""The 8 asynchronous sub-agents (ARCHITECTURE_SPEC.md §5).

Each agent: opens a RUNNING artifact, broadcasts `subagent_status`, does real work (SymPy subprocess, corpus
search, arXiv, graph surgery, HTML/SVG generation), stores an inspectable payload and broadcasts the result.
When an LLM engine is available it is consulted and its JSON validated; the deterministic path always runs
first or as the fallback so every agent works with zero configuration.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Optional

from .. import db, demos, llm, tools
from .. import cognitive_math as cm
from ..hub import hub
from ..models import LLMDiagnosis, LLMOntology
from . import prompts
from .content_bank import CONTENT

# ------------------------------------------------------------------ plumbing


async def _status(agent: str, state: str, message: str, artifact_id: Optional[str] = None,
                  session_id: Optional[str] = None) -> None:
    await hub.broadcast("subagent_status", {"agent_name": agent, "state": state, "message": message,
                                            "artifact_id": artifact_id, "session_id": session_id})


async def run_agent(agent: str, session_id: Optional[str], title: str, content_type: str,
                    work: Callable[[], Awaitable[tuple[str, str]]]) -> dict[str, Any]:
    """Run `work` (returning (payload_text, final_title)) under artifact + telemetry bookkeeping."""
    with db.tx() as conn:
        aid = db.insert_artifact(conn, agent, "RUNNING", title, content_type, "", session_id)
    await _status(agent, "RUNNING", title, aid, session_id)
    try:
        payload, final_title = await work()
        status = "COMPLETED"
    except Exception as e:  # the failure itself is the inspectable artifact
        payload, final_title, status = f"{type(e).__name__}: {e}", title, "FAILED"
    with db.tx() as conn:
        db.update_artifact(conn, aid, status, payload, final_title)
        art = db.get_artifact(conn, aid)
    await _status(agent, status, final_title, aid, session_id)
    await hub.broadcast("artifact", art)
    return art


def _slug(text: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:n] or "item"


# ------------------------------------------------------------------ 1. SYMBOLIC_VERIFIER
async def symbolic_verify(session_id: Optional[str], code: str, title: str) -> tuple[tools.VerifyResult, dict[str, Any]]:
    holder: dict[str, tools.VerifyResult] = {}

    async def work() -> tuple[str, str]:
        res = await asyncio.to_thread(tools.verify_math_sympy, code)
        holder["r"] = res
        tag = "✓ VERIFIED" if res.verified else ("⏱ TIMEOUT" if res.timed_out else "✗ NOT VERIFIED")
        return res.as_log(), f"{tag} · {title}"

    art = await run_agent("SYMBOLIC_VERIFIER", session_id, title, "sympy_log", work)
    res = holder.get("r") or tools.VerifyResult(False, False, "", art["payload_text"], -1, False, code)
    return res, art


EQ_RX = re.compile(r"([A-Za-z0-9_\s\+\-\*/\^\(\)\.]{1,80})=([A-Za-z0-9_\s\+\-\*/\^\(\)\.]{1,80})")


def extract_checkable_equations(text: str, limit: int = 2) -> list[tuple[str, str]]:
    """Plain-ASCII equations in a learner chunk (e.g. `(a+b)^2 = a^2 + 2ab + b^2`) that SymPy can check."""
    out = []
    for line in text.splitlines():
        if "\\" in line or "==" in line:
            continue
        for m in EQ_RX.finditer(line):
            lhs, rhs = m.group(1).strip(), m.group(2).strip()
            if not lhs or not rhs or not re.search(r"[A-Za-z]", lhs + rhs):
                continue
            lhs = re.sub(r"^(?:[A-Za-z]{2,}\s+)+", "", lhs)    # leading prose ("so ...")
            rhs = re.sub(r"(?:\s+[A-Za-z]{2,})+$", "", rhs)    # trailing prose ("... here")
            if not lhs or not rhs or re.search(r"[A-Za-z]{4,}", lhs + rhs):   # prose, not algebra
                continue
            lhs, rhs = _implicit_mult(lhs), _implicit_mult(rhs)
            out.append((lhs, rhs))
            if len(out) >= limit:
                return out
    return out


FUNCTION_NAMES = {"sin", "cos", "tan", "exp", "log", "ln", "max", "min", "var", "abs"}


def _implicit_mult(expr: str) -> str:
    """`2ab` → `2*a*b`, `^` → `**`; short letter runs that are not function names are products of symbols."""
    expr = expr.replace("^", "**")
    expr = re.sub(r"(\d)([a-zA-Z(])", r"\1*\2", expr)
    expr = re.sub(r"\b([a-z]{2,3})\b", lambda m: m.group(1) if m.group(1) in FUNCTION_NAMES else "*".join(m.group(1)), expr)
    return re.sub(r"\)\s*\(", ")*(", expr)


async def verify_learner_equations(session_id: Optional[str], text: str) -> list[dict[str, Any]]:
    results = []
    for lhs, rhs in extract_checkable_equations(text):
        syms = " ".join(sorted(set(re.findall(r"\b[a-zA-Z]\b", lhs + " " + rhs)))) or "x"
        code = tools.check_equivalence_code(lhs, rhs, syms)
        res, art = await symbolic_verify(session_id, code, f"Learner equation {lhs} = {rhs}")
        results.append({"lhs": lhs, "rhs": rhs, "verified": res.verified, "ok": res.ok, "artifact_id": art["id"],
                        "stdout": res.stdout.strip()[:200]})
    return results


# ------------------------------------------------------------------ 2. BUG_LIBRARY_DIAGNOSTICIAN
IGNORANCE_MARKERS = ("no idea", "just guess", "guessing", "i guess", "not sure", "don't know", "dont know", "idk",
                     "random", "by elimination", "eliminat", "no clue", "never seen", "don't remember", "lucky")
HEDGES = ("uh", "um", "maybe", "guess", "wait", "i think", "probably", "not sure", "kind of", "sort of", "perhaps")
NOTATION_MARKERS = ("what is", "what does", "symbol", "notation", "don't recognize", "dont recognize", "unfamiliar",
                    "\\odot", "silu", "what's the", "which means", "meaning of")
SLIP_MARKERS = ("arithmetic", "sign error", "typo", "factor of", "miscalcul", "calculation", "off by", "dropped a")
ANALOGY_MARKERS = ("like ", "similar to", "same as", "just like", "analogous", "by analogy")
UNIVERSAL_MARKERS = ("always", "every ", "for all", "for any", "any ", "never", "all ")
MATH_TOKENS = ("$", "=", "^", "\\", "var", "e[", "sum", "∑", "≤", "≥", "<", ">", "sqrt", "frac", "max", "lim")
STRUCTURAL = ("FALSE_ANALOGY", "BOUNDARY_OMISSION", "CUE_BLINDNESS")


def node_concept_groups(node_id: str) -> list[list[str]]:
    c = CONTENT.get(node_id)
    if c:
        groups: list[list[str]] = []
        for lvl in (1, 2):
            groups += c["practice"][lvl]["concept_groups"]
        return groups
    return []


def _text_blob(ctx: dict[str, Any]) -> str:
    notes = " ".join(f"{n.get('quote', '')} {n.get('thought', '')}" for n in ctx.get("thinking_while_reading", []))
    return " ".join([ctx.get("raw_prediction_locked", ""), notes, ctx.get("verification_thinking", ""),
                     ctx.get("extra_text", "")]).lower()


def trace_quality(ctx: dict[str, Any], node: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """Deterministic process-quality estimate q ∈ [0.05, 0.98] from the three thinking channels + prosody."""
    text = _text_blob(ctx)
    words = len(text.split())
    groups = ctx.get("concept_groups") or node_concept_groups(node["id"])
    if groups:
        covered = sum(1 for g in groups if any(s.lower() in text for s in g))
        coverage = covered / len(groups)
    else:
        key = {w for w in re.findall(r"[a-z]{5,}", (node["statement_latex"] + " " + node["title"]).lower())}
        coverage = min(1.0, len(key & set(re.findall(r"[a-z]{5,}", text))) / max(3, len(key) * 0.4))
    math_density = min(1.0, sum(text.count(t) for t in MATH_TOKENS) / 6.0)
    length = min(1.0, words / 40.0)
    ignorance = sum(1 for m in IGNORANCE_MARKERS if m in text)
    pros = ctx.get("prosody", {}) or {}
    text_hedges = sum(len(re.findall(rf"\b{re.escape(h)}\b", text)) for h in HEDGES)
    hedges = text_hedges + int(pros.get("hedge_count", 0))
    q = (0.20 + 0.45 * coverage + 0.15 * math_density + 0.20 * length
         - 0.35 * min(ignorance, 2) - min(0.20, 0.04 * hedges)
         - (0.05 if int(pros.get("hesitation_count", 0)) >= 4 else 0.0))
    q = cm.clip(q, 0.05, 0.98)
    return q, {"coverage": coverage, "math_density": math_density, "length": length, "ignorance_markers": ignorance,
               "hedges": hedges}


def classify_miss(ctx: dict[str, Any], node: dict[str, Any], conn) -> tuple[str, Optional[dict[str, Any]]]:
    """Return (miss_class, matched_misconception or None) for an incorrect attempt."""
    text = _text_blob(ctx)
    for mis in (CONTENT.get(node["id"], {}).get("misconceptions") or []):
        if any(k.lower() in text for k in mis["trigger_keywords"]):
            return mis["miss_class"], mis
    if any(m in text for m in NOTATION_MARKERS):
        return "NOTATION_OBSTRUCTION", None
    if any(m in text for m in SLIP_MARKERS):
        return "ALGEBRAIC_SLIP", None
    weak_premises = []
    for e in db.all_edges(conn):
        if e["edge_type"] == "DEDUCTION" and e["conclusion_node_id"] == node["id"]:
            for p in e["premise_node_ids"]:
                pn = db.get_node(conn, p)
                if pn and pn["bkt_p_mastery"] < 0.40:
                    weak_premises.append(p)
    if weak_premises:
        return "MISSING_PREREQUISITE", None
    if any(m in f" {text} " for m in UNIVERSAL_MARKERS):
        return "BOUNDARY_OMISSION", None
    if any(m in text for m in ANALOGY_MARKERS):
        return "FALSE_ANALOGY", None
    if len(ctx.get("raw_prediction_locked", "").strip()) < 25:
        return "CUE_BLINDNESS", None
    return "FALSE_ANALOGY", None


def upsert_buggy_rule(conn, node: dict[str, Any], miss_class: str, mis: Optional[dict[str, Any]],
                      learner_text: str, session_id: Optional[str]) -> str:
    """Create or reinforce a BUGGY_RULE shadow node attached by a CONTRASTIVE edge to `node`."""
    if mis:
        title = mis["buggy_title"]
        statement = mis["buggy_statement_latex"]
    else:
        title = f"{miss_class.replace('_', ' ').title()} on: {node['title']}"
        snippet = learner_text.strip().replace("\n", " ")[:220] or "(no written reasoning)"
        statement = rf"\text{{Learner belief (unverified): }} \text{{{_latex_text(snippet)}}}"
    bug_id = f"bug_{_slug(node['id'], 30)}_{_slug(title, 30)}"
    existing = db.get_node(conn, bug_id)
    if existing:
        db.update_node_fields(conn, bug_id, fsrs_lapses=existing["fsrs_lapses"] + 1, last_miss_class=miss_class,
                              intuition_summary=f"Observed {existing['fsrs_lapses'] + 2}× · latest trace: "
                                                f"{learner_text.strip()[:160]}")
    else:
        db.upsert_node(conn, {
            "id": bug_id, "title": title, "node_type": "BUGGY_RULE", "statement_latex": statement,
            "intuition_summary": f"Observed 1× · trace: {learner_text.strip()[:200]}",
            "formal_proof_sketch_latex": "", "domain_cluster": "Buggy Rules", "logical_depth": node["logical_depth"],
            "bkt_p_mastery": 0.15, "last_reviewed_at": db.now_iso(), "last_miss_class": miss_class,
            "created_in_session_id": session_id, "fsrs_lapses": 1,
        })
        db.insert_edge(conn, "CONTRASTIVE", [bug_id], node["id"],
                       rf"\text{{Misconception }} {statement} \;\perp\; \text{{{_latex_text(node['title'])}}}",
                       rf"\text{{The correct statement requires: }} {node['statement_latex'][:300]}", session_id)
        db.recompute_depths(conn)
    return bug_id


def _latex_text(s: str) -> str:
    return re.sub(r"([{}#%&_$\\^~])", r"\\\1", s)


async def diagnose(session_id: Optional[str], ctx: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """Return {is_correct, trace_quality_score, miss_class, right_for_wrong_reason, diagnosis_markdown, buggy_rule_id}."""
    result: dict[str, Any] = {}

    async def work() -> tuple[str, str]:
        q, parts = trace_quality(ctx, node)
        y = int(ctx["is_correct"])
        text = _text_blob(ctx)
        rfwr = bool(y and (parts["ignorance_markers"] > 0 or q < 0.45))
        if rfwr:
            q = min(q, 0.40)
        miss, mis = ("NONE", None)
        with db.ro() as conn:
            if not y:
                miss, mis = classify_miss(ctx, node, conn)
        engine = "deterministic"
        llm_res = await llm.complete_json(
            prompts.SUBAGENT_PROMPTS["BUG_LIBRARY_DIAGNOSTICIAN"],
            prompts.node_context(node) + "\n\nTelemetry tuple:\n" + json.dumps({
                "raw_prediction_locked": ctx.get("raw_prediction_locked", ""),
                "thinking_while_reading": ctx.get("thinking_while_reading", []),
                "verification_thinking": ctx.get("verification_thinking", ""),
                "prosody_metrics": ctx.get("prosody", {}), "confidence_slider": ctx.get("confidence", 0.5),
                "selected_answer": ctx.get("selected_answer", ""), "correct_answer": ctx.get("correct_answer", ""),
                "objective_correct": bool(y)}, indent=1),
            max_tokens=900,
        ) if ctx.get("allow_llm", True) else llm.LLMResult(None, "deterministic")
        llm_note = ""
        if llm_res.data:
            try:
                d = LLMDiagnosis.model_validate(llm_res.data)
                q = 0.5 * q + 0.5 * cm.clip(d.trace_quality_score, 0.0, 1.0)
                if not y and d.miss_class != "NONE":
                    miss = d.miss_class
                rfwr = rfwr or (bool(y) and d.right_for_wrong_reason)
                llm_note = d.diagnosis_markdown
                if d.buggy_rule_statement and not mis and miss in STRUCTURAL:
                    mis = {"buggy_title": d.buggy_rule_statement[:80], "buggy_statement_latex": d.buggy_rule_statement,
                           "miss_class": miss, "trigger_keywords": []}
                engine = llm_res.engine
            except Exception:
                engine = f"{llm_res.engine} (invalid JSON → deterministic)"
        bug_id = None
        if not y and (miss in STRUCTURAL or mis is not None) and miss not in ("NOTATION_OBSTRUCTION", "ALGEBRAIC_SLIP"):
            with db.tx() as conn:
                bug_id = upsert_buggy_rule(conn, node, miss, mis, text, session_id)
        lines = [f"**Node:** {node['title']}  ", f"**Objective result:** {'correct' if y else 'incorrect'} · "
                 f"**trace quality** $q={q:.2f}$ · **miss class** `{miss}`"]
        if rfwr:
            lines.append("⚠️ **Right answer, weak reasoning:** the locked prediction or thinking trace admits guessing or "
                         "lacks the structural ideas, so mastery credit is damped (guess rate inflated to 0.65).")
        if not y and miss == "NOTATION_OBSTRUCTION":
            lines.append("Benign miss: the obstruction looks notational, not conceptual — slip penalty softened (s=0.48).")
        if not y and miss == "ALGEBRAIC_SLIP":
            lines.append("Benign miss: algebraic slip — slip penalty softened (s=0.35).")
        if not y and miss == "MISSING_PREREQUISITE":
            lines.append("A premise of this node has low mastery; the plan will splice a remedial step before it.")
        if mis:
            lines.append(f"Matched misconception: **{mis['buggy_title']}** — ${mis['buggy_statement_latex']}$")
        if bug_id:
            lines.append(f"Recorded shadow node `{bug_id}` (BUGGY_RULE) in the hypergraph.")
        conf = float(ctx.get("confidence", 0.5))
        if not y and conf >= cm.HYPERCORRECTION_CONFIDENCE:
            lines.append(f"🔥 High-confidence error (confidence {conf:.0%}) — hypercorrection flag set. Correcting this "
                         "belief is unusually durable (Butterfield & Metcalfe 2001).")
        if llm_note:
            lines.append("\n" + llm_note)
        result.update(is_correct=y, trace_quality_score=round(q, 3), miss_class=miss, right_for_wrong_reason=rfwr,
                      diagnosis_markdown="\n".join(lines), buggy_rule_id=bug_id, quality_parts=parts, engine=engine)
        return json.dumps(result, indent=2), f"Diagnosis · {node['title']} · q={q:.2f} · {miss}"

    await run_agent("BUG_LIBRARY_DIAGNOSTICIAN", session_id, f"Diagnosing trace on {node['title']}", "json_diagnosis", work)
    if not result:
        q, _ = trace_quality(ctx, node)
        result = {"is_correct": int(ctx["is_correct"]), "trace_quality_score": q, "miss_class": "NONE",
                  "right_for_wrong_reason": False, "diagnosis_markdown": "", "buggy_rule_id": None}
    return result


# ------------------------------------------------------------------ 3. COUNTEREXAMPLE_SYNTHESIZER
COUNTEREXAMPLE_LIBRARY: list[dict[str, Any]] = [
    {"id": "cnt_uncorrelated_not_independent", "keywords": [["uncorrelated", "covariance", "cov"], ["independent", "independence"]],
     "title": r"Uncorrelated but dependent: $X\sim\mathcal N(0,1),\ Y=X^2$",
     "claim": "Zero covariance implies independence", "missing": "joint Gaussianity (or independence itself)",
     "latex": r"X\sim\mathcal N(0,1),\ Y=X^2:\ \operatorname{Cov}(X,Y)=\mathbb E[X^3]=0,\ \text{yet } Y \text{ is a function of } X.",
     "code": "import sympy as sp\nx=sp.symbols('x',real=True)\nphi=sp.exp(-x**2/2)/sp.sqrt(2*sp.pi)\ncov=sp.integrate(x*x**2*phi,(x,-sp.oo,sp.oo))\n"
             "p_joint=sp.integrate(phi,(x,-1,1))  # P(|X|<1, Y<1) = P(|X|<1)\np_prod=p_joint*p_joint  # P(|X|<1)P(Y<1)\n"
             "assert cov==0 and sp.N(p_joint-p_prod)>0.1\nprint('VERIFIED: counterexample holds: Cov=0 but P(|X|<1,Y<1)=',sp.N(p_joint,4),'!=',sp.N(p_prod,4))"},
    {"id": "cnt_unbounded_indicator_escape", "keywords": [["limit", "lim", "converge", "pointwise"], ["integral", "integrate", "int", "expectation", "swap", "interchange", "exchange"]],
     "title": r"Mass escaping to a spike: $f_n=n\mathbf 1_{(0,1/n)}$",
     "claim": "Pointwise limits commute with integrals", "missing": r"a dominating $g\in L^1$ (or monotonicity)",
     "latex": r"f_n=n\,\mathbf 1_{(0,1/n)}\to 0 \text{ pointwise, but } \int_0^1 f_n=1\ne 0.",
     "code": "import sympy as sp\nn,x=sp.symbols('n x',positive=True)\nI=sp.integrate(n,(x,0,1/n))\nassert sp.simplify(I-1)==0\n"
             "print('VERIFIED: counterexample holds: integral of f_n =',I,'for all n while f_n -> 0 pointwise')"},
    {"id": "cnt_transpose_order", "keywords": [["transpose", "^t", "^\\top", "top"], ["product", "ab", "multiply"]],
     "title": r"$(AB)^\top\neq A^\top B^\top$ for $2\times 2$ matrices",
     "claim": "Transpose distributes without reversing order", "missing": r"the order reversal $(AB)^\top=B^\top A^\top$",
     "latex": r"A=\begin{pmatrix}1&1\\0&0\end{pmatrix},\ B=\begin{pmatrix}1&0\\1&0\end{pmatrix}:\ (AB)^\top\ne A^\top B^\top.",
     "code": "import sympy as sp\nA=sp.Matrix([[1,1],[0,0]]);B=sp.Matrix([[1,0],[1,0]])\nassert (A*B).T!=A.T*B.T and (A*B).T==B.T*A.T\n"
             "print('VERIFIED: counterexample holds:',(A*B).T,'!=',A.T*B.T)"},
    {"id": "cnt_contraction_incomplete_space", "keywords": [["contraction", "fixed point", "banach"]],
     "title": r"Contraction on an incomplete space: $T(x)=x/2$ on $(0,1]$",
     "claim": "Every contraction has a fixed point", "missing": "completeness of the metric space (and T mapping X into X)",
     "latex": r"T(x)=x/2 \text{ on } X=(0,1]:\ |Tx-Ty|=\tfrac12|x-y|, \text{ but } T x = x \iff x=0\notin X.",
     "code": "import sympy as sp\nx=sp.symbols('x')\nsol=sp.solve(sp.Eq(x/2,x),x)\nassert sol==[0]\n"
             "print('VERIFIED: counterexample holds: only fixed point of x/2 is',sol[0],'which is outside (0,1]')"},
    {"id": "cnt_expected_max_gt_max_expected", "keywords": [["max", "maximum", "argmax"], ["expect", "mean", "average", "e["]],
     "title": r"$\mathbb E[\max(Z_1,Z_2)]=1/\sqrt\pi>0=\max\mathbb E[Z_i]$",
     "claim": "The expectation of a max equals the max of expectations", "missing": "degenerate (noise-free) estimates",
     "latex": r"Z_1,Z_2\overset{iid}\sim\mathcal N(0,1):\ \mathbb E[\max(Z_1,Z_2)]=\tfrac{1}{\sqrt\pi}\approx0.564>0.",
     "code": "import numpy as np, sympy as sp\nrng=np.random.default_rng(0)\nZ=rng.standard_normal((400000,2))\nm=Z.max(1).mean()\n"
             "assert abs(m-1/np.sqrt(np.pi))<0.01\nprint('VERIFIED: counterexample holds: E[max]=%.4f vs max E=0' % m)"},
    {"id": "cnt_variance_correlated_sum", "keywords": [["variance", "var"], ["sum", "add", "additive"]],
     "title": r"Variance of a correlated sum: $\operatorname{Var}(X+X)=4\neq 2$",
     "claim": "Variance of a sum is always the sum of variances", "missing": "pairwise uncorrelatedness",
     "latex": r"\operatorname{Var}(X+X)=\operatorname{Var}(2X)=4\operatorname{Var}(X)\ne 2\operatorname{Var}(X).",
     "code": "import numpy as np\nrng=np.random.default_rng(1)\nX=rng.standard_normal(500000)\nv=np.var(X+X)\nassert abs(v-4)<0.05\n"
             "print('VERIFIED: counterexample holds: Var(X+X)=%.3f, not 2' % v)"},
    {"id": "cnt_matrix_commute", "keywords": [["commute", "ab = ba", "ab=ba", "order doesn't matter", "order does not matter"]],
     "title": r"Non-commuting rotations-and-shears: $AB\neq BA$",
     "claim": "Matrix products commute", "missing": "simultaneous diagonalisability (e.g. both rotations in the same plane)",
     "latex": r"A=\begin{pmatrix}0&1\\0&0\end{pmatrix},\ B=\begin{pmatrix}0&0\\1&0\end{pmatrix}:\ AB\ne BA.",
     "code": "import sympy as sp\nA=sp.Matrix([[0,1],[0,0]]);B=sp.Matrix([[0,0],[1,0]])\nassert A*B!=B*A\nprint('VERIFIED: counterexample holds:',A*B,'!=',B*A)"},
    {"id": "cnt_rotation_absolute_position", "keywords": [["rotation", "rope", "rotary"], ["absolute", "position m", "depends on m"]],
     "title": r"RoPE scores do not depend on absolute position",
     "claim": "Rotary attention scores depend on absolute positions", "missing": "orthogonality: $R_m^\\top R_n=R_{n-m}$",
     "latex": r"\langle R_m q, R_n k\rangle=\langle R_{m+s} q, R_{n+s} k\rangle \text{ for every shift } s.",
     "code": "import sympy as sp\nm,n,s,t=sp.symbols('m n s theta',real=True)\nR=lambda a: sp.Matrix([[sp.cos(a*t),-sp.sin(a*t)],[sp.sin(a*t),sp.cos(a*t)]])\n"
             "q=sp.Matrix([1,2]);k=sp.Matrix([3,-1])\nd=sp.simplify(((R(m)*q).T*(R(n)*k))[0]-((R(m+s)*q).T*(R(n+s)*k))[0])\nassert d==0\n"
             "print('VERIFIED: counterexample holds: score invariant under shift s')"},
]
UNIVERSAL_RX = re.compile(r"\b(always|every|all|any|for all|for any|never|whenever|must)\b", re.I)


def find_universal_claims(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    return [s.strip() for s in sentences if UNIVERSAL_RX.search(s) and len(s.strip()) > 12]


def match_counterexample(sentence: str) -> Optional[dict[str, Any]]:
    s = sentence.lower()
    best, best_score = None, 0
    for c in COUNTEREXAMPLE_LIBRARY:
        if all(any(k in s for k in group) for group in c["keywords"]):
            score = sum(1 for g in c["keywords"] for k in g if k in s)
            if score > best_score:
                best, best_score = c, score
    return best


async def synthesize_counterexample(session_id: Optional[str], text: str, node: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Scan the learner's text for hypothesis-dropping universal claims; attach a verified COUNTEREXAMPLE node."""
    claims = find_universal_claims(text)
    picked = None
    for c in claims:
        m = match_counterexample(c)
        if m:
            picked = (c, m)
            break
    if not picked and claims:
        llm_res = await llm.complete_json(prompts.SUBAGENT_PROMPTS["COUNTEREXAMPLE_SYNTHESIZER"],
                                          prompts.node_context(node) + "\n\nLearner text:\n" + text, max_tokens=1200)
        d = llm_res.data or {}
        if all(k in d for k in ("claim", "counterexample_latex", "code")):
            picked = (d["claim"], {"id": f"cnt_{_slug(d.get('title') or d['claim'], 36)}", "title": d.get("title") or d["claim"],
                                   "claim": d["claim"], "missing": d.get("missing_hypothesis", ""),
                                   "latex": d["counterexample_latex"], "code": d["code"]})
    if not picked:
        return None
    sentence, ce = picked
    res, _ = await symbolic_verify(session_id, ce["code"], f"Counterexample check: {ce['claim']}")
    out: dict[str, Any] = {}

    async def work() -> tuple[str, str]:
        if not res.verified:
            raise RuntimeError(f"counterexample failed verification; not attached.\n{res.as_log()}")
        node_id = ce["id"]
        with db.tx() as conn:
            if not db.node_exists(conn, node_id):
                db.upsert_node(conn, {
                    "id": node_id, "title": ce["title"], "node_type": "COUNTEREXAMPLE", "statement_latex": ce["latex"],
                    "intuition_summary": f"Refutes the over-general claim “{ce['claim']}”; missing hypothesis: {ce['missing']}.",
                    "formal_proof_sketch_latex": "", "domain_cluster": node["domain_cluster"],
                    "logical_depth": node["logical_depth"], "last_reviewed_at": db.now_iso(),
                    "created_in_session_id": session_id,
                })
            already = any(e["edge_type"] == "CONTRASTIVE" and node_id in e["premise_node_ids"] and e["conclusion_node_id"] == node["id"]
                          for e in db.all_edges(conn))
            if not already:
                db.insert_edge(conn, "CONTRASTIVE", [node_id], node["id"],
                               rf"\text{{Counterexample to: {_latex_text(ce['claim'])}}}",
                               rf"\text{{Requires: }} {ce['missing']}", session_id)
            db.recompute_depths(conn)
        out.update(node_id=node_id, claim=sentence, title=ce["title"], latex=ce["latex"], missing=ce["missing"])
        payload = (f"Learner claim: “{sentence}”\nOver-general pattern: {ce['claim']}\nMissing hypothesis: {ce['missing']}\n"
                   f"Counterexample: {ce['latex']}\nAttached node: {node_id}\n\n{res.as_log()}")
        return payload, f"Counterexample · {ce['claim']}"

    await run_agent("COUNTEREXAMPLE_SYNTHESIZER", session_id, f"Refuting: {sentence[:60]}", "sympy_log", work)
    return out or None


# ------------------------------------------------------------------ 4. SANDBOX_DEMO_BUILDER
def demo_targets(html: str) -> list[str]:
    m = re.search(r"<!--\s*harness-targets:\s*(\[.*?\])\s*-->", html)
    if m:
        try:
            return list(json.loads(m.group(1)))
        except json.JSONDecodeError:
            return []
    return []


async def build_demo(session_id: Optional[str], topic: str, node: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    async def work() -> tuple[str, str]:
        title = f"Interactive demo · {node['title'] if node else topic}"
        demo_id = f"demo_{_slug((node or {}).get('id', topic), 40)}"
        html = None
        llm_res = await llm.complete_json(prompts.SUBAGENT_PROMPTS["SANDBOX_DEMO_BUILDER"],
                                          (prompts.node_context(node) if node else "") + f"\nTopic: {topic}\nDemo id: {demo_id}",
                                          max_tokens=6000)
        if llm_res.data and isinstance(llm_res.data.get("html"), str) and "<!DOCTYPE html" in llm_res.data["html"] \
                and "HARNESS_DEMO_TELEMETRY" in llm_res.data["html"] and "http" not in re.sub(r"https?://www\.w3\.org[^\"']*", "", llm_res.data["html"]):
            html = llm_res.data["html"]
            title = llm_res.data.get("title") or title
        if html is None:
            html = demos.build_demo_html(demo_id, title, topic + " " + (node or {}).get("title", ""),
                                         (node or {}).get("statement_latex", ""))
        targets = [node["id"]] if node else []
        html = html.replace("</html>", f"<!-- harness-targets: {json.dumps(targets)} -->\n</html>", 1) \
            if "harness-targets" not in html else html
        return html, title

    return await run_agent("SANDBOX_DEMO_BUILDER", session_id, f"Building demo: {topic[:60]}", "html_demo", work)


# ------------------------------------------------------------------ 5. SVG_DIAGRAM_MAKER
async def make_svg(session_id: Optional[str], node: dict[str, Any]) -> dict[str, Any]:
    async def work() -> tuple[str, str]:
        with db.ro() as conn:
            edges = [e for e in db.all_edges(conn) if node["id"] in e["premise_node_ids"] or e["conclusion_node_id"] == node["id"]]
            ids = {node["id"]} | {p for e in edges for p in e["premise_node_ids"]} | {e["conclusion_node_id"] for e in edges}
            nodes = [n for n in (db.get_node(conn, i) for i in ids) if n]
        svg = demos.build_svg_diagram(f"Neighbourhood of {node['title']}", nodes, edges)
        return svg, f"Diagram · {node['title']}"

    return await run_agent("SVG_DIAGRAM_MAKER", session_id, f"Drawing {node['title']}", "svg", work)


# ------------------------------------------------------------------ 6. LOCAL_CORPUS_RAG
async def corpus_rag(session_id: Optional[str], query: str, attached: list[str] | None = None,
                     pattern: str = "") -> dict[str, Any]:
    async def work() -> tuple[str, str]:
        files = tools.list_workspace_files()
        blocks = tools.corpus_search(query)
        grep_hits = tools.grep_workspace(pattern or _grep_pattern(query))
        parts = [f"# Local corpus retrieval\nQuery: {query}\nFiles in workspace: {len(files)}\n"]
        for rel in attached or []:
            try:
                data = tools.read_workspace_file(rel)
                parts.append(f"## Attached: {rel} ({len(data['blocks'])} structured blocks)")
                for b in data["blocks"][:8]:
                    parts.append(f"- [{b['env']}] {b['title']} (line {b['line']})")
            except Exception as e:
                parts.append(f"## Attached: {rel} — unreadable: {e}")
        parts.append("## Best matching theorem/definition/problem blocks")
        for b in blocks:
            parts.append(f"### {b['path']}:{b['line']} — {b['env']} {b['title']}\n{b['body'][:600]}")
        parts.append("## grep hits")
        for h in grep_hits[:20]:
            parts.append(f"- {h['path']}:{h['line']}: {h['text'][:160]}")
        return "\n".join(parts), f"RAG · {len(blocks)} blocks, {len(grep_hits)} hits · {query[:40]}"

    return await run_agent("LOCAL_CORPUS_RAG", session_id, f"Searching notes for: {query[:50]}", "rag_excerpt", work)


def _grep_pattern(query: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z]{4,}", query)][:4]
    return "|".join(re.escape(w) for w in words) or "theorem"


# ------------------------------------------------------------------ 7. LITERATURE_RESEARCHER
async def literature(session_id: Optional[str], query: str) -> dict[str, Any]:
    async def work() -> tuple[str, str]:
        entries, source = await asyncio.to_thread(tools.search_arxiv, query)
        lines = [f"# Literature for: {query}", f"Source: {'arXiv API (live)' if source == 'arxiv' else 'offline knowledge base'}\n"]
        for e in entries:
            lines.append(f"- **{e['title']}** — {e['authors']} ({e['year']}) `{e['id']}`\n  {e['statement']}")
        return "\n".join(lines), f"Literature · {len(entries)} refs ({source}) · {query[:40]}"

    return await run_agent("LITERATURE_RESEARCHER", session_id, f"Researching: {query[:50]}", "rag_excerpt", work)


# ------------------------------------------------------------------ 8. ONTOLOGIST_EXTRACTOR
TYPE_FOR_ENV = {"definition": "AXIOM", "theorem": "PROPOSITION", "proposition": "PROPOSITION", "lemma": "PROPOSITION",
                "corollary": "PROPOSITION", "problem": "MOVE", "example": "INTUITION", "remark": "INTUITION"}
DOMAIN_KEYWORDS = {
    "Reinforcement Learning": ("bellman", "q-learning", "policy", "reward", "mdp", "value function", "dqn", "markov decision"),
    "Transformers & Attention": ("attention", "transformer", "softmax", "token", "rope", "rotary", "embedding", "mlp"),
    "Measure-Theoretic Probability": ("expectation", "variance", "random variable", "measure", "integral", "convergence", "probability", "jensen"),
    "Linear Algebra & Functional Analysis": ("matrix", "inner product", "orthogonal", "norm", "contraction", "banach", "linear", "metric"),
}


def guess_domain(text: str) -> str:
    t = text.lower()
    best, score = "Linear Algebra & Functional Analysis", 0
    for dom, kws in DOMAIN_KEYWORDS.items():
        s = sum(t.count(k) for k in kws)
        if s > score:
            best, score = dom, s
    return best


def import_tex_blocks(conn, rel_path: str, session_id: Optional[str]) -> dict[str, list[str]]:
    """Deterministic ontology extraction from a .tex file: definitions → AXIOM, theorems → PROPOSITION,
    problems → MOVE; within a section, every definition is a DEDUCTION premise of every theorem."""
    data = tools.read_tex_or_md(rel_path)
    added_nodes, added_edges = [], []
    section_defs: list[str] = []
    stem = _slug(rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0], 20)
    for b in data["blocks"]:
        if b["env"] in ("section", "subsection"):
            section_defs = []
            continue
        ntype = TYPE_FOR_ENV.get(b["env"])
        if not ntype or not b["body"]:
            continue
        nid = f"{stem}_{_slug(b['title'] or b['env'], 28)}_{b['line']}"
        if not db.node_exists(conn, nid):
            db.upsert_node(conn, {
                "id": nid, "title": b["title"] or f"{b['env'].title()} (line {b['line']})", "node_type": ntype,
                "statement_latex": b["body"][:1200], "intuition_summary": f"Imported from {rel_path}:{b['line']}",
                "formal_proof_sketch_latex": "", "domain_cluster": guess_domain(b["body"] + " " + b["title"]),
                "logical_depth": 0, "last_reviewed_at": db.now_iso(), "created_in_session_id": session_id,
            })
            added_nodes.append(nid)
        if ntype == "AXIOM":
            section_defs.append(nid)
        elif ntype == "PROPOSITION" and section_defs:
            eid = f"he_{nid}_from_defs"
            if not any(e["id"] == eid for e in db.all_edges(conn)):
                db.insert_edge(conn, "DEDUCTION", list(section_defs), nid,
                               rf"\text{{From the definitions in this section of {rel_path}}}", "", session_id, edge_id=eid)
                added_edges.append(eid)
    return {"nodes": added_nodes, "edges": added_edges}


async def ontologist(session_id: Optional[str], session: Optional[dict[str, Any]] = None,
                     import_file: Optional[str] = None) -> dict[str, Any]:
    out: dict[str, Any] = {}

    async def work() -> tuple[str, str]:
        diff: dict[str, Any] = {"added_nodes": [], "added_edges": [], "depth_changes": {}, "note_path": None}
        transcript = ""
        with db.tx() as conn:
            if import_file and import_file.endswith(".tex"):
                r = import_tex_blocks(conn, import_file, session_id)
                diff["added_nodes"] += r["nodes"]
                diff["added_edges"] += r["edges"]
            if session:
                plan = session["dependency_plan"]
                existing = db.all_edges(conn)
                for i, item in enumerate(plan):
                    if item.get("remedial") and i + 1 < len(plan):
                        tgt = plan[i + 1]["node_id"]
                        src = item["node_id"]
                        if src != tgt and not any(e["edge_type"] == "DEDUCTION" and src in e["premise_node_ids"]
                                                  and e["conclusion_node_id"] == tgt for e in existing):
                            eid = db.insert_edge(conn, "DEDUCTION", [src], tgt,
                                                 r"\text{Remedial prerequisite discovered in session}", "", session_id)
                            diff["added_edges"].append(eid)
                traces = db.session_traces(conn, session["id"])
                transcript = "\n".join(
                    f"[{t['phase']}] nodes={t['target_node_ids']} outcome={t['outcome']} raw='{t['raw_prediction_locked'][:200]}' "
                    f"verify='{t['verification_thinking'][:300]}'" for t in traces)
        if session and transcript:
            llm_res = await llm.complete_json(prompts.SUBAGENT_PROMPTS["ONTOLOGIST_EXTRACTOR"],
                                              f"Session goal: {session['target_goal']}\nTranscript:\n{transcript[:9000]}",
                                              max_tokens=2500)
            if llm_res.data:
                try:
                    onto = LLMOntology.model_validate(llm_res.data)
                    with db.tx() as conn:
                        for n in onto.nodes[:8]:
                            nid = _slug(str(n.get("id") or n.get("title", "")), 48)
                            if n.get("node_type") not in ("AXIOM", "PROPOSITION", "MOVE", "COUNTEREXAMPLE", "INTUITION", "BUGGY_RULE"):
                                continue
                            if not db.node_exists(conn, nid):
                                db.upsert_node(conn, {"id": nid, "title": str(n.get("title", nid))[:160], "node_type": n["node_type"],
                                                      "statement_latex": str(n.get("statement_latex", ""))[:1500],
                                                      "intuition_summary": str(n.get("intuition_summary", ""))[:800],
                                                      "domain_cluster": n.get("domain_cluster") or guess_domain(str(n)),
                                                      "logical_depth": 0, "last_reviewed_at": db.now_iso(),
                                                      "created_in_session_id": session_id, "formal_proof_sketch_latex": ""})
                                diff["added_nodes"].append(nid)
                        for e in onto.hyperedges[:12]:
                            prem = [p for p in e.get("premise_node_ids", []) if db.node_exists(conn, p)]
                            concl = e.get("conclusion_node_id")
                            if e.get("edge_type") in ("DEDUCTION", "CONTRASTIVE", "ISOMORPHISM", "CUE_TRIGGER") and prem \
                                    and concl and db.node_exists(conn, concl) and concl not in prem:
                                diff["added_edges"].append(db.insert_edge(conn, e["edge_type"], prem, concl,
                                                                          str(e.get("reasoning_chain_latex", ""))[:1500],
                                                                          str(e.get("discriminating_condition_latex", ""))[:600],
                                                                          session_id))
                except Exception as exc:
                    diff["llm_error"] = str(exc)[:300]
        with db.tx() as conn:
            diff["depth_changes"] = db.recompute_depths(conn)
        if session:
            diff["note_path"] = export_session_note(session)
        out.update(diff)
        return json.dumps(diff, indent=2), (f"Ontology · +{len(diff['added_nodes'])} nodes, +{len(diff['added_edges'])} edges, "
                                            f"{len(diff['depth_changes'])} depth changes")

    await run_agent("ONTOLOGIST_EXTRACTOR", session_id, "Extracting propositions & implications", "graph_diff", work)
    await hub.broadcast("graph_updated", {"reason": "ontologist"})
    return out


def export_session_note(session: dict[str, Any]) -> str:
    with db.ro() as conn:
        traces = db.session_traces(conn, session["id"])
        plan_nodes = [db.get_node(conn, p["node_id"]) for p in session["dependency_plan"]]
        edges = db.all_edges(conn)
    ids = {n["id"] for n in plan_nodes if n}
    lines = [f"# Session note — {session['title']}", "",
             f"- **Mode:** {session['mode']} / {session['sub_mode']}", f"- **Goal:** {session['target_goal']}",
             f"- **Final step velocity** $\\Delta = {session['step_velocity_delta']:.1f}$", f"- **Session id:** `{session['id']}`", "",
             "## Propositions (dependency order)", ""]
    for n in plan_nodes:
        if not n:
            continue
        lines += [f"### {n['title']} (`{n['id']}`, {n['node_type']}, depth {n['logical_depth']})", "",
                  f"$$ {n['statement_latex']} $$", "", f"*Intuition:* {n['intuition_summary']}", "",
                  f"Mastery $P(L)={n['bkt_p_mastery']:.2f}$ · stability $S={n['fsrs_stability']:.1f}$ d · difficulty $D={n['fsrs_difficulty']:.1f}$", ""]
    lines += ["## Implications touching this session", ""]
    for e in edges:
        if e["conclusion_node_id"] in ids or ids & set(e["premise_node_ids"]):
            sym = {"DEDUCTION": r"\implies", "CONTRASTIVE": r"\perp", "ISOMORPHISM": r"\cong", "CUE_TRIGGER": r"\leadsto"}[e["edge_type"]]
            lines.append(f"- {e['edge_type']}: {', '.join(e['premise_node_ids'])} ${sym}$ {e['conclusion_node_id']} — {e['reasoning_chain_latex'][:200]}")
    lines += ["", "## Telemetry trace", "", "| step | phase | outcome | conf | q | miss | ΔP(L) | ΔS (d) |", "|---|---|---|---|---|---|---|---|"]
    for t in traces:
        lines.append(f"| {t['step_index']} | {t['phase']} | {t['outcome']} | {t['confidence_slider']:.2f} | {t['trace_quality_score']:.2f} | "
                     f"{t['miss_class']} | {t['bkt_mastery_after'] - t['bkt_mastery_before']:+.3f} | "
                     f"{t['fsrs_stability_after'] - t['fsrs_stability_before']:+.2f} |")
    return tools.write_note(f"session_{session['id']}.md", "\n".join(lines) + "\n")


ALL_RUNNERS = ("SYMBOLIC_VERIFIER", "BUG_LIBRARY_DIAGNOSTICIAN", "COUNTEREXAMPLE_SYNTHESIZER", "SANDBOX_DEMO_BUILDER",
               "SVG_DIAGRAM_MAKER", "LOCAL_CORPUS_RAG", "LITERATURE_RESEARCHER", "ONTOLOGIST_EXTRACTOR")
