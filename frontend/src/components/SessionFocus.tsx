/**
 * Session focus view: a thin strip (topic, one progress dot per idea in the plan, Exit) above ONE centered card.
 * The answered card stays on screen with its inline result until Continue; while the engine prepares the next step the
 * card is a calm skeleton. With Advanced telemetry on, the legacy helper dock and dependency tree flank the card.
 */
import { useMemo } from 'react';
import { usePrefs } from '../store/prefs';
import { useHarnessStore, type HeldResult } from '../store/useHarnessStore';
import type { Outcome, PlanItem, StepPayload } from '../types/harness';
import DependencyMiniMap from './DependencyMiniMap';
import EpistemicLockBox from './EpistemicLockBox';
import { DetailRow, Details, PrimaryButton, usePrimaryAction } from './kit';
import PracticeArena from './PracticeArena';
import ReadingStreamBox from './ReadingStreamBox';
import RefereeDuelArena from './RefereeDuelArena';
import SidebarSubagentDock from './SidebarSubagentDock';
import { PreparingCard } from './stepParts';
import { VoiceRow } from './TelemetryInputDock';

function StepView({ step, held }: { step: StepPayload; held?: HeldResult | null }): JSX.Element {
  switch (step.kind) {
    case 'PROBE':
    case 'PREDICT':
    case 'CHECK':
    case 'PRODUCTIVE_FAILURE':
      return <EpistemicLockBox key={step.step_id} step={step} held={held} />;
    case 'READING':
      return <ReadingStreamBox key={step.step_id} step={step} />;
    case 'PRACTICE_CHUNK':
      return <PracticeArena key={step.step_id} step={step} held={held} />;
    case 'REFEREE':
    case 'FEYNMAN':
      return <RefereeDuelArena key={step.step_id} step={step} held={held} />;
    case 'COMPLETE':
      return <SessionComplete />;
  }
}

const DOT_WORD: Record<string, string> = {
  pending: 'coming up',
  active: 'now',
  done: 'done',
  probed_mastered: 'you already know this',
  probed_unmastered: 'worth learning',
  skipped: 'skipped',
};

function ProgressDots({ plan, activeIds }: { plan: PlanItem[]; activeIds: Set<string> }): JSX.Element {
  const done = plan.filter((p) => p.status === 'done' || p.status === 'probed_mastered').length;
  return (
    <ol className="dots" aria-label={`Progress: ${done} of ${plan.length} ideas`}>
      {plan.map((p, i) => {
        const active = p.status === 'active' || activeIds.has(p.node_id);
        const cls = active ? 'now' : p.status === 'done' || p.status === 'probed_mastered' ? 'done' : p.status === 'probed_unmastered' ? 'gap' : 'todo';
        return (
          <li key={`${p.node_id}-${i}`} className={`dot ${cls}${p.remedial ? ' extra' : ''}`} title={`${p.title}: ${active ? 'now' : DOT_WORD[p.status] ?? p.status}${p.remedial ? ' (an extra step Pólya added)' : ''}`}>
            <span className="sr">{p.title}</span>
          </li>
        );
      })}
    </ol>
  );
}

