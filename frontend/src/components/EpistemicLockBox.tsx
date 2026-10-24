/**
 * Two-Stage Epistemic Lock (ARCHITECTURE_SPEC §6.2, Law 3; pretesting effect per SPEC.md).
 * Handles PROBE / PREDICT / CHECK (lock flow) and PRODUCTIVE_FAILURE (open exploration, no options).
 *  Stage 1: raw stream-of-consciousness prediction (≥15 chars, typed or dictated) → "Lock In Raw Prediction (Cmd+Enter)"
 *  Stage 2: options unblur (or the direct symbolic-verification prompt appears); confidence + verification → submit.
 */
import { useEffect, useMemo, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { EIGRow, StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import TelemetryInputDock from './TelemetryInputDock';
import { Bar, C, fmtDateTime, fx } from './ui';

const MIN_RAW = 15;

export const KIND_LABEL: Record<string, string> = {
  PROBE: 'Diagnostic Probe',
  PRODUCTIVE_FAILURE: 'Productive Failure',
  PREDICT: 'Predict',
  CHECK: 'Check',
  READING: 'Reading',
  PRACTICE_CHUNK: 'Cue-Demand Practice',
  REFEREE: 'Proof Referee',
  FEYNMAN: 'Feynman Duel',
  COMPLETE: 'Complete',
};

export function StepHeader({ step }: { step: StepPayload }): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const titles = step.target_node_ids.map((id) => ({ id, title: graph?.nodes.find((n) => n.id === id)?.title ?? id }));
  return (
    <div className="step-head">
      <div className="step-head-row">
        <span className={`kind-badge k-${step.kind.toLowerCase()}`}>{KIND_LABEL[step.kind] ?? step.kind}</span>
        <span className="mono dim">step {step.step_index + 1}</span>
        <span className="mono dim" title="Cue obfuscation level: 1 canonical · 2 disguised · 3 synthesis/contrast · 4 violated premise">
          cue L{step.cue_level}
        </span>
        <span className="mono dim" title="Step velocity Δ (reasoning leap size)">
          Δ {step.delta.toFixed(1)}
        </span>
        <span className="spacer" />
        <span className="mono dim small" title="Engine that generated this step">
          {step.generated_by}
        </span>
      </div>
      {step.title ? <h2 className="step-title">{step.title}</h2> : null}
      {titles.length ? (
        <div className="target-chips">
          {titles.map((t) => (
            <button key={t.id} className="chip" onClick={() => focus(t.id)} title="Open in hypergraph inspector">
              ◎ {t.title}
            </button>
          ))}
        </div>
      ) : null}
      {step.rationale ? (
        <div className="rationale">
          <span className="rationale-k mono">why this step</span> <MathText text={step.rationale} inline />
        </div>
      ) : null}
    </div>
  );
}

function EigTable({ rows, chosen }: { rows: EIGRow[]; chosen: string | undefined }): JSX.Element {
  const [open, setOpen] = useState(true);
  const max = Math.max(1e-9, ...rows.map((r) => r.eig));
  const sorted = [...rows].sort((a, b) => b.eig - a.eig);
  return (
    <div className="eig">
      <button className="eig-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span>Why this probe? Expected-information-gain ranking</span>
        <span className="mono dim">
          EIG = H(v)·(1 + 0.4·P·|anc| + 0.4·(1−P)·|desc|) {open ? '▾' : '▸'}
        </span>
      </button>
      {open ? (
        <table className="tbl compact">
          <thead>
            <tr>
              <th>node</th>
              <th className="num">P(L)</th>
              <th className="num">H(v)</th>
              <th className="num">anc</th>
              <th className="num">desc</th>
              <th className="num">EIG</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.node_id} className={r.node_id === chosen ? 'chosen' : ''}>
                <td className="truncate" title={r.node_id}>
                  {r.node_id === chosen ? '▸ ' : ''}
                  {r.title}
                </td>
                <td className="num mono">{fx(r.p_mastery)}</td>
                <td className="num mono">{fx(r.entropy, 3)}</td>
                <td className="num mono">{r.unprobed_ancestors}</td>
                <td className="num mono">{r.unprobed_descendants}</td>
                <td className="num mono">{fx(r.eig, 3)}</td>
                <td className="bar-cell">
                  <Bar value={r.eig / max} color={r.node_id === chosen ? C.cyan : C.indigo} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}

export default function EpistemicLockBox({ step }: { step: StepPayload }): JSX.Element {
  const draft = useHarnessStore((s) => s.draft);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const lock = useHarnessStore((s) => s.lockRawPrediction);
  const setMicTarget = useHarnessStore((s) => s.setMicTarget);
  const micTarget = useHarnessStore((s) => s.micTarget);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busy = useHarnessStore((s) => s.busy.submit);

  const isPF = step.kind === 'PRODUCTIVE_FAILURE';
  // §6.2: every PROBE / PREDICT / CHECK step is locked (API Law 3 makes it mandatory when options_locked=true).
  const needsLock = !isPF;
  const locked = draft.rawLockedAtMs !== null;
  const gateOpen = !needsLock || locked;
  const rawLen = draft.rawPrediction.trim().length;
  const hasOptions = step.options.length > 0;

  // Law 3: Cmd/Ctrl+Enter anywhere locks the raw prediction while the lock is pending.
  useEffect(() => {
    if (!needsLock || locked) return;
    const onKey = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        lock();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [needsLock, locked, lock]);

  const canSubmit = useMemo(() => {
    if (busy) return false;
    if (!gateOpen) return false;
    if (hasOptions) return draft.selectedOption !== '';
    if (isPF) return draft.text.trim().length > 0 || draft.rawPrediction.trim().length > 0;
    return true;
  }, [busy, gateOpen, hasOptions, draft.selectedOption, draft.text, draft.rawPrediction, isPF]);

  const submit = (): void => {
    if (!canSubmit) return;
    void submitStep(isPF && !draft.rawPrediction.trim() ? { raw_prediction_locked: draft.text.trim() } : undefined);
  };

  const lockLatency = locked && draft.rawLockedAtMs !== null ? draft.rawLockedAtMs - draft.stepShownAt : 0;

  return (
    <div className="stream-card lockbox">
      <StepHeader step={step} />
      <div className="prompt">
        <MathText text={step.prompt_latex} />
      </div>
      {step.kind === 'PROBE' && step.eig_table.length ? <EigTable rows={step.eig_table} chosen={step.target_node_ids[0]} /> : null}

      {isPF ? (
        <div className="pf-note">
          <b>Productive failure.</b> Generate as many solution attempts and representations as you can before any instruction. Wrong
          attempts are logged as <span className="mono">EXPLORATION_LOGGED</span> and are not penalised — they prime the canonical
          solution you will see next.
        </div>
      ) : null}

      {needsLock ? (
        <div className={`raw-stage${locked ? ' locked' : ''}`}>
          <div className="raw-head">
            <span className="raw-title">Stage 1 · Raw prediction</span>
            {micTarget === 'raw' && !locked ? <span className="mic-target mono">● dictation → here</span> : null}
            <span className="spacer" />
            {locked ? (
              <span className="mono lock-stamp" title={new Date(draft.rawLockedAtMs ?? 0).toISOString()}>
                🔒 locked {fmtDateTime(new Date(draft.rawLockedAtMs ?? 0).toISOString())} · +{(lockLatency / 1000).toFixed(1)}s
              </span>
            ) : (
              <span className={`mono char-count${rawLen >= MIN_RAW ? ' ok' : ''}`}>
                {rawLen}/{MIN_RAW}
              </span>
            )}
          </div>
          {locked ? (
            <div className="raw-locked mono">{draft.rawPrediction}</div>
          ) : (
            <>
              <textarea
                className="raw-input"
                rows={3}
                autoFocus
                value={draft.rawPrediction}
                placeholder="Before seeing any options: what do you expect, and why? Stream of consciousness — half-formed is fine."
                onFocus={() => setMicTarget('raw')}
                onChange={(e) => setDraft({ rawPrediction: e.target.value })}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    lock();
                  }
                }}
              />
              <div className="raw-actions">
                <button className="btn primary" disabled={rawLen < MIN_RAW} onClick={() => lock()}>
                  🔒 Lock In Raw Prediction <span className="kbd mono">⌘/Ctrl+Enter</span>
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}

      {hasOptions ? (
        <div className={`options-wrap${gateOpen ? ' open' : ' sealed'}`}>
          <div className="options" aria-hidden={!gateOpen}>
            {step.options.map((o, i) => (
              <button
                key={o.id}
                className={`option${draft.selectedOption === o.id ? ' selected' : ''}`}
                disabled={!gateOpen}
                tabIndex={gateOpen ? 0 : -1}
                onClick={() => setDraft({ selectedOption: o.id })}
              >
                <span className="opt-key mono">{String.fromCharCode(65 + i)}</span>
                <MathText text={o.label_latex} latexField inline />
              </button>
            ))}
          </div>
          {!gateOpen ? (
            <div className="lock-overlay">
              <div className="lock-icon">🔒</div>
              <div className="lock-title">Epistemic Lock Active</div>
              <div className="lock-copy">
                Log your raw stream-of-consciousness prediction or intuition first to prevent recognition cues from contaminating
                retrieval.
              </div>
              <div className="lock-science">
                Pretesting effect (Richland, Kornell &amp; Kao 2009; Kornell, Hays &amp; Bjork 2009): an unaided retrieval attempt —
                even a wrong one — made <i>before</i> the answer is visible measurably improves what you learn from it. Options would turn
                recall into recognition.
              </div>
            </div>
          ) : null}
        </div>
      ) : gateOpen && !isPF ? (
        <div className="verify-prompt">
          <span className="mono tag cyan">DIRECT VERIFICATION</span> No options for this step — write the derivation or symbolic check in the
          dock; the Symbolic Verifier will test it.
        </div>
      ) : null}

      <TelemetryInputDock
        label={isPF ? 'Your attempts (exploration log)' : gateOpen ? 'Stage 2 · Verification thinking' : 'Verification thinking (unlocks with the prediction)'}
        placeholder={
          isPF
            ? 'Try anything: special cases, d=1, pictures, brute force. Every attempt is telemetry.'
            : 'Why this option? Check shapes, limits, the scalar case… LaTeX welcome: \\mathbb{E}[q^\\top k] = 0'
        }
        onShiftEnter={submit}
        shiftEnterLabel="submit step"
        disabled={!gateOpen}
        actions={[
          {
            label: hasOptions && !draft.selectedOption && gateOpen ? 'Select an option' : isPF ? 'Submit attempt' : 'Submit',
            onClick: submit,
            disabled: !canSubmit,
            busy,
          },
        ]}
      />
    </div>
  );
}
