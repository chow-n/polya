# CLAUDE.md — Pólya (formerly LearnHarness)

**After any context compaction, re-read this file, `ARCHITECTURE_SPEC.md` and `docs/specs/learnharness/SPEC.md` (decisions + assumptions).**

## Rename + UI (approved 2026-10-23, docs/specs/ui-simplify/SPEC.md)
- Product name **Pólya** (identifiers `polya`); env vars `POLYA_*` with `LEARNHARNESS_*` accepted; data home `~/Polya`
  (auto-moved from `~/LearnHarness`, symlink left); CLI `./polya`; app `Pólya.app` (`make app` / `make bundle`).
- The verbatim spec below still says "LearnHarness"; it is historical. The UI is the minimalist focus layout
  (Learn · Review · Map), with advanced telemetry behind Details / Settings → Advanced.

## Build decisions (approved fast-track 2026-10-23)
- Zero-key LLM default: `claude -p --output-format json` (90s timeout) → deterministic SymPy/graph engine.
- Six modes = PROBE, PRODUCTIVE_FAILURE, TEACH, PRACTICE, REFEREE_DUEL/PROOF_REFEREE, REFEREE_DUEL/FEYNMAN_STUDENT.
- Backend venv: `backend/.venv` (uv). Tests: `make test` (forces `LEARNHARNESS_LLM=deterministic`). Frontend: `cd frontend && npm run build`.
- Science additions: Murphy Brier decomposition, desired-retention due dates (r=0.90), interleaving penalty, pretesting-effect rationale.

---
# Verbatim specification

You are going to autonomously architect, implement, test, and launch **Maximal LearnHarness**—a complete, local-first AI cognitive learning harness that models the human learner's brain as a Partially Observable Markov Decision Process (POMDP).

---

# 0. AUTONOMOUS EXECUTION & CONTEXT-SURVIVAL RULES (READ FIRST)

1. **Step 0 — Persist Spec to Disk Immediately:** Before creating any code files, write this entire specification verbatim into `CLAUDE.md` and `ARCHITECTURE_SPEC.md` in the root directory. If your context window compacts at any point during the build, immediately re-read `CLAUDE.md` and `ARCHITECTURE_SPEC.md` so zero equations, schemas, prompts, or UI requirements are lost.
2. **Continuous Execution (No Halting):** Do NOT pause between phases to ask for human confirmation. Execute Phases 1 through 7 sequentially until all backend `pytest` suites pass, `npm run build` succeeds with zero TypeScript errors, the database is seeded, and both servers are running live.
3. **Strict Anti-Stub Policy:** Never write `TODO`, `pass`, `NotImplementedError`, placeholder math, or dummy UI buttons. Every mathematical formula (FSRS-v5, Process-Aware Extended BKT, Hyperedge Belief Propagation, Mutual Information Active Probe, Brier Calibration Decomposition, Hypercorrection Multiplier, Dynamic Step-Size $\Delta$-Controller), every sub-agent tool, every system prompt, and every React component must be implemented in full.
4. **Multi-Provider LLM Engine with Zero-Key Local Fallback (`backend/llm.py`):**
   - Support direct API keys via environment variables or runtime UI configuration: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`.
   - **Mandatory Zero-Config Fallback:** If no API key is set in the environment, automatically route LLM calls through the local `claude -p --output-format json` CLI subprocess (and if `claude` CLI is unavailable or nested-invocation locked, provide a deterministic algorithmic + symbolic fallback engine backed by the local SymPy kernel and knowledge graph) so the application works 100% out of the box on first launch.
5. **Dual-Engine Voice & Prosody Telemetry:**
   - Support streaming WebSocket dictation via `DEEPGRAM_API_KEY` (`nova-3` model).
   - **Mandatory Zero-Config Fallback:** Implement native browser `SpeechRecognition` / `webkitSpeechRecognition` paired with a real-time **Web Audio API `AnalyserNode` Acoustic Prosody Tracker** that measures RMS decibel levels at 60Hz to compute `initial_latency_ms`, `hesitation_pause_count`, `total_silence_ms`, `words_per_minute`, and `hedge_word_density`.

---

# 1. EXACT MONOREPO DIRECTORY TREE

Create this exact project structure:

```text
learn-harness/
├── CLAUDE.md
├── ARCHITECTURE_SPEC.md
├── Makefile
├── start.sh
├── harness-cli                          # Executable terminal helper CLI
├── workspace/
│   ├── scratch.tex                      # Live-watched LaTeX scratchpad synced to UI via WebSockets
│   ├── notes/
│   │   └── measure_rl_transformers.tex  # Starter user lecture notes for local RAG testing
│   └── problems/
│       └── bellman_contraction_pset.tex # Starter custom problem file for Practice import
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── __init__.py
│   ├── config.py                        # Env vars, runtime settings, paths
│   ├── db.py                            # SQLite WAL engine, DDL migrations, CRUD helpers
│   ├── models.py                        # Complete Pydantic v2 schemas for API, WS, and LLM I/O
│   ├── cognitive_math.py                # FSRS-v5, Extended BKT, DAG Belief Prop, Mutual Info, Brier
│   ├── tools.py                         # SymPy/NumPy sandbox verifier, ripgrep/find/PDF/LaTeX tools
│   ├── llm.py                           # Multi-provider async LLM router + claude CLI subprocess bridge
│   ├── scratchpad_watcher.py            # Watchdog async monitor for workspace/scratch.tex & notes/
│   ├── seed.py                          # Rich 20-node, 16-hyperedge cross-domain seed dataset
│   ├── main.py                          # FastAPI REST endpoints + bi-directional WebSocket hub
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── prompts.py                   # Exhaustive verbatim system prompts for all modes & sub-agents
│   │   ├── subagents.py                 # The 8 asynchronous sub-agents with live WS telemetry
│   │   └── orchestrator.py              # The 6-Mode Pedagogical State Machine & Delta-Step Controller
│   └── tests/
│       ├── __init__.py
│       ├── test_cognitive_math.py       # Unit tests for FSRS-v5, BKT, Mutual Info, Brier, Hypercorrection
│       ├── test_tools_and_db.py         # Unit tests for SQLite hypergraph, topological depth, SymPy kernel
│       └── test_api_and_modes.py        # Integration tests for all 6 pedagogical modes & WS endpoints
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── types/
        │   └── harness.ts               # Exact TypeScript mirrors of all backend Pydantic schemas
        ├── store/
        │   └── useHarnessStore.ts       # Central state & WebSocket event dispatcher
        ├── utils/
        │   ├── katexRenderer.tsx        # Fast KaTeX parser with custom math macros (\R, \E, \Var, etc.)
        │   └── prosodyAudioEngine.ts    # Web Audio API AnalyserNode + SpeechRecognition prosody tracker
        └── components/
            ├── TopTelemetryBar.tsx      # Mode switcher, scratch.tex sync pill, Brier & Bjork counters
            ├── SidebarSubagentDock.tsx  # Session list, file importer, live 8-Sub-Agent activity monitor
            ├── EpistemicLockBox.tsx     # Two-Stage Epistemic Lock (forces raw prediction before options)
            ├── ReadingStreamBox.tsx     # Inline sentence/equation highlight anchoring + margin stream
            ├── TelemetryInputDock.tsx   # Tri-modal input: LaTeX editor + live preview + Mic + Confidence
            ├── PracticeArena.tsx        # Chunked thinking stream, R0-R4 Hint Ladder, Metadata Drawer
            ├── RefereeDuelArena.tsx     # Proof-Referee line-click debugger & Feynman Buggy-Student chat
            ├── SandboxDemoViewer.tsx    # Sandboxed iframe for HTML5/WebGL demos + Dark-Mode Guard switch
            ├── DependencyMiniMap.tsx    # Right-pane live topological session DAG with Delta-branching
            ├── HypergraphCanvas.tsx     # Full-screen 2D/WebGL graph with Y-axis depth lock & 4 overlays
            └── ReasoningChainsTable.tsx # Filterable proposition/hyperedge table + Bjork Batch launcher
