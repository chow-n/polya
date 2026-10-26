---
slug: explain
status: approved
bead: none (learn-harness is not a gc rig)
approved_by: Nathan ("yes", 2026-10-26)
approved_at: 2026-10-26
---
# Ask Pólya: explanations on request and when the evidence says you need one

## Goals
1. The learner can ask for an explanation, or any question, at any point in a session, in a side chat that knows
   the current card.
2. Pólya offers an explanation on its own when the evidence says it would help, and stays quiet when it would not.
3. Explanations close the loop: a skippable one-line "say it back" feeds the learner model.

## Non-goals
- No change to the step state machine (PREDICT → READING → CHECK, probes, practice ladder) or to scoring rules.
- No new step kinds and no auto-inserted explanation steps (D2 rejected alternative).
- Not a general chatbot: replies stay grounded in the session's ideas, notes and paper; off-topic questions get a
  short answer and a pointer back.

## Science behind the policy
- **When to offer** (the assistance dilemma, Koedinger & Aleven 2007): give help after an attempt, not before.
  Explanations land better once the learner has met the problem (Kapur's productive failure; Schwartz & Bransford
  1998, "A time for telling"). So no offers before a first attempt, and none at all on productive-failure steps
  until their result is shown.
- **Errors**: elaborated feedback beats right/wrong feedback (Shute 2008). For a confident error, use a refutation
  explanation that names the wrong belief and says why it fails (Butterfield & Metcalfe 2001; Tippett 2010).
- **Wheel-spinning**: after two failed attempts on one idea, struggle stops paying off (Beck & Gong 2013). Offer a
  worked example instead (the worked-example effect, Sweller).
