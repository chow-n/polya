---
slug: paper-reading
status: approved-fasttrack
bead: none
approved_by: Nathan ("yes this look sright … build out the full research loop"; D2–D6 delegated)
approved_at: 2026-10-24
---
# Read a research paper, deeply (v1 of the research loop)

## Goals
- G1 Turn one paper (arXiv link or PDF) into a map of what it claims, what it assumes and what you need to know
  first, checked against what you already know.
- G2 Teach the missing background first, then take you through the paper in guess-first passes, with every
  explanation quoting the paper and saying where.
- G3 Track down the sources that matter: the references the paper leans on where you struggled, the papers that
  build on it, and explainers for your gaps.
- G4 Keep the paper: its key claims enter spaced review; each paper shows how much of it you understand.

## Non-goals (v1)
- OpenReview comparison, citation exploration more than one hop, cross-paper maps and conflict detection (v2).
- Paywalled publishers, figure/table OCR, equation extraction from PDFs beyond pypdf text.
- Fixing general goal matching (docs/specs/topic-map, still open).

## User-facing behaviour
- **Start:** paste an arXiv link or id (`2401.01234`, `arxiv.org/abs/…`, `…/pdf/…v2`) into Learn and the button reads
  **Read paper**. **Read a paper…** under the field also accepts a PDF (upload) or a PDF already in your notes.
- While it prepares (about 30–90 s with an AI engine), the card says what it is doing: fetching, reading, mapping.
- **The session:**
  1. *Skim (pass 1):* the abstract and section list, then "What do you think the main result is, and what must be
     true for it to hold?" — your guess is kept and shown again at the end.
  2. *Background:* quick probes on the prerequisites the paper assumes; ones you know are skipped, gaps are taught
     (the normal Pólya predict → read → check loop).
  3. *The paper (pass 2):* its definitions, assumptions and claims in order, each card grounded in a quoted passage
     with its section ("§3.2 Method"). Checks include "which assumption does this step need?".
  4. *Critical reading (pass 3):* find the flaw in a corrupted version of the paper's own key argument, then explain
     the main result to a sceptical student until you have stated every assumption it needs.
  5. *Done:* your first guess next to the actual contribution, how much of the paper you now understand, and what to
     read next.
- **Paper sheet** (the "Paper" button in the session strip, or a paper row on Learn): summary, contributions,
  notation table (paper symbol → meaning → the idea you already know), understanding %, and **Sources**:
  - *Read next* — references ranked by where the paper cites them (method/proof sections over related work), whether
    Semantic Scholar marks them influential, and whether they cover an idea you missed; each says why
    ("cited 3× in §3 Method, where you missed ‘importance weighting’").
  - *Builds on this* — the most-cited later papers (surveys flagged).
  - *Explainers for your gaps* — highly cited surveys/tutorials on each idea you missed.
  - Each source links out (arXiv / DOI / Semantic Scholar / Hugging Face papers page for code) and arXiv ones have
    **Read this paper**.
- **Learn home** lists your papers ("Attention Is All You Need — 60% understood") under the continue rows.
- Without an AI engine: the paper is still fetched and parsed; the map holds its theorem/definition blocks and its
  references, with a clear note that a full map needs an AI engine.

## Architecture and integration decisions
- D1 One paper, deeply (above). Rejected: citation explorer first; everything at once.
- D2 Text: arXiv LaTeX source (`arxiv.org/e-print/<id>`) first — exact math, theorem environments, `\cite` contexts,
  `.bbl`/`.bib`; else the arXiv PDF or an uploaded PDF via pypdf, with page anchors. Rejected: PDF only (math lost).
- D3 Services: arXiv API (metadata), Semantic Scholar Graph API (ids, intents, `isInfluential`; optional, retried,
  never required), OpenAlex (forward citations sorted by `cited_by_count`, explainer search). Citation *contexts*
  come from the LaTeX itself, so ranking works when Semantic Scholar rate-limits. OpenReview → v2.
- D4 No new destination: Learn accepts papers; a Paper sheet; papers listed on Learn.
- D5 Side tables `papers`, `paper_nodes`, `paper_refs` (original DDL untouched); paper files on disk under
  `~/Polya/workspace/papers/<paper_id>/` (source, `paper.json`, PDF).