```

---

# 2. COMPLETE SQLITE HYPERGRAPH SCHEMA (`backend/db.py`)

Configure SQLite (`harness.db`) with `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`. Implement these exact tables:

```sql
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN (
        'AXIOM',           -- Unconditional starting primitives, base observations, formal definitions
        'PROPOSITION',     -- Derived mathematical/theoretical claims requiring proof/justification
        'MOVE',            -- Procedural problem-solving tactics triggered by situational cues
        'COUNTEREXAMPLE',  -- Boundary objects/pathologies that falsify naive generalizations
        'INTUITION',       -- Dual-coded geometric/physical/spatial mental models
        'BUGGY_RULE'       -- Shadow nodes representing recurring learner misconceptions
    )),
    statement_latex TEXT NOT NULL,
    intuition_summary TEXT NOT NULL,
    formal_proof_sketch_latex TEXT NOT NULL DEFAULT '',
    domain_cluster TEXT NOT NULL,
    logical_depth INTEGER NOT NULL DEFAULT 0,
    
    -- Extended Bayesian Knowledge Tracing (BKT) State
    bkt_p_mastery REAL NOT NULL DEFAULT 0.15,
    bkt_p_transit REAL NOT NULL DEFAULT 0.12,
    bkt_p_slip REAL NOT NULL DEFAULT 0.08,
    bkt_p_guess REAL NOT NULL DEFAULT 0.05,
    
    -- FSRS-v5 Memory Dynamics State (Bjork Storage vs. Retrieval Strength)
    fsrs_stability REAL NOT NULL DEFAULT 1.0,    -- S in days
    fsrs_difficulty REAL NOT NULL DEFAULT 5.0,   -- D in [1.0, 10.0]
    fsrs_reps INTEGER NOT NULL DEFAULT 0,
    fsrs_lapses INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT NOT NULL,
    
    -- 5D Transfer-Appropriate Cue-Breadth Vector (values in [0.0, 1.0])
    cue_symbolic REAL NOT NULL DEFAULT 0.0,
    cue_disguised_notation REAL NOT NULL DEFAULT 0.0,
    cue_geometric REAL NOT NULL DEFAULT 0.0,
    cue_computational REAL NOT NULL DEFAULT 0.0,
    cue_adversarial REAL NOT NULL DEFAULT 0.0,
    
    -- Metacognitive Calibration & Hypercorrection State
    brier_sum REAL NOT NULL DEFAULT 0.0,
    brier_count INTEGER NOT NULL DEFAULT 0,
    hypercorrection_flag INTEGER NOT NULL DEFAULT 0, -- 1 if missed with confidence >= 0.75
    last_miss_class TEXT NOT NULL DEFAULT 'NONE',
    
    created_in_session_id TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hyperedges (
    id TEXT PRIMARY KEY,
    edge_type TEXT NOT NULL CHECK (edge_type IN (
        'DEDUCTION',    -- Directed logical implication: Premise_1 AND Premise_2 ... => Conclusion
        'CONTRASTIVE',  -- Discriminative boundary between two easily confused nodes (u perp v)
        'ISOMORPHISM',  -- Cross-domain structural functor / equivalence (u cong v)
        'CUE_TRIGGER'   -- Situational cue pattern c triggers procedural move m
    )),
    premise_node_ids_json TEXT NOT NULL,         -- JSON list of source node IDs, e.g. ["id1", "id2"]
    conclusion_node_id TEXT NOT NULL,            -- Target node ID
    reasoning_chain_latex TEXT NOT NULL,         -- Explicit step-by-step derivation or boundary discriminator
    discriminating_condition_latex TEXT NOT NULL DEFAULT '', -- Specifically for CONTRASTIVE edges
    edge_mastery REAL NOT NULL DEFAULT 0.50,
    session_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conclusion_node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN (
        'PROBE', 'PRODUCTIVE_FAILURE', 'TEACH', 'PRACTICE', 'REFEREE_DUEL'
    )),
    sub_mode TEXT NOT NULL DEFAULT 'STANDARD',   -- e.g. 'PROOF_REFEREE' or 'FEYNMAN_STUDENT'
    target_goal TEXT NOT NULL,
    attached_files_json TEXT NOT NULL DEFAULT '[]',
    step_velocity_delta REAL NOT NULL DEFAULT 1.0, -- Dynamic reasoning leap size Delta in [0.5, 2.5]
    current_step_index INTEGER NOT NULL DEFAULT 0,
    dependency_plan_json TEXT NOT NULL DEFAULT '[]',
    active_step_payload_json TEXT NOT NULL DEFAULT '{}',
    history_steps_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_traces (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN (
        'PROBE', 'PRODUCTIVE_FAILURE', 'PREDICT', 'READING', 'CHECK', 'PRACTICE_CHUNK', 'REFEREE'
    )),
    target_node_ids_json TEXT NOT NULL,
    cue_level INTEGER NOT NULL DEFAULT 1,        -- 1=Canonical, 2=Disguised, 3=Synthesis/Contrast, 4=Violated-Premise
    prompt_shown_latex TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '[]',
    
    -- The 3 Thinking Telemetry Channels
    raw_prediction_locked TEXT NOT NULL DEFAULT '',         -- Channel 1: Locked BEFORE options/explanations unlock
    thinking_while_reading_json TEXT NOT NULL DEFAULT '[]', -- Channel 2: Array of {quote, thought, timestamp_ms}
    verification_thinking TEXT NOT NULL DEFAULT '',         -- Channel 3: Post-step reasoning or chunk submission
    
    selected_answer TEXT NOT NULL DEFAULT '',
    confidence_slider REAL NOT NULL DEFAULT 0.50,           -- Subjective probability in [0.0, 1.0]
    
    -- Voice & Prosody Telemetry
    prosody_metrics_json TEXT NOT NULL DEFAULT '{"initial_latency_ms":0,"total_silence_ms":0,"hesitation_count":0,"hedge_count":0,"wpm":0}',
    
    -- Diagnostic Evaluation & Memory Delta
    is_correct INTEGER NOT NULL DEFAULT 0,
    trace_quality_score REAL NOT NULL DEFAULT 0.50,         -- [0.0, 1.0] assessed by Bug-Library Agent
    outcome TEXT NOT NULL CHECK (outcome IN (
        'SOLVED_CLEAN', 'SOLVED_WITH_HINTS', 'PARTIAL', 'FAILED', 'HIGH_CONFIDENCE_ERROR', 'EXPLORATION_LOGGED'
    )),
    max_hint_rung TEXT NOT NULL DEFAULT 'NONE' CHECK (max_hint_rung IN ('NONE', 'R0', 'R1', 'R2', 'R3', 'R4')),
    miss_class TEXT NOT NULL DEFAULT 'NONE' CHECK (miss_class IN (
        'NONE', 'ALGEBRAIC_SLIP', 'NOTATION_OBSTRUCTION', 'MISSING_PREREQUISITE',
        'BOUNDARY_OMISSION', 'FALSE_ANALOGY', 'CUE_BLINDNESS'
    )),
    ai_diagnosis_markdown TEXT NOT NULL DEFAULT '',
    brier_score REAL NOT NULL DEFAULT 0.0,
    bkt_mastery_before REAL NOT NULL DEFAULT 0.0,
    bkt_mastery_after REAL NOT NULL DEFAULT 0.0,
    fsrs_stability_before REAL NOT NULL DEFAULT 0.0,
    fsrs_stability_after REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subagent_artifacts (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    agent_name TEXT NOT NULL CHECK (agent_name IN (
        'SYMBOLIC_VERIFIER', 'BUG_LIBRARY_DIAGNOSTICIAN', 'COUNTEREXAMPLE_SYNTHESIZER',
        'SANDBOX_DEMO_BUILDER', 'SVG_DIAGRAM_MAKER', 'LOCAL_CORPUS_RAG',
        'LITERATURE_RESEARCHER', 'ONTOLOGIST_EXTRACTOR'
    )),
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    title TEXT NOT NULL,
    content_type TEXT NOT NULL, -- 'sympy_log', 'svg', 'html_demo', 'json_diagnosis', 'rag_excerpt', 'graph_diff'
    payload_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

---

# 3. EXACT MATHEMATICAL & COGNITIVE ALGORITHMS (`backend/cognitive_math.py`)

Implement every equation below with full numerical stability:

### 3.1 FSRS-v5 & Bjork’s New Theory of Disuse (Storage vs. Retrieval Strength)
1. **Power-Law Retrievability Curve:**
   Given stability $S > 0$ (in days) and elapsed time $t = \max(0, \text{now} - \text{last\_reviewed\_at})$ in days:
   $$R(t, S) = \left(1 + \frac{19}{81} \cdot \frac{t}{\max(S, 0.05)}\right)^{-0.5}$$
2. **Rating Assignment $G \in \{1, 2, 3, 4\}$ from Telemetry:**
   - If `is_correct == 0` or `outcome in ('FAILED', 'HIGH_CONFIDENCE_ERROR')`: $G = 1$ (Again / Lapse).
   - If `is_correct == 1` and `max_hint_rung in ('R2', 'R3', 'R4')`: $G = 2$ (Hard).
   - If `is_correct == 1` and (`max_hint_rung in ('R0', 'R1')` or `trace_quality_score < 0.72` or `prosody.hesitation_count >= 4`): $G = 3$ (Good).
   - If `is_correct == 1` and `max_hint_rung == 'NONE'` and `trace_quality_score >= 0.72`: $G = 4$ (Easy).
3. **Difficulty Update $D' \in [1.0, 10.0]$ with Mean Reversion:**
   $$\Delta D = -0.85 \cdot (G - 3), \qquad D_{\text{raw}} = D + \Delta D \cdot \left(\frac{10 - D}{9}\right), \qquad D' = \text{clip}\big(0.15 \cdot 5.0 + 0.85 \cdot D_{\text{raw}},\; 1.0,\; 10.0\big)$$
4. **Stability Update $S'$ (Enforcing Bjork’s Inverse Retrieval-Gain Law):**
   - If $G \in \{2, 3, 4\}$ (Successful Recall):
     Let hard/easy multipliers be $m_2 = 0.55$, $m_3 = 1.00$, $m_4 = 1.38$.
     Define the **Intraday / Over-Practice Dampener**: if $R > 0.92$ (practicing immediately after learning when $R \approx 1$), the term $(e^{0.95(1 - R)} - 1)$ naturally compresses stability gain so cramming cannot inflate long-term stability $S$. However, always grant a small minimum floor gain of $+0.15 \cdot m_G$ days so first-day practice still registers visibly on the UI:
     $$S' = S \cdot \left(1 + e^{1.75} \cdot (11 - D') \cdot \max(S, 0.5)^{-0.22} \cdot \max\Big(0.06,\; e^{0.95(1 - R)} - 1\Big) \cdot m_G\right)$$
   - If $G = 1$ (Lapse / Forgetting):
     $$S' = \max\left(0.20,\; \min\Big(S \cdot 0.65,\; 0.38 \cdot (D')^{-0.28} \cdot (S + 1)^{0.22} \cdot e^{0.45(1 - R)}\Big)\right)$$

