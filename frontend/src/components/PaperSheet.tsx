/**
 * Paper sheet (docs/specs/paper-reading): what a paper claims, how much of it you understand, its notation, and where
 * to read next — the references it leans on where you struggled, the papers that build on it, and explainers for your
 * gaps. Opened from a paper row on Learn or the "Paper" button in a paper session's strip.
 */
import { useEffect, useRef, useState } from 'react';
import { api, useHarnessStore } from '../store/useHarnessStore';
import type { PaperDetail, PaperRole, PaperSourceOut } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { Details, PrimaryButton, Spinner, useEscape } from './kit';

const ROLE_WORD: Record<PaperRole, string> = {
  prerequisite: 'Background',
  definition: 'Definition',
  assumption: 'Assumption',
  claim: 'Claim',
  main_result: 'Main result',
};

type SourceTab = 'reference' | 'citation' | 'explainer';
const TAB_WORD: Record<SourceTab, string> = { reference: 'Read next', citation: 'Builds on this', explainer: 'Explainers' };
const TAB_EMPTY: Record<SourceTab, string> = {
  reference: 'No references found yet.',
  citation: 'No later papers found (arXiv papers only).',
  explainer: 'Explainers appear for ideas you find hard.',
};

function pct(x: number | null | undefined): string {
  return x === null || x === undefined ? '—' : `${Math.round(x * 100)}%`;
}

function SourceRow({ s, onRead, busy }: { s: PaperSourceOut; onRead: (arxiv: string) => void; busy: boolean }): JSX.Element {
  return (
    <li className="source-row">
      <div className="source-main">
        <a href={s.url} target="_blank" rel="noreferrer" className="source-title">
          {s.title}
        </a>
        <span className="muted small">
          {[s.year, s.is_survey ? 'survey' : null].filter(Boolean).join(' · ')}
        </span>
      </div>
      <p className="source-why small">{s.why}</p>
      {s.contexts.length ? (
        <Details label="Where it is cited">
          {s.contexts.map((c, i) => (
            <blockquote key={i} className="source-ctx small">
              <MathText text={c.sentence} inline />
              {c.section ? <span className="muted"> (§ {c.section})</span> : null}
            </blockquote>
          ))}
        </Details>
      ) : null}
      {s.arxiv_id ? (
        <button className="text-btn small" disabled={busy} onClick={() => onRead(s.arxiv_id)}>
          Read this paper
        </button>
      ) : null}
    </li>
  );
}

