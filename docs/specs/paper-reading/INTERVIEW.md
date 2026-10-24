---
slug: paper-reading
status: approved
bead: none (learn-harness is not a gc rig)
started: 2026-10-24
---
# Objective (user's words, verbatim)
"another important thing that I want to do is understanding research papers. As I get into more research-grade
material, this will be important; how can I optimize this part of my learning loop? Definitely using the core paper
itself as a source is very important, maybe finding more sosurces for me and tracking down the citations? Think about
even more."

# Recon
- PDF: backend/tools.py:199 read_pdf_file (pypdf, plain text, math is lost; first 30 pages). .tex parser
  (theorem/definition/problem envs) in tools.py read_tex_or_md; subagents.py import_tex_blocks turns a .tex file into
  nodes + DEDUCTION edges (deterministic, section-level, crude).
- arXiv: tools.search_arxiv + subagents.py:514 literature() = keyword search only; no fetch of a paper, no citations.
- corpus_rag (subagents.py:482) = term-overlap over .tex/.md blocks; PDFs not searched; results never reach lesson
  prompts (orchestrator._llm_step:173) — same gap as topic-map D3.
- New goals = one node, no decomposition (topic-map spec, open). A paper map is the topic map with the paper as the
  grounding source → topic-map is a prerequisite of this work.
- Offline engine cannot explain an arbitrary paper; this feature needs an AI engine (claude CLI / key / Codex).
- External sources (to verify in build): arXiv e-print LaTeX source (arxiv.org/e-print/<id>), Semantic Scholar Graph
  API (references, citations, citation contexts + intents, "influential"; no key at low rate), OpenAlex (free),
  OpenReview API (public reviews for ICLR/NeurIPS-style venues), Papers with Code (implementations).

# Idea catalogue (proposed to Nathan 2026-10-24)
1 Ingest: arXiv id/URL → LaTeX source (exact math, theorem envs); PDF fallback; page/section anchors for every quote.
2 Paper map: contributions, definitions, assumptions, theorems/claims, key equations, experiments → nodes + edges
  tagged with the paper; gap analysis against your mastery → teach missing prerequisites first.
3 Guided passes (Keshav three-pass): skim → predict the contribution from the abstract; main argument → predict the
  next proof step / which assumption a step uses; deep → re-derive a key equation or reproduce a small figure.
4 Grounded answers: every explanation quotes the paper with a page/section anchor; "where does it say that?".
5 Citation tracking: references ranked by where they are cited (method/proof sections, "we use the lemma of [12]")
  and whether they cover a gap of yours; forward citations (follow-ups, critiques, replications, surveys).
6 More sources per gap: survey/textbook/lecture-note explainers; Papers with Code implementations.
7 Critical reading: assumption hunt, Proof-Referee on the paper's own proofs, counterexample when an assumption is
  dropped, "write a 5-line review" then compare with real OpenReview reviews.
8 Notation crosswalk: paper symbols ↔ your existing nodes (reuses NOTATION_OBSTRUCTION miss class).
9 Retention: the paper's key claims enter spaced review; per-paper "understanding" = mastery over its claim nodes.
10 Across papers: shared nodes, conflicting claims, ISOMORPHISM edges; a reading list ordered by prerequisites.

# Decision tree
- D1 [CP] v1 scope — ACCEPTED
- D2 [CP] Paper text source: arXiv LaTeX first, PDF fallback — DELEGATED
- D3 [CP] Citation/source services (Semantic Scholar + OpenAlex + arXiv; OpenReview) — DELEGATED
- D4 Where it lives in the UI (Learn box accepts an arXiv link / PDF vs a new "Papers" tab) — DELEGATED
- D5 Data model: papers side table + node↔paper links (keep original DDL) — DELEGATED
- D6 Sequencing vs topic-map (paper map reuses the goal decomposer) — DELEGATED

# Ledger
- D1 ACCEPTED: "one paper, deeply" (ideas 1–5, 8, 9; plus the cheap critical-reading steps of idea 7 that reuse the
  referee/Feynman duels). Rejected: citation explorer first; everything at once. Nathan: "yes this look sright" 2026-10-24
- D2–D6 DELEGATED: Nathan said "build out the full research loop" without addressing them → my recommendations:
  D2 arXiv LaTeX source first, arXiv PDF / uploaded PDF fallback (pypdf). D3 Semantic Scholar (metadata, intents,
  influential; retried, optional) + OpenAlex (forward citations sorted by citations, explainers) + arXiv API; citation
  contexts come from the LaTeX itself; OpenReview deferred to v2. D4 no new tab: the Learn box accepts an arXiv link,
  "Read a paper…" adds PDF upload; papers list on Learn; a Paper sheet in the session strip. D5 side tables papers /
  paper_nodes / paper_refs, original DDL untouched, paper text on disk under ~/Polya/workspace/papers/<id>/.
  D6 the paper mapper is independent of goal matching; topic-map stays open and can reuse the mapper later. 2026-10-24

# Assumptions
- Needs an AI engine; offline shows structure only (sections, theorem list, references) with a clear message.
- Paper metadata/titles are sent to public scholarly APIs; paper contents are sent only to the chosen AI engine.

# Constraints / Non-goals
- No scraping of paywalled publishers; open-access sources only.

# Reuse
- tools.read_pdf_file / read_tex_or_md, subagents.import_tex_blocks, literature(), corpus_rag, Proof-Referee and
  Feynman duel, model_predictions / controller, topic-map decomposer (once built).

# Open questions

# Pending question: none — APPROVED (fast-track) by Nathan ("build out the full research loop") 2026-10-24

# Build notes (2026-10-24)
- Live: 1706.03762 → LaTeX source, 23 sections, 40 refs, cite contexts; claude_cli map in 177 s (12 ideas, all quotes
  verified, 2 prerequisites + 1 claim reused existing nodes); top references Gehring/GNMT/Bahdanau (method sections +
  S2 influential). OpenAlex citing list has data noise (one mis-merged record). Explainer search needs short concepts →
  mapper now returns `concept`; exact-phrase OpenAlex title search.
- Spec drift: paper files are NOT added to notes RAG (would flood the notes picker with .sty/.tex); grounding comes from
  `orchestrator.paper_context` instead. Mapper timeout 300 s (`llm.complete_json(timeout=)`).
- Deterministic sessions skip the referee/Feynman finale (they need the AI map's key_argument/assumptions).