### 3.2 Process-Aware Extended Bayesian Knowledge Tracing (BKT) & Hyperedge Belief Propagation
1. **Observation Likelihood Modulation via Thinking-Trace Quality:**
   In standard BKT, an answer is binary. In LearnHarness, if a learner selects the right multiple-choice option via algebraic elimination while admitting in their `raw_prediction_locked` field *"I have no idea what RoPE is, just guessing from transpose rules"*, we MUST NOT credit full mastery!
   - Let $q = \text{trace\_quality\_score} \in [0, 1]$, objective correctness $y \in \{0, 1\}$, prior mastery $p = P(L_{t-1})$, slip $s = P(S)$, guess $g = P(G)$, transit $T = P(T)$.
   - Compute effective slip $s_{\text{eff}}$ and effective guess $g_{\text{eff}}$:
     - If `miss_class == 'NOTATION_OBSTRUCTION'`: $s_{\text{eff}} = 0.48$ (softens penalty when the learner only stumbled on an unfamiliar symbol like $\odot$ or $\text{SiLU}$).
     - If `miss_class == 'ALGEBRAIC_SLIP'`: $s_{\text{eff}} = 0.35$.
     - Otherwise: $s_{\text{eff}} = s = 0.08$.
     - If $y = 1$ but $q < 0.45$ (lucky guess / surface heuristic without structural understanding): inflate $g_{\text{eff}} = 0.65$ so the posterior barely moves. Otherwise $g_{\text{eff}} = g \cdot (1.2 - 0.8q)$.
   - Posterior given observation:
     $$P(L_t \mid \text{obs}) = \begin{cases} \dfrac{p(1 - s_{\text{eff}})}{p(1 - s_{\text{eff}}) + (1 - p)g_{\text{eff}}} & \text{if } y = 1 \\[10pt] \dfrac{p \cdot s_{\text{eff}}}{p \cdot s_{\text{eff}} + (1 - p)(1 - g_{\text{eff}})} & \text{if } y = 0 \end{cases}$$
   - Apply learning transition weighted by trace quality:
     $$P(L_t) = \text{clip}\Big(P(L_t \mid \text{obs}) + \big(1 - P(L_t \mid \text{obs})\big) \cdot T \cdot (0.4 + 0.6q),\; 0.01,\; 0.995\Big)$$
