/**
 * Left sidebar (ARCHITECTURE_SPEC §6.2): New-Session launcher (topic, 6 modes, workspace .tex/.pdf attachments),
 * session list, and the live 8-Sub-Agent swarm monitor. Clicking an artifact opens its exact payload
 * (SymPy script/log, JSON diagnosis, RAG excerpt, SVG, sandbox demo, graph diff). Each agent can be dispatched manually.
 */
import { useEffect, useMemo, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import {
  ALL_AGENTS,
  type AgentName,
  type ArtifactOut,
  type CreateSessionRequest,
  type SessionMode,
  type SubMode,
  type SubagentRunRequest,
} from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import SandboxDemoViewer from './SandboxDemoViewer';
import { C, Modal, Spinner, fmtDateTime, modeLabel, timeAgo } from './ui';

interface ModeOption {
  key: string;
  mode: SessionMode;
  sub_mode: SubMode;
  label: string;
  blurb: string;
}

export const MODE_OPTIONS: ModeOption[] = [
  { key: 'probe', mode: 'PROBE', sub_mode: 'STANDARD', label: 'Probe → Teach', blurb: 'EIG binary search over prerequisites, then teach the gaps.' },
  { key: 'pf', mode: 'PRODUCTIVE_FAILURE', sub_mode: 'STANDARD', label: 'Productive Failure → Teach', blurb: 'Struggle with an open problem first; failure is logged as exploration.' },
  { key: 'teach', mode: 'TEACH', sub_mode: 'STANDARD', label: 'Teach (direct)', blurb: 'PREDICT → READING → CHECK per plan node.' },
  { key: 'practice', mode: 'PRACTICE', sub_mode: 'STANDARD', label: 'Adaptive Practice', blurb: 'Cue-demand problems from the interleaved Bjork-window queue.' },
  { key: 'referee', mode: 'REFEREE_DUEL', sub_mode: 'PROOF_REFEREE', label: 'Proof-Referee Duel', blurb: 'Find the one camouflaged fallacy in a 5-step proof.' },
  { key: 'feynman', mode: 'REFEREE_DUEL', sub_mode: 'FEYNMAN_STUDENT', label: 'Feynman Student Duel', blurb: 'Explain to a student holding a buggy rule until boundaries are rigorous.' },
];

export const AGENT_META: Record<AgentName, { short: string; glyph: string; role: string }> = {
  SYMBOLIC_VERIFIER: { short: 'Symbolic Verifier', glyph: '∑', role: 'SymPy/NumPy subprocess checks' },
  BUG_LIBRARY_DIAGNOSTICIAN: { short: 'Bug-Library Diagnostician', glyph: '⚕', role: 'trace quality · miss class · buggy rules' },
  COUNTEREXAMPLE_SYNTHESIZER: { short: 'Counterexample Synth', glyph: '✕', role: 'falsifies over-general claims' },
  SANDBOX_DEMO_BUILDER: { short: 'Sandbox Demo Builder', glyph: '◫', role: 'interactive HTML5 demos' },
  SVG_DIAGRAM_MAKER: { short: 'SVG Diagram Maker', glyph: '⬡', role: 'dark-mode diagrams' },
  LOCAL_CORPUS_RAG: { short: 'Local Corpus RAG', glyph: '⌕', role: 'grep/parse workspace notes' },
  LITERATURE_RESEARCHER: { short: 'Literature Researcher', glyph: '❡', role: 'arXiv citations' },
  ONTOLOGIST_EXTRACTOR: { short: 'Ontologist Extractor', glyph: '⟁', role: 'nodes + hyperedges + depth' },
};

export default function SidebarSubagentDock(): JSX.Element {
  return (
    <aside className="sidebar">
      <NewSessionLauncher />
      <SessionList />
      <SwarmMonitor />
    </aside>
  );
}

/** Artifact + dispatch modals, mounted once at the app root so they open from any view. */
export function SubagentModals(): JSX.Element | null {
  const modal = useHarnessStore((s) => s.modal);
  const openModal = useHarnessStore((s) => s.openModal);
  if (modal?.kind === 'artifact') return <ArtifactModal id={modal.id} onClose={() => openModal(null)} />;
  if (modal?.kind === 'dispatch') return <DispatchModal agent={modal.agent} onClose={() => openModal(null)} />;
  return null;
}

// ------------------------------------------------------------------ launcher
function NewSessionLauncher(): JSX.Element {
  const files = useHarnessStore((s) => s.workspaceFiles);
  const graph = useHarnessStore((s) => s.graph);
  const createSession = useHarnessStore((s) => s.createSession);
  const busy = useHarnessStore((s) => s.busy.create);
  const preset = useHarnessStore((s) => s.launcherPreset);
  const [topic, setTopic] = useState('');
  const [modeKey, setModeKey] = useState('probe');
  const [attached, setAttached] = useState<string[]>([]);
  const [targetNode, setTargetNode] = useState('');
  const [cueLevel, setCueLevel] = useState(1);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (!preset) return;
    setOpen(true);
    if (preset.attached_files) setAttached(preset.attached_files);
    if (preset.target_node_id !== undefined) setTargetNode(preset.target_node_id ?? '');
    if (preset.target_goal) setTopic(preset.target_goal);
    if (preset.mode) {
      const m = MODE_OPTIONS.find((o) => o.mode === preset.mode && (!preset.sub_mode || o.sub_mode === preset.sub_mode));
      if (m) setModeKey(m.key);
    }
  }, [preset]);

  const opt = MODE_OPTIONS.find((o) => o.key === modeKey) ?? MODE_OPTIONS[0];
  const attachable = files.filter((f) => f.kind === 'tex' || f.kind === 'pdf' || f.kind === 'md');
  const nodes = useMemo(() => [...(graph?.nodes ?? [])].sort((a, b) => a.title.localeCompare(b.title)), [graph]);
  const targetTitle = nodes.find((n) => n.id === targetNode)?.title;
  const goal = topic.trim() || (targetTitle ? `${opt.label}: ${targetTitle}` : '');
  const canLaunch = goal.length > 0 || opt.mode === 'PRACTICE';

  const launch = async (): Promise<void> => {
    const req: CreateSessionRequest = {
      mode: opt.mode,
      sub_mode: opt.sub_mode,
      target_goal: goal || 'Interleaved Bjork-window practice',
      attached_files: attached,
      target_node_id: targetNode || null,
      cue_level: cueLevel,
    };
    const st = await createSession(req);
    if (st) setTopic('');
  };

  return (
    <section className="side-section">
      <button className="side-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span>New Session</span>
        <span className="dim mono">{open ? '−' : '+'}</span>
      </button>
      {open ? (
        <div className="launcher">
          <textarea
            className="launcher-topic"
            placeholder="What do you want to understand? e.g. Why does attention divide by √d_k?"
            value={topic}
            rows={2}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && canLaunch) {
                e.preventDefault();
                e.stopPropagation();
                void launch();
              }
            }}
          />
          <div className="mode-grid" role="radiogroup" aria-label="Mode">
            {MODE_OPTIONS.map((o) => (
              <button
                key={o.key}
                role="radio"
                aria-checked={o.key === modeKey}
                className={`mode-chip${o.key === modeKey ? ' on' : ''}`}
                onClick={() => setModeKey(o.key)}
                title={o.blurb}
              >
                {o.label}
              </button>
            ))}
          </div>
          <div className="dim small launcher-blurb">{opt.blurb}</div>
          <div className="launcher-row">
            <select value={targetNode} onChange={(e) => setTargetNode(e.target.value)} title="Optional target node">
              <option value="">target node: auto</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.title}
                </option>
              ))}
            </select>
            {opt.mode === 'PRACTICE' ? (
              <select value={cueLevel} onChange={(e) => setCueLevel(Number(e.target.value))} title="Cue obfuscation level">
                <option value={1}>L1 canonical</option>
                <option value={2}>L2 disguised</option>
                <option value={3}>L3 synthesis</option>
                <option value={4}>L4 violated premise</option>
              </select>
            ) : null}
          </div>
          {attachable.length ? (
            <div className="attach-list">
              <div className="dim small">Attach from workspace/</div>
              {attachable.map((f) => (
                <label key={f.path} className="attach">
                  <input
                    type="checkbox"
                    checked={attached.includes(f.path)}
                    onChange={(e) =>
                      setAttached((a) => (e.target.checked ? [...a, f.path] : a.filter((p) => p !== f.path)))
                    }
                  />
                  <span className="mono truncate" title={f.path}>
                    {f.path}
                  </span>
                  <span className="dim mono">{(f.size / 1024).toFixed(1)}k</span>
                </label>
              ))}
            </div>
          ) : null}
          <button className="btn primary block" disabled={!canLaunch || busy} onClick={() => void launch()}>
            {busy ? (
              <>
                <Spinner /> Planning…
              </>
            ) : (
              <>Launch {opt.label}</>
            )}
          </button>
        </div>
      ) : null}
    </section>
  );
}