- **Confusion**: confusion helps only when it gets resolved (D'Mello et al. 2014). Offer a nudge when the learner
  is stuck, but never force one.
- **Expertise reversal** (Kalyuga 2003): detailed explanations help novices and slow down experts. The style
  follows P(L):
  - < 0.40: a worked example on the smallest concrete case.
  - 0.40–0.85: contrast the learner's attempt with the right idea (Loibl & Rummel 2014).
  - ≥ 0.85: terse, and no offers.
- **Say it back** (self-explanation effect, Chi et al. 1989/1994; ICAP, Chi & Wylie 2014): restating the idea is
  constructive, which beats passive reading. Recall right after an explanation is short-term evidence, so it is
  weighted down (FR6).
- **Explain differently** (dual coding, Paivio and Mayer): rotate the representation between concrete case,
  picture/geometry, symbols and computation.

## User-facing behaviour
- The focus strip gains an **Ask** button (shortcut `?`) that opens the **Ask Pólya** side chat. On wide screens it
  docks to the right of the card, and when Advanced is on it replaces the dependency rail while open. On narrow
  screens it is a bottom sheet. It is closed by default.
- The chat header names the current card ("About: Scaled dot-product variance"). Quick chips sit above the input:
  **Explain this**, **Explain differently**, **Simpler**. A free-text box takes any question
  ("why √d and not d?"). The thread lasts for the whole session, and each reply is tagged with the card it was about.
- **Offers** appear:
  - as one quiet line in the result block ("Want to see why? Ask Pólya →");
  - as a line under the card for a stuck nudge;
  - as a dot on the Ask button.
  Clicking opens the chat and sends the offer's request. Offers never open the chat by themselves.
- After each explanation, the chat shows **"In one line, in your own words: …?"**:
  - **Skip** dismisses it.
  - Submitting it gives a one-line verdict ("Got it" / "Close — you left out …").
- While the AI answers, the chat shows a typing indicator ("Pólya is writing… up to ~30 s"). Without an engine,
  replies come from the deterministic explainer, labelled "(offline explanation)".

## Architecture and integration decisions
- **D1 (accepted): full explanations at any time, with no scoring penalty.**
  - Why: Nathan wants the chat usable as a reference.
  - Rejected: holding back the answer and counting the attempt as assisted (that keeps the model honest).
  - Mitigation: each thread message stores `before_answer` (asked on a graded step before submitting). Model-eval
    can later measure whether those answers inflate mastery.
- **D2 (accepted): evidence-based offers.** See FR3, which holds the exact triggers and suppressions.
  - Rejected: offers after wrong answers only (misses the lucky-guess and stuck cases).
  - Rejected: auto-inserted steps (they take control away from the learner).
- **D3 (accepted): a session side chat.**
  - Rejected: a per-card button with follow-ups.
  - Rejected: a single button.
  - The chat follows the active card, so it gives most of the per-card benefit.
- **D4 (accepted): a skippable say-it-back that updates the model.**
- **D5 (default): style follows P(L), per the expertise-reversal bands above.**
- **Storage:** a new side table `explanations`. The original DDL is untouched, the same pattern as
  `model_predictions`.

## Existing components to reuse (do not rebuild)
- `backend/agents/prompts.py`: `CORE_LAWS`, `node_context`, `delta_instruction` style.
- `backend/agents/topic_map.py:notes_context`, `orchestrator.paper_context`. Grounding comes from the session's notes
  and paper.
- `backend/agents/orchestrator.py`:
  - `_load`/`_persist`, `apply_assessment` (BKT/FSRS/Brier, `log_prediction`).
  - The `hint` cap pattern (`RUNG_ORDER`) and `content_for`. The deterministic explainer reads the bank's `reading`,
    `explanation` and `canonical_insight`.
- `backend/agents/subagents.diagnose`: grades the say-it-back (trace quality q, miss_class).
- `backend/db.py`: the side-table pattern and `recent_successes`.
- Frontend:
  - `stepParts.tsx:ResultBlock` (hosts the offer line) and `kit.tsx` primitives.
  - `SessionFocus.tsx` strip and rails.
  - `MathText` for KaTeX.

## Interfaces and data contracts
- **Table** (owner: `backend/db.py`):
  `explanations(id, session_id, step_index, node_id, role CHECK IN ('learner','polya','say_back'), kind, text,
  trigger, style, engine, before_answer INTEGER, created_at)`.
  - `kind` is one of `ASK`, `EXPLAIN`, `DIFFERENT`, `SIMPLER`, `OFFER`, `SAY_BACK`.
  - `trigger` is one of `''`, `WRONG`, `CONFIDENT_WRONG`, `WEAK_REASONING`, `WHEEL_SPINNING`, `STUCK`.
- **`POST /api/sessions/{id}/explain`** `{action: ASK|EXPLAIN|DIFFERENT|SIMPLER|OFFER, message?: str, trigger?: str}`
  returns `ExplainReply {reply_markdown, style, engine, node_id, say_back_prompt: str|null, thread: [ExplainMsg]}`.
- **`GET /api/sessions/{id}/explain`** returns `{thread, offer: Offer|null}`. This restores the chat on reload.
- **`POST /api/sessions/{id}/say-back`** `{text, confidence?}` returns
  `{verdict_markdown, is_correct, trace_quality_score, node_update}`.
- **`StepResult.offer`** (new optional field): `{trigger, label, action}`. It is computed in `submit` from that
  step's evidence.
- **`SessionState.stuck_after_ms`** (new field): the stuck threshold for the client (FR3).
- **`StepSubmission.elapsed_ms`** (new optional field): time from the card shown to the submit. It is stored in the
  history entry.
- **Prompt** `prompts.EXPLAINER`:
  - Inputs: CORE_LAWS (Law 1 adapted: the learner asked, so derivations are allowed), the node context with its
    premises' reasoning chains, the card's prompt and options, the learner's attempt if any, notes/paper grounding,
    the style band, the trigger, and the last 6 thread messages.
  - Output: JSON `{reply_markdown ≤ 220 words, say_back_prompt}`.
- **TypeScript mirrors** go in `frontend/src/types/harness.ts`. Store actions go in `useHarnessStore.ts`:
  `askPolya`, `sayBack`, `loadThread`, `chatOpen`.

## Functional requirements
- **FR1 Ask any time.** `/explain` works on every step kind, before or after submitting, including COMPLETE (where
  it explains the session's goal).
  - The reply is about the active card's first target node. A free-text question that names another idea in the
    plan is answered about that idea.
  - Replies store `before_answer = 1` when asked on a graded step (PROBE/CHECK/PRACTICE_CHUNK/REFEREE/FEYNMAN)
    before submission.
  - Scoring is unchanged (D1).
- **FR2 Style.** `style` is chosen from the node's P(L) at the time of the request:
  - `WORKED_EXAMPLE` when < 0.40;
  - `CONTRAST` when 0.40–0.85 and an attempt exists, else `EXPLAIN`;
  - `TERSE` when ≥ 0.85.
  - `SIMPLER` forces `WORKED_EXAMPLE`.
  - `DIFFERENT` rotates the representation (concrete → geometric → symbolic → computational), skipping the last one
    used in this thread.
  - Confident-wrong triggers use `REFUTATION`, which names the learner's wrong claim and the `BUGGY_RULE`, if
    diagnose found one.
- **FR3 Offer policy** (`backend/agents/explain.py:offer_for`, a pure function, unit-tested):
  - After a graded submit, return the first trigger that applies:
    1. `CONFIDENT_WRONG` (outcome HIGH_CONFIDENCE_ERROR);
    2. `WHEEL_SPINNING` (this plan item has ≥ 2 failed attempts, or 2 consecutive failures on the node across
       sessions);
    3. `WRONG` (is_correct 0);
    4. `WEAK_REASONING` (is_correct 1 and q < 0.45).
  - Suppressed when:
    - the node's P(L) after the update is ≥ 0.85;
    - an explanation of this node was already shown in this step;
    - the step is PREDICT/READING.
  - Stuck nudge (client-side):
    - Threshold: `stuck_after_ms = max(90 s, 2 × median elapsed_ms of the last 20 graded steps)`, or 120 s with
      fewer than 5 samples.
    - Fires when time on card ≥ threshold, fewer than 40 characters are typed, the step is graded and unsubmitted,
      and the step is not PRODUCTIVE_FAILURE.
    - It sends `trigger = STUCK`. The explainer then gives a setup nudge (what is being asked, which earlier idea is
      relevant, the smallest case to try) and never the answer.
    - At most one stuck nudge per card.
- **FR4 Grounding.** Every explainer call includes:
  - the node's statement, intuition and proof sketch;
  - the premises' reasoning chains (`he_*` DEDUCTION edges into the node);
  - `_controller.notes` and the paper passage when present.
  - A reply that uses a notes passage cites its label.
- **FR5 Deterministic explainer** (no engine, or the engine failed):
  - `EXPLAIN`/`TERSE`: the bank `reading`, else intuition + statement.
  - `WORKED_EXAMPLE`: the bank R3/R4 hint text and the reading.
  - `CONTRAST`/`REFUTATION`: the answer explanation, plus the buggy rule's statement and its falsifier.
  - `DIFFERENT`: the next available field (intuition / statement / proof sketch / premise chain).
  - Free-text questions: the best `corpus_search` block on the question's distinctive terms plus the node summary.
  - These replies are labelled `engine: deterministic`.
- **FR6 Say it back.**
  - Grading: `subagents.diagnose` with concept groups from the bank (else the node's key terms).
  - Pass: is_correct 1 when concept coverage ≥ 0.5.
  - Recording: a trace with phase `CHECK`, `prompt_shown_latex = "Say it back: …"`, `max_hint_rung` forced to `R2`
    (an explanation was just shown, so the FSRS rating is capped at 2, "Hard"), the confidence from the request
    (default 0.5), and `apply_assessment` as usual.
  - It does not advance the step, and does not feed the difficulty controller or splice remedial steps.
  - Skipping records nothing.
- **FR7 Thread persistence.**
  - `GET /explain` returns the session thread in order and the pending offer, if any.
  - Threads survive reload and app restart.
  - Session deletion cascades.

## Non-functional requirements
- At most one explainer LLM call per request (timeout 90 s). The deterministic fallback replies in under 200 ms.
- No new network services. The prompt sends nothing beyond what step generation already sends.
- Keyboard and accessibility:
  - `?` opens and closes the chat; `Esc` closes it.
  - Enter sends; Shift+Enter adds a newline.
  - The chat is `aria-live="polite"`, and focus returns to the card on close.
- Light and dark themes use the existing tokens. At phone width the chat is a bottom sheet.

## Edge cases and failure behaviour
- Ask while the next step is being prepared: the request queues against the step the learner is looking at (the
  held card if shown).
- Stale step (the active step changed during a slow reply): the reply is still stored and tagged with its original
  `step_index`, and the chat shows it under that card's divider.
- Paper sessions: grounding uses `paper_context`, and the skim step explains the paper's question, not its answer.
- Duplicate offer clicks are idempotent per (step_index, trigger).
- If the say-back text is empty or under 8 characters, a 422 is returned and the UI keeps the box open.
- Each reply has a ⧉ copy button. No other chat history UI.

## Acceptance and verification
- **`backend/tests/test_explain.py`** (deterministic engine, fake LLM via monkeypatch):
  - `offer_for` truth table: each trigger, the P(L) ≥ 0.85 suppression, PREDICT/READING suppression and the
    already-explained suppression (FR3).
  - Ask before answering a CHECK → reply stored with `before_answer = 1`. The later submit's scoring is identical
    to the case with no ask (D1/FR1).
  - Style selection by P(L), `SIMPLER` and the `DIFFERENT` rotation (FR2). A confident-wrong submit returns
    `offer.trigger == "CONFIDENT_WRONG"`, and the refutation prompt names the buggy rule (FR3/FR2).
  - The explainer prompt contains the premise reasoning chain and the notes block for a notes-grounded session (FR4).
  - With no engine, every action returns a non-empty deterministic reply (FR5).
  - Say-back adds a CHECK trace with `max_hint_rung == "R2"` and moves BKT, while Δ and the plan are unchanged (FR6).
  - `GET /explain` returns the thread after reload (FR7).
  - `stuck_after_ms` is computed from history `elapsed_ms` (FR3).
- **`make test` green; `cd frontend && npm run build` exit 0.**
- **Live check** with claude_cli (and chatgpt_browser if selected):
  - ask "why √d and not d?" on the scaled dot-product card;
  - answer a CHECK wrong with 90% confidence → see the refutation offer → accept → say it back.
  - Screenshots go in the scratchpad.

## Decomposition sketch (one worker, sequential)
1. **Backend core (prefactor + slice):**
   - `explanations` table and CRUD;
   - `explain.py` with `offer_for`, `style_for`, the deterministic explainer and `prompts.EXPLAINER`;
   - `/explain` GET/POST and `/say-back`;
   - `StepResult.offer`, `elapsed_ms`, `stuck_after_ms`;
   - tests.
2. **Frontend slice:**
   - types and store actions;
   - the `AskPanel.tsx` side chat (docked / bottom sheet) and the Ask button on the strip;
   - the offer line in ResultBlock and the stuck nudge timer in SessionFocus;
   - the say-it-back box.
3. **Live check, CLAUDE.md "Explanations" section, `make bundle` reinstall.**

## Risks, assumptions, deferred decisions
- RISK (D1): reading the full answer before answering inflates P(L). It is visible later via `before_answer` in
  model-eval. Deferred: a scoreboard row "answers after asking".
- ASSUMED: P(L) bands 0.40/0.85 and stuck threshold max(90 s, 2× median), with 120 s when cold.
- ASSUMED: the say-back is weighted down via the R2 cap rather than a new BKT parameter.
- ASSUMED: replies ≤ 220 words. This bends Law 4's 180 for asked-for explanations, but they stay short.
- DEFERRED: voice questions in the chat (the VoiceRow exists, but is not wired here). Explanation effectiveness
  analytics (success on the next CHECK after an explanation).