function SessionComplete(): JSX.Element {
  const st = useHarnessStore((s) => s.sessionState);
  const graph = useHarnessStore((s) => s.graph);
  const createSession = useHarnessStore((s) => s.createSession);
  const exitFocus = useHarnessStore((s) => s.exitFocus);
  const setTab = useHarnessStore((s) => s.setTab);
  const busy = useHarnessStore((s) => s.busy.create);
  const summary = useMemo(() => {
    const traces = st?.traces ?? [];
    const counts = new Map<Outcome, number>();
    traces.forEach((t) => counts.set(t.outcome, (counts.get(t.outcome) ?? 0) + 1));
    const graded = traces.filter((t) => t.outcome !== 'EXPLORATION_LOGGED');
    const right = graded.filter((t) => t.is_correct === 1).length;
    const brier = graded.length ? graded.reduce((a, t) => a + t.brier_score, 0) / graded.length : null;
    const conf = graded.length ? graded.reduce((a, t) => a + t.confidence_slider, 0) / graded.length : null;
    const planIds = new Set((st?.session.dependency_plan ?? []).map((p) => p.node_id));
    const weakest = (graph?.nodes ?? []).filter((n) => planIds.has(n.id)).sort((a, b) => a.bkt_p_mastery - b.bkt_p_mastery)[0];
    return { counts, graded: graded.length, right, brier, conf, weakest };
  }, [st, graph]);

  const back = (): void => {
    exitFocus();
    setTab(1);
  };
  usePrimaryAction(back, true);
  if (!st) return <PreparingCard />;
  return (
    <article className="card complete">
      <header className="card-head">
        <p className="kind">Session complete</p>
        <h1 className="card-title">Nice work.</h1>
      </header>
      <p className="lede">
        {summary.graded
          ? `You got ${summary.right} of ${summary.graded} ${summary.graded === 1 ? 'question' : 'questions'} right.`
          : 'You worked through every step.'}{' '}
        Pólya will bring these ideas back right before you would forget them.
      </p>
      {summary.weakest ? (
        <p className="aside-note">
          Worth another look: <b>{summary.weakest.title}</b>.{' '}
          <button
            className="text-btn inline"
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
            Practice it now
          </button>
        </p>
      ) : null}
      <div className="actions">
        <PrimaryButton onClick={back}>Back to Learn</PrimaryButton>
      </div>
      <Details>
        <div className="dsec">
          <DetailRow k="Outcomes">
            {[...summary.counts.entries()].map(([o, n]) => `${o.toLowerCase().replace(/_/g, ' ')} ×${n}`).join(' · ') || '—'}
          </DetailRow>
          <DetailRow k="Mean confidence">{summary.conf === null ? '—' : `${Math.round(summary.conf * 100)}%`}</DetailRow>
          <DetailRow k="Session Brier score">{summary.brier === null ? '—' : summary.brier.toFixed(3)}</DetailRow>
          <DetailRow k="Final step size Δ">{st.session.step_velocity_delta.toFixed(1)}</DetailRow>
        </div>
      </Details>
    </article>
  );
}

export default function SessionFocus(): JSX.Element {
  const st = useHarnessStore((s) => s.sessionState);
  const held = useHarnessStore((s) => s.held);
  const creatingGoal = useHarnessStore((s) => s.creatingGoal);
  const busyCreate = useHarnessStore((s) => s.busy.create);
  const busyAdvance = useHarnessStore((s) => s.busy.advance);
  const busySession = useHarnessStore((s) => s.busy.session);
  const exitFocus = useHarnessStore((s) => s.exitFocus);
  const advanced = usePrefs((s) => s.advanced);

  const creating = Boolean(busyCreate && creatingGoal !== null);
  const topic = creating ? creatingGoal : st?.session.target_goal ?? '';
  const plan = creating ? [] : st?.session.dependency_plan ?? [];
  const activeIds = new Set(st?.active_step.target_node_ids ?? []);
  const showHeld = Boolean(held && st && held.sessionId === st.session.id);

  let body: JSX.Element;
  if (creating) body = <PreparingCard text="Preparing your first question…" />;
  else if (!st || busySession) body = <PreparingCard text="Opening your session…" />;
  else if (showHeld && held) body = <StepView step={held.step} held={held} />;
  else if (busyAdvance) body = <PreparingCard />;
  else body = <StepView step={st.active_step} />;

  return (
    <div className={`focus${advanced ? ' with-rails' : ''}`}>
      <div className="strip">
        <div className="strip-inner">
          <p className="strip-topic" title={topic ?? undefined}>
            {topic}
          </p>
          <ProgressDots plan={plan} activeIds={activeIds} />
          <button className="text-btn" onClick={exitFocus}>
            Exit
          </button>
        </div>
      </div>
      <div className="focus-body">
        {advanced ? (
          <div className="rail left legacy-skin">
            <SidebarSubagentDock />
          </div>
        ) : null}
        <div className="focus-center">
          {body}
          {advanced ? (
            <div className="legacy-skin voice-panel">
              <VoiceRow />
            </div>
          ) : null}
        </div>
        {advanced ? (
          <div className="rail right legacy-skin">
            <DependencyMiniMap />
          </div>
        ) : null}
      </div>
    </div>
  );
}
