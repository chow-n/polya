/**
 * Review: one big "Start review (N due)" (interleaved practice: POST /api/sessions mode PRACTICE, no target, so the
 * backend picks from its queue), the due list with a simple memory bar, "Challenge me" (proof check / explain it) and
 * one plain sentence about calibration, with the Brier decomposition under Details.
 */
import { useMemo, useState } from 'react';
import { usePrefs } from '../store/prefs';
import { useHarnessStore } from '../store/useHarnessStore';
import type { CalibrationOut, DueItem } from '../types/harness';
import { DetailRow, Details, PrimaryButton, usePrimaryAction } from './kit';
import { ArenaLauncher } from './PracticeArena';

export function memoryWord(r: number): { word: string; tone: 'good' | 'mid' | 'bad' } {
  if (r >= 0.85) return { word: 'strong', tone: 'good' };
  if (r >= 0.7) return { word: 'fading', tone: 'mid' };
  return { word: 'needs review', tone: 'bad' };
}

export function MemoryBar({ r }: { r: number }): JSX.Element {
  const m = memoryWord(r);
  return (
    <span className={`membar tone-${m.tone}`} title={`Chance you'd recall it now: about ${Math.round(r * 100)}%`}>
      <span className="membar-track" aria-hidden="true">
        <span className="membar-fill" style={{ width: `${Math.max(4, Math.min(100, r * 100))}%` }} />
      </span>
      <span className="membar-word">{m.word}</span>
    </span>
  );
}

function when(d: DueItem): string {
  if (d.days_until_due <= 0) return 'due now';
  if (d.days_until_due < 1) return 'later today';
  const n = Math.round(d.days_until_due);
  return n === 1 ? 'tomorrow' : `in ${n} days`;
}

export function calibrationSentence(cal: CalibrationOut | undefined): string {
  if (!cal || cal.label === 'NO_DATA' || cal.n === 0) {
    return 'Answer a few questions and Pólya will tell you how well your confidence matches your results.';
  }
  const said = Math.round(cal.mean_confidence * 100);
  const right = Math.round(cal.accuracy * 100);
  switch (cal.label) {
    case 'OVERCONFIDENT':
      return `You tend to be overconfident: you say ${said}% sure and you’re right ${right}% of the time.`;
    case 'UNDERCONFIDENT':
      return `You tend to be underconfident: you say ${said}% sure but you’re right ${right}% of the time. Trust yourself a little more.`;
    default:
      return `Your confidence matches your results: you say ${said}% sure and you’re right ${right}% of the time.`;
  }
}

