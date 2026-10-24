/**
 * LearnHarness cognitive workspace shell (ARCHITECTURE_SPEC §6).
 * Views: 1 Active Learning Session · 2 Epistemic Hypergraph · 3 Practice & Referee Arena · 4 Reasoning Chains & Vault.
 * Global keys: 1–4 switch views (when not typing) · Ctrl+Space toggles the mic · Esc closes the inspector.
 * (Cmd/Ctrl+Enter = lock raw prediction and Shift+Enter = submit chunk/step are bound by the step components.)
 */
import { useEffect, useMemo } from 'react';
import DependencyMiniMap from './components/DependencyMiniMap';
import EpistemicLockBox from './components/EpistemicLockBox';
import HypergraphCanvas from './components/HypergraphCanvas';
import PracticeArena, { ArenaLauncher, AssessmentCard } from './components/PracticeArena';
import ReadingStreamBox from './components/ReadingStreamBox';
import ReasoningChainsTable from './components/ReasoningChainsTable';
import RefereeDuelArena from './components/RefereeDuelArena';
import SidebarSubagentDock, { SubagentModals } from './components/SidebarSubagentDock';
import TopTelemetryBar from './components/TopTelemetryBar';
import { C, EmptyState, OUTCOME_COLOR, fx, isTypingTarget, modeLabel, pct } from './components/ui';
import { useHarnessStore, type TabId } from './store/useHarnessStore';
import type { Outcome, SessionState, StepPayload } from './types/harness';

const ARENA_KINDS = new Set(['PRACTICE_CHUNK', 'REFEREE', 'FEYNMAN']);

function StepView({ step }: { step: StepPayload }): JSX.Element {
  switch (step.kind) {
    case 'PROBE':
    case 'PREDICT':
    case 'CHECK':
    case 'PRODUCTIVE_FAILURE':
      return <EpistemicLockBox key={step.step_id} step={step} />;
    case 'READING':
      return <ReadingStreamBox key={step.step_id} step={step} />;
    case 'PRACTICE_CHUNK':
      return <PracticeArena key={step.step_id} step={step} />;
    case 'REFEREE':
    case 'FEYNMAN':
      return <RefereeDuelArena key={step.step_id} step={step} />;
    case 'COMPLETE':
      return <SessionComplete />;
  }
}

function SessionHeader({ st }: { st: SessionState }): JSX.Element {
  const loadSession = useHarnessStore((s) => s.loadSession);
  const clearSession = useHarnessStore((s) => s.clearSession);
  const busy = useHarnessStore((s) => s.busy.session);
  const s = st.session;
  return (
    <div className="session-header">
      <div className="sh-main">
        <div className="sh-title">{s.title}</div>
        <div className="sh-meta mono">
          <span className={`mode-tag m-${s.mode.toLowerCase()}`}>{modeLabel(s.mode, s.sub_mode)}</span>
          <span className="dim">step {st.active_step.step_index + 1}</span>
          <span className="dim">{st.traces.length} traces</span>
          <span className={`status-tag ${s.status.toLowerCase()}`}>{s.status}</span>
          {s.attached_files.length ? <span className="dim">📎 {s.attached_files.join(', ')}</span> : null}
        </div>
      </div>
      <button className="btn tiny ghost" disabled={busy} onClick={() => void loadSession(s.id)} title="Reload GET /api/sessions/{id}">
        ↻
      </button>
      <button className="btn tiny ghost" onClick={clearSession} title="Close this session view">
        ✕
      </button>
    </div>
  );
}

