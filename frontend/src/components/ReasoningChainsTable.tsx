/**
 * View 4 — Reasoning Chains & Vault (ARCHITECTURE_SPEC §6.1 tab 4, §1).
 *  - filterable hyperedge browser (type / domain / text / mastery) and proposition table
 *  - 5D cue-breadth matrix (nodes × Symbolic/Disguised/Geometric/Computational/Adversarial)
 *  - Bjork Batch launcher (interleaved queue + desirable-difficulty window) and `harness-cli due`-style due list
 *  - .tex notes manager over workspace/notes + workspace/problems (parsed theorem/definition/problem blocks)
 *  - full sub-agent artifact vault
 */
import { Fragment, useEffect, useMemo, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import { ALL_AGENTS, CUE_DIMENSIONS, type AgentName, type EdgeType, type NodeType } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { AGENT_META } from './SidebarSubagentDock';
import { Bar, C, CUE_LABELS, NODE_TYPE_GLYPH, Spinner, domainColor, dueRelative, fmtDateTime, fx, masteryColor, timeAgo, withAlpha } from './ui';

type Sub = 'chains' | 'props' | 'cues' | 'bjork' | 'notes' | 'artifacts';
const SUBS: { id: Sub; label: string }[] = [
  { id: 'chains', label: 'Hyperedge chains' },
  { id: 'props', label: 'Propositions' },
  { id: 'cues', label: '5D Cue-Breadth Matrix' },
  { id: 'bjork', label: 'Bjork Batch & Due' },
  { id: 'notes', label: '.tex Notes' },
  { id: 'artifacts', label: 'Artifact Vault' },
];
const EDGE_TYPES: EdgeType[] = ['DEDUCTION', 'CONTRASTIVE', 'ISOMORPHISM', 'CUE_TRIGGER'];
const EDGE_SYM: Record<EdgeType, string> = { DEDUCTION: '⟹', CONTRASTIVE: '⊥', ISOMORPHISM: '≅', CUE_TRIGGER: '⇝' };

export default function ReasoningChainsTable(): JSX.Element {
  const [sub, setSub] = useState<Sub>('chains');
  return (
    <div className="vault">
      <div className="vault-tabs" role="tablist">
        {SUBS.map((s) => (
          <button key={s.id} role="tab" aria-selected={sub === s.id} className={`vault-tab${sub === s.id ? ' on' : ''}`} onClick={() => setSub(s.id)}>
            {s.label}
          </button>
        ))}
      </div>
      <div className="vault-body">
        {sub === 'chains' ? <ChainsPanel /> : null}
        {sub === 'props' ? <PropsPanel /> : null}
        {sub === 'cues' ? <CueMatrix /> : null}
        {sub === 'bjork' ? <BjorkPanel /> : null}
        {sub === 'notes' ? <NotesPanel /> : null}
        {sub === 'artifacts' ? <ArtifactVault /> : null}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ hyperedges
function ChainsPanel(): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const selectEdge = useHarnessStore((s) => s.selectEdge);
  const setTab = useHarnessStore((s) => s.setTab);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const createSession = useHarnessStore((s) => s.createSession);
  const [types, setTypes] = useState<Set<EdgeType>>(new Set(EDGE_TYPES));
  const [domain, setDomain] = useState('');
  const [q, setQ] = useState('');
  const [minMastery, setMinMastery] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sort, setSort] = useState<'type' | 'mastery' | 'created'>('type');

  const byId = useMemo(() => new Map((graph?.nodes ?? []).map((n) => [n.id, n])), [graph]);
  const domains = useMemo(() => [...new Set((graph?.nodes ?? []).map((n) => n.domain_cluster))].sort(), [graph]);
  const rows = useMemo(() => {
    const ql = q.trim().toLowerCase();
    const out = (graph?.hyperedges ?? []).filter((e) => {
      if (!types.has(e.edge_type)) return false;
      if (e.edge_mastery < minMastery) return false;
      const ids = [...e.premise_node_ids, e.conclusion_node_id];
      if (domain && !ids.some((id) => byId.get(id)?.domain_cluster === domain)) return false;
      if (ql) {
        const hay = [e.reasoning_chain_latex, e.discriminating_condition_latex, ...ids.map((id) => byId.get(id)?.title ?? id)].join(' ').toLowerCase();
        if (!hay.includes(ql)) return false;
      }
      return true;
    });
    out.sort((a, b) =>
      sort === 'mastery'
        ? a.edge_mastery - b.edge_mastery
        : sort === 'created'
          ? b.created_at.localeCompare(a.created_at)
          : a.edge_type.localeCompare(b.edge_type) || (byId.get(a.conclusion_node_id)?.logical_depth ?? 0) - (byId.get(b.conclusion_node_id)?.logical_depth ?? 0),
    );
    return out;
  }, [graph, types, domain, q, minMastery, sort, byId]);

  const title = (id: string): string => byId.get(id)?.title ?? id;

  return (
    <div className="panel-fill">
      <div className="filters">
        {EDGE_TYPES.map((t) => (
          <label key={t} className={`filter-chip e-${t.toLowerCase()}${types.has(t) ? ' on' : ''}`}>
            <input
              type="checkbox"
              checked={types.has(t)}
              onChange={(e) =>
                setTypes((s) => {
                  const n = new Set(s);
                  if (e.target.checked) n.add(t);
                  else n.delete(t);
                  return n;
                })
              }
            />
            {EDGE_SYM[t]} {t}
          </label>
        ))}
        <select value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">all domains</option>
          {domains.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <input className="filter-q" placeholder="search premises, conclusions, derivations…" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="small dim range-filter">
          edge mastery ≥ <span className="mono">{minMastery.toFixed(2)}</span>
          <input type="range" min={0} max={1} step={0.05} value={minMastery} onChange={(e) => setMinMastery(Number(e.target.value))} />
        </label>
        <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
          <option value="type">sort: type · depth</option>
          <option value="mastery">sort: weakest first</option>
          <option value="created">sort: newest</option>
        </select>
        <span className="mono dim small">
          {rows.length}/{graph?.hyperedges.length ?? 0}
        </span>
      </div>
      <div className="table-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 120 }}>type</th>
              <th>premises</th>
              <th style={{ width: 28 }} />
              <th>conclusion</th>
              <th style={{ width: 130 }}>edge mastery</th>
              <th style={{ width: 90 }}>created</th>
              <th style={{ width: 150 }} />
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <Fragment key={e.id}>
                <tr className={`clickable${expanded === e.id ? ' expanded' : ''}`} onClick={() => setExpanded(expanded === e.id ? null : e.id)}>
                  <td>
                    <span className={`edge-tag mono e-${e.edge_type.toLowerCase()}`}>{e.edge_type}</span>
                  </td>
                  <td>
                    {e.premise_node_ids.map((p, i) => (
                      <span key={p}>
                        {i > 0 ? <span className="dim"> ∧ </span> : null}
                        <span className="dot-inline" style={{ background: domainColor(byId.get(p)?.domain_cluster ?? '', byId.get(p)?.node_type) }} />
                        {title(p)}
                      </span>
                    ))}
                  </td>
                  <td className="mono" style={{ textAlign: 'center' }}>
                    {EDGE_SYM[e.edge_type]}
                  </td>
                  <td>
                    <span className="dot-inline" style={{ background: domainColor(byId.get(e.conclusion_node_id)?.domain_cluster ?? '', byId.get(e.conclusion_node_id)?.node_type) }} />
                    {title(e.conclusion_node_id)}
                  </td>
                  <td>
                    <span className="mono">{fx(e.edge_mastery)}</span> <Bar value={e.edge_mastery} />
                  </td>
                  <td className="mono dim small">{timeAgo(e.created_at)}</td>
                  <td onClick={(ev) => ev.stopPropagation()}>
                    <button
                      className="btn tiny ghost"
                      onClick={() => {
                        selectEdge(e.id);
                        setTab(2);
                      }}
                    >
                      graph ▸
                    </button>
                    <button
                      className="btn tiny"
                      onClick={() =>
                        void createSession({
                          mode: 'PRACTICE',
                          target_goal: `Practice the link into ${title(e.conclusion_node_id)}`,
                          target_node_id: e.conclusion_node_id,
                          contrastive_pair: e.edge_type === 'CONTRASTIVE',
                          cue_level: e.edge_type === 'CONTRASTIVE' ? 3 : 2,
                        })
                      }
                    >
                      practice
                    </button>
                  </td>
                </tr>
                {expanded === e.id ? (
                  <tr className="expansion">
                    <td colSpan={7}>
                      <div className="expansion-grid">
                        <div>
                          <div className="insp-label">{e.edge_type === 'CONTRASTIVE' ? 'Boundary discriminator' : 'Reasoning chain'}</div>
                          <MathText text={e.reasoning_chain_latex} latexField />
                        </div>
                        {e.discriminating_condition_latex ? (
                          <div>
                            <div className="insp-label">Discriminating condition</div>
                            <MathText text={e.discriminating_condition_latex} latexField />
                          </div>
                        ) : null}
                        <div className="chips-wrap">
                          {[...e.premise_node_ids, e.conclusion_node_id].map((id) => (
                            <button key={id} className="chip" onClick={() => focus(id)}>
                              ◎ {title(id)}
                            </button>
                          ))}
                          <span className="mono dim small">
                            {e.id} · {fmtDateTime(e.created_at)}
                          </span>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? <div className="dim pad">No hyperedges match the filters.</div> : null}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ propositions
const NODE_TYPES: NodeType[] = ['AXIOM', 'PROPOSITION', 'MOVE', 'COUNTEREXAMPLE', 'INTUITION', 'BUGGY_RULE'];

function PropsPanel(): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const [type, setType] = useState<NodeType | ''>('');
  const [domain, setDomain] = useState('');
  const [q, setQ] = useState('');
  const [sort, setSort] = useState<'depth' | 'mastery' | 'retrievability' | 'due'>('depth');
  const domains = useMemo(() => [...new Set((graph?.nodes ?? []).map((n) => n.domain_cluster))].sort(), [graph]);
  const rows = useMemo(() => {
    const ql = q.trim().toLowerCase();
    const out = (graph?.nodes ?? []).filter(
      (n) =>
        (!type || n.node_type === type) &&
        (!domain || n.domain_cluster === domain) &&
        (!ql || `${n.title} ${n.statement_latex} ${n.intuition_summary}`.toLowerCase().includes(ql)),
    );
    out.sort((a, b) =>
      sort === 'mastery'
        ? a.bkt_p_mastery - b.bkt_p_mastery
        : sort === 'retrievability'
          ? a.retrievability - b.retrievability
          : sort === 'due'
            ? a.days_until_due - b.days_until_due
            : a.logical_depth - b.logical_depth || a.title.localeCompare(b.title),
    );
    return out;
  }, [graph, type, domain, q, sort]);

  return (
    <div className="panel-fill">
      <div className="filters">
        <select value={type} onChange={(e) => setType(e.target.value as NodeType | '')}>
          <option value="">all node types</option>
          {NODE_TYPES.map((t) => (
            <option key={t} value={t}>
              {NODE_TYPE_GLYPH[t]} {t}
            </option>
          ))}
        </select>
        <select value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">all domains</option>
          {domains.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <input className="filter-q" placeholder="search statements…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
          <option value="depth">sort: logical depth</option>
          <option value="mastery">sort: lowest P(L)</option>
          <option value="retrievability">sort: lowest R(t)</option>
          <option value="due">sort: due soonest</option>
        </select>
        <span className="mono dim small">{rows.length} nodes</span>
      </div>
      <div className="table-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>node</th>
              <th>type</th>
              <th className="num">depth</th>
              <th style={{ width: 130 }}>P(L)</th>
              <th className="num">R(t)</th>
              <th className="num">S (d)</th>
              <th className="num">D</th>
              <th>next due</th>
              <th className="num">cue c̄</th>
              <th>flags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((n) => (
              <tr key={n.id} className="clickable" onClick={() => focus(n.id)}>
                <td>
                  <span className="dot-inline" style={{ background: domainColor(n.domain_cluster, n.node_type) }} />
                  {n.title}
                </td>
                <td className="mono small">
                  {NODE_TYPE_GLYPH[n.node_type]} {n.node_type}
                </td>
                <td className="num mono">{n.logical_depth}</td>
                <td>
                  <span className="mono" style={{ color: masteryColor(n.bkt_p_mastery) }}>
                    {fx(n.bkt_p_mastery)}
                  </span>{' '}
                  <Bar value={n.bkt_p_mastery} />
                </td>
                <td className="num mono" style={{ color: n.in_bjork_window ? C.cyan : n.retrievability < 0.7 ? C.rose : undefined }}>
                  {fx(n.retrievability, 3)}
                </td>
                <td className="num mono">{fx(n.fsrs_stability)}</td>
                <td className="num mono">{fx(n.fsrs_difficulty, 1)}</td>
                <td className="mono small" style={{ color: n.days_until_due <= 0 ? C.rose : undefined }}>
                  {dueRelative(n.days_until_due)}
                </td>
                <td className="num mono">{fx(n.cue_mean)}</td>
                <td className="mono small">
                  {n.hypercorrection_flag ? <span style={{ color: C.rose }}>⚑ </span> : null}
                  {n.last_miss_class !== 'NONE' ? <span className="dim">{n.last_miss_class}</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ cue matrix
function CueMatrix(): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const createSession = useHarnessStore((s) => s.createSession);
  const [sortDim, setSortDim] = useState<(typeof CUE_DIMENSIONS)[number] | 'cue_mean'>('cue_mean');
  const rows = useMemo(
    () =>
      [...(graph?.nodes ?? [])]
        .filter((n) => n.node_type !== 'BUGGY_RULE')
        .sort((a, b) => (sortDim === 'cue_mean' ? a.cue_mean - b.cue_mean : a.cues[sortDim] - b.cues[sortDim])),
    [graph, sortDim],
  );
  const colMeans = CUE_DIMENSIONS.map((d) => (rows.length ? rows.reduce((a, n) => a + n.cues[d], 0) / rows.length : 0));
  const LEVEL: Record<string, number> = { cue_symbolic: 1, cue_disguised_notation: 2, cue_geometric: 3, cue_computational: 3, cue_adversarial: 4 };

  return (
    <div className="panel-fill">
      <div className="filters">
        <span className="dim small">
          Transfer-appropriate processing: a node is only robust once it is retrievable from every cue type. Click a cell to practice that
          dimension (cue level mapped L1 symbolic → L2 disguised → L3 geometric/computational → L4 adversarial).
        </span>
      </div>
      <div className="table-scroll">
        <table className="tbl cue-matrix">
          <thead>
            <tr>
              <th>node</th>
              {CUE_DIMENSIONS.map((d) => (
                <th key={d} className={`num clickable${sortDim === d ? ' sorted' : ''}`} onClick={() => setSortDim(d)}>
                  {CUE_LABELS[d]}
                </th>
              ))}
              <th className={`num clickable${sortDim === 'cue_mean' ? ' sorted' : ''}`} onClick={() => setSortDim('cue_mean')}>
                mean
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((n) => (
              <tr key={n.id}>
                <td className="clickable" onClick={() => focus(n.id)}>
                  <span className="dot-inline" style={{ background: domainColor(n.domain_cluster, n.node_type) }} />
                  {n.title}
                </td>
                {CUE_DIMENSIONS.map((d) => (
                  <td
                    key={d}
                    className="heat clickable"
                    style={{ background: withAlpha(C.cyan, 0.06 + 0.7 * n.cues[d]) }}
                    title={`Practice ${n.title} at cue level ${LEVEL[d]} (${CUE_LABELS[d]})`}
                    onClick={() =>
                      void createSession({
                        mode: d === 'cue_adversarial' ? 'REFEREE_DUEL' : 'PRACTICE',
                        sub_mode: d === 'cue_adversarial' ? 'PROOF_REFEREE' : 'STANDARD',
                        target_goal: `${CUE_LABELS[d]} cue practice: ${n.title}`,
                        target_node_id: n.id,
                        cue_level: LEVEL[d],
                      })
                    }
                  >
                    <span className="mono">{fx(n.cues[d])}</span>
                  </td>
                ))}
                <td className="num mono">{fx(n.cue_mean)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="dim">column mean</td>
              {colMeans.map((m, i) => (
                <td key={i} className="num mono">
                  {fx(m)}
                </td>
              ))}
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Bjork batch + due
function BjorkPanel(): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const due = useHarnessStore((s) => s.due);
  const queue = useHarnessStore((s) => s.practiceQueue);
  const refreshDue = useHarnessStore((s) => s.refreshDue);
  const refreshQueue = useHarnessStore((s) => s.refreshQueue);
  const createSession = useHarnessStore((s) => s.createSession);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const busy = useHarnessStore((s) => s.busy.create);
  const [cueLevel, setCueLevel] = useState(2);

  useEffect(() => {
    void refreshDue();
    void refreshQueue();
  }, [refreshDue, refreshQueue]);

  const windowNodes = useMemo(
    () => (graph?.nodes ?? []).filter((n) => n.retrievability >= 0.7 && n.retrievability <= 0.85).sort((a, b) => a.retrievability - b.retrievability),
    [graph],
  );
  const domainsInQueue = new Set(queue.slice(0, 6).map((q) => q.domain_cluster)).size;

  const launch = (): void => {
    void createSession({
      mode: 'PRACTICE',
      target_goal: `Bjork batch: ${windowNodes.length} nodes in the desirable-difficulty window, interleaved across ${domainsInQueue} domains`,
      cue_level: cueLevel,
    });
  };

  return (
    <div className="bjork-grid">
      <section className="card">
        <div className="card-head">
          <span>Bjork Batch launcher</span>
          <span className="mono dim">{windowNodes.length} nodes with R ∈ [0.70, 0.85]</span>
        </div>
        <p className="dim small">
          Retrieval is most potent just before forgetting (Bjork's desirable difficulty). The batch runs the interleaved practice queue —
          consecutive picks from one domain are penalised (Rohrer &amp; Taylor 2007) — at the chosen cue level.
        </p>
        <div className="row gap">
          <div className="seg">
            <span className="seg-label">Cue level</span>
            {[1, 2, 3, 4].map((l) => (
              <button key={l} className={`seg-btn${cueLevel === l ? ' on' : ''}`} onClick={() => setCueLevel(l)}>
                L{l}
              </button>
            ))}
          </div>
          <span className="spacer" />
          <button className="btn primary" disabled={busy || queue.length === 0} onClick={launch}>
            {busy ? <Spinner /> : null}Launch Bjork Batch ({Math.min(queue.length, 12)} items)
          </button>
        </div>
        <div className="window-list">
          {windowNodes.length === 0 ? <div className="dim small">No nodes in the window right now — the queue will target the nearest ones.</div> : null}
          {windowNodes.map((n) => (
            <button key={n.id} className="window-item" onClick={() => focus(n.id)}>
              <span className="dot-inline" style={{ background: domainColor(n.domain_cluster, n.node_type) }} />
              <span className="truncate">{n.title}</span>
              <span className="mono" style={{ color: C.cyan }}>
                R {fx(n.retrievability, 3)}
              </span>
            </button>
          ))}
        </div>
        <div className="insp-label">Batch order (interleaved queue)</div>
        <ol className="batch-order mono small">
          {queue.map((q) => (
            <li key={q.node_id}>
              <span className="dot-inline" style={{ background: domainColor(q.domain_cluster) }} />
              {q.title} <span className="dim">score {fx(q.score, 3)}</span>
              {q.interleave_penalty > 0 ? <span style={{ color: C.amber }}> −{fx(q.interleave_penalty, 2)} interleave</span> : null}
            </li>
          ))}
        </ol>
      </section>
      <section className="card">
        <div className="card-head">
          <span className="mono">$ ./harness-cli due</span>
          <span className="mono dim">desired retention r = 0.90 · I = (81/19)·S·(r⁻² − 1)</span>
        </div>
        <div className="table-scroll">
          <table className="tbl compact mono">
            <thead>
              <tr>
                <th>next due</th>
                <th>Δ</th>
                <th className="num">R</th>
                <th className="num">S</th>
                <th>node</th>
              </tr>
            </thead>
            <tbody>
              {due.map((d) => (
                <tr key={d.node_id} className="clickable" onClick={() => focus(d.node_id)}>
                  <td>{fmtDateTime(d.next_due_at)}</td>
                  <td style={{ color: d.days_until_due <= 0 ? C.rose : d.days_until_due < 1 ? C.amber : C.muted }}>{dueRelative(d.days_until_due)}</td>
                  <td className="num">{fx(d.retrievability, 3)}</td>
                  <td className="num">{fx(d.stability, 2)}d</td>
                  <td className="truncate sans">{d.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {due.length === 0 ? <div className="dim pad small">Nothing scheduled.</div> : null}
        </div>
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ notes manager
function NotesPanel(): JSX.Element {
  const files = useHarnessStore((s) => s.workspaceFiles);
  const openFile = useHarnessStore((s) => s.openFile);
  const openWorkspaceFile = useHarnessStore((s) => s.openWorkspaceFile);
  const refreshFiles = useHarnessStore((s) => s.refreshFiles);
  const runSubagent = useHarnessStore((s) => s.runSubagent);
  const openModal = useHarnessStore((s) => s.openModal);
  const setLauncherPreset = useHarnessStore((s) => s.setLauncherPreset);
  const setTab = useHarnessStore((s) => s.setTab);
  const createSession = useHarnessStore((s) => s.createSession);
  const busy = useHarnessStore((s) => s.busy.dispatch);
  const activeId = useHarnessStore((s) => s.activeSessionId);
  const [view, setView] = useState<'blocks' | 'source'>('blocks');
  const [pattern, setPattern] = useState('');

  useEffect(() => {
    void refreshFiles();
  }, [refreshFiles]);

  const groups = useMemo(() => {
    const g = new Map<string, typeof files>();
    files.forEach((f) => {
      const dir = f.path.includes('/') ? f.path.split('/')[0] : '.';
      g.set(dir, [...(g.get(dir) ?? []), f]);
    });
    return [...g.entries()];
  }, [files]);

  const run = async (agent: AgentName, extra: { filename?: string; pattern?: string; topic?: string }): Promise<void> => {
    const a = await runSubagent(agent, { session_id: activeId, ...extra });
    if (a) openModal({ kind: 'artifact', id: a.id });
  };

  return (
    <div className="notes-grid">
      <aside className="file-tree">
        <div className="card-head">
          <span>workspace/</span>
          <button className="btn tiny ghost" onClick={() => void refreshFiles()}>
            ↻
          </button>
        </div>
        {groups.map(([dir, fs]) => (
          <div key={dir} className="file-group">
            <div className="file-dir mono dim">{dir}/</div>
            {fs.map((f) => (
              <button key={f.path} className={`file-item${openFile?.path === f.path ? ' on' : ''}`} onClick={() => void openWorkspaceFile(f.path)}>
                <span className={`ft mono ft-${f.kind}`}>{f.kind}</span>
                <span className="truncate">{f.path.split('/').slice(1).join('/') || f.path}</span>
                <span className="dim mono small">{timeAgo(f.modified_at)}</span>
              </button>
            ))}
          </div>
        ))}
        {files.length === 0 ? <div className="dim small pad">No files in workspace/notes or workspace/problems.</div> : null}
        <div className="rag-box">
          <div className="insp-label">Corpus search (LOCAL_CORPUS_RAG)</div>
          <input className="mono" placeholder="ripgrep pattern" value={pattern} onChange={(e) => setPattern(e.target.value)} />
          <button className="btn small block" disabled={!pattern.trim() || busy} onClick={() => void run('LOCAL_CORPUS_RAG', { pattern })}>
            {busy ? <Spinner /> : null}grep workspace
          </button>
        </div>
      </aside>
      <section className="file-view">
        {openFile ? (
          <>
            <div className="card-head">
              <span className="mono">{openFile.path}</span>
              <span className="spacer" />
              <div className="seg">
                <button className={`seg-btn${view === 'blocks' ? ' on' : ''}`} onClick={() => setView('blocks')}>
                  blocks ({openFile.blocks.length})
                </button>
                <button className={`seg-btn${view === 'source' ? ' on' : ''}`} onClick={() => setView('source')}>
                  source
                </button>
              </div>
            </div>
            <div className="file-actions">
              <button
                className="btn small"
                onClick={() => {
                  setLauncherPreset({ attached_files: [openFile.path] });
                  setTab(1);
                }}
              >
                Attach to new session
              </button>
              {openFile.path.startsWith('problems/') ? (
                <button
                  className="btn small primary"
                  onClick={() => void createSession({ mode: 'PRACTICE', target_goal: `Practice from ${openFile.path}`, problem_file: openFile.path, cue_level: 2 })}
                >
                  Practice this problem set
                </button>
              ) : null}
              <button className="btn small ghost" disabled={busy} onClick={() => void run('LOCAL_CORPUS_RAG', { filename: openFile.path })}>
                RAG excerpt
              </button>
              <button className="btn small ghost" disabled={busy} onClick={() => void run('ONTOLOGIST_EXTRACTOR', { filename: openFile.path, topic: openFile.path })}>
                Extract ontology → graph
              </button>
            </div>
            <div className="file-content">
              {view === 'source' ? (
                <pre className="code-block">{openFile.content}</pre>
              ) : openFile.blocks.length ? (
                openFile.blocks.map((b, i) => (
                  <div key={i} className={`tex-block env-${b.env}`}>
                    <div className="tex-block-head mono">
                      <span className="tag">{b.env}</span> {b.title} <span className="dim">L{b.line}</span>
                    </div>
                    <MathText text={b.body} />
                  </div>
                ))
              ) : (
                <MathText text={openFile.content} />
              )}
            </div>
          </>
        ) : (
          <div className="dim pad">Select a note or problem file to read its parsed theorem / definition / problem blocks.</div>
        )}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ artifact vault
function ArtifactVault(): JSX.Element {
  const artifacts = useHarnessStore((s) => s.artifacts);
  const refreshArtifacts = useHarnessStore((s) => s.refreshArtifacts);
  const openModal = useHarnessStore((s) => s.openModal);
  const [agent, setAgent] = useState<AgentName | ''>('');
  const rows = artifacts.filter((a) => !agent || a.agent_name === agent);
  return (
    <div className="panel-fill">
      <div className="filters">
        <select value={agent} onChange={(e) => setAgent(e.target.value as AgentName | '')}>
          <option value="">all 8 agents</option>
          {ALL_AGENTS.map((a) => (
            <option key={a} value={a}>
              {AGENT_META[a].short}
            </option>
          ))}
        </select>
        <button className="btn small ghost" onClick={() => void refreshArtifacts()}>
          ↻ refresh
        </button>
        <span className="mono dim small">{rows.length} artifacts</span>
      </div>
      <div className="table-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>agent</th>
              <th>title</th>
              <th>type</th>
              <th>status</th>
              <th>session</th>
              <th>created</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id} className="clickable" onClick={() => openModal({ kind: 'artifact', id: a.id })}>
                <td className="mono small">
                  {AGENT_META[a.agent_name].glyph} {a.agent_name}
                </td>
                <td>{a.title}</td>
                <td>
                  <span className={`ct mono ct-${a.content_type}`}>{a.content_type}</span>
                </td>
                <td className={`mono small s-${a.status.toLowerCase()}`}>{a.status}</td>
                <td className="mono dim small">{a.session_id ?? '—'}</td>
                <td className="mono dim small">{fmtDateTime(a.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