- D6 The paper mapper is its own module; topic-map can reuse it later.
- Session: `mode = PROBE`, `sub_mode = PAPER`, paper id in the controller state; existing step kinds are reused
  (PREDICT, PROBE, READING, CHECK, REFEREE, FEYNMAN) — no new step kinds, so the existing cards render everything.

## Existing components to reuse
- `backend/tools.py`: `read_pdf_file`, `_safe_path`, `search_arxiv`; `backend/agents/subagents.py`: `run_agent`,
  `guess_domain`, `_slug`, `_latex_text`, `literature`.
- `backend/agents/orchestrator.py`: `decide_next`, `step_probe/predict/reading/check/referee/feynman`, `_llm_step`,
  `build_plan`-style plan items, `submit` (all grading, BKT/FSRS, predictions, controller unchanged).
- `backend/llm.complete_json`, `db.upsert_node/insert_edge/recompute_depths`, `hub.broadcast`.
- Frontend: `LearnHome`, `SessionFocus` strip, `kit.tsx` (Sheet/Details/PrimaryButton), `useHarnessStore`.

## Interfaces and data contracts
- Tables:
  - `papers(id, source, arxiv_id, doi, s2_id, openalex_id, title, authors_json, year, abstract, text_kind, status,
    status_detail, map_json, first_guess, created_at, updated_at)`; `status ∈ {FETCHING, PARSED, MAPPED, FAILED}`.
  - `paper_nodes(paper_id, node_id, role, anchor, quote, ord)`; `role ∈ {prerequisite, definition, assumption, claim,
    main_result}`.
  - `paper_refs(id, paper_id, direction, ref_key, title, authors, year, arxiv_id, doi, s2_id, url, contexts_json,
    sections_json, influential, intents_json, cited_by_count, score, why)`; `direction ∈ {reference, citation, explainer}`.
- `backend/papers/latex.py` (pure): `parse_source(dir) -> PaperDoc` — main-file detection, `\input` inlining,
  comment stripping, zero-argument macro expansion, sections, abstract, theorem-like environments (incl.
  `\newtheorem` aliases), labelled equations, `\cite*` contexts (sentence + section), bibliography from `.bbl`/`.bib`.
- `backend/papers/fetch.py`: `parse_arxiv_ref(text) -> id|None`, `fetch_arxiv(id, dest)`, safe tar/gzip extraction
  (text files only, size caps, no paths outside `dest`).
- `backend/papers/scholar.py`: `s2_paper`, `s2_references`, `openalex_work`, `openalex_citing`, `openalex_explainers`
  — each returns `[]`/`None` on any network error.
- `backend/papers/mapper.py`: `LLMPaperMap {summary, contributions[], ideas[{key,title,node_type,role,statement_latex,
  intuition_summary,anchor,quote,existing_node_id?}], edges[{premises[],conclusion,reasoning}], notation[{symbol_latex,
  meaning,existing_node_id?}], key_argument{claim, steps[]}, assumptions_for_main[{label,keywords[]}]}`; quotes are
  verified against the paper text (whitespace/LaTeX-normalised); unverifiable quotes are dropped and counted.
- `backend/papers/service.py`: `ingest(ref|upload) -> paper`, `build_map(paper)`, `rank_refs(paper)`,
  `understanding(paper)`, `start_session(paper)`.
- REST: `POST /api/papers {arxiv?: str, workspace_path?: str}`; `POST /api/papers/upload` (multipart PDF);
  `GET /api/papers`; `GET /api/papers/{id}`; `POST /api/papers/{id}/sources/refresh`; `POST /api/papers/{id}/session`.
  WS: `paper_progress {paper_id, status, detail}`.

## Functional requirements
- FR1 arXiv references in any common form resolve to an id; unknown input → 422 with a plain message.
- FR2 Fetch prefers LaTeX source; falls back to PDF; PDF-only uploads are supported. Extraction is size-capped
  (50 MB archive, 5 MB per text file) and refuses absolute paths, `..`, links and devices.