function SessionComplete(): JSX.Element {
  const st = useHarnessStore((s) => s.sessionState);
  const graph = useHarnessStore((s) => s.graph);
  const createSession = useHarnessStore((s) => s.createSession);
  const setTab = useHarnessStore((s) => s.setTab);
  const busy = useHarnessStore((s) => s.busy.create);
  const summary = useMemo(() => {
    const traces = st?.traces ?? [];
    const counts = new Map<Outcome, number>();
    traces.forEach((t) => counts.set(t.outcome, (counts.get(t.outcome) ?? 0) + 1));
    const graded = traces.filter((t) => t.outcome !== 'EXPLORATION_LOGGED');
    const brier = graded.length ? graded.reduce((a, t) => a + t.brier_score, 0) / graded.length : null;
    const acc = graded.length ? graded.filter((t) => t.is_correct === 1).length / graded.length : null;
    const conf = graded.length ? graded.reduce((a, t) => a + t.confidence_slider, 0) / graded.length : null;
    const planIds = new Set((st?.session.dependency_plan ?? []).map((p) => p.node_id));
    const weakest = (graph?.nodes ?? []).filter((n) => planIds.has(n.id)).sort((a, b) => a.bkt_p_mastery - b.bkt_p_mastery)[0];
    return { traces, counts, brier, acc, conf, weakest };
  }, [st, graph]);
  if (!st) return <EmptyState title="No session" />;
  return (
    <div className="stream-card complete">
      <div className="complete-title">Session complete</div>
      <div className="dim">{st.session.target_goal}</div>
      <div className="outcome-bars">
        {[...summary.counts.entries()].map(([o, n]) => (
          <span key={o} className="outcome-tag mono" style={{ color: OUTCOME_COLOR[o], borderColor: OUTCOME_COLOR[o] }}>
            {o} ×{n}
          </span>
        ))}
      </div>
      <div className="meta-grid">
        <div className="stat">
          <div className="stat-k">Accuracy</div>
          <div className="stat-v mono">{summary.acc === null ? '—' : pct(summary.acc)}</div>
        </div>
        <div className="stat">
          <div className="stat-k">Mean confidence</div>
          <div className="stat-v mono">{summary.conf === null ? '—' : pct(summary.conf)}</div>
        </div>
        <div className="stat">
          <div className="stat-k">Session Brier</div>
          <div className="stat-v mono">{fx(summary.brier, 3)}</div>
        </div>
        <div className="stat">
          <div className="stat-k">Final Δ</div>
          <div className="stat-v mono">{st.session.step_velocity_delta.toFixed(1)}</div>
        </div>
      </div>
      <div className="row gap">
        <button className="btn" onClick={() => setTab(2)}>
          Open hypergraph
        </button>
        {summary.weakest ? (
          <button
            className="btn primary"
            disabled={busy}
            onClick={() =>
              void createSession({
                mode: 'PRACTICE',
                target_goal: `Practice: ${summary.weakest?.title}`,
                target_node_id: summary.weakest?.id,
                cue_level: 2,
              })
            }
          >
            Practice weakest node: {summary.weakest.title} ({fx(summary.weakest.bkt_p_mastery)})
          </button>
        ) : null}
      </div>
    </div>
  );
}

function LastResult({ compact }: { compact?: boolean }): JSX.Element | null {
  const last = useHarnessStore((s) => s.lastResult);
  const activeId = useHarnessStore((s) => s.activeSessionId);
  if (!last || last.sessionId !== activeId) return null;
  return <AssessmentCard key={last.result.trace.id} result={last.result} defaultOpen={!compact} />;
}

function Welcome(): JSX.Element {
  const sessions = useHarnessStore((s) => s.sessions);
  const loadSession = useHarnessStore((s) => s.loadSession);
  const stats = useHarnessStore((s) => s.stats);
  const backendOk = useHarnessStore((s) => s.backendOk);
  return (
    <div className="welcome">
      <div className="welcome-title">No active session</div>
      <p className="dim">
        Launch a session from the left dock: <b>Probe → Teach</b> binary-searches your prerequisites by expected information gain,{' '}
        <b>Productive Failure</b> lets you struggle first, <b>Adaptive Practice</b> serves cue-demand problems from the Bjork window, and the{' '}
        <b>duels</b> stress-test you adversarially.
      </p>
      {stats ? (
        <div className="welcome-stats mono">
          <span>{stats.total_nodes} nodes</span>
          <span>{stats.total_hyperedges} hyperedges</span>
          <span style={{ color: C.cyan }}>{stats.bjork_window_count} in Bjork window</span>
          <span style={{ color: stats.due_count ? C.amber : undefined }}>{stats.due_count} due</span>
          <span>mean P(L) {fx(stats.mean_mastery)}</span>
        </div>
      ) : backendOk === false ? (
        <div className="warn-text">Backend unreachable on :8000 — start it with ./start.sh; the UI reconnects automatically.</div>
      ) : null}
      {sessions.length ? (
        <div className="welcome-sessions">
          <div className="insp-label">Resume</div>
          {sessions.slice(0, 5).map((s) => (
            <button key={s.id} className="session-item" onClick={() => void loadSession(s.id, s.mode === 'PRACTICE' || s.mode === 'REFEREE_DUEL' ? 3 : 1)}>
              <div className="session-title">{s.title}</div>
              <div className="session-meta mono">
                <span className={`mode-tag m-${s.mode.toLowerCase()}`}>{modeLabel(s.mode, s.sub_mode)}</span>
                <span className={`status-tag ${s.status.toLowerCase()}`}>{s.status}</span>
              </div>
            </button>
          ))}
        </div>
      ) : null}
      <div className="keys mono dim small">
        keys · 1–4 views · ⌘/Ctrl+Enter lock prediction · Shift+Enter submit chunk/step · Ctrl+Space mic · Esc close
      </div>
    </div>
  );
}

