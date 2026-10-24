"""Cross-domain seed dataset (ARCHITECTURE_SPEC.md §7): 20 nodes, 16 hyperedges, 3 demos, 3 sessions.

Learner state is staggered (review ages × stabilities) so every overlay — Bjork window, decay, hypercorrection —
has something to show on first launch. The 3 sessions are produced by driving the real orchestrator with a
scripted learner under the deterministic engine, so their traces are genuine outputs of the cognitive models.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db, demos, llm

LA = "Linear Algebra & Functional Analysis"
PR = "Measure-Theoretic Probability"
TR = "Transformers & Attention"
RL = "Reinforcement Learning"
BUG = "Buggy Rules"

# (id, type, domain, depth, title, statement, intuition, proof sketch,
#  learner state: (P(L), S days, D, reviewed days ago, hypercorrection flag, cues[5]))
NODES: list[tuple] = [
    ("ax_inner_product_bilinearity", "AXIOM", LA, 0, "Bilinearity & symmetry of the inner product",
     r"\langle u, v\rangle = u^\top v \text{ on } \mathbb{R}^d \text{ is symmetric and bilinear: } \langle au+bw, v\rangle = a\langle u,v\rangle + b\langle w,v\rangle",
     "The dot product is a sum of coordinate-wise products, so scaling or adding one argument passes straight through.",
     r"\langle au+bw,v\rangle=\sum_i (au_i+bw_i)v_i=a\sum_i u_iv_i+b\sum_i w_iv_i.",
     (0.92, 30.0, 2.5, 21.0, 0, [0.9, 0.6, 0.5, 0.7, 0.2])),
    ("ax_orthogonal_matrix_preserve", "AXIOM", LA, 0, "Orthogonal maps preserve inner products",
     r"Q^\top Q = I \implies \langle Qu, Qv\rangle = u^\top Q^\top Q v = \langle u, v\rangle,\ \ \|Qu\|_2=\|u\|_2",
     "Rotations and reflections are rigid motions: they move vectors around without stretching or changing angles.",
     r"\langle Qu,Qv\rangle=(Qu)^\top(Qv)=u^\top Q^\top Q v=u^\top v.",
     (0.85, 12.0, 3.5, 9.0, 0, [0.8, 0.4, 0.6, 0.3, 0.1])),
    ("prop_2d_rotation_group", "PROPOSITION", LA, 1, "2D rotations depend only on relative angle",
     r"R(\theta)=\begin{pmatrix}\cos\theta&-\sin\theta\\ \sin\theta&\cos\theta\end{pmatrix},\quad R(\alpha)^\top R(\beta)=R(\beta-\alpha)",
     "Undoing a rotation by α and then rotating by β is the same as rotating by the difference β − α.",
     r"R(\alpha)^\top=R(-\alpha)\text{ and } R(-\alpha)R(\beta)=R(\beta-\alpha)\text{ by the angle-addition formulas.}",
     (0.62, 4.0, 5.0, 10.0, 0, [0.5, 0.2, 0.4, 0.2, 0.0])),
    ("prop_banach_contraction", "PROPOSITION", LA, 1, "Banach fixed-point theorem",
     r"T:X\to X,\ d(Tx,Ty)\le\gamma\,d(x,y),\ \gamma\in[0,1),\ (X,d)\text{ complete} \implies \exists!\,x^*=Tx^*,\ d(x_k,x^*)\le\gamma^k d(x_0,x^*)",
     "Each application of T shrinks all distances by γ, so iterates form a Cauchy sequence that must land on one point.",
     r"d(x_{k+1},x_k)\le\gamma^k d(x_1,x_0)\Rightarrow(x_k)\text{ Cauchy}\Rightarrow x_k\to x^*\text{ (completeness)}; Tx^*=x^*\text{ by continuity; uniqueness: } d(x^*,y^*)\le\gamma d(x^*,y^*).",
     (0.55, 6.0, 5.5, 6.0, 0, [0.4, 0.1, 0.3, 0.2, 0.0])),
    ("int_covector_hyperplanes", "INTUITION", LA, 1, "Covectors as stacks of level-set hyperplanes",
     r"\omega\in V^*\ \leftrightarrow\ \{v:\omega(v)=c\}_{c\in\mathbb{Z}},\qquad df_x(v)=\nabla f(x)^\top v",
     "A linear functional is a family of parallel sheets; ω(v) counts how many sheets v pierces. Gradient steps cross the densest stacks.",
     r"\text{By Riesz, }\omega(v)=\langle w,v\rangle;\ \text{level sets are hyperplanes orthogonal to } w \text{ spaced } 1/\|w\|.",
     (0.40, 2.0, 6.0, 5.5, 0, [0.2, 0.0, 0.5, 0.0, 0.0])),
    ("ax_linearity_expectation", "AXIOM", PR, 0, "Linearity of expectation (no independence needed)",
     r"\mathbb{E}\Big[\sum_i a_iX_i\Big]=\sum_i a_i\,\mathbb{E}[X_i]\ \text{ for any integrable } X_i",
     "Expectation is an integral, and integrals are linear — dependence between the X_i never enters.",
     r"\mathbb{E}[aX+bY]=\int (aX+bY)\,dP=a\int X\,dP+b\int Y\,dP.",
     (0.90, 25.0, 2.8, 19.0, 0, [0.9, 0.5, 0.2, 0.8, 0.3])),
    ("prop_var_indep_sum", "PROPOSITION", PR, 1, "Variance adds for uncorrelated sums; scales quadratically",
     r"\operatorname{Var}\Big(\sum_{i=1}^d X_i\Big)=d\sigma^2\ \text{(uncorrelated, each } \sigma^2),\qquad \operatorname{Var}(cX)=c^2\operatorname{Var}(X)",
     "Cross terms are covariances; when they vanish only the d diagonal variances survive. Scaling by c scales deviations by c, squared deviations by c².",
     r"\operatorname{Var}(\sum X_i)=\sum_i\operatorname{Var}X_i+2\sum_{i<j}\operatorname{Cov}(X_i,X_j)=d\sigma^2.",
     (0.70, 5.0, 4.5, 5.5, 1, [0.6, 0.3, 0.1, 0.5, 0.1])),
    ("prop_var_product_indep", "PROPOSITION", PR, 1, "Variance of a product of independent zero-mean variables",
     r"X\perp\!\!\!\perp Y,\ \mathbb{E}X=\mathbb{E}Y=0 \implies \operatorname{Var}(XY)=\mathbb{E}[X^2]\mathbb{E}[Y^2]=\sigma_X^2\sigma_Y^2",
     "With zero means, the product has zero mean, and independence lets the second moment factor.",
     r"\mathbb{E}[XY]=\mathbb{E}X\,\mathbb{E}Y=0,\ \ \operatorname{Var}(XY)=\mathbb{E}[X^2Y^2]=\mathbb{E}[X^2]\mathbb{E}[Y^2].",
     (0.50, 3.0, 5.0, 8.0, 0, [0.4, 0.1, 0.0, 0.3, 0.0])),
    ("prop_jensen_convex_max", "PROPOSITION", PR, 1, "Jensen for the max: E[max] ≥ max E",
     r"\phi(x)=\max_a x_a \text{ convex} \implies \mathbb{E}\big[\max_a Z_a\big]\ge\max_a\mathbb{E}[Z_a]",
     "Noise pushes the maximum up: whichever coordinate is luckily high gets picked, so the average of maxima overshoots.",
     r"\max_a Z_a\ge Z_b\ \forall b\Rightarrow\mathbb{E}\max_a Z_a\ge\mathbb{E}Z_b\ \forall b\Rightarrow\ \ge\max_b\mathbb{E}Z_b.",
     (0.45, 2.5, 5.5, 7.5, 0, [0.3, 0.1, 0.2, 0.1, 0.0])),
    ("prop_dct_vs_mct", "PROPOSITION", PR, 2, "Dominated vs. Monotone Convergence",
     r"\text{DCT: } f_n\to f,\ |f_n|\le g\in L^1\Rightarrow\int f_n\to\int f;\qquad \text{MCT: } 0\le f_n\uparrow f\Rightarrow\int f_n\uparrow\int f",
     "You may swap lim and ∫ when mass cannot escape: either an integrable envelope fences it in (DCT) or monotone growth from below forbids loss (MCT).",
     r"\text{DCT via Fatou applied to } g\pm f_n;\ \text{MCT via simple-function approximation and monotonicity.}",
     (0.30, 1.5, 6.5, 9.0, 1, [0.2, 0.0, 0.0, 0.0, 0.1])),
    ("cnt_unbounded_indicator_escape", "COUNTEREXAMPLE", PR, 2, "Mass escaping to a spike",
     r"f_n=n\,\mathbf{1}_{(0,1/n)}\to0 \text{ pointwise on }(0,1),\quad \int f_n\,d\lambda=1\ne0=\int\lim f_n\,d\lambda",
     "A unit of area squeezed into ever-taller, thinner spikes vanishes pointwise yet keeps its integral — no L¹ envelope exists.",
     r"\int_0^1 n\mathbf 1_{(0,1/n)}=n\cdot\tfrac1n=1;\ \sup_n f_n(x)\approx 1/x\notin L^1(0,1).",
     (0.35, 1.2, 6.0, 1.0, 0, [0.3, 0.0, 0.4, 0.0, 0.0])),
    ("bug_uncorrelated_implies_indep", "BUGGY_RULE", BUG, 1, "Misconception: uncorrelated ⇒ independent",
     r"\operatorname{Cov}(X,Y)=0\ \overset{?}{\implies}\ X\perp\!\!\!\perp Y\quad(\text{false: } X\sim\mathcal N(0,1),\ Y=X^2)",
     "Covariance only sees linear dependence; Y = X² is perfectly dependent on X yet uncorrelated with it.",
     r"\operatorname{Cov}(X,X^2)=\mathbb{E}[X^3]-\mathbb{E}X\,\mathbb{E}X^2=0,\ \text{but } P(|X|<1,Y<1)\ne P(|X|<1)P(Y<1).",
     (0.15, 1.0, 5.0, 3.0, 0, [0.0, 0.0, 0.0, 0.0, 0.0])),
    ("prop_row_local_mlp", "PROPOSITION", TR, 1, "Position-wise MLPs never mix tokens",
     r"X\in\mathbb{R}^{T\times d},\ W\in\mathbb{R}^{d\times d'}:\ \big(\sigma(XW)\big)_{t,:}=\sigma(x_t^\top W)",
     "Right-multiplication acts on each row separately and σ is coordinate-wise, so row t of the output only ever sees row t of the input.",
     r"(XW)_{tj}=\sum_k X_{tk}W_{kj}=\langle x_t, W_{:,j}\rangle \text{ depends on row } t \text{ only.}",
     (0.75, 8.0, 4.0, 6.5, 0, [0.7, 0.4, 0.3, 0.6, 0.0])),
    ("prop_causal_mask_support", "PROPOSITION", TR, 1, "Causal masking restricts outputs to the past",
     r"M_{ij}=\begin{cases}0&j\le i\\-\infty&j>i\end{cases}\Rightarrow A=\operatorname{softmax}(S+M),\ A_{ij}=0\ (j>i),\ (AV)_{i,:}\in\operatorname{span}\{v_1,\dots,v_i\}",
     "Adding −∞ before softmax turns those logits into exp(−∞) = 0 weights, so future values receive no attention.",
     r"A_{ij}=e^{S_{ij}+M_{ij}}/\sum_k e^{S_{ik}+M_{ik}}=0\text{ for }j>i;\ (AV)_i=\sum_{j\le i}A_{ij}v_j.",
     (0.80, 10.0, 3.8, 8.0, 0, [0.8, 0.5, 0.4, 0.5, 0.2])),
    ("prop_scaled_dot_product_variance", "PROPOSITION", TR, 2, "Why attention divides by √d_k",
     r"q,k\in\mathbb{R}^{d_k}\text{ iid, mean }0,\text{ var }1:\ \operatorname{Var}(q^\top k)=d_k,\ \ \operatorname{Var}\big(q^\top k/\sqrt{d_k}\big)=1",
     "Each q_i k_i has variance 1 and the d_k terms are uncorrelated, so logits grow like √d_k and saturate softmax unless rescaled.",
     r"\operatorname{Var}(\sum_i q_ik_i)=\sum_i\operatorname{Var}(q_ik_i)=\sum_i \mathbb{E}q_i^2\mathbb{E}k_i^2=d_k;\ \operatorname{Var}(cZ)=c^2\operatorname{Var}Z,\ c=1/\sqrt{d_k}.",
     (0.58, 3.0, 5.2, 2.4, 1, [0.5, 0.2, 0.3, 0.2, 0.0])),
    ("prop_rope_relative_invariance", "PROPOSITION", TR, 2, "RoPE encodes relative position in the score",
     r"\langle R_{\Theta,m}q,\ R_{\Theta,n}k\rangle=q^\top R_{\Theta,m}^\top R_{\Theta,n}k=q^\top R_{\Theta,n-m}k",
     "Rotate q by its position and k by its position; because rotations are orthogonal and compose by angle difference, only n − m survives.",
     r"\text{Block-diagonal } R_{\Theta,m}=\oplus_i R(m\theta_i);\ R(m\theta_i)^\top R(n\theta_i)=R((n-m)\theta_i)\text{ blockwise.}",
     (0.38, 1.8, 6.2, 4.0, 0, [0.3, 0.0, 0.4, 0.1, 0.0])),
    ("move_scalar_base_case_check", "MOVE", TR, 1, "Move: reduce to the 1×1 scalar case first",
     r"\text{To check a tensor/matrix identity, set } d=1 \text{ (or } n=2\text{) and verify scaling powers and variances.}",
     "If an identity fails for scalars it fails everywhere; the scalar case also exposes the exponent of d in any variance scaling.",
     r"\text{E.g. } \operatorname{Var}(q^\top k)\text{ at } d_k=1 \text{ is } \operatorname{Var}(q_1k_1)=1, \text{ at } d_k=2 \text{ it is } 2 \Rightarrow \text{linear in } d_k.",
     (0.65, 4.5, 4.6, 3.3, 0, [0.6, 0.2, 0.1, 0.6, 0.0])),
    ("prop_bellman_sup_norm_contraction", "PROPOSITION", RL, 2, "Bellman optimality operator is a γ-contraction",
     r"(\mathcal T^*V)(s)=\max_a\Big[R(s,a)+\gamma\sum_{s'}P(s'|s,a)V(s')\Big],\quad \|\mathcal T^*U-\mathcal T^*V\|_\infty\le\gamma\|U-V\|_\infty",
     "Two value guesses that differ by at most ε anywhere produce backups that differ by at most γε: the discount shrinks every disagreement.",
     r"|\max_a f(a)-\max_a g(a)|\le\max_a|f(a)-g(a)|\le\gamma\max_{s'}|U(s')-V(s')|;\ \text{Banach}\Rightarrow\exists!\,V^*.",
     (0.52, 2.8, 5.4, 14.0, 0, [0.4, 0.1, 0.3, 0.1, 0.0])),
    ("prop_qlearning_maximization_bias", "PROPOSITION", RL, 2, "Q-learning's maximization bias",
     r"Y_t=R_{t+1}+\gamma\max_aQ_\theta(S_{t+1},a):\quad \mathbb{E}\big[\max_a\hat Q(s',a)\big]>\max_a\mathbb{E}\big[\hat Q(s',a)\big]",
     "The max picks whichever estimate got lucky noise, so the bootstrapped target is systematically too high.",
     r"\text{Jensen for the convex max applied to } \hat Q=Q+\varepsilon,\ \mathbb{E}\varepsilon=0;\ \text{strict when } \varepsilon \text{ non-degenerate.}",
     (0.28, 1.0, 6.8, 6.0, 1, [0.2, 0.0, 0.0, 0.1, 0.0])),
    ("prop_double_dqn_decoupling", "PROPOSITION", RL, 3, "Double DQN decouples selection from evaluation",
     r"a^*=\arg\max_aQ_\theta(S_{t+1},a),\quad Y_t^{\text{DDQN}}=R_{t+1}+\gamma\,Q_{\theta^-}(S_{t+1},a^*)",
     "Let one network pick the action and an independently-noisy one score it: the lucky noise that drove the pick no longer inflates the score.",
     r"\text{If errors of } \theta,\theta^- \text{ are independent, } \mathbb{E}[Q_{\theta^-}(s',a^*)\mid a^*]=Q(s',a^*)\le\max_aQ(s',a).",
     (0.20, 0.8, 7.0, 0.3, 0, [0.1, 0.0, 0.0, 0.0, 0.0])),
]

# (id, type, premises, conclusion, reasoning chain, discriminating condition)
EDGES: list[tuple] = [
    ("he_rotation_from_orthogonal", "DEDUCTION", ["ax_orthogonal_matrix_preserve"], "prop_2d_rotation_group",
     r"R(\theta)^\top R(\theta)=I \Rightarrow R(\alpha)^\top=R(-\alpha);\ R(-\alpha)R(\beta)=R(\beta-\alpha)\text{ (angle addition)}.", ""),
    ("he_rope_from_rotations", "DEDUCTION", ["ax_orthogonal_matrix_preserve", "prop_2d_rotation_group"], "prop_rope_relative_invariance",
     r"\langle R_mq,R_nk\rangle=q^\top R_m^\top R_nk\ \text{(orthogonal adjoint)}=q^\top R_{n-m}k\ \text{(rotation group, blockwise)}.", ""),
    ("he_covector_from_inner_product", "DEDUCTION", ["ax_inner_product_bilinearity"], "int_covector_hyperplanes",
     r"\text{Bilinearity makes } v\mapsto\langle w,v\rangle \text{ linear; its level sets } \langle w,v\rangle=c \text{ are parallel hyperplanes.}", ""),
    ("he_rowlocal_from_inner_product", "DEDUCTION", ["ax_inner_product_bilinearity"], "prop_row_local_mlp",
     r"(XW)_{tj}=\langle x_t,W_{:,j}\rangle \text{ involves row } t \text{ only; coordinate-wise } \sigma \text{ preserves this.}", ""),
    ("he_varsum_from_linearity", "DEDUCTION", ["ax_linearity_expectation"], "prop_var_indep_sum",
     r"\operatorname{Var}(\sum X_i)=\mathbb{E}[(\sum (X_i-\mu_i))^2]=\sum_{i,j}\operatorname{Cov}(X_i,X_j)\ \text{(linearity)};\ \text{off-diagonal terms vanish.}", ""),
    ("he_varprod_from_linearity", "DEDUCTION", ["ax_linearity_expectation"], "prop_var_product_indep",
     r"\operatorname{Var}(XY)=\mathbb{E}[X^2Y^2]-(\mathbb{E}XY)^2;\ \text{independence factors both moments, zero means kill the second term.}", ""),
    ("he_jensen_from_linearity", "DEDUCTION", ["ax_linearity_expectation"], "prop_jensen_convex_max",
     r"\max_aZ_a\ge Z_b\ \forall b;\ \text{monotonicity + linearity of } \mathbb{E}\Rightarrow \mathbb{E}\max_aZ_a\ge\max_b\mathbb{E}Z_b.", ""),
    ("he_sdpa_from_variance", "DEDUCTION", ["prop_var_indep_sum", "prop_var_product_indep"], "prop_scaled_dot_product_variance",
     r"\operatorname{Var}(q_ik_i)=1\ \text{(product rule)};\ \operatorname{Var}(\sum_i q_ik_i)=d_k\ \text{(uncorrelated sum)};\ \operatorname{Var}(\cdot/\sqrt{d_k})=1\ \text{(quadratic scaling)}.", ""),
    ("he_bellman_from_banach", "DEDUCTION", ["prop_banach_contraction"], "prop_bellman_sup_norm_contraction",
     r"|\max f-\max g|\le\max|f-g| \Rightarrow \|\mathcal T^*U-\mathcal T^*V\|_\infty\le\gamma\|U-V\|_\infty;\ (\mathbb{R}^{|S|},\|\cdot\|_\infty) \text{ complete} \Rightarrow \text{Banach applies.}", ""),
    ("he_bellman_iso_picard", "ISOMORPHISM", ["prop_banach_contraction"], "prop_bellman_sup_norm_contraction",
     r"\text{Value iteration } V_{k+1}=\mathcal T^*V_k \;\cong\; \text{Picard iteration } x_{k+1}=Tx_k:\ \text{same geometric rate } \gamma^k.", ""),
    ("he_maxbias_from_jensen_bellman", "DEDUCTION", ["prop_jensen_convex_max", "prop_bellman_sup_norm_contraction"], "prop_qlearning_maximization_bias",
     r"\text{The Bellman target applies } \max_a \text{ to noisy } \hat Q;\ \text{Jensen for the convex max} \Rightarrow \text{upward bias, which the contraction then propagates.}", ""),
    ("he_ddqn_from_maxbias", "DEDUCTION", ["prop_qlearning_maximization_bias"], "prop_double_dqn_decoupling",
     r"\text{The bias comes from using the same noise to select and to evaluate; decorrelating them removes the selection-induced term.}", ""),
    ("he_dqn_vs_ddqn", "CONTRASTIVE", ["prop_qlearning_maximization_bias"], "prop_double_dqn_decoupling",
     r"\text{Standard DQN target } \max_aQ_{\theta^-}(s',a) \;\perp\; \text{Double DQN target } Q_{\theta^-}(s',\arg\max_aQ_\theta(s',a)).",
     r"\text{Same network for argmax and evaluation (biased)} \;\text{vs.}\; \text{decorrelated networks (unbiased under independent errors).}"),
    ("he_bug_vs_varsum", "CONTRASTIVE", ["bug_uncorrelated_implies_indep"], "prop_var_indep_sum",
     r"\text{Variance additivity needs only } \operatorname{Cov}=0;\ \text{the bug upgrades that to independence.}",
     r"\operatorname{Cov}(X,Y)=0 \not\Rightarrow X\perp\!\!\!\perp Y\ \ (Y=X^2);\ \text{equivalence holds for jointly Gaussian } (X,Y)."),
    ("he_spike_vs_dct", "CONTRASTIVE", ["cnt_unbounded_indicator_escape"], "prop_dct_vs_mct",
     r"\text{The spike sequence satisfies pointwise convergence but no integrable envelope exists, so DCT does not apply.}",
     r"\exists g\in L^1,\ |f_n|\le g\ \text{(DCT)}\ \text{vs.}\ \sup_n f_n\sim 1/x\notin L^1."),
    ("he_cue_scalar_check", "CUE_TRIGGER", ["move_scalar_base_case_check"], "prop_scaled_dot_product_variance",
     r"\text{Cue: a } \sqrt{d_k} \text{ (or any power of } d) \text{ in a tensor formula} \leadsto \text{set } d_k=1,2 \text{ and read off the exponent.}", ""),
]


def _ts(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def seed_graph(conn) -> None:
    for (nid, ntype, dom, depth, title, stmt, intuition, sketch, state) in NODES:
        p, s, d, ago, flag, cues = state
        db.upsert_node(conn, {
            "id": nid, "title": title, "node_type": ntype, "statement_latex": stmt, "intuition_summary": intuition,
            "formal_proof_sketch_latex": sketch, "domain_cluster": dom, "logical_depth": depth,
            "bkt_p_mastery": p, "fsrs_stability": s, "fsrs_difficulty": d, "fsrs_reps": max(1, int(s // 2)),
            "fsrs_lapses": 1 if flag else 0, "last_reviewed_at": _ts(ago),
            "cue_symbolic": cues[0], "cue_disguised_notation": cues[1], "cue_geometric": cues[2],
            "cue_computational": cues[3], "cue_adversarial": cues[4],
            "brier_sum": 0.62 if flag else 0.0, "brier_count": 1 if flag else 0, "hypercorrection_flag": flag,
            "last_miss_class": "FALSE_ANALOGY" if flag else "NONE",
        })
    for (eid, etype, prem, concl, chain, disc) in EDGES:
        db.insert_edge(conn, etype, prem, concl, chain, disc, None, edge_id=eid,
                       mastery=0.5 if etype != "DEDUCTION" else 0.55)
    for d in demos.DEMO_SEED:
        db.insert_artifact(conn, "SANDBOX_DEMO_BUILDER", "COMPLETED", d["title"], d["content_type"],
                           d["payload_text"].replace("</html>", f"<!-- harness-targets: {__import__('json').dumps(d['target_node_ids'])} -->\n</html>", 1),
                           None, artifact_id=d["id"])
    db.recompute_depths(conn)


async def _answer_active(session_id: str, good: bool, confidence: float, text: str) -> dict[str, Any]:
    """Scripted learner: answers the active step using its hidden key when `good`."""
    from .agents import orchestrator
    with db.ro() as conn:
        s = db.load_session(conn, session_id)
    a = s["active_step"]
    meta = a.get("_meta", {})
    kind = a["kind"]
    sub: dict[str, Any] = {"step_id": a["step_id"], "raw_prediction_locked": text, "confidence": confidence,
                           "verification_thinking": text,
                           "prosody": {"initial_latency_ms": 2400 if not good else 900, "total_silence_ms": 3100,
                                       "hesitation_count": 1 if good else 4, "hedge_count": 0 if good else 3, "wpm": 118,
                                       "hedge_density": 0.0 if good else 0.08, "engine": "browser"}}
    if kind in ("PROBE", "CHECK"):
        opts = [o["id"] for o in a["options"]]
        sub["selected_answer"] = meta["correct"] if good else next(o for o in opts if o != meta["correct"])
    elif kind == "PRACTICE_CHUNK":
        groups = meta.get("concept_groups", [])
        chunk_text = " ".join(g[0] for g in (groups if good else groups[:1])) + ". " + text
        await orchestrator.chunk(session_id, chunk_text, confidence)
    elif kind == "READING":
        sub["thinking_while_reading"] = [{"quote": a["body_markdown"][:60], "thought": text, "timestamp_ms": 4200}]
    return await orchestrator.submit(session_id, sub)


async def seed_sessions() -> None:
    from .agents import orchestrator
    token = llm.force_deterministic.set(True)
    try:
        # 1. Completed Probe → Teach on scaled dot-product attention (historical)
        st = await orchestrator.create_session({"mode": "PROBE", "target_goal": "Why does attention divide by sqrt(d_k)?",
                                                "target_node_id": "prop_scaled_dot_product_variance"})
        sid = st["session"]["id"]
        script = [(True, 0.8), (False, 0.85), (True, 0.7), (True, 0.8), (True, 0.85), (True, 0.9), (True, 0.85),
                  (True, 0.9), (True, 0.9), (True, 0.9), (True, 0.9), (True, 0.9), (True, 0.9), (True, 0.9)]
        for good, conf in script:
            with db.ro() as conn:
                if db.load_session(conn, sid)["status"] != "ACTIVE":
                    break
            await _answer_active(sid, good, conf,
                                 "Each q_i k_i has variance 1 and the terms are uncorrelated so the variance of the sum is d_k; "
                                 "dividing by sqrt(d_k) scales variance by 1/d_k, quadratic scaling, back to 1." if good else
                                 "I think it's to normalise like a mean, dividing by d_k, it's always like averaging every term.")
        # 2. Active Adaptive Practice on the Q-learning maximization bias (one chunk in progress)
        st = await orchestrator.create_session({"mode": "PRACTICE", "target_goal": "Maximization bias in Q-learning",
                                                "target_node_id": "prop_qlearning_maximization_bias", "cue_level": 2,
                                                "contrastive_pair": True})
        sid = st["session"]["id"]
        with db.ro() as conn:
            meta = db.load_session(conn, sid)["active_step"]["_meta"]
        first = meta["concept_groups"][0][0] if meta.get("concept_groups") else "max"
        await orchestrator.chunk(sid, f"Hmm, the target uses a {first} over noisy estimates... maybe the noise matters? "
                                       "With two arms the cross term shows up: (x+y)^2 = x^2 + 2xy + y^2", 0.5)
        # 3. Active Proof-Referee duel on dominated convergence (fresh, unanswered)
        await orchestrator.create_session({"mode": "REFEREE_DUEL", "sub_mode": "PROOF_REFEREE",
                                           "target_goal": "When can I swap a limit and an integral?",
                                           "target_node_id": "prop_dct_vs_mct"})
    finally:
        llm.force_deterministic.reset(token)


async def seed_if_empty() -> bool:
    db.init_db()
    with db.ro() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
    if n:
        return False
    with db.tx() as conn:
        seed_graph(conn)
    await seed_sessions()
    return True


if __name__ == "__main__":
    print("seeded" if asyncio.run(seed_if_empty()) else "database already populated")
