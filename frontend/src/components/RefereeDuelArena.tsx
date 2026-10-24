/**
 * Adversarial Referee & Feynman Duel (ARCHITECTURE_SPEC §6.4.2).
 *  Mode A — Proof-Referee Debugger (REFEREE): clickable numbered proof-step cards, exactly one hides a camouflaged fallacy.
 *           Flag it, explain the violated hypothesis (dock), give a minimal counterexample, set confidence → POST /submit.
 *  Mode B — Feynman Buggy-Student Duel (FEYNMAN): a student holding a BUGGY_RULE stress-tests your explanation via
 *           POST /duel until every boundary condition is stated rigorously (`resolved`), then POST /submit.
 */
import { useEffect, useMemo, useRef } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { DuelTurn, StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { StepHeader } from './EpistemicLockBox';
import TelemetryInputDock from './TelemetryInputDock';
import { C } from './ui';

function ProofReferee({ step }: { step: StepPayload }): JSX.Element {
  const flagged = useHarnessStore((s) => s.draft.flaggedStepIndex);
  const counterexample = useHarnessStore((s) => s.draft.counterexample);
  const text = useHarnessStore((s) => s.draft.text);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busy = useHarnessStore((s) => s.busy.submit);
  const steps = [...step.proof_steps].sort((a, b) => a.index - b.index);
  const canSubmit = flagged !== null && text.trim().length > 0 && !busy;

  const submit = (): void => {
    if (!canSubmit) return;
    void submitStep({ selected_answer: String(flagged) });
  };

  return (
    <div className="stream-card referee">
      <StepHeader step={step} />
      <div className="prompt">
        <MathText text={step.prompt_latex || 'Exactly one step below contains a camouflaged fallacy. Find it.'} />
      </div>
      <div className="referee-legend dim small">
        Common camouflage: swapping lim and ∫ without a dominating envelope · assuming (AB)ᵀ = AᵀBᵀ · dropping covariance terms in a
        variance of a sum · max/expectation interchange.
      </div>
      <ol className="proof-steps">
        {steps.map((p, i) => (
          <li key={p.index}>
            <button
              className={`proof-step${flagged === p.index ? ' flagged' : ''}`}
              onClick={() => setDraft({ flaggedStepIndex: flagged === p.index ? null : p.index })}
              aria-pressed={flagged === p.index}
            >
              <span className="proof-num mono">Step {i + 1}</span>
              <span className="proof-text">
                <MathText text={p.text_latex} latexField />
              </span>
              <span className="proof-flag mono">{flagged === p.index ? '⚑ FLAGGED' : 'flag ▸'}</span>
            </button>
          </li>
        ))}
      </ol>
      <label className="field">
        <span className="field-label">Minimal counterexample (falsifies the flagged step)</span>
        <textarea
          rows={3}
          value={counterexample}
          placeholder="e.g. f_n = n·1_(0,1/n): ∫f_n = 1 for all n but f_n → 0 pointwise"
          onChange={(e) => setDraft({ counterexample: e.target.value })}
        />
      </label>
      <TelemetryInputDock
        label={flagged === null ? 'Violated hypothesis (flag a step first)' : `Why step ${steps.findIndex((s) => s.index === flagged) + 1} fails — the violated hypothesis`}
        placeholder="Name the hypothesis the step silently assumes and why it does not hold here."
        onShiftEnter={submit}
        shiftEnterLabel="submit verdict"
        actions={[{ label: 'Submit referee verdict', onClick: submit, disabled: !canSubmit, busy }]}
      />
    </div>
  );
}

function sameTurn(a: DuelTurn, b: DuelTurn): boolean {
  return a.role === b.role && a.text.trim() === b.text.trim();
}

function FeynmanDuel({ step }: { step: StepPayload }): JSX.Element {
  const duelLog = useHarnessStore((s) => s.duelLog);
  const sendDuel = useHarnessStore((s) => s.sendDuel);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busyDuel = useHarnessStore((s) => s.busy.duel);
  const busySubmit = useHarnessStore((s) => s.busy.submit);
  const text = useHarnessStore((s) => s.draft.text);
  const graph = useHarnessStore((s) => s.graph);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const chatRef = useRef<HTMLDivElement>(null);

  const local = duelLog.stepId === step.step_id ? duelLog : { turns: [] as DuelTurn[], reply: null };
  const transcript = useMemo(() => {
    const server = step.duel_transcript;
    const extra = local.turns.filter((t) => !server.some((s) => sameTurn(s, t)));
    return [...server, ...extra];
  }, [step.duel_transcript, local.turns]);

  const met = local.reply?.boundary_conditions_met ?? step.boundary_conditions_met;
  const total = Math.max(step.boundary_conditions_total, met.length + (local.reply?.boundary_conditions_remaining ?? 0));
  const resolved = local.reply?.resolved ?? (total > 0 && met.length >= total);
  const buggy = step.buggy_rule_id ? graph?.nodes.find((n) => n.id === step.buggy_rule_id) : undefined;
  const learnerTurns = transcript.filter((t) => t.role === 'learner');

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' });
  }, [transcript.length, busyDuel]);

  const submit = (): void => {
    void submitStep({
      verification_thinking: learnerTurns.map((t) => t.text).join('\n\n'),
      raw_prediction_locked: learnerTurns[0]?.text ?? '',
      selected_answer: resolved ? 'RESOLVED' : 'UNRESOLVED',
    });
  };

  return (
    <div className="stream-card feynman">
      <StepHeader step={step} />
      <div className="persona">
        <div className="persona-avatar">☺</div>
        <div className="persona-body">
          <div className="persona-title">
            Simulated student
            {buggy ? (
              <>
                {' '}
                holding{' '}
                <button className="link rose" onClick={() => focus(buggy.id)}>
                  ◆ {buggy.title}
                </button>
              </>
            ) : null}
          </div>
          <MathText text={step.student_persona || step.prompt_latex} />
          {buggy ? (
            <div className="dim small">
              <MathText text={buggy.statement_latex} inline latexField />
            </div>
          ) : null}
        </div>
      </div>
      {step.student_persona && step.prompt_latex ? (
        <div className="prompt subtle">
          <MathText text={step.prompt_latex} />
        </div>
      ) : null}

      <div className="boundary">
        <div className="boundary-head">
          <span>Boundary conditions stated</span>
          <span className="mono" style={{ color: resolved ? C.emerald : C.amber }}>
            {met.length}/{total || '?'} {resolved ? '· RESOLVED' : ''}
          </span>
        </div>
        <div className="boundary-track">
          {Array.from({ length: Math.max(total, met.length, 1) }).map((_, i) => (
            <span key={i} className={`boundary-cell${i < met.length ? ' met' : ''}`} title={met[i] ?? 'not yet stated'} />
          ))}
        </div>
        {met.length ? (
          <div className="boundary-list">
            {met.map((b) => (
              <span key={b} className="concept ok">
                ✓ <MathText text={b} inline />
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="chat" ref={chatRef}>
        {transcript.length === 0 ? <div className="dim small">The student is waiting for your explanation.</div> : null}
        {transcript.map((t, i) => (
          <div key={i} className={`bubble ${t.role}`}>
            <div className="bubble-role mono">{t.role === 'student' ? 'student' : 'you'}</div>
            <MathText text={t.text} />
          </div>
        ))}
        {busyDuel ? <div className="bubble student typing mono">student is thinking…</div> : null}
      </div>

      {resolved ? (
        <div className="resolved-banner">
          ✓ Every boundary condition has been stated rigorously. Submit the duel to update the graph (adversarial cue dimension).
        </div>
      ) : null}

      <TelemetryInputDock
        label="Your explanation to the student"
        placeholder="Explain the proposition — and its exact hypotheses — so the student cannot misapply it."
        onShiftEnter={() => void sendDuel()}
        shiftEnterLabel="send to student"
        actions={[
          { label: 'Send ▸', kind: resolved ? 'ghost' : 'primary', onClick: () => void sendDuel(), disabled: !text.trim(), busy: busyDuel },
          {
            label: resolved ? 'Submit duel for assessment' : 'Submit (unresolved)',
            kind: resolved ? 'primary' : 'ghost',
            onClick: submit,
            disabled: learnerTurns.length === 0,
            busy: busySubmit,
          },
        ]}
      />
    </div>
  );
}

export default function RefereeDuelArena({ step }: { step: StepPayload }): JSX.Element {
  return step.kind === 'FEYNMAN' ? <FeynmanDuel step={step} /> : <ProofReferee step={step} />;
}