2. **Directed Hyperedge Message Passing (`propagate_hyperedge_beliefs`):**
   - **Upward Confirmation:** When conclusion node $C$ of a `DEDUCTION` hyperedge $\{A_1, \dots, A_k\} \implies C$ is solved cleanly ($y=1, q \ge 0.75$), update every premise $A_i$:
     $$P(L_{A_i}) \leftarrow \min\big(0.99,\; P(L_{A_i}) + 0.08 \cdot q \cdot (1 - P(L_{A_i}))\big)$$
   - **Downward Diagnostic Decay:** When node $C$ fails with `miss_class == 'MISSING_PREREQUISITE'`, slightly increase uncertainty on premises $A_i$ ($P(L_{A_i}) \leftarrow 0.90 \cdot P(L_{A_i}) + 0.05$) so the Probe/Teach engine knows to check them.

### 3.3 Information-Theoretic Active Epistemic Binary Search (`select_next_probe_node`)
Given a candidate prerequisite DAG $G = (V, E)$ and the set of already-probed nodes $V_{\text{probed}}$:
1. For every unprobed node $v \in V \setminus V_{\text{probed}}$, compute its binary Shannon entropy:
   $$H(v) = -P(L_v)\log_2 P(L_v) - (1 - P(L_v))\log_2(1 - P(L_v))$$
2. Compute the **Markov Blanket Reachability Leverage** $W(v)$:
   - If $v$ is proven mastered, all $\text{Ancestors}(v)$ gain positive belief mass.
   - If $v$ is proven unmastered, all $\text{Descendants}(v)$ become more likely unreachable without teaching $v$.
   - Expected Information Gain proxy:
     $$\text{EIG}(v) = H(v) \cdot \Big(1 + 0.40 \cdot P(L_v) \cdot |\text{UnprobedAncestors}(v)| + 0.40 \cdot (1 - P(L_v)) \cdot |\text{UnprobedDescendants}(v)|\Big)$$
3. Return $v^* = \arg\max_{v \in V \setminus V_{\text{probed}}} \text{EIG}(v)$, along with the full ranked EIG table so the UI can display *why* that probe question was chosen!

### 3.4 Hypercorrection Effect, Brier Calibration & Cue-Demand Priority Scheduler
1. **Brier Score & Hypercorrection Trigger (Butterfield & Metcalfe, 2001):**
   - For confidence $c \in [0, 1]$ and outcome $y \in \{0, 1\}$, `brier = (c - y)**2`.
   - If $y = 0$ and $c \ge 0.75$: set `outcome = 'HIGH_CONFIDENCE_ERROR'` and `node.hypercorrection_flag = 1`. When the learner later resolves a node with `hypercorrection_flag == 1` cleanly ($y = 1, q \ge 0.75$), clear the flag and apply a **1.25x Hypercorrection Stability Bonus** to $S'$ (reflecting the neurocognitive attentional surge of correcting a high-confidence false belief).
2. **5D Cue-Breadth Update:**
   - Map `cue_level` and session mode to the 5 cue dimensions:
     - Level 1 $\to$ `cue_symbolic`
     - Level 2 $\to$ `cue_disguised_notation`
     - Demo / Diagram step $\to$ `cue_geometric`
     - Code / Scalar matrix calculation $\to$ `cue_computational`
     - Level 4 / Proof-Referee Duel $\to$ `cue_adversarial`
   - On clean solve, update that dimension: $c_d \leftarrow \min(1.0,\; c_d + 0.35 \cdot (1 - c_d))$.
3. **Practice Node Priority Score (`rank_nodes_for_practice`):**
   $$\text{Score}(v) = 0.35 \cdot \exp\left(-\frac{(R(t, S) - 0.78)^2}{2 \cdot (0.12)^2}\right) + 0.25 \cdot (1 - R(t, S)) + 0.20 \cdot (1 - \overline{\mathbf{c}}_v) + 0.20 \cdot \mathbb{I}(\text{hypercorrection\_flag}_v = 1)$$
   Notice the Gaussian peak centered at $R = 0.78$: this actively targets **Bjork's Desirable Difficulty Window** ($R \in [0.70, 0.85]$) right before forgetting occurs!

---

# 4. EXHAUSTIVE SYSTEM PROMPTS & SCHEMAS (`backend/agents/prompts.py`)

Implement `backend/agents/prompts.py` containing detailed, structured system prompts enforcing these exact laws across all 6 modes and 8 sub-agents:

1. **Core Pedagogical Laws (Injected into Teaching & Practice Agents):**
   - **Law 1 (Anti-Illusion of Competence):** The greatest danger in AI-assisted learning is NOT hallucination; it is letting the learner skip the cognitive struggle. Never hand over a multi-step derivation unprompted.
   - **Law 2 (Unconditional Truths First, Conditional Abstractions Second):** Never introduce a formal definition, notation, or theorem before the learner has felt the concrete problem or obstruction it solves. Start from unconditional base truths (e.g., $d=1$ or $2 \times 2$ matrices, variance of sums of independent variables) and walk upward one logical implication ($A \land B \implies C$) at a time.
   - **Law 3 (Two-Stage Epistemic Lock):** Every `PROBE`, `PREDICT`, and `CHECK` step MUST require a raw, open-ended prediction or stream-of-consciousness thought FIRST (`options_locked: true`), before any multiple-choice discriminators are revealed.
   - **Law 4 (No Walls of Text — Continuous Closed-Loop Telemetry):** Keep every teaching step under 180 words of crystal-clear prose + display LaTeX so the learner continuously feeds back `thinking_while_reading` and `verification_thinking` telemetry after every single logical link.
   - **Law 5 (Cue-Demand Framing in Practice):** Do not write generic textbook exercises. Frame every practice problem as a realistic situational cue where the learner must *recognize which proposition/move comes to mind* without being told the theorem name in the prompt.
   - **Law 6 (Strict 5-Rung Socratic Hint Ladder):** When evaluating a learner's `PRACTICE_CHUNK`:
     - `R0 (Metacognitive / Type-Shape Check)`: Ask the learner to check dimensions, matrix shapes, domains, or limiting behavior ($x \to 0, \infty$).
     - `R1 (Attention Pointer)`: Quote the exact expression in the learner's thinking box where an unstated assumption or slip occurred, without fixing it for them.
     - `R2 (Cue Prime)`: Ask a question that primes the relevant upstream node from their graph without naming the final move.
     - `R3 (Base-Case Reduction)`: Ask them to explicitly compute the scalar ($d=1$) or two-element ($n=2$) version first.
     - `R4 (Worked Isomorphic Analog)`: Show a 3-line worked solution to an isomorphic problem in a simpler setting and ask them to transfer the exact move back.

