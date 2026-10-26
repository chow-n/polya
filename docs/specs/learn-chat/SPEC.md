---
slug: learn-chat
status: approved
bead: none (learn-harness is not a gc rig)
approved_by: Nathan ("Yes, build both", 2026-10-26)
approved_at: 2026-10-26
---
# Learn chat: first exposure as a sourced conversation, until you're ready to recall

## Goals
1. Ideas the learner has never studied are first taught as a conversation (a chat in the main card), not quizzed.
2. The chat draws on sources: the learner's notes and papers first, then open sources fetched for the topic, cited.
3. Pólya moves to recall when its learner model predicts recall will mostly succeed. Recall starts after a short
   lag and interleaves the ideas.

## Non-goals
- No change for ideas with history: probe → predict → read → check, the practice ladder, referee/Feynman, paper
  sessions and the 85% difficulty controller are unchanged.
- No paid or keyed search APIs. No browsing beyond the two open sources (Wikipedia, arXiv).
- Builds on `docs/specs/explain` (approved). This spec supersedes that spec's non-goal "no new step kinds".

## Science behind the design
- **Explain before retrieval for new material.** Retrieval practice strengthens what was encoded. With nothing
  encoded, recall mostly fails. Its benefit is largest when initial retrieval mostly succeeds (Rowland 2014
  meta-analysis), so first exposure is study, not a test.
- **Interactive beats passive** (ICAP, Chi & Wylie 2014). Each tutor turn is short (Law 4) and ends with one small
  question: elaborative interrogation (Pressley 1987; Dunlosky 2013) or a "what happens when d = 1?" prediction.
  The learner's replies are the evidence for readiness.
- **Prior-knowledge activation.** The chat opens with "What do you already know about X?" (Ausubel's advance
  organisers). This doubles as a cheap, open pretest.
- **Bottom-up order** (Law 2): ideas are taught in plan order, premises before conclusions.
- **Readiness = predicted recall ≥ 0.70.** Predicted recall is P(correct) = P(L)(1−s) + (1−P(L))·g, the same
  quantity the model scoreboard logs. One good self-generated answer (q ≥ 0.75) lifts a new idea from 0.15 past the
  bar; a lucky or weak one (q < 0.45) barely moves it. That is the trace-quality guard in §3.2.
- **A short lag and interleaving before recall** (lag effect, Cepeda 2006; interleaving, Rohrer & Taylor 2007).
  Recall starts with the idea learned earliest, so every idea has some delay and the questions mix ideas.

## User-facing behaviour
- Start a goal as today. If the plan has a run of ideas the learner has never studied, the first card for that run
  is a chat titled "Learning: <goal>".
- **Opening.** Pólya asks what the learner already knows; they can reply or press **Skip**. Then, idea by idea:
  - a short grounded explanation (≤ 180 words, KaTeX, inline citations `[1]`), then one small question;
  - the learner can answer, ask anything, press **Go on**, or press **Quiz me** (start recall now).
- **Progress.** A row of chips above the chat, one per idea in the run, fills as predicted recall rises. Hover shows
  "Ready to recall: 72%".
- **Next idea.** Pólya moves on when the current idea reaches 0.70 or after 4 exchanges. It says which applied:
  - "You've got this one — next: …"
  - "Let's move on; we'll come back to this in recall."
- **Ready.** When every idea in the run is covered, Pólya says "You're ready to try recalling these" and a primary
  **Start recall** button appears. Recall cards (CHECK, cue level 2) follow, earliest-learned idea first, with the
  usual scoring, explanations offers (explain spec) and remediation.
- **Sources.** A **Sources** disclosure under the chat lists [n] title, site and link. Notes passages show their
  `path:line`. Without sources (offline / fetch failed), replies are labelled "from the AI's own knowledge".
- The learn chat and the Ask Pólya side chat share one session thread, so later Ask Pólya shows the conversation.
  While the learn chat is the main card, the Ask button is hidden.

## Architecture and integration decisions
- **D1 (accepted):** automatic for never-studied ideas, i.e. `fsrs_reps == 0` and `brier_count == 0`. Ideas with
  history keep their flow. Rejected: every session; a separate mode.
- **D2 (accepted):** sources are tried in this order: notes/papers, fetched open sources (Wikipedia sections, arXiv
  abstracts), then marked AI knowledge. Rejected: no fetching; AI knowledge only.
- **D3 (accepted):** model-based readiness (≥ 0.70 predicted recall), Quiz me at any time, ≤ 4 exchanges per idea.
  Rejected: AI judgement only (unmeasured); learner-only (no guidance).
- **D4 (accepted):** delayed, interleaved recall, earliest idea first. Rejected: a check right after each idea.
- **D5 (default):** open with prior-knowledge activation (skippable).
- **Session order:** probes run only over ideas with history (EIG rule unchanged). Then the plan is walked in order:
  each maximal run of consecutive never-studied ideas becomes one LEARN step followed by its recall block. Other
  ideas go through predict → read → check as today.