- FR3 Parsing yields sections, abstract, theorem-like blocks, citation contexts with sections, and bibliography entries
  with titles; a PDF yields pages, the abstract heuristic and a reference list.
- FR4 Mapping (AI engine) yields 4–12 ideas, at least one main_result, edges, notation; prerequisites reuse existing
  node ids where the engine names a real one; every created node is a normal node (enters review) linked in
  `paper_nodes`. Without an engine: theorem/definition blocks become ideas; the paper status says the map is partial.
- FR5 Paper session plan = prerequisite gaps (probed by EIG first) then paper ideas in dependency order, then the key
  argument referee step and the assumptions Feynman step; skim PREDICT first. Card prompts for paper ideas include the
  anchored passage; reading cards show the quote with its section.
- FR6 Reference ranking: score = Σ contexts × section weight (method/theory/proof 3, results/experiments 2,
  intro/background 1, related work 0.5) + 2·influential + 3·(cited in a section anchoring an idea you missed or have
  P(L) < 0.5); each gets a one-line `why`. Forward citations: top 8 by `cited_by_count`; explainers: up to 2 per gap.
- FR7 Understanding % = mean P(L) over the paper's non-prerequisite ideas, shown on Learn and in the sheet.
- FR8 "Read this paper" on an arXiv source ingests it and starts its session.

## Non-functional requirements
- Network calls: 10 s timeouts, one retry with backoff on 429, polite `User-Agent` with a contact-free project
  string; Semantic Scholar at most 1 request/second. The test suite makes no network calls (fixtures).
- Paper text sent to the AI engine is capped (~24k characters, abstract + intro + method sections + theorem blocks).
- Ingest runs in the background; the UI shows progress over WS and never blocks other screens.

## Edge cases and failure behaviour
- arXiv withdrawn / no source / unparsable → PDF route; both fail → status FAILED with the reason, nothing created.
- Map JSON invalid → one retry, then the deterministic partial map.
- Ingesting the same arXiv id twice → the existing paper is returned (and its session resumed if active).
- A quote the engine invents → dropped; the card shows the passage text instead.
- Huge papers (>200 pages) → first 60 pages for PDFs; LaTeX trimmed per the cap above.

## Acceptance and verification
- Unit: arXiv ref parsing; LaTeX parsing on a fixture source tree (sections, theorems with `\newtheorem` alias, cite
  contexts, `.bbl` titles, `\input`); safe extraction rejects `../` and links; quote verification; reference ranking;
  deterministic partial map; understanding %.
- API (deterministic engine, fixtures, no network): ingest from a fixture source → MAPPED/partial; session runs skim →
  probe/teach → referee → Feynman → COMPLETE; nodes linked; `/api/papers/{id}` shape.
- Live (network + claude CLI): ingest 1706.03762, map built, a session started, Sources lists ranked references with
  reasons and citing papers. WebKit light/dark screenshots of the Learn papers list, the session strip and the sheet.
- `make test`, `npm run build`, `make bundle` pass.

## Decomposition sketch
1. `papers/fetch.py` + `papers/latex.py` + fixtures + tests (pure, no DB).
2. Tables + `papers/scholar.py` + `papers/mapper.py` + `service.ingest/build_map/rank_refs` + REST + WS (+ tests).
3. Paper session in the orchestrator (plan, grounding, critical steps, completion summary) + tests.
4. Frontend: Learn input detection + "Read a paper…" + papers list + Paper sheet + strip button.
5. Docs (README, API.md, CLAUDE.md), live check, bundle, v0.5.0.
Built after the chatgpt-engine slices, one worker, in order.

## Risks, assumptions, deferred decisions
- Mapping quality depends on the engine; the deterministic map is honest but thin.
- Semantic Scholar's shared pool rate-limits (seen 2026-10-24); it is enrichment only.
- ASSUMED: paper ideas use the existing domain clusters via `guess_domain`; papers/<id> files count as notes for RAG.
- Deferred to v2: OpenReview review comparison, "write a 5-line review", multi-hop citation graph, cross-paper maps,
  reading lists ordered by prerequisites, reproducing a figure in the sandbox.