2. **Dynamic Step-Size Controller ($\Delta$-Adapter in `orchestrator.py`):**
   - Maintain `session.step_velocity_delta` $\in [0.5, 2.5]$.
   - After two consecutive `SOLVED_CLEAN` steps with `trace_quality_score >= 0.80` and `confidence_slider >= 0.75`, increment $\Delta \leftarrow \min(2.5, \Delta + 0.5)$ and instruct the Teaching Agent to compress trivial algebraic bridges and ask a higher-leap synthesis prediction.
   - On any `FAILED`, `HIGH_CONFIDENCE_ERROR`, or `MISSING_PREREQUISITE`, drop $\Delta \leftarrow 0.5$ and dynamically splice a remedial sub-node into `session.dependency_plan_json` immediately before the current node!

---

# 5. DETERMINISTIC SUB-AGENT TOOLS & SANDBOXES (`backend/tools.py` & `backend/agents/subagents.py`)

Implement all 8 sub-agents so they execute real work and store inspectable records in `subagent_artifacts`:

1. **`SYMBOLIC_VERIFIER` (`verify_math_sympy`):**
   - Executes generated Python verification code inside a restricted `subprocess.run([sys.executable, "-c", code], timeout=5, capture_output=True)` with `sympy`, `numpy`, and `scipy` available.
   - Used automatically during problem generation, step checking, and counterexample synthesis. Logs the exact SymPy script and verification stdout into `subagent_artifacts`.
2. **`BUG_LIBRARY_DIAGNOSTICIAN`:**
   - Analyzes the tuple `(raw_prediction_locked, thinking_while_reading_json, verification_thinking, prosody_metrics_json, confidence_slider, selected_answer, correct_answer)`.
   - Detects when the learner got the right answer for the wrong reason (e.g., guessing via dimension elimination while admitting ignorance in the thinking box) or the wrong answer for a benign reason (`NOTATION_OBSTRUCTION` vs `FALSE_ANALOGY`).
   - Automatically creates or updates a `BUGGY_RULE` node in `nodes` whenever a structural misconception is detected!
3. **`COUNTEREXAMPLE_SYNTHESIZER`:**
   - Scans the learner's thinking trace for universal claims ("every", "always", "any continuous...", "for all matrices...") that drop a required hypothesis, constructs a minimal counterexample, verifies it in SymPy/NumPy, and attaches it to the hypergraph as a `COUNTEREXAMPLE` node.
4. **`SANDBOX_DEMO_BUILDER`:**
   - Generates a complete, self-contained HTML5 document (`<!DOCTYPE html>...`) with embedded `<canvas>` or interactive SVG, dark-mode styling (`background: #0b0f19; color: #f8fafc; font-family: Inter, system-ui`), 2 to 4 parameter `<input type="range">` sliders, real-time mathematical plotting, and a **Goal-Directed Challenge Banner** at the top.
   - Whenever the user drags a slider or meets the challenge target, the iframe calls:
     ```javascript
     window.parent.postMessage({
       type: 'HARNESS_DEMO_TELEMETRY',
       demoId: '...',
       params: currentParams,
       challengeSolved: isTargetMet,
       summary: 'User tuned learning rate eta=0.08, batch_size=32 -> stationary variance=0.19'
     }, '*');
     ```
5. **`SVG_DIAGRAM_MAKER`:**
   - Produces clean, responsive `<svg viewBox="0 0 720 340">` architectural diagrams, commutative diagrams, geometric projections, and tensor shape flows using crisp dark-mode palettes (`#1e293b` fills, `#6366f1` / `#10b981` / `#f59e0b` strokes, `#f8fafc` labels).
6. **`LOCAL_CORPUS_RAG`:**
   - Exposes `list_workspace_files()`, `grep_workspace(pattern)`, `read_tex_or_md(filename)`, and `read_pdf_file(filename)` over `workspace/notes/` and `workspace/problems/`. Parses `\section`, `\begin{theorem}`, `\begin{definition}`, and `\begin{problem}` environments from `.tex` files.
7. **`LITERATURE_RESEARCHER`:**
   - Queries the public arXiv API (`[http://export.arxiv.org/api/query?search_query=](http://export.arxiv.org/api/query?search_query=)...`) with an offline fallback knowledge base when offline, returning citations and theorem statements.
8. **`ONTOLOGIST_EXTRACTOR`:**
   - Extracts atomic propositions (`nodes`) and logical implications (`hyperedges`: `DEDUCTION`, `CONTRASTIVE`, `ISOMORPHISM`, `CUE_TRIGGER`) after every completed teaching node or session, recomputes topological `logical_depth` across the entire graph, and exports a clean Markdown+LaTeX summary note into `workspace/notes/session_<id>.md`.

---

# 6. FRONTEND COGNITIVE WORKSPACE SPECIFICATION (`frontend/src/`)

Build a responsive, zero-glare dark-mode UI (`#070a12` canvas background, `#0f172a` elevated panels, `#1e293b` borders, `#f8fafc` primary text) with zero layout shift and full keyboard navigation.

### 6.1 Global Top Telemetry Bar (`TopTelemetryBar.tsx`)
- **4 Primary View Tabs:**
  1. `1. Active Learning Session` (Split-pane Socratic & Productive Failure workspace)
  2. `2. Epistemic Hypergraph (2D/DAG)` (Full interactive node/hyperedge canvas)
  3. `3. Practice & Referee Arena` (Cue-Demand stream, Contrastive Pairs, Proof-Referee & Feynman Duel)
  4. `4. Reasoning Chains & Vault` (Tabular hyperedge browser, 5D Cue-Breadth matrix, `.tex` notes manager)
- **Live Status Pills:**
  - **`scratch.tex` Live Sync Pill:** Pulsing emerald indicator showing real-time sync with `workspace/scratch.tex` (with a 1-click modal to view/edit `scratch.tex` or copy the terminal command `nvim workspace/scratch.tex`).
  - **Bjork Optimal Window Counter:** Count of nodes currently in $R(t) \in [0.70, 0.85]$.
  - **Hypercorrection Alert Badge:** Count of nodes flagged with high-confidence errors (`hypercorrection_flag == 1`).
  - **Metacognitive Calibration Badge:** Mean Brier Score & Over/Under-confidence indicator.