// ------------------------------------------------------------------ sessions
function SessionList(): JSX.Element {
  const sessions = useHarnessStore((s) => s.sessions);
  const activeId = useHarnessStore((s) => s.activeSessionId);
  const loadSession = useHarnessStore((s) => s.loadSession);
  return (
    <section className="side-section sessions">
      <div className="side-head static">
        <span>Sessions</span>
        <span className="dim mono">{sessions.length}</span>
      </div>
      <div className="session-list">
        {sessions.length === 0 ? <div className="dim small pad">No sessions yet — launch one above.</div> : null}
        {sessions.map((s) => {
          const done = s.dependency_plan.filter((p) => p.status === 'done' || p.status === 'probed_mastered').length;
          return (
            <button
              key={s.id}
              className={`session-item${s.id === activeId ? ' active' : ''}`}
              onClick={() => void loadSession(s.id, s.mode === 'PRACTICE' || s.mode === 'REFEREE_DUEL' ? 3 : 1)}
              title={s.target_goal}
            >
              <div className="session-title truncate">{s.title}</div>
              <div className="session-meta mono">
                <span className={`mode-tag m-${s.mode.toLowerCase()}`}>{modeLabel(s.mode, s.sub_mode)}</span>
                <span className="dim">
                  {done}/{s.dependency_plan.length} · Δ{s.step_velocity_delta.toFixed(1)}
                </span>
                <span className={`status-tag ${s.status.toLowerCase()}`}>{s.status}</span>
                <span className="dim">{timeAgo(s.updated_at)}</span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ swarm monitor
function SwarmMonitor(): JSX.Element {
  const subagents = useHarnessStore((s) => s.subagents);
  const artifacts = useHarnessStore((s) => s.artifacts);
  const activeId = useHarnessStore((s) => s.activeSessionId);
  const openModal = useHarnessStore((s) => s.openModal);
  const [sessionOnly, setSessionOnly] = useState(false);

  const byAgent = useMemo(() => {
    const m = new Map<AgentName, ArtifactOut[]>();
    ALL_AGENTS.forEach((a) => m.set(a, []));
    for (const a of artifacts) {
      if (sessionOnly && activeId && a.session_id !== activeId) continue;
      m.get(a.agent_name)?.push(a);
    }
    return m;
  }, [artifacts, sessionOnly, activeId]);

  const running = ALL_AGENTS.filter((a) => subagents[a].state === 'RUNNING').length;

  return (
    <section className="side-section swarm">
      <div className="side-head static">
        <span>Sub-Agent Swarm</span>
        <span className="mono" style={{ color: running ? C.indigo : C.dim }}>
          {running}/8 running
        </span>
      </div>
      <label className="swarm-filter small dim">
        <input type="checkbox" checked={sessionOnly} disabled={!activeId} onChange={(e) => setSessionOnly(e.target.checked)} />
        only this session's artifacts
      </label>
      <div className="agent-cards">
        {ALL_AGENTS.map((name) => {
          const st = subagents[name];
          const list = byAgent.get(name) ?? [];
          const meta = AGENT_META[name];
          return (
            <div key={name} className={`agent-card s-${st.state.toLowerCase()}`}>
              <div className="agent-top">
                <span className="agent-glyph">{meta.glyph}</span>
                <div className="agent-names">
                  <div className="agent-name">{meta.short}</div>
                  <div className="agent-role dim">{meta.role}</div>
                </div>
                <span className={`agent-state mono s-${st.state.toLowerCase()}`}>{st.state}</span>
              </div>
              <div className="agent-msg mono truncate" title={st.message}>
                {st.state === 'RUNNING' ? <Spinner /> : null} {st.message}
              </div>
              <div className="agent-arts">
                {list.slice(0, 3).map((a) => (
                  <button key={a.id} className="art-link" onClick={() => openModal({ kind: 'artifact', id: a.id })} title={a.title}>
                    <span className={`ct mono ct-${a.content_type}`}>{a.content_type}</span>
                    <span className="truncate">{a.title}</span>
                  </button>
                ))}
                {list.length > 3 ? <div className="dim small mono">+{list.length - 3} more in Vault</div> : null}
              </div>
              <div className="agent-foot">
                <span className="dim mono small">{list.length} artifacts</span>
                <button className="btn tiny ghost" onClick={() => openModal({ kind: 'dispatch', agent: name })}>
                  Dispatch ▸
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ artifact modal
function prettyJson(text: string): { ok: boolean; pretty: string; value: unknown } {
  try {
    const v = JSON.parse(text) as unknown;
    return { ok: true, pretty: JSON.stringify(v, null, 2), value: v };
  } catch {
    return { ok: false, pretty: text, value: null };
  }
}

export function ArtifactBody({ artifact }: { artifact: ArtifactOut }): JSX.Element {
  const sessionId = useHarnessStore((s) => s.activeSessionId);
  switch (artifact.content_type) {
    case 'html_demo':
      return <SandboxDemoViewer artifact={artifact} sessionId={sessionId} height={520} />;
    case 'svg':
      return (
        <div className="svg-frame">
          <img alt={artifact.title} src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(artifact.payload_text)}`} />
        </div>
      );
    case 'rag_excerpt':
      return <MathText text={artifact.payload_text} className="rag-body" />;
    case 'json_diagnosis':
    case 'graph_diff': {
      const j = prettyJson(artifact.payload_text);
      const md =
        j.ok && j.value && typeof j.value === 'object'
          ? ((j.value as Record<string, unknown>).diagnosis_markdown ?? (j.value as Record<string, unknown>).summary_markdown)
          : null;
      return (
        <>
          {typeof md === 'string' && md ? <MathText text={md} className="diag-md" /> : null}
          <pre className="code-block">{j.pretty}</pre>
        </>
      );
    }
    case 'sympy_log':
    default:
      return <pre className="code-block">{artifact.payload_text}</pre>;
  }
}

function ArtifactModal({ id, onClose }: { id: string; onClose: () => void }): JSX.Element {
  const art = useHarnessStore((s) => s.artifactCache[id]);
  const fetchArtifact = useHarnessStore((s) => s.fetchArtifact);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    void fetchArtifact(id);
  }, [id, fetchArtifact]);
  return (
    <Modal
      wide
      onClose={onClose}
      title={
        art ? (
          <>
            <span className="mono dim">{art.agent_name}</span> · {art.title}
          </>
        ) : (
          'Loading artifact…'
        )
      }
      footer={
        art ? (
          <>
            <span className="mono dim small">
              {art.id} · {art.content_type} · {art.status} · {fmtDateTime(art.created_at)}
              {art.session_id ? ` · session ${art.session_id}` : ''}
            </span>
            <span className="spacer" />
            <button
              className="btn ghost"
              onClick={() => {
                void navigator.clipboard
                  .writeText(art.payload_text)
                  .then(() => {
                    setCopied(true);
                    window.setTimeout(() => setCopied(false), 1500);
                  })
                  .catch(() => setCopied(false));
              }}
            >
              {copied ? '✓ Copied' : 'Copy payload'}
            </button>
          </>
        ) : null
      }
    >
      {art ? <ArtifactBody artifact={art} /> : <Spinner />}
    </Modal>
  );
}

// ------------------------------------------------------------------ manual dispatch
const SYMPY_TEMPLATE = `import sympy as sp
d = sp.symbols('d', positive=True, integer=True)
# Var(q.k) for iid unit-variance entries is d; scaling by 1/sqrt(d) restores unit variance
print(sp.simplify((1/sp.sqrt(d))**2 * d))`;

type FieldKey = 'topic' | 'node_id' | 'pattern' | 'filename' | 'code';
const AGENT_FIELDS: Record<AgentName, FieldKey[]> = {
  SYMBOLIC_VERIFIER: ['code', 'topic'],
  BUG_LIBRARY_DIAGNOSTICIAN: ['topic', 'node_id'],
  COUNTEREXAMPLE_SYNTHESIZER: ['topic', 'node_id'],
  SANDBOX_DEMO_BUILDER: ['topic', 'node_id'],
  SVG_DIAGRAM_MAKER: ['topic', 'node_id'],
  LOCAL_CORPUS_RAG: ['pattern', 'filename', 'topic'],
  LITERATURE_RESEARCHER: ['topic'],
  ONTOLOGIST_EXTRACTOR: ['topic', 'filename', 'node_id'],
};
const TOPIC_HINT: Record<AgentName, string> = {
  SYMBOLIC_VERIFIER: 'What the script verifies',
  BUG_LIBRARY_DIAGNOSTICIAN: 'Paste a learner thinking trace to diagnose',
  COUNTEREXAMPLE_SYNTHESIZER: 'Universal claim to falsify, e.g. "uncorrelated variables are always independent"',
  SANDBOX_DEMO_BUILDER: 'Demo concept, e.g. softmax saturation vs d_k',
  SVG_DIAGRAM_MAKER: 'Diagram subject, e.g. RoPE block rotations',
  LOCAL_CORPUS_RAG: 'Question to answer from your notes',
  LITERATURE_RESEARCHER: 'arXiv query, e.g. double Q-learning overestimation',
  ONTOLOGIST_EXTRACTOR: 'Text or topic to extract propositions from',
};

function DispatchModal({ agent, onClose }: { agent: AgentName; onClose: () => void }): JSX.Element {
  const runSubagent = useHarnessStore((s) => s.runSubagent);
  const openModal = useHarnessStore((s) => s.openModal);
  const busy = useHarnessStore((s) => s.busy.dispatch);
  const graph = useHarnessStore((s) => s.graph);
  const files = useHarnessStore((s) => s.workspaceFiles);
  const activeId = useHarnessStore((s) => s.activeSessionId);
  const selectedNode = useHarnessStore((s) => s.selectedNodeId);
  const fields = AGENT_FIELDS[agent];
  const [form, setForm] = useState<Record<FieldKey, string>>({
    topic: '',
    node_id: selectedNode ?? '',
    pattern: '',
    filename: '',
    code: agent === 'SYMBOLIC_VERIFIER' ? SYMPY_TEMPLATE : '',
  });
  const [attachSession, setAttachSession] = useState(Boolean(activeId));
  const set = (k: FieldKey, v: string): void => setForm((f) => ({ ...f, [k]: v }));

  const run = async (): Promise<void> => {
    const req: SubagentRunRequest = {
      session_id: attachSession ? activeId : null,
      topic: form.topic,
      node_id: form.node_id || null,
      pattern: form.pattern,
      filename: form.filename,
      code: form.code,
    };
    const a = await runSubagent(agent, req);
    if (a) openModal({ kind: 'artifact', id: a.id });
  };

  const hasInput = fields.some((f) => form[f].trim().length > 0);

  return (
    <Modal
      title={
        <>
          Dispatch <span className="mono">{agent}</span>
        </>
      }
      onClose={onClose}
      footer={
        <>
          <label className="small dim">
            <input type="checkbox" checked={attachSession} disabled={!activeId} onChange={(e) => setAttachSession(e.target.checked)} /> attach to
            active session
          </label>
          <span className="spacer" />
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy || !hasInput} onClick={() => void run()}>
            {busy ? (
              <>
                <Spinner /> Running…
              </>
            ) : (
              'Run agent'
            )}
          </button>
        </>
      }
    >
      <div className="dim small">{AGENT_META[agent].role}. The result is stored in subagent_artifacts and streamed to every client.</div>
      {fields.includes('code') ? (
        <label className="field">
          <span className="field-label">Python verification script (sympy / numpy / scipy, 5 s timeout)</span>
          <textarea className="code-editor" spellCheck={false} value={form.code} onChange={(e) => set('code', e.target.value)} />
        </label>
      ) : null}
      {fields.includes('topic') ? (
        <label className="field">
          <span className="field-label">{agent === 'SYMBOLIC_VERIFIER' ? 'Label' : 'Topic / input'}</span>
          <textarea rows={3} value={form.topic} placeholder={TOPIC_HINT[agent]} onChange={(e) => set('topic', e.target.value)} />
        </label>
      ) : null}
      {fields.includes('pattern') ? (
        <label className="field">
          <span className="field-label">ripgrep pattern</span>
          <input className="mono" value={form.pattern} placeholder="e.g. contraction|Banach" onChange={(e) => set('pattern', e.target.value)} />
        </label>
      ) : null}
      {fields.includes('filename') ? (
        <label className="field">
          <span className="field-label">Workspace file</span>
          <select value={form.filename} onChange={(e) => set('filename', e.target.value)}>
            <option value="">(none)</option>
            {files.map((f) => (
              <option key={f.path} value={f.path}>
                {f.path}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {fields.includes('node_id') ? (
        <label className="field">
          <span className="field-label">Graph node</span>
          <select value={form.node_id} onChange={(e) => set('node_id', e.target.value)}>
            <option value="">(none)</option>
            {(graph?.nodes ?? []).map((n) => (
              <option key={n.id} value={n.id}>
                {n.title}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </Modal>
  );
}
