/** Pieces every step card shares: plain headings, the inline result, the "Preparing…" skeleton and the Details body. */
import { useMemo, type ReactNode } from 'react';
import { useHarnessStore, type HeldResult } from '../store/useHarnessStore';
import type { EIGRow, ProsodyMetrics, StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { DetailRow, PrimaryButton, outcomeHeadline, plainFeedback, usePrimaryAction } from './kit';
import { AssessmentCard } from './PracticeArena';

export const KIND_LINE: Record<string, string> = {
  PROBE: 'What do you already know?',
  PREDICT: 'Make a prediction',
  CHECK: 'Check yourself',
  PRODUCTIVE_FAILURE: 'Give it a try before any explanation',
  READING: 'Read',
  PRACTICE_CHUNK: 'Practice',
  REFEREE: 'Find the flaw',
  FEYNMAN: 'Explain it',
  LEARN: 'Learn it first',
  COMPLETE: 'Done',
};

/** Plain heading for a step: the idea it is about (server titles carry internal labels such as "cue level 2"). */
export function useStepHeading(step: StepPayload): string {
  const graph = useHarnessStore((s) => s.graph);
  const plan = useHarnessStore((s) => s.sessionState?.session.dependency_plan);
  return useMemo(() => {
    const id = step.target_node_ids[0];
    const nodeTitle = (id && (graph?.nodes.find((n) => n.id === id)?.title ?? plan?.find((p) => p.node_id === id)?.title)) || '';
    const t = step.title.trim();
    if (!t || /cue level|^session complete$/i.test(t)) return nodeTitle || t;
    const dot = t.indexOf(' · ');
    if (dot > 0 && dot < 24) return t.slice(dot + 3);
    return t;
  }, [step, graph, plan]);
}

/** Server prompts occasionally carry pacing notes such as "(Δ = 2.5)"; they belong in Details. */
export function cleanPrompt(s: string): string {
  return s.replace(/\s*\(Δ\s*=\s*[\d.]+\)/g, '').replace(/\*Synthesis leap:\*/g, '*A bigger step:*');
}

export function CardHead({ step, children }: { step: StepPayload; children?: ReactNode }): JSX.Element {
  const heading = useStepHeading(step);
  return (
    <header className="card-head">
      <p className="kind">{KIND_LINE[step.kind] ?? ''}</p>
      {heading ? <h1 className="card-title">{heading}</h1> : null}
      {children}
    </header>
  );
}

// ------------------------------------------------------------------ inline result
export function ResultBlock({ held }: { held: HeldResult }): JSX.Element {
  const continueFromResult = useHarnessStore((s) => s.continueFromResult);
  const askPolya = useHarnessStore((s) => s.askPolya);
  const thread = useHarnessStore((s) => s.chat.thread);
  const r = held.result;
  const offer = r.offer && !thread.some((m) => m.role === 'polya' && m.step_index === r.offer?.step_index) ? r.offer : null;
  const head = outcomeHeadline(r.trace.outcome, held.step.kind);
  const fb = useMemo(() => plainFeedback(r.feedback_markdown), [r.feedback_markdown]);
  usePrimaryAction(continueFromResult, true);
  return (
    <section className={`result tone-${head.tone}`} aria-live="polite">
      <p className="result-head">
        <span className="result-mark" aria-hidden="true">
          {head.tone === 'good' ? '✓' : head.tone === 'bad' ? '✗' : head.tone === 'mid' ? '◐' : '·'}
        </span>
        {head.text}
      </p>
      {fb.main.map((p, i) => (
        <MathText key={i} text={p} className="result-body" />
      ))}
      {offer ? (
        <p className="offer-line">
          <button className="text-btn inline" onClick={() => void askPolya('OFFER', { trigger: offer.trigger, stepIndex: offer.step_index })}>
            {offer.label} <span aria-hidden="true">Ask Pólya →</span>
          </button>
        </p>
      ) : null}
      <div className="actions">
        <PrimaryButton onClick={continueFromResult}>Continue</PrimaryButton>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ skeleton
export function PreparingCard({ text = 'Preparing your next step…' }: { text?: string }): JSX.Element {
  return (
    <article className="card preparing" aria-busy="true">
      <p className="kind" role="status">
        {text}
      </p>
      <div className="sk sk-title" />
      <div className="sk sk-line" />
      <div className="sk sk-line" />
      <div className="sk sk-line short" />
      <div className="sk sk-box" />
      <p className="prep-note">This can take up to half a minute when a fresh question is being written.</p>
    </article>
  );
}

// ------------------------------------------------------------------ details body
function EigTable({ rows, chosen }: { rows: EIGRow[]; chosen: string | undefined }): JSX.Element {
  const sorted = [...rows].sort((a, b) => b.eig - a.eig);
  return (
    <table className="dtable">
      <caption>Why this question: expected information gain (EIG) for each idea</caption>
      <thead>
        <tr>
          <th>idea</th>
          <th className="num">P(knows)</th>
          <th className="num">entropy</th>
          <th className="num">EIG</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.node_id} className={r.node_id === chosen ? 'chosen' : ''}>
            <td>{r.title}</td>
            <td className="num">{r.p_mastery.toFixed(2)}</td>
            <td className="num">{r.entropy.toFixed(3)}</td>
            <td className="num">{r.eig.toFixed(3)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ProsodyRows({ m }: { m: ProsodyMetrics }): JSX.Element {
  return (
    <DetailRow k="Voice (prosody)">
      {m.engine} · first word after {m.initial_latency_ms} ms · {m.hesitation_count} pauses · {m.hedge_count} hedges · {Math.round(m.wpm)} wpm ·{' '}
      {(m.total_silence_ms / 1000).toFixed(1)} s silence
    </DetailRow>
  );
}

function RelatedArtifacts({ sessionId }: { sessionId: string | null }): JSX.Element | null {
  const artifacts = useHarnessStore((s) => s.artifacts);
  const openModal = useHarnessStore((s) => s.openModal);
  const list = useMemo(() => artifacts.filter((a) => sessionId && a.session_id === sessionId).slice(0, 8), [artifacts, sessionId]);
  if (!list.length) return null;
  return (
    <div className="dsec">
      <div className="dsec-k">Helper output (sub-agent artifacts)</div>
      <ul className="dlist">
        {list.map((a) => (
          <li key={a.id}>
            <button className="linkish" onClick={() => openModal({ kind: 'artifact', id: a.id })}>
              {a.title}
            </button>{' '}
            <span className="muted">{a.agent_name.toLowerCase().replace(/_/g, ' ')}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Body of the Details disclosure for any step card. */
export function StepDetails({ step, held, extra }: { step: StepPayload; held?: HeldResult | null; extra?: ReactNode }): JSX.Element {
  const sessionId = useHarnessStore((s) => s.activeSessionId);
  const metrics = useHarnessStore((s) => s.voice.metrics);
  const tech = held ? plainFeedback(held.result.feedback_markdown).tech : [];
  return (
    <>
      {step.rationale ? (
        <div className="dsec">
          <div className="dsec-k">Why this step</div>
          <MathText text={step.rationale} />
        </div>
      ) : null}
      {step.kind === 'PROBE' && step.eig_table.length ? <EigTable rows={step.eig_table} chosen={step.target_node_ids[0]} /> : null}
      {extra}
      {tech.length ? (
        <div className="dsec">
          <div className="dsec-k">Scoring notes</div>
          {tech.map((p, i) => (
            <MathText key={i} text={p} />
          ))}
        </div>
      ) : null}
      {held ? <AssessmentCard result={held.result} defaultOpen /> : null}
      <div className="dsec">
        <DetailRow k="Step">
          {step.step_index + 1} · {step.kind} · cue level {step.cue_level} · Δ {step.delta.toFixed(1)} · written by {step.generated_by}
        </DetailRow>
        {held?.result.controller ? <DetailRow k="Pacing">{held.result.controller.summary}</DetailRow> : null}
        <ProsodyRows m={held ? held.result.trace.prosody_metrics : metrics} />
      </div>
      <RelatedArtifacts sessionId={sessionId} />
    </>
  );
}