### 6.2 View 1: Active Learning Session (`EpistemicLockBox.tsx`, `ReadingStreamBox.tsx`, `TelemetryInputDock.tsx`, `DependencyMiniMap.tsx`)
- **Left Sidebar (`SidebarSubagentDock.tsx`):**
  - `"New Session"` launcher supporting custom topic prompts, mode selection (`Probe -> Teach`, `Productive Failure -> Teach`, `Adaptive Practice`, `Proof-Referee Duel`, `Feynman Student Duel`), and attaching local `.tex`/`.pdf` files from `workspace/`.
  - **Live 8-Sub-Agent Swarm Monitor:** Displays real-time status cards for all 8 sub-agents (`SYMBOLIC_VERIFIER`, `BUG_LIBRARY_DIAGNOSTICIAN`, `SANDBOX_DEMO_BUILDER`, etc.). Clicking any artifact opens a modal showing the exact SymPy verification script, JSON cognitive diagnosis, or RAG excerpt.
- **Center Cognitive Stream:**
  - **The Two-Stage Epistemic Lock (`EpistemicLockBox.tsx`):**
    - Whenever a `PROBE`, `PREDICT`, or `CHECK` step is active, the multiple-choice options are visually locked (blurred card with lock icon: *"Epistemic Lock Active: Log your raw stream-of-consciousness prediction or intuition first to prevent recognition cues from contaminating retrieval"*).
    - Once the user types or dictates at least 15 characters into the `Raw Prediction` field and clicks **`Lock In Raw Prediction (Cmd+Enter)`**, the lock opens smoothly, recording the exact locked prediction timestamp and revealing the diagnostic options (or direct symbolic verification prompt).
  - **Inline Sentence & Equation Highlighting (`ReadingStreamBox.tsx`):**
    - During the `TEACH` explanation step, the user can select/highlight any text or click any equation block to attach an anchored `Thinking-While-Reading` note, or type/dictate continuously into the persistent `"Thinking while reading (stream of consciousness)..."` field.
  - **The Tri-Modal Telemetry Input Dock (`TelemetryInputDock.tsx`):**
    - **LaTeX-Aware Textarea + Live KaTeX Preview Bar:** As the user types LaTeX (e.g., `q^\top R_{\Theta, n-m} k`), a live preview strip immediately below renders the formatted math in real time.
    - **Quick Math Snippet Toolbar & `scratch.tex` Pull:** One-click buttons for `\frac{}{}`, `\sum`, `\int`, `\mathbb{E}[]`, `\text{Var}()`, `\nabla`, matrix templates, plus an automatic live-sync toggle that mirrors `workspace/scratch.tex` whenever the file is saved in the terminal.
    - **Voice Dictation + Acoustic Prosody Meter (`prosodyAudioEngine.ts`):**
      - Push-to-talk button (or `Ctrl+Space` toggle).
      - Displays a live 12-bar audio waveform visualizer + real-time prosody metrics: `Initial Latency (ms)`, `Hesitation Pauses`, `Hedge Words ("uh", "maybe", "guess", "wait")`, and `WPM`.
    - **Epistemic Confidence Slider (0% – 100%):**
      - Interactive gradient slider (`0% Pure Guess` $\to$ `25% Doubtful` $\to$ `50% Coin Flip` $\to$ `75% Fairly Confident` $\to$ `95%+ Certain`) with a warning indicator showing that errors at $\ge 75\%$ trigger a **Hypercorrection Flag**.
- **Right Pane (`DependencyMiniMap.tsx`):**
  - Renders the live vertical dependency tree for the current session, showing how each prerequisite node feeds into the goal, the current `Step Velocity Delta` ($\Delta \in [0.5, 2.5]$), and any dynamically spawned remedial sub-nodes.

### 6.3 View 2: The Epistemic Hypergraph Visualizer (`HypergraphCanvas.tsx`)
Build a high-performance interactive HTML5 Canvas / WebGL graph explorer with smooth pan, zoom, node dragging, hover highlighting of upstream/downstream Markov blankets, and these exact controls:
1. **`Lock Y-Axis to Logical Depth` Toggle Switch:**
   - When ON: Pins `logical_depth = 0` (`AXIOM` / unconditional observations) at the bottom layer and arranges derived propositions strictly upward by `logical_depth` ($y = H - \text{depth} \times 130\text{px}$), with spring relaxation along the X-axis so every `DEDUCTION` arrow flows cleanly upward!
   - When OFF: Runs a smooth physics-based force-directed cluster layout.
2. **4 Visual Color-Coding Modes (Toolbar):**
   - `1. Domain Clusters`: Colors nodes by mathematical/CS domain (`Measure-Theoretic Probability` = Indigo, `Transformers & Attention` = Emerald, `Reinforcement Learning` = Amber, `Linear Algebra & Functional Analysis` = Cyan, `Buggy Rules` = Rose).
   - `2. Bayesian Mastery P(L)`: Smooth heatmap from Rose ($P(L) < 0.35$) to Amber ($0.55$) to Emerald ($P(L) \ge 0.85$).
   - `3. FSRS Retrievability & Bjork Window`: Highlights nodes currently inside Bjork's Desirable Difficulty Window ($0.70 \le R(t) \le 0.85$) with a glowing cyan outer ring, fresh nodes ($R > 0.85$) in slate-emerald, and decaying nodes ($R < 0.70$) with a pulsing red urgency ring.
   - `4. Hypercorrection & Buggy Rules`: Spotlights nodes with `hypercorrection_flag == 1` and renders dashed crimson links to any attached `BUGGY_RULE` misconception nodes.
3. **Hyperedge Visual Semantics:**
   - `DEDUCTION` ($\{A, B\} \implies C$): Directed solid lines from premises $A, B$ converging into a small diamond **Conjunction Hub Node ($\land$)**, with a bold arrow pointing into conclusion $C$.
   - `CONTRASTIVE` ($u \perp v$): Bi-directional dashed amber line with a `⊥` badge at the midpoint.
   - `ISOMORPHISM` ($u \cong v$): Glowing violet double-line with a `≅` badge bridging across domain clusters.
   - `CUE_TRIGGER` ($c \leadsto m$): Dotted cyan arrow.
4. **Slide-Over Node & Hyperedge Inspector Drawer:**
   - Clicking any node or hyperedge opens a detailed inspector showing:
     - Full rendered KaTeX statement, intuition summary, and formal proof sketch.
     - Live BKT Mastery $P(L_t)$, FSRS Stability $S$ (days), Difficulty $D$, and current Retrievability $R(t)$.
     - **5D Cue-Breadth Pentagon / Progress Bars** (`Symbolic`, `Disguised Notation`, `Geometric`, `Computational`, `Adversarial`).
     - Incoming premise chains, outgoing conclusions, and contrastive boundary peers.
     - One-click buttons: **`Practice This Node Now`**, **`Launch Proof-Referee Duel on This Node`**, and **`Jump to Source Session`**.

