/**
 * Question card: PROBE / PREDICT / CHECK (guess first, then choose) and PRODUCTIVE_FAILURE (try first, no options).
 *  1. "Your guess, in your own words" (≥15 characters, typed or dictated) → Lock in guess
 *  2. the answer options fade in (their space is reserved, so nothing below moves) → pick one → confidence chip → Check
 *  3. the result appears inline → Continue
 * The submission payload is unchanged: the store builds it from the draft exactly as before.
 */
import { useMemo, useState } from 'react';
import { useHarnessStore, type HeldResult } from '../store/useHarnessStore';
import type { StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { ConfidenceChips, Details, MathField, PrimaryButton, correctFromFeedback, isChipValue, usePrimaryAction } from './kit';
import { CardHead, ResultBlock, StepDetails, cleanPrompt } from './stepParts';

const MIN_RAW = 15;

export default function EpistemicLockBox({ step, held }: { step: StepPayload; held?: HeldResult | null }): JSX.Element {
  const liveDraft = useHarnessStore((s) => s.draft);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const lock = useHarnessStore((s) => s.lockRawPrediction);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busy = useHarnessStore((s) => s.busy.submit);
  const [why, setWhy] = useState(false);

  const done = Boolean(held);
  const draft = held ? held.draft : liveDraft;
  const isPF = step.kind === 'PRODUCTIVE_FAILURE';
  const needsLock = !isPF;
  const locked = draft.rawLockedAtMs !== null;
  const gateOpen = !needsLock || locked;
  const rawLen = draft.rawPrediction.trim().length;
  const hasOptions = step.options.length > 0;
  const chosen = isChipValue(draft.confidence);
  const correctId = held ? correctFromFeedback(held.result.feedback_markdown) : null;

  const canSubmit = useMemo(() => {
    if (busy || done) return false;
    if (!gateOpen) return false;
    if (hasOptions) return draft.selectedOption !== '' && chosen;
    if (isPF) return draft.text.trim().length > 0 || draft.rawPrediction.trim().length > 0;
    return true;
  }, [busy, done, gateOpen, hasOptions, draft.selectedOption, draft.text, draft.rawPrediction, isPF, chosen]);

  const submit = (): void => {
    if (!canSubmit) return;
    void submitStep(isPF && !draft.rawPrediction.trim() ? { raw_prediction_locked: draft.text.trim() } : undefined);
  };

  /** PREDICT has no options: locking the guess is the whole step. */
  const lockAndMaybeSubmit = (): void => {
    if (done || busy) return;
    if (!lock()) return;
    if (!hasOptions) void submitStep();
  };

  const primary = !gateOpen || (!hasOptions && !isPF) ? lockAndMaybeSubmit : submit;
  usePrimaryAction(primary, !done);

  return (
    <article className="card question">
      <CardHead step={step} />
      <div className="prompt">
        <MathText text={cleanPrompt(step.prompt_latex)} />
      </div>

      {isPF ? (
        <>
          <MathField
            label="Your attempts"
            placeholder="Try anything: a special case, a picture, a small example. Dead ends are useful."
            value={draft.text}
            onChange={(v) => setDraft({ text: v })}
            micTarget="dock"
            rows={5}
            readOnly={done}
            autoFocus
          />
          {!done ? (
            <div className="actions">
              <PrimaryButton onClick={submit} disabled={!canSubmit} busy={busy} busyLabel="Saving…">
                Show me the idea
              </PrimaryButton>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <MathField
            label="Your guess, in your own words"
            placeholder="Before you see any choices: what do you expect, and why? Half-formed is fine."
            value={draft.rawPrediction}
            onChange={(v) => setDraft({ rawPrediction: v })}
            micTarget="raw"
            rows={3}
            readOnly={locked || done}
            autoFocus={!locked}
          />
          <div className="lock-row">
            {locked ? (
              <span className="locked-note">✓ Guess locked in</span>
            ) : (
              <>
                <PrimaryButton
                  onClick={lockAndMaybeSubmit}
                  disabled={rawLen < MIN_RAW}
                  busy={busy}
                  busyLabel="Saving…"
                  title={rawLen < MIN_RAW ? `Write at least ${MIN_RAW} characters` : undefined}
                >
                  Lock in guess
                </PrimaryButton>
                <span className="muted small">
                  {rawLen < MIN_RAW
                    ? 'One sentence is enough.'
                    : hasOptions
                      ? 'The choices appear once your guess is locked in.'
                      : 'Then read on and see how close you were.'}
                </span>
              </>
            )}
          </div>
        </>
      )}

      {hasOptions ? (
        <div className={`options-zone${gateOpen ? ' open' : ''}`}>
          <div className="options" role="radiogroup" aria-label="Answer choices" aria-hidden={!gateOpen}>
            {step.options.map((o, i) => {
              const sel = draft.selectedOption === o.id;
              const right = correctId !== null && o.id === correctId;
              const wrong = done && sel && correctId !== null && !right;
              return (
                <button
                  key={o.id}
                  role="radio"
                  aria-checked={sel}
                  className={`option${sel ? ' on' : ''}${right ? ' right' : ''}${wrong ? ' wrong' : ''}`}
                  disabled={!gateOpen || done}
                  tabIndex={gateOpen && !done ? 0 : -1}
                  onClick={() => setDraft({ selectedOption: o.id })}
                >
                  <span className="opt-key" aria-hidden="true">
                    {String.fromCharCode(65 + i)}
                  </span>
                  <span className="opt-text">
                    <MathText text={o.label_latex} latexField inline />
                  </span>
                </button>
              );
            })}
          </div>
          {!gateOpen ? (
            <div className="options-veil" aria-hidden="true">
              <span>Answer choices appear here after you lock in your guess.</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {hasOptions && gateOpen ? (
        <div className="after-lock">
          {why || draft.text ? (
            <MathField
              label="Why this choice? (optional)"
              placeholder="A line of reasoning helps Pólya see how you think."
              value={draft.text}
              onChange={(v) => setDraft({ text: v })}
              micTarget="dock"
              rows={2}
              readOnly={done}
            />
          ) : !done ? (
            <button className="text-btn" onClick={() => setWhy(true)}>
              Add your reasoning
            </button>
          ) : null}
          <ConfidenceChips value={draft.confidence} onChange={(v) => setDraft({ confidence: v })} disabled={done} />
          {!done ? (
            <div className="actions">
              <PrimaryButton onClick={submit} disabled={!canSubmit} busy={busy} busyLabel="Checking…">
                Check
              </PrimaryButton>
              {!draft.selectedOption ? <span className="muted small">Pick an answer, then say how sure you are.</span> : !chosen ? <span className="muted small">How sure are you?</span> : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {held ? <ResultBlock held={held} /> : null}

      <Details>
        <StepDetails step={step} held={held} />
      </Details>
    </article>
  );
}
