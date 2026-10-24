/**
 * Challenge cards.
 *  Proof check (REFEREE): the proof's steps as cards; click the wrong one, explain why (optionally a counterexample) → Submit.
 *  Explain it (FEYNMAN): a chat with a confused student (POST /duel) until every edge case is covered, then Finish (POST /submit).
 * Submission payloads are unchanged from the previous components.
 */
import { useEffect, useMemo, useRef } from 'react';
import { useHarnessStore, type HeldResult } from '../store/useHarnessStore';
import type { DuelTurn, StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { ConfidenceChips, DetailRow, Details, MathField, PrimaryButton, Spinner, usePrimaryAction } from './kit';
import { CardHead, ResultBlock, StepDetails, cleanPrompt } from './stepParts';

function ProofReferee({ step, held }: { step: StepPayload; held?: HeldResult | null }): JSX.Element {
  const live = useHarnessStore((s) => s.draft);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busy = useHarnessStore((s) => s.busy.submit);
  const done = Boolean(held);
  const draft = held ? held.draft : live;
  const flagged = draft.flaggedStepIndex;
  const steps = [...step.proof_steps].sort((a, b) => a.index - b.index);
  const canSubmit = !done && flagged !== null && draft.text.trim().length > 0 && !busy;

  const submit = (): void => {
    if (!canSubmit) return;
    void submitStep({ selected_answer: String(flagged) });
  };
  usePrimaryAction(submit, canSubmit);

  return (
    <article className="card referee">
      <CardHead step={step} />
      <div className="prompt">
        <MathText text={cleanPrompt(step.prompt_latex || 'Exactly one step below is wrong. Find it.')} />
      </div>
      <ol className="proof" aria-label="Proof steps">
        {steps.map((p, i) => {
          const on = flagged === p.index;
          return (
            <li key={p.index}>
              <button
                className={`proof-step${on ? ' on' : ''}`}
                onClick={() => setDraft({ flaggedStepIndex: on ? null : p.index })}
                aria-pressed={on}
                disabled={done}
              >
                <span className="proof-n">Step {i + 1}</span>
                <span className="proof-t">
                  <MathText text={p.text_latex} latexField />
                </span>
                {on ? <span className="proof-flag">This one</span> : null}
              </button>
            </li>
          );
        })}
      </ol>
      <MathField
        label={flagged === null ? 'Why is it wrong? (click a step first)' : `Why is step ${steps.findIndex((s) => s.index === flagged) + 1} wrong?`}
        placeholder="Name what the step quietly assumes, and why that does not hold here."
        value={draft.text}
        onChange={(v) => setDraft({ text: v })}
        micTarget="dock"
        rows={3}
        readOnly={done}
      />
      <label className="plain-field">
        <span className="field-label">A counterexample (optional)</span>
        <textarea
          rows={2}
          value={draft.counterexample}
          readOnly={done}
          placeholder="A small case where the step's claim fails."
          onChange={(e) => setDraft({ counterexample: e.target.value })}
        />
      </label>
      <ConfidenceChips value={draft.confidence} onChange={(v) => setDraft({ confidence: v })} disabled={done} />
      {!done ? (
        <div className="actions">
          <PrimaryButton onClick={submit} disabled={!canSubmit} busy={busy} busyLabel="Checking…">
            Submit
          </PrimaryButton>
        </div>
      ) : null}
      {held ? <ResultBlock held={held} /> : null}
      <Details>
        <StepDetails step={step} held={held} />
      </Details>
    </article>
  );
}

function sameTurn(a: DuelTurn, b: DuelTurn): boolean {
  return a.role === b.role && a.text.trim() === b.text.trim();
}

function FeynmanDuel({ step, held }: { step: StepPayload; held?: HeldResult | null }): JSX.Element {
  const duelLog = useHarnessStore((s) => s.duelLog);
  const sendDuel = useHarnessStore((s) => s.sendDuel);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busyDuel = useHarnessStore((s) => s.busy.duel);
  const busySubmit = useHarnessStore((s) => s.busy.submit);
  const liveText = useHarnessStore((s) => s.draft.text);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const graph = useHarnessStore((s) => s.graph);
  const chatRef = useRef<HTMLOListElement>(null);
  const done = Boolean(held);
  const text = held ? held.draft.text : liveText;

  const local = !held && duelLog.stepId === step.step_id ? duelLog : { turns: [] as DuelTurn[], reply: null };
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
    chatRef.current?.lastElementChild?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [transcript.length, busyDuel]);

  const submit = (): void => {
    if (done || learnerTurns.length === 0 || busySubmit) return;
    void submitStep({
      verification_thinking: learnerTurns.map((t) => t.text).join('\n\n'),
      raw_prediction_locked: learnerTurns[0]?.text ?? '',
      selected_answer: resolved ? 'RESOLVED' : 'UNRESOLVED',
    });
  };
  const send = (): void => {
    if (done || !text.trim() || busyDuel) return;
    void sendDuel();
  };
  const primary = resolved ? submit : send;
  usePrimaryAction(primary, !done);

  return (
    <article className="card feynman">
      <CardHead step={step} />
      <div className="prompt">
        <MathText text={cleanPrompt(step.prompt_latex)} />
      </div>
      {step.student_persona ? (
        <p className="aside-note">
          <MathText text={step.student_persona} inline />
        </p>
      ) : null}

      <div className="covered" aria-label={`Edge cases covered: ${met.length} of ${total || 'several'}`}>
        <span className="muted small">
          Edge cases covered: {met.length} of {total || '?'}
        </span>
        <span className="covered-track" aria-hidden="true">
          {Array.from({ length: Math.max(total, met.length, 1) }).map((_, i) => (
            <span key={i} className={`covered-cell${i < met.length ? ' on' : ''}`} title={met[i] ?? 'Not covered yet'} />
          ))}
        </span>
      </div>

      <ol className="chat" ref={chatRef} aria-label="Conversation">
        {transcript.map((t, i) => (
          <li key={i} className={`bubble ${t.role}`}>
            <span className="who">{t.role === 'student' ? 'Student' : 'You'}</span>
            <MathText text={t.text} />
          </li>
        ))}
        {busyDuel ? (
          <li className="bubble student typing">
            <span className="who">Student</span>
            <span className="muted">
              <Spinner /> thinking…
            </span>
          </li>
        ) : null}
      </ol>

      {resolved && !done ? <p className="aside-note good">The student is convinced. Finish to save how it went.</p> : null}

      {!done ? (
        <>
          <MathField
            label="Your explanation"
            placeholder="Explain the idea, and exactly when it applies, so the student can't misuse it."
            value={text}
            onChange={(v) => setDraft({ text: v })}
            micTarget="dock"
            rows={3}
            autoFocus
            onShiftEnter={send}
            hint="Shift+Enter sends your message."
          />
          <div className="actions">
            {resolved ? (
              <PrimaryButton onClick={submit} busy={busySubmit} busyLabel="Saving…">
                Finish
              </PrimaryButton>
            ) : (
              <>
                <PrimaryButton onClick={send} disabled={!text.trim()} busy={busyDuel} busyLabel="Sending…">
                  Send
                </PrimaryButton>
                {learnerTurns.length ? (
                  <button className="text-btn" disabled={busySubmit} onClick={submit}>
                    {busySubmit ? <Spinner /> : null}Finish now
                  </button>
                ) : null}
              </>
            )}
          </div>
        </>
      ) : null}

      {held ? <ResultBlock held={held} /> : null}

      <Details>
        <StepDetails
          step={step}
          held={held}
          extra={
            <div className="dsec">
              {buggy ? (
                <DetailRow k="The student's misconception (buggy rule)">
                  {buggy.title}: <MathText text={buggy.statement_latex} inline latexField />
                </DetailRow>
              ) : null}
              {met.length ? <DetailRow k="Boundary conditions stated">{met.join(' · ')}</DetailRow> : null}
            </div>
          }
        />
      </Details>
    </article>
  );
}

export default function RefereeDuelArena({ step, held }: { step: StepPayload; held?: HeldResult | null }): JSX.Element {
  return step.kind === 'FEYNMAN' ? <FeynmanDuel step={step} held={held} /> : <ProofReferee step={step} held={held} />;
}