### 6.4 View 3: Practice & Adversarial Referee Arena (`PracticeArena.tsx` & `RefereeDuelArena.tsx`)
1. **Cue-Demand Practice Stream (`PracticeArena.tsx`):**
   - Header controls to pick **Cue Obfuscation Level (1 to 4)**, toggle **Contrastive Pair Mode**, or import a problem file from `workspace/problems/`.
   - **Chunked Stream-of-Consciousness Submission:** Users submit incremental raw thinking chunks (`Shift+Enter`). After each chunk, the `BUG_LIBRARY_DIAGNOSTICIAN` and `SYMBOLIC_VERIFIER` evaluate whether the core demand is satisfied or if a subtle slip occurred.
   - **Interactive 5-Rung Socratic Hint Ladder (`R0` $\to$ `R4`):** Visual stepper bar allowing the learner to unlock one hint rung at a time (`R0 Dimensional Check`, `R1 Attention Pointer`, `R2 Cue Prime`, `R3 Scalar/2D Base Case`, `R4 Worked Analog`) while showing how each rung impacts the FSRS stability multiplier.
   - **Collapsible Assessment Metadata Card:** Shows the exact JSON metadata wired back into the hypergraph (`Target Nodes`, `Cue Level`, `Outcome`, `Max Hint Rung`, `Miss Class`, `Trace Quality Score`, `Confidence vs. Accuracy`, `BKT Delta`, and `FSRS Stability Delta +days`).
2. **Adversarial Referee & Feynman Duel (`RefereeDuelArena.tsx`):**
   - **Mode A — `Proof-Referee Debugger`:** Renders a multi-step mathematical proof as clickable numbered step cards (`Step 1` ... `Step 5`). Exactly one step contains a camouflaged mathematical fallacy (e.g., swapping $\lim$ and $\int$ without dominated convergence, assuming $(AB)^\top = A^\top B^\top$, or ignoring correlation in variance sums). The learner clicks the flawed step card, explains the violated hypothesis in the thinking box, provides a minimal counterexample, and sets their confidence slider.
   - **Mode B — `Feynman Buggy-Student Duel`:** A simulated student agent holding a specific `BUGGY_RULE` misconception asks the learner to explain a proposition. The student agent stress-tests the learner's explanation against edge cases until the learner states the exact rigorous boundary conditions.