export default function PaperSheet({ id, onClose }: { id: string; onClose: () => void }): JSX.Element {
  const detail = useHarnessStore((s) => s.paperDetails[id]) as PaperDetail | undefined;
  const fetchPaper = useHarnessStore((s) => s.fetchPaper);
  const startPaperSession = useHarnessStore((s) => s.startPaperSession);
  const addPaper = useHarnessStore((s) => s.addPaper);
  const sessions = useHarnessStore((s) => s.sessions);
  const loadSession = useHarnessStore((s) => s.loadSession);
  const openModal = useHarnessStore((s) => s.openModal);
  const busy = useHarnessStore((s) => s.busy.create);
  const [tab, setTab] = useState<SourceTab>('reference');
  const [refreshing, setRefreshing] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEscape(onClose, true);
  useEffect(() => {
    void fetchPaper(id);
    panelRef.current?.focus();
  }, [id, fetchPaper]);

  const p = detail;
  const session = p?.session_id ? sessions.find((x) => x.id === p.session_id) : undefined;
  const reading = session?.status === 'ACTIVE';
  const read = (): void => {
    if (!p) return;
    if (reading && session) {
      openModal(null);
      void loadSession(session.id);
    } else void startPaperSession(p.id);
  };
  const refresh = (): void => {
    setRefreshing(true);
    void api
      .refreshPaperSources(id)
      .catch((e: unknown) => useHarnessStore.getState().toast('error', `Update sources: ${e instanceof Error ? e.message : String(e)}`))
      .then(() => fetchPaper(id))
      .finally(() => setRefreshing(false));
  };
  const sources = p?.sources[tab] ?? [];
  const mainIdeas = (p?.ideas ?? []).filter((i) => i.role !== 'prerequisite');
  const background = (p?.ideas ?? []).filter((i) => i.role === 'prerequisite');

  return (
    <div className="sheet-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet paper-sheet" role="dialog" aria-modal="true" aria-labelledby="paper-h" tabIndex={-1} ref={panelRef}>
        <header className="sheet-head">
          <h2 id="paper-h">Paper</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close paper" title="Close (Esc)">
            ×
          </button>
        </header>
        {!p ? (
          <section className="sheet-sec">
            <Spinner label="Loading…" />
          </section>
        ) : (
          <>
            <section className="sheet-sec">
              <h3 className="paper-title">{p.title || 'Untitled paper'}</h3>
              <p className="muted small">
                {[p.authors.slice(0, 4).join(', ') + (p.authors.length > 4 ? ' et al.' : ''), p.year].filter(Boolean).join(' · ')}
              </p>
              <p className="paper-links small">
                {p.links.arxiv ? (
                  <a href={p.links.arxiv} target="_blank" rel="noreferrer">
                    arXiv
                  </a>
                ) : null}
                {p.links.pdf ? (
                  <a href={p.links.pdf} target="_blank" rel="noreferrer">
                    PDF
                  </a>
                ) : null}
                {p.links.code ? (
                  <a href={p.links.code} target="_blank" rel="noreferrer">
                    Code &amp; discussion
                  </a>
                ) : null}
                {p.links.semantic_scholar ? (
                  <a href={p.links.semantic_scholar} target="_blank" rel="noreferrer">
                    Semantic Scholar
                  </a>
                ) : null}
              </p>
              {p.status !== 'MAPPED' ? (
                <p className={`paper-status small${p.status === 'FAILED' ? ' bad' : ''}`}>
                  {p.status === 'FAILED' ? null : <Spinner />}
                  {p.status_detail}
                </p>
              ) : (
                <>
                  <div className="understood" aria-label={`You understand about ${pct(p.understanding)} of this paper`}>
                    <span className="understood-num">{pct(p.understanding)}</span>
                    <span className="muted small">understood, across {p.idea_count} ideas</span>
                    <span className="meter" aria-hidden="true">
                      <span style={{ width: `${Math.round((p.understanding ?? 0) * 100)}%` }} />
                    </span>
                  </div>
                  <div className="row">
                    <PrimaryButton onClick={read} busy={busy} busyLabel="Opening…">
                      {reading ? 'Continue reading' : session ? 'Read it again' : 'Start reading'}
                    </PrimaryButton>
                  </div>
                  {p.partial_map ? (
                    <p className="muted small">This map only has the paper&rsquo;s own theorem blocks. Connect an AI engine in Settings for a full map.</p>
                  ) : null}
                </>
              )}
            </section>

            {p.map.summary || p.map.contributions.length ? (
              <section className="sheet-sec" aria-labelledby="paper-claims">
                <h3 id="paper-claims">What it shows</h3>
                {p.map.summary ? <MathText text={p.map.summary} /> : null}
                {p.map.contributions.length ? (
                  <ul className="paper-list">
                    {p.map.contributions.map((c, i) => (
                      <li key={i}>
                        <MathText text={c} inline />
                      </li>
                    ))}
                  </ul>
                ) : null}
                {p.first_guess ? (
                  <>
                    <p className="field-label">Your first guess</p>
                    <blockquote className="source-ctx">{p.first_guess}</blockquote>
                  </>
                ) : null}
              </section>
            ) : null}

            {mainIdeas.length ? (
              <section className="sheet-sec" aria-labelledby="paper-ideas">
                <h3 id="paper-ideas">Its ideas</h3>
                <ul className="idea-list">
                  {mainIdeas.map((i) => (
                    <li key={i.node_id}>
                      <span className="idea-role">{ROLE_WORD[i.role]}</span>
                      <span className="idea-title">
                        <MathText text={i.title} inline />
                      </span>
                      <span className="muted small">{i.answered ? pct(i.mastery) : 'not yet'}</span>
                    </li>
                  ))}
                </ul>
                {background.length ? (
                  <p className="muted small">
                    Background it assumes: {background.map((b) => `${b.title} (${pct(b.mastery)})`).join(' · ')}
                  </p>
                ) : null}
              </section>
            ) : null}

            {p.map.notation.length ? (
              <section className="sheet-sec" aria-labelledby="paper-notation">
                <h3 id="paper-notation">Notation</h3>
                <dl className="notation">
                  {p.map.notation.map((n, i) => (
                    <div key={i}>
                      <dt>
                        <MathText text={n.symbol_latex} inline latexField />
                      </dt>
                      <dd>
                        <MathText text={n.meaning} inline />
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}

            {p.status === 'MAPPED' ? (
              <section className="sheet-sec" aria-labelledby="paper-sources">
                <h3 id="paper-sources">Sources</h3>
                <div className="seg" role="tablist" aria-labelledby="paper-sources">
                  {(Object.keys(TAB_WORD) as SourceTab[]).map((t) => (
                    <button key={t} role="tab" aria-selected={tab === t} className={`seg-opt${tab === t ? ' on' : ''}`} onClick={() => setTab(t)}>
                      {TAB_WORD[t]}
                      <span className="muted"> {p.sources[t].length || ''}</span>
                    </button>
                  ))}
                </div>
                {sources.length ? (
                  <ol className="sources">
                    {sources.slice(0, 12).map((s) => (
                      <SourceRow key={s.id} s={s} busy={Boolean(busy)} onRead={(ax) => void addPaper({ arxiv: ax })} />
                    ))}
                  </ol>
                ) : (
                  <p className="muted small">{TAB_EMPTY[tab]}</p>
                )}
                <button className="btn-secondary" onClick={refresh} disabled={refreshing}>
                  {refreshing ? <Spinner /> : null}Update sources
                </button>
                <p className="muted small">Ranked by where the paper cites them and by the ideas you missed. Updates after each reading session.</p>
              </section>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