- **Evidence weighting:** chat replies are scored like the explain spec's say-it-back:
  - `subagents.diagnose` grades them;
  - `apply_assessment` records them with `max_hint_rung = R2` (just explained, so the FSRS rating is capped at Hard);
  - telemetry phase is `CHECK`, prompt "Learn chat: …";
  - they are excluded from the difficulty controller's success window and never splice remedial steps.

## Existing components to reuse (do not rebuild)
- Explain spec:
  - the `explanations` thread table;
  - `explain.py` grounding, style-by-P(L) and the deterministic explainer;
  - the say-back grading path.
- `topic_map.notes_passages` / `notes_context`; `orchestrator.paper_context`; `prompts.node_context`, `CORE_LAWS`.
- `tools.search_arxiv` (with its offline fallback); `papers/fetch._get` (size cap, retries, offline guard).
- `orchestrator`:
  - `decide_next`, `build_plan`, `step_check`, `submit`;
  - `apply_assessment` / `log_prediction`;
  - `cm.select_next_probe_node`.
- Frontend: `MathText`, `kit.tsx` primitives, `SessionFocus` card slot, and the Ask Pólya message list component
  (shared).

## Interfaces and data contracts
- **New step kind `LEARN`:**
  - phase `READING`;
  - `_meta.learn = {ideas: [node_id…], current: int, exchanges: {id: n}, opened: bool}`.
  - The public step carries `learn_ideas: [{node_id, title, p_recall, status: todo|current|covered|moved_on}]`.
- **`POST /api/sessions/{id}/learn`** `{action: OPEN_REPLY|SKIP|REPLY|ASK|GO_ON|QUIZ_ME, message?}`:
  - returns `LearnTurn {thread: [ExplainMsg], learn_ideas, ready: bool, sources: [Source]}`;
  - `ExplainMsg.kind` adds `LEARN` and `LEARN_Q`.
  - Start recall = the existing `POST /submit` on the LEARN step. It records an EXPLORATION_LOGGED trace and
    `decide_next` returns the recall block.
- **Side table `session_sources`** (owner `backend/sources.py`):
  `(session_id, n, kind CHECK IN ('notes','paper','wikipedia','arxiv'), title, url, passage, fetched_at)`.
  `n` is stable per session (citation number).
- **`backend/sources.py`:**
  - `fetch_for(session_id, goal, idea_titles)` returns `list[Source]`. It covers the Wikipedia search + section
    extracts (the `action=query` API, plaintext, ≤ 6k chars per article) for the goal and ≤ 4 ideas, and the arXiv
    top 3 abstracts for the goal.
  - Timeouts: 8 s per request, 20 s total. Requests run in parallel, and the goal-level fetch runs concurrently with
    the topic map.
  - `passages_for(session_id, node)` returns the top 3 passages by distinctive-term score, ≤ 3,000 chars, with
    their [n].
- **Prompt `prompts.LEARN_TUTOR`:**
  - CORE_LAWS: Law 1 holds; build understanding in steps, don't dump derivations.
  - Inputs: node context, premises' chains, the learner's last replies, the passages with [n], the style band.
  - Output: JSON `{reply_markdown ≤ 180 words, question, concept_groups: [[str]], cited: [n]}`. `concept_groups`
    grades the learner's answer to `question`.
- **Prefs:** `fetch_sources: bool` (default true) in `~/Polya/prefs.json`, shown in Settings → Advanced
  ("Look up Wikipedia and arXiv for new topics").

## Functional requirements
- **FR1 New-idea detection.** `is_new(node) = fsrs_reps == 0 and brier_count == 0`. `decide_next`:
  - probes only non-new ideas;
  - groups consecutive new pending ideas in plan order into a LEARN step;
  - after the LEARN step is submitted, emits the recall block (FR6), then continues the plan.
  - Practice / referee / paper sessions never produce LEARN.
- **FR2 Opening.** The first LEARN turn asks what the learner already knows about the goal. The reply is stored and
  given to the tutor as prior knowledge. It is not graded. SKIP goes straight to idea 1.
- **FR3 Tutor turns.** Each turn targets `ideas[current]`. The style follows the explain spec's P(L) bands, and
  `ASK` answers the question and then returns to the idea. Every turn ends with exactly one small question, except
  ASK replies. A `REPLY` is graded against that question's `concept_groups` (FR4), and the next turn builds on it,
  CONTRAST style if partly wrong.
- **FR4 Readiness.**
  - After each graded reply, `p_recall = P(L)(1−s) + (1−P(L))·g` from the updated node.
  - The idea is `covered` when `p_recall ≥ 0.70`, or `moved_on` after 4 exchanges. A REPLY, GO_ON or ASK counts as
    an exchange, but GO_ON never grades.
  - `ready` is true when every idea is covered or moved_on.
  - QUIZ_ME sets `ready` at once. Remaining ideas are marked moved_on, and their recall comes after the covered ones.