### 6.5Sandboxed Interactive Demo Viewer (`SandboxDemoViewer.tsx`)
- Renders interactive HTML5 Canvas / SVG demos generated by `SANDBOX_DEMO_BUILDER`.
- Includes an explicit **`Invert Colors / Dark-Mode Guard`** toggle button in the frame header (just like Eero's anti-flashbang switch, plus default dark theme injection).
- Listens for `window.addEventListener('message')` events (`HARNESS_DEMO_TELEMETRY`) from the iframe and displays a live **"Sandbox Telemetry Captured"** pill showing the exact slider parameters the learner tuned.

---

# 7. RICH CROSS-DOMAIN SEED DATASET (`backend/seed.py`)

Populate `harness.db` automatically on startup (when empty) with **20 nodes, 16 hyperedges, 3 pre-built interactive HTML5 Canvas/SVG demos, and 3 historical/active sessions** across four deeply connected mathematical and AI domains so every feature can be tested immediately:

1. **Cluster A — Linear Algebra & Functional Analysis Foundations:**
   - `ax_inner_product_bilinearity` (`AXIOM`, depth 0): Bilinearity and symmetry of inner products $\langle u, v \rangle = u^\top v$ on $\mathbb{R}^d$.
   - `ax_orthogonal_matrix_preserve` (`AXIOM`, depth 0): Orthogonal transformations $Q^\top Q = I$ preserve inner products and $\ell_2$ norms: $\langle Qu, Qv \rangle = u^\top Q^\top Q v = \langle u, v \rangle$.
   - `prop_2d_rotation_group` (`PROPOSITION`, depth 1): 2D rotation matrices $R(\theta)$ satisfy $R(\alpha)^\top R(\beta) = R(\beta - \alpha)$, depending strictly on relative angle $\beta - \alpha$.
   - `prop_banach_contraction` (`PROPOSITION`, depth 1): Banach Fixed-Point Theorem — any $\gamma$-contraction mapping $T: X \to X$ ($\gamma \in [0, 1)$) on a complete metric space $(X, d)$ admits a unique fixed point $x^* = Tx^*$ with geometric convergence $d(x_k, x^*) \le \gamma^k d(x_0, x^*)$.
   - `int_covector_hyperplanes` (`INTUITION`, depth 1): Geometric dual-coding of linear functionals / covectors $\omega \in V^*$ as oriented stacks of parallel level-set hyperplanes $\{v : \omega(v) = c\}$, connecting differential forms $df$ to gradient descent step geometry.

2. **Cluster B — Measure-Theoretic Probability & Mathematical Statistics:**
   - `ax_linearity_expectation` (`AXIOM`, depth 0): Linearity of expectation $\mathbb{E}[\sum_i a_i X_i] = \sum_i a_i \mathbb{E}[X_i]$ holds unconditionally without requiring independence.
   - `prop_var_indep_sum` (`PROPOSITION`, depth 1): For uncorrelated/independent random variables $X_1, \dots, X_d$ with variance $\sigma^2$, $\text{Var}(\sum_{i=1}^d X_i) = d\sigma^2$, whereas $\text{Var}(c X) = c^2 \text{Var}(X)$.
   - `prop_var_product_indep` (`PROPOSITION`, depth 1): If $X, Y$ are independent with $\mathbb{E}[X] = \mathbb{E}[Y] = 0$ and $\text{Var}(X)=\sigma_X^2, \text{Var}(Y)=\sigma_Y^2$, then $\text{Var}(XY) = \mathbb{E}[X^2]\mathbb{E}[Y^2] = \sigma_X^2 \sigma_Y^2$.
   - `prop_jensen_convex_max` (`PROPOSITION`, depth 1): By Jensen's inequality and convexity of the pointwise maximum operator $\phi(x) = \max_a x_a$, for any random vector $Z$, $\mathbb{E}[\max_a Z_a] \ge \max_a \mathbb{E}[Z_a]$ (strict inequality when components have non-degenerate noise).
   - `prop_dct_vs_mct` (`PROPOSITION`, depth 2): Dominated Convergence Theorem ($\vert f_n \vert \le g \in L^1$) vs. Monotone Convergence Theorem ($0 \le f_n \uparrow f$).
   - `cnt_unbounded_indicator_escape` (`COUNTEREXAMPLE`, depth 2): Sequence $f_n = n \cdot \mathbf{1}_{(0, 1/n)}$ converges pointwise to $0$ on $(0, 1)$ with $\int f_n \, d\lambda = 1 \neq \int \lim f_n \, d\lambda = 0$, falsifying naive exchange of $\lim$ and $\int$ without a dominating $L^1$ envelope.
   - `bug_uncorrelated_implies_indep` (`BUGGY_RULE`, depth 1): Recurring misconception that $\text{Cov}(X, Y) = 0 \implies X \perp\!\!\!\perp Y$ (falsified by $X \sim \mathcal{N}(0,1), Y = X^2$).

3. **Cluster C — Transformer Architecture & Attention Mathematics:**
   - `prop_row_local_mlp` (`PROPOSITION`, depth 1): Right-multiplying token matrix $X \in \mathbb{R}^{T \times d}$ by weight matrix $W \in \mathbb{R}^{d \times d'}$ and applying coordinate-wise activation $\sigma(XW)$ acts independently on each row $x_t^\top$, causing zero cross-position information mixing.
   - `prop_causal_mask_support` (`PROPOSITION`, depth 1): Adding causal mask $M_{ij} = 0$ for $j \le i$ and $-\infty$ for $j > i$ before row-wise softmax forces attention weights $A_{ij} = 0$ for all future tokens $j > i$, restricting output row $i$ to $\text{span}\{v_1, \dots, v_i\}$.
   - `prop_scaled_dot_product_variance` (`PROPOSITION`, depth 2, deduced via `DEDUCTION` hyperedge from `prop_var_indep_sum` + `prop_var_product_indep`): When $q, k \in \mathbb{R}^{d_k}$ have i.i.d. entries with mean $0$ and variance $1$, $q^\top k = \sum_{i=1}^{d_k} q_i k_i$ has mean $0$ and variance $d_k$; dividing by $\sqrt{d_k}$ scales variance by $(1/\sqrt{d_k})^2 = 1/d_k$, restoring $\text{Var}(q^\top k / \sqrt{d_k}) = 1$ and preventing softmax saturation into vanishing-gradient regions.
   - `prop_rope_relative_invariance` (`PROPOSITION`, depth 2, deduced via `DEDUCTION` hyperedge from `ax_orthogonal_matrix_preserve` + `prop_2d_rotation_group`): Rotary Positional Embeddings (RoPE) apply block-diagonal 2D rotations $R_{\Theta, m}$ so that $\langle R_{\Theta, m} q, R_{\Theta, n} k \rangle = q^\top R_{\Theta, m}^\top R_{\Theta, n} k = q^\top R_{\Theta, n-m} k$, encoding relative position $n - m$ directly into the inner product.
   - `move_scalar_base_case_check` (`MOVE`, depth 1): When verifying a multi-head tensor or matrix derivative identity, first reduce to the $1 \times 1$ scalar case and check variance/dimension scaling powers.

4. **Cluster D — Markov Decision Processes & Deep Reinforcement Learning:**
   - `prop_bellman_sup_norm_contraction` (`PROPOSITION`, depth 2, deduced from `prop_banach_contraction` and connected via an `ISOMORPHISM` edge to contraction iterations): The Bellman optimality operator $(\mathcal{T}^* V)(s) = \max_a [R(s,a) + \gamma \sum_{s'} P(s'\mid s,a)V(s')]$ is a $\gamma$-contraction in the supremum norm $\|\mathcal{T}^* U - \mathcal{T}^* V\|_\infty \le \gamma \|U - V\|_\infty$, guaranteeing a unique fixed point $V^*$.
   - `prop_qlearning_maximization_bias` (`PROPOSITION`, depth 2, deduced via `DEDUCTION` hyperedge from `prop_jensen_convex_max` + `prop_bellman_sup_norm_contraction`): Standard Q-learning targets $Y_t = R_{t+1} + \gamma \max_a Q_\theta(S_{t+1}, a)$ suffer systematic positive overestimation bias $\mathbb{E}[\max_a \hat{Q}(s', a)] > \max_a \mathbb{E}[\hat{Q}(s', a)]$ when action-value estimates contain zero-mean noise.
   - `prop_double_dqn_decoupling` (`PROPOSITION`, depth 3, connected via `DEDUCTION` from `prop_qlearning_maximization_bias` and `CONTRASTIVE` edge against standard DQN): Double DQN decouples action selection $a^* = \arg\max_a Q_\theta(S_{t+1}, a)$ from action evaluation $Q_{\theta^-}(S_{t+1}, a^*)$, eliminating upward maximization bias when estimation errors between $\theta$ and $\theta^-$ are decorrelated.

5. **Pre-Built Interactive Sandbox Demos & SVG Diagrams (Seeded in `subagent_artifacts`):**
   - **Demo 1 (HTML5 Canvas):** *Attention Logit Variance & Softmax Entropy Saturation Explorer* — Interactive sliders for dimension $d_k \in [1, 512]$, temperature scaling $\tau$, and input variance $\sigma^2$, plotting the empirical distribution of $q^\top k / \tau$, softmax Jacobian norm $\|\nabla \text{softmax}\|_F$, and a goal challenge to restore non-vanishing gradients at $d_k = 256$.
   - **Demo 2 (HTML5 Canvas):** *SGD & Momentum Trajectory on Anisotropic Quadratic Loss Surface* — Interactive contour canvas with sliders for learning rate $\eta$, momentum $\beta$, and Hessian condition number $\kappa$, plus dark-mode invert guard and live slider telemetry back to the parent window.
   - **Demo 3 (Interactive SVG):** *RoPE Block-2D Relative Rotation & Bellman $\ell_\infty$ Contraction Funnel Diagrams*.

---

# 8. VERIFICATION, TESTING & ONE-COMMAND LAUNCH

1. **Automated Backend Test Suite (`backend/tests/`):**
   Write and run `pytest` covering:
   - `test_fsrs_bjork_disuse()`: Verifies $R(t, S)$ decay and proves that recall at $R \approx 0.78$ produces a larger stability gain $\Delta S$ than immediate cramming at $R \approx 0.99$.
   - `test_bkt_trace_quality_and_propagation()`: Verifies that a lucky guess with low `trace_quality_score` does not falsely spike $P(L_t)$, that `NOTATION_OBSTRUCTION` softens slip penalty, and that mastering conclusion $C$ propagates positive belief to premises $A, B$.
   - `test_active_probe_mutual_information()`: Verifies `select_next_probe_node` picks the highest-leverage midpoint node in a dependency DAG.
   - `test_hypercorrection_trigger()`: Verifies that an incorrect answer with `confidence_slider = 0.85` sets `hypercorrection_flag = 1` and `outcome = 'HIGH_CONFIDENCE_ERROR'`.
   - `test_sympy_verifier_and_api()`: Tests `verify_math_sympy` subprocess execution and all FastAPI REST/WebSocket endpoints across all 6 modes (`PROBE`, `PRODUCTIVE_FAILURE`, `TEACH`, `PRACTICE`, `REFEREE_DUEL`).
2. **Frontend Production Build Verification:**
   Run `npm install && npm run build` inside `frontend/` and fix any TypeScript or Vite bundling issues until it exits with code `0`.
3. **Executable Launchers (`./start.sh` and `./harness-cli`):**
   - Make both `chmod +x`.
   - `./start.sh` must start the FastAPI server (`port 8000`) and Vite frontend (`port 5173`), wait until both health checks respond `200 OK`, and print a clean terminal dashboard showing the URL (`http://localhost:5173`), the live scratchpad path (`workspace/scratch.tex`), and available `./harness-cli` commands (`status`, `due`, `graph`, `scratch`).

Begin immediately with Step 0 (`CLAUDE.md` and `ARCHITECTURE_SPEC.md`) and execute the entire build through final server verification.