function SessionCenter(): JSX.Element {
  const st = useHarnessStore((s) => s.sessionState);
  const setTab = useHarnessStore((s) => s.setTab);
  if (!st) return <Welcome />;
  const step = st.active_step;
  return (
    <div className="center-stream">
      <SessionHeader st={st} />
      <LastResult compact={step.kind !== 'COMPLETE'} />
      {ARENA_KINDS.has(step.kind) ? (
        <div className="arena-hint small">
          This step runs in the arena —{' '}
          <button className="link" onClick={() => setTab(3)}>
            open 3. Practice &amp; Referee Arena
          </button>{' '}
          for the queue and launch controls.
        </div>
      ) : null}
      <StepView step={step} />
    </div>
  );
}

function ArenaCenter(): JSX.Element {
  const st = useHarnessStore((s) => s.sessionState);
  const setTab = useHarnessStore((s) => s.setTab);
  const step = st?.active_step;
  return (
    <div className="center-stream arena">
      <ArenaLauncher />
      {st ? <SessionHeader st={st} /> : null}
      <LastResult />
      {step && ARENA_KINDS.has(step.kind) ? <StepView step={step} /> : null}
      {step && step.kind === 'COMPLETE' ? <SessionComplete /> : null}
      {step && !ARENA_KINDS.has(step.kind) && step.kind !== 'COMPLETE' ? (
        <div className="stream-card muted-card">
          The active session is on a <b>{step.kind}</b> step.{' '}
          <button className="link" onClick={() => setTab(1)}>
            Continue it in 1. Active Learning Session
          </button>{' '}
          or start a practice / duel above.
        </div>
      ) : null}
      {!st ? (
        <div className="stream-card muted-card">
          Pick a cue level and start practice, launch a Proof-Referee or Feynman duel, or practise any node straight from the queue.
        </div>
      ) : null}
    </div>
  );
}

function Toasts(): JSX.Element {
  const toasts = useHarnessStore((s) => s.toasts);
  const dismiss = useHarnessStore((s) => s.dismissToast);
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <button key={t.id} className={`toast ${t.kind}`} onClick={() => dismiss(t.id)}>
          {t.text}
        </button>
      ))}
    </div>
  );
}

function OfflineBanner(): JSX.Element | null {
  const backendOk = useHarnessStore((s) => s.backendOk);
  const ws = useHarnessStore((s) => s.wsStatus);
  if (backendOk !== false && ws !== 'closed') return null;
  return (
    <div className="offline">
      {backendOk === false ? 'Backend unreachable (http://127.0.0.1:8000).' : 'Live WebSocket disconnected.'} Reconnecting automatically ·{' '}
      <span className="mono">./start.sh</span>
    </div>
  );
}

export default function App(): JSX.Element {
  const init = useHarnessStore((s) => s.init);
  const tab = useHarnessStore((s) => s.tab);
  const setTab = useHarnessStore((s) => s.setTab);
  const toggleMic = useHarnessStore((s) => s.toggleMic);

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      // Ctrl+Space: toggle dictation anywhere (even while typing)
      if (e.ctrlKey && (e.code === 'Space' || e.key === ' ')) {
        e.preventDefault();
        void toggleMic();
        return;
      }
      const s = useHarnessStore.getState();
      if (e.key === 'Escape' && !s.modal && (s.selectedNodeId || s.selectedEdgeId)) {
        s.selectNode(null);
        s.selectEdge(null);
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target) || s.modal) return;
      if (e.key >= '1' && e.key <= '4') {
        e.preventDefault();
        setTab(Number(e.key) as TabId);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setTab, toggleMic]);

  const withSidebar = tab === 1 || tab === 3;

  return (
    <div className="app">
      <TopTelemetryBar />
      <main className={`main${withSidebar ? ' with-sidebar' : ''} tab-${tab}`}>
        <OfflineBanner />
        {withSidebar ? <SidebarSubagentDock /> : null}
        {tab === 1 ? <SessionCenter /> : null}
        {tab === 3 ? <ArenaCenter /> : null}
        {withSidebar ? <DependencyMiniMap /> : null}
        {tab === 2 ? <HypergraphCanvas /> : null}
        {tab === 4 ? <ReasoningChainsTable /> : null}
      </main>
      <SubagentModals />
      <Toasts />
    </div>
  );
}