- **FR5 Sources.**
  - Passages are cited in order: notes/papers first, then fetched open sources.
  - Fetches are kept per session and are idempotent.
  - With `fetch_sources` false, offline, or after a failed fetch, only notes are used, and AI-only turns carry
    `engine_note: "from the AI's own knowledge"`.
  - The tutor may cite only the passage numbers it was given; unknown `[n]` markers are stripped.
- **FR6 Recall block.**
  - One CHECK (cue level 2) per idea in the run, ordered by when each idea was first covered (earliest first),
    moved_on ideas last.
  - Scoring, offers (explain spec FR3) and the difficulty controller are as today.
  - A failed recall can splice remediation as today.
- **FR7 Deterministic fallback** (no engine):
  - turns use the bank `reading` / predict prompt for the idea and its source passages, with the question from the
    bank's `check.prompt`;
  - grading uses the bank concept groups, else the node's key terms;
  - readiness is unchanged.
- **FR8 Persistence.** The thread, `learn_ideas` state and sources survive reload and app restart. Reopening a
  session in LEARN restores the chat.

## Non-functional requirements
- **Latency:** source fetching adds ≤ 20 s and overlaps the topic map (~90 s). Per idea, cached passages make
  turns no slower than explain replies (~20–50 s with an AI engine). The deterministic engine answers in < 300 ms.
- **Privacy:** only the topic text and idea titles go to Wikipedia/arXiv. Nothing else leaves the machine through
  this feature. Tests never touch the network (fetchers are monkeypatched).
- **Accessibility:** the chat is `aria-live="polite"`. Enter sends and Shift+Enter adds a newline. Go on / Quiz me
  are buttons with shortcuts (⌘→ / ⌘Q is reserved, so ⌘↵ = Quiz me). It works at phone width.

## Edge cases and failure behaviour
- **All plan ideas have history:** no LEARN, today's flow.
- **The goal itself is the only new idea** (fallback goal node, no map): a one-idea LEARN.
- **The learner leaves mid-chat:** the session stays ACTIVE in LEARN. Reopening restores the thread.
- **A Wikipedia disambiguation or empty result:** skipped. An arXiv offline fallback result is labelled.
- **The engine fails mid-chat:** that turn falls back to deterministic content, labelled (offline explanation).
- **Explain-spec offers** are suppressed during LEARN; the chat is the explanation.

## Acceptance and verification
- **`backend/tests/test_learn_chat.py`** (deterministic engine, scripted LLM, fetchers monkeypatched):
  - a new topic (scripted map) → first step is LEARN with the new ideas in plan order, and no PROBE on new ideas
    (FR1);
  - a mixed plan → probes only over ideas with history;
  - OPEN_REPLY/SKIP behaviour (FR2);
  - a good REPLY lifts p_recall ≥ 0.70 → covered and the next idea; a weak reply (q < 0.45) stays below; 4
    exchanges → moved_on (FR4);
  - QUIZ_ME → ready; submit LEARN → CHECKs earliest-covered first, moved_on last (FR6);
  - chat evidence traces have `max_hint_rung == "R2"` and are absent from `recent_successes` (decisions);
  - sources: numbering stable, notes before Wikipedia before arXiv, unknown `[n]` stripped, `fetch_sources=false`
    → no fetch call, offline → AI-knowledge label (FR5);
  - reload restores the thread and learn state (FR8).
- **`make test` green; `cd frontend && npm run build` exit 0.**
- **Live:** "imitation learning" with claude_cli. The chat cites Wikipedia/arXiv, reaches ready after good replies,
  and recall starts with the first idea. Screenshots go in the scratchpad.

## Decomposition sketch (one worker, sequential; after the explain build)
1. **Explain spec build** (thread table, explainer, side chat). This is the foundation reused here.
2. **`backend/sources.py`** + `session_sources` + prefs flag + tests (network mocked).
3. **LEARN step:**
   - `decide_next` grouping, `/learn` endpoint, `LEARN_TUTOR`, readiness, recall block, deterministic path;
   - tests.
4. **Frontend:** `LearnChat.tsx` (main-card chat sharing the Ask Pólya message list), idea chips, Sources
   disclosure, Start recall.
5. **Finish:** live check, CLAUDE.md section, `make bundle` reinstall, commit + push when you say.

## Risks, assumptions, deferred decisions
- ASSUMED: the 0.70 readiness bar, ≤ 4 exchanges per idea, ≤ 4 idea-level Wikipedia lookups, 20 s fetch budget.
- ASSUMED: "never studied" = no FSRS reviews and no graded answers. Seed ideas that were never answered count as
  new.
- RISK: Wikipedia may miss niche topics. arXiv abstracts are terse, so niche topics lean on notes and AI knowledge
  (labelled).
- RISK: the conversation can feel slow with the CLI engines (20–50 s per turn). The ChatGPT browser engine is
  faster (~21 s).
- DEFERRED: voice replies in the chat; more open sources (nLab, Stanford Encyclopedia); a "teach me again" re-entry
  for ideas with history.