function CalibrationDetails({ cal }: { cal: CalibrationOut }): JSX.Element {
  return (
    <div className="dsec">
      <DetailRow k="Mean Brier score">{cal.mean_brier === null ? '—' : cal.mean_brier.toFixed(4)}</DetailRow>
      <DetailRow k="Murphy (1973) decomposition">
        BS = reliability − resolution + uncertainty = {cal.reliability.toFixed(4)} − {cal.resolution.toFixed(4)} + {cal.uncertainty.toFixed(4)}
      </DetailRow>
      <DetailRow k="Judgements">{cal.n}</DetailRow>
      <DetailRow k="Over/under-confidence">
        {cal.overconfidence >= 0 ? '+' : ''}
        {(cal.overconfidence * 100).toFixed(1)}%
      </DetailRow>
      {cal.bins.filter((b) => b.count > 0).length ? (
        <table className="dtable">
          <caption>By confidence level</caption>
          <thead>
            <tr>
              <th className="num">said</th>
              <th className="num">right</th>
              <th className="num">n</th>
            </tr>
          </thead>
          <tbody>
            {cal.bins
              .filter((b) => b.count > 0)
              .map((b, i) => (
                <tr key={i}>
                  <td className="num">{Math.round(b.mean_confidence * 100)}%</td>
                  <td className="num">{Math.round(b.accuracy * 100)}%</td>
                  <td className="num">{b.count}</td>
                </tr>
              ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}

export default function ReviewScreen(): JSX.Element {
  const due = useHarnessStore((s) => s.due);
  const stats = useHarnessStore((s) => s.stats);
  const createSession = useHarnessStore((s) => s.createSession);
  const busy = useHarnessStore((s) => s.busy.create);
  const setTab = useHarnessStore((s) => s.setTab);
  const graph = useHarnessStore((s) => s.graph);
  const advanced = usePrefs((s) => s.advanced);
  const [pick, setPick] = useState('');

  const dueNow = useMemo(() => due.filter((d) => d.days_until_due <= 0), [due]);
  const list = useMemo(() => (dueNow.length ? dueNow : due).slice(0, 8), [due, dueNow]);
  const n = stats?.due_count ?? dueNow.length;
  const nodes = useMemo(
    () => [...(graph?.nodes ?? [])].filter((x) => x.node_type !== 'BUGGY_RULE').sort((a, b) => a.title.localeCompare(b.title)),
    [graph],
  );
  const target = pick || dueNow[0]?.node_id || due[0]?.node_id || nodes[0]?.id || '';
  const targetTitle = nodes.find((x) => x.id === target)?.title ?? due.find((d) => d.node_id === target)?.title ?? '';

  const startReview = (): void => {
    if (busy || n === 0) return;
    void createSession({ mode: 'PRACTICE', target_goal: 'Review', target_node_id: null, cue_level: 1, contrastive_pair: false, problem_file: null });
  };
  const practiceOne = (d: DueItem): void => {
    void createSession({ mode: 'PRACTICE', target_goal: `Review: ${d.title}`, target_node_id: d.node_id, cue_level: 1 });
  };
  const duel = (sub: 'PROOF_REFEREE' | 'FEYNMAN_STUDENT'): void => {
    if (!target) return;
    void createSession({
      mode: 'REFEREE_DUEL',
      sub_mode: sub,
      target_goal: `${sub === 'PROOF_REFEREE' ? 'Find the flaw' : 'Explain it'}: ${targetTitle}`,
      target_node_id: target,
      cue_level: sub === 'PROOF_REFEREE' ? 4 : 1,
    });
  };
  usePrimaryAction(startReview, n > 0 && !busy);

  return (
    <div className="page review">
      <header className="page-head">
        <h1>Review</h1>
        <p className="lede">Pólya brings ideas back right before you’d forget them. A few minutes a day is plenty.</p>
      </header>

      {n > 0 ? (
        <div className="actions">
          <PrimaryButton onClick={startReview} busy={busy} busyLabel="Starting…">
            Start review ({n} due)
          </PrimaryButton>
        </div>
      ) : (
        <p className="empty">
          Nothing due. <button className="text-btn inline" onClick={() => setTab(1)}>Start something new</button>
        </p>
      )}

      {list.length ? (
        <section className="block" aria-labelledby="due-h">
          <h2 id="due-h">{dueNow.length ? 'Due now' : 'Coming up'}</h2>
          <ul className="rows">
            {list.map((d) => (
              <li key={d.node_id}>
                <button className="row-btn" onClick={() => practiceOne(d)} disabled={busy} title="Practice this idea now">
                  <span className="row-title">{d.title}</span>
                  <MemoryBar r={d.retrievability} />
                  <span className="row-meta">{dueNow.length ? '' : when(d)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="block" aria-labelledby="challenge-h">
        <h2 id="challenge-h">Challenge me</h2>
        <label className="inline-pick">
          <span className="muted">On</span>
          <select value={target} onChange={(e) => setPick(e.target.value)}>
            {nodes.map((x) => (
              <option key={x.id} value={x.id}>
                {x.title}
              </option>
            ))}
          </select>
        </label>
        <div className="challenge">
          <button className="challenge-btn" disabled={busy || !target} onClick={() => duel('PROOF_REFEREE')}>
            <span className="challenge-t">Find the flaw in a proof</span>
            <span className="muted small">One step is wrong. Spot it and say why.</span>
          </button>
          <button className="challenge-btn" disabled={busy || !target} onClick={() => duel('FEYNMAN_STUDENT')}>
            <span className="challenge-t">Explain it to a confused student</span>
            <span className="muted small">Keep explaining until they can’t find a hole.</span>
          </button>
        </div>
      </section>

      <section className="block" aria-labelledby="cal-h">
        <h2 id="cal-h">How well you know what you know</h2>
        <p className="cal-sentence">{calibrationSentence(stats?.calibration)}</p>
        {stats?.calibration ? (
          <Details>
            <CalibrationDetails cal={stats.calibration} />
          </Details>
        ) : null}
      </section>

      {advanced ? (
        <section className="block legacy-skin" aria-label="Advanced practice">
          <h2>Advanced practice</h2>
          <ArenaLauncher />
        </section>
      ) : null}
    </div>
  );
}
