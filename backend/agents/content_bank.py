"""Deterministic (no-LLM) teaching content for the 20 LearnHarness seed nodes.

Used whenever no LLM is available. Every node carries:
  probe / predict / reading / check / productive_failure / practice (cue levels 1-4) /
  referee (5-step proof with one camouflaged fallacy) / feynman (buggy-student duel) /
  misconceptions (bug-library entries).

Pedagogical laws (ARCHITECTURE_SPEC.md section 4) enforced in the content:
  * readings start from a scalar / 2x2 / n=2 base case and add one implication at a time,
    stay under 180 words, and end with a self-explanation question (Laws 2, 4);
  * every probe / check is preceded by an open prediction (Law 3);
  * practice prompts are situational cues that never name the theorem (Law 5);
  * every hint ladder follows R0 type-shape check -> R1 attention pointer (with {quote}) ->
    R2 cue prime -> R3 base-case reduction -> R4 worked isomorphic analog (Law 6).

Each ``verify_code`` snippet is self-contained (numpy / sympy / scipy) and prints a line starting
with ``VERIFIED:`` when the canonical answer checks out.
"""

from typing import TypedDict, Any


class Option(TypedDict):
    id: str
    label: str


class MultipleChoice(TypedDict):
    prompt: str
    options: list[Option]
    correct: str
    explanation: str


class Predict(TypedDict):
    prompt: str


class ProductiveFailure(TypedDict):
    prompt: str
    canonical_insight: str


class HintLadder(TypedDict):
    R0: str
    R1: str
    R2: str
    R3: str
    R4: str


class PracticeItem(TypedDict):
    prompt: str
    answer_summary: str
    concept_groups: list[list[str]]
    verify_code: str
    hints: HintLadder


class Referee(TypedDict):
    claim: str
    steps: list[str]
    flawed_index: int
    violated_keywords: list[str]
    explanation: str
    counterexample: str


class BoundaryCondition(TypedDict):
    id: str
    label: str
    keywords: list[str]
    challenge: str


class Feynman(TypedDict):
    buggy_rule_id: str | None
    persona: str
    opening: str
    boundary_conditions: list[BoundaryCondition]


class Misconception(TypedDict):
    trigger_keywords: list[str]
    miss_class: str
    buggy_title: str
    buggy_statement_latex: str


class NodeContent(TypedDict):
    probe: MultipleChoice
    predict: Predict
    reading: str
    check: MultipleChoice
    productive_failure: ProductiveFailure
    practice: dict[int, PracticeItem]
    referee: Referee
    feynman: Feynman
    misconceptions: list[Misconception]


def _opts(a: str, b: str, c: str, d: str) -> list[Option]:
    return [
        {"id": "A", "label": a},
        {"id": "B", "label": b},
        {"id": "C", "label": c},
        {"id": "D", "label": d},
    ]


def _hints(r0: str, r1: str, r2: str, r3: str, r4: str) -> HintLadder:
    return {"R0": r0, "R1": r1, "R2": r2, "R3": r3, "R4": r4}


def _bc(id_: str, label: str, keywords: list[str], challenge: str) -> BoundaryCondition:
    return {"id": id_, "label": label, "keywords": keywords, "challenge": challenge}


def _mis(trigger_keywords: list[str], miss_class: str, title: str, latex: str) -> Misconception:
    return {
        "trigger_keywords": trigger_keywords,
        "miss_class": miss_class,
        "buggy_title": title,
        "buggy_statement_latex": latex,
    }


CONTENT: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------ Cluster A
    "ax_inner_product_bilinearity": {
        "probe": {
            "prompt": r"For $u, v \in \mathbb{R}^d$, which expression equals $\langle 2u + v,\; u - 3v \rangle$?",
            "options": _opts(
                r"$2\|u\|^2 - 3\|v\|^2$",
                r"$2\|u\|^2 - 5\langle u, v\rangle - 3\|v\|^2$",
                r"$2\|u\|^2 - 6\langle u, v\rangle - 3\|v\|^2$",
                r"$2\|u\|^2 - 7\langle u, v\rangle - 3\|v\|^2$",
            ),
            "correct": "B",
            "explanation": r"Expand slot by slot: $2\langle u,u\rangle - 6\langle u,v\rangle + \langle v,u\rangle - 3\langle v,v\rangle$. Symmetry merges $-6\langle u,v\rangle + \langle v,u\rangle = -5\langle u,v\rangle$. Option A drops the cross terms; C forgets the $\langle v,u\rangle$ term; D adds instead of cancelling.",
        },
        "predict": {
            "prompt": r"Before reading: if you double one vector and leave the other alone, what happens to their dot product? If you replace $u$ by $u + w$, can you predict $\langle u + w, v\rangle$ from numbers you already know, without touching the $d$ coordinates again?",
        },
        "reading": r"""**Base case $d = 1$.** Here $\langle u, v\rangle = uv$, ordinary multiplication: it distributes, $(au + bw)v = a\,uv + b\,wv$, and commutes, $uv = vu$.

**Step to $d = 2$.** $u^\top v = u_1 v_1 + u_2 v_2$ is a *sum of $d=1$ products*, so each property survives coordinate by coordinate:
$$\langle au + bw,\, v\rangle = a\langle u, v\rangle + b\langle w, v\rangle, \qquad \langle u, v\rangle = \langle v, u\rangle.$$
Linear in the first slot; by symmetry, linear in the second. Nothing changes for general $d$.

**One implication further.** Apply both slots at once:
$$\|u+v\|^2 = \langle u+v, u+v\rangle = \|u\|^2 + 2\langle u, v\rangle + \|v\|^2.$$
The cross term appears twice ($\langle u,v\rangle$ and $\langle v,u\rangle$) and symmetry lets us merge them. Note that linearity is *per slot*: $\langle 2u, 2v\rangle = 4\langle u, v\rangle$, not $2\langle u,v\rangle$.

**Self-explanation:** Why does $\|u+v\|^2$ carry the coefficient $2$ on the cross term, and for which pairs $u, v$ does that term vanish?""",
        "check": {
            "prompt": r"Using Einstein summation (repeated indices summed), let $s(a, b) = a_i b_i$. Simplify $s(a + b,\; a - b)$.",
            "options": _opts(
                r"$a_i a_i + b_i b_i$",
                r"$0$",
                r"$a_i a_i - b_i b_i$",
                r"$a_i a_i - 2 a_i b_i - b_i b_i$",
            ),
            "correct": "C",
            "explanation": r"$s(a+b, a-b) = a_ia_i - a_ib_i + b_ia_i - b_ib_i$; symmetry ($a_ib_i = b_ia_i$) cancels the cross terms, leaving $\|a\|^2 - \|b\|^2$.",
        },
        "productive_failure": {
            "prompt": r"You are told only three numbers: $\|u\| = 3$, $\|v\| = 4$, $\|u + v\| = 5$. No coordinates. Find $\langle u, v\rangle$ and $\|u - v\|$. Then try to invent a general formula that recovers $\langle u, v\rangle$ from lengths alone.",
            "canonical_insight": r"Expanding $\|u \pm v\|^2 = \|u\|^2 \pm 2\langle u,v\rangle + \|v\|^2$ (bilinearity + symmetry) gives $25 = 9 + 2\langle u,v\rangle + 16$, so $\langle u,v\rangle = 0$ and $\|u-v\| = 5$. Subtracting the two expansions yields the polarization identity $\langle u, v\rangle = \tfrac14\big(\|u+v\|^2 - \|u-v\|^2\big)$: lengths determine all inner products.",
        },
        "practice": {
            1: {
                "prompt": r"Your recommender scores a user vector $u$ against item embeddings by dot product. A new item is created as the blend $v_{\text{new}} = 0.7\,v_a + 0.3\,v_b$. You already cached $u^\top v_a = 2.0$ and $u^\top v_b = -1.0$. What is the new item's score, and why can you skip touching the 768 coordinates?",
                "answer_summary": r"$u^\top(0.7 v_a + 0.3 v_b) = 0.7(2.0) + 0.3(-1.0) = 1.1$, because the dot product is linear in its second argument.",
                "concept_groups": [["1.1"], ["linear", "distribut", "bilinear", "split"]],
                "verify_code": r"""import sympy as sp
u = sp.Matrix(sp.symbols('u0:4')); a = sp.Matrix(sp.symbols('a0:4')); b = sp.Matrix(sp.symbols('b0:4'))
c1, c2 = sp.Rational(7, 10), sp.Rational(3, 10)
lhs = (u.T * (c1 * a + c2 * b))[0]
rhs = c1 * (u.T * a)[0] + c2 * (u.T * b)[0]
assert sp.expand(lhs - rhs) == 0
score = c1 * 2 + c2 * (-1)
assert score == sp.Rational(11, 10)
print('VERIFIED: blended score =', float(score))
""",
                "hints": _hints(
                    r"Type check: the score is a scalar and the blend weights sum to 1. Should the new score lie between the two cached scores?",
                    r"You wrote “{quote}”. Which property of the dot product would let you move the 0.7 and 0.3 outside?",
                    r"What happens to $u^\top(v_a + v_b)$ if you write it coordinate by coordinate?",
                    r"Do it with $d = 1$: $u = 2$, $v_a = 1$, $v_b = -0.5$. Compute $u(0.7 v_a + 0.3 v_b)$ both directly and as $0.7(uv_a) + 0.3(uv_b)$.",
                    r"Analog: a portfolio's return is $w^\top r$. If $w = 0.5 w_1 + 0.5 w_2$ with returns $w_1^\top r = 4\%$, $w_2^\top r = 2\%$, then $w^\top r = 0.5(4\%) + 0.5(2\%) = 3\%$. Transfer this exact move to the item blend.",
                ),
            },
            2: {
                "prompt": r"A physics-style note writes the metric pairing as $g(\mathbf a, \mathbf b) = \sum_i a^i b^i$. An embedding drifts as $e_{t+1} = e_t + \delta$. Express the change in squared length $g(e_{t+1}, e_{t+1}) - g(e_t, e_t)$ using only $g(e_t, \delta)$ and $g(\delta, \delta)$.",
                "answer_summary": r"$g(e_t+\delta, e_t+\delta) - g(e_t,e_t) = 2\,g(e_t,\delta) + g(\delta,\delta)$ by bilinearity and symmetry of $g$.",
                "concept_groups": [["2g", "2 g", "2·g", "2*g", "twice", "two cross"], ["g(δ,δ)", "g(δ, δ)", "g(\\delta", "g(d,d)", "g(delta", "‖δ‖", "|δ|", "δ²", "delta squared"]],
                "verify_code": r"""import sympy as sp
e = sp.Matrix(sp.symbols('e0:3')); d = sp.Matrix(sp.symbols('d0:3'))
g = lambda a, b: (a.T * b)[0]
lhs = g(e + d, e + d) - g(e, e)
rhs = 2 * g(e, d) + g(d, d)
assert sp.expand(lhs - rhs) == 0
print('VERIFIED: g(e+d,e+d) - g(e,e) = 2 g(e,d) + g(d,d)')
""",
                "hints": _hints(
                    r"Shape check: both sides must be scalars, and the answer must be $0$ when $\delta = 0$. Does yours pass?",
                    r"In “{quote}”, how many cross terms does expanding the pairing produce before you merge them?",
                    r"The symbol $g$ is just a dot product in disguise. What do you already know about $\|x + y\|^2$?",
                    r"Take one coordinate: $(e + \delta)^2 - e^2$. What do you get?",
                    r"Analog: $(x+h)^2 - x^2 = 2xh + h^2$. Each piece has a pairing counterpart: $xh \to g(e,\delta)$, $h^2 \to g(\delta,\delta)$. Rewrite your answer with those.",
                ),
            },
            3: {
                "prompt": r"Your retrieval system L2-normalizes all embeddings. One teammate ranks neighbours by squared Euclidean distance $\|u - v\|^2$, another by cosine similarity. Will they ever disagree on the ranking? Give the exact relation between the two scores.",
                "answer_summary": r"For unit vectors, $\|u - v\|^2 = \|u\|^2 - 2\langle u,v\rangle + \|v\|^2 = 2 - 2\langle u,v\rangle$, a strictly decreasing affine function of cosine similarity, so the rankings are identical (reversed order of the scores).",
                "concept_groups": [["2 - 2", "2-2", "2−2", "2 − 2", "2(1-", "2(1 -", "2(1−", "2(1 −"], ["cross term", "expand", "bilinear", "symmetr"], ["same rank", "never disagree", "identical rank", "same order", "monoton", "won't disagree", "do not disagree", "don't disagree"]],
                "verify_code": r"""import sympy as sp
a, b = sp.symbols('a b', real=True)
u = sp.Matrix([sp.cos(a), sp.sin(a)]); v = sp.Matrix([sp.cos(b), sp.sin(b)])
dist2 = ((u - v).T * (u - v))[0]
cos_sim = (u.T * v)[0]
assert sp.simplify(dist2 - (2 - 2 * cos_sim)) == 0
print('VERIFIED: ||u-v||^2 = 2 - 2<u,v> for unit vectors')
""",
                "hints": _hints(
                    r"Limit check: what is $\|u-v\|^2$ when $u = v$, and when $u = -v$? Which cosine values do those correspond to?",
                    r"Look at “{quote}”. What happens to the terms $\|u\|^2$ and $\|v\|^2$ once you use that the embeddings are normalized?",
                    r"You already know how to expand $\|u+v\|^2$. What changes when the sign in the middle is a minus?",
                    r"Do it in $\mathbb{R}^2$ with $u = (1, 0)$ and $v = (\cos\theta, \sin\theta)$. Compute $\|u-v\|^2$ and compare with $\cos\theta$.",
                    r"Analog: for scalars on the unit circle, $|e^{ia} - e^{ib}|^2 = 2 - 2\cos(a-b)$. Distance is a decreasing function of the cosine. Transfer that to general unit vectors.",
                ),
            },
            4: {
                "prompt": r"A colleague defines a learned similarity $s(u, v) = u^\top A v$ with $A = \begin{pmatrix}1 & 2\\ 0 & 1\end{pmatrix}$ and expands $s(u+v, u+v) = s(u,u) + 2\,s(u,v) + s(v,v)$. Test the expansion on $u = e_1$, $v = e_2$ and fix it.",
                "answer_summary": r"$A$ is not symmetric, so $s(u,v) \neq s(v,u)$ in general. The correct expansion is $s(u,u) + s(u,v) + s(v,u) + s(v,v)$; the cross term is $u^\top(A + A^\top)v$. With $u=e_1, v=e_2$: true value $1 + 2 + 0 + 1 = 4$, the colleague's formula gives $6$.",
                "concept_groups": [["symmetr", "a^t", "a^\\top", "s(v,u)", "s(v, u)", "transpose"], ["4"], ["6", "a + a^t", "a+a^t", "a + a^\\top"]],
                "verify_code": r"""import numpy as np
A = np.array([[1., 2.], [0., 1.]])
s = lambda x, y: x @ A @ y
u, v = np.array([1., 0.]), np.array([0., 1.])
true = s(u + v, u + v)
claimed = s(u, u) + 2 * s(u, v) + s(v, v)
fixed = s(u, u) + s(u, v) + s(v, u) + s(v, v)
assert np.isclose(true, 4) and np.isclose(claimed, 6) and np.isclose(fixed, true)
assert np.isclose(s(u, v) + s(v, u), u @ (A + A.T) @ v)
print('VERIFIED: true 4, claimed 6, cross term u^T(A+A^T)v')
""",
                "hints": _hints(
                    r"Before expanding, check the one property the merge “$s(u,v) + s(v,u) = 2s(u,v)$” needs. Is $A$ equal to $A^\top$?",
                    r"In “{quote}”, which step treats the pairing as if swapping its arguments changes nothing?",
                    r"For the plain dot product, which axiom licensed merging the two cross terms?",
                    r"Compute $s(e_1, e_2)$ and $s(e_2, e_1)$ directly from the entries of $A$.",
                    r"Analog: for $B = \begin{pmatrix}0 & 1\\ 0 & 0\end{pmatrix}$, $e_1^\top B e_2 = 1$ but $e_2^\top B e_1 = 0$, so $(e_1+e_2)^\top B (e_1+e_2) = 1 \ne 2$. Redo this with the colleague's $A$.",
                ),
            },
        },
        "referee": {
            "claim": r"For every square matrix $A \in \mathbb{R}^{d\times d}$ and all $u, v \in \mathbb{R}^d$: $\langle Au, v\rangle = \langle u, Av\rangle$.",
            "steps": [
                r"By definition of the inner product, $\langle Au, v\rangle = (Au)^\top v$.",
                r"Transposing the column vector $Au$ just lays it flat: $(Au)^\top = u^\top A$, so $\langle Au, v\rangle = u^\top A v$.",
                r"Matrix multiplication is associative, so $u^\top A v = u^\top (Av)$.",
                r"By definition of the inner product, $u^\top (Av) = \langle u, Av\rangle$.",
                r"Hence $\langle Au, v\rangle = \langle u, Av\rangle$: every square matrix is self-adjoint.",
            ],
            "flawed_index": 2,
            "violated_keywords": ["transpose", "reverse", "a^t", "a^\\top", "u^t a^t", "order", "symmetric", "(ab)^t"],
            "explanation": r"Transposition reverses products: $(Au)^\top = u^\top A^\top$, not $u^\top A$. The correct chain gives $\langle Au, v\rangle = \langle u, A^\top v\rangle$, which equals $\langle u, Av\rangle$ only when $A$ is symmetric.",
            "counterexample": r"$A = \begin{pmatrix}0&1\\0&0\end{pmatrix}$, $u = e_2$, $v = e_1$: $\langle Au, v\rangle = \langle e_1, e_1\rangle = 1$ but $\langle u, Av\rangle = \langle e_2, 0\rangle = 0$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Sam, a first-year ML student who treats dot products exactly like multiplication of real numbers, including the rule that a zero product forces a zero factor.",
            "opening": r"So the dot product is 'linear', which I think means $\langle 2u, 2v\rangle = 2\langle u, v\rangle$. And since it's just multiplication, if $\langle u, v\rangle = 0$ then $u$ or $v$ must be zero. Can you explain what bilinearity actually guarantees?",
            "boundary_conditions": [
                _bc("per_slot_linearity", r"Linear in each argument separately (the other held fixed), so scaling both by $a$ scales by $a^2$",
                    ["each argument", "each slot", "one argument at a time", "other fixed", "separately", "a^2", "a²", "4⟨", "4 times"],
                    r"If it's linear, then scaling both vectors by 2 should scale the result by 2, right?"),
                _bc("symmetry_scope", r"Symmetry $\langle u,v\rangle = \langle v,u\rangle$ holds for the real dot product $u^\top v$; a general form $u^\top A v$ is symmetric only if $A = A^\top$",
                    ["symmetr", "a = a^t", "a=a^t", "a^\\top", "u^t a v", "real"],
                    r"Then any similarity $u^\top A v$ is symmetric too — swapping $u$ and $v$ never matters?"),
                _bc("orthogonal_not_zero", r"$\langle u,v\rangle = 0$ means orthogonal, not zero; only $\langle u,u\rangle = 0$ forces $u = 0$ (positive definiteness)",
                    ["orthogonal", "perpendicular", "positive definite", "⟨u,u⟩", "<u,u>", "only if u = 0", "only if u=0"],
                    r"$e_1 \cdot e_2 = 0$ — so which one of them is the zero vector?"),
            ],
        },
        "misconceptions": [
            _mis(["linear in both at once", "jointly linear", "<2u,2v> = 2", "⟨2u,2v⟩ = 2", "scales by 2"], "FALSE_ANALOGY",
                 "Joint linearity", r"\langle a u, a v\rangle = a\langle u, v\rangle"),
            _mis(["one of them must be zero", "dot product zero means zero vector", "so u or v is zero"], "FALSE_ANALOGY",
                 "Zero-divisor analogy", r"\langle u, v\rangle = 0 \implies u = 0 \lor v = 0"),
            _mis(["no cross term", "(u+v)^2 = u^2 + v^2", "norm of sum is sum of norms squared"], "ALGEBRAIC_SLIP",
                 "Dropped cross term", r"\|u+v\|^2 = \|u\|^2 + \|v\|^2"),
        ],
    },
    "ax_orthogonal_matrix_preserve": {
        "probe": {
            "prompt": r"Which matrix preserves the Euclidean length of **every** vector in $\mathbb{R}^2$?",
            "options": _opts(
                r"$\begin{pmatrix}1&1\\0&1\end{pmatrix}$",
                r"$\begin{pmatrix}2&0\\0&1/2\end{pmatrix}$",
                r"$\begin{pmatrix}0&-1\\1&0\end{pmatrix}$",
                r"$\begin{pmatrix}1&0\\0&0\end{pmatrix}$",
            ),
            "correct": "C",
            "explanation": r"Only C has orthonormal columns ($Q^\top Q = I$). B has determinant 1 but stretches $e_1$ to length 2; A (a shear) also has determinant 1 yet sends $(0,1)$ to $(1,1)$; D collapses $e_2$.",
        },
        "predict": {
            "prompt": r"Predict: if a matrix has determinant $1$, must it preserve lengths? And if a matrix preserves every length, must it also preserve every angle between vectors? Commit to yes/no for each before reading.",
        },
        "reading": r"""**Base case $d = 1$.** A $1\times1$ "matrix" is a number $q$, and $|qx| = |x|$ for all $x$ iff $q^2 = 1$, i.e. $q^\top q = 1$.

**Step to $d = 2$.** Length squared is an inner product: $\|Qu\|^2 = (Qu)^\top(Qu) = u^\top Q^\top Q\, u$. If $Q^\top Q = I$, this is $u^\top u = \|u\|^2$.

**One implication further.** The same line with two vectors:
$$\langle Qu, Qv\rangle = u^\top Q^\top Q\, v = u^\top v = \langle u, v\rangle,$$
so angles and distances $\|Qu - Qv\| = \|Q(u-v)\|$ are preserved too.

**Reading the condition.** $(Q^\top Q)_{ij} = \langle Qe_i, Qe_j\rangle$, so $Q^\top Q = I$ says the columns are orthonormal. It forces $(\det Q)^2 = 1$, but not conversely: $\mathrm{diag}(2, \tfrac12)$ has determinant $1$ and doubles $e_1$. Determinant tracks area, not shape. For square $Q$, $Q^\top Q = I$ also gives $QQ^\top = I$.

**Self-explanation:** Expanding $\|Q(u+v)\|^2$, why does preserving every *length* already force preserving every *inner product*?""",
        "check": {
            "prompt": r"A whitening step uses a real square matrix $W$ with $W^{\mathsf H} W = I$ (over the reals, $\mathsf H$ is just transpose). For token vectors $a, b \ne 0$, the cosine of the angle between $Wa$ and $Wb$ equals:",
            "options": _opts(
                r"$\cos\angle(a,b)\cdot\det W$",
                r"$\cos\angle(a,b)$",
                r"$\cos\angle(a,b)/\|W\|_F$",
                r"It depends on $W$ beyond $W^{\mathsf H}W = I$",
            ),
            "correct": "B",
            "explanation": r"$\langle Wa, Wb\rangle = a^\top W^\top W b = \langle a,b\rangle$ and $\|Wa\| = \|a\|$, $\|Wb\| = \|b\|$, so the cosine is unchanged. $\det W = \pm1$ never enters.",
        },
        "productive_failure": {
            "prompt": r"Find **all** real $2\times2$ matrices that preserve the length of every vector. Try to parametrize them. How many continuous families are there, and which of them can be reached continuously from the identity?",
            "canonical_insight": r"Length preservation $\iff Q^\top Q = I \iff$ orthonormal columns. The first column is $(\cos\theta, \sin\theta)$; the second is a unit vector orthogonal to it, giving two choices: $(-\sin\theta, \cos\theta)$ (rotations, $\det = 1$, connected to $I$) or $(\sin\theta, -\cos\theta)$ (reflections, $\det = -1$). So $O(2)$ is two circles.",
        },
        "practice": {
            1: {
                "prompt": r"To anonymize embeddings before sharing, you multiply every embedding by the same random matrix $Q$ with $Q^\top Q = I$. A partner then runs Euclidean nearest-neighbour search. Do any neighbours change? Justify in one line of algebra.",
                "answer_summary": r"No: $\|Qu - Qv\|^2 = (u-v)^\top Q^\top Q (u-v) = \|u - v\|^2$, so all pairwise distances, hence all neighbour rankings, are unchanged.",
                "concept_groups": [["unchanged", "same neighbo", "do not change", "don't change", "doesn't change", "does not change", "preserved", "invariant", "nothing changes", "no change"], ["q^tq", "q^\\top q", "q^t q", "identity", "orthogonal", "orthonormal"], ["u - v", "u-v", "difference", "linear"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(0)
Q, _ = np.linalg.qr(rng.normal(size=(16, 16)))
X = rng.normal(size=(50, 16))
D0 = np.linalg.norm(X[:, None] - X[None], axis=-1)
Y = X @ Q.T
D1 = np.linalg.norm(Y[:, None] - Y[None], axis=-1)
assert np.allclose(D0, D1)
assert (np.argsort(D0, axis=1) == np.argsort(D1, axis=1)).mean() > 0.99
print('VERIFIED: all pairwise distances preserved under Q')
""",
                "hints": _hints(
                    r"Distances are lengths of differences. What does $Q$ do to the difference $u - v$?",
                    r"You wrote “{quote}”. Did you use the property of Q itself, or just its randomness?",
                    r"How do you write a squared length as an inner product, and what does $Q^\top Q = I$ do inside it?",
                    r"Take $d=1$, $Q = -1$. Is $|(-u) - (-v)| = |u - v|$?",
                    r"Analog: a rigid rotation of a map by $30^\circ$ leaves every city-to-city distance unchanged because $\|R(x-y)\| = \|x-y\|$. Transfer this to the anonymizing $Q$.",
                ),
            },
            2: {
                "prompt": r"A quantum-inspired layer uses a real square matrix $U \in \mathbb{R}^{n\times n}$, and the unit test only checks $UU^\top = I_n$ (note the order). A teammate fears $U^\top U = I$ was never verified, so $\|Ux\| = \|x\|$ might fail. Settle it, and say what would change if $U$ were $k\times n$ with $k < n$.",
                "answer_summary": r"For square $U$, $UU^\top = I$ means $U^\top$ is a right inverse, and a one-sided inverse of a square matrix is two-sided, so $U^\top U = I$ and norms are preserved. For a $k\times n$ $V$ with $VV^\top = I_k$, $V^\top V$ is a rank-$k$ projection, not $I_n$, and $\|Vx\| \le \|x\|$.",
                "concept_groups": [["square"], ["inverse", "u^{-1}", "two-sided", "left inverse", "right inverse"], ["projection", "rank", "rectangular", "k < n", "non-square", "not square"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(1)
U, _ = np.linalg.qr(rng.normal(size=(6, 6)))
assert np.allclose(U @ U.T, np.eye(6)) and np.allclose(U.T @ U, np.eye(6))
V = U[:3]          # 3 x 6 with orthonormal rows
assert np.allclose(V @ V.T, np.eye(3))
assert not np.allclose(V.T @ V, np.eye(6))
x = rng.normal(size=6)
assert np.linalg.norm(V @ x) < np.linalg.norm(x)
print('VERIFIED: square one-sided inverse is two-sided; rectangular V shrinks norms')
""",
                "hints": _hints(
                    r"Shape check: what are the shapes of $UU^\top$ and $U^\top U$ when $U$ is square, and when it is $k\times n$?",
                    r"Look at “{quote}”. What does $UU^\top = I$ say about $U^\top$ in terms of inverses?",
                    r"For square matrices, if $AB = I$, what do you know about $BA$?",
                    r"Try $n = 1$: $u^2 = 1$. Then try a $1\times2$ matrix $V = (1, 0)$: compute $VV^\top$ and $V^\top V$.",
                    r"Analog: $R(\theta)R(\theta)^\top = I$ and $R(\theta)^\top = R(-\theta)$ is its inverse from both sides. But $V = (\cos\theta\;\sin\theta)$ has $VV^\top = 1$ while $V^\top V$ is a rank-1 projection. Apply the same split to $U$.",
                ),
            },
            3: {
                "prompt": r"You push a ring of unit vectors through two candidate layers: $A = \mathrm{diag}(2, \tfrac12)$ and a rotation $R(\theta)$. Both have determinant $1$. Describe the image of the ring under each, and name the single matrix identity that separates them.",
                "answer_summary": r"$R(\theta)$ maps the unit circle onto itself; $A$ maps it to an ellipse with semi-axes $2$ and $\tfrac12$ (same area, distorted shape). The separating identity is $M^\top M = I$: $R^\top R = I$ but $A^\top A = \mathrm{diag}(4, \tfrac14)$. Determinant only measures area.",
                "concept_groups": [["ellipse", "stretch", "squash", "distort"], ["r^tr", "r^\\top r", "a^ta", "a^\\top a", "m^tm", "m^\\top m", "q^tq", "orthonormal column", "transpose times"], ["area", "volume"]],
                "verify_code": r"""import numpy as np
t = np.linspace(0, 2 * np.pi, 400)
ring = np.stack([np.cos(t), np.sin(t)])
A = np.diag([2.0, 0.5]); th = 0.7
R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
assert np.isclose(np.linalg.det(A), 1) and np.isclose(np.linalg.det(R), 1)
assert np.allclose(np.linalg.norm(R @ ring, axis=0), 1)
nA = np.linalg.norm(A @ ring, axis=0)
assert np.isclose(nA.max(), 2, atol=1e-3) and np.isclose(nA.min(), 0.5, atol=1e-3)
assert np.allclose(A.T @ A, np.diag([4, 0.25])) and np.allclose(R.T @ R, np.eye(2))
print('VERIFIED: R keeps the circle, A makes an ellipse (2, 1/2); A^T A != I')
""",
                "hints": _hints(
                    r"Track two test vectors: where do $e_1$ and $e_2$ go under $A$? What are their new lengths?",
                    r"In “{quote}”, what does determinant 1 actually guarantee — length, angle, or area?",
                    r"Which product of a matrix with itself encodes all the lengths and angles of its columns?",
                    r"Compute $A^\top A$ and $R^\top R$ entry by entry for $\theta = 90^\circ$.",
                    r"Analog: $S = \begin{pmatrix}1&1\\0&1\end{pmatrix}$ has $\det S = 1$, yet $S^\top S = \begin{pmatrix}1&1\\1&2\end{pmatrix} \ne I$ and $S(0,1)^\top = (1,1)^\top$ has length $\sqrt2$. Run the same test on $A$.",
                ),
            },
            4: {
                "prompt": r"To save memory you compress 512-d embeddings with $P \in \mathbb{R}^{64\times512}$ whose rows are orthonormal ($PP^\top = I_{64}$), then assume cosine scores between compressed vectors equal the original ones because 'P is orthogonal'. What is wrong, and what inequality does hold?",
                "answer_summary": r"$P$ is not square: $P^\top P$ is a rank-64 orthogonal projection, not $I_{512}$. So $\|Px\|^2 = x^\top P^\top P x \le \|x\|^2$, with equality only for $x$ in the row space; lengths and angles of general vectors change.",
                "concept_groups": [["p^tp", "p^\\top p", "projection", "rank", "not square", "rectangular"], ["≤", "<=", "less", "shrink", "smaller", "lose", "lost"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(2)
Q, _ = np.linalg.qr(rng.normal(size=(512, 512)))
P = Q[:64]
assert np.allclose(P @ P.T, np.eye(64))
M = P.T @ P
assert np.allclose(M @ M, M) and np.linalg.matrix_rank(M) == 64
x, y = rng.normal(size=512), rng.normal(size=512)
assert np.linalg.norm(P @ x) < np.linalg.norm(x)
cos = lambda a, b: a @ b / np.linalg.norm(a) / np.linalg.norm(b)
assert abs(cos(P @ x, P @ y) - cos(x, y)) > 1e-3
print('VERIFIED: P^T P is a rank-64 projection; norms shrink and cosines change')
""",
                "hints": _hints(
                    r"Shape check: is $P^\top P$ the same size as $PP^\top$? Which one would have to equal the identity for $\|Px\| = \|x\|$?",
                    r"You wrote “{quote}”. Which condition, $PP^\top = I$ or $P^\top P = I$, does the length computation $\|Px\|^2 = x^\top(\cdot)x$ actually need?",
                    r"What is the rank of a $64\times512$ matrix, and can a rank-64 matrix be the $512\times512$ identity?",
                    r"Take the $1\times2$ matrix $P = (1, 0)$ and $x = (0, 1)$. Compute $\|Px\|$.",
                    r"Analog: projecting 3-D points onto the floor plane with $P = \begin{pmatrix}1&0&0\\0&1&0\end{pmatrix}$ satisfies $PP^\top = I_2$, yet a vertical stick of length 1 becomes a point. Transfer to the 64-d compression.",
                ),
            },
        },
        "referee": {
            "claim": r"Every real square matrix $Q$ with $|\det Q| = 1$ preserves Euclidean norms: $\|Qx\| = \|x\|$ for all $x$.",
            "steps": [
                r"$\det(Q^\top Q) = \det(Q^\top)\det(Q) = (\det Q)^2 = 1$.",
                r"$Q^\top Q$ is symmetric positive semidefinite, so its eigenvalues are real, $\lambda_i \ge 0$, with $\prod_i \lambda_i = \det(Q^\top Q) = 1$.",
                r"A symmetric PSD matrix whose eigenvalues multiply to $1$ must have every eigenvalue equal to $1$, so $Q^\top Q = I$.",
                r"Therefore $\|Qx\|^2 = x^\top Q^\top Q x = x^\top x$.",
                r"Taking square roots, $\|Qx\| = \|x\|$ for every $x$.",
            ],
            "flawed_index": 3,
            "violated_keywords": ["product", "each eigenvalue", "individual", "4 and 1/4", "1/4", "0.25", "need not", "diag(2"],
            "explanation": r"A product of eigenvalues equal to $1$ does not force each eigenvalue to be $1$: $4 \cdot \tfrac14 = 1$. The determinant constrains volume only; norm preservation needs every eigenvalue of $Q^\top Q$ to be $1$.",
            "counterexample": r"$Q = \mathrm{diag}(2, \tfrac12)$: $\det Q = 1$, $Q^\top Q = \mathrm{diag}(4, \tfrac14)$, and $\|Qe_1\| = 2 \ne 1$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Priya, a graphics hobbyist who believes 'determinant 1 means the matrix is a rotation, so it keeps lengths'.",
            "opening": r"In my shader code I only check $\det M = 1$ to make sure a transform is rigid. Then lengths and angles are safe, right? Can you explain what actually guarantees that?",
            "boundary_conditions": [
                _bc("qtq_identity", r"The condition is $Q^\top Q = I$ (orthonormal columns), not $\det Q = 1$",
                    ["q^tq", "q^\\top q", "q^t q", "orthonormal", "columns"],
                    r"$\mathrm{diag}(2, 1/2)$ has determinant 1 — why doesn't it count as rigid?"),
                _bc("square_matrix", r"$Q$ must be square; a $k\times n$ matrix with $PP^\top = I_k$ ($k<n$) is a projection and shrinks norms",
                    ["square", "p^tp", "p^\\top p", "non-square", "rectangular", "projection"],
                    r"My $64\times512$ compressor has $PP^\top = I$ — that's orthogonal too, isn't it?"),
                _bc("inner_products_preserved", r"$Q^\top Q = I$ preserves inner products, hence angles and distances (polarization), not just lengths",
                    ["inner product", "angle", "polarization", "distance", "u^t v", "⟨qu, qv⟩"],
                    r"OK, lengths are preserved, but couldn't the angle between two vectors still change?"),
            ],
        },
        "misconceptions": [
            _mis(["det = 1", "determinant 1", "determinant one", "det is 1 so"], "FALSE_ANALOGY",
                 "Unit determinant implies isometry", r"\det Q = 1 \implies \|Qx\| = \|x\|"),
            _mis(["pp^t = i so", "orthonormal rows so it preserves", "projection preserves"], "BOUNDARY_OMISSION",
                 "Semi-orthogonal rectangular map is an isometry", r"PP^\top = I_k,\ P\in\mathbb{R}^{k\times n} \implies \|Px\| = \|x\|"),
            _mis(["(qu)^t = u^t q", "transpose of qu is u^t q"], "ALGEBRAIC_SLIP",
                 "Transpose without order reversal", r"(Qu)^\top = u^\top Q"),
        ],
    },
    "prop_2d_rotation_group": {
        "probe": {
            "prompt": r"With $R(\theta) = \begin{pmatrix}\cos\theta & -\sin\theta\\ \sin\theta & \cos\theta\end{pmatrix}$, compute $R(30^\circ)^\top R(75^\circ)$.",
            "options": _opts(r"$R(105^\circ)$", r"$R(45^\circ)$", r"$R(-45^\circ)$", r"$R(75^\circ)$"),
            "correct": "B",
            "explanation": r"$R(30^\circ)^\top = R(-30^\circ)$ and rotations compose by adding angles: $R(-30^\circ)R(75^\circ) = R(45^\circ)$. Only the relative angle $75^\circ - 30^\circ$ survives.",
        },
        "predict": {
            "prompt": r"Predict: you rotate a query vector by $\alpha$ and a key vector by $\beta$, then take their dot product. Which single number about the pair $(\alpha, \beta)$ does the result remember? Would it change if you added $10^\circ$ to both?",
        },
        "reading": r"""**Base case.** Rotating $e_1$ by $\theta$ gives $(\cos\theta, \sin\theta)$, rotating $e_2$ gives $(-\sin\theta, \cos\theta)$: these are the columns of
$$R(\theta) = \begin{pmatrix}\cos\theta & -\sin\theta\\ \sin\theta & \cos\theta\end{pmatrix}.$$

**Step 1: transpose is inverse.** $\cos$ is even and $\sin$ is odd, so $R(\theta)^\top = R(-\theta)$. Check: $R(\theta)^\top R(\theta)$ has diagonal $\cos^2\theta + \sin^2\theta = 1$ and off-diagonal $0$.

**Step 2: angles add.** The $(1,1)$ entry of $R(\alpha)R(\beta)$ is $\cos\alpha\cos\beta - \sin\alpha\sin\beta = \cos(\alpha+\beta)$; the other entries follow the same way, so $R(\alpha)R(\beta) = R(\alpha + \beta) = R(\beta)R(\alpha)$.

**Step 3: combine.**
$$R(\alpha)^\top R(\beta) = R(-\alpha)R(\beta) = R(\beta - \alpha).$$
Hence $\langle R(\alpha)q,\, R(\beta)k\rangle = q^\top R(\beta-\alpha)\,k$: only the *relative* angle appears. Caveat: commutation is special to planar rotations; reflections and 3-D rotations generally do not commute.

**Self-explanation:** Why does adding the same angle $\phi$ to both $\alpha$ and $\beta$ leave the inner product unchanged?""",
        "check": {
            "prompt": r"Identify $\mathbb{R}^2$ with $\mathbb{C}$. Encode $z_q = q\,e^{i\alpha}$ and $z_k = k\,e^{i\beta}$ for complex $q, k$. The real number $\mathrm{Re}(\overline{z_q}\, z_k)$ depends on the angles only through:",
            "options": _opts(r"$\alpha + \beta$", r"$\alpha\beta$", r"$\beta - \alpha$", r"$\max(\alpha, \beta)$"),
            "correct": "C",
            "explanation": r"$\overline{z_q}z_k = \bar q k\, e^{i(\beta - \alpha)}$. Complex conjugation is the transpose of a rotation; multiplying phases adds angles. $\mathrm{Re}(\bar z_q z_k)$ is exactly the real dot product of the two 2-vectors.",
        },
        "productive_failure": {
            "prompt": r"Design a way to inject token positions $m, n$ into 2-D queries and keys so that the attention score depends on the positions **only through the offset** $n - m$. Try additive position vectors $q + p_m$, $k + p_n$ first. Where does it fail, and what kind of operation fixes it?",
            "canonical_insight": r"Additive: $(q+p_m)^\top(k+p_n) = q^\top k + q^\top p_n + p_m^\top k + p_m^\top p_n$; the middle cross terms depend on absolute $n$ and $m$. Multiplicative rotations fix it: $(R(m\theta)q)^\top R(n\theta)k = q^\top R((n-m)\theta)k$ because $R^\top = R^{-1}$ and planar rotations compose by adding angles.",
        },
        "practice": {
            1: {
                "prompt": r"A 2-D toy attention head rotates the query at position $m$ by $m\theta$ and the key at position $n$ by $n\theta$, with $\theta = 0.1$ rad. Query $q = (1, 0)$ sits at $m = 3$, key $k = (0, 1)$ at $n = 8$. Compute the attention logit.",
                "answer_summary": r"Logit $= q^\top R(3\theta)^\top R(8\theta) k = q^\top R(0.5)k = (1,0)\cdot(-\sin 0.5, \cos 0.5) = -\sin 0.5 \approx -0.479$.",
                "concept_groups": [["-0.479", "−0.479", "-0.48", "−0.48", "-sin(0.5)", "−sin(0.5)", "-sin 0.5", "−sin 0.5"], ["n-m", "n - m", "n−m", "0.5", "offset", "relative", "difference", "β-α", "β − α"]],
                "verify_code": r"""import numpy as np
R = lambda t: np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
q, k, th = np.array([1., 0.]), np.array([0., 1.]), 0.1
logit = (R(3 * th) @ q) @ (R(8 * th) @ k)
assert np.isclose(logit, -np.sin(0.5))
assert np.isclose(logit, (R(13 * th) @ q) @ (R(18 * th) @ k))
print('VERIFIED: logit = -sin(0.5) =', round(logit, 4))
""",
                "hints": _hints(
                    r"Sanity check: the logit of two unit vectors lies in $[-1, 1]$. Which angle between them does the rotation produce?",
                    r"In “{quote}”, did you rotate both vectors by their own angles, or did you combine the two rotations into one first?",
                    r"What is the transpose of a rotation matrix, and how do two planar rotations combine?",
                    r"Start with $m = n$: what is the logit then, for any common angle?",
                    r"Analog: $q = (1,0)$ at angle $0.2$, $k = (1, 0)$ at angle $0.5$: logit $= \cos(0.5 - 0.2) = \cos 0.3$. Here $k = (0,1)$ already starts $90^\circ$ ahead; transfer the move.",
                ),
            },
            2: {
                "prompt": r"A signal-processing colleague stores query and key as phasors, $z_q = 2e^{i\pi/6}$, $z_k = 3e^{i\pi/3}$. At positions $m$ and $n$ they multiply by $e^{im\varphi}$ and $e^{in\varphi}$, and score with $\mathrm{Re}\big(\overline{z_q e^{im\varphi}}\; z_k e^{in\varphi}\big)$. With $\varphi = \pi/12$, $m = 2$, $n = 4$, compute the score.",
                "answer_summary": r"$\overline{z_q e^{im\varphi}}\, z_k e^{in\varphi} = 6\, e^{i(\pi/3 - \pi/6 + (n-m)\varphi)} = 6e^{i\pi/3}$, so the score is $6\cos(\pi/3) = 3$.",
                "concept_groups": [["= 3", "=3", "3.0", "equals 3", "is 3", "score 3", "6cos(π/3)", "6 cos(π/3)", "6cos(pi/3)", "6 cos(pi/3)"], ["n-m", "n - m", "n−m", "relative", "difference", "offset", "2φ", "2\\varphi", "π/6"]],
                "verify_code": r"""import numpy as np
zq, zk, phi, m, n = 2 * np.exp(1j * np.pi / 6), 3 * np.exp(1j * np.pi / 3), np.pi / 12, 2, 4
score = np.real(np.conj(zq * np.exp(1j * m * phi)) * zk * np.exp(1j * n * phi))
assert np.isclose(score, 3.0)
print('VERIFIED: phasor score =', round(score, 6))
""",
                "hints": _hints(
                    r"Magnitude check: $|z_q||z_k| = 6$, so the score is $6\cos(\text{something})$. What angle?",
                    r"In “{quote}”, what does conjugation do to the phase $m\varphi$?",
                    r"Conjugating a unit phasor plays the role of which matrix operation on a rotation?",
                    r"Ignore positions first ($m = n = 0$): compute $\mathrm{Re}(\overline{z_q} z_k)$.",
                    r"Analog: $\mathrm{Re}(\overline{e^{i a}}\,e^{i b}) = \cos(b - a)$. With $a = \pi/6 + 2\varphi$ and $b = \pi/3 + 4\varphi$, subtract the angles and multiply by the magnitudes.",
                ),
            },
            3: {
                "prompt": r"Two position schemes for a 2-D head: (a) add $p_m = (\cos m\theta, \sin m\theta)$ to the query and $p_n$ to the key; (b) rotate the query by $R(m\theta)$ and the key by $R(n\theta)$. You shift the whole sequence by $s$ tokens. Which logits are unchanged, and which terms break the other scheme?",
                "answer_summary": r"(b) is shift-invariant: $q^\top R(m\theta)^\top R(n\theta)k = q^\top R((n-m)\theta)k$. In (a), $(q + p_m)^\top(k + p_n)$ contains $q^\top p_n$ and $p_m^\top k$, which depend on the absolute positions (only $q^\top k$ and $p_m^\top p_n = \cos((n-m)\theta)$ are relative).",
                "concept_groups": [["rotat", "(b)", "multiplicative"], ["cross term", "q^tp", "q^\\top p", "p_m^t k", "p_m^\\top k", "absolute"]],
                "verify_code": r"""import numpy as np
R = lambda t: np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
p = lambda m, th: np.array([np.cos(m * th), np.sin(m * th)])
rng = np.random.default_rng(3); q, k = rng.normal(size=2), rng.normal(size=2); th = 0.3
add = lambda m, n: (q + p(m, th)) @ (k + p(n, th))
rot = lambda m, n: (R(m * th) @ q) @ (R(n * th) @ k)
assert np.isclose(rot(2, 7), rot(12, 17))
assert not np.isclose(add(2, 7), add(12, 17))
assert np.isclose(p(2, th) @ p(7, th), p(12, th) @ p(17, th))
print('VERIFIED: rotation scores shift-invariant; additive cross terms are not')
""",
                "hints": _hints(
                    r"Write out each logit as a sum of terms. For each term, ask: does it depend on $m$ and $n$ separately, or only on $n-m$?",
                    r"In “{quote}”, which of the four expanded terms did you check for shift invariance?",
                    r"For two rotations, what is $R(m\theta)^\top R(n\theta)$?",
                    r"Set $q = k = 0$ in (a): which term survives, and is it relative? Now set $p$'s to zero except one.",
                    r"Analog: in (a) the term $q^\top p_n = q_1\cos n\theta + q_2 \sin n\theta$ changes when $n \mapsto n + s$ while $q$ is fixed. In (b) the shift contributes $R(s\theta)^\top R(s\theta) = I$. Classify every term this way.",
                ),
            },
            4: {
                "prompt": r"A teammate's 'rotation' kernel has a sign typo: $M(\theta) = \begin{pmatrix}\cos\theta & \sin\theta\\ \sin\theta & \cos\theta\end{pmatrix}$. They still expect $M(\alpha)^\top M(\beta) = M(\beta - \alpha)$ and relative-position logits. Test it.",
                "answer_summary": r"$M$ is not orthogonal: $M^\top M = \begin{pmatrix}1 & \sin 2\theta\\ \sin2\theta & 1\end{pmatrix} \ne I$ and $\det M = \cos 2\theta$. Also $M(\alpha)^\top M(\beta) = \begin{pmatrix}\cos(\beta-\alpha) & \sin(\alpha+\beta)\\ \sin(\alpha+\beta) & \cos(\beta-\alpha)\end{pmatrix}$, whose off-diagonal depends on the absolute sum $\alpha + \beta$.",
                "concept_groups": [["not orthogonal", "m^tm", "m^\\top m", "not a rotation", "det", "cos 2θ", "cos(2θ)"], ["α+β", "α + β", "alpha+beta", "alpha + beta", "absolute", "sum"]],
                "verify_code": r"""import sympy as sp
a, b = sp.symbols('alpha beta', real=True)
M = lambda t: sp.Matrix([[sp.cos(t), sp.sin(t)], [sp.sin(t), sp.cos(t)]])
P = sp.simplify(M(a).T * M(b))
assert sp.simplify(P[0, 1] - sp.sin(a + b)) == 0
assert sp.simplify(P[0, 0] - sp.cos(b - a)) == 0
assert sp.simplify((M(a).T * M(a))[0, 1] - sp.sin(2 * a)) == 0
print('VERIFIED: off-diagonal is sin(alpha+beta); M not orthogonal')
""",
                "hints": _hints(
                    r"Before anything else: compute $M(\theta)^\top M(\theta)$. Is it the identity?",
                    r"Look at “{quote}”. Which property of a genuine rotation were you relying on there?",
                    r"Where in the derivation $R(\alpha)^\top R(\beta) = R(\beta-\alpha)$ did you use $R^\top = R^{-1}$?",
                    r"Take $\alpha = \beta = \pi/4$: compute $M(\pi/4)$ and $M(\pi/4)^\top M(\pi/4)$ numerically.",
                    r"Analog: the reflection-like $F(\theta) = \begin{pmatrix}\cos\theta & \sin\theta\\ \sin\theta & -\cos\theta\end{pmatrix}$ gives $F(\alpha)^\top F(\beta) = R(\beta - \alpha)$ only because $F^\top F = I$. Check which ingredient $M$ lacks.",
                ),
            },
        },
        "referee": {
            "claim": r"Any two real $2\times 2$ orthogonal matrices commute, so $Q_1^\top Q_2 = Q_2 Q_1^\top$.",
            "steps": [
                r"Every $2\times2$ orthogonal $Q$ has orthonormal columns, so its first column is $(\cos\theta, \sin\theta)^\top$ for some $\theta$.",
                r"The second column is a unit vector orthogonal to the first, so it equals $(-\sin\theta, \cos\theta)^\top$.",
                r"Hence every $2\times2$ orthogonal matrix is a rotation $R(\theta)$.",
                r"Rotations compose by adding angles: $R(\alpha)R(\beta) = R(\alpha + \beta) = R(\beta)R(\alpha)$.",
                r"Therefore any two $2\times 2$ orthogonal matrices commute, and in particular $Q_1^\top Q_2 = Q_2 Q_1^\top$.",
            ],
            "flawed_index": 2,
            "violated_keywords": ["reflection", "two choices", "sign", "det = -1", "det -1", "(sin", "orientation", "-cos"],
            "explanation": r"A unit vector orthogonal to $(\cos\theta, \sin\theta)$ can also be $(\sin\theta, -\cos\theta)$. That choice gives a reflection ($\det = -1$), and reflections do not commute with rotations.",
            "counterexample": r"$Q_1 = \mathrm{diag}(1, -1)$, $Q_2 = R(90^\circ)$: $Q_1^\top Q_2 = \begin{pmatrix}0&-1\\-1&0\end{pmatrix}$ but $Q_2 Q_1^\top = \begin{pmatrix}0&1\\1&0\end{pmatrix}$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": r"Leo, who thinks transposing a rotation matrix 'just flips it' and that angles always add, so $R(\alpha)^\top R(\beta) = R(\alpha+\beta)$.",
            "opening": r"Transpose just mirrors the entries, and rotations add angles, so $R(\alpha)^\top R(\beta) = R(\alpha+\beta)$. Why does everyone say RoPE only sees $\beta - \alpha$?",
            "boundary_conditions": [
                _bc("transpose_inverse", r"$R(\alpha)^\top = R(-\alpha) = R(\alpha)^{-1}$ because $\cos$ is even and $\sin$ is odd",
                    ["inverse", "r(-α)", "r(-alpha)", "-α", "−α", "minus alpha", "negative angle", "undo"],
                    r"Transposing just flips the matrix across the diagonal — why would that undo the rotation?"),
                _bc("relative_only", r"Only the relative angle $\beta - \alpha$ appears; a common shift cancels",
                    ["relative", "β-α", "β − α", "beta - alpha", "difference", "common shift", "cancel"],
                    r"If I add $10^\circ$ to both angles, surely the result changes a bit?"),
                _bc("commutation_scope", r"Commutation $R(\alpha)R(\beta) = R(\beta)R(\alpha)$ is special to planar rotations; reflections and 3-D rotations generally do not commute",
                    ["commut", "3d", "3-d", "reflection", "abelian", "planar", "2d only"],
                    r"So all rotation matrices commute — in 3-D as well?"),
            ],
        },
        "misconceptions": [
            _mis(["r(α+β)", "r(alpha+beta)", "alpha + beta", "angles add up", "α+β"], "ALGEBRAIC_SLIP",
                 "Transpose ignored in composition", r"R(\alpha)^\top R(\beta) = R(\alpha + \beta)"),
            _mis(["all rotations commute", "3d rotations commute", "rotations always commute"], "FALSE_ANALOGY",
                 "Rotations commute in every dimension", r"R_1 R_2 = R_2 R_1\ \ \forall R_1, R_2 \in SO(3)"),
            _mis(["transpose is just flipping", "transpose is the same rotation", "transpose doesn't change the angle"], "MISSING_PREREQUISITE",
                 "Transpose unrelated to inverse", r"R(\alpha)^\top = R(\alpha)"),
        ],
    },
    "prop_banach_contraction": {
        "probe": {
            "prompt": r"Let $T(x) = x/2 + 1$ on $\mathbb{R}$. Starting from $x_0 = 10$ and iterating $x_{k+1} = T(x_k)$, what happens?",
            "options": _opts(
                r"The iterates diverge",
                r"They converge to $2$, and the distance to $2$ halves every step",
                r"They converge to $1$",
                r"They oscillate forever around $2$",
            ),
            "correct": "B",
            "explanation": r"The fixed point solves $x = x/2 + 1$, so $x^* = 2$. Since $T(x) - 2 = (x - 2)/2$, the error goes $8, 4, 2, 1, \dots$: geometric convergence with ratio $\gamma = 1/2$.",
        },
        "predict": {
            "prompt": r"Predict: if a map brings any two distinct points strictly closer, $d(Tx, Ty) < d(x, y)$, must repeated application converge to a fixed point? What could go wrong if the space has a 'hole' exactly where the iterates are heading?",
        },
        "reading": r"""**Base case.** $T(x) = x/2 + 1$ on $\mathbb{R}$. Its fixed point is $x^* = 2$, and $T(x) - 2 = \tfrac12(x - 2)$, so $|x_k - 2| = 2^{-k}|x_0 - 2|$.

**Generalize the inequality.** Suppose $d(Tx, Ty) \le \gamma\, d(x, y)$ with a *single* $\gamma < 1$. Then consecutive steps shrink: $d(x_{k+1}, x_k) \le \gamma^k d(x_1, x_0)$.

**Sum the tail.** For $m > k$, the triangle inequality and a geometric series give
$$d(x_m, x_k) \le \frac{\gamma^k}{1-\gamma}\, d(x_1, x_0) \to 0,$$
so $(x_k)$ is Cauchy.

**Completeness converts Cauchy into a limit** $x^* \in X$; continuity of $T$ gives $Tx^* = \lim x_{k+1} = x^*$.

**Uniqueness.** If $Tx = x$ and $Ty = y$, then $d(x,y) \le \gamma d(x,y)$, forcing $d(x, y) = 0$. Rate: $d(x_k, x^*) \le \gamma^k d(x_0, x^*)$.

**Self-explanation:** Which step used completeness, and what breaks for $T(x) = x/2$ on $X = (0, 1]$?""",
        "check": {
            "prompt": r"An operator $\Phi$ on $C([0,1])$ with the sup norm satisfies $\|\Phi f - \Phi g\|_\infty \le 0.9\,\|f - g\|_\infty$. Starting from $f_0$ with $\|f_0 - f^\star\|_\infty = 1$, how many iterations guarantee $\|f_k - f^\star\|_\infty \le 10^{-3}$?",
            "options": _opts(r"$10$", r"$66$", r"$1000$", r"No guarantee: function spaces are infinite-dimensional"),
            "correct": "B",
            "explanation": r"Need $0.9^k \le 10^{-3}$, i.e. $k \ge \ln 1000 / \ln(1/0.9) \approx 65.6$, so $k = 66$. $C([0,1])$ with $\|\cdot\|_\infty$ is complete, so the contraction principle applies regardless of dimension.",
        },
        "productive_failure": {
            "prompt": r"The map $T(x) = x + 1/x$ on $X = [1, \infty)$ satisfies $|T(x) - T(y)| < |x - y|$ for all $x \ne y$, and $[1,\infty)$ is complete. Does $T$ have a fixed point? Pin down exactly which hypothesis of a guaranteed-convergence result is missing.",
            "canonical_insight": r"$T(x) - T(y) = (x - y)\big(1 - \tfrac{1}{xy}\big)$ with factor in $[0, 1)$, so distances strictly shrink, yet $x = x + 1/x$ has no solution and $x_k \to \infty$. The ratio $1 - 1/(xy)$ approaches $1$; there is no **uniform** $\gamma < 1$. Strict shrinking is not enough; a uniform contraction constant is.",
        },
        "practice": {
            1: {
                "prompt": r"Your iterative solver runs $x_{k+1} = 0.5\cos(x_k)$ on the whole real line. Will it converge from every initialization? To how many different limits? How fast does the error shrink?",
                "answer_summary": r"$|T'(x)| = 0.5|\sin x| \le 0.5$, so by the mean value theorem $T$ is a $0.5$-contraction on the complete space $\mathbb{R}$: from any start the iterates converge to the unique fixed point $x^* \approx 0.4502$, with $|x_k - x^*| \le 0.5^k|x_0 - x^*|$.",
                "concept_groups": [["0.5", "1/2", "half"], ["unique", "one fixed", "single", "same limit", "one limit"], ["complete", "real line", "all of r", "ℝ is"], ["0.45"]],
                "verify_code": r"""import numpy as np
from scipy.optimize import brentq
T = lambda x: 0.5 * np.cos(x)
xs = brentq(lambda x: T(x) - x, -2, 2)
assert abs(xs - 0.4502) < 1e-3
for x0 in [-100.0, -3.0, 0.0, 7.0, 1e6]:
    x = x0
    e0 = abs(T(x) - xs)
    for k in range(60):
        x = T(x)
    assert abs(x - xs) < 1e-12
grid = np.linspace(-50, 50, 200001)
assert np.max(np.abs(0.5 * np.sin(grid))) <= 0.5
print('VERIFIED: unique fixed point', round(xs, 6), 'contraction factor 0.5')
""",
                "hints": _hints(
                    r"Bound the slope: what is the largest possible $|T'(x)|$ over all real $x$?",
                    r"You wrote “{quote}”. Does that inequality hold with one constant for every pair of points, or only near the solution?",
                    r"A map that shrinks all distances by a fixed factor on a complete space — what does that guarantee about fixed points?",
                    r"Run two iterations by hand from $x_0 = 0$ and $x_0 = 3$. How fast does the gap between the two sequences shrink?",
                    r"Analog: $x_{k+1} = 0.3\sin(x_k) + 1$ has $|T'| \le 0.3$, so it converges from anywhere to the unique solution of $x = 0.3\sin x + 1$ with error $\le 0.3^k|x_0 - x^*|$. Transfer.",
                ),
            },
            2: {
                "prompt": r"A planning routine updates a vector $v \in \mathbb{R}^3$ by $F(v) = r + 0.8\,P v$ where every row of $P$ is nonnegative and sums to $1$. Measuring error with $\|\cdot\|_\infty$, show the iteration converges from any start and give a closed form for the limit.",
                "answer_summary": r"Each $(Pv - Pw)_i$ is a convex combination of entries of $v - w$, so $\|Pv - Pw\|_\infty \le \|v - w\|_\infty$ and $F$ is a $0.8$-contraction on the complete space $(\mathbb{R}^3, \|\cdot\|_\infty)$. The unique limit solves $v = r + 0.8Pv$: $v^* = (I - 0.8P)^{-1} r$.",
                "concept_groups": [["0.8"], ["row", "stochastic", "convex combination", "average", "sum to 1", "sums to 1"], ["(i - 0.8p)^{-1}", "(i-0.8p)^{-1}", "(i − 0.8p)", "inverse", "solve", "linear system"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(4)
P = rng.random((3, 3)); P /= P.sum(1, keepdims=True)
r = rng.normal(size=3)
F = lambda v: r + 0.8 * P @ v
for _ in range(200):
    a, b = rng.normal(size=3) * 10, rng.normal(size=3) * 10
    assert np.abs(F(a) - F(b)).max() <= 0.8 * np.abs(a - b).max() + 1e-12
v = rng.normal(size=3) * 100
for _ in range(300):
    v = F(v)
assert np.allclose(v, np.linalg.solve(np.eye(3) - 0.8 * P, r))
print('VERIFIED: 0.8-contraction in sup norm, limit (I-0.8P)^{-1} r')
""",
                "hints": _hints(
                    r"Which norm makes 'a row of $P$ averages entries' easy to bound? Check: can an average exceed the largest absolute entry?",
                    r"In “{quote}”, where did you use that the rows of P sum to 1 and are nonnegative?",
                    r"What do you know about iterating a map that shrinks every distance by the same factor below 1 on a complete space?",
                    r"Do the 1-state version: $F(v) = r + 0.8v$. What is the fixed point and the error ratio?",
                    r"Analog: $G(v) = c + 0.5Av$ with $\|A\|_\infty \le 1$ gives $\|G(a) - G(b)\| \le 0.5\|a - b\|$ and limit $(I - 0.5A)^{-1}c$. Transfer with $0.8$ and the averaging matrix $P$.",
                ),
            },
            3: {
                "prompt": r"Two implementations of the same update, $x \mapsto x/2$, both started at $x_0 = 1$: one lives on the interval $(0, 1]$, the other on $[0, 1]$. Both shrink distances by exactly one half. Compare the outcomes and name the hypothesis that decides the difference.",
                "answer_summary": r"In both, $x_k = 2^{-k} \to 0$. On $[0,1]$ (complete) the limit $0$ is in the space and is the unique fixed point. On $(0,1]$ the sequence is Cauchy but its limit $0 \notin X$: there is no fixed point. Completeness decides.",
                "concept_groups": [["complete", "closed", "hole", "missing 0", "0 is not in", "0 ∉", "limit outside", "not in the space"], ["no fixed point", "no fixed", "doesn't have a fixed", "does not have a fixed"], ["cauchy", "2^{-k}", "2^-k", "→ 0", "-> 0", "converge"]],
                "verify_code": r"""import sympy as sp
x, k = sp.symbols('x k', real=True)
T = lambda y: y / 2
fixed = sp.solve(sp.Eq(T(x), x), x)
assert fixed == [0]
assert sp.limit(sp.Rational(1, 2) ** k, k, sp.oo) == 0
in_half_open = lambda y: (y > 0) and (y <= 1)
assert not in_half_open(fixed[0]) and (0 <= fixed[0] <= 1)
print('VERIFIED: only fixed point is 0, absent from (0,1], present in [0,1]')
""",
                "hints": _hints(
                    r"Write $x_k$ explicitly. Where is the sequence heading, and is that point inside each space?",
                    r"In “{quote}”, did you check whether the limit you found actually belongs to the space?",
                    r"Which property of a space guarantees that sequences whose terms get arbitrarily close actually have a limit inside the space?",
                    r"Solve $T(x) = x$ by hand. Is the solution in $(0, 1]$?",
                    r"Analog: Newton's method for $x^2 = 2$ on $\mathbb{Q}$ produces a Cauchy sequence of rationals whose limit $\sqrt2$ is not rational: no fixed point in $\mathbb{Q}$, one in $\mathbb{R}$. Transfer to $(0,1]$ vs $[0,1]$.",
                ),
            },
            4: {
                "prompt": r"A colleague iterates the softplus map $T(x) = \ln(1 + e^x)$ and argues: '$T'(x)$ is the sigmoid, which is always strictly less than $1$, so $T$ shrinks every distance and iteration must converge to a unique fixed point.' Check the claim.",
                "answer_summary": r"$\sup_x T'(x) = \sup_x \sigma(x) = 1$: there is no uniform $\gamma < 1$, so $T$ is not a contraction. In fact $T(x) - x = \ln(1 + e^{-x}) > 0$ for all $x$, so there is no fixed point and the iterates increase to $+\infty$.",
                "concept_groups": [["sup", "uniform", "approaches 1", "→ 1", "-> 1", "tends to 1", "not bounded away", "no single", "no uniform"], ["no fixed point", "diverge", "> x", "greater than x", "grows", "increase", "∞", "infinity"]],
                "verify_code": r"""import numpy as np
import sympy as sp
x = sp.symbols('x', real=True)
T = sp.log(1 + sp.exp(x))
assert sp.simplify(sp.diff(T, x) - 1 / (1 + sp.exp(-x))) == 0
assert sp.limit(sp.diff(T, x), x, sp.oo) == 1
gap = sp.log(1 + sp.exp(-x))
assert sp.simplify(sp.expand_log(T - x - gap, force=True)) == 0 or abs(float((T - x - gap).subs(x, 3))) < 1e-12
v = 0.0
for _ in range(2000):
    v = np.logaddexp(0.0, v)
assert v > 5
print('VERIFIED: sup T\' = 1, T(x) - x = log(1+e^-x) > 0, iterates grow to', round(v, 2))
""",
                "hints": _hints(
                    r"Limit check: what does $T'(x)$ approach as $x \to +\infty$?",
                    r"You wrote “{quote}”. Is the bound strictly below one by a fixed margin, or does it creep up to one?",
                    r"For the convergence guarantee you want, is $|T'(x)| < 1$ at every point the same as $\sup_x |T'(x)| < 1$?",
                    r"Compute $T(x) - x$ at $x = 0, 5, 20$. Is it ever zero?",
                    r"Analog: $T(x) = x + 1/x$ on $[1,\infty)$ shrinks every distance but $T(x) > x$ always, so the iterates run off to infinity. Show softplus behaves the same way.",
                ),
            },
        },
        "referee": {
            "claim": r"The map $T(x) = x/2$ on $X = (0, 1]$ with $d(x,y) = |x - y|$ has a unique fixed point.",
            "steps": [
                r"$|T(x) - T(y)| = \tfrac12|x - y|$, so $T$ is a $\tfrac12$-contraction, and $T$ maps $X$ into $X$.",
                r"From $x_0 = 1$, the iterates are $x_k = 2^{-k}$ and $|x_{k+1} - x_k| = 2^{-(k+1)}$.",
                r"Summing the geometric tail, $|x_m - x_k| \le 2^{-k}$ for $m > k$, so $(x_k)$ is Cauchy.",
                r"Every Cauchy sequence converges in $X$, so $x_k \to x^* \in X$.",
                r"By continuity $T(x^*) = \lim T(x_k) = \lim x_{k+1} = x^*$, and the contraction inequality gives uniqueness.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["complete", "cauchy", "0 is not", "0 ∉", "not in x", "(0,1]", "closed", "limit outside"],
            "explanation": r"$(0, 1]$ is not complete: the Cauchy sequence $2^{-k}$ converges in $\mathbb{R}$ to $0 \notin X$. Without completeness the contraction principle gives no fixed point.",
            "counterexample": r"$T(x) = x/2$ on $(0,1]$ has no fixed point at all: $x/2 = x$ forces $x = 0 \notin (0, 1]$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Ava, an optimization enthusiast convinced that any map that brings points closer must have a fixed point that iteration finds.",
            "opening": r"If $d(Tx, Ty) < d(x, y)$ for all $x \ne y$, the iterates obviously settle down to a fixed point. Why do textbooks fuss about extra conditions?",
            "boundary_conditions": [
                _bc("uniform_gamma", r"Need a single uniform constant $\gamma < 1$ with $d(Tx,Ty) \le \gamma\, d(x,y)$, not just strict shrinking",
                    ["uniform", "γ < 1", "gamma < 1", "γ<1", "fixed constant", "same constant", "single constant", "lipschitz constant"],
                    r"$x + 1/x$ on $[1, \infty)$ shrinks every distance. Where's its fixed point?"),
                _bc("complete_space", r"The metric space must be complete (Cauchy sequences converge inside it)",
                    ["complete", "cauchy", "closed"],
                    r"$x/2$ on $(0, 1]$ is a $\tfrac12$-contraction. Where's its fixed point?"),
                _bc("self_map", r"$T$ must map $X$ into itself",
                    ["into x", "maps x to x", "self-map", "self map", "stays in", "x → x", "x to itself", "into itself"],
                    r"$T(x) = x/2 + 3$ on $[0, 1]$ is a contraction — so is its fixed point $6$ in $[0,1]$?"),
            ],
        },
        "misconceptions": [
            _mis(["shrinks distances so it converges", "strictly smaller distance", "d(tx,ty) < d(x,y) so", "strictly closer so"], "BOUNDARY_OMISSION",
                 "Weak contraction suffices", r"d(Tx,Ty) < d(x,y)\ \forall x\ne y \implies \exists!\, x^* = Tx^*"),
            _mis(["any metric space", "don't need complete", "cauchy so it converges in x", "completeness doesn't matter"], "BOUNDARY_OMISSION",
                 "Completeness is optional", r"(X,d) \text{ arbitrary},\ T \text{ contraction} \implies \exists\, x^* \in X"),
            _mis(["derivative less than 1 so contraction", "|t'(x)| < 1 so", "slope below one everywhere"], "FALSE_ANALOGY",
                 "Pointwise slope bound as contraction", r"|T'(x)| < 1\ \forall x \implies T \text{ is a contraction}"),
        ],
    },
    "int_covector_hyperplanes": {
        "probe": {
            "prompt": r"For the linear functional $\omega(v) = 3v_1 + 4v_2$ on $\mathbb{R}^2$, draw the level lines $\{v : \omega(v) = c\}$ for integer $c$. What is the Euclidean spacing between adjacent lines?",
            "options": _opts(r"$5$", r"$1/5$", r"$1/7$", r"$7$"),
            "correct": "B",
            "explanation": r"Adjacent lines differ by $\Delta\omega = 1$. Moving along the unit normal $(3,4)/5$ changes $\omega$ at rate $\|(3,4)\| = 5$, so the spacing is $1/5$. A bigger covector means a denser stack.",
        },
        "predict": {
            "prompt": r"Predict: if you double a linear functional $\omega$, do its integer level lines spread apart or crowd together? And which direction of a unit step makes $\omega$ grow fastest?",
        },
        "reading": r"""**Base case $d = 1$.** $\omega(v) = a v$. Its level sets $\{av = c\}$, $c \in \mathbb{Z}$, are points spaced $1/|a|$ apart; $\omega(v)$ *counts how many you cross* moving from $0$ to $v$.

**Step to $d = 2$.** $\omega(v) = a_1 v_1 + a_2 v_2$. Level sets are parallel lines, Euclidean-perpendicular to $(a_1, a_2)$, spaced $1/\|a\|$. Doubling $\omega$ halves the spacing: a *bigger covector is a denser stack*.

**Derivatives are covectors.** For smooth $f$, $df_x$ is the functional with $df_x(v) = $ directional derivative of $f$ along $v$. Its stack is the linearized contour lines of $f$; a small step $v$ changes $f$ by about the number of lines crossed. No inner product needed.

**Arrows need a metric.** To turn the stack into a descent *direction*, choose an inner product $G$: $\nabla f = G^{-1} df^\top$. With $G = I$ the arrow is perpendicular to the lines; another $G$ (a preconditioner) tilts it.

**Self-explanation:** Rescaling coordinates $x_1 \mapsto 10x_1$ changes the gradient-descent direction. Why does it not change $df(v)$ for a fixed physical step $v$?""",
        "check": {
            "prompt": r"In index notation a 1-form is $\alpha = \alpha_i\,dx^i$ with $\alpha = 2\,dx^1 - dx^2$. A displacement has components $v = (3, 1)$. How many unit-spaced level surfaces of $\alpha$ does $v$ cross (net)?",
            "options": _opts(r"$5$", r"$\sqrt5\cdot\sqrt{10}$", r"$7$", r"$1/5$"),
            "correct": "A",
            "explanation": r"Contraction of a covector with a vector: $\alpha(v) = \alpha_i v^i = 2\cdot3 - 1\cdot 1 = 5$. No metric enters; B multiplies lengths, which would need one.",
        },
        "productive_failure": {
            "prompt": r"Loss $f(x, y) = 50x^2 + \tfrac12 y^2$. At $(1, 1)$, which direction should you step to decrease $f$ fastest? Now rename $u = 10x$, recompute the 'fastest descent' direction in $(u, y)$ coordinates, and map it back to $(x, y)$. Same physical direction? Explain the discrepancy.",
            "canonical_insight": r"In $(x,y)$: $\nabla f = (100, 1)$. In $(u, y)$: $f = \tfrac12u^2 + \tfrac12y^2$, $\nabla = (10, 1)$; mapped back via $dx = du/10$ the step is $\propto(1, 1)$, which points straight at the minimum. The covector $df$ (the stack) is the same object in both; 'steepest' depends on the inner product used to turn it into an arrow. Choosing the metric is preconditioning.",
        },
        "practice": {
            1: {
                "prompt": r"Near the current weights, your loss is effectively linear: $L(w + v) \approx L(w) + 2v_1 - v_2 + 2v_3$. You take the step $v = (0.1, 0.3, -0.05)$. Predict the change in loss. Then: what is the length of the shortest step that lowers the loss by exactly $0.3$?",
                "answer_summary": r"$\Delta L = \omega(v) = 0.2 - 0.3 - 0.1 = -0.2$. The level sets of $\omega = (2, -1, 2)$ are spaced $1/\|\omega\| = 1/3$ per unit of loss, so the shortest step for $\Delta L = -0.3$ has length $0.3/3 = 0.1$ (along $-\omega/\|\omega\|$).",
                "concept_groups": [["-0.2", "−0.2"], ["0.1"], ["norm", "‖ω‖", "= 3", "perpendicular", "spacing", "along -ω", "along −ω", "normal"]],
                "verify_code": r"""import numpy as np
w = np.array([2., -1., 2.]); v = np.array([0.1, 0.3, -0.05])
assert np.isclose(w @ v, -0.2)
vstar = -0.3 * w / (w @ w)
assert np.isclose(w @ vstar, -0.3) and np.isclose(np.linalg.norm(vstar), 0.1)
rng = np.random.default_rng(5)
for _ in range(1000):
    z = rng.normal(size=3); z -= (w @ z) / (w @ w) * w
    cand = vstar + z
    assert np.linalg.norm(cand) >= 0.1 - 1e-12
print('VERIFIED: delta L = -0.2, shortest step length 0.1')
""",
                "hints": _hints(
                    r"Units check: $\omega(v)$ is a loss change (a number). The step length is a distance. Which quantity converts 'loss per unit distance'?",
                    r"In “{quote}”, did you treat the coefficient vector as something to dot with $v$, or as a step direction?",
                    r"Picture the level sets of $\omega$: how far apart are two that differ by one unit of loss?",
                    r"In 1-D, $\omega(v) = 3v$: how long a step lowers $\omega$ by $0.3$?",
                    r"Analog: $\omega = (3, 4)$ has spacing $1/5$; to change it by $-1$ the shortest step is $-(3,4)/25$, length $1/5$. Repeat with $\omega = (2,-1,2)$ and $-0.3$.",
                ),
            },
            2: {
                "prompt": r"Index notation: a covector $\theta = \theta_i\,dx^i$ with components $\theta_i = (1, 2)$, in coordinates where the metric is $g_{ij} = \mathrm{diag}(4, 1)$. Compute the vector $\theta^\sharp$ with components $\theta^i = g^{ij}\theta_j$, and check that $\theta(\theta^\sharp) = g(\theta^\sharp, \theta^\sharp)$.",
                "answer_summary": r"$g^{ij} = \mathrm{diag}(1/4, 1)$, so $\theta^\sharp = (1/4, 2)$. Then $\theta(\theta^\sharp) = 1\cdot\tfrac14 + 2\cdot 2 = 4.25$ and $g(\theta^\sharp,\theta^\sharp) = 4\cdot\tfrac1{16} + 1\cdot 4 = 4.25$.",
                "concept_groups": [["1/4", "0.25"], ["g^{-1}", "inverse metric", "g^{ij}", "g^ij", "raise", "divide by 4"], ["4.25", "17/4"]],
                "verify_code": r"""import sympy as sp
g = sp.diag(4, 1); th = sp.Matrix([1, 2])
sharp = g.inv() * th
assert list(sharp) == [sp.Rational(1, 4), 2]
assert (th.T * sharp)[0] == (sharp.T * g * sharp)[0] == sp.Rational(17, 4)
print('VERIFIED: theta_sharp = (1/4, 2), both pairings = 17/4')
""",
                "hints": _hints(
                    r"Index check: lowering uses $g_{ij}$, raising uses $g^{ij}$. Which one turns a covector into a vector?",
                    r"In “{quote}”, did you multiply by the metric or by its inverse?",
                    r"If the metric stretches the $x^1$ direction by 4, how should a vector's first component compensate?",
                    r"Do the 1-D case: metric $g = 4$, covector $\theta = 1$. What vector $v$ satisfies $g\,v = \theta$?",
                    r"Analog: with $g = \mathrm{diag}(9, 1)$ and $\theta = (3, 1)$, $\theta^\sharp = (1/3, 1)$, and $\theta(\theta^\sharp) = 1 + 1 = 2 = 9\cdot\tfrac19 + 1$. Transfer to $\mathrm{diag}(4,1)$.",
                ),
            },
            3: {
                "prompt": r"On $L(x, y) = 50x^2 + \tfrac12y^2$ at $(1, 1)$, plain gradient descent steps along $-(100, 1)$ while a curvature-preconditioned step uses $-H^{-1}\nabla L$. Explain, in terms of level-set stacks, why the plain method zig-zags and which object the preconditioner converts into which.",
                "answer_summary": r"$dL = (100\,dx + dy)$ is a covector whose stack is very dense in $x$. Plain GD turns it into an arrow with the Euclidean metric, which points across the narrow valley and overshoots, so it zig-zags. The preconditioner uses the metric $H = \mathrm{diag}(100, 1)$: $H^{-1}\nabla L = (1, 1)$, pointing straight at the minimum $(0,0)$. It converts the covector $dL$ into a vector with a better inner product.",
                "concept_groups": [["covector", "1-form", "dual", "level set", "stack", "contour"], ["metric", "inner product", "precondition", "h^{-1}", "inverse hessian"], ["zig", "oscillat", "overshoot", "perpendicular"], ["(1, 1)", "(1,1)", "origin", "minimum", "(0,0)", "(0, 0)"]],
                "verify_code": r"""import numpy as np
H = np.diag([100., 1.]); p = np.array([1., 1.])
g = H @ p
step = np.linalg.solve(H, g)
assert np.allclose(step, [1., 1.]) and np.allclose(p - step, [0., 0.])
eta = 0.019; x = p.copy(); signs = []
for _ in range(6):
    x = x - eta * (H @ x); signs.append(np.sign(x[0]))
assert any(signs[i] != signs[i + 1] for i in range(5))
print('VERIFIED: preconditioned step hits the minimum; plain GD flips sign in x (zig-zag)')
""",
                "hints": _hints(
                    r"Compare the two components of $\nabla L$ with the distances to the minimum along each axis. Do the ratios match?",
                    r"In “{quote}”, which object did you treat as an arrow, and which inner product did that silently use?",
                    r"How does the spacing of the contour stack in $x$ compare with that in $y$? Which metric would make the stack look equally spaced?",
                    r"In 1-D, $L = 50x^2$ at $x = 1$: what step size does plain GD need to land exactly at $0$, and what does dividing by the curvature give?",
                    r"Analog: on $L = 8x^2 + \tfrac12y^2$, $\nabla L = (16x, y)$ while $H^{-1}\nabla L = (x, y)$ points at the origin; with $\eta = 0.12$, plain GD gives $x \mapsto (1 - 1.92)x = -0.92x$ (sign flip). Transfer to the $50$ case.",
                ),
            },
            4: {
                "prompt": r"A teammate insists: 'The gradient is the arrow perpendicular to the contours, so it's coordinate-free. Reparametrizing $x_1 = 10u_1$ can't change the gradient-descent update.' Test this on $f(x) = x_1 + x_2$: take one GD step in $u$-coordinates and map it back to $x$.",
                "answer_summary": r"In $u$-coordinates $f = 10u_1 + x_2$, so $\nabla_u f = (10, 1)$ and the step is $\Delta u = -\eta(10, 1)$, i.e. $\Delta x = (10\Delta u_1, \Delta x_2) = -\eta(100, 1)$, versus $-\eta(1,1)$ in $x$-coordinates. The covector $df$ is the same object; 'perpendicular' depends on the metric, which the reparametrization changed.",
                "concept_groups": [["100"], ["metric", "inner product", "perpendicular depends", "coordinate"], ["covector", "df", "1-form", "level", "stack"]],
                "verify_code": r"""import sympy as sp
u1, x2, eta = sp.symbols('u1 x2 eta', positive=True)
f_u = 10 * u1 + x2
grad_u = sp.Matrix([sp.diff(f_u, u1), sp.diff(f_u, x2)])
du = -eta * grad_u
dx = sp.Matrix([10 * du[0], du[1]])
assert sp.simplify(dx - sp.Matrix([-100 * eta, -eta])) == sp.zeros(2, 1)
assert dx != sp.Matrix([-eta, -eta])
print('VERIFIED: step in x via u-coords is -eta*(100, 1), not -eta*(1, 1)')
""",
                "hints": _hints(
                    r"Track units: if $x_1$ is measured in tens of $u_1$, how do the components of $df$ and of a step $v$ transform?",
                    r"Look at “{quote}”. 'Perpendicular' with respect to which inner product?",
                    r"What extra structure must you choose to turn the covector $df$ into an arrow?",
                    r"Do the 1-D case $f(x) = x$, $x = 10u$: compute $df/du$, the GD step in $u$, and the resulting change in $x$.",
                    r"Analog: $f(x) = x$, $x = 10u$: $\Delta u = -\eta\cdot10$, so $\Delta x = -100\eta$, not $-\eta$. Same function, same stack, different arrow. Now add the $x_2$ coordinate.",
                ),
            },
        },
        "referee": {
            "claim": r"Gradient descent is invariant under any invertible linear reparametrization $x = Au$: the induced step in $x$ equals $-\eta\nabla_x f$.",
            "steps": [
                r"Let $g(u) = f(Au)$. By the chain rule $dg_u = df_{Au}\circ A$, i.e. $\nabla_u g^\top = \nabla_x f^\top A$.",
                r"Transposing, $\nabla_u g = A^\top\nabla_x f$.",
                r"A GD step in $u$ is $\Delta u = -\eta A^\top\nabla_x f$, which maps to $\Delta x = A\Delta u = -\eta AA^\top\nabla_x f$.",
                r"Since $A$ is invertible, $AA^\top = I$, so $\Delta x = -\eta\nabla_x f$.",
                r"Hence the GD step is the same in both parametrizations: steepest descent is coordinate-free.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["orthogonal", "aa^t", "aa^\\top", "a a^t", "a a^\\top", "invertible is not", "only if a is orthogonal", "metric"],
            "explanation": r"$AA^\top = I$ holds only for orthogonal $A$, not for every invertible $A$. In general the step in $x$ is $-\eta AA^\top\nabla_x f$: reparametrizing changes the metric used to turn $df$ into an arrow.",
            "counterexample": r"$A = \mathrm{diag}(10, 1)$, $f = x_1 + x_2$: $\Delta x = -\eta(100, 1) \ne -\eta(1, 1)$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Noah, an ML engineer who believes 'the derivative is just the uphill arrow' and that it doesn't depend on any choice.",
            "opening": r"The derivative of a loss is the arrow pointing uphill — end of story. Why do people talk about covectors, level-set stacks and metrics?",
            "boundary_conditions": [
                _bc("df_is_covector", r"$df_x$ is a covector: it eats a displacement and returns a number (the count of level sets crossed)",
                    ["covector", "1-form", "linear functional", "eats a vector", "dual", "level set", "stack", "returns a number"],
                    r"Isn't the derivative literally the arrow pointing uphill?"),
                _bc("metric_needed", r"Turning $df$ into an arrow needs an inner product: $\nabla f = G^{-1}df^\top$; changing $G$ (or coordinates) changes the arrow",
                    ["metric", "inner product", "g^{-1}", "riesz", "raise", "precondition"],
                    r"If I stretch the $x$-axis, the contour picture is the same — why would the uphill arrow change?"),
                _bc("spacing_inverse", r"Level-set spacing is $1/\|\omega\|$ in the chosen metric: a larger covector means a denser stack",
                    ["spacing", "1/‖", "1/|", "denser", "closer together", "crowd", "dense"],
                    r"If I double the loss, the contours just get relabelled — the stack looks the same, right?"),
            ],
        },
        "misconceptions": [
            _mis(["gradient is coordinate independent", "gradient is invariant", "same direction in any coordinates", "coordinate-free arrow"], "FALSE_ANALOGY",
                 "Gradient as a coordinate-free arrow", r"\nabla_u (f\circ A) = A^{-1}\nabla_x f"),
            _mis(["bigger covector wider spacing", "larger gradient means spread out", "spacing is the norm"], "NOTATION_OBSTRUCTION",
                 "Inverted level-set spacing", r"\text{spacing} = \|\omega\|"),
            _mis(["df is a vector", "dx is a small displacement vector", "1-form is an arrow"], "NOTATION_OBSTRUCTION",
                 "Covector / vector conflation", r"df = \nabla f \text{ as the same object}"),
        ],
    },
    # ------------------------------------------------------------------ Cluster B
    "ax_linearity_expectation": {
        "probe": {
            "prompt": r"Which of these identities **requires** an independence (or uncorrelatedness) assumption?",
            "options": _opts(
                r"$\mathbb{E}[X + Y] = \mathbb{E}[X] + \mathbb{E}[Y]$",
                r"$\mathbb{E}[3X - 2] = 3\,\mathbb{E}[X] - 2$",
                r"$\mathbb{E}[XY] = \mathbb{E}[X]\,\mathbb{E}[Y]$",
                r"$\mathbb{E}\big[\sum_{i=1}^{100} X_i\big] = \sum_{i=1}^{100}\mathbb{E}[X_i]$ for 100 strongly dependent coin flips",
            ),
            "correct": "C",
            "explanation": r"Expectation is linear with no assumptions on dependence (A, B, D). Products are not linear operations: with $X = Y = \pm1$ fair, $\mathbb{E}[XY] = 1$ but $\mathbb{E}[X]\mathbb{E}[Y] = 0$. The product rule needs $X, Y$ uncorrelated.",
        },
        "predict": {
            "prompt": r"Predict: 100 guests check their hats, and the hats are handed back in a uniformly random order. What is the expected number of guests who get their own hat? Does your answer grow, shrink, or stay put as the number of guests grows?",
        },
        "reading": r"""**Base case.** Two random variables on the same outcomes $\omega$:
$$\mathbb{E}[X+Y] = \sum_\omega \big(X(\omega) + Y(\omega)\big)P(\omega) = \sum_\omega X(\omega)P(\omega) + \sum_\omega Y(\omega)P(\omega).$$
We only split a sum. Nothing about how $X$ and $Y$ depend on each other was used.

**Scaling.** Likewise $\mathbb{E}[aX] = a\,\mathbb{E}[X]$. By induction, $\mathbb{E}\big[\sum_i a_i X_i\big] = \sum_i a_i\,\mathbb{E}[X_i]$, provided each $\mathbb{E}|X_i| < \infty$.

**Indicator trick.** A count is a sum of indicators: $N = \sum_i \mathbf{1}_{A_i}$, so $\mathbb{E}[N] = \sum_i P(A_i)$.

**Hats.** Guest $i$ gets their own hat with probability $1/n$. So $\mathbb{E}[N] = n\cdot\tfrac1n = 1$ for every $n$, even though the events are heavily dependent.

**Limit of the rule.** Products and nonlinear maps are not covered: for $X = Y = \pm1$ fair, $\mathbb{E}[XY] = 1 \ne 0 = \mathbb{E}[X]\mathbb{E}[Y]$.

**Self-explanation:** In the hat problem, which step would break if you computed the *variance* of $N$ the same way?""",
        "check": {
            "prompt": r"A training loop draws a minibatch of $B$ examples **without replacement** from a finite dataset $\mathcal{D}$ (so the draws are dependent) and computes $\hat g = \frac1B\sum_{b=1}^B \ell(x_b)$. Relative to the dataset mean $\mathbb{E}_{x\sim\mathcal{D}}[\ell(x)]$, the estimator $\hat g$ is:",
            "options": _opts(
                r"Biased, because the draws are dependent",
                r"Unbiased",
                r"Unbiased only if $B$ divides $|\mathcal{D}|$",
                r"Unbiased only when sampling with replacement",
            ),
            "correct": "B",
            "explanation": r"Each $x_b$ is marginally uniform on $\mathcal{D}$, so $\mathbb{E}[\ell(x_b)] = \mathbb{E}_{\mathcal{D}}[\ell]$; linearity then gives $\mathbb{E}[\hat g] = \mathbb{E}_{\mathcal{D}}[\ell]$. Dependence affects the variance, not the mean.",
        },
        "productive_failure": {
            "prompt": r"Shuffle a standard 52-card deck. What is the expected number of adjacent positions $(k, k+1)$ where both cards are hearts? Try computing the full distribution of that count first. Then look for a shortcut.",
            "canonical_insight": r"The distribution is messy, but the count is $\sum_{k=1}^{51}\mathbf{1}\{\text{cards } k, k+1 \text{ both hearts}\}$, each with probability $\tfrac{13}{52}\cdot\tfrac{12}{51} = \tfrac1{17}$. Linearity gives $51/17 = 3$, ignoring all dependence between overlapping pairs.",
        },
        "practice": {
            1: {
                "prompt": r"Your hash table maps 1000 keys into 500 buckets, each key independently and uniformly. Capacity planning needs the expected number of **empty** buckets. Get it without computing the joint distribution of bucket loads.",
                "answer_summary": r"Write empties as $\sum_{j=1}^{500}\mathbf{1}\{\text{bucket } j \text{ empty}\}$, each with probability $(1 - 1/500)^{1000}$. Linearity: $500(499/500)^{1000} \approx 500e^{-2} \approx 67.5$.",
                "concept_groups": [["indicator", "1{", "sum over buckets", "each bucket"], ["(1 - 1/500)", "(1-1/500)", "499/500", "(499/500)", "e^{-2}", "e^-2", "67"], ["sum", "linear", "add up", "adding"]],
                "verify_code": r"""import numpy as np
exact = 500 * (499 / 500) ** 1000
assert abs(exact - 67.53) < 0.05 and abs(exact - 500 * np.exp(-2)) < 0.2
rng = np.random.default_rng(6)
T = 2000
keys = rng.integers(0, 500, size=(T, 1000)) + 500 * np.arange(T)[:, None]
counts = np.bincount(keys.ravel(), minlength=500 * T).reshape(T, 500)
mc = (counts == 0).sum(1).mean()
assert abs(mc - exact) < 0.6
print('VERIFIED: expected empty buckets =', round(exact, 2), 'MC', round(mc, 2))
""",
                "hints": _hints(
                    r"Sanity bounds: the answer is between 0 and 500. With twice as many keys as buckets, should most buckets be empty or occupied?",
                    r"In “{quote}”, are you trying to track how buckets interact? Do you need to?",
                    r"Can you write 'number of empty buckets' as a sum of simple 0/1 variables, one per bucket?",
                    r"Shrink it: 2 keys, 2 buckets. List the 4 equally likely outcomes and the number of empty buckets in each. Compare with 2 × P(bucket 1 empty).",
                    r"Analog: rolling a die 6 times, expected number of faces never seen $= 6\cdot(5/6)^6 \approx 2.01$ — one indicator per face, probabilities added. Transfer to buckets.",
                ),
            },
            2: {
                "prompt": r"Physics notation: $\langle\cdot\rangle$ is an ensemble average. A spin chain has spins $s_1, \dots, s_N \in \{\pm1\}$ with strong nearest-neighbour correlations, but each spin has $\langle s_i\rangle = m$. With fixed couplings $J_i$, compute $\langle M\rangle$ for $M = \sum_i J_i s_i$. Does the correlation structure matter?",
                "answer_summary": r"$\langle M\rangle = \sum_i J_i\langle s_i\rangle = m\sum_i J_i$. Linearity of the average holds regardless of correlations; correlations would matter for $\langle M^2\rangle$, not $\langle M\rangle$.",
                "concept_groups": [["m \\sum", "m∑", "m sum", "m·∑", "m*sum", "m times the sum", "sum of j", "∑j", "∑ j", "m(j", "m (j"], ["regardless", "doesn't matter", "does not matter", "no independence", "without independence", "correlation doesn't", "irrelevant", "linear"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(7)
N, T = 5, 400000
J = np.array([1.0, -2.0, 0.5, 3.0, 1.5])
common = np.where(rng.random(T) < 0.6, 1.0, -1.0)[:, None]
flip = np.where(rng.random((T, N)) < 0.1, -1.0, 1.0)
s = common * flip
m = 0.2 * 0.8
assert np.corrcoef(s[:, 0], s[:, 1])[0, 1] > 0.5
M = s @ J
assert abs(s.mean() - m) < 0.01 and abs(M.mean() - m * J.sum()) < 0.05
print('VERIFIED: <M> = sum_i J_i <s_i> despite correlation', round(M.mean(), 3))
""",
                "hints": _hints(
                    r"Check the units: $\langle M\rangle$ should scale linearly if you double every $J_i$. Does your expression?",
                    r"You wrote “{quote}”. Which of those correlations actually enter an average of a sum?",
                    r"For a sum of random quantities, which operation can you push inside an expectation with no assumptions?",
                    r"Take $N = 2$ with $s_2 = s_1$ (perfect correlation). Compute $\langle J_1 s_1 + J_2 s_2\rangle$ directly.",
                    r"Analog: the expected total score of a correlated pair of dice is $3.5 + 3.5 = 7$ whether they are glued together or independent. Transfer to the weighted spins.",
                ),
            },
            3: {
                "prompt": r"In the random hat-return setting with $n \ge 2$ guests, let $F$ be the number who get their own hat back. Compute both $\mathbb{E}[F]$ and $\mathrm{Var}(F)$. Which of the two needs information about *pairs* of guests?",
                "answer_summary": r"$\mathbb{E}[F] = n\cdot\tfrac1n = 1$ (no pairwise info). $\mathrm{Var}(F) = \sum_i\mathrm{Var}(I_i) + \sum_{i\ne j}\mathrm{Cov}(I_i, I_j) = n\cdot\tfrac1n(1 - \tfrac1n) + n(n-1)\big(\tfrac{1}{n(n-1)} - \tfrac1{n^2}\big) = 1$. The variance needs the pair probabilities $P(I_i = I_j = 1) = \tfrac1{n(n-1)}$.",
                "concept_groups": [["e[f] = 1", "e[f]=1", "expectation is 1", "mean is 1", "expected value is 1", "expected number is 1", "e = 1"], ["covariance", "cov", "pairwise", "pairs", "joint", "1/(n(n-1))"], ["var(f) = 1", "var(f)=1", "variance is 1", "variance = 1", "variance 1", "var = 1"]],
                "verify_code": r"""import itertools
import numpy as np
for n in [2, 3, 6]:
    fp = np.array([sum(p[i] == i for i in range(n)) for p in itertools.permutations(range(n))], dtype=float)
    assert abs(fp.mean() - 1) < 1e-12 and abs(fp.var() - 1) < 1e-12
print('VERIFIED: E[F] = 1 and Var(F) = 1 for n = 2, 3, 6')
""",
                "hints": _hints(
                    r"Limit check: for $n = 2$ the only outcomes are 'both' or 'neither'. What are $\mathbb{E}[F]$ and $\mathrm{Var}(F)$ there?",
                    r"In “{quote}”, did you add up variances as if the indicators were independent?",
                    r"The mean of a sum splits freely. What extra terms appear when you expand the square of a sum?",
                    r"Do $n = 3$ by listing all 6 permutations and counting fixed points.",
                    r"Analog: two indicators with $P(A) = P(B) = 1/2$ and $P(A\cap B) = 1/2$ (always together): $\mathrm{Var}(I_A + I_B) = \tfrac14 + \tfrac14 + 2(\tfrac12 - \tfrac14) = 1$. Apply the same bookkeeping to the hat indicators.",
                ),
            },
            4: {
                "prompt": r"A dashboard reports the expected inverse latency $\mathbb{E}[1/X]$ where $X$ is uniform on $\{1, 2, 3\}$ seconds. The analyst computed it as $1/\mathbb{E}[X] = 1/2$, 'just pull the expectation inside, like with sums'. Check it.",
                "answer_summary": r"Linearity covers only affine maps; $x \mapsto 1/x$ is nonlinear (convex on $x > 0$). Directly: $\mathbb{E}[1/X] = \tfrac13(1 + \tfrac12 + \tfrac13) = \tfrac{11}{18} \approx 0.611 > \tfrac12$, as convexity predicts.",
                "concept_groups": [["11/18", "0.611", "0.61"], ["nonlinear", "not linear", "non-linear", "convex", "jensen", "only affine", "affine"]],
                "verify_code": r"""import sympy as sp
xs = [1, 2, 3]
E_inv = sp.Rational(1, 3) * sum(sp.Rational(1, x) for x in xs)
inv_E = 1 / (sp.Rational(1, 3) * sum(xs))
assert E_inv == sp.Rational(11, 18) and inv_E == sp.Rational(1, 2) and E_inv > inv_E
print('VERIFIED: E[1/X] = 11/18 > 1/E[X] = 1/2')
""",
                "hints": _hints(
                    r"Check the definition: is $x\mapsto 1/x$ of the form $ax + b$?",
                    r"In “{quote}”, which operation did you pull the expectation through?",
                    r"Linearity of expectation is about sums and constant multiples. What do you know about expectations of curved functions?",
                    r"Compute $\mathbb{E}[1/X]$ for the two-point case $X\in\{1, 3\}$ equally likely, and compare with $1/\mathbb{E}[X]$.",
                    r"Analog: $X\in\{1, 3\}$: $\mathbb{E}[X^2] = 5$ but $(\mathbb{E}X)^2 = 4$. Squaring is not linear, so the expectation does not pass through it. Same story for $1/x$.",
                ),
            },
        },
        "referee": {
            "claim": r"For any random variables $X, Y$ with finite second moments, $\mathbb{E}[XY] = \mathbb{E}[X]\,\mathbb{E}[Y]$.",
            "steps": [
                r"Expectation is linear: $\mathbb{E}[aU + bV] = a\,\mathbb{E}[U] + b\,\mathbb{E}[V]$.",
                r"Polarization: $XY = \tfrac14\big[(X+Y)^2 - (X-Y)^2\big]$ pointwise.",
                r"By linearity, $\mathbb{E}[XY] = \tfrac14\big(\mathbb{E}[(X+Y)^2] - \mathbb{E}[(X-Y)^2]\big)$.",
                r"Linearity also gives $\mathbb{E}[(X+Y)^2] = (\mathbb{E}[X+Y])^2 = (\mathbb{E}X + \mathbb{E}Y)^2$, and likewise for $X - Y$.",
                r"Hence $\mathbb{E}[XY] = \tfrac14\big[(\mathbb{E}X + \mathbb{E}Y)^2 - (\mathbb{E}X - \mathbb{E}Y)^2\big] = \mathbb{E}X\,\mathbb{E}Y$.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["square", "nonlinear", "not linear", "e[x^2]", "variance", "(e[x])^2", "jensen", "e[z^2]"],
            "explanation": r"Squaring is not linear: $\mathbb{E}[Z^2] = (\mathbb{E}Z)^2 + \mathrm{Var}(Z)$. Restoring the variances gives $\mathbb{E}[XY] = \mathbb{E}X\mathbb{E}Y + \tfrac14(\mathrm{Var}(X+Y) - \mathrm{Var}(X-Y)) = \mathbb{E}X\mathbb{E}Y + \mathrm{Cov}(X,Y)$.",
            "counterexample": r"$X = Y = \pm1$ with probability $\tfrac12$ each: $\mathbb{E}[XY] = 1$ but $\mathbb{E}X\,\mathbb{E}Y = 0$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Mia, a careful statistics student who believes you may only add expectations when the variables are independent.",
            "opening": r"In the hat-check problem the events 'guest $i$ gets their hat' are dependent, so you can't just add up $n$ copies of $1/n$. Can you explain why everyone says the answer is exactly $1$?",
            "boundary_conditions": [
                _bc("no_independence_needed", r"Linearity holds with no independence assumption: it is just splitting a sum (or integral) over outcomes",
                    ["no independence", "without independence", "regardless", "dependent", "any dependence", "doesn't need independence", "does not need independence", "split"],
                    r"The hat events are dependent — surely adding the $1/n$'s ignores that?"),
                _bc("integrability", r"Needs each $\mathbb{E}|X_i| < \infty$ (otherwise $\infty - \infty$ can appear)",
                    ["finite", "integrable", "e|x", "∞ - ∞", "infinity minus infinity", "exist"],
                    r"If $X$ is Cauchy and $Y = -X$, is $\mathbb{E}[X+Y] = \mathbb{E}[X] + \mathbb{E}[Y]$?"),
                _bc("linear_only", r"Covers linear (affine) combinations only; products and nonlinear functions need more",
                    ["product", "e[xy]", "nonlinear", "non-linear", "affine", "only linear", "squares"],
                    r"Then $\mathbb{E}[X^2] = (\mathbb{E}X)^2$ too, by the same linearity?"),
            ],
        },
        "misconceptions": [
            _mis(["needs independence", "only if independent", "since they're dependent we can't", "can't add because dependent"], "FALSE_ANALOGY",
                 "Linearity requires independence", r"\mathbb{E}[X+Y] = \mathbb{E}X + \mathbb{E}Y \text{ only if } X \perp\!\!\!\perp Y"),
            _mis(["e[xy] = e[x]e[y]", "expectation of a product is the product"], "FALSE_ANALOGY",
                 "Product rule for expectation", r"\mathbb{E}[XY] = \mathbb{E}[X]\,\mathbb{E}[Y]"),
            _mis(["e[1/x] = 1/e[x]", "e[f(x)] = f(e[x])", "plug in the mean"], "FALSE_ANALOGY",
                 "Expectation commutes with nonlinear maps", r"\mathbb{E}[f(X)] = f(\mathbb{E}[X])"),
        ],
    },
    "prop_var_indep_sum": {
        "probe": {
            "prompt": r"$X_1, X_2, X_3, X_4$ are i.i.d. with variance $\sigma^2$. What are $\mathrm{Var}(X_1 + X_2 + X_3 + X_4)$ and $\mathrm{Var}(4X_1)$?",
            "options": _opts(
                r"Both $4\sigma^2$",
                r"$4\sigma^2$ and $16\sigma^2$",
                r"$16\sigma^2$ and $4\sigma^2$",
                r"$2\sigma^2$ and $4\sigma^2$",
            ),
            "correct": "B",
            "explanation": r"Independent terms: variances add, $4\sigma^2$. One variable scaled by $4$: $\mathrm{Var}(4X_1) = 16\sigma^2$, which is the sum of four *perfectly correlated* copies, where all 12 cross-covariances equal $\sigma^2$.",
        },
        "predict": {
            "prompt": r"Predict: you sum readings from $n$ independent noisy sensors. Does the standard deviation of the sum grow like $n$ or like $\sqrt n$? What changes if all sensors share one common noise source?",
        },
        "reading": r"""**Base case $n = 2$.** Center first: $X' = X - \mathbb{E}X$, $Y' = Y - \mathbb{E}Y$. Then
$$\mathrm{Var}(X + Y) = \mathbb{E}[(X' + Y')^2] = \mathrm{Var}X + \mathrm{Var}Y + 2\,\mathrm{Cov}(X, Y).$$
The cross term is the whole story. If $\mathrm{Cov}(X, Y) = 0$ (for instance, independent), variances add.

**Induct.** $\mathrm{Var}\big(\sum_i X_i\big) = \sum_i \mathrm{Var}X_i + 2\sum_{i<j}\mathrm{Cov}(X_i, X_j)$. Pairwise uncorrelated with variance $\sigma^2$: the sum has variance $d\sigma^2$, standard deviation $\sqrt d\,\sigma$.

**Contrast scaling.** $\mathrm{Var}(cX) = \mathbb{E}[(cX')^2] = c^2\,\mathrm{Var}X$. So $dX$ has variance $d^2\sigma^2$. Seen as a sum of $d$ copies of the *same* variable, the extra $d(d-1)\sigma^2$ comes from the $d(d-1)$ cross-covariances, each equal to $\sigma^2$.

**Consequence.** The average of $d$ uncorrelated readings has variance $\sigma^2/d$: noise falls like $1/\sqrt d$.

**Self-explanation:** Use the cross term to compute $\mathrm{Var}(X_1 + X_2)$ when $X_2 = -X_1$. Why is it $0$?""",
        "check": {
            "prompt": r"Signal processing: $n[t]$ is zero-mean white noise with $\mathbb{E}[n[t]\,n[s]] = N_0\,\delta_{ts}$. A moving-sum filter outputs $y = \sum_{t=1}^{16} n[t]$. The output power $\mathbb{E}[y^2]$ is:",
            "options": _opts(r"$16N_0$", r"$256N_0$", r"$4N_0$", r"$N_0$"),
            "correct": "A",
            "explanation": r"$\mathbb{E}[y^2] = \sum_{t,s}\mathbb{E}[n[t]n[s]] = \sum_{t,s}N_0\delta_{ts} = 16N_0$. White means the cross terms vanish, so 'powers' (variances) add.",
        },
        "productive_failure": {
            "prompt": r"Two thermometers each have error variance $1$, and their errors have correlation $\rho$. You report $wT_1 + (1-w)T_2$. Find the $w$ minimizing the error variance and the minimum value. What happens as $\rho \to 1$? As $\rho \to -1$?",
            "canonical_insight": r"$\mathrm{Var} = w^2 + (1-w)^2 + 2w(1-w)\rho$, minimized at $w = \tfrac12$ by symmetry, giving $(1+\rho)/2$. At $\rho = 0$ averaging halves the variance; at $\rho \to 1$ there is no gain (shared noise doesn't cancel); at $\rho \to -1$ errors cancel completely. The covariance cross term decides everything.",
        },
        "practice": {
            1: {
                "prompt": r"You accumulate gradients over 64 independent microbatches; each microbatch gradient has per-coordinate noise variance $0.25$. What is the noise standard deviation of the **summed** gradient, and of the **averaged** gradient?",
                "answer_summary": r"Sum: variance $64 \times 0.25 = 16$, std $4$. Average: variance $0.25/64$, std $0.5/8 = 0.0625$.",
                "concept_groups": [["4"], ["0.0625", "1/16"], ["independent", "uncorrelated", "add", "cov"]],
                "verify_code": r"""import numpy as np
var_sum = 64 * 0.25; var_mean = 0.25 / 64
assert np.isclose(np.sqrt(var_sum), 4.0) and np.isclose(np.sqrt(var_mean), 0.0625)
rng = np.random.default_rng(8)
g = rng.normal(0, 0.5, size=(20000, 64))
assert abs(g.sum(1).std() - 4) < 0.08 and abs(g.mean(1).std() - 0.0625) < 0.0015
print('VERIFIED: sum std 4, mean std 0.0625')
""",
                "hints": _hints(
                    r"Units check: variance is in squared units. Are you adding variances or standard deviations?",
                    r"In “{quote}”, did you scale the standard deviation by 64 or by the square root of 64?",
                    r"For independent pieces, which quantity adds up exactly: the spread or its square?",
                    r"Two microbatches only: variance of the sum? Of the average?",
                    r"Analog: 100 independent coin-flip counters with variance $0.25$ each: sum variance $25$ (std $5$), average variance $0.0025$ (std $0.05$). Transfer to 64 microbatches.",
                ),
            },
            2: {
                "prompt": r"Notation: $\mathbb{V}[\cdot]$ is variance and $\epsilon_l \overset{\text{iid}}{\sim}(0, s^2)$. A residual stream accumulates $h_L = h_0 + \sum_{l=1}^L \epsilon_l$ with $h_0$ fixed. For $L = 9$, $s = 0.1$, compute $\mathbb{V}[h_L]$ and compare with $\mathbb{V}[L\,\epsilon_1]$ (one update reused $L$ times).",
                "answer_summary": r"$\mathbb{V}[h_L] = L s^2 = 9 \times 0.01 = 0.09$. $\mathbb{V}[L\epsilon_1] = L^2 s^2 = 81\times0.01 = 0.81$. Independent updates add variance linearly in $L$; a reused update scales it by $L^2$.",
                "concept_groups": [["0.09"], ["0.81"], ["c^2", "c²", "squared", "l^2", "l²", "81"]],
                "verify_code": r"""import numpy as np
L, s = 9, 0.1
assert np.isclose(L * s**2, 0.09) and np.isclose(L**2 * s**2, 0.81)
rng = np.random.default_rng(9)
e = rng.normal(0, s, size=(200000, L))
assert abs(e.sum(1).var() - 0.09) < 0.002 and abs((L * e[:, 0]).var() - 0.81) < 0.015
print('VERIFIED: V[h_L] = 0.09, V[L eps] = 0.81')
""",
                "hints": _hints(
                    r"The fixed $h_0$ contributes what to the variance?",
                    r"In “{quote}”, which of the two expressions is a sum of different random terms and which is one term scaled?",
                    r"What does a constant multiplier do to variance, compared with adding independent copies?",
                    r"Try $L = 2$: compute $\mathbb{V}[\epsilon_1 + \epsilon_2]$ and $\mathbb{V}[2\epsilon_1]$.",
                    r"Analog: two independent dice sum has variance $2\times\tfrac{35}{12}$; doubling one die gives $4\times\tfrac{35}{12}$. Now use $L = 9$, $s^2 = 0.01$.",
                ),
            },
            3: {
                "prompt": r"You ensemble 10 models whose prediction errors each have variance $1$ and pairwise correlation $0.3$. What is the error variance of the ensemble **average**? Compare with uncorrelated errors, and with the limit of infinitely many such models.",
                "answer_summary": r"$\mathrm{Var}(\bar e) = \tfrac{1}{n^2}\big(n + n(n-1)\rho\big) = \rho + \tfrac{1-\rho}{n} = 0.3 + 0.07 = 0.37$. Uncorrelated: $1/10 = 0.1$. As $n \to\infty$ it floors at $\rho = 0.3$: correlated error cannot be averaged away.",
                "concept_groups": [["0.37"], ["0.1"], ["0.3", "floor", "ρσ²", "rho"], ["covariance", "cov", "cross", "correlat"]],
                "verify_code": r"""import numpy as np
n, rho = 10, 0.3
C = np.full((n, n), rho) + (1 - rho) * np.eye(n)
w = np.ones(n) / n
v = w @ C @ w
assert np.isclose(v, 0.37)
big = 10**6
assert abs(rho + (1 - rho) / big - 0.3) < 1e-6
print('VERIFIED: ensemble variance 0.37, uncorrelated 0.1, floor 0.3')
""",
                "hints": _hints(
                    r"Limit check: with $\rho = 1$ the average equals any single model. Does your formula give $1$ there?",
                    r"In “{quote}”, how many cross-covariance terms did you include, and what is each one worth?",
                    r"Expanding the variance of a sum produces two kinds of terms. What are they, and how many of each?",
                    r"Two models with correlation $\rho$: compute $\mathrm{Var}\big(\tfrac{e_1 + e_2}{2}\big)$.",
                    r"Analog: 4 models, $\rho = 0.5$: $\tfrac1{16}(4 + 12\times0.5) = 0.625 = 0.5 + 0.5/4$. Transfer to 10 models and $\rho = 0.3$.",
                ),
            },
            4: {
                "prompt": r"A risk report computes the two-day return variance as $\mathrm{Var}(X_1 + X_2) = 2\sigma^2 = 2$, where $X_1, X_2$ are consecutive daily returns with $\sigma^2 = 1$ each. But returns in this market have lag-1 correlation $-0.4$. Correct the number.",
                "answer_summary": r"Variances add only for uncorrelated returns. $\mathrm{Var}(X_1+X_2) = 1 + 1 + 2(-0.4)(1) = 1.2$: the negative autocorrelation (mean reversion) reduces two-day risk.",
                "concept_groups": [["1.2"], ["covariance", "cov", "correlat", "cross term"]],
                "verify_code": r"""import numpy as np
C = np.array([[1.0, -0.4], [-0.4, 1.0]])
assert np.isclose(np.ones(2) @ C @ np.ones(2), 1.2)
rng = np.random.default_rng(10)
X = rng.multivariate_normal([0, 0], C, size=200000)
assert abs(X.sum(1).var() - 1.2) < 0.02
print('VERIFIED: Var(X1+X2) = 1.2')
""",
                "hints": _hints(
                    r"Bounds check: with correlation between $-1$ and $1$, the two-day variance must lie between $0$ and $4$. Where does $2$ sit, and why?",
                    r"You wrote “{quote}”. Which assumption about the two days does that formula silently make?",
                    r"Expanding $(X_1' + X_2')^2$, which term did the report drop?",
                    r"Try the extreme $X_2 = -X_1$ (correlation $-1$): what is the variance of the sum?",
                    r"Analog: correlation $+0.5$, unit variances: $\mathrm{Var} = 1 + 1 + 2(0.5) = 3$. Redo it with $-0.4$.",
                ),
            },
        },
        "referee": {
            "claim": r"If $\mathrm{Var}X = \mathrm{Var}Y = 1$, then $\mathrm{Var}(X+Y) = 2$.",
            "steps": [
                r"$\mathrm{Var}(Z) = \mathbb{E}[(Z - \mathbb{E}Z)^2]$ for any square-integrable $Z$.",
                r"Let $Z = X+Y$. By linearity of expectation, $\mathbb{E}Z = \mathbb{E}X + \mathbb{E}Y$.",
                r"Hence $Z - \mathbb{E}Z = (X - \mathbb{E}X) + (Y - \mathbb{E}Y)$.",
                r"Squaring and taking expectations, $\mathbb{E}[(Z - \mathbb{E}Z)^2] = \mathbb{E}[(X-\mathbb{E}X)^2] + \mathbb{E}[(Y - \mathbb{E}Y)^2]$, since both centred parts have mean zero.",
                r"Therefore $\mathrm{Var}(X+Y) = \mathrm{Var}X + \mathrm{Var}Y = 2$.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["cross term", "covariance", "cov", "2e[", "correlat", "y = x", "uncorrelated", "mean zero is not"],
            "explanation": r"Squaring a sum produces the cross term $2\,\mathbb{E}[(X - \mathbb{E}X)(Y - \mathbb{E}Y)] = 2\,\mathrm{Cov}(X,Y)$. Each factor having mean zero does not make their product have mean zero; that requires the variables to be uncorrelated.",
            "counterexample": r"$Y = X$ with $\mathrm{Var}X = 1$: $\mathrm{Var}(X + Y) = \mathrm{Var}(2X) = 4 \ne 2$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Ethan, who thinks variance behaves exactly like expectation: it adds for any sum and scales linearly with constants.",
            "opening": r"Variance is just an expectation of a square, and expectations are linear, so $\mathrm{Var}(X+Y) = \mathrm{Var}X + \mathrm{Var}Y$ always and $\mathrm{Var}(3X) = 3\mathrm{Var}X$. Right?",
            "boundary_conditions": [
                _bc("uncorrelated", r"Variances add only when the terms are pairwise uncorrelated; in general add $2\sum_{i<j}\mathrm{Cov}(X_i, X_j)$",
                    ["uncorrelated", "covariance", "independent", "cov", "cross term"],
                    r"Then $\mathrm{Var}(X + X) = 2\,\mathrm{Var}X$, right?"),
                _bc("square_scaling", r"Constants come out squared: $\mathrm{Var}(cX) = c^2\,\mathrm{Var}X$",
                    ["c^2", "c²", "squared", "square of the constant", "9 var", "9var"],
                    r"Why isn't $\mathrm{Var}(3X)$ just $3\,\mathrm{Var}(X)$, like expectation?"),
                _bc("finite_variance", r"Requires finite variances (finite second moments)",
                    ["finite variance", "second moment", "square-integrable", "square integrable", "finite"],
                    r"Two independent Cauchy variables — what's the variance of their sum?"),
            ],
        },
        "misconceptions": [
            _mis(["var(cx) = c var(x)", "variance scales linearly", "c times the variance"], "ALGEBRAIC_SLIP",
                 "Unsquared scaling", r"\mathrm{Var}(cX) = c\,\mathrm{Var}(X)"),
            _mis(["variances always add", "var(x+y) = var(x) + var(y) always", "variance of a sum is the sum of variances"], "BOUNDARY_OMISSION",
                 "Variances add unconditionally", r"\mathrm{Var}(X+Y) = \mathrm{Var}X + \mathrm{Var}Y\ \ \forall X, Y"),
            _mis(["standard deviations add", "std adds", "σ_x + σ_y"], "FALSE_ANALOGY",
                 "Standard deviations add", r"\sigma_{X+Y} = \sigma_X + \sigma_Y"),
        ],
    },
    "prop_var_product_indep": {
        "probe": {
            "prompt": r"$X$ and $Y$ are independent, both with mean $0$, $\mathrm{Var}X = 2$ and $\mathrm{Var}Y = 3$. What is $\mathrm{Var}(XY)$?",
            "options": _opts(r"$5$", r"$6$", r"$0$", r"$36$"),
            "correct": "B",
            "explanation": r"$\mathrm{Var}(XY) = \mathbb{E}[X^2Y^2] - (\mathbb{E}[XY])^2 = \mathbb{E}[X^2]\mathbb{E}[Y^2] - 0 = 2\cdot3 = 6$. Option A adds as if it were a sum; C confuses mean zero with variance zero.",
        },
        "predict": {
            "prompt": r"Predict: if $X, Y$ are independent with variance $1$ but means $\mu_X = \mu_Y = 1$ instead of $0$, is $\mathrm{Var}(XY)$ still $1$? Bigger or smaller, and why?",
        },
        "reading": r"""**Base identity.** For any $Z$, $\mathrm{Var}(Z) = \mathbb{E}[Z^2] - (\mathbb{E}Z)^2$. Take $Z = XY$:
$$\mathrm{Var}(XY) = \mathbb{E}[X^2Y^2] - (\mathbb{E}[XY])^2.$$

**Independence, used twice.** If $X \perp\!\!\!\perp Y$, then $X^2 \perp\!\!\!\perp Y^2$, so $\mathbb{E}[X^2Y^2] = \mathbb{E}[X^2]\,\mathbb{E}[Y^2]$; also $\mathbb{E}[XY] = \mathbb{E}X\,\mathbb{E}Y$.

**Zero means.** Then $\mathbb{E}[XY] = 0$ and $\mathbb{E}[X^2] = \sigma_X^2$, so
$$\mathrm{Var}(XY) = \sigma_X^2\,\sigma_Y^2.$$

**Nonzero means.** $\mathbb{E}[X^2] = \sigma_X^2 + \mu_X^2$, which gives
$$\mathrm{Var}(XY) = \sigma_X^2\sigma_Y^2 + \mu_X^2\sigma_Y^2 + \mu_Y^2\sigma_X^2.$$

**Why it matters.** Each term $q_ik_i$ of an attention dot product is exactly such a product: with zero-mean, unit-variance, independent entries it has variance $1$.

**Self-explanation:** Which step needs $X^2$ and $Y^2$ to be uncorrelated, a property that $\mathrm{Cov}(X, Y) = 0$ alone does not provide?""",
        "check": {
            "prompt": r"Let $\xi \perp\!\!\!\perp \eta$ with $\mathbb{E}\xi = \mathbb{E}\eta = 0$, $\mathbb{E}\xi^2 = a$ and $\mathbb{E}\eta^2 = b$. Then $\mathbb{E}[(\xi\eta)^2] - (\mathbb{E}[\xi\eta])^2$ equals:",
            "options": _opts(r"$a + b$", r"$\sqrt{ab}$", r"$ab$", r"$ab - 1$"),
            "correct": "C",
            "explanation": r"The expression is $\mathrm{Var}(\xi\eta)$. Independence factorizes $\mathbb{E}[\xi^2\eta^2] = ab$, and $\mathbb{E}[\xi\eta] = 0$.",
        },
        "productive_failure": {
            "prompt": r"Let $X \sim \mathcal{N}(0,1)$. Compute $\mathrm{Var}(XY)$ for (i) $Y = X$ and (ii) $Y = X^2 - 1$. In case (ii), check that $\mathrm{Cov}(X, Y) = 0$. Compare each answer with $\mathrm{Var}X\cdot\mathrm{Var}Y$. What hypothesis is the product formula really using?",
            "canonical_insight": r"(i) $\mathrm{Var}(X^2) = 3 - 1 = 2$ vs $1\cdot1 = 1$. (ii) $\mathrm{Cov}(X, X^2-1) = \mathbb{E}X^3 = 0$, yet $\mathrm{Var}(X^3 - X) = \mathbb{E}X^6 - 2\mathbb{E}X^4 + \mathbb{E}X^2 = 15 - 6 + 1 = 10$ vs $1\cdot2 = 2$. The formula needs $\mathbb{E}[X^2Y^2] = \mathbb{E}[X^2]\mathbb{E}[Y^2]$, which follows from independence, not from zero covariance.",
        },
        "practice": {
            1: {
                "prompt": r"A gating unit multiplies two independent, zero-mean activations whose standard deviations are $0.5$ and $3$. What standard deviation should you expect for the gated product when you set your initialization scale?",
                "answer_summary": r"Zero means + independence: $\mathrm{Var}(XY) = \mathbb{E}[X^2]\mathbb{E}[Y^2] = 0.25\times9 = 2.25$, so the std is $1.5$.",
                "concept_groups": [["1.5", "2.25"], ["e[x^2]", "e[x²]", "product of", "multipl", "σ_x²σ_y²", "σ²σ²", "0.25 × 9", "0.25*9", "0.25 x 9"], ["independen", "zero mean", "mean zero", "mean 0"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(11)
x = rng.normal(0, 0.5, 10**6); y = rng.normal(0, 3, 10**6)
assert np.isclose(0.25 * 9, 2.25) and abs((x * y).std() - 1.5) < 0.01
print('VERIFIED: product std 1.5 (variance 2.25)')
""",
                "hints": _hints(
                    r"Units check: the product's spread should scale like (spread of X) × (spread of Y). Is that what your number does?",
                    r"In “{quote}”, did you add the two variances or multiply them?",
                    r"Write the variance of the product as a second moment minus a squared mean. What do independence and zero means do to each piece?",
                    r"Shrink to signs: $X, Y = \pm1$ independent fair. What is $\mathrm{Var}(XY)$?",
                    r"Analog: stds $2$ and $0.1$: $\mathrm{Var}(XY) = 4\times0.01 = 0.04$, std $0.2$ — standard deviations multiply. Transfer to $0.5$ and $3$.",
                ),
            },
            2: {
                "prompt": r"An activation $a$ with $\mathbb{E}a = 0$, $\mathbb{E}a^2 = v$ is multiplied by an independent random mask $m$ with $\mathbb{E}m = 1$ and $\mathrm{Var}\,m = p/(1-p)$. Compute $\mathrm{Var}(am)$ in closed form.",
                "answer_summary": r"$\mathrm{Var}(am) = \mathbb{E}[a^2]\mathbb{E}[m^2] - (\mathbb{E}a\,\mathbb{E}m)^2 = v\big(\tfrac{p}{1-p} + 1\big) = \tfrac{v}{1-p}$.",
                "concept_groups": [["v/(1-p)", "v/(1 - p)", "v/(1−p)", "v/(1 − p)", "1/(1-p)", "1/(1−p)"], ["e[m^2]", "e[m²]", "second moment", "1 + p/(1-p)", "var + mean", "variance plus"]],
                "verify_code": r"""import sympy as sp
v, p = sp.symbols('v p', positive=True)
Em2 = p / (1 - p) + 1
var_am = v * Em2 - (0 * 1) ** 2
assert sp.simplify(var_am - v / (1 - p)) == 0
import numpy as np
rng = np.random.default_rng(12); pp = 0.3
m = (rng.random(10**6) > pp) / (1 - pp)
a = rng.normal(0, 2.0, 10**6)
assert abs(m.mean() - 1) < 0.01 and abs(m.var() - pp / (1 - pp)) < 0.01
assert abs((a * m).var() - 4.0 / (1 - pp)) < 0.05
print('VERIFIED: Var(am) = v/(1-p)')
""",
                "hints": _hints(
                    r"Limit check: as $p \to 0$ the mask is always $1$. Your answer must reduce to $v$.",
                    r"In “{quote}”, did you use the mask's variance where its second moment belongs?",
                    r"The mask does not have mean zero. How do you get $\mathbb{E}[m^2]$ from its mean and variance?",
                    r"Let the mask be constant $m \equiv 2$. What is $\mathrm{Var}(2a)$? Does your formula with $\mathbb{E}[m^2] = 4$ agree?",
                    r"Analog: $\mathbb{E}b = 0$, $\mathbb{E}b^2 = 3$, independent $c$ with $\mathbb{E}c = 2$, $\mathrm{Var}\,c = 1$: $\mathrm{Var}(bc) = 3\times(1 + 4) = 15$. Transfer with $\mathbb{E}m = 1$.",
                ),
            },
            3: {
                "prompt": r"Two independent features both have mean $2$ and variance $1$. Your pipeline can either add them or multiply them. Compute $\mathrm{Var}(X + Y)$ and $\mathrm{Var}(XY)$, and explain why only one of them depends on the means.",
                "answer_summary": r"$\mathrm{Var}(X+Y) = 1 + 1 = 2$ (shifts never change variance). $\mathrm{Var}(XY) = \sigma_X^2\sigma_Y^2 + \mu_X^2\sigma_Y^2 + \mu_Y^2\sigma_X^2 = 1 + 4 + 4 = 9$: in a product, each variable's mean *scales* the other's fluctuations.",
                "concept_groups": [["9"], ["= 2", "=2", "is 2", "var(x+y) = 2", "var(x + y) = 2", "1 + 1"], ["mean", "μ", "shift", "location", "scales"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(13)
x = rng.normal(2, 1, 10**6); y = rng.normal(2, 1, 10**6)
assert abs((x + y).var() - 2) < 0.02 and abs((x * y).var() - 9) < 0.1
print('VERIFIED: Var(X+Y) = 2, Var(XY) = 9')
""",
                "hints": _hints(
                    r"Shift test: what happens to $\mathrm{Var}(X+Y)$ if you add $5$ to both? To $\mathrm{Var}(XY)$?",
                    r"In “{quote}”, did you use the second moments or the variances inside the product?",
                    r"For the product, write $\mathbb{E}[X^2]$ in terms of the mean and variance of $X$.",
                    r"Make $Y$ constant: $Y \equiv 2$. Then $\mathrm{Var}(XY) = 4\,\mathrm{Var}X$. Which term of the general formula is that?",
                    r"Analog: means $1$, variances $1$: $\mathrm{Var}(XY) = 1 + 1 + 1 = 3$ while $\mathrm{Var}(X + Y) = 2$. Now redo it with means $2$.",
                ),
            },
            4: {
                "prompt": r"To save parameters, a teammate ties keys to queries ($k = q$, so each logit term is $q_1k_1 = q_1^2$) and still writes $\mathrm{Var}(q_1k_1) = \mathrm{Var}(q_1)\mathrm{Var}(k_1) = 1$ for $q_1 \sim \mathcal{N}(0,1)$. What is the correct variance and which premise broke?",
                "answer_summary": r"$q_1$ and $k_1 = q_1$ are not independent. $\mathrm{Var}(q_1^2) = \mathbb{E}q_1^4 - (\mathbb{E}q_1^2)^2 = 3 - 1 = 2$. Also the mean is $1$, not $0$.",
                "concept_groups": [["= 2", "=2", "is 2", "2.0", "two", "3 - 1", "3-1", "3 − 1"], ["not independent", "dependent", "tied", "same variable", "e[q^4]", "fourth moment", "e[x^4]", "e[q⁴]"]],
                "verify_code": r"""import sympy as sp
from sympy.stats import Normal, E, variance
q = Normal('q', 0, 1)
assert sp.simplify(E(q**4)) == 3
assert sp.simplify(variance(q**2)) == 2
print('VERIFIED: Var(q^2) = 2 for standard normal q')
""",
                "hints": _hints(
                    r"Mean check first: what is $\mathbb{E}[q_1^2]$? Is it zero, as the product formula assumed?",
                    r"In “{quote}”, which hypothesis of the product rule did tying the weights remove?",
                    r"Without independence, you must compute $\mathbb{E}[Z^2] - (\mathbb{E}Z)^2$ for $Z = q_1^2$ directly. Which moment of the Gaussian do you need?",
                    r"Replace the Gaussian by $q = \pm1$: then $q^2 \equiv 1$. What is its variance, and why does that already contradict the formula?",
                    r"Analog: $U$ uniform on $\{-1, 0, 1\}$: $\mathrm{Var}(U\cdot U) = \mathbb{E}U^4 - (\mathbb{E}U^2)^2 = \tfrac23 - \tfrac49 = \tfrac29$, not $(\tfrac23)^2$. Use $\mathbb{E}q^4 = 3$ for the Gaussian.",
                ),
            },
        },
        "referee": {
            "claim": r"If $\mathbb{E}X = \mathbb{E}Y = 0$ and $\mathrm{Cov}(X, Y) = 0$, then $\mathrm{Var}(XY) = \mathrm{Var}(X)\,\mathrm{Var}(Y)$.",
            "steps": [
                r"$\mathrm{Var}(XY) = \mathbb{E}[X^2Y^2] - (\mathbb{E}[XY])^2$.",
                r"$\mathbb{E}[XY] = \mathrm{Cov}(X, Y) + \mathbb{E}X\,\mathbb{E}Y = 0$.",
                r"Since $\mathrm{Cov}(X,Y) = 0$, $X$ and $Y$ are independent, so $X^2$ and $Y^2$ are independent too.",
                r"Hence $\mathbb{E}[X^2Y^2] = \mathbb{E}[X^2]\,\mathbb{E}[Y^2]$.",
                r"With zero means $\mathbb{E}[X^2] = \mathrm{Var}X$ and $\mathbb{E}[Y^2] = \mathrm{Var}Y$, so $\mathrm{Var}(XY) = \mathrm{Var}X\,\mathrm{Var}Y$.",
            ],
            "flawed_index": 3,
            "violated_keywords": ["uncorrelated", "independen", "cov = 0", "zero covariance", "y = x^2", "x^2 - 1", "x² - 1"],
            "explanation": r"Zero covariance does not imply independence, and it says nothing about whether $X^2$ and $Y^2$ are correlated. The factorization $\mathbb{E}[X^2Y^2] = \mathbb{E}[X^2]\mathbb{E}[Y^2]$ genuinely needs independence (or at least uncorrelated squares).",
            "counterexample": r"$X\sim\mathcal{N}(0,1)$, $Y = X^2 - 1$: $\mathrm{Cov}(X,Y) = \mathbb{E}X^3 = 0$ and both means are $0$, but $\mathrm{Var}(XY) = 15 - 6 + 1 = 10 \ne \mathrm{Var}X\cdot\mathrm{Var}Y = 2$.",
        },
        "feynman": {
            "buggy_rule_id": "bug_uncorrelated_implies_indep",
            "persona": r"Omar, who learned that zero covariance means 'unrelated' and therefore applies every independence formula once $\mathrm{Cov} = 0$.",
            "opening": r"For the attention-variance argument we only need $q_i$ and $k_i$ uncorrelated, right? Zero covariance, so $\mathrm{Var}(q_ik_i) = \mathrm{Var}(q_i)\mathrm{Var}(k_i)$. Can you explain why people insist on independence?",
            "boundary_conditions": [
                _bc("independence", r"Needs independence (so $X^2, Y^2$ are uncorrelated and $\mathbb{E}[X^2Y^2] = \mathbb{E}X^2\,\mathbb{E}Y^2$), not just $\mathrm{Cov}(X,Y) = 0$",
                    ["independen", "x² and y²", "x^2 and y^2", "e[x^2y^2]", "e[x²y²]", "squares"],
                    r"$\mathrm{Cov}(X, Y) = 0$ was enough for adding variances — why not for multiplying?"),
                _bc("zero_means", r"Zero means; otherwise $\mathrm{Var}(XY) = \sigma_X^2\sigma_Y^2 + \mu_X^2\sigma_Y^2 + \mu_Y^2\sigma_X^2$",
                    ["zero mean", "mean zero", "mean 0", "μ", "centered", "centred"],
                    r"What if both variables have mean $5$? Same formula?"),
                _bc("finite_second_moments", r"Finite second moments $\mathbb{E}X^2, \mathbb{E}Y^2 < \infty$",
                    ["finite", "second moment", "square-integrable", "square integrable"],
                    r"Does it still work if $X$ is Student-$t$ with 2 degrees of freedom?"),
            ],
        },
        "misconceptions": [
            _mis(["var(xy) = var(x) + var(y)", "variances add for products", "add the variances of the factors"], "FALSE_ANALOGY",
                 "Product variance adds", r"\mathrm{Var}(XY) = \mathrm{Var}X + \mathrm{Var}Y"),
            _mis(["uncorrelated is enough", "cov = 0 so e[x^2y^2]", "zero covariance so independent", "uncorrelated so the formula holds"], "BOUNDARY_OMISSION",
                 "Uncorrelated suffices for products", r"\mathrm{Cov}(X,Y) = 0 \implies \mathrm{Var}(XY) = \mathrm{Var}X\,\mathrm{Var}Y"),
            _mis(["means don't matter", "regardless of the mean", "mean doesn't affect"], "BOUNDARY_OMISSION",
                 "Mean-free product variance", r"\mathrm{Var}(XY) = \sigma_X^2\sigma_Y^2 \text{ for any } \mu_X, \mu_Y"),
        ],
    },
    "prop_jensen_convex_max": {
        "probe": {
            "prompt": r"$Z_1, Z_2$ are i.i.d. $\mathcal{N}(0, 1)$. What is $\mathbb{E}[\max(Z_1, Z_2)]$?",
            "options": _opts(r"$0$", r"$1/\sqrt\pi \approx 0.564$", r"$1$", r"$-1/\sqrt\pi$"),
            "correct": "B",
            "explanation": r"$\max(a,b) = \tfrac{a+b}2 + \tfrac{|a-b|}2$. $Z_1 - Z_2 \sim \mathcal{N}(0, 2)$ has $\mathbb{E}|Z_1 - Z_2| = \sqrt2\sqrt{2/\pi} = 2/\sqrt\pi$, so $\mathbb{E}\max = 1/\sqrt\pi > 0 = \max_a\mathbb{E}Z_a$.",
        },
        "predict": {
            "prompt": r"Predict: 10 slot machines all have true mean payout $0$. You estimate each from 5 noisy pulls and pick the one with the highest estimate. On average, will its estimate be $0$, positive, or negative? Does that grow with more machines?",
        },
        "reading": r"""**Base case: two numbers.** $\varphi(a, b) = \max(a, b)$ is convex: each coordinate of $\lambda z + (1-\lambda)z'$ is at most $\lambda\max(z) + (1-\lambda)\max(z')$.

**The inequality in one line.** For every outcome and every fixed index $a$, $\max_b Z_b \ge Z_a$. Take expectations: $\mathbb{E}[\max_b Z_b] \ge \mathbb{E}[Z_a]$ for each $a$. The left side does not depend on $a$, so
$$\mathbb{E}\big[\max_a Z_a\big] \ge \max_a \mathbb{E}[Z_a].$$
This is Jensen's inequality for the convex map $\varphi = \max$.

**When is it strict?** Equality forces one fixed coordinate to be the maximum almost surely. With independent non-degenerate noise, different coordinates win on different draws, so the gap is positive. Example: $Z_1, Z_2$ i.i.d. $\mathcal{N}(0,1)$ give $\mathbb{E}\max = 1/\sqrt\pi \approx 0.56 > 0$.

**Reading the gap.** The left side picks the winner *after* seeing the noise; the right side commits *before*. Hindsight has positive value.

**Self-explanation:** Why is the one-line argument "$\max_b Z_b \ge Z_a$ for each $a$" already a complete proof, with no convexity machinery?""",
        "check": {
            "prompt": r"Let $\mathrm{LSE}_\beta(z) = \tfrac1\beta\log\sum_a e^{\beta z_a}$, a smooth convex surrogate of $\max_a z_a$. For a random vector $z$ with finite mean, compare $\mathbb{E}[\mathrm{LSE}_\beta(z)]$ and $\mathrm{LSE}_\beta(\mathbb{E}z)$.",
            "options": _opts(
                r"$\mathbb{E}[\mathrm{LSE}_\beta(z)] \le \mathrm{LSE}_\beta(\mathbb{E}z)$",
                r"$\mathbb{E}[\mathrm{LSE}_\beta(z)] \ge \mathrm{LSE}_\beta(\mathbb{E}z)$",
                r"They are always equal",
                r"No general relation",
            ),
            "correct": "B",
            "explanation": r"$\mathrm{LSE}_\beta$ is convex, so Jensen gives $\mathbb{E}\varphi(z) \ge \varphi(\mathbb{E}z)$, the same direction as for the hard max.",
        },
        "productive_failure": {
            "prompt": r"Three treatments all have true effect $0$. Each is estimated once with independent $\mathcal{N}(0,1)$ noise, and you report the best-looking one. Estimate $\mathbb{E}[\text{reported effect}]$ (simulation in your head is fine). Then design a procedure that reports an effect with no upward bias.",
            "canonical_insight": r"$\mathbb{E}[\max\text{ of 3 i.i.d. }\mathcal{N}(0,1)] = \tfrac{3}{2\sqrt\pi} \approx 0.846 > 0$: selecting on noise inflates the winner. Fix: select the winner with one sample and re-estimate it on an independent sample. Conditional on the selection, the fresh estimate is unbiased (the double-estimator / cross-fitting idea).",
        },
        "practice": {
            1: {
                "prompt": r"Your hyperparameter sweep compares 2 configurations that are truly equivalent; each validation score has independent $\mathcal{N}(0, 0.04)$ noise around the same true value. You report the better score. By how much does your report overstate the truth on average?",
                "answer_summary": r"Optimism $= \mathbb{E}[\max(\varepsilon_1, \varepsilon_2)] = \sigma/\sqrt\pi = 0.2/\sqrt\pi \approx 0.113$, positive because $\mathbb{E}\max \ge \max\mathbb{E}$ and the winner varies with the noise.",
                "concept_groups": [["0.113", "0.11", "σ/√π", "0.2/√π", "0.2/sqrt(pi)"], ["max", "convex", "jensen", "selection", "optimis", "winner"]],
                "verify_code": r"""import numpy as np
from scipy import integrate, stats
s = 0.2
f = lambda x: x * 2 * stats.norm.pdf(x, 0, s) * stats.norm.cdf(x, 0, s)
val, _ = integrate.quad(f, -3, 3)
assert abs(val - s / np.sqrt(np.pi)) < 1e-6 and abs(val - 0.1128) < 1e-3
print('VERIFIED: optimism =', round(val, 4))
""",
                "hints": _hints(
                    r"Sign check: can the expected maximum of two zero-mean noises be negative? Can it be zero?",
                    r"In “{quote}”, did you assume the noise averages out after the selection step?",
                    r"Compare 'pick the winner, then average over noise' with 'average over noise, then pick'. Which is larger?",
                    r"Write $\max(a, b) = \tfrac{a + b}{2} + \tfrac{|a - b|}{2}$ and take expectations for the two noises.",
                    r"Analog: two fair coins valued $\pm1$: $\mathbb{E}\max = \tfrac34(1) + \tfrac14(-1) = \tfrac12 > 0$. Use the $|a - b|$ identity for the Gaussian case with $\sigma = 0.2$.",
                ),
            },
            2: {
                "prompt": r"Economics notation: an agent picks $\arg\sup_{a\in A}\hat u(a)$ with $\hat u(a) = u(a) + \varepsilon_a$, $\varepsilon_a$ i.i.d. Gumbel$(0,1)$, $|A| = n$, and all $u(a) = 0$. Compute $\mathbb{E}[\sup_a\hat u(a)] - \sup_a\mathbb{E}[\hat u(a)]$.",
                "answer_summary": r"The max of $n$ i.i.d. Gumbel$(0,1)$ is Gumbel$(\ln n, 1)$, with mean $\ln n + \gamma_E$; each $\mathbb{E}\hat u(a) = \gamma_E$. The Euler constant cancels: the gap is $\ln n$.",
                "concept_groups": [["ln n", "log n", "\\log n", "ln(n)", "log(n)"], ["gumbel", "euler", "γ", "0.577", "cancel"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(14)
n = 5
g = rng.gumbel(0, 1, size=(400000, n))
gap = g.max(1).mean() - g.mean()
assert abs(gap - np.log(n)) < 0.01
print('VERIFIED: gap =', round(gap, 4), 'vs ln 5 =', round(np.log(n), 4))
""",
                "hints": _hints(
                    r"Check $n = 1$: what must the gap be?",
                    r"In “{quote}”, did you subtract the mean of a single Gumbel from the mean of the maximum?",
                    r"The CDF of a maximum of i.i.d. variables is the CDF raised to the power $n$. What does that do to $\exp(-e^{-x})$?",
                    r"Compute $F(x)^n$ for $F(x) = \exp(-e^{-x})$ and $n = 2$. Which shift turns it back into a standard Gumbel CDF?",
                    r"Analog: maximum of $n$ i.i.d. Exp$(1)$ has mean $1 + \tfrac12 + \dots + \tfrac1n$, so the gap is $H_n - 1$. For Gumbel the CDF shifts by exactly $\ln n$; transfer that.",
                ),
            },
            3: {
                "prompt": r"Two noisy estimates $Z_1, Z_2$ are each standard normal with correlation $\rho$. Compute $\mathbb{E}[\max(Z_1, Z_2)]$ for $\rho = 0$, $0.75$, and $1$, and explain the trend.",
                "answer_summary": r"$\mathbb{E}\max = \tfrac12\mathbb{E}|Z_1 - Z_2| = \sqrt{(1-\rho)/\pi}$: $0.564$, $0.282$, $0$. The gap shrinks as the noise becomes shared; at $\rho = 1$ the same coordinate always wins and Jensen's inequality is tight.",
                "concept_groups": [["0.564", "0.56", "1/√π"], ["0.282", "0.28"], ["ρ = 1", "rho = 1", "ρ=1", "perfectly correlated", "no gap", "equality", "tight", "same coordinate"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(15)
for rho, target in [(0.0, 0.5642), (0.75, 0.2821), (1.0, 0.0)]:
    assert abs(np.sqrt((1 - rho) / np.pi) - target) < 1e-3
    C = np.array([[1, rho], [rho, 1]])
    Z = rng.multivariate_normal([0, 0], C, size=400000)
    assert abs(Z.max(1).mean() - target) < 0.006
print('VERIFIED: E max = sqrt((1-rho)/pi): 0.564, 0.282, 0')
""",
                "hints": _hints(
                    r"Extreme check: at $\rho = 1$, $Z_1 = Z_2$. What is $\mathbb{E}\max$ there?",
                    r"In “{quote}”, how did the correlation enter the spread of the difference?",
                    r"Express the max through the difference $Z_1 - Z_2$. What is the variance of that difference?",
                    r"Compute $\mathrm{Var}(Z_1 - Z_2)$ for $\rho = 0.75$ and then $\mathbb{E}|Z_1 - Z_2|$ for a centered Gaussian with that variance.",
                    r"Analog: if $\mathrm{Var}(Z_1 - Z_2) = 2$, then $\mathbb{E}|Z_1 - Z_2| = \sqrt2\sqrt{2/\pi}$ and $\mathbb{E}\max = 1/\sqrt\pi$. Redo with $\mathrm{Var} = 2(1 - \rho)$.",
                ),
            },
            4: {
                "prompt": r"A colleague estimating worst-case loss argues: 'By the same argument as for the best-case estimate, $\mathbb{E}[\min_a Z_a] \ge \min_a\mathbb{E}[Z_a]$.' Check this for two i.i.d. standard normals.",
                "answer_summary": r"$\min$ is concave, so the inequality reverses: $\mathbb{E}[\min_a Z_a] \le \min_a\mathbb{E}[Z_a]$ (since $\min_b Z_b \le Z_a$ for each $a$). For two i.i.d. $\mathcal{N}(0,1)$, $\mathbb{E}\min = -1/\sqrt\pi \approx -0.564 < 0$.",
                "concept_groups": [["concave"], ["≤", "<=", "revers", "opposite", "less than", "flips"], ["-0.564", "−0.564", "-1/√π", "−1/√π", "-0.56", "−0.56"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(16)
Z = rng.normal(size=(10**6, 2))
m = Z.min(1).mean()
assert abs(m + 1 / np.sqrt(np.pi)) < 0.005 and m < 0
print('VERIFIED: E[min] =', round(m, 4), '< 0 = min E')
""",
                "hints": _hints(
                    r"Sign check: can the average of the smaller of two zero-mean draws be positive?",
                    r"In “{quote}”, what property of min did you assume? Is min convex or concave?",
                    r"Write the pointwise one-liner for min: how does $\min_b Z_b$ compare with each $Z_a$?",
                    r"Use $\min(a,b) = \tfrac{a+b}2 - \tfrac{|a-b|}2$ with two standard normals.",
                    r"Analog: two fair $\pm1$ coins: $\mathbb{E}\min = \tfrac14(1) + \tfrac34(-1) = -\tfrac12 < 0$. Transfer to Gaussians.",
                ),
            },
        },
        "referee": {
            "claim": r"For any integrable random vector $Z \in \mathbb{R}^n$, $\mathbb{E}[\max_a Z_a] = \max_a\mathbb{E}[Z_a]$.",
            "steps": [
                r"For every outcome, $\max_a Z_a \ge Z_b$ for each fixed $b$.",
                r"Taking expectations, $\mathbb{E}[\max_a Z_a] \ge \mathbb{E}[Z_b]$ for each $b$, hence $\mathbb{E}[\max_a Z_a] \ge \max_b\mathbb{E}[Z_b]$.",
                r"Conversely, let $a^\star = \arg\max_a\mathbb{E}[Z_a]$; then $\max_a Z_a = Z_{a^\star}$.",
                r"So $\mathbb{E}[\max_a Z_a] = \mathbb{E}[Z_{a^\star}] = \max_a\mathbb{E}[Z_a]$.",
                r"Combining both directions, $\mathbb{E}[\max_a Z_a] = \max_a\mathbb{E}[Z_a]$.",
            ],
            "flawed_index": 3,
            "violated_keywords": ["random", "depends on the outcome", "argmax changes", "not fixed", "data-dependent", "outcome", "varies", "each draw"],
            "explanation": r"The index attaining $\max_a Z_a$ is random: it depends on the outcome. The deterministic $a^\star = \arg\max_a \mathbb{E}Z_a$ satisfies only $Z_{a^\star} \le \max_a Z_a$, which reproduces the $\ge$ direction and nothing more.",
            "counterexample": r"$Z_1, Z_2$ i.i.d. $\mathcal{N}(0,1)$: $\mathbb{E}\max = 1/\sqrt\pi \approx 0.564 \ne 0 = \max_a\mathbb{E}Z_a$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Zoe, a data scientist who believes zero-mean noise always averages out, even after you pick the best-looking option.",
            "opening": r"If every estimate is unbiased, then the best-looking estimate is unbiased for the best true value — noise averages out. Why would picking the max introduce bias?",
            "boundary_conditions": [
                _bc("direction", r"$\mathbb{E}[\max_a Z_a] \ge \max_a\mathbb{E}[Z_a]$ (convexity of max; pointwise $\max_b Z_b \ge Z_a$)",
                    ["convex", "≥", ">=", "pointwise", "jensen", "at least"],
                    r"Zero-mean noise averages out, so $\mathbb{E}\max = \max\mathbb{E}$, no?"),
                _bc("strictness", r"Strict when the winning index varies with the noise (non-degenerate, not perfectly correlated); equality if one coordinate is a.s. the max",
                    ["strict", "argmax varies", "non-degenerate", "perfectly correlated", "equality when", "same coordinate", "winner changes"],
                    r"If all estimates share exactly the same noise, is there still a gap?"),
                _bc("integrability", r"Requires $\mathbb{E}|Z_a| < \infty$ for each $a$",
                    ["integrable", "finite expectation", "e|z", "finite mean", "finite"],
                    r"Does the inequality even make sense for Cauchy-distributed noise?"),
            ],
        },
        "misconceptions": [
            _mis(["noise averages out", "zero-mean noise cancels", "unbiased max", "max is unbiased"], "FALSE_ANALOGY",
                 "Selection is unbiased", r"\mathbb{E}[\max_a Z_a] = \max_a \mathbb{E}[Z_a]"),
            _mis(["e[min] ≥ min e", "same for min", "min works the same way"], "FALSE_ANALOGY",
                 "Min behaves like max", r"\mathbb{E}[\min_a Z_a] \ge \min_a \mathbb{E}[Z_a]"),
            _mis(["e[max] ≤ max e", "max of expectations is bigger", "jensen goes the other way"], "ALGEBRAIC_SLIP",
                 "Reversed Jensen", r"\mathbb{E}[\max_a Z_a] \le \max_a \mathbb{E}[Z_a]"),
        ],
    },
    "prop_dct_vs_mct": {
        "probe": {
            "prompt": r"Which theorem most directly justifies $\lim_{n\to\infty}\int_0^1 x^n\,dx = \int_0^1 \lim_{n\to\infty} x^n\,dx = 0$?",
            "options": _opts(
                r"Monotone convergence, because $x^n$ is monotone in $n$",
                r"Dominated convergence with envelope $g \equiv 1$ on $[0,1]$",
                r"Neither applies; the limit exchange fails",
                r"Fatou's lemma gives equality here",
            ),
            "correct": "B",
            "explanation": r"$|x^n| \le 1$ and $1$ is integrable on $[0,1]$, and $x^n \to 0$ a.e. MCT needs an *increasing* sequence; $x^n$ decreases. Fatou alone gives only an inequality.",
        },
        "predict": {
            "prompt": r"Predict: $f_n = \mathbf{1}_{[n, n+1]}$ on $\mathbb{R}$ is a unit block sliding to the right. What are $\lim_n\int f_n$ and $\int\lim_n f_n$? What hypothesis would forbid this kind of escape?",
        },
        "reading": r"""**Base case where it works.** $f_n(x) = x^n$ on $[0,1]$: $f_n \to 0$ except at $x = 1$ (measure zero), and $\int f_n = \tfrac1{n+1} \to 0$. The exchange is fine.

**Where it fails.** $g_n = \mathbf{1}_{[n, n+1]}$: $g_n \to 0$ pointwise, yet $\int g_n = 1$ for all $n$. The mass *escapes to infinity*.

**Guarantee 1 (MCT).** If $0 \le f_n \uparrow f$ pointwise, then $\int f_n \uparrow \int f$ (possibly $+\infty$). Increasing nonnegative functions can only gain mass, never lose it.

**Guarantee 2 (DCT).** If $f_n \to f$ a.e. and $|f_n| \le g$ for one $g$ with $\int g < \infty$, then $\int f_n \to \int f$. The fixed integrable envelope traps the mass.

**Contrast.** MCT needs sign and monotonicity, no envelope. DCT needs an envelope, no monotonicity. For $g_n$ the smallest envelope is $\sup_n g_n = \mathbf{1}_{[1,\infty)}$, which is not integrable, and $g_n$ is not increasing, so neither applies.

**Self-explanation:** Why can MCT survive without any integrable envelope while DCT cannot?""",
        "check": {
            "prompt": r"Probability notation: $X_n \to X$ almost surely and $|X_n| \le Y$ for all $n$, with $\mathbb{E}Y < \infty$. Then:",
            "options": _opts(
                r"$\mathbb{E}X_n \to \mathbb{E}X$",
                r"$\mathbb{E}X_n \uparrow \mathbb{E}X$ monotonically",
                r"Only $\liminf_n\mathbb{E}X_n \ge \mathbb{E}X$",
                r"Nothing, unless additionally $X_n \ge 0$",
            ),
            "correct": "A",
            "explanation": r"This is dominated convergence in expectation notation: an integrable envelope $Y$ makes the exchange valid. No monotonicity or sign condition is needed.",
        },
        "productive_failure": {
            "prompt": r"Compute $\lim_{n\to\infty}\int_0^\infty \frac{n\sin(x/n)}{x(1 + x^2)}\,dx$. Before computing anything, decide whether you may move the limit inside, and find a concrete reason that would make the move legitimate.",
            "canonical_insight": r"Pointwise $n\sin(x/n) \to x$, so the integrand $\to \tfrac1{1+x^2}$. Since $|\sin t| \le |t|$, $\big|\tfrac{n\sin(x/n)}{x(1+x^2)}\big| \le \tfrac{1}{1+x^2}$, an integrable envelope independent of $n$. Dominated convergence gives the limit $\int_0^\infty \tfrac{dx}{1+x^2} = \tfrac\pi2$. The hard part is finding $g$.",
        },
        "practice": {
            1: {
                "prompt": r"An annealed importance-weighting scheme multiplies a density $e^{-2x}$ on $[0,\infty)$ by weights $w_n(x) = (1 + x/n)^n$ that sharpen as training proceeds. Find the limit of the total weighted mass $\int_0^\infty e^{-2x}(1 + x/n)^n\,dx$ as $n\to\infty$, and justify the exchange.",
                "answer_summary": r"For $x \ge 0$, $(1 + x/n)^n \uparrow e^x$, so the integrands are nonnegative and increase to $e^{-x}$. Monotone convergence: the limit is $\int_0^\infty e^{-x}\,dx = 1$.",
                "concept_groups": [["= 1", "=1", "is 1", "equals 1", "→ 1", "-> 1", "limit 1", "tends to 1"], ["increas", "monoton", "↑", "nonnegative", "non-negative"], ["e^x", "e^{x}", "exp(x)", "e^{-x}", "e^-x"]],
                "verify_code": r"""import numpy as np
from scipy import integrate
vals = []
for n in [5, 50, 500, 5000]:
    v, _ = integrate.quad(lambda x: np.exp(-2 * x + n * np.log1p(x / n)), 0, np.inf)
    vals.append(v)
assert all(a < b for a, b in zip(vals, vals[1:])) and vals[-1] < 1 and abs(vals[-1] - 1) < 1e-3
xs = np.linspace(0, 30, 500)
assert np.all(np.diff([(1 + xs / n) ** n for n in [1, 2, 4, 8, 16]], axis=0) >= -1e-9)
print('VERIFIED: weighted mass increases to 1:', [round(v, 4) for v in vals])
""",
                "hints": _hints(
                    r"Check the integrand at a fixed $x$ as $n$ grows: does it go up or down, and what is its limit?",
                    r"In “{quote}”, which property of the sequence did you use to justify moving the limit inside?",
                    r"For nonnegative integrands that only increase with $n$, what does the limit of the integrals equal?",
                    r"Fix $x = 1$ and compute $(1 + 1/n)^n$ for $n = 1, 2, 10$. What pattern do you see?",
                    r"Analog: $\int_0^\infty e^{-3x}(1 + x/n)^n dx$: the integrand increases to $e^{-2x}$, so the limit is $\tfrac12$ by monotone convergence. Transfer with $e^{-2x}$.",
                ),
            },
            2: {
                "prompt": r"RL notation: $V_N = \mathbb{E}\big[\sum_{t=0}^N\gamma^t r_t\big]$ with $|r_t| \le r_{\max}$ and $\gamma < 1$; rewards can be negative. Justify $\lim_{N\to\infty}V_N = \mathbb{E}\big[\sum_{t=0}^\infty\gamma^tr_t\big]$, naming the dominating random variable.",
                "answer_summary": r"Partial sums converge pointwise, and $\big|\sum_{t\le N}\gamma^tr_t\big| \le \sum_t\gamma^tr_{\max} = r_{\max}/(1-\gamma)$, a constant (hence integrable) envelope. Dominated convergence applies. Monotone convergence does not, since negative rewards make partial sums non-monotone.",
                "concept_groups": [["r_max/(1-γ)", "r_{\\max}/(1-\\gamma)", "rmax/(1-gamma)", "r_max/(1−γ)", "1/(1-γ)", "1/(1-gamma)", "1/(1−γ)", "r_max/(1-gamma)"], ["dominat", "envelope", "bound", "integrable"], ["negative", "not monoton", "non-monoton", "sign"]],
                "verify_code": r"""import numpy as np
import sympy as sp
t = sp.symbols('t', integer=True, nonnegative=True)
assert sp.summation(sp.Rational(9, 10) ** t, (t, 0, sp.oo)) == 10
rng = np.random.default_rng(17)
gam, R = 0.9, 2.0
r = rng.uniform(-R, R, size=(5000, 400))
disc = gam ** np.arange(400)
partial = np.cumsum(r * disc, axis=1)
assert np.abs(partial).max() <= R / (1 - gam) + 1e-9
assert np.any(np.diff(partial, axis=1) < 0) and np.any(np.diff(partial, axis=1) > 0)
assert np.abs(partial[:, -1] - partial[:, 199]).max() <= R * gam ** 200 / (1 - gam) + 1e-12
print('VERIFIED: |partial sums| <= r_max/(1-gamma); partial sums non-monotone')
""",
                "hints": _hints(
                    r"Bound check: what is the largest possible absolute value of any partial sum, whatever the rewards?",
                    r"In “{quote}”, did you rely on the partial sums increasing? Can they decrease?",
                    r"Which convergence theorem needs a single integrable bound rather than monotonicity?",
                    r"Take $r_t \equiv r_{\max}$ and sum the geometric series. That is your envelope.",
                    r"Analog: $\mathbb{E}[\sum_t 2^{-t}\cos(\theta_t)]$ with random phases: $|\cdot| \le \sum_t 2^{-t} = 2$, so dominated convergence swaps $\lim$ and $\mathbb{E}$. Transfer with $\gamma$ and $r_{\max}$.",
                ),
            },
            3: {
                "prompt": r"Two weight schedules on $[0,\infty)$: (a) $f_n = \mathbf{1}_{[0,n]}e^{-x}$ and (b) $h_n = \tfrac1n\mathbf{1}_{[0,n]}$. Both converge pointwise, and (b) even converges uniformly to $0$. For each, compare $\lim\int$ with $\int\lim$ and identify which convergence theorem (if any) applies.",
                "answer_summary": r"(a) $0 \le f_n \uparrow e^{-x}$: MCT (or DCT with $e^{-x}$) gives $\lim\int f_n = 1 = \int e^{-x}$. (b) $\int h_n = 1$ for all $n$ but $h_n \to 0$ uniformly, so $\int\lim = 0$. It is not monotone, and $\sup_n h_n(x) \approx 1/x$ is not integrable on $[0, \infty)$: no envelope. Uniform convergence does not help on an infinite-measure space.",
                "concept_groups": [["monoton", "mct", "increasing", "↑"], ["no integrable", "not integrable", "1/x", "envelope", "dominat"], ["uniform", "infinite measure", "infinite-measure"]],
                "verify_code": r"""import sympy as sp
x, n = sp.symbols('x n', positive=True)
Ia = sp.integrate(sp.exp(-x), (x, 0, n))
assert sp.limit(Ia, n, sp.oo) == 1
Ib = sp.integrate(1 / n, (x, 0, n))
assert sp.simplify(Ib) == 1
assert sp.integrate(1 / x, (x, 1, sp.oo)) == sp.oo
print('VERIFIED: (a) -> 1 = int e^-x; (b) integrals stay 1, envelope ~1/x not integrable')
""",
                "hints": _hints(
                    r"Compute $\int h_n$ exactly. Does it depend on $n$?",
                    r"In “{quote}”, you used uniform convergence. On what kind of domain does uniform convergence force convergence of integrals?",
                    r"For (b), what is the smallest function that dominates every $h_n$? Is it integrable?",
                    r"Evaluate $\sup_n h_n(x)$ at $x = 1, 2, 10$. What function of $x$ is that?",
                    r"Analog: $k_n = \tfrac1n\mathbf{1}_{[0,n^2]}$ converges uniformly to $0$ but $\int k_n = n \to \infty$. On infinite measure, height going to zero does not control area. Classify (a) and (b) with that lens.",
                ),
            },
            4: {
                "prompt": r"A teammate argues: '$f_n(x) = n^2x\,e^{-nx}$ on $[0,\infty)$ converges to $0$ pointwise, and for large $x$ every $f_n$ decays exponentially, so the tails are under control and we may pass the limit inside: $\int f_n \to 0$.' Check the conclusion and locate the gap.",
                "answer_summary": r"$\int_0^\infty n^2xe^{-nx}\,dx = n^2\cdot\tfrac1{n^2} = 1$ for all $n$, so $\lim\int = 1 \ne 0$. Decay at infinity is irrelevant: the envelope $\sup_n f_n(x) = 4e^{-2}/x$ (at $n = 2/x$) is not integrable near $0$. The mass concentrates as a spike at the origin.",
                "concept_groups": [["= 1", "=1", "is 1", "equals 1", "stays 1", "always 1"], ["1/x", "not integrable", "no integrable", "sup", "envelope", "near 0", "near zero", "spike"]],
                "verify_code": r"""import sympy as sp
x, n = sp.symbols('x n', positive=True)
f = n**2 * x * sp.exp(-n * x)
assert sp.simplify(sp.integrate(f, (x, 0, sp.oo))) == 1
nstar = sp.solve(sp.diff(f, n), n)
env = sp.simplify(f.subs(n, nstar[0]))
assert sp.simplify(env - 4 * sp.exp(-2) / x) == 0
assert sp.integrate(env, (x, 0, 1)) == sp.oo
print('VERIFIED: integral = 1 for all n; envelope 4e^-2/x not integrable at 0')
""",
                "hints": _hints(
                    r"Before arguing, compute $\int f_n$ for $n = 1$ and $n = 10$.",
                    r"In “{quote}”, you checked the tail. Where else could an envelope fail to be integrable?",
                    r"Dominated convergence needs one integrable $g$ above every $f_n$ simultaneously. What is $\sup_n f_n(x)$ for small $x$?",
                    r"Maximize $n^2xe^{-nx}$ over $n$ for fixed $x$ (set the $n$-derivative to zero).",
                    r"Analog: $f_n = n\,\mathbf{1}_{(0,1/n)}$ decays to $0$ everywhere and is zero for $x \ge 1$, yet $\int f_n = 1$: its envelope behaves like $1/x$ at the origin. Find the analogous envelope here.",
                ),
            },
        },
        "referee": {
            "claim": r"$\lim_{n\to\infty}\int_0^\infty \frac{n}{1 + n^2x^2}\,dx = 0$.",
            "steps": [
                r"For each $x > 0$, $\frac{n}{1+n^2x^2} \le \frac{n}{n^2x^2} = \frac1{nx^2} \to 0$, so $f_n \to 0$ almost everywhere.",
                r"Each $f_n$ is continuous, positive, and integrable on $(0,\infty)$.",
                r"For $x \ge 1$, $f_n(x) \le \frac{1}{nx^2} \le \frac1{x^2}$, which is integrable on $[1,\infty)$.",
                r"So the $f_n$ are dominated by an integrable function, and the Dominated Convergence Theorem lets us pass the limit inside.",
                r"Therefore $\lim_n\int_0^\infty f_n = \int_0^\infty 0\,dx = 0$.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["near 0", "near zero", "(0,1)", "only on [1", "1/(2x)", "1/x", "whole domain", "not integrable", "entire domain"],
            "explanation": r"Domination was shown only on $[1,\infty)$. On $(0,1)$ the envelope $\sup_n f_n(x) = \frac{1}{2x}$ (attained at $n = 1/x$) is not integrable, so DCT does not apply on the whole domain.",
            "counterexample": r"$\int_0^\infty\frac{n}{1+n^2x^2}dx = \big[\arctan(nx)\big]_0^\infty = \frac\pi2$ for every $n$, so the limit is $\frac\pi2 \ne 0$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Kai, an applied-math student who thinks pointwise convergence plus 'nice-looking' functions is enough to swap limits and integrals.",
            "opening": r"If $f_n \to f$ at every point, the areas under $f_n$ must approach the area under $f$ — the graphs are getting closer everywhere! Why do we need DCT and MCT at all?",
            "boundary_conditions": [
                _bc("dct_envelope", r"DCT: one integrable $g$ with $|f_n| \le g$ for all $n$ (the same $g$)",
                    ["integrable", "dominat", "envelope", "same g", "single g", "l^1", "l1"],
                    r"$n\mathbf{1}_{(0,1/n)} \to 0$ pointwise — why doesn't its integral go to $0$?"),
                _bc("mct_conditions", r"MCT: $f_n \ge 0$ and increasing in $n$; the limit integral may be $+\infty$",
                    ["nonnegative", "non-negative", "increasing", "monoton", "↑"],
                    r"$\mathbf{1}_{[n,\infty)}$ decreases to $0$ — does monotone convergence give $\int \to 0$?"),
                _bc("measure_space", r"Pointwise / uniform convergence alone is not enough, especially on infinite-measure spaces",
                    ["uniform", "infinite measure", "infinite-measure", "almost everywhere", "a.e.", "escape"],
                    r"$\tfrac1n\mathbf{1}_{[0,n]} \to 0$ uniformly — surely that's enough?"),
            ],
        },
        "misconceptions": [
            _mis(["pointwise convergence so the integrals converge", "converges pointwise so", "graphs get closer so the areas"], "BOUNDARY_OMISSION",
                 "Pointwise convergence suffices", r"f_n \to f \text{ pointwise} \implies \int f_n \to \int f"),
            _mis(["bounded by a constant on [0,∞)", "dominated by 1 on the real line", "bounded so dct"], "BOUNDARY_OMISSION",
                 "Constant envelope on infinite measure", r"|f_n| \le C \text{ on } [0,\infty) \implies \int f_n \to \int f"),
            _mis(["monotone decreasing so mct", "decreasing so mct", "mct for decreasing"], "FALSE_ANALOGY",
                 "MCT for decreasing sequences", r"f_n \downarrow f \implies \int f_n \to \int f"),
        ],
    },
    "cnt_unbounded_indicator_escape": {
        "probe": {
            "prompt": r"Let $f_n = n\cdot\mathbf{1}_{(0, 1/n)}$ on $(0, 1)$ with Lebesgue measure. What are $\lim_n\int f_n\,d\lambda$ and $\int\lim_n f_n\,d\lambda$?",
            "options": _opts(r"$0$ and $0$", r"$1$ and $1$", r"$1$ and $0$", r"$\infty$ and $0$"),
            "correct": "C",
            "explanation": r"Each $\int f_n = n\cdot\tfrac1n = 1$. For fixed $x \in (0,1)$, $f_n(x) = 0$ once $n > 1/x$, so the pointwise limit is $0$ and $\int\lim f_n = 0$. The exchange fails.",
        },
        "predict": {
            "prompt": r"Predict: picture spikes of height $n$ and width $1/n$ squeezed against $x = 0$. As $n\to\infty$, where does the area go? What does the pointwise limit 'see' at each fixed point?",
        },
        "reading": r"""**Compute the integrals.** $\int_0^1 f_n = n\cdot\tfrac1n = 1$ for every $n$.

**Compute the pointwise limit.** Fix $x \in (0,1)$. As soon as $n > 1/x$, $x \notin (0, 1/n)$, so $f_n(x) = 0$. Hence $\lim_n f_n(x) = 0$ everywhere on $(0,1)$ and $\int\lim f_n = 0 \ne 1$.

**Which guarantee failed?**
- *Monotone?* No: at fixed $x$, $f_n(x)$ climbs to about $1/x$, then drops to $0$.
- *Dominated?* Any $g$ with $g \ge f_n$ for all $n$ must satisfy $g(x) \ge \sup_n f_n(x) \ge \tfrac1x - 1$, and $\int_0^1 \big(\tfrac1x - 1\big)dx = \infty$. No integrable envelope exists.

**Where the mass goes.** It concentrates into a spike at $0$: $\int f_n\varphi \to \varphi(0)$ for continuous $\varphi$ (convergence to a Dirac mass), invisible to pointwise limits.

**What survives.** Fatou's inequality $\int\liminf f_n \le \liminf\int f_n$ holds ($0 \le 1$), strictly.

**Self-explanation:** Why can no integrable $g$ dominate every $f_n$, even one that blows up at $0$?""",
        "check": {
            "prompt": r"Let $U \sim \mathrm{Unif}(0,1)$ and $X_n = n\,\mathbf{1}\{U < 1/n\}$. Which statement is true?",
            "options": _opts(
                r"$X_n \to 0$ a.s. and $\mathbb{E}X_n \to 0$",
                r"$X_n \to 0$ a.s. but $\mathbb{E}X_n = 1$ for all $n$",
                r"$X_n \to \infty$ a.s.",
                r"$\mathbb{E}X_n \to 0$ but $X_n$ does not converge a.s.",
            ),
            "correct": "B",
            "explanation": r"This is the same spike in probability language: for each $U > 0$, eventually $1/n < U$, so $X_n \to 0$ a.s.; but $\mathbb{E}X_n = n\cdot P(U < 1/n) = 1$.",
        },
        "productive_failure": {
            "prompt": r"Construct a sequence of **continuous**, nonnegative functions on $[0,1]$ that converge pointwise to $0$ but whose integrals tend to $+\infty$. Then state the weakest single condition you know of that would have ruled your example out.",
            "canonical_insight": r"Tent functions $f_n$ with peak $n^2$ at $x = 1/n$ and support $[\tfrac1{2n}, \tfrac{3}{2n}]$ go to $0$ pointwise (and $f_n(0) = 0$), with $\int f_n = \tfrac{n^2}{2}\cdot\tfrac1n = \tfrac n2 \to \infty$. Domination by an integrable $g$ (or, more weakly, uniform integrability) rules this out; Fatou only guarantees $\int\lim \le \liminf\int$.",
        },
        "practice": {
            1: {
                "prompt": r"A warmup schedule injects learning-rate 'budget' $\eta_n(t) = n\cdot\mathbf{1}\{0 < t < 1/n\}$ (time in epochs). As you tune $n$ upward, the spike gets shorter and taller. What is the total budget $\int_0^1\eta_n\,dt$ for each $n$, what schedule does $\eta_n$ approach pointwise, and can you swap limit and integral?",
                "answer_summary": r"Total budget is $1$ for every $n$. Pointwise $\eta_n(t) \to 0$ for every $t > 0$. No swap: $\int\lim = 0 \ne 1 = \lim\int$, because $\sup_n \eta_n(t) \approx 1/t$ is not integrable, so no integrable envelope exists.",
                "concept_groups": [["= 1", "=1", "always 1", "equals 1", "is 1", "budget 1", "integral 1", "total of 1"], ["pointwise 0", "limit 0", "limit is 0", "→ 0", "-> 0", "goes to 0", "to zero", "zero"], ["dominat", "envelope", "integrable", "1/t", "1/x"]],
                "verify_code": r"""import sympy as sp
t, n = sp.symbols('t n', positive=True)
assert sp.integrate(n, (t, 0, 1 / n)) == 1
assert sp.integrate(1 / t - 1, (t, 0, 1)) == sp.oo
eta = lambda nn, tt: nn if 0 < tt < 1 / nn else 0
assert all(eta(nn, 0.01) == 0 for nn in range(101, 1000))
print('VERIFIED: budget 1 for all n, pointwise limit 0, envelope ~1/t not integrable')
""",
                "hints": _hints(
                    r"Area check: height times width. What is it for $n = 10$? For $n = 1000$?",
                    r"In “{quote}”, did you compute the limit of the areas or the area of the limit?",
                    r"Pick a fixed time $t = 0.01$. What is $\eta_n(0.01)$ once $n$ is large?",
                    r"Draw $\eta_1, \eta_2, \eta_4$ and compute each area by hand.",
                    r"Analog: a hammer blow delivering impulse $1$ over $1/n$ seconds has force $n$; as $n\to\infty$ the force is $0$ at every $t > 0$ but the impulse stays $1$. Transfer to the LR budget.",
                ),
            },
            2: {
                "prompt": r"Physics notation: 'nascent delta' densities $\rho_\epsilon(x) = \epsilon^{-1}\mathbf{1}_{(0,\epsilon)}(x)$. For the test function $\varphi(x) = \cos x$, compute $\lim_{\epsilon\to0}\int\rho_\epsilon\varphi\,dx$ and $\int\big(\lim_{\epsilon\to0}\rho_\epsilon\big)\varphi\,dx$.",
                "answer_summary": r"$\int\rho_\epsilon\varphi = \tfrac{\sin\epsilon}{\epsilon} \to 1 = \varphi(0)$. Pointwise $\rho_\epsilon(x) \to 0$ for every $x \ne 0$, so $\int(\lim\rho_\epsilon)\varphi = 0$. The mass concentrates into a spike at $0$ with no integrable envelope.",
                "concept_groups": [["φ(0)", "phi(0)", "cos(0)", "cos 0", "= 1", "→ 1", "-> 1", "sin(ε)/ε", "sin ε/ε"], ["pointwise", "zero pointwise", "→ 0", "-> 0", "limit is 0", "= 0"], ["dominat", "envelope", "spike", "concentrat", "delta", "dirac"]],
                "verify_code": r"""import sympy as sp
x, e = sp.symbols('x epsilon', positive=True)
I = sp.integrate(sp.cos(x) / e, (x, 0, e))
assert sp.simplify(I - sp.sin(e) / e) == 0
assert sp.limit(I, e, 0) == 1
print('VERIFIED: int rho_eps cos -> 1 = phi(0), while pointwise limit integrates to 0')
""",
                "hints": _hints(
                    r"Total-mass check: what is $\int\rho_\epsilon\,dx$ for every $\epsilon$?",
                    r"In “{quote}”, did you take the limit of the function first or of the integral first?",
                    r"An average of a continuous function over a shrinking interval near $0$ approaches what?",
                    r"Use $\varphi \equiv 1$ first: compute both quantities.",
                    r"Analog: $\int n\mathbf{1}_{(0,1/n)}(x)\,e^x dx = n(e^{1/n} - 1) \to 1 = e^0$, while the pointwise limit integrates to $0$. Transfer to $\cos$.",
                ),
            },
            3: {
                "prompt": r"Compare two spike families on $(0,1)$: $g_n = n\,\mathbf{1}_{(0,1/n)}$ and $h_n = \sqrt n\,\mathbf{1}_{(0,1/n)}$. For each, give the pointwise limit, $\lim_n\int$, and decide whether an integrable dominating function exists.",
                "answer_summary": r"Both $\to 0$ pointwise. $\int g_n = 1$ but $\int h_n = 1/\sqrt n \to 0$, so the exchange works for $h_n$. Envelopes: $\sup_n h_n(x) \lesssim x^{-1/2}$, integrable on $(0,1)$ (DCT applies); $\sup_n g_n(x) \approx 1/x$, not integrable (DCT fails, and indeed the exchange fails).",
                "concept_groups": [["1/√n", "1/sqrt(n)", "n^{-1/2}", "n^(-1/2)"], ["x^{-1/2}", "1/√x", "1/sqrt(x)", "x^(-1/2)"], ["1/x", "not integrable", "no dominat", "no integrable"]],
                "verify_code": r"""import sympy as sp
x, n = sp.symbols('x n', positive=True)
assert sp.integrate(sp.sqrt(n), (x, 0, 1 / n)) == 1 / sp.sqrt(n)
assert sp.integrate(n, (x, 0, 1 / n)) == 1
assert sp.integrate(1 / sp.sqrt(x), (x, 0, 1)) == 2
assert sp.integrate(1 / x, (x, 0, 1)) == sp.oo
print('VERIFIED: int h_n = n^-1/2 -> 0 with integrable envelope x^-1/2; g_n envelope 1/x not integrable')
""",
                "hints": _hints(
                    r"Compute both areas as height × width before anything else.",
                    r"In “{quote}”, which envelope did you propose, and did you check its integral near 0?",
                    r"The smallest possible dominating function is the pointwise supremum over $n$. What is it for each family at a point $x$?",
                    r"At $x = 0.01$, which $n$ maximize $g_n(x)$ and $h_n(x)$, and what are the maxima?",
                    r"Analog: $k_n = n^{1/3}\mathbf{1}_{(0,1/n)}$ has envelope $\approx x^{-1/3}$ (integrable) and $\int k_n = n^{-2/3} \to 0$. Do the same for exponents $1/2$ and $1$.",
                ),
            },
            4: {
                "prompt": r"A colleague says: 'The general inequality $\int\liminf f_n \le \liminf\int f_n$ gives $0 \le 1$ for $f_n = n\mathbf{1}_{(0,1/n)}$. Both sides are limits, so really they must be equal. And the same reasoning applied to $-f_n$ is fine.' Identify both errors.",
                "answer_summary": r"Fatou is only an inequality and can be strict: here $0 < 1$. And Fatou requires $f_n \ge 0$ (or a common integrable lower bound). For $-f_n$ it would claim $\int\liminf(-f_n) = 0 \le \liminf\int(-f_n) = -1$, which is false.",
                "concept_groups": [["strict", "0 < 1", "not equal", "inequality only", "can be strict", "only an inequality"], ["nonnegative", "non-negative", "≥ 0", ">= 0", "bounded below", "lower bound"], ["-1", "−1"]],
                "verify_code": r"""import sympy as sp
x, n = sp.symbols('x n', positive=True)
lhs_pos, rhs_pos = 0, sp.integrate(n, (x, 0, 1 / n))
assert lhs_pos < rhs_pos == 1
lhs_neg, rhs_neg = 0, sp.integrate(-n, (x, 0, 1 / n))
assert rhs_neg == -1 and not (lhs_neg <= rhs_neg)
print('VERIFIED: Fatou strict (0 < 1) for f_n; fails (0 <= -1 false) for -f_n')
""",
                "hints": _hints(
                    r"Sign check: are the $-f_n$ nonnegative? Which hypothesis of Fatou's lemma is that?",
                    r"In “{quote}”, what licenses turning an inequality into an equality?",
                    r"What extra hypothesis upgrades Fatou's inequality to the equality $\lim\int = \int\lim$?",
                    r"Write out both sides of Fatou for $-f_n$ explicitly.",
                    r"Analog: $f_n = \mathbf{1}_{[n,n+1]}$ satisfies Fatou strictly ($0 < 1$); $-f_n$ would give $0 \le -1$, false, because $-f_n$ is not bounded below by an integrable function. Transfer.",
                ),
            },
        },
        "referee": {
            "claim": r"For $f_n = n\,\mathbf{1}_{(0,1/n)}$ on $(0,1)$, $\lim_n\int_0^1 f_n\,d\lambda = 0$.",
            "steps": [
                r"Fix $x \in (0,1)$. For $n > 1/x$ we have $x \ge 1/n$, so $f_n(x) = 0$; thus $f_n \to 0$ pointwise.",
                r"Each $f_n$ is bounded (by $n$) and supported in $(0,1)$, so each $f_n$ is integrable.",
                r"Every $f_n$ is bounded and so is the limit, so the family is dominated by a bounded, hence integrable, function on $(0,1)$.",
                r"By the Dominated Convergence Theorem, $\int f_n \to \int\lim f_n$.",
                r"Since $\lim f_n = 0$, we conclude $\lim\int f_n = 0$.",
            ],
            "flawed_index": 3,
            "violated_keywords": ["depends on n", "uniform bound", "single", "same g", "1/x", "not integrable", "sup_n", "no common bound"],
            "explanation": r"Each $f_n$ is bounded, but by $n$, a bound that grows with $n$. Domination requires one $g$ for all $n$; the smallest candidate $\sup_n f_n(x) \approx 1/x$ is not integrable.",
            "counterexample": r"$\int_0^1 f_n = 1$ for every $n$, so $\lim\int f_n = 1 \ne 0$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Riley, who believes that if every point eventually sees the value $0$, the area must eventually be $0$ too.",
            "opening": r"At every $x$, $n\mathbf{1}_{(0,1/n)}(x)$ is eventually $0$. So the area under it must go to $0$. How could the integral possibly stay at $1$?",
            "boundary_conditions": [
                _bc("area_stays_one", r"Exhibit the integrals: $\int f_n = n\cdot\tfrac1n = 1$ for all $n$ while $f_n \to 0$ pointwise",
                    ["= 1", "always 1", "area 1", "integral 1", "n · 1/n", "n*(1/n)", "n/n", "height times width"],
                    r"But every point eventually sees $0$ — how can the area stay $1$?"),
                _bc("no_envelope", r"No integrable envelope: $\sup_n f_n(x) \approx 1/x$, not integrable near $0$",
                    ["1/x", "envelope", "dominat", "not integrable", "sup"],
                    r"Each $f_n$ is bounded — isn't the family dominated, so DCT applies?"),
                _bc("fatou_only", r"Only Fatou's inequality $\int\liminf f_n \le \liminf\int f_n$ survives for $f_n \ge 0$; mass concentrates into a spike (Dirac mass) at $0$",
                    ["fatou", "inequality", "spike", "delta", "dirac", "concentrat", "escape"],
                    r"So is there nothing true about $\int\lim$ versus $\lim\int$ here?"),
            ],
        },
        "misconceptions": [
            _mis(["each f_n is bounded so dominated", "bounded functions are dominated", "bounded by n so dct"], "BOUNDARY_OMISSION",
                 "n-dependent bound as domination", r"|f_n| \le n\ \forall n \implies \text{DCT applies}"),
            _mis(["pointwise to 0 so integral to 0", "converges to zero so the area", "eventually zero so the integral"], "FALSE_ANALOGY",
                 "Pointwise zero forces zero area", r"f_n \to 0 \text{ pointwise} \implies \int f_n \to 0"),
            _mis(["fatou gives equality", "fatou says equal", "both sides are limits so equal"], "BOUNDARY_OMISSION",
                 "Fatou as an equality", r"\int\liminf f_n = \liminf\int f_n"),
        ],
    },
    "bug_uncorrelated_implies_indep": {
        "probe": {
            "prompt": r"Let $X\sim\mathcal{N}(0,1)$ and $Y = X^2$. Which statement is true?",
            "options": _opts(
                r"$\mathrm{Cov}(X,Y) = 0$ and $X, Y$ are independent",
                r"$\mathrm{Cov}(X,Y) = 0$ but $X, Y$ are dependent",
                r"$\mathrm{Cov}(X,Y) \ne 0$ and $X, Y$ are dependent",
                r"$\mathrm{Cov}(X,Y) \ne 0$ but $X, Y$ are independent",
            ),
            "correct": "B",
            "explanation": r"$\mathrm{Cov}(X, X^2) = \mathbb{E}X^3 - \mathbb{E}X\,\mathbb{E}X^2 = 0$ by symmetry, yet $Y$ is a deterministic function of $X$: e.g. $P(Y > 1 \mid |X| < 1) = 0 \ne P(Y > 1)$.",
        },
        "predict": {
            "prompt": r"Predict: if knowing $X$ tells you $Y$ exactly, can $\mathrm{Cov}(X, Y)$ still be $0$? Sketch a scatter plot that would make this happen before reading.",
        },
        "reading": r"""**Base case.** $X$ uniform on $\{-1, 0, 1\}$, $Y = X^2$. Knowing $X = 0$ forces $Y = 0$: dependent. Yet
$$\mathrm{Cov}(X,Y) = \mathbb{E}[X^3] - \mathbb{E}X\,\mathbb{E}X^2 = 0 - 0 = 0.$$

**Why.** Covariance measures only the best *linear* trend. The parabola's left and right arms pull the slope equally in opposite directions, so the fitted line is flat.

**What independence demands.** $X \perp\!\!\!\perp Y$ means $P(X\in A, Y\in B) = P(X\in A)P(Y\in B)$ for all $A, B$; equivalently $\mathbb{E}[f(X)g(Y)] = \mathbb{E}f(X)\,\mathbb{E}g(Y)$ for all bounded $f, g$. Covariance tests a single pair, $f(x) = x$, $g(y) = y$.

**Valid direction.** Independence with finite variances implies $\mathrm{Cov} = 0$. The converse holds for *jointly* Gaussian vectors, not merely Gaussian marginals.

**Same story continuously.** $X\sim\mathcal{N}(0,1)$, $Y = X^2$: $\mathrm{Cov} = \mathbb{E}X^3 = 0$.

**Self-explanation:** In the parabola example, which choice of $f$ and $g$ exposes the dependence?""",
        "check": {
            "prompt": r"Signal processing: $\theta\sim\mathrm{Unif}[0, 2\pi)$, $s = \cos\theta$, $c = \sin\theta$. Which is true?",
            "options": _opts(
                r"$s, c$ are uncorrelated and independent",
                r"$s, c$ are uncorrelated but dependent",
                r"$s, c$ are correlated",
                r"$s, c$ are independent but correlated",
            ),
            "correct": "B",
            "explanation": r"$\mathbb{E}[sc] = \tfrac12\mathbb{E}\sin 2\theta = 0$ and both means are $0$, so they are uncorrelated. But $s^2 + c^2 = 1$: knowing $s$ pins $|c|$, so they are dependent.",
        },
        "productive_failure": {
            "prompt": r"Construct a pair $(X, Y)$ such that $X$ and $Y$ are each exactly $\mathcal{N}(0,1)$, $\mathrm{Cov}(X,Y) = 0$, and yet $X, Y$ are **not** independent. Prove all three properties.",
            "canonical_insight": r"Let $W = \pm1$ be a fair sign independent of $X\sim\mathcal{N}(0,1)$ and $Y = WX$. By symmetry $Y\sim\mathcal{N}(0,1)$; $\mathrm{Cov}(X,Y) = \mathbb{E}W\,\mathbb{E}X^2 = 0$; but $|Y| = |X|$, so they are dependent ($\mathbb{E}[X^2Y^2] = 3 \ne 1$). $(X,Y)$ is not jointly Gaussian: $X + Y = 0$ with probability $\tfrac12$.",
        },
        "practice": {
            1: {
                "prompt": r"Your feature-selection pipeline drops any feature whose covariance with the target is near zero. On a large dataset it drops feature $Z$ (symmetric around $0$), while the target is $T = Z^2 + \text{small noise}$. Was dropping $Z$ justified? What should the screen have measured instead?",
                "answer_summary": r"Not justified: $\mathrm{Cov}(Z, T) \approx \mathbb{E}Z^3 = 0$ by symmetry, but $T$ depends strongly on $Z$ through a nonlinear (quadratic) relation. Covariance detects only linear dependence; use a nonlinear dependence measure (e.g. mutual information, or correlation of $T$ with $Z^2$).",
                "concept_groups": [["not justified", "shouldn't", "should not", "don't drop", "do not drop", "keep", "mistake", "wrong", "unjustified"], ["nonlinear", "non-linear", "quadratic", "z^2", "z²", "squared"], ["linear", "mutual information"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(18)
Z = rng.normal(size=10**6)
T = Z**2 + 0.1 * rng.normal(size=10**6)
assert abs(np.corrcoef(Z, T)[0, 1]) < 0.01
assert np.corrcoef(Z**2, T)[0, 1] > 0.99
print('VERIFIED: corr(Z, T) ~ 0 but corr(Z^2, T) > 0.99')
""",
                "hints": _hints(
                    r"Check the sign structure: for $Z = 2$ and $Z = -2$, what is $T$? What slope would a line through those points have?",
                    r"In “{quote}”, which kind of relationship does covariance actually measure?",
                    r"What does it mean for two variables to be independent, as opposed to merely having zero linear trend?",
                    r"Take $Z$ uniform on $\{-1, 0, 1\}$ and $T = Z^2$ exactly. Compute $\mathrm{Cov}(Z, T)$ and $P(T = 0 \mid Z = 0)$.",
                    r"Analog: wind speed $W$ symmetric around $0$ (direction-signed) and turbine power $\propto W^2$: zero covariance, yet power is completely determined by $W$. Transfer to the feature screen.",
                ),
            },
            2: {
                "prompt": r"Kernel-methods notation: for $X\sim\mathrm{Unif}[-1,1]$ and $Y = |X|$, the linear cross-covariance $\Sigma_{XY} = \mathbb{E}[(X - \mu_X)(Y - \mu_Y)]$ vanishes. Compute $\mathbb{E}[\phi(X)\psi(Y)] - \mathbb{E}\phi(X)\,\mathbb{E}\psi(Y)$ for $\phi(x) = x^2$, $\psi(y) = y$, and interpret.",
                "answer_summary": r"$\mathbb{E}[X^2|X|] = \mathbb{E}|X|^3 = \tfrac14$, $\mathbb{E}X^2 = \tfrac13$, $\mathbb{E}|X| = \tfrac12$, so the nonlinear covariance is $\tfrac14 - \tfrac16 = \tfrac1{12} \ne 0$: $X$ and $Y$ are dependent even though $\Sigma_{XY} = 0$.",
                "concept_groups": [["1/12", "0.0833", "0.083"], ["dependent", "not independent", "dependence"]],
                "verify_code": r"""import sympy as sp
x = sp.symbols('x', real=True)
E = lambda f: sp.integrate(f / 2, (x, -1, 1))
assert sp.simplify(E(x * sp.Abs(x)) - E(x) * E(sp.Abs(x))) == 0
val = E(x**2 * sp.Abs(x)) - E(x**2) * E(sp.Abs(x))
assert sp.simplify(val - sp.Rational(1, 12)) == 0
print('VERIFIED: linear cov 0, nonlinear cov 1/12')
""",
                "hints": _hints(
                    r"Range check: $X^2$ and $|X|$ both lie in $[0,1]$ and move together. Should their covariance be positive, negative, or zero?",
                    r"In “{quote}”, did you compute the expectation of the product, or the product of expectations?",
                    r"Independence would force this quantity to vanish for every pair of functions. What does one nonzero value tell you?",
                    r"Compute $\mathbb{E}|X|^3$ for $X\sim\mathrm{Unif}[-1,1]$ using symmetry: it equals $\int_0^1 x^3dx$.",
                    r"Analog: $\phi(x) = |x|$, $\psi(y) = y$ gives $\mathbb{E}X^2 - (\mathbb{E}|X|)^2 = \tfrac13 - \tfrac14 = \tfrac1{12}$ too. Do the same bookkeeping for $\phi(x) = x^2$.",
                ),
            },
            3: {
                "prompt": r"Two pairs, each with $\mathcal{N}(0,1)$ marginals and covariance $0$: (a) $(X, Y)$ jointly Gaussian; (b) $X\sim\mathcal{N}(0,1)$, $Y = WX$ with $W$ an independent fair random sign. Which pair is independent, and give one computable statistic that separates them.",
                "answer_summary": r"(a) is independent: a jointly Gaussian vector with identity covariance has a factorizing density. (b) is dependent: $|Y| = |X|$, so $\mathbb{E}[X^2Y^2] = \mathbb{E}X^4 = 3$ versus $1$ in (a); also $X + Y = 0$ with probability $\tfrac12$, so (b) is not jointly Gaussian.",
                "concept_groups": [["jointly gaussian", "joint gaussian", "multivariate normal", "bivariate normal", "jointly normal"], ["|x| = |y|", "|x|=|y|", "x+y", "x + y", "e[x^2y^2]", "e[x²y²]", "same magnitude", "= 3"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(19)
N = 10**6
Xa, Ya = rng.normal(size=N), rng.normal(size=N)
X = rng.normal(size=N); W = rng.choice([-1.0, 1.0], size=N); Y = W * X
assert abs(np.mean(X * Y)) < 0.01 and abs(Y.std() - 1) < 0.01
assert abs(np.mean(Xa**2 * Ya**2) - 1) < 0.05 and abs(np.mean(X**2 * Y**2) - 3) < 0.1
assert abs(np.mean(X + Y == 0) - 0.5) < 0.01
print('VERIFIED: E[X^2Y^2] = 1 (joint Gaussian) vs 3 (random sign); P(X+Y=0) = 1/2')
""",
                "hints": _hints(
                    r"Which of the two pairs can ever have $|X| \ne |Y|$?",
                    r"In “{quote}”, did you assume that Gaussian marginals make the pair jointly Gaussian?",
                    r"Covariance only tests $f(x) = x$, $g(y) = y$. Try squares instead.",
                    r"For (b), compute the distribution of $X + Y$: what happens when $W = -1$?",
                    r"Analog: $X\sim\mathrm{Unif}[-1,1]$, $Y = WX$: uniform marginals, zero covariance, but $|X| = |Y|$. Transfer the 'magnitude' test to the Gaussian case.",
                ),
            },
            4: {
                "prompt": r"An analyst claims: 'For any two random variables, $\mathrm{Cov}(X,Y) = 0$ means the regression of $Y$ on $X$ is flat, so $\mathbb{E}[Y\mid X] = \mathbb{E}[Y]$.' Test this with $X\sim\mathcal{N}(0,1)$ and $Y = X^2$, and state which direction of implication is actually true.",
                "answer_summary": r"Zero covariance only makes the best *linear* predictor flat. Here $\mathrm{Cov} = 0$ but $\mathbb{E}[Y\mid X] = X^2$, which is not constant. The true direction: mean independence $\mathbb{E}[Y\mid X] = \mathbb{E}Y$ implies $\mathrm{Cov}(X,Y) = 0$, not conversely.",
                "concept_groups": [["linear", "best linear", "slope"], ["x^2", "x²", "nonlinear", "conditional mean", "e[y|x] = x"], ["mean independen", "converse", "other direction", "one direction", "one-way", "only implies"]],
                "verify_code": r"""import sympy as sp
from sympy.stats import Normal, E, covariance
X = Normal('X', 0, 1)
assert sp.simplify(covariance(X, X**2)) == 0
x = sp.symbols('x', real=True)
cond_mean = x**2
assert sp.diff(cond_mean, x) != 0
assert sp.simplify(E(X**2)) == 1
print('VERIFIED: Cov(X, X^2) = 0 while E[Y|X] = X^2 is not constant')
""",
                "hints": _hints(
                    r"Compute $\mathbb{E}[Y\mid X = 2]$ and $\mathbb{E}[Y\mid X = 0]$. Are they equal?",
                    r"In “{quote}”, which regression did you have in mind — the best straight line, or the true conditional mean?",
                    r"Covariance is tied to the slope of the least-squares line. What does that line ignore?",
                    r"Use $X$ uniform on $\{-1, 0, 1\}$, $Y = X^2$: list $\mathbb{E}[Y\mid X]$ at each value.",
                    r"Analog: $Y = |X|$ with $X$ symmetric: least-squares slope $0$, conditional mean $|x|$, a V shape. Transfer to $X^2$, and check which implication survives.",
                ),
            },
        },
        "referee": {
            "claim": r"If $X\sim\mathcal{N}(0,1)$, $Y\sim\mathcal{N}(0,1)$ and $\mathrm{Cov}(X, Y) = 0$, then $X \perp\!\!\!\perp Y$.",
            "steps": [
                r"$X$ and $Y$ each have the standard normal density $\phi(t) = e^{-t^2/2}/\sqrt{2\pi}$.",
                r"A pair of Gaussian random variables forms a bivariate Gaussian vector with covariance matrix $\begin{pmatrix}1 & \rho\\ \rho & 1\end{pmatrix}$.",
                r"Here $\rho = \mathrm{Cov}(X, Y) = 0$, so the covariance matrix is $I$.",
                r"The bivariate Gaussian density with covariance $I$ factorizes: $p(x, y) = \phi(x)\phi(y)$.",
                r"A factorizing joint density means $X \perp\!\!\!\perp Y$.",
            ],
            "flawed_index": 2,
            "violated_keywords": ["jointly", "joint", "marginal", "bivariate", "not necessarily", "random sign"],
            "explanation": r"Gaussian marginals do not make the pair jointly Gaussian. Only for a jointly Gaussian vector does zero covariance imply independence.",
            "counterexample": r"$X\sim\mathcal{N}(0,1)$, $Y = WX$ with an independent fair sign $W$: both marginals are $\mathcal{N}(0,1)$, $\mathrm{Cov} = 0$, but $|X| = |Y|$ (dependent), and $X + Y = 0$ with probability $\tfrac12$.",
        },
        "feynman": {
            "buggy_rule_id": "bug_uncorrelated_implies_indep",
            "persona": "Casey, an analyst who reads 'correlation 0.00' on a dashboard as 'these two variables have nothing to do with each other'.",
            "opening": r"The correlation between $X$ and $Y$ is exactly zero, so they're independent — there's no relationship to model. Can you explain why my stats professor says that's wrong?",
            "boundary_conditions": [
                _bc("linear_only", r"Covariance detects only linear dependence; independence requires $\mathbb{E}[f(X)g(Y)] = \mathbb{E}f(X)\,\mathbb{E}g(Y)$ for all $f, g$ (joint law = product of marginals)",
                    ["linear", "all functions", "every f", "joint distribution", "factor", "product of marginals"],
                    r"Zero correlation means a flat scatter plot trend — so no relationship, right?"),
                _bc("parabola_counterexample", r"Counterexample: symmetric $X$ and $Y = X^2$ have $\mathrm{Cov} = \mathbb{E}X^3 = 0$ but $Y$ is a function of $X$",
                    ["x^2", "x²", "y = x", "symmetric", "parabola", "cos", "circle"],
                    r"Give me one concrete pair where $Y$ is literally determined by $X$ but the covariance is $0$."),
                _bc("joint_gaussian", r"The converse holds for jointly Gaussian vectors (not just Gaussian marginals); and independence $\Rightarrow \mathrm{Cov} = 0$ needs finite variances",
                    ["jointly gaussian", "joint gaussian", "multivariate normal", "jointly normal", "bivariate normal"],
                    r"OK, but for Gaussian variables zero correlation always means independence, doesn't it?"),
            ],
        },
        "misconceptions": [
            _mis(["uncorrelated so independent", "zero correlation means independent", "cov = 0 implies independen", "covariance is zero so they are independent"], "FALSE_ANALOGY",
                 "Uncorrelated implies independent", r"\mathrm{Cov}(X,Y) = 0 \implies X \perp\!\!\!\perp Y"),
            _mis(["both normal so independent", "gaussian marginals and uncorrelated", "each is gaussian so zero correlation"], "BOUNDARY_OMISSION",
                 "Marginal Gaussianity suffices", r"X, Y \sim \mathcal{N},\ \mathrm{Cov}(X,Y) = 0 \implies X \perp\!\!\!\perp Y"),
            _mis(["no relationship", "unrelated because correlation", "nothing to do with each other"], "CUE_BLINDNESS",
                 "Zero correlation means no relationship", r"\rho_{XY} = 0 \implies Y \text{ carries no information about } X"),
        ],
    },
    # ------------------------------------------------------------------ Cluster C
    "prop_row_local_mlp": {
        "probe": {
            "prompt": r"Token matrix $X \in \mathbb{R}^{T\times d}$, weights $W\in\mathbb{R}^{d\times d'}$, output $Y = \sigma(XW)$ with $\sigma$ applied entrywise. If you change only row 3 of $X$, which rows of $Y$ can change?",
            "options": _opts(r"All rows", r"Only row 3", r"Rows 1 through 3", r"Rows 3 through $T$"),
            "correct": "B",
            "explanation": r"Row $t$ of $XW$ is $x_t^\top W$, which reads only row $t$ of $X$; an entrywise $\sigma$ keeps it that way. Right-multiplication mixes features, never positions.",
        },
        "predict": {
            "prompt": r"Predict: if you swap tokens 1 and 5 in the input to a position-wise feed-forward block, what happens to the output rows? What does your answer imply about where tokens must exchange information in a transformer?",
        },
        "reading": r"""**Base case $T = 1$.** $X = x^\top$ is one row; $XW = x^\top W$ and $\sigma$ acts on each entry. Nothing to mix.

**Step to $T = 2$.** Row $t$ of a product is (row $t$ of the left factor) times the right factor:
$$XW = \begin{pmatrix} x_1^\top W\\ x_2^\top W\end{pmatrix}.$$
Applying $\sigma$ entrywise keeps each row's computation private: row $t$ of $\sigma(XW)$ is $\sigma(x_t^\top W)$.

**Consequences.** The Jacobian is block-diagonal: $\partial Y_{s,:}/\partial x_t = 0$ for $s \ne t$. The map is permutation-equivariant: $\sigma(PXW) = P\,\sigma(XW)$ for any permutation matrix $P$. Stacking more layers $\sigma(\sigma(XW_1)W_2)$ changes nothing.

**Where mixing lives.** Left multiplication $AX$ with $A\in\mathbb{R}^{T\times T}$ gives rows $\sum_s A_{ts}x_s^\top$: positions mix. Attention is exactly such a data-dependent $A$. Caveat: the nonlinearity must be entrywise; a softmax over the token axis, or normalization with cross-token statistics, would break locality.

**Self-explanation:** Which operand's side decides whether positions mix, and why can't the nonlinearity change that?""",
        "check": {
            "prompt": r"In code: `Y = gelu(einsum('btd,de->bte', X, W))`. Along which index can information flow between different entries of `X`?",
            "options": _opts(
                r"Along `t` (between tokens)",
                r"Only from `d` to `e`, within the same `(b, t)`",
                r"Along `b` (between batch elements)",
                r"Along all indices",
            ),
            "correct": "B",
            "explanation": r"The contraction is over `d` only; `b` and `t` appear unchanged on both sides, so each `(b, t)` slice is computed independently. GELU is entrywise.",
        },
        "productive_failure": {
            "prompt": r"Using only matrix products with learned or computed matrices and entrywise nonlinearities on $X\in\mathbb{R}^{T\times d}$, design a layer in which token $t$ can read information from earlier tokens. Which side must your mixing matrix act on, what shape must it have, and how would you prevent reading from later tokens?",
            "canonical_insight": r"Mixing across positions requires a left factor $A\in\mathbb{R}^{T\times T}$: $(AX)_t = \sum_s A_{ts}x_s$. Right factors $W\in\mathbb{R}^{d\times d'}$ only mix features within a row. A lower-triangular $A$ (e.g. causal averaging) reads only the past; attention builds $A = \mathrm{softmax}(QK^\top/\sqrt{d_k} + M)$ from the data itself.",
        },
        "practice": {
            1: {
                "prompt": r"Debugging: in a 12-token sequence you perturb token 7's embedding and observe that outputs at tokens 1–6 change after a block that is supposed to be the feed-forward sublayer $\sigma(XW_1)W_2$. Is that possible for a correct implementation? What kind of bug would you look for?",
                "answer_summary": r"Impossible for a correct FFN: output row $s$ depends only on $x_s$ because right-multiplication and entrywise $\sigma$ act row by row. Look for an operation along the token axis: a transpose/reshape that applies $W$ over positions, or a norm/softmax computing statistics across tokens.",
                "concept_groups": [["row", "per-token", "position-wise", "each token independently", "row-local", "token-wise"], ["transpose", "wrong axis", "axis", "reshape", "batchnorm", "batch norm", "across tokens", "left"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(20)
T, d, h = 12, 8, 16
X = rng.normal(size=(T, d)); W1 = rng.normal(size=(d, h)); W2 = rng.normal(size=(h, d))
ffn = lambda Z: np.maximum(Z @ W1, 0) @ W2
Xp = X.copy(); Xp[6] += rng.normal(size=d)
diff = np.abs(ffn(Xp) - ffn(X)).sum(1)
assert np.all(diff[:6] == 0) and np.all(diff[7:] == 0) and diff[6] > 0
Wt = rng.normal(size=(T, T))
buggy = lambda Z: np.maximum(Wt @ Z, 0)
assert np.abs(buggy(Xp) - buggy(X))[:6].sum() > 0
print('VERIFIED: correct FFN only changes row 7; token-axis matmul leaks')
""",
                "hints": _hints(
                    r"Shape check: in $\sigma(XW_1)W_2$, which dimension of $X$ do $W_1$ and $W_2$ contract against?",
                    r"In “{quote}”, which operation are you assuming can reach across rows?",
                    r"Row $t$ of a product $XW$ is built from which rows of $X$?",
                    r"Take $T = 2$, $d = 1$: $X = (x_1, x_2)^\top$, $W = w$. Write $\sigma(XW)$ and check whether $x_2$ appears in row 1.",
                    r"Analog: a per-pixel colour transform (multiply each RGB vector by the same $3\times3$ matrix, then clip) can never blur an image; blurring needs a spatial kernel. Map 'pixel' to 'token' and look for the hidden spatial kernel.",
                ),
            },
            2: {
                "prompt": r"Index notation for a hidden layer: $h_{tj} = \phi\big(\sum_i x_{ti}W_{ij} + b_j\big)$. Compute $\partial h_{sj}/\partial x_{ti}$, distinguishing $s \ne t$ and $s = t$.",
                "answer_summary": r"$\dfrac{\partial h_{sj}}{\partial x_{ti}} = \delta_{st}\,\phi'\big(\textstyle\sum_k x_{sk}W_{kj} + b_j\big)W_{ij}$: zero for $s \ne t$, and $\phi'(\cdot)W_{ij}$ for $s = t$.",
                "concept_groups": [["= 0", "=0", "zero", "vanish", "δ_{st}", "delta_{st}", "kronecker", "δ_st"], ["φ'", "phi'", "φ′", "derivative of φ", "w_{ij}", "w_ij"]],
                "verify_code": r"""import sympy as sp
x = sp.Matrix(2, 2, sp.symbols('x0:2_0:2')); W = sp.Matrix(2, 2, sp.symbols('w0:2_0:2')); b = sp.Matrix(1, 2, sp.symbols('b0:2'))
phi = sp.Function('phi')
H = sp.Matrix(2, 2, lambda s, j: phi(sum(x[s, i] * W[i, j] for i in range(2)) + b[j]))
for s in range(2):
    for j in range(2):
        for t in range(2):
            for i in range(2):
                dv = sp.diff(H[s, j], x[t, i])
                if s != t:
                    assert dv == 0
                else:
                    assert sp.simplify(dv / W[i, j] - sp.diff(H[s, j], x[s, i]) / W[i, j]) == 0 and dv.has(W[i, j])
print('VERIFIED: dh_sj/dx_ti = delta_st * phi\'(.) * W_ij')
""",
                "hints": _hints(
                    r"Index check: which indices appear inside $\phi$ for $h_{sj}$? Does $t$ appear there when $t \ne s$?",
                    r"In “{quote}”, which index did you sum over, and did a row index sneak into the sum?",
                    r"If an expression does not contain a variable, what is its derivative with respect to that variable?",
                    r"Do $T = 2$, $d = 1$: $h_1 = \phi(x_1w + b)$, $h_2 = \phi(x_2w + b)$. Compute $\partial h_1/\partial x_2$ and $\partial h_1/\partial x_1$.",
                    r"Analog: $y_s = \tanh(a\,x_s)$ for $s = 1..T$ has $\partial y_s/\partial x_t = \delta_{st}\,a\,(1 - \tanh^2(ax_s))$. Add the feature indices $i, j$.",
                ),
            },
            3: {
                "prompt": r"For $X\in\mathbb{R}^{3\times 2}$ compare $Y_1 = \sigma(XW)$ with $W\in\mathbb{R}^{2\times2}$ and $Y_2 = \sigma(AX)$ with $A\in\mathbb{R}^{3\times3}$ lower-triangular with nonzero entries. Which input rows can influence output row 2 in each case? What changes if $A$ is a full matrix?",
                "answer_summary": r"$Y_1$: only row 2 (right-multiplication is row-local). $Y_2$: rows 1 and 2, since $(AX)_2 = A_{21}x_1^\top + A_{22}x_2^\top$. With a full $A$, all three rows. The left factor mixes positions; the right factor mixes features.",
                "concept_groups": [["only row 2", "just row 2", "row 2 only", "itself"], ["rows 1 and 2", "rows 1, 2", "row 1 and row 2", "1 and 2", "earlier", "previous"], ["left", "token axis", "a mixes", "rows mix", "mixes positions"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(21)
X = rng.normal(size=(3, 2)); W = rng.normal(size=(2, 2))
A = np.tril(rng.uniform(0.5, 1.5, size=(3, 3))); F = rng.uniform(0.5, 1.5, size=(3, 3))
def influence(f):
    out = []
    for t in range(3):
        Xp = X.copy(); Xp[t] += 1.0
        out.append(np.abs(f(Xp)[1] - f(X)[1]).sum() > 1e-12)
    return out
assert influence(lambda Z: np.tanh(Z @ W)) == [False, True, False]
assert influence(lambda Z: np.tanh(A @ Z)) == [True, True, False]
assert influence(lambda Z: np.tanh(F @ Z)) == [True, True, True]
print('VERIFIED: row 2 depends on {2} (XW), {1,2} (tril A X), {1,2,3} (full A X)')
""",
                "hints": _hints(
                    r"Shape check: $A$ is $T\times T$ and $W$ is $d\times d'$. Which one has rows and columns indexed by positions?",
                    r"In “{quote}”, did you read the matrix product row by row on the correct side?",
                    r"Row $t$ of $AX$ is which linear combination of the rows of $X$?",
                    r"Write $(AX)_{2,:}$ explicitly for a lower-triangular $3\times3$ $A$.",
                    r"Analog: a causal moving average $A = \tfrac12\begin{pmatrix}2&0\\1&1\end{pmatrix}$ gives row 2 $= \tfrac12(x_1 + x_2)$, while $XW$ row 2 is $x_2^\top W$. Extend to $3\times3$.",
                ),
            },
            4: {
                "prompt": r"Your team swaps LayerNorm for BatchNorm in front of the FFN, normalizing over the (batch × sequence) axis using the **current batch's** statistics, and still documents the block as 'position-wise'. Is it? What about at inference with frozen running statistics?",
                "answer_summary": r"With current-batch statistics it is not position-wise: each token is normalized by a mean/variance computed across other tokens (and examples), so output row $t$ depends on other rows. LayerNorm normalizes within a row and stays local. With frozen running statistics BatchNorm becomes a fixed affine map per feature, so the block is row-local again.",
                "concept_groups": [["not row-local", "no longer", "not local", "not position-wise", "mixes", "depends on other"], ["statistic", "mean", "variance", "across tokens", "across rows"], ["layernorm", "layer norm", "within a row", "per row", "running", "frozen"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(22)
X = rng.normal(size=(6, 4)); W = rng.normal(size=(4, 4))
bn = lambda Z: (Z - Z.mean(0)) / (Z.std(0) + 1e-5)
ln = lambda Z: (Z - Z.mean(1, keepdims=True)) / (Z.std(1, keepdims=True) + 1e-5)
mu, sd = X.mean(0), X.std(0)
frozen = lambda Z: (Z - mu) / (sd + 1e-5)
Xp = X.copy(); Xp[5] += 3.0
row0 = lambda f, Z: np.maximum(f(Z) @ W, 0)[0]
assert not np.allclose(row0(bn, X), row0(bn, Xp))
assert np.allclose(row0(ln, X), row0(ln, Xp)) and np.allclose(row0(frozen, X), row0(frozen, Xp))
print('VERIFIED: batch-stat BN leaks across tokens; LayerNorm and frozen BN do not')
""",
                "hints": _hints(
                    r"Shape check: over which axis is each normalization's mean computed? Does that axis index tokens?",
                    r"In “{quote}”, which statistic is shared across rows?",
                    r"A block is position-wise only if every operation in it is. Which operation in the new block reads several rows at once?",
                    r"Take $T = 2$ tokens, $d = 1$: BatchNorm gives $(x_1 - \bar x)/s$ with $\bar x = (x_1 + x_2)/2$. Does $x_2$ appear in row 1?",
                    r"Analog: grading on a curve (subtract the class mean) makes your grade depend on classmates; grading against a fixed rubric does not. Map class mean ↔ batch statistics, rubric ↔ frozen running statistics.",
                ),
            },
        },
        "referee": {
            "claim": r"For a feature-major framework that stores activations as $X^\top\in\mathbb{R}^{d\times T}$, the layer $Y = XW$ (with $W\in\mathbb{R}^{d\times d'}$) is implemented as $Y^\top = X^\top W^\top$ with the same weights.",
            "steps": [
                r"The row-major layer is $Y = XW$ with $X\in\mathbb{R}^{T\times d}$, $W\in\mathbb{R}^{d\times d'}$, $Y\in\mathbb{R}^{T\times d'}$.",
                r"A feature-major framework stores the transposes $X^\top\in\mathbb{R}^{d\times T}$ and $Y^\top\in\mathbb{R}^{d'\times T}$.",
                r"Transpose distributes over products: $(XW)^\top = X^\top W^\top$.",
                r"Hence $Y^\top$ is obtained by right-multiplying the stored $X^\top$ by $W^\top$.",
                r"So the feature-major layer is $Y^\top = X^\top W^\top$: same weights, no reordering needed.",
            ],
            "flawed_index": 3,
            "violated_keywords": ["reverse", "w^t x^t", "w^\\top x^\\top", "order", "shape", "(ab)^t = b^t a^t", "b^t a^t"],
            "explanation": r"Transposition reverses order: $(XW)^\top = W^\top X^\top$. The feature-major layer is a *left* multiplication by $W^\top$. The claimed $X^\top W^\top$ is $(d\times T)(d'\times d)$, undefined unless $T = d'$, and wrong even when the shapes happen to fit.",
            "counterexample": r"$X = \begin{pmatrix}1&2\\3&4\end{pmatrix}$, $W = \begin{pmatrix}0&1\\1&0\end{pmatrix}$: $(XW)^\top = \begin{pmatrix}2&4\\1&3\end{pmatrix}$ but $X^\top W^\top = \begin{pmatrix}3&1\\4&2\end{pmatrix}$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Jules, who believes the big dense MLP weight matrices are where tokens 'talk to each other' in a transformer.",
            "opening": r"The FFN has the biggest weight matrices in the model, and dense matrices mix everything. So the MLP must be where tokens share information. Why do people call it 'position-wise'?",
            "boundary_conditions": [
                _bc("right_multiplication", r"Row $t$ of $XW$ is $x_t^\top W$: right-multiplication mixes features within a row, never positions",
                    ["row", "x_t^t w", "x_t^\\top w", "right-multipl", "right multipl", "features", "per token", "each row"],
                    r"But $W$ is a huge dense matrix — doesn't it mix everything?"),
                _bc("entrywise_nonlinearity", r"The nonlinearity must be entrywise; a softmax over the token axis, or norms with cross-token statistics, break locality",
                    ["coordinate-wise", "elementwise", "element-wise", "pointwise", "entrywise", "entry-wise"],
                    r"What if the activation were a softmax over the sequence dimension?"),
                _bc("left_mixing", r"Mixing positions requires left-multiplication by a $T\times T$ matrix (attention, convolution over time)",
                    ["left", "t×t", "t x t", "txt", "attention", "ax", "a x"],
                    r"So where in a transformer do tokens actually exchange information?"),
            ],
        },
        "misconceptions": [
            _mis(["mlp mixes tokens", "ffn mixes positions", "w mixes all tokens", "dense layer mixes the sequence"], "FALSE_ANALOGY",
                 "Dense weights mix tokens", r"\big(\sigma(XW)\big)_{t,:} \text{ depends on } x_s,\ s \ne t"),
            _mis(["(xw)^t = x^t w^t", "transpose distributes", "transpose each factor in place"], "ALGEBRAIC_SLIP",
                 "Transpose without reversal", r"(XW)^\top = X^\top W^\top"),
            _mis(["any activation is local", "softmax activation is still row-local", "every nonlinearity is position-wise"], "BOUNDARY_OMISSION",
                 "Every nonlinearity is position-wise", r"\mathrm{softmax}_{\text{tokens}}(XW) \text{ is row-local}"),
        ],
    },
    "prop_causal_mask_support": {
        "probe": {
            "prompt": r"Sequence length $T = 4$. Row $i = 2$ (1-indexed) of the logits is $(1, 2, 3, 4)$. After adding the causal mask ($0$ for $j \le i$, $-\infty$ for $j > i$) and a row softmax, the attention weights in row 2 are approximately:",
            "options": _opts(
                r"$(0.032,\ 0.087,\ 0.237,\ 0.644)$",
                r"$(0.269,\ 0.731,\ 0,\ 0)$",
                r"$(0.5,\ 0.5,\ 0,\ 0)$",
                r"$(0.269,\ 0.731,\ -\infty,\ -\infty)$",
            ),
            "correct": "B",
            "explanation": r"$e^{-\infty} = 0$ removes positions 3 and 4 and the softmax renormalizes over $\{1, 2\}$: $\big(\tfrac{e}{e + e^2}, \tfrac{e^2}{e+e^2}\big) \approx (0.269, 0.731)$. A is the unmasked softmax; D confuses logits with weights.",
        },
        "predict": {
            "prompt": r"Predict: after masking future positions with $-\infty$ and applying softmax, can output row $i$ depend on $v_{i+1}$ in any way, forward or through gradients? And what would happen to a row in which *every* entry is masked?",
        },
        "reading": r"""**Base case $T = 2$.** Row 1 has logits $(s_{11}, s_{12} - \infty)$. Since $e^{-\infty} = 0$,
$$A_{11} = \frac{e^{s_{11}}}{e^{s_{11}} + 0} = 1, \qquad A_{12} = 0,$$
so $o_1 = v_1$. Row 2 has no masked entries.

**General row $i$.**
$$A_{ij} = \frac{e^{s_{ij}}\,\mathbf{1}[j \le i]}{\sum_{l\le i} e^{s_{il}}}.$$
Weights vanish for $j > i$, are positive for $j \le i$, and sum to $1$.

**Support.** $o_i = \sum_j A_{ij}v_j = \sum_{j\le i}A_{ij}v_j$: a convex combination, so $o_i \in \mathrm{span}\{v_1, \dots, v_i\}$. Future logits are absent from the denominator too, so $o_i$ ignores future keys as well.

**Backward pass.** $\partial o_i/\partial v_j = A_{ij}I = 0$ for $j > i$: no gradient leak either.

**Fragile spots.** A fully masked row gives $0/0 = \mathrm{NaN}$; the unmasked diagonal $M_{ii} = 0$ prevents that. Finite stand-ins like $-10^4$ overflow in fp16.

**Self-explanation:** Why is keeping the diagonal entry $M_{ii} = 0$ essential for every row to be well-defined?""",
        "check": {
            "prompt": r"In code: `P = scores.masked_fill(torch.triu(torch.ones(T, T), diagonal=1).bool(), float('-inf')).softmax(-1)`. For $j > i$, the entry `P[i, j]` equals:",
            "options": _opts(r"$-\infty$", r"$0$", r"$1/T$", r"NaN"),
            "correct": "B",
            "explanation": r"`triu(..., diagonal=1)` selects strictly-upper entries $j > i$; filling them with $-\infty$ and exponentiating inside the softmax gives exact zeros. No row is fully masked because the diagonal is kept, so no NaN appears.",
        },
        "productive_failure": {
            "prompt": r"You must train a language model on all $T$ positions in parallel, yet the prediction at position $i$ must never use tokens $> i$. Design the cheapest modification of full attention $\mathrm{softmax}(QK^\top/\sqrt{d_k})V$ that achieves this, and prove that no information leaks forward or backward.",
            "canonical_insight": r"Add a mask $M$ with $M_{ij} = -\infty$ for $j > i$ (and $0$ otherwise) before the row softmax. Future weights become exactly $0$, the denominator sums only over $j \le i$, so $o_i = \sum_{j\le i}A_{ij}v_j$ is independent of $q_{j}, k_j, v_j$ for $j > i$, and all its gradients with respect to them vanish.",
        },
        "practice": {
            1: {
                "prompt": r"Your decoder's validation loss is suspiciously close to zero after one epoch. Inspecting attention weights for position 5 of a 10-token sequence, you find nonzero mass on positions 6–10. What constraint is broken, and exactly what should row 5 of the attention matrix look like?",
                "answer_summary": r"Future leakage: the causal mask is missing or misapplied (wrong orientation, or applied after the softmax). Correct row 5: $A_{5j} = 0$ for $j > 5$, $A_{5j} > 0$ for $j \le 5$, and $\sum_{j\le5}A_{5j} = 1$.",
                "concept_groups": [["leak", "future", "cheat", "peek"], ["j > i", "j>i", "positions 6", "6-10", "6–10", "after position 5", "upper triang"], ["sum to 1", "sums to 1", "renormal", "add up to 1", "adds up to 1"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(23)
T = 10
S = rng.normal(size=(T, T))
M = np.where(np.arange(T)[None, :] > np.arange(T)[:, None], -np.inf, 0.0)
Z = S + M
A = np.exp(Z - Z.max(1, keepdims=True)); A /= A.sum(1, keepdims=True)
row5 = A[4]
assert np.all(row5[5:] == 0) and np.all(row5[:5] > 0) and np.isclose(row5.sum(), 1)
print('VERIFIED: masked row 5 is zero on 6..10, positive on 1..5, sums to 1')
""",
                "hints": _hints(
                    r"Sanity check: a near-zero loss on next-token prediction means the model can see what?",
                    r"In “{quote}”, which positions should row 5 be allowed to see?",
                    r"What value must a logit have so that, after exponentiation in the softmax, its weight is exactly zero?",
                    r"Do $T = 3$ by hand: write the allowed pattern (1 = allowed) of the $3\times3$ attention matrix.",
                    r"Analog: an exam proctor lets student 3 see answers from students 1–3 only; if answers from 4–5 appear, the screen between rows is missing. Here the 'screen' is the $-\infty$ mask on $j > i$.",
                ),
            },
            2: {
                "prompt": r"With all logits $L\in\mathbb{R}^{3\times3}$ equal to $0$, mask $M = \begin{pmatrix}0&-\infty&-\infty\\0&0&-\infty\\0&0&0\end{pmatrix}$, and values $V = (3, 6, 9)^\top$, compute $\mathrm{softmax}_{\text{row}}(L + M)\,V$.",
                "answer_summary": r"$\mathrm{softmax}_{\text{row}}(L + M) = \begin{pmatrix}1&0&0\\ \tfrac12&\tfrac12&0\\ \tfrac13&\tfrac13&\tfrac13\end{pmatrix}$, so the output is $(3, 4.5, 6)^\top$: running (prefix) means of $V$.",
                "concept_groups": [["3, 4.5, 6", "3,4.5,6", "(3, 4.5, 6)", "[3, 4.5, 6]", "4.5"], ["prefix", "running mean", "running average", "cumulative", "average of", "mean of the first"]],
                "verify_code": r"""import numpy as np
M = np.array([[0, -np.inf, -np.inf], [0, 0, -np.inf], [0, 0, 0]])
Z = np.zeros((3, 3)) + M
A = np.exp(Z); A /= A.sum(1, keepdims=True)
out = A @ np.array([3., 6., 9.])
assert np.allclose(out, [3, 4.5, 6])
print('VERIFIED: output', out.tolist())
""",
                "hints": _hints(
                    r"Each row of weights must sum to 1. How many unmasked entries does each row have?",
                    r"In “{quote}”, what did you take as the exponential of minus infinity?",
                    r"With equal logits, how does a softmax distribute its weight among the allowed entries?",
                    r"Row 1 has a single allowed entry. What weight must it get?",
                    r"Analog: with values $(2, 4, 6, 8)$ and equal logits, a causal mask yields $(2, 3, 4, 5)$ — the running means. Transfer to $(3, 6, 9)$.",
                ),
            },
            3: {
                "prompt": r"A teammate proposes masking **after** the softmax: compute $P = \mathrm{softmax}_{\text{row}}(QK^\top/\sqrt{d})$ over all positions, then multiply by a $0/1$ lower-triangular mask without renormalizing. Compare with additive $-\infty$ masking before the softmax: are the weights the same? Is the no-leak guarantee the same?",
                "answer_summary": r"No. Post-softmax masking keeps $P_{ij}$ for $j \le i$, but those weights have the *full* denominator $\sum_{l=1}^T e^{s_{il}}$, which includes future logits $s_{il} = q_i^\top k_l/\sqrt d$ for $l > i$. So rows do not sum to $1$, and $o_i$ depends on future keys: information leaks. Pre-softmax $-\infty$ masking removes the future from the denominator.",
                "concept_groups": [["sum to 1", "sums to 1", "don't sum", "do not sum", "not normalized", "renormal"], ["denominator", "normaliz", "partition"], ["leak", "depends on future", "future keys", "k_j", "future logits"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(24)
T, d = 4, 3
Q, K, V = rng.normal(size=(T, d)), rng.normal(size=(T, d)), rng.normal(size=(T, d))
tril = np.tril(np.ones((T, T)))
def pre(K):
    S = Q @ K.T / np.sqrt(d) + np.where(tril == 1, 0, -np.inf)
    A = np.exp(S - S.max(1, keepdims=True)); return (A / A.sum(1, keepdims=True)) @ V
def post(K):
    S = Q @ K.T / np.sqrt(d)
    P = np.exp(S - S.max(1, keepdims=True)); P /= P.sum(1, keepdims=True)
    return (P * tril) @ V
K2 = K.copy(); K2[3] += 5.0
assert np.allclose(pre(K)[0], pre(K2)[0])
assert not np.allclose(post(K)[0], post(K2)[0])
print('VERIFIED: post-softmax masking leaks future keys through the denominator')
""",
                "hints": _hints(
                    r"Check the row sums of the post-softmax-masked matrix. Are they 1?",
                    r"In “{quote}”, which quantities appear in the softmax denominator for row i?",
                    r"A weight can be zero and still be computed using future information. Where would that information hide?",
                    r"Take $T = 2$. Write $P_{11}$ for post-softmax masking and check whether it contains $k_2$.",
                    r"Analog: dividing your score by the class total (including students who haven't taken the exam yet) and then hiding their scores still lets their results move your normalized score. Transfer to the softmax denominator.",
                ),
            },
            4: {
                "prompt": r"For left-padded batches, a teammate masks every key position that is padding — including in the query row that is itself a pad token, which leaves row 1 entirely $-\infty$. They argue causality is 'trivially' preserved for that row. Run the computation and explain what actually happens.",
                "answer_summary": r"A fully masked row gives $\mathrm{softmax}(-\infty, \dots, -\infty) = 0/0 = \mathrm{NaN}$, which then propagates into outputs, the loss, and every gradient. Keep at least one finite entry per row (e.g. the diagonal), or zero out pad-query rows explicitly.",
                "concept_groups": [["nan", "0/0", "undefined", "not a number"], ["diagonal", "at least one", "self", "finite", "zero out"]],
                "verify_code": r"""import numpy as np
with np.errstate(invalid='ignore'):
    z = np.array([-np.inf, -np.inf, -np.inf])
    p = np.exp(z) / np.exp(z).sum()
    assert np.all(np.isnan(p))
    loss = (p * np.array([1., 2., 3.])).sum()
    assert np.isnan(loss)
z2 = np.array([0.0, -np.inf, -np.inf])
p2 = np.exp(z2) / np.exp(z2).sum()
assert np.allclose(p2, [1, 0, 0])
print('VERIFIED: fully masked row -> NaN; keeping the diagonal -> well defined')
""",
                "hints": _hints(
                    r"Compute the softmax denominator for that row. What number is it?",
                    r"In “{quote}”, what does the softmax return when every input is minus infinity?",
                    r"In the standard causal mask, which entry of every row is guaranteed to be unmasked?",
                    r"Evaluate $e^{-\infty}/(e^{-\infty} + e^{-\infty})$ in floating point.",
                    r"Analog: averaging over an empty set of grades gives $0/0$; a report card with that cell poisons every downstream statistic. Keep one valid entry (the diagonal) or drop the row entirely.",
                ),
            },
        },
        "referee": {
            "claim": r"Multiplying the post-softmax attention weights by a $0/1$ lower-triangular mask (with no renormalization) makes output $i$ independent of all future tokens.",
            "steps": [
                r"Let $P = \mathrm{softmax}_{\text{row}}(QK^\top/\sqrt d)$ and $A = P\odot L$ with $L_{ij} = \mathbf{1}[j \le i]$.",
                r"Then $A_{ij} = 0$ for every $j > i$.",
                r"So $o_i = \sum_j A_{ij}v_j = \sum_{j\le i}P_{ij}v_j$ contains no $v_j$ with $j > i$.",
                r"Each weight $P_{ij}$ with $j \le i$ depends only on $q_i$ and $k_j$, so $o_i$ depends only on tokens $1, \dots, i$.",
                r"Hence post-softmax masking is leak-free.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["denominator", "normaliz", "partition", "all keys", "k_2", "sum over all", "future logits"],
            "explanation": r"$P_{ij} = e^{s_{ij}}/\sum_{l=1}^T e^{s_{il}}$: the denominator includes the future logits $s_{il} = q_i^\top k_l/\sqrt d$ for $l > i$. So $o_i$ depends on future keys even though future values are zeroed.",
            "counterexample": r"$T = 2$: $o_1 = P_{11}v_1$ with $P_{11} = e^{s_{11}}/(e^{s_{11}} + e^{s_{12}})$. Changing $k_2$ changes $s_{12}$ and hence $o_1$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Dana, who implements causal masking by setting the future logits to 0 'since zero means no attention'.",
            "opening": r"To stop token $i$ from looking ahead, I just set the logits for $j > i$ to $0$. Zero means 'no attention', right? Why does every implementation use $-\infty$ instead?",
            "boundary_conditions": [
                _bc("neg_inf_before_softmax", r"The mask must add $-\infty$ before the softmax, so $e^{-\infty} = 0$ removes the entry from numerator and denominator; a logit of $0$ still gets weight $e^0/\sum > 0$",
                    ["-∞", "−∞", "-inf", "negative infinity", "minus infinity", "before softmax", "before the softmax", "exp(-inf)"],
                    r"Why not just set future logits to $0$ — isn't that 'no attention'?"),
                _bc("diagonal_kept", r"The diagonal $j = i$ stays unmasked so each row has non-empty support; a fully masked row gives NaN",
                    ["diagonal", "j = i", "j=i", "nan", "empty row", "itself", "at least one"],
                    r"What happens in row 1 if I also mask $j = i$?"),
                _bc("support_and_gradient", r"$o_i$ is a convex combination of $v_1..v_i$ (in their span), and gradients with respect to future $v_j, k_j$ are exactly zero",
                    ["span", "convex", "gradient", "backward", "weighted average"],
                    r"Even if the forward pass is clean, couldn't the gradient leak future information?"),
            ],
        },
        "misconceptions": [
            _mis(["mask with 0", "set future logits to zero", "multiply logits by the mask", "zero logits for the future"], "ALGEBRAIC_SLIP",
                 "Zero-logit masking", r"L_{ij} \leftarrow 0 \text{ for } j > i \implies A_{ij} = 0"),
            _mis(["mask after softmax", "zero the weights after softmax", "multiply the attention weights by the mask"], "BOUNDARY_OMISSION",
                 "Post-softmax masking is equivalent", r"\big(\mathrm{softmax}(S)\odot L\big)V = \mathrm{softmax}(S + M)V"),
            _mis(["mask j < i", "upper triangular keeps the past", "mask the earlier tokens"], "NOTATION_OBSTRUCTION",
                 "Mask orientation flipped", r"M_{ij} = -\infty \text{ for } j < i"),
        ],
    },
    "prop_scaled_dot_product_variance": {
        "probe": {
            "prompt": r"$q, k\in\mathbb{R}^{64}$ have i.i.d. entries with mean $0$ and variance $1$, and $q$ is independent of $k$. What is the standard deviation of $q^\top k$?",
            "options": _opts(r"$1$", r"$8$", r"$64$", r"$4096$"),
            "correct": "B",
            "explanation": r"Each $q_ik_i$ has mean $0$ and variance $1$, and the 64 terms are uncorrelated, so $\mathrm{Var}(q^\top k) = 64$ and the standard deviation is $\sqrt{64} = 8$.",
        },
        "predict": {
            "prompt": r"Predict: you double the attention head dimension $d_k$ without changing the logit scaling. What happens to the typical size of the attention logits, to the softmax's entropy, and to the gradients flowing through it?",
        },
        "reading": r"""**Base case $d_k = 1$.** The logit is $s = q_1k_1$. With $q_1 \perp\!\!\!\perp k_1$, both mean $0$, variance $1$:
$$\mathrm{Var}(q_1k_1) = \mathbb{E}[q_1^2]\,\mathbb{E}[k_1^2] = 1.$$

**Add coordinates.** $q^\top k = \sum_{i=1}^{d_k}q_ik_i$. Terms with different $i$ involve disjoint independent coordinates, so they are uncorrelated and variances add:
$$\mathbb{E}[q^\top k] = 0, \qquad \mathrm{Var}(q^\top k) = d_k.$$
The logit standard deviation grows like $\sqrt{d_k}$.

**Why it hurts.** Large logits push the softmax toward one-hot; its Jacobian $\mathrm{diag}(p) - pp^\top$ then approaches $0$, so gradients vanish.

**The fix, one more step.** $\mathrm{Var}(cZ) = c^2\,\mathrm{Var}(Z)$. With $c = 1/\sqrt{d_k}$:
$$\mathrm{Var}\big(q^\top k/\sqrt{d_k}\big) = d_k/d_k = 1,$$
independent of width. If entries had variance $\sigma^2$, the divisor would be $\sigma^2\sqrt{d_k}$.

**Self-explanation:** Why divide by $\sqrt{d_k}$ and not $d_k$? What would $1/d_k$ do to the logits at $d_k = 512$?""",
        "check": {
            "prompt": r"Let $\mathbf a, \mathbf b\in\mathbb{R}^n$ be independent with entries i.i.d. $\mathcal{N}(0, \sigma^2)$. Which $\tau$ makes $\mathrm{Var}(\mathbf a\cdot\mathbf b/\tau) = 1$?",
            "options": _opts(r"$\sigma\sqrt n$", r"$n\sigma^2$", r"$\sigma^2\sqrt n$", r"$\sqrt n$"),
            "correct": "C",
            "explanation": r"Each term $a_ib_i$ has variance $\sigma^2\cdot\sigma^2 = \sigma^4$, so $\mathrm{Var}(\mathbf a\cdot\mathbf b) = n\sigma^4$; dividing by $\tau$ divides variance by $\tau^2$, so $\tau = \sigma^2\sqrt n$.",
        },
        "productive_failure": {
            "prompt": r"Attention logits at $d_k = 256$ have standard deviation about $16$, and training stalls. Without being told any rule, find a single scalar rescaling of the logits that makes their distribution width-independent, and prove it works. List every assumption about $q$ and $k$ your proof used.",
            "canonical_insight": r"Under i.i.d. mean-0 variance-1 coordinates and $q \perp\!\!\!\perp k$: $\mathrm{Var}(q_ik_i) = 1$ (product of independent zero-mean variables) and the $d_k$ terms are uncorrelated, so $\mathrm{Var}(q^\top k) = d_k$ (std $16$ at $d_k = 256$). Since $\mathrm{Var}(cZ) = c^2\mathrm{Var}Z$, dividing by $\sqrt{d_k}$ restores unit variance. Assumptions: zero means, unit variances, independence across coordinates and between $q$ and $k$.",
        },
        "practice": {
            1: {
                "prompt": r"You double your attention head dimension from $64$ to $128$ but keep the logit divisor at $8$ ($=\sqrt{64}$). Assume unit-variance i.i.d. query/key entries. By what factor does the logit variance change, and which divisor restores the original scale?",
                "answer_summary": r"$\mathrm{Var}(q^\top k/8) = 128/64 = 2$: the variance doubles (std $\times\sqrt2$). The divisor $\sqrt{128} = 8\sqrt2 \approx 11.31$ restores unit variance.",
                "concept_groups": [["2", "doubl", "twice"], ["√128", "sqrt(128)", "11.3", "8√2", "8*sqrt(2)", "8 sqrt(2)", "8·√2"], ["independen", "sum of variances", "variances add", "d_k terms", "each term variance 1", "uncorrelated"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(25)
q = rng.normal(size=(200000, 128)); k = rng.normal(size=(200000, 128))
s = (q * k).sum(1)
assert abs((s / 8).var() - 2) < 0.03
assert abs((s / np.sqrt(128)).var() - 1) < 0.015 and np.isclose(np.sqrt(128), 11.3137, atol=1e-3)
print('VERIFIED: variance doubles with divisor 8; sqrt(128) ~ 11.31 restores 1')
""",
                "hints": _hints(
                    r"Dimension check: how does $\mathrm{Var}(q^\top k)$ scale with the number of coordinates?",
                    r"In “{quote}”, did you square the divisor when you computed its effect on variance?",
                    r"A sum of $d_k$ uncorrelated unit-variance terms has what variance? And what does dividing by $c$ do to a variance?",
                    r"Do $d_k = 1$ then $d_k = 2$ with divisor $1$: what are the variances?",
                    r"Analog: going from $16$ to $64$ dims with divisor $4$ gives $\mathrm{Var} = 64/16 = 4$; the fix is divisor $8 = \sqrt{64}$. Transfer to $64 \to 128$.",
                ),
            },
            2: {
                "prompt": r"A paper uses queries $\mathbf u$ and keys $\mathbf w$ in $\mathbb{R}^m$, independent, with entries i.i.d. $\mathcal{N}(0, 1/2)$, and scores $\langle\mathbf u, \mathbf w\rangle/\lambda$. Which $\lambda$ gives unit-variance scores at $m = 200$?",
                "answer_summary": r"Each term has variance $\tfrac12\cdot\tfrac12 = \tfrac14$, so $\mathrm{Var}\langle\mathbf u,\mathbf w\rangle = m/4 = 50$; $\lambda = \sqrt{50} = 5\sqrt2 \approx 7.07$.",
                "concept_groups": [["√50", "sqrt(50)", "7.07", "5√2", "5*sqrt(2)", "5 sqrt(2)"], ["m/4", "50", "1/4", "0.25"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(26)
m = 200
u = rng.normal(0, np.sqrt(0.5), size=(100000, m)); w = rng.normal(0, np.sqrt(0.5), size=(100000, m))
s = (u * w).sum(1)
assert abs(s.var() - 50) < 1.0 and abs((s / np.sqrt(50)).var() - 1) < 0.02
print('VERIFIED: Var = m/4 = 50, lambda = sqrt(50) ~ 7.07')
""",
                "hints": _hints(
                    r"Units check: with entry variance $1/2$, should the needed divisor be larger or smaller than $\sqrt m$?",
                    r"In “{quote}”, what variance did you assign to a single product term?",
                    r"For independent zero-mean factors, the variance of the product is what combination of their variances?",
                    r"Take $m = 1$: compute $\mathrm{Var}(u_1w_1)$ with both variances $1/2$.",
                    r"Analog: entries with variance $2$ in $m = 10$ dims give $\mathrm{Var} = 10\cdot4 = 40$, divisor $\sqrt{40}$. Transfer with variance $1/2$ and $m = 200$.",
                ),
            },
            3: {
                "prompt": r"At $d_k = 512$ with unit-variance i.i.d. query/key entries, compare scaling logits by $1/\sqrt{d_k}$ versus $1/d_k$. Compute the logit standard deviation in each case, and predict how a softmax over 128 keys behaves under the second choice.",
                "answer_summary": r"$1/\sqrt{d_k}$: std $1$. $1/d_k$: std $\sqrt{512}/512 = 1/\sqrt{512} \approx 0.044$. Logits that small make the softmax nearly uniform (entropy $\approx\log 128$), so attention cannot focus: the opposite failure from saturation.",
                "concept_groups": [["0.044", "1/√512", "1/sqrt(512)", "0.0442"], ["uniform", "flat", "max entropy", "can't focus", "cannot focus", "log 128", "log(128)"], ["std 1", "variance 1", "unit variance", "std of 1", "= 1"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(27)
d, n = 512, 128
q = rng.normal(size=(200, d)); K = rng.normal(size=(n, d))
S = q @ K.T
assert abs((S / np.sqrt(d)).std() - 1) < 0.05 and abs((S / d).std() - 1 / np.sqrt(d)) < 0.003
def ent(Z):
    P = np.exp(Z - Z.max(1, keepdims=True)); P /= P.sum(1, keepdims=True)
    return -(P * np.log(P)).sum(1).mean()
assert np.log(n) - ent(S / d) < 0.002 and np.log(n) - ent(S / np.sqrt(d)) > 0.3
print('VERIFIED: stds 1 vs 0.044; 1/d_k softmax is ~uniform')
""",
                "hints": _hints(
                    r"Limit check: as logits shrink to $0$, what does a softmax over $128$ entries converge to?",
                    r"In “{quote}”, did you scale the standard deviation or the variance by the divisor?",
                    r"Dividing by $d_k$ makes the variance $d_k/d_k^2$. What does that do to the spread of logits?",
                    r"Try $d_k = 4$: the std of $q^\top k$ is $2$. Divide by $2$ and by $4$; what std results each time?",
                    r"Analog: at $d_k = 100$, $1/\sqrt{d_k}$ gives std $1$ while $1/d_k$ gives std $0.1$ — softmax over a handful of keys is then within a few percent of uniform. Transfer to $512$.",
                ),
            },
            4: {
                "prompt": r"A teammate reuses the scaling argument for self-similarity scores with tied keys, $k = q$ (so the logit is $q^\top q/\sqrt{d_k}$ with $q$ having i.i.d. $\mathcal{N}(0,1)$ entries), and concludes the logits have mean $0$ and variance $1$. Correct both numbers and name the broken premise.",
                "answer_summary": r"$q$ is not independent of itself. $q^\top q = \sum_i q_i^2$ has mean $d_k$ and variance $2d_k$ (since $\mathrm{Var}(q_i^2) = 2$), so $q^\top q/\sqrt{d_k}$ has mean $\sqrt{d_k}$ and variance $2$.",
                "concept_groups": [["√d", "sqrt(d", "mean d", "mean is d", "not zero", "nonzero mean", "mean √"], ["var 2", "variance 2", "variance is 2", "2d_k", "2d", "e[q^4]", "fourth moment"], ["independen", "tied", "same vector", "not independent"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(28)
d = 64
q = rng.normal(size=(200000, d))
s = (q * q).sum(1) / np.sqrt(d)
assert abs(s.mean() - np.sqrt(d)) < 0.02 and abs(s.var() - 2) < 0.05
print('VERIFIED: tied logits have mean sqrt(d) and variance 2')
""",
                "hints": _hints(
                    r"Sign check: can $q^\top q$ ever be negative? So can its mean be $0$?",
                    r"In “{quote}”, which assumption about q and k does tying the weights remove?",
                    r"Each term is now $q_i^2$ rather than $q_ik_i$. What are the mean and variance of $q_i^2$ for a standard Gaussian?",
                    r"Take $d_k = 1$: compute $\mathbb{E}[q_1^2]$ and $\mathrm{Var}(q_1^2)$.",
                    r"Analog: with $\pm1$ entries, $q^\top q = d_k$ exactly: mean $d_k$, variance $0$, nothing like $(0, d_k)$. For Gaussians use $\mathbb{E}q^4 = 3$.",
                ),
            },
        },
        "referee": {
            "claim": r"Let $q, k\in\mathbb{R}^d$ be independent random vectors whose coordinates each have mean $0$ and variance $1$ (coordinates within $q$, and within $k$, may be correlated). Then $\mathrm{Var}(q^\top k) = d$.",
            "steps": [
                r"$q^\top k = \sum_{i=1}^d q_ik_i$.",
                r"$\mathbb{E}[q_ik_i] = \mathbb{E}[q_i]\,\mathbb{E}[k_i] = 0$ by independence of $q$ and $k$.",
                r"$\mathrm{Var}(q_ik_i) = \mathbb{E}[q_i^2]\,\mathbb{E}[k_i^2] = 1$ for each $i$.",
                r"The variance of a sum is the sum of the variances, so $\mathrm{Var}(q^\top k) = \sum_i\mathrm{Var}(q_ik_i)$.",
                r"Hence $\mathrm{Var}(q^\top k) = d$, and dividing by $\sqrt d$ normalizes the logits.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["covariance", "cross term", "correlat", "cov(q_i", "uncorrelated", "pairwise"],
            "explanation": r"Variances add only for uncorrelated terms. Here $\mathrm{Cov}(q_ik_i, q_jk_j) = \mathbb{E}[q_iq_j]\,\mathbb{E}[k_ik_j]$, which is nonzero when coordinates are correlated. In general $\mathrm{Var}(q^\top k) = \mathrm{tr}(C_qC_k)$.",
            "counterexample": r"$q = z\mathbf 1$, $k = w\mathbf 1$ with $z, w$ independent $\mathcal{N}(0,1)$: each coordinate has mean $0$ and variance $1$, but $q^\top k = d\,zw$ has variance $d^2$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": r"Rae, who thinks the $\sqrt{d_k}$ in attention is there 'to average the $d_k$ terms' and keeps wondering why it isn't $d_k$.",
            "opening": r"We sum $d_k$ terms, so to normalize we should divide by $d_k$ — like taking an average. Why does everybody divide by $\sqrt{d_k}$ instead?",
            "boundary_conditions": [
                _bc("uncorrelated_terms", r"The terms $q_ik_i$ must be uncorrelated (i.i.d. coordinates, $q \perp\!\!\!\perp k$) so the variances add to $d_k$",
                    ["independen", "uncorrelated", "iid", "i.i.d"],
                    r"What if every coordinate of $q$ is a copy of the same number?"),
                _bc("square_scaling", r"$\mathrm{Var}(cZ) = c^2\,\mathrm{Var}(Z)$, so $c = 1/\sqrt{d_k}$ gives variance $1$, whereas $1/d_k$ shrinks it to $1/d_k$",
                    ["c^2", "c²", "squared", "square", "1/√d", "sqrt"],
                    r"Dividing by $d_k$ averages the terms — isn't that the natural normalization?"),
                _bc("moment_assumptions", r"Entries need mean $0$ and variance $1$; with variance $\sigma^2$ the divisor becomes $\sigma^2\sqrt{d_k}$",
                    ["mean 0", "zero mean", "mean zero", "unit variance", "variance 1", "σ²", "sigma^2"],
                    r"If the entries have variance $4$, is $\sqrt{d_k}$ still the right divisor?"),
            ],
        },
        "misconceptions": [
            _mis(["divide by d_k", "average the terms", "1/d_k", "normalize by the dimension"], "FALSE_ANALOGY",
                 "Mean normalization instead of variance normalization", r"\mathrm{Var}\big(q^\top k / d_k\big) = 1"),
            _mis(["dividing by √d divides the variance by √d", "variance divided by sqrt", "var/√d"], "ALGEBRAIC_SLIP",
                 "Unsquared scaling of variance", r"\mathrm{Var}\big(Z/\sqrt{d_k}\big) = \mathrm{Var}(Z)/\sqrt{d_k}"),
            _mis(["variance is d_k regardless", "always d_k even if correlated", "correlation doesn't matter for the logit"], "BOUNDARY_OMISSION",
                 "Ignoring correlation among coordinates", r"\mathrm{Var}(q^\top k) = d_k \text{ for any coordinate covariance}"),
        ],
    },
    "prop_rope_relative_invariance": {
        "probe": {
            "prompt": r"A model uses rotary position embeddings (block-diagonal 2-D rotations $R_{\Theta,m}$ applied to queries and keys). If both the query position $m$ and the key position $n$ increase by $100$, the attention logit for the same content vectors $q, k$:",
            "options": _opts(
                r"is unchanged",
                r"increases by $100\,\theta$",
                r"flips sign",
                r"changes, because the norms of the rotated vectors grow",
            ),
            "correct": "A",
            "explanation": r"$\langle R_{\Theta,m}q, R_{\Theta,n}k\rangle = q^\top R_{\Theta,n-m}k$ depends only on $n - m$, which a common shift leaves unchanged. Rotations are orthogonal, so norms never grow.",
        },
        "predict": {
            "prompt": r"Predict: RoPE rotates each 2-D coordinate pair of a query by $m\theta_j$ and of a key by $n\theta_j$. If you run the same sentence starting at position $0$ and again starting at position $500$, would the attention logits between the same two words differ? Why?",
        },
        "reading": r"""**Base case $d = 2$.** Rotate the query by $m\theta$ and the key by $n\theta$:
$$\langle R(m\theta)q,\ R(n\theta)k\rangle = q^\top R(m\theta)^\top R(n\theta)\,k.$$
Three facts finish it: $(AB)^\top = B^\top A^\top$ (used above), $R(\alpha)^\top = R(-\alpha)$ (orthogonality), and $R(\alpha)R(\beta) = R(\alpha + \beta)$. So the logit is $q^\top R((n-m)\theta)\,k$.

**Step to $d = 2b$.** $R_{\Theta,m} = \mathrm{blockdiag}\big(R(m\theta_1), \dots, R(m\theta_b)\big)$. Block-diagonal matrices transpose and multiply block by block, so
$$R_{\Theta,m}^\top R_{\Theta,n} = \mathrm{blockdiag}\big(R((n-m)\theta_j)\big) = R_{\Theta, n-m}.$$
Positions enter only through the offset $n - m$.

**Bonus.** Each $R_{\Theta,m}$ is orthogonal, so $\|R_{\Theta,m}q\| = \|q\|$: RoPE never distorts magnitudes. Frequencies $\theta_j = 10000^{-2(j-1)/d}$ give offsets a multi-scale fingerprint.

**What it needs.** Both $q$ and $k$ rotated, by the same frequencies, with genuinely orthogonal blocks.

**Self-explanation:** Where exactly does orthogonality enter, and would scaling each block by $1.01$ per position break the relative property?""",
        "check": {
            "prompt": r"Represent coordinate pair $j$ as a complex number. Encode $\tilde q_j = q_je^{im\theta_j}$ and $\tilde k_j = k_je^{in\theta_j}$. The score $\mathrm{Re}\sum_j\tilde q_j\,\overline{\tilde k_j}$ equals:",
            "options": _opts(
                r"$\mathrm{Re}\sum_j q_j\bar k_j\,e^{i(m-n)\theta_j}$, a function of $m - n$ only",
                r"$\mathrm{Re}\sum_j q_j\bar k_j\,e^{i(m+n)\theta_j}$",
                r"$\sum_j|q_j||k_j|$, independent of positions",
                r"$\mathrm{Re}\sum_j q_j\bar k_j\,e^{imn\theta_j}$",
            ),
            "correct": "A",
            "explanation": r"$e^{im\theta}\,\overline{e^{in\theta}} = e^{i(m-n)\theta}$: conjugation plays the role of the transpose, and phases multiply by adding angles. Only the offset survives.",
        },
        "productive_failure": {
            "prompt": r"Design a position encoding $f(x, m)$ for $x\in\mathbb{R}^d$ such that $\langle f(q, m), f(k, n)\rangle$ depends on positions only through $n - m$, for all $q, k, m, n$, and such that $\|f(x, m)\| = \|x\|$. Restrict to linear maps $f(x, m) = A_mx$. What equations must the matrices $A_m$ satisfy, and what family solves them?",
            "canonical_insight": r"Need $A_m^\top A_n = B_{n-m}$ for some family $B$; with $m = n$ this gives $A_m^\top A_m = B_0$, and norm preservation forces $B_0 = I$, so every $A_m$ is orthogonal and $A_m^\top A_n$ depends only on $n - m$. Powers of one orthogonal matrix, $A_m = A^m$, work since they commute: $A_m^\top A_n = A^{n-m}$. The real normal form of an orthogonal matrix is block-diagonal 2-D rotations — exactly RoPE.",
        },
        "practice": {
            1: {
                "prompt": r"Your model rotates each 2-D pair of query and key coordinates by an angle proportional to the token's position, and you extend its context from 2k to 8k tokens. A colleague worries that a query at position 7000 attending to a key at 6990 will score differently from a query at 10 and a key at 0, for identical content. Compute both logits for $d = 2$, $\theta = 0.01$, $q = k = (1, 0)$.",
                "answer_summary": r"Both logits equal $q^\top R((n-m)\theta)k = \cos(-10\cdot0.01) = \cos(0.1) \approx 0.995$. Only the offset $n - m = -10$ matters.",
                "concept_groups": [["0.995", "cos(0.1)", "cos 0.1", "cos(-0.1)", "cos(−0.1)"], ["same", "identical", "equal", "unchanged", "relative", "n - m", "n-m", "n−m", "offset"]],
                "verify_code": r"""import numpy as np
R = lambda t: np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
q = k = np.array([1.0, 0.0]); th = 0.01
s1 = (R(7000 * th) @ q) @ (R(6990 * th) @ k)
s2 = (R(10 * th) @ q) @ (R(0 * th) @ k)
assert np.isclose(s1, s2) and np.isclose(s1, np.cos(0.1))
print('VERIFIED: both logits = cos(0.1) =', round(s1, 5))
""",
                "hints": _hints(
                    r"Norm check: rotated unit vectors stay unit, so the logit is the cosine of the angle between them. What is that angle in each case?",
                    r"In “{quote}”, did you combine the two rotations into one before evaluating?",
                    r"What is $R(a)^\top R(b)$ for planar rotations?",
                    r"Compute the 10-and-0 case first: rotate $q$ by $0.1$, leave $k$ alone, take the dot product.",
                    r"Analog: two clock hands at 3:00 and 3:10 make the same angle as at 9:00 and 9:10; the angle between hands depends only on the time difference. Transfer to positions 7000/6990.",
                ),
            },
            2: {
                "prompt": r"A paper writes position maps as matrix exponentials: $\mathcal{R}_p := \exp(p\,\Omega)$ with $\Omega = \mathrm{blockdiag}\Big(\begin{smallmatrix}0 & -\omega_j\\ \omega_j & 0\end{smallmatrix}\Big)$. Show in two lines that $\mathcal{R}_a^\top\mathcal{R}_b = \mathcal{R}_{b-a}$.",
                "answer_summary": r"$\Omega$ is skew-symmetric, $\Omega^\top = -\Omega$, so $\mathcal{R}_a^\top = \exp(a\Omega)^\top = \exp(a\Omega^\top) = \exp(-a\Omega)$. Since $-a\Omega$ and $b\Omega$ commute, $\exp(-a\Omega)\exp(b\Omega) = \exp((b-a)\Omega) = \mathcal{R}_{b-a}$.",
                "concept_groups": [["skew", "ω^t = -ω", "ω^⊤ = -ω", "omega^t = -omega", "-aω", "−aω", "exp(-a", "e^{-aω}", "transpose of the exponential"], ["commut"]],
                "verify_code": r"""import numpy as np
from scipy.linalg import expm
w = [0.7, 0.13]
Om = np.zeros((4, 4))
for j, wj in enumerate(w):
    Om[2 * j:2 * j + 2, 2 * j:2 * j + 2] = [[0, -wj], [wj, 0]]
assert np.allclose(Om.T, -Om)
Rp = lambda p: expm(p * Om)
for a, b in [(3.0, 8.0), (-2.5, 4.0), (10.0, 1.0)]:
    assert np.allclose(Rp(a).T @ Rp(b), Rp(b - a))
assert np.allclose(Rp(1.0)[:2, :2], [[np.cos(0.7), -np.sin(0.7)], [np.sin(0.7), np.cos(0.7)]])
print('VERIFIED: exp(a Om)^T exp(b Om) = exp((b-a) Om)')
""",
                "hints": _hints(
                    r"Check one block at $p = 1$: what is $\exp$ of $\begin{pmatrix}0 & -\omega\\ \omega & 0\end{pmatrix}$?",
                    r"In “{quote}”, how did you move the transpose inside the exponential?",
                    r"What property of $\Omega$ makes its transpose so simple, and when does $e^Ae^B = e^{A+B}$ hold?",
                    r"Take a $1\times1$ analog: $\exp(a\cdot i\omega)$ with complex conjugate as transpose. Compute $\overline{e^{ia\omega}}e^{ib\omega}$.",
                    r"Analog: for any matrix $N$, $\exp(sN)\exp(tN) = \exp((s+t)N)$ because $sN$ and $tN$ commute; and for skew $N$, $\exp(N)^\top = \exp(-N)$. Chain these two facts.",
                ),
            },
            3: {
                "prompt": r"A variant of your position-rotation scheme also scales each rotation block by $\rho^m$ at position $m$ (with $\rho = 1.001$, to let magnitudes encode position). Is the logit $\langle\rho^mR(m\theta)q,\ \rho^nR(n\theta)k\rangle$ still shift-invariant? Compute it and identify the property that RoPE needs and this variant lacks.",
                "answer_summary": r"Logit $= \rho^{m+n}\,q^\top R((n-m)\theta)k$: it depends on the absolute sum $m + n$, so it is not shift-invariant. RoPE needs the per-position maps to be orthogonal ($A_m^\top A_m = I$); $\rho^mR(m\theta)$ has $A_m^\top A_m = \rho^{2m}I$.",
                "concept_groups": [["ρ^{m+n}", "rho^(m+n)", "rho^{m+n}", "ρ^(m+n)", "m+n", "m + n"], ["orthogonal", "norm", "r^tr = i", "r^⊤r = i", "a^ta", "isometr"]],
                "verify_code": r"""import sympy as sp
m, n, th, rho = sp.symbols('m n theta rho', positive=True)
q = sp.Matrix(sp.symbols('q0:2')); k = sp.Matrix(sp.symbols('k0:2'))
R = lambda t: sp.Matrix([[sp.cos(t), -sp.sin(t)], [sp.sin(t), sp.cos(t)]])
logit = ((rho**m * R(m * th) * q).T * (rho**n * R(n * th) * k))[0]
target = rho**(m + n) * (q.T * R((n - m) * th) * k)[0]
assert sp.simplify(sp.expand_trig(logit - target)) == 0
f = sp.lambdify((m, n), logit.subs({th: 0.3, rho: 1.001, 'q0': 1, 'q1': 0.5, 'k0': -0.2, 'k1': 1}))
assert abs(f(2, 7) - f(102, 107)) > 1e-3
print('VERIFIED: logit = rho^(m+n) q^T R((n-m)theta) k, not shift invariant')
""",
                "hints": _hints(
                    r"Norm check: what is $\|\rho^mR(m\theta)q\|$? Does it depend on $m$?",
                    r"In “{quote}”, what happened to the scalar factors when you transposed and multiplied?",
                    r"Which property of the per-position maps made the original RoPE derivation collapse to $R_{n-m}$?",
                    r"Set $\theta = 0$: the logit is $\rho^{m+n}q^\top k$. Is that shift-invariant?",
                    r"Analog: encoding position by scaling alone, $\langle\rho^mq, \rho^nk\rangle = \rho^{m+n}q^\top k$, clearly depends on $m + n$. Rotations contribute $R(n-m)$; the scale factors don't cancel. Combine both.",
                ),
            },
            4: {
                "prompt": r"To save compute, a teammate applies the position-dependent block rotations $R_{\Theta,m}$ to queries only and leaves keys unrotated, claiming the logit still depends only on relative position. Compute $\langle R_{\Theta,m}q, k\rangle$ and check the claim.",
                "answer_summary": r"$\langle R_{\Theta,m}q, k\rangle = q^\top R_{\Theta,m}^\top k = q^\top R_{\Theta,-m}k$: it depends on the absolute query position $m$ and not at all on the key position $n$. Relativity needs both sides rotated so that $R_m^\top R_n = R_{n-m}$.",
                "concept_groups": [["absolute", "depends on m", "only m", "-m", "−m", "query position"], ["both", "keys too", "rotate the key", "rotate k", "key position"]],
                "verify_code": r"""import numpy as np
R = lambda t: np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
rng = np.random.default_rng(29); q, k = rng.normal(size=2), rng.normal(size=2); th = 0.2
q_only = lambda m, n: (R(m * th) @ q) @ k
both = lambda m, n: (R(m * th) @ q) @ (R(n * th) @ k)
assert not np.isclose(q_only(3, 5), q_only(13, 15))
assert np.isclose(q_only(3, 5), q_only(3, 40))
assert np.isclose(both(3, 5), both(13, 15))
assert np.isclose(q_only(3, 0), q @ R(-3 * th) @ k)
print('VERIFIED: query-only rotation depends on absolute m; rotating both is relative')
""",
                "hints": _hints(
                    r"Bookkeeping: which position indices even appear in the expression $\langle R_{\Theta,m}q, k\rangle$?",
                    r"In “{quote}”, where would the key position n enter the computation?",
                    r"In the full RoPE derivation, the product $R_m^\top R_n$ collapsed to $R_{n-m}$. What is left if one factor is missing?",
                    r"Take $d = 2$, $q = k = e_1$: compute the query-only logit at $m = 0$ and $m = 5$ with the same offset.",
                    r"Analog: measuring the angle between two clock hands only works if both hands move; if only the minute hand moves, the angle tells you the absolute time. Transfer to query-only rotation.",
                ),
            },
        },
        "referee": {
            "claim": r"Let $S$ be a fixed invertible $2\times2$ matrix and encode $\tilde q = S\,R(m\theta)q$, $\tilde k = S\,R(n\theta)k$. Then $\langle\tilde q, \tilde k\rangle$ depends on positions only through $n - m$.",
            "steps": [
                r"$\langle\tilde q, \tilde k\rangle = \big(SR(m\theta)q\big)^\top\big(SR(n\theta)k\big)$.",
                r"Transposing reverses the product: $\big(SR(m\theta)q\big)^\top = q^\top R(m\theta)^\top S^\top$.",
                r"So $\langle\tilde q,\tilde k\rangle = q^\top R(m\theta)^\top\,(S^\top S)\,R(n\theta)\,k$.",
                r"$S^\top S$ is symmetric positive definite, hence commutes with every rotation, so the expression equals $q^\top S^\top S\,R(m\theta)^\top R(n\theta)\,k$.",
                r"Therefore $\langle\tilde q,\tilde k\rangle = q^\top S^\top S\,R((n-m)\theta)\,k$ depends only on $n - m$.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["commut", "scalar multiple", "s^ts = ci", "s^⊤s = ci", "isotropic", "not orthogonal", "diag(2"],
            "explanation": r"A symmetric positive definite matrix commutes with all rotations only if it is a multiple of the identity. For anisotropic $S^\top S$ the rotation cannot be moved past it, and absolute positions leak in.",
            "counterexample": r"$S = \mathrm{diag}(2, 1)$, $q = k = e_1$, $\theta = \pi/2$: at $m = n = 0$ the logit is $\|Se_1\|^2 = 4$; at $m = n = 1$, $R(\pi/2)e_1 = e_2$ and the logit is $\|Se_2\|^2 = 1$. Same offset $0$, different logits.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Theo, who learned sinusoidal position embeddings first and believes RoPE is 'just adding sines and cosines to the vectors'.",
            "opening": r"RoPE adds a sinusoidal signal to each query and key, like the original transformer. So why do people say its logits depend only on relative position?",
            "boundary_conditions": [
                _bc("orthogonal_rotation", r"RoPE multiplies by orthogonal rotations ($R^\top R = I$, $R(\alpha)^\top = R(-\alpha)$); it does not add a vector",
                    ["orthogonal", "r^t r", "r^⊤r", "transpose is the inverse", "inverse", "multipl", "rotate"],
                    r"Isn't RoPE just adding a sinusoid to the vector?"),
                _bc("both_sides", r"The same block-diagonal rotation family (shared frequencies) is applied to both $q$ and $k$",
                    ["both", "q and k", "query and key", "same frequenc", "block"],
                    r"Why not rotate only the query and save half the compute?"),
                _bc("relative_composition", r"Planar rotations compose by adding angles and commute, so $R_m^\top R_n = R_{n-m}$",
                    ["commut", "add angles", "angles add", "n-m", "n − m", "n - m", "relative"],
                    r"Why does the 2-D block structure matter — would arbitrary different rotations per position work?"),
            ],
        },
        "misconceptions": [
            _mis(["rope adds", "add the rotation", "additive position", "adds a sinusoid"], "FALSE_ANALOGY",
                 "RoPE is additive", r"\tilde q = q + p_m,\ \tilde k = k + p_n"),
            _mis(["rotate only the query", "only q is rotated", "keys don't need rotation"], "BOUNDARY_OMISSION",
                 "One-sided rotation is enough", r"\langle R_{\Theta,m}q, k\rangle = g(q, k, n - m)"),
            _mis(["r_m^t r_n = r_{m+n}", "angles add up to m+n", "m+n"], "ALGEBRAIC_SLIP",
                 "Transpose dropped", r"R_{\Theta,m}^\top R_{\Theta,n} = R_{\Theta,m+n}"),
        ],
    },
    "move_scalar_base_case_check": {
        "probe": {
            "prompt": r"Someone claims $\nabla_A\log\det A = A^{-1}$ for invertible $A\in\mathbb{R}^{n\times n}$. You test $n = 1$. What does the check tell you?",
            "options": _opts(
                r"It passes, so the identity is exactly right",
                r"It passes, but a $1\times1$ check cannot distinguish $A^{-1}$ from $A^{-\top}$; the correct gradient is $A^{-\top}$",
                r"It fails: the scalar case gives $1/a^2$",
                r"It fails: the scalar case gives $\log a$",
            ),
            "correct": "B",
            "explanation": r"$\tfrac{d}{da}\log a = 1/a$ matches, but transposes are invisible on scalars. The true gradient is $A^{-\top}$, which a $2\times2$ non-symmetric check exposes.",
        },
        "predict": {
            "prompt": r"Predict: a colleague claims $\mathrm{Var}\big(\sum_{i=1}^d q_ik_i/d\big) = 1$ for unit-variance i.i.d. entries. Without any general proof, what is the fastest mental test you could run, and would $d = 1$ alone settle it?",
        },
        "reading": r"""**The move.** Facing a matrix or tensor identity, first set every dimension to $1$. Matrices become scalars, transposes vanish, products commute.

**Example 1.** Claim: $\nabla_W\|XW - y\|^2 = 2X^\top(XW - y)$. Scalar: $\tfrac{d}{dw}(xw - y)^2 = 2x(xw - y)$. ✓ Consistent.

**Example 2: power counting.** Claim: $\mathrm{Var}\big(\tfrac1d\sum_{i\le d}q_ik_i\big) = 1$. At $d = 1$: $\mathrm{Var}(qk) = 1$. ✓ It passes! At $d = 2$: $\tfrac{2}{4} = \tfrac12$. ✗ So also check how each side scales with $d$: numerator variance $\propto d$, divisor squared $\propto d^2$.

**Blind spots.** Scalars commute and equal their transposes, so a $1\times1$ check cannot catch $(AB)^{-1} = A^{-1}B^{-1}$ or a missing transpose. Follow up with a $2\times2$ non-commuting or non-symmetric example, and always check shapes.

**Self-explanation:** Why is $d = 1$ alone insufficient for a variance-scaling claim, and what is the minimal second case that catches it?""",
        "check": {
            "prompt": r"A colleague claims that averaging $B$ i.i.d. per-example gradients (each with standard deviation $\sigma$) gives gradient noise with standard deviation $\sigma/B$. Which minimal check refutes it?",
            "options": _opts(
                r"$B = 1$: both sides equal $\sigma$",
                r"$B = 2$: $\mathrm{Var}\big(\tfrac{g_1 + g_2}{2}\big) = \sigma^2/2$, so the std is $\sigma/\sqrt2 \ne \sigma/2$",
                r"$B\to\infty$: both sides go to $0$",
                r"No small case can refute it",
            ),
            "correct": "B",
            "explanation": r"$B = 1$ is degenerate and passes any formula of the form $\sigma/B^p$; the first case that exercises the scaling is $B = 2$, which pins the exponent at $p = \tfrac12$.",
        },
        "productive_failure": {
            "prompt": r"You're handed: 'For $X\in\mathbb{R}^{n\times d}$ with i.i.d. $\mathcal{N}(0,1)$ entries, $\mathbb{E}\|X^\top X\|_F^2 = nd(n + d + 1)$.' Without deriving the general case first, decide how much to trust it using the smallest cases you can compute by hand. Then try to prove it.",
            "canonical_insight": r"$(n,d) = (1,1)$: $\mathbb{E}x^4 = 3 = 1\cdot1\cdot3$ ✓. $(2,1)$: $\mathbb{E}(x_1^2 + x_2^2)^2 = 8 = 2\cdot1\cdot4$ ✓. $(1,2)$: $\|xx^\top\|_F^2 = (x_1^2 + x_2^2)^2$, also $8$ ✓. Proof: diagonal entries give $d(n^2 + 2n)$, off-diagonal give $d(d-1)n$; total $nd(n + d + 1)$. Asymmetric small cases test both scalings before you invest in a proof.",
        },
        "practice": {
            1: {
                "prompt": r"A colleague's notes claim the gradient of $L(W) = \tfrac12\|XW - Y\|_F^2$ (with $X\in\mathbb{R}^{n\times d}$, $W\in\mathbb{R}^{d\times k}$) is $X(XW - Y)^\top$. Before trusting it, test it. Which test passes, which fails, and what is the correct gradient?",
                "answer_summary": r"The $1\times1$ scalar test passes: $\tfrac{d}{dw}\tfrac12(xw - y)^2 = x(xw - y)$. The shape test fails: $X(XW - Y)^\top$ is $n\times n$, but $\nabla_WL$ must be $d\times k$. Correct: $\nabla_WL = X^\top(XW - Y)$.",
                "concept_groups": [["shape", "dimension", "d×k", "d x k", "n×n", "n x n"], ["x^t(xw - y)", "x^t(xw-y)", "x^⊤(xw-y)", "x^⊤(xw - y)", "x^t (xw - y)", "x^\\top(xw - y)", "x^\\top (xw - y)", "x^\\top(xw-y)"]],
                "verify_code": r"""import sympy as sp
n, d, k = 3, 2, 2
X = sp.Matrix(n, d, sp.symbols('x0:6')); W = sp.Matrix(d, k, sp.symbols('w0:4')); Y = sp.Matrix(n, k, sp.symbols('y0:6'))
R = X * W - Y
L = sum(e**2 for e in R) / 2
G = sp.Matrix(d, k, lambda i, j: sp.diff(L, W[i, j]))
assert sp.simplify(G - X.T * R) == sp.zeros(d, k)
assert (X * R.T).shape == (n, n) != G.shape
print('VERIFIED: grad = X^T (XW - Y); claimed X (XW - Y)^T has shape (3, 3)')
""",
                "hints": _hints(
                    r"Shape check: what shape must $\nabla_WL$ have, and what shape does $X(XW - Y)^\top$ have?",
                    r"In “{quote}”, which test did you run, and is that test able to see transposes?",
                    r"After the scalar case passes, what second, cheap check exposes misplaced transposes?",
                    r"Write the $1\times1$ case, then the shapes for $n = 3$, $d = 2$, $k = 2$ next to each factor.",
                    r"Analog: claim $\nabla_x\tfrac12\|Ax - b\|^2 = A(Ax - b)$: the scalar check passes, but for $A\in\mathbb{R}^{3\times2}$, $A(Ax - b)$ is not even defined; the fix is $A^\top(Ax - b)$. Transfer to the matrix case.",
                ),
            },
            2: {
                "prompt": r"Code under review: `out = einsum('hqd,hkd->hqk', Q, K) / d**0.5`, where `d` is the per-head dimension, `H` the number of heads, and $Q, K$ have i.i.d. unit-variance entries. A reviewer claims each entry of `out` has variance $H$ 'because there are $H$ heads'. Settle it with the smallest informative case.",
                "answer_summary": r"Each `out[h, q, k]` contracts only over `d` ($h$ appears in the output, so it is a batch index): variance $d/d = 1$, independent of $H$. Minimal case: $H = 2$, $d = 1$ gives `out[h] = Q_h K_h`, two separate unit-variance entries, not a sum over heads.",
                "concept_groups": [["variance 1", "var 1", "= 1", "unit variance", "is 1", "variance of 1"], ["not summed over h", "no sum over h", "not contracted", "per head", "independent of h", "h stays", "batch", "output index"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(30)
for H in [1, 4, 16]:
    d = 16
    Q = rng.normal(size=(H, 64, d)); K = rng.normal(size=(H, 64, d))
    out = np.einsum('hqd,hkd->hqk', Q, K) / d**0.5
    assert out.shape == (H, 64, 64) and abs(out.var() - 1) < 0.1
print('VERIFIED: einsum output variance ~1 regardless of H')
""",
                "hints": _hints(
                    r"Index check: which letters disappear between the inputs and the output of the einsum?",
                    r"In “{quote}”, did you treat h as a summed index?",
                    r"Only contracted indices produce sums. How many terms are summed for each output entry, and what is each term's variance?",
                    r"Set $d = 1$, $H = 2$: write out every output entry explicitly.",
                    r"Analog: `einsum('bi,bi->b', A, B)` sums over `i` only; the batch size never enters the per-entry variance. Same for `h` here.",
                ),
            },
            3: {
                "prompt": r"A derivation in your notes uses $(AB)^{-1} = A^{-1}B^{-1}$. Contrast what a $1\times1$ check and a $2\times2$ check reveal about it, and state the correct identity.",
                "answer_summary": r"$1\times1$ passes, since scalars commute: $(ab)^{-1} = a^{-1}b^{-1}$. A $2\times2$ check with non-commuting matrices fails, e.g. $A = \begin{pmatrix}1&1\\0&1\end{pmatrix}$, $B = \begin{pmatrix}1&0\\1&1\end{pmatrix}$. Correct: $(AB)^{-1} = B^{-1}A^{-1}$.",
                "concept_groups": [["commut"], ["b^{-1}a^{-1}", "b^-1 a^-1", "b^{-1} a^{-1}", "b^-1a^-1", "reverse"], ["2×2", "2x2", "2 by 2", "don't commute", "do not commute", "non-commuting", "noncommuting"]],
                "verify_code": r"""import sympy as sp
A = sp.Matrix([[1, 1], [0, 1]]); B = sp.Matrix([[1, 0], [1, 1]])
assert (A * B).inv() != A.inv() * B.inv()
assert (A * B).inv() == B.inv() * A.inv()
a, b = sp.symbols('a b', nonzero=True)
assert sp.simplify(1 / (a * b) - (1 / a) * (1 / b)) == 0
print('VERIFIED: scalar check passes, 2x2 check fails; (AB)^-1 = B^-1 A^-1')
""",
                "hints": _hints(
                    r"Verify the candidate directly: multiply $AB$ by $A^{-1}B^{-1}$. Does the product collapse to $I$, and if not, which pair of factors fails to meet?",
                    r"In “{quote}”, which property of scalars did your check silently rely on?",
                    r"A scalar check cannot see the order of factors. Which kind of matrix pair would?",
                    r"Compute $AB$, $(AB)^{-1}$, and $A^{-1}B^{-1}$ for the two shear matrices.",
                    r"Analog: $(AB)^\top = A^\top B^\top$ passes for scalars but fails for $A = \begin{pmatrix}0&1\\0&0\end{pmatrix}$, $B = A^\top$; the correct rule reverses the order. Apply the same idea to inverses.",
                ),
            },
            4: {
                "prompt": r"A teammate 'verifies' that $\mathbb{E}[\max(Z_1, \dots, Z_n)] = 0$ for i.i.d. $\mathcal{N}(0,1)$ by checking $n = 1$ ($\mathbb{E}Z_1 = 0$ ✓) and concludes it holds for all $n$. Diagnose the verification and give the value at the first informative case.",
                "answer_summary": r"$n = 1$ is degenerate: the max of one variable involves no selection, so it cannot test a claim about maxima. The first informative case $n = 2$ gives $\mathbb{E}\max = 1/\sqrt\pi \approx 0.564 \ne 0$.",
                "concept_groups": [["n=2", "n = 2", "two"], ["0.564", "1/√π", "1/sqrt(pi)", "0.56"], ["degenerate", "trivial", "max of one", "no selection", "doesn't exercise", "does not exercise"]],
                "verify_code": r"""import numpy as np
from scipy import integrate, stats
emax = lambda n: integrate.quad(lambda x: x * n * stats.norm.pdf(x) * stats.norm.cdf(x) ** (n - 1), -10, 10)[0]
assert abs(emax(1)) < 1e-10
assert abs(emax(2) - 1 / np.sqrt(np.pi)) < 1e-8
print('VERIFIED: E max n=1 is 0, n=2 is 1/sqrt(pi) =', round(emax(2), 4))
""",
                "hints": _hints(
                    r"Does the operation in the claim (taking a maximum) actually do anything when $n = 1$?",
                    r"In “{quote}”, did your base case exercise the feature the claim is about?",
                    r"A base case is informative only if it contains the structure being tested. What is the smallest $n$ with a genuine choice?",
                    r"Compute $\mathbb{E}\max(Z_1, Z_2)$ using $\max(a,b) = \tfrac{a+b}2 + \tfrac{|a-b|}2$.",
                    r"Analog: checking '$\mathrm{Var}(\text{sum of } n) = n^2\sigma^2$' at $n = 1$ passes ($\sigma^2$) but $n = 2$ gives $2\sigma^2 \ne 4\sigma^2$. Pick the first case that exercises the max.",
                ),
            },
        },
        "referee": {
            "claim": r"For all invertible $A, B\in\mathbb{R}^{n\times n}$: $(AB)^{-1} = A^{-1}B^{-1}$.",
            "steps": [
                r"Check $n = 1$: $(ab)^{-1} = \tfrac1{ab} = \tfrac1a\cdot\tfrac1b$. ✓",
                r"Check diagonal matrices: products and inverses act entrywise on the diagonals, so the identity holds. ✓",
                r"Both sides are continuous functions of $(A, B)$ on the open set of invertible pairs.",
                r"Diagonalizable matrices are dense, and for diagonalizable $A$ and $B$ the identity reduces, eigenvalue by eigenvalue, to the scalar case.",
                r"By density and continuity, $(AB)^{-1} = A^{-1}B^{-1}$ for all invertible $A, B$.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["simultaneous", "commut", "same eigenbasis", "different eigenvectors", "shared basis", "common basis", "b^{-1}a^{-1}"],
            "explanation": r"Diagonalizing $A$ and $B$ separately uses different eigenbases; the reduction to scalars needs a *common* eigenbasis (simultaneous diagonalizability, i.e. commuting matrices). The base cases chosen all commute, so they cannot detect the order error.",
            "counterexample": r"$A = \begin{pmatrix}1&1\\0&1\end{pmatrix}$, $B = \begin{pmatrix}1&0\\1&1\end{pmatrix}$: $(AB)^{-1} = \begin{pmatrix}1&-1\\-1&2\end{pmatrix}$ but $A^{-1}B^{-1} = \begin{pmatrix}2&-1\\-1&1\end{pmatrix}$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Sasha, a fast-moving researcher who treats 'it works for $d = 1$' as a proof of any matrix identity.",
            "opening": r"I always check my matrix identities in the $1\times1$ case. If it works there, it works — what more could a bigger case possibly reveal?",
            "boundary_conditions": [
                _bc("scalar_blind_spots", r"The scalar case checks constants and scaling powers but is blind to transposes and the order of non-commuting factors",
                    ["transpose", "commut", "order", "blind", "can't see", "cannot see"],
                    r"$(AB)^\top = A^\top B^\top$ works for $1\times1$ numbers — isn't that evidence?"),
                _bc("second_case", r"Add a second, informative base case ($d = 2$, $n = 2$, or a non-commuting $2\times2$) to expose $d$-scaling and order effects",
                    ["d=2", "d = 2", "2×2", "2x2", "second case", "n=2", "n = 2", "two"],
                    r"$\mathrm{Var}\big(\sum_{i\le d}q_ik_i/d\big) = 1$ passes at $d = 1$. Done?"),
                _bc("shape_check", r"Also check shapes / dimensions of every factor",
                    ["shape", "dimension", "rows", "columns", "conform"],
                    r"My gradient $X(XW - Y)^\top$ matches the scalar version — so it's right?"),
            ],
        },
        "misconceptions": [
            _mis(["works for d=1 so", "scalar case proves", "checked n=1 so it holds", "true for 1x1 so"], "BOUNDARY_OMISSION",
                 "Base case as proof", r"\text{identity holds for } n = 1 \implies \text{holds for all } n"),
            _mis(["scalars commute so matrices", "same as numbers", "matrices behave like numbers"], "FALSE_ANALOGY",
                 "Scalar intuition transfers to matrices", r"AB = BA\ \ \forall A, B"),
            _mis(["(ab)^{-1} = a^{-1}b^{-1}", "(ab)^-1 = a^-1 b^-1", "inverse of a product is the product of inverses"], "ALGEBRAIC_SLIP",
                 "Inverse without reversal", r"(AB)^{-1} = A^{-1}B^{-1}"),
        ],
    },
    # ------------------------------------------------------------------ Cluster D
    "prop_bellman_sup_norm_contraction": {
        "probe": {
            "prompt": r"With discount $\gamma = 0.9$, two value functions satisfy $\|U - V\|_\infty = 10$. What is the best guaranteed bound on $\|\mathcal{T}^*U - \mathcal{T}^*V\|_\infty$ for the Bellman optimality operator?",
            "options": _opts(r"$10$", r"$9$", r"$0.9$", r"$1$"),
            "correct": "B",
            "explanation": r"$\mathcal{T}^*$ is a $\gamma$-contraction in the sup norm: $\|\mathcal{T}^*U - \mathcal{T}^*V\|_\infty \le 0.9\times10 = 9$.",
        },
        "predict": {
            "prompt": r"Predict: how many value-iteration sweeps does it take to shrink the error by $1000\times$ with $\gamma = 0.99$ versus $\gamma = 0.5$? And could the $\max$ over actions — which can switch between iterates — ever amplify differences and break the shrinkage?",
        },
        "reading": r"""**Base case: one state, one action.** $(\mathcal{T}V) = r + \gamma V$, so $|\mathcal{T}U - \mathcal{T}V| = \gamma|U - V|$, with fixed point $V^* = r/(1 - \gamma)$.

**Add actions and states.** $(\mathcal{T}^*V)(s) = \max_a\big[R(s,a) + \gamma\sum_{s'}P(s'\mid s,a)V(s')\big]$.

**Lemma: max is non-expansive.** $|\max_af(a) - \max_ag(a)| \le \max_a|f(a) - g(a)|$. If $f$ peaks at $a_1$, then $\max f - \max g \le f(a_1) - g(a_1)$; swap roles for the other side.

**Apply it.** Rewards cancel inside the difference:
$$|\mathcal{T}^*U(s) - \mathcal{T}^*V(s)| \le \gamma\max_a\Big|\sum_{s'}P(s'\mid s,a)\,(U - V)(s')\Big| \le \gamma\|U - V\|_\infty,$$
because $P(\cdot\mid s,a)$ is a probability vector: an average never exceeds the largest absolute entry. Take $\sup_s$.

**Conclude.** $(\mathbb{R}^{|S|}, \|\cdot\|_\infty)$ is complete, so the contraction principle gives a unique $V^*$ and $\|V_k - V^*\|_\infty \le \gamma^k\|V_0 - V^*\|_\infty$.

**Self-explanation:** Which property of $P$ was needed, and would the argument survive if each row of $P$ summed to $1.2$?""",
        "check": {
            "prompt": r"An operator on bounded functions $f: \mathcal{S}\to\mathbb{R}$ is $(\mathcal{B}f)(s) = \sup_a\big\{c(s,a) + \beta\,\mathbb{E}_{s'\sim p(\cdot\mid s,a)}f(s')\big\}$ with $\beta = 0.95$ and $\|c\|_\infty \le 1$. Starting from $f_0 \equiv 0$, a valid bound on $\|f_k - f^\star\|_\infty$ is:",
            "options": _opts(
                r"$20\,(0.95)^k$",
                r"$(0.95)^k$",
                r"$20/k$",
                r"None: a $\sup$ over infinitely many actions breaks the contraction",
            ),
            "correct": "A",
            "explanation": r"$\|f^\star\|_\infty \le \|c\|_\infty/(1 - \beta) = 20$, so $\|f_0 - f^\star\|_\infty \le 20$, and $\beta$-contraction gives $20(0.95)^k$. Sup is non-expansive just like max.",
        },
        "productive_failure": {
            "prompt": r"An engineer proposes an 'optimistic' backup for a 2-state MDP: $(\mathcal{T}_{\text{opt}}V)(s) = \max_a\big[R(s,a) + \gamma\max_{s'}V(s')\big]$ — a max over next states instead of an expectation. Is it still a contraction in some norm? If so, what is its fixed point for $R \equiv 1$, and how does that compare with the standard operator's?",
            "canonical_insight": r"Yes: $|\max_{s'}U(s') - \max_{s'}V(s')| \le \|U - V\|_\infty$, so $\mathcal{T}_{\text{opt}}$ is still a $\gamma$-contraction in $\|\cdot\|_\infty$. With $R\equiv1$ both operators have fixed point $1/(1-\gamma)$, but in general the optimistic one converges to a different (larger) fixed point. What the proof really uses is that the backup is monotone and $1$-Lipschitz in $\|\cdot\|_\infty$, a property shared by expectations, max and min.",
        },
        "practice": {
            1: {
                "prompt": r"Your value iteration with $\gamma = 0.95$ currently shows $\|V_k - V_{k-1}\|_\infty = 0.5$. Bound the distance $\|V_k - V^*\|_\infty$, and estimate how many further sweeps guarantee $\|V - V^*\|_\infty \le 10^{-3}$.",
                "answer_summary": r"$\|V_k - V^*\| \le \|V_k - V_{k+1}\| + \|V_{k+1} - V^*\| \le \gamma\|V_k - V_{k-1}\| + \gamma\|V_k - V^*\|$, so $\|V_k - V^*\|_\infty \le \tfrac{\gamma}{1-\gamma}\cdot0.5 = 19\times0.5 = 9.5$. Need $9.5\cdot0.95^j \le 10^{-3}$: $j \ge \ln(9500)/\ln(1/0.95) \approx 178.6$, so $179$ sweeps.",
                "concept_groups": [["9.5"], ["179", "178"], ["γ/(1-γ)", "gamma/(1-gamma)", "γ/(1−γ)", "19", "geometric"]],
                "verify_code": r"""import numpy as np
g = 0.95
bound = g / (1 - g) * 0.5
j = int(np.ceil(np.log(bound / 1e-3) / np.log(1 / g)))
assert np.isclose(bound, 9.5) and j == 179
rng = np.random.default_rng(31)
S, A = 6, 3
P = rng.random((S, A, S)); P /= P.sum(-1, keepdims=True); R = rng.normal(size=(S, A))
T = lambda V: (R + g * P @ V).max(1)
Vs = np.zeros(S)
for _ in range(3000):
    Vs = T(Vs)
V = rng.normal(size=S) * 50
for _ in range(20):
    Vp, V = V, T(V)
    assert np.abs(V - Vs).max() <= g / (1 - g) * np.abs(V - Vp).max() + 1e-9
print('VERIFIED: bound 9.5, 179 further sweeps; a-posteriori bound holds on a random MDP')
""",
                "hints": _hints(
                    r"Units check: the observed step size is $0.5$; should the distance to the optimum be larger or smaller than that when $\gamma$ is close to $1$?",
                    r"In “{quote}”, did you bound the distance to the optimum by the last step alone, without the geometric tail?",
                    r"The remaining error is a sum of all future steps, each a factor $\gamma$ smaller. What does that series add up to?",
                    r"Do the 1-state chain $V \mapsto 1 + 0.95V$ starting at $0$: compare $|V_1 - V_0|$ with $|V_1 - V^*|$.",
                    r"Analog: with $\gamma = 0.9$ and last step $1$, the bound is $\tfrac{0.9}{0.1} = 9$, and reaching $10^{-2}$ takes $\lceil\ln 900/\ln(1/0.9)\rceil = 65$ sweeps. Transfer with $0.95$ and $0.5$.",
                ),
            },
            2: {
                "prompt": r"Cost-minimization notation: $(\mathcal{L}J)(x) = \min_u\big\{g(x,u) + \alpha\sum_yp_{xy}(u)J(y)\big\}$ with $\alpha = 0.8$. Show $\|\mathcal{L}J - \mathcal{L}J'\|_\infty \le 0.8\|J - J'\|_\infty$. What, if anything, changes compared with the max version?",
                "answer_summary": r"Min is also non-expansive: $|\min_uf(u) - \min_uh(u)| \le \max_u|f(u) - h(u)|$. Costs cancel, and $\sum_yp_{xy}(u)(J - J')(y)$ is an average bounded by $\|J - J'\|_\infty$. So $\mathcal{L}$ is a $0.8$-contraction; swapping max for min changes nothing in the proof.",
                "concept_groups": [["min", "minimum"], ["nonexpansive", "non-expansive", "1-lipschitz", "max |f", "max|f", "≤ max"], ["probabilit", "sum to 1", "sums to 1", "stochastic", "average", "convex combination"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(32)
S, A, a = 5, 4, 0.8
P = rng.random((S, A, S)); P /= P.sum(-1, keepdims=True); g = rng.normal(size=(S, A))
L = lambda J: (g + a * P @ J).min(1)
worst = 0.0
for _ in range(2000):
    J1, J2 = rng.normal(size=S) * 10, rng.normal(size=S) * 10
    worst = max(worst, np.abs(L(J1) - L(J2)).max() / np.abs(J1 - J2).max())
assert worst <= 0.8 + 1e-12
print('VERIFIED: min-Bellman operator is a 0.8-contraction (worst ratio', round(worst, 3), ')')
""",
                "hints": _hints(
                    r"Sanity check: if $J' = J + c$ for a constant $c$, what is $\mathcal{L}J' - \mathcal{L}J$?",
                    r"In “{quote}”, how did you handle the possibility that the minimizing u differs for J and J′?",
                    r"Is there a min-version of the inequality $|\max f - \max g| \le \max|f - g|$?",
                    r"Single state, two actions: compare $\min(f_1, f_2) - \min(h_1, h_2)$ with $\max(|f_1 - h_1|, |f_2 - h_2|)$ for a few numbers.",
                    r"Analog: $\min$ satisfies $\min f = -\max(-f)$, so $|\min f - \min h| = |\max(-f) - \max(-h)| \le \max|f - h|$. Then repeat the averaging step with $\alpha = 0.8$.",
                ),
            },
            3: {
                "prompt": r"A colleague measures value-iteration progress in the Euclidean norm instead of the sup norm. Construct a 2-state example where $\|\mathcal{T}U - \mathcal{T}V\|_2 > \gamma\|U - V\|_2$, and explain why the sup norm never has this problem.",
                "answer_summary": r"One action, $R = 0$, both states transition to state 1: $\mathcal{T}V = \gamma(V_1, V_1)$. With $U - V = (1, 0)$: $\|U - V\|_2 = 1$ but $\|\mathcal{T}U - \mathcal{T}V\|_2 = \gamma\sqrt2 > \gamma$. In $\|\cdot\|_\infty$ each entry is an average of entries of $U - V$, so it is at most $\gamma\|U - V\|_\infty$.",
                "concept_groups": [["√2", "sqrt(2)", "1.41", "γ√2"], ["sup", "∞", "max norm", "infinity norm", "l∞", "l-infinity"], ["not a contraction", "fails", "> γ", "exceeds", "larger than γ"]],
                "verify_code": r"""import numpy as np
g = 0.9
P = np.array([[1.0, 0.0], [1.0, 0.0]])
T = lambda V: g * P @ V
U, V = np.array([1.0, 0.0]), np.zeros(2)
assert np.isclose(np.linalg.norm(T(U) - T(V)), g * np.sqrt(2)) and g * np.sqrt(2) > g * np.linalg.norm(U - V)
assert np.abs(T(U) - T(V)).max() <= g * np.abs(U - V).max()
print('VERIFIED: L2 ratio gamma*sqrt(2) > gamma; sup-norm ratio <= gamma')
""",
                "hints": _hints(
                    r"Norm check: compute $\|(1,1)\|_2$ and $\|(1,1)\|_\infty$. Which norm penalizes copying one value into two states?",
                    r"In “{quote}”, which step of the contraction proof did you assume works in every norm?",
                    r"In the sup-norm proof, an average of entries is bounded by the largest entry. What is the analogous statement in the 2-norm, and does it hold?",
                    r"Use two states that both transition deterministically to state 1, with zero reward.",
                    r"Analog: the averaging matrix $\begin{pmatrix}1&0\\1&0\end{pmatrix}$ has $\infty$-norm $1$ but spectral norm $\sqrt2$. Multiply by $\gamma$ and compare the two norms.",
                ),
            },
            4: {
                "prompt": r"For an undiscounted continuing task, a colleague runs value iteration with $\gamma = 1$ on a 2-state cycle that pays reward $1$ per step, and cites the usual value-iteration convergence guarantee to promise convergence. What actually happens, and which hypothesis fails?",
                "answer_summary": r"With $\gamma = 1$ the operator is only non-expansive (Lipschitz constant $1$), not a contraction. Here $V_{k+1} = 1 + V_k$ componentwise, so $V_k = k(1,1)$ diverges and there is no fixed point.",
                "concept_groups": [["γ = 1", "gamma = 1", "γ=1", "gamma=1", "not < 1", "not less than 1", "no discount", "undiscounted"], ["diverge", "grows", "no fixed point", "unbounded", "→ ∞", "-> ∞", "infinity", "blows up"]],
                "verify_code": r"""import numpy as np
P = np.array([[0.0, 1.0], [1.0, 0.0]]); r = np.ones(2)
V = np.zeros(2)
for k in range(1, 101):
    V = r + 1.0 * P @ V
    assert np.allclose(V, [k, k])
U = np.array([3.0, -1.0]); W = np.zeros(2)
assert np.isclose(np.abs((r + P @ U) - (r + P @ W)).max(), np.abs(U - W).max())
print('VERIFIED: gamma = 1 gives V_k = k(1,1) (diverges); Lipschitz constant exactly 1')
""",
                "hints": _hints(
                    r"Limit check: what is $\sum_{t\ge0}\gamma^t$ when $\gamma = 1$?",
                    r"In “{quote}”, which number did the contraction proof need strictly below one?",
                    r"What is the contraction factor of $V \mapsto r + \gamma PV$ in the sup norm, as a function of $\gamma$?",
                    r"Run three iterations by hand from $V_0 = (0, 0)$.",
                    r"Analog: $x \mapsto x + 1$ on $\mathbb{R}$ is an isometry (Lipschitz $1$) with no fixed point; iterates march off to infinity. Map this onto the undiscounted backup.",
                ),
            },
        },
        "referee": {
            "claim": r"The Bellman optimality operator is a $\gamma$-contraction in the $\ell_1$ norm $\|V\|_1 = \sum_s|V(s)|$.",
            "steps": [
                r"For each $s$, $|(\mathcal{T}^*U)(s) - (\mathcal{T}^*V)(s)| \le \gamma\max_a\sum_{s'}P(s'\mid s,a)\,|U(s') - V(s')|$.",
                r"Let $a_s$ attain that max, so the bound equals $\gamma\sum_{s'}P(s'\mid s,a_s)\,|U(s') - V(s')|$.",
                r"Summing over $s$: $\|\mathcal{T}^*U - \mathcal{T}^*V\|_1 \le \gamma\sum_{s'}|U(s') - V(s')|\sum_sP(s'\mid s,a_s)$.",
                r"Since $P(\cdot\mid s,a_s)$ is a probability distribution, $\sum_sP(s'\mid s,a_s) = 1$.",
                r"Therefore $\|\mathcal{T}^*U - \mathcal{T}^*V\|_1 \le \gamma\|U - V\|_1$.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["column", "row", "sum over s", "doubly stochastic", "column sums", "rows sum", "over s'"],
            "explanation": r"$P(\cdot\mid s,a)$ sums to $1$ over the *next* state $s'$ (rows). Step 4 sums over the *current* state $s$ (columns), and column sums of a stochastic matrix can be anything in $[0, |S|]$.",
            "counterexample": r"One action, $R = 0$, both states go to state 1: $\mathcal{T}V = \gamma(V_1, V_1)$. With $U - V = (1, 0)$: $\|\mathcal{T}U - \mathcal{T}V\|_1 = 2\gamma > \gamma = \gamma\|U - V\|_1$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Jordan, an RL practitioner who suspects that the max over actions can amplify value differences when the greedy action switches between iterates.",
            "opening": r"When $U$ and $V$ prefer different actions, the max jumps from one branch to another, so $\mathcal{T}^*U - \mathcal{T}^*V$ could be bigger than $U - V$. Why is value iteration still guaranteed to converge?",
            "boundary_conditions": [
                _bc("max_nonexpansive", r"Max is non-expansive: $|\max_af(a) - \max_ag(a)| \le \max_a|f(a) - g(a)|$, even when the argmax switches",
                    ["nonexpansive", "non-expansive", "1-lipschitz", "max |f", "max|f", "|max f - max g|", "argmax switches"],
                    r"The max can switch actions between $U$ and $V$ — can't that jump amplify the difference?"),
                _bc("stochastic_rows", r"Each $P(\cdot\mid s,a)$ is a probability distribution, so the expectation of $U - V$ is bounded by $\|U - V\|_\infty$",
                    ["probability", "sums to 1", "sum to 1", "stochastic", "average", "convex combination"],
                    r"What if a bug made the transition rows sum to $1.2$?"),
                _bc("gamma_complete_supnorm", r"$\gamma < 1$, the sup norm specifically, and completeness of $(\mathbb{R}^{|S|}, \|\cdot\|_\infty)$ give a unique fixed point",
                    ["γ < 1", "gamma < 1", "γ<1", "complete", "sup norm", "infinity norm", "∞-norm", "sup-norm"],
                    r"With $\gamma = 1$, or measuring in the 2-norm, does the guarantee still hold?"),
            ],
        },
        "misconceptions": [
            _mis(["max can amplify", "max is not lipschitz", "switching actions breaks", "argmax switch makes it bigger"], "FALSE_ANALOGY",
                 "Max amplifies differences", r"\|\mathcal{T}^*U - \mathcal{T}^*V\|_\infty > \gamma\|U - V\|_\infty \text{ when argmax switches}"),
            _mis(["contraction in l2", "euclidean norm contraction", "any norm works", "contraction in every norm"], "BOUNDARY_OMISSION",
                 "Norm-agnostic contraction", r"\|\mathcal{T}^*U - \mathcal{T}^*V\|_2 \le \gamma\|U - V\|_2"),
            _mis(["γ = 1 still converges", "undiscounted still contraction", "gamma = 1 is fine"], "BOUNDARY_OMISSION",
                 "Discount optional", r"\gamma = 1 \implies \mathcal{T}^* \text{ has a unique fixed point}"),
        ],
    },
    "prop_qlearning_maximization_bias": {
        "probe": {
            "prompt": r"In state $s'$, four actions all have true value $Q(s', a) = 0$. Their estimates are $\hat Q(s', a) = \varepsilon_a$ with i.i.d. $\varepsilon_a\sim\mathcal{N}(0,1)$. What is $\mathbb{E}[\max_a\hat Q(s', a)]$?",
            "options": _opts(r"$0$", r"$\approx 1.03$", r"$\approx -1.03$", r"$4$"),
            "correct": "B",
            "explanation": r"The expected maximum of 4 i.i.d. standard normals is about $1.03$. Every estimate is unbiased, but the max of them is not: $\mathbb{E}\max \ge \max\mathbb{E} = 0$.",
        },
        "predict": {
            "prompt": r"Predict: in a state where every action is equally useless (true value $0$), what value does the Q-learning target bootstrap toward if the action-value estimates are noisy but unbiased? What happens over many updates?",
        },
        "reading": r"""**Base case.** One next state, two actions, true values $0$, estimates $\hat Q(a) = \varepsilon_a$ with $\varepsilon_a$ i.i.d. $\mathcal{N}(0, \sigma^2)$. The target uses $\max_a\hat Q(a)$:
$$\mathbb{E}\big[\max(\varepsilon_1, \varepsilon_2)\big] = \sigma/\sqrt\pi > 0 = \max_a\mathbb{E}\hat Q(a).$$
This is $\mathbb{E}[\max] \ge \max\mathbb{E}$, from convexity of the max.

**Why.** The same noisy numbers both *select* the action and *evaluate* it. Whichever action got lucky noise wins, so the winner's estimate is biased upward, even though each estimate alone is unbiased.

**Bootstrapping propagates it.** The biased target becomes the next estimate, which feeds earlier states' targets. Each backup adds roughly $\gamma b$ (with $b$ the per-state bias), and through the contraction the fixed point drifts by up to about $\gamma b/(1-\gamma)$.

**Size.** The bias grows with noise $\sigma$ and with the number of near-tied actions (about $\sigma\sqrt{2\ln n}$ for many i.i.d. actions). It vanishes when one action is clearly best.

**Self-explanation:** Why is the selected action's estimate biased upward even though every individual estimate is unbiased?""",
        "check": {
            "prompt": r"Bandit notation: arms $i = 1, \dots, K$ with sample means $\bar X_i$ from $n$ pulls each; all true means equal $\mu$. The 'winner's curse' $\mathbb{E}[\max_i\bar X_i] - \mu$ is:",
            "options": _opts(
                r"$0$, because each $\bar X_i$ is unbiased",
                r"Positive; it grows with $K$ and shrinks with $n$",
                r"Negative",
                r"Positive and independent of $n$",
            ),
            "correct": "B",
            "explanation": r"Same maximization bias: with noise std $\sigma/\sqrt n$, the gap is $(\sigma/\sqrt n)\,\mathbb{E}[\max\text{ of }K\text{ standard normals}]$ (for Gaussian noise), increasing in $K$ and decreasing in $n$.",
        },
        "productive_failure": {
            "prompt": r"Ten actions all have true value $0$, and you have two independent sets of noisy estimates, $Q^A$ and $Q^B$. Design an estimator of $\max_a\mathbb{E}[Q(a)]$ that is not biased upward, using only $Q^A$ and $Q^B$. Analyze its bias here, and think about whether it could ever be biased *downward* in other situations.",
            "canonical_insight": r"Select with one, evaluate with the other: $a^* = \arg\max_aQ^A(a)$, report $Q^B(a^*)$. Since $Q^B$'s noise is independent of $a^*$, $\mathbb{E}[Q^B(a^*)\mid a^*] = Q(a^*)$, so $\mathbb{E} = \mathbb{E}[Q(a^*)] \le \max_aQ(a)$. Here it is exactly $0$ (unbiased). When true values differ, picking a suboptimal $a^*$ makes it biased downward. This is the double estimator behind Double DQN.",
        },
        "practice": {
            1: {
                "prompt": r"Your DQN's predicted Q-values keep climbing well above the actual Monte-Carlo returns in an environment with 6 actions whose true values are all similar. Quantify the one-step target bias when true values are all $0$, reward is $0$, $\gamma = 0.99$, and estimates carry i.i.d. $\mathcal{N}(0, 0.25)$ noise.",
                "answer_summary": r"$\mathbb{E}[\max\text{ of 6 i.i.d. }\mathcal{N}(0,1)] \approx 1.267$, so with $\sigma = 0.5$ the max is biased by $\approx0.634$, and the target by $\gamma\times0.634 \approx 0.627$. Selection on noise ($\mathbb{E}\max \ge \max\mathbb{E}$) causes the overestimation, and bootstrapping compounds it.",
                "concept_groups": [["0.63", "0.627", "0.634"], ["max", "e[max", "convex", "jensen", "selection", "maximization"], ["noise", "overestimat"]],
                "verify_code": r"""import numpy as np
from scipy import integrate, stats
n = 6
e6 = integrate.quad(lambda x: x * n * stats.norm.pdf(x) * stats.norm.cdf(x) ** (n - 1), -10, 10)[0]
assert abs(e6 - 1.2672) < 1e-3
bias = 0.99 * 0.5 * e6
assert abs(bias - 0.627) < 1e-3
print('VERIFIED: E max6 =', round(e6, 4), 'target bias =', round(bias, 4))
""",
                "hints": _hints(
                    r"Sign check: can the expected maximum of six zero-mean noises be $\le 0$?",
                    r"In “{quote}”, did you assume the noise averages out after taking the max?",
                    r"Which inequality relates the expectation of a maximum to the maximum of expectations?",
                    r"Start with 2 actions: $\mathbb{E}\max(\varepsilon_1, \varepsilon_2) = \sigma/\sqrt\pi$. Then use the tabulated $1.267$ for 6 standard normals and scale by $\sigma$ and $\gamma$.",
                    r"Analog: 4 actions with $\mathcal{N}(0,1)$ noise and $\gamma = 0.9$: bias $= 0.9\times1.029 \approx 0.93$. Transfer to 6 actions, $\sigma = 0.5$, $\gamma = 0.99$.",
                ),
            },
            2: {
                "prompt": r"Notation: $y = r + \gamma\hat V(s')$ with $\hat V(s') := \max_a\hat q_a$, $\hat q_a = q_a + \eta_a$, $\eta_a$ i.i.d. $\mathrm{Unif}[-1, 1]$, two actions with $q_1 = q_2 = 0$, and $\gamma = 0.9$. Compute $\mathbb{E}[y] - (r + \gamma\cdot0)$.",
                "answer_summary": r"The max of two i.i.d. $\mathrm{Unif}[-1,1]$ has density $(x + 1)/2$ on $[-1, 1]$ and mean $\tfrac13$. So the bias is $\gamma\cdot\tfrac13 = 0.3$.",
                "concept_groups": [["0.3"], ["1/3", "0.333"]],
                "verify_code": r"""import sympy as sp
x = sp.symbols('x', real=True)
dens = sp.diff(((x + 1) / 2) ** 2, x)
assert sp.integrate(dens, (x, -1, 1)) == 1
m = sp.integrate(x * dens, (x, -1, 1))
assert m == sp.Rational(1, 3) and sp.Rational(9, 10) * m == sp.Rational(3, 10)
print('VERIFIED: E max = 1/3, bias = 0.3')
""",
                "hints": _hints(
                    r"Range check: the max lies in $[-1, 1]$. Should its mean be above or below $0$?",
                    r"In “{quote}”, which distribution did you integrate against — a single noise term's, or the maximum's?",
                    r"The CDF of the maximum of two i.i.d. variables is the single CDF squared. What is it here?",
                    r"Work on $[0, 1]$ first: the max of two $\mathrm{Unif}[0,1]$ has mean $2/3$. Then map $x \mapsto 2x - 1$.",
                    r"Analog: the max of three $\mathrm{Unif}[0,1]$ has mean $3/4$, so for $\mathrm{Unif}[-1,1]$ it is $2\cdot\tfrac34 - 1 = \tfrac12$. Do the two-action case and multiply by $\gamma$.",
                ),
            },
            3: {
                "prompt": r"Compare true next-state values $q = (0, 0)$ versus $q = (0, -5)$, each estimate carrying i.i.d. $\mathcal{N}(0,1)$ noise. Compute the bias $\mathbb{E}[\max_a\hat q_a] - \max_aq_a$ in each case and explain when this optimism matters.",
                "answer_summary": r"Tied: $1/\sqrt\pi \approx 0.564$. Separated by $5$: the max almost always selects action 1, and the bias is $\approx7\times10^{-5}$, essentially $0$. Bias is large when several actions are near-tied relative to the noise, so the argmax is driven by noise.",
                "concept_groups": [["0.564", "1/√π", "0.56"], ["≈ 0", "negligible", "tiny", "near zero", "almost zero", "vanish", "7e-5", "0.00007"], ["gap", "separat", "argmax", "same action", "tie", "close"]],
                "verify_code": r"""import numpy as np
from scipy import integrate, stats
def emax(m1, m2):
    f = lambda x: x * (stats.norm.pdf(x, m1) * stats.norm.cdf(x, m2) + stats.norm.pdf(x, m2) * stats.norm.cdf(x, m1))
    return integrate.quad(f, -20, 20, limit=200)[0]
b0 = emax(0, 0); b5 = emax(0, -5)
assert abs(b0 - 1 / np.sqrt(np.pi)) < 1e-6 and 0 < b5 < 1e-4
print('VERIFIED: bias tied =', round(b0, 4), ' bias separated =', '%.2e' % b5)
""",
                "hints": _hints(
                    r"Limit check: if one action is better by a huge margin, how often does noise change the argmax?",
                    r"In “{quote}”, did you account for how often the worse action wins the max?",
                    r"Maximization bias comes from the argmax being decided by noise. When does noise decide it?",
                    r"For $q = (0, -5)$, estimate $P(\hat q_2 > \hat q_1) = P(\mathcal{N}(-5, 2) > 0)$.",
                    r"Analog: two lottery tickets worth $0$ and $-5$ with $\pm1$ noise can never swap order, so the max is just the first ticket — zero bias. With Gaussian noise, swaps are possible but rare. Quantify the rarity.",
                ),
            },
            4: {
                "prompt": r"A teammate argues: 'Our estimation errors are zero-mean, so the max over them is unbiased. The overestimation in our agent must come from function approximation.' Test the claim in a purely tabular setting.",
                "answer_summary": r"Wrong: even tabular estimates with zero-mean noise yield $\mathbb{E}[\max_a\hat Q] > \max_a\mathbb{E}\hat Q$ whenever the argmax varies with the noise (convexity of max). Function approximation can add error, but the selection bias exists without it.",
                "concept_groups": [["zero-mean", "zero mean", "individually unbiased", "each unbiased", "unbiased"], ["e[max", "max of", "convex", "jensen", "selection"], ["tabular", "without function approx", "any estimator", "noise alone", "even without"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(33)
nA, visits, trials = 5, 10, 20000
rewards = rng.normal(0, 1, size=(trials, nA, visits))
Qhat = rewards.mean(-1)
assert np.abs(Qhat.mean(0)).max() < 0.02
bias = Qhat.max(1).mean()
assert bias > 0.3
print('VERIFIED: tabular sample-mean estimates are unbiased, yet E[max] =', round(bias, 3))
""",
                "hints": _hints(
                    r"Sanity check: in a table with sample-mean estimates, is each entry unbiased? Is the maximum entry?",
                    r"In “{quote}”, you concluded unbiasedness of the max from unbiasedness of each entry. Which operation sits in between?",
                    r"What inequality relates the expectation of a max to the max of expectations, and does it use function approximation anywhere?",
                    r"Two tabular actions, each estimated by one $\pm1$ coin flip around true value $0$: compute $\mathbb{E}\max$.",
                    r"Analog: picking the tallest of 5 people measured with a noisy ruler overstates the tallest true height even though the ruler is unbiased — no neural network involved. Transfer to the Q-table.",
                ),
            },
        },
        "referee": {
            "claim": r"If each $\hat Q(s', a)$ is an unbiased estimate of $Q(s', a)$, then the Q-learning target $r + \gamma\max_a\hat Q(s', a)$ is unbiased for $r + \gamma\max_aQ(s', a)$.",
            "steps": [
                r"The target is $Y = r + \gamma\max_a\hat Q(s', a)$.",
                r"By linearity of expectation, $\mathbb{E}[Y] = r + \gamma\,\mathbb{E}[\max_a\hat Q(s', a)]$.",
                r"Let $a^\dagger = \arg\max_aQ(s', a)$ be the truly best action; then $\max_a\hat Q(s', a) = \hat Q(s', a^\dagger)$.",
                r"By unbiasedness, $\mathbb{E}[\hat Q(s', a^\dagger)] = Q(s', a^\dagger)$.",
                r"So $\mathbb{E}[Y] = r + \gamma\max_aQ(s', a)$: the target is unbiased.",
            ],
            "flawed_index": 3,
            "violated_keywords": ["argmax of the estimate", "noisy argmax", "random", "selected", "different action", "not the true", "≥ q̂(s', a†)", "lucky"],
            "explanation": r"The maximizing action of the *estimates* is random and need not be $a^\dagger$. In fact $\max_a\hat Q(s', a) \ge \hat Q(s', a^\dagger)$, with strict inequality whenever another action's noise lifts it above, so $\mathbb{E}[Y] \ge r + \gamma\max_aQ$.",
            "counterexample": r"Two actions with $Q = 0$ and $\mathcal{N}(0,1)$ estimation noise: $\mathbb{E}\max_a\hat Q = 1/\sqrt\pi \approx 0.564 > 0$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Morgan, who is sure that Q-learning's overestimation is purely an artifact of neural-network extrapolation.",
            "opening": r"In a table, every $\hat Q$ is an honest average, so the target is honest too. Overestimation only appears with neural networks extrapolating badly — right?",
            "boundary_conditions": [
                _bc("jensen_max", r"$\mathbb{E}[\max_a\hat Q] \ge \max_a\mathbb{E}\hat Q$ by convexity of max, strict when noise can change the argmax",
                    ["convex", "jensen", "e[max", "≥ max", "selection", "winner"],
                    r"Each $\hat Q$ is unbiased — where could bias possibly come from?"),
                _bc("same_estimates", r"Selection and evaluation use the same noisy estimates",
                    ["same estimate", "select and evaluate", "selection and evaluation", "same noise", "same network", "coupled", "same numbers"],
                    r"If I used a different, independent estimate to score the chosen action, would the bias go away?"),
                _bc("bootstrapping", r"Bootstrapping propagates and accumulates the bias through $\gamma$ (fixed point shifted by up to about $\gamma b/(1-\gamma)$)",
                    ["bootstrap", "propagat", "accumulat", "1/(1-γ)", "1/(1−γ)", "compound", "next update"],
                    r"A small bias per step is harmless, isn't it?"),
            ],
        },
        "misconceptions": [
            _mis(["zero-mean noise so unbiased", "noise averages out", "unbiased estimates so unbiased max"], "FALSE_ANALOGY",
                 "Unbiased inputs give an unbiased max", r"\mathbb{E}[\hat Q(s',a)] = Q(s',a)\ \forall a \implies \mathbb{E}[\max_a\hat Q] = \max_a Q"),
            _mis(["only function approximation", "only with neural networks", "tabular is unbiased"], "BOUNDARY_OMISSION",
                 "Overestimation needs function approximation", r"\text{tabular } \hat Q \implies \mathbb{E}[\max_a \hat Q] = \max_a Q"),
            _mis(["e[max] = max e", "max of expectations equals", "expectation commutes with max"], "ALGEBRAIC_SLIP",
                 "Expectation commutes with max", r"\mathbb{E}[\max_a \hat Q(s',a)] = \max_a \mathbb{E}[\hat Q(s',a)]"),
        ],
    },
    "prop_double_dqn_decoupling": {
        "probe": {
            "prompt": r"Which target is the Double DQN target (online parameters $\theta$, target-network parameters $\theta^-$)?",
            "options": _opts(
                r"$r + \gamma\max_aQ_{\theta^-}(s', a)$",
                r"$r + \gamma\,Q_{\theta^-}\big(s', \arg\max_aQ_\theta(s', a)\big)$",
                r"$r + \gamma\,Q_\theta\big(s', \arg\max_aQ_\theta(s', a)\big)$",
                r"$r + \gamma\cdot\tfrac12\big(\max_aQ_\theta(s', a) + \max_aQ_{\theta^-}(s', a)\big)$",
            ),
            "correct": "B",
            "explanation": r"Double DQN selects the action with the online network and evaluates it with the target network. A is the standard DQN target; C uses the same network for both (equal to $\max_aQ_\theta$); D averages two biased maxima.",
        },
        "predict": {
            "prompt": r"Predict: if you choose the action using one noisy estimate and score it using a second, independent noisy estimate, can the result still be biased upward? Could it be biased downward?",
        },
        "reading": r"""**Base case.** Two actions, true values $0$. Two independent estimate sets $Q^A = \varepsilon^A$ and $Q^B = \varepsilon^B$.

**Select with $A$.** $a^* = \arg\max_aQ^A(a)$ is random, but it depends only on $\varepsilon^A$.

**Evaluate with $B$.** Since $\varepsilon^B$ is independent of $a^*$,
$$\mathbb{E}\big[Q^B(a^*)\mid a^*\big] = Q(a^*), \qquad \mathbb{E}\big[Q^B(a^*)\big] = \mathbb{E}[Q(a^*)] \le \max_aQ(a).$$
No upward bias; here exactly $0$.

**Double DQN.** $a^* = \arg\max_aQ_\theta(s', a)$, target $r + \gamma\,Q_{\theta^-}(s', a^*)$. It removes the bias to the extent that the errors of $\theta^-$ are independent of the selection. Because $\theta^-$ is a lagged copy of $\theta$, the decorrelation is partial: bias is reduced, not eliminated.

**Flip side.** When the true values differ, noise sometimes selects a suboptimal $a^*$, so $\mathbb{E}[Q(a^*)] < \max_aQ$: mild *underestimation*.

**Self-explanation:** Where exactly did independence of $\varepsilon^B$ from $a^*$ enter, and what happens if $\theta^- = \theta$?""",
        "check": {
            "prompt": r"Cross-fitting notation: split data into folds $\mathcal{D}_1, \mathcal{D}_2$. Choose $\hat k = \arg\max_k\hat\mu_k^{(1)}$ using fold 1 and report $\hat\mu^{(2)}_{\hat k}$ from fold 2. If all true means equal $\mu$, then $\mathbb{E}[\hat\mu^{(2)}_{\hat k}] - \mu$ is:",
            "options": _opts(r"Positive", r"$0$", r"Negative", r"Undefined"),
            "correct": "B",
            "explanation": r"Fold-2 estimates are independent of the fold-1 selection, so conditionally on $\hat k$ the reported mean is unbiased for $\mu_{\hat k} = \mu$. It is the same decoupling as Double DQN.",
        },
        "productive_failure": {
            "prompt": r"Suppose the errors of your two estimators are each $\mathcal{N}(0,1)$ per action but correlated across estimators with coefficient $\rho$ (two actions, true values $0$). Compute the bias of $Q^B(\arg\max_aQ^A(a))$ as a function of $\rho$. What does this say about using a lagged target network?",
            "canonical_insight": r"Write $\varepsilon^B = \rho\,\varepsilon^A + \sqrt{1 - \rho^2}\,\xi$ with $\xi$ independent. Then $\mathbb{E}[\varepsilon^B_{a^*}] = \rho\,\mathbb{E}[\max_a\varepsilon^A_a] = \rho/\sqrt\pi$. Bias scales linearly with error correlation: $\rho = 1$ (same network) recovers the full max bias, $\rho = 0$ removes it. A lagged $\theta^-$ sits in between.",
        },
        "practice": {
            1: {
                "prompt": r"Your DQN overestimates. You may change one line of the target computation and already hold both the online network $\theta$ and a periodically synced target network $\theta^-$ in memory. Which line do you change, to what, and why does it reduce the bias?",
                "answer_summary": r"Replace $y = r + \gamma\max_aQ_{\theta^-}(s', a)$ by $a^* = \arg\max_aQ_\theta(s', a)$, $y = r + \gamma Q_{\theta^-}(s', a^*)$. Selection uses $\theta$'s errors and evaluation uses $\theta^-$'s; to the extent these are decorrelated, $\mathbb{E}[Q_{\theta^-}(s', a^*)\mid a^*] \approx Q(s', a^*) \le \max_aQ$.",
                "concept_groups": [["argmax", "select"], ["evaluat", "θ⁻", "theta-", "target net", "θ−", "theta^-", "θ^-"], ["decorrelat", "independen", "different noise", "decouple", "decoupling"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(34)
T, nA = 400000, 10
eA = rng.normal(size=(T, nA)); eB = rng.normal(size=(T, nA))
single = eA.max(1).mean()
astar = eA.argmax(1)
double = eB[np.arange(T), astar].mean()
assert single > 1.4 and abs(double) < 0.01
print('VERIFIED: max bias', round(single, 3), 'vs decoupled estimate', round(double, 4))
""",
                "hints": _hints(
                    r"Which two jobs does $\max_aQ(s', a)$ do at once?",
                    r"In “{quote}”, does the same set of noisy numbers both choose the action and score it?",
                    r"If you choose with one estimate and evaluate with an independent one, what is the conditional expectation of the evaluation given the choice?",
                    r"Two actions with true value 0 and independent noise in two networks: compute $\mathbb{E}[Q^B(\arg\max Q^A)]$.",
                    r"Analog: pick a stock using last year's noisy returns, then judge it on next year's returns — the luck that made it look good does not carry over. Implement the same split with $\theta$ and $\theta^-$.",
                ),
            },
            2: {
                "prompt": r"Notation: estimators $\hat f^{(1)}, \hat f^{(2)}$ of $f: \mathcal{A}\to\mathbb{R}$, with independent i.i.d. $\mathcal{N}(0,1)$ errors, $|\mathcal{A}| = 5$, and $f\equiv0$. Compare $\mathbb{E}\big[\hat f^{(2)}(\arg\max\hat f^{(1)})\big]$ with $\mathbb{E}\big[\max\hat f^{(1)}\big]$.",
                "answer_summary": r"Decoupled: $0$ (the fold-2 error is independent of the selected index). Coupled: $\mathbb{E}[\max\text{ of 5 i.i.d. }\mathcal{N}(0,1)] \approx 1.163$.",
                "concept_groups": [["= 0", "=0", "zero", "unbiased"], ["1.16"], ["independen", "conditional", "decoupl"]],
                "verify_code": r"""import numpy as np
from scipy import integrate, stats
n = 5
e5 = integrate.quad(lambda x: x * n * stats.norm.pdf(x) * stats.norm.cdf(x) ** (n - 1), -10, 10)[0]
assert abs(e5 - 1.163) < 1e-3
rng = np.random.default_rng(35)
A = rng.normal(size=(400000, n)); B = rng.normal(size=(400000, n))
dec = B[np.arange(len(A)), A.argmax(1)].mean()
assert abs(dec) < 0.01 and abs(A.max(1).mean() - e5) < 0.01
print('VERIFIED: decoupled ~0, coupled', round(e5, 4))
""",
                "hints": _hints(
                    r"Which of the two quantities uses the same noise for choosing and scoring?",
                    r"In “{quote}”, what is the distribution of the second estimator's error at an index chosen by the first?",
                    r"Condition on the selected index. Given it, what is the mean of an independent, zero-mean error at that index?",
                    r"Take $|\mathcal{A}| = 2$: compute both quantities ($1/\sqrt\pi$ for the coupled one).",
                    r"Analog: with 2 arms, the coupled value is $0.564$ and the decoupled value is $0$. For 5 arms the coupled value is the expected max of five standard normals; the decoupled value doesn't change.",
                ),
            },
            3: {
                "prompt": r"Two actions with true values $q = (1, 0)$, each estimate carrying independent $\mathcal{N}(0,1)$ noise. Compute the expected target value (ignore $r$ and $\gamma$) for (i) the single-estimator max, and (ii) the double estimator (select with one independent copy, evaluate with another). Which over- and which underestimates $\max q = 1$?",
                "answer_summary": r"(i) $\mathbb{E}\max(1 + \varepsilon_1, \varepsilon_2) = \Phi(1/\sqrt2) + \sqrt2\,\phi(1/\sqrt2) \approx 1.20 > 1$ (over). (ii) $\mathbb{E}[q(a^*)] = P(a^* = 1) = \Phi(1/\sqrt2) \approx 0.76 < 1$ (under): the double estimator sometimes picks the worse action.",
                "concept_groups": [["0.76"], ["1.2", "1.19"], ["underestimat", "downward", "below"]],
                "verify_code": r"""import numpy as np
from scipy import stats
a = 1 / np.sqrt(2)
single = stats.norm.cdf(a) + np.sqrt(2) * stats.norm.pdf(a)
double = stats.norm.cdf(a)
assert abs(single - 1.1996) < 1e-3 and abs(double - 0.7602) < 1e-3
rng = np.random.default_rng(36)
q = np.array([1.0, 0.0]); N = 400000
A = q + rng.normal(size=(N, 2)); B = q + rng.normal(size=(N, 2))
assert abs(A.max(1).mean() - single) < 0.01 and abs(B[np.arange(N), A.argmax(1)].mean() - double) < 0.01
print('VERIFIED: single', round(single, 4), '> 1 > double', round(double, 4))
""",
                "hints": _hints(
                    r"Bounds check: the double estimator's value is $q(a^*)$ on average, which lies between $\min q$ and $\max q$. Which bound does that rule out?",
                    r"In “{quote}”, did you assume the double estimator always selects the truly best action?",
                    r"For (ii), the evaluation is unbiased given the selection. So the bias is entirely about how often the selection is wrong. What is that probability?",
                    r"Compute $P(1 + \varepsilon_1 > \varepsilon_2) = P(\mathcal{N}(1, 2) > 0)$.",
                    r"Analog: with $q = (2, 0)$, the double estimator gives $2\,\Phi(\sqrt2) \approx 1.84 < 2$, while the max gives slightly above $2$. Redo with $q = (1, 0)$.",
                ),
            },
            4: {
                "prompt": r"A teammate implements the target $r + \gamma Q_{\theta^-}(s', \arg\max_aQ_\theta(s', a))$ but, to 'keep the target fresh', syncs $\theta^- \leftarrow \theta$ after every gradient step. Does the overestimation fix survive? Explain in terms of error correlation.",
                "answer_summary": r"No. With $\theta^- = \theta$ the target is $Q_\theta(s', \arg\max_aQ_\theta(s', a)) = \max_aQ_\theta(s', a)$: selection and evaluation use identical estimates (error correlation $\rho = 1$), so the full maximization bias returns, as in standard Q-learning.",
                "concept_groups": [["θ⁻ = θ", "theta- = theta", "same network", "identical", "same estimate", "θ− = θ", "θ^- = θ"], ["bias returns", "no longer", "back to", "standard", "overestimat", "doesn't survive", "does not survive"], ["correlat", "ρ = 1", "rho = 1", "ρ=1"]],
                "verify_code": r"""import numpy as np
rng = np.random.default_rng(37)
N, nA = 400000, 4
e = rng.normal(size=(N, nA))
same = e[np.arange(N), e.argmax(1)].mean()
assert np.isclose(same, e.max(1).mean()) and same > 1.0
for rho, tol in [(0.0, 0.01), (0.5, 0.02)]:
    eB = rho * e + np.sqrt(1 - rho**2) * rng.normal(size=(N, nA))
    val = eB[np.arange(N), e.argmax(1)].mean()
    assert abs(val - rho * e.max(1).mean()) < tol
print('VERIFIED: theta- = theta reproduces full max bias', round(same, 3), '; bias scales with rho')
""",
                "hints": _hints(
                    r"Substitute $\theta^- = \theta$ into the Double DQN target. What expression do you get?",
                    r"In “{quote}”, are the two networks still making independent errors?",
                    r"The decoupling argument needs the evaluator's errors to be independent of the selection. What is the correlation when the networks are identical?",
                    r"Two actions, true values $0$, one shared noise vector used for both selecting and evaluating: compute the expected target.",
                    r"Analog: grading a student on the very same exam used to pick the 'top student' reproduces the winner's curse; a fresh exam removes it. Syncing every step reuses the same exam.",
                ),
            },
        },
        "referee": {
            "claim": r"If the errors of $Q_{\theta^-}$ are independent of the errors of $Q_\theta$, the Double DQN target is exactly unbiased for $r + \gamma\max_aQ(s', a)$.",
            "steps": [
                r"Let $a^* = \arg\max_aQ_\theta(s', a)$; the target is $Y = r + \gamma Q_{\theta^-}(s', a^*)$.",
                r"Because $\theta^-$'s errors are independent of $\theta$'s (hence of $a^*$), $\mathbb{E}[Q_{\theta^-}(s', a^*)\mid a^*] = Q(s', a^*)$.",
                r"Taking expectations, $\mathbb{E}[Y] = r + \gamma\,\mathbb{E}[Q(s', a^*)]$.",
                r"Since $a^*$ maximizes the estimate, it maximizes the true value: $Q(s', a^*) = \max_aQ(s', a)$.",
                r"Hence $\mathbb{E}[Y] = r + \gamma\max_aQ(s', a)$: the target is exactly unbiased.",
            ],
            "flawed_index": 4,
            "violated_keywords": ["wrong action", "suboptimal", "not the true", "misselect", "underestimat", "noisy argmax", "probability", "can pick"],
            "explanation": r"The argmax of a noisy estimate is not always the true best action. In general $\mathbb{E}[Q(s', a^*)] \le \max_aQ(s', a)$, with strict inequality whenever noise can select a worse action: Double DQN trades upward bias for possible downward bias.",
            "counterexample": r"$q = (1, 0)$ with independent $\mathcal{N}(0,1)$ errors: $\mathbb{E}[Q(a^*)] = \Phi(1/\sqrt2) \approx 0.76 < 1$.",
        },
        "feynman": {
            "buggy_rule_id": None,
            "persona": "Taylor, who thinks Double DQN works by averaging two networks so that their noise cancels.",
            "opening": r"Double DQN just averages the online and target networks' maxima, right? Two noisy estimates averaged means less noise, so less bias. Can you explain what it really does?",
            "boundary_conditions": [
                _bc("decouple", r"Select the action with $\theta$ (argmax) and evaluate it with $\theta^-$; no averaging of maxima",
                    ["select with", "selection", "argmax with", "evaluate with", "evaluation", "decoupl"],
                    r"Isn't Double DQN just averaging the two networks' max values?"),
                _bc("independence_needed", r"Bias removal needs the evaluator's errors independent of the selection; a lagged $\theta^-$ is only partially decorrelated, so bias is reduced, not eliminated",
                    ["independen", "decorrelat", "lag", "partially", "not eliminated", "reduced"],
                    r"If $\theta^-$ is just an old copy of $\theta$, aren't their errors basically the same?"),
                _bc("underestimation", r"It can underestimate: $\mathbb{E}[Q(a^*)] \le \max_aQ$ when noise selects a suboptimal action",
                    ["underestimat", "downward", "≤ max", "suboptimal", "wrong action", "below"],
                    r"So Double DQN is exactly unbiased?"),
            ],
        },
        "misconceptions": [
            _mis(["average the two networks", "average of max", "mean of both maxima", "averaging cancels the noise"], "FALSE_ANALOGY",
                 "Double DQN as ensemble averaging", r"Y = r + \tfrac{\gamma}{2}\big(\max_a Q_\theta + \max_a Q_{\theta^-}\big)"),
            _mis(["double dqn is unbiased", "removes all bias", "exactly unbiased", "no bias at all"], "BOUNDARY_OMISSION",
                 "Double DQN is exactly unbiased", r"\mathbb{E}\big[Q_{\theta^-}(s', \arg\max_a Q_\theta(s',a))\big] = \max_a Q(s',a)"),
            _mis(["sync every step", "update target every step", "copy theta each step"], "BOUNDARY_OMISSION",
                 "Instant target sync keeps the decoupling", r"\theta^- \equiv \theta \implies \text{bias removed}"),
        ],
    },
}
