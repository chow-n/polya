/**
 * Settings → Advanced: "How well Pólya predicts you" (docs/specs/model-eval-85). For each predictor of "will you get
 * the next one right?" — the learner model and two simple baselines — log-loss, Brier, AUC and a 5-bin calibration
 * strip, from GET /api/model-eval. Below 50 graded answers the numbers are shown greyed out.
 */
import { useEffect, useState } from 'react';
import { api } from '../store/useHarnessStore';
import type { CalibrationBin, ModelEvalOut } from '../types/harness';
import { Spinner } from './kit';

const fmt = (x: number | null, digits: number): string => (x === null ? '—' : x.toFixed(digits));
const pct = (x: number | null): string => (x === null ? '—' : `${Math.round(x * 100)}%`);

/** One cell per confidence bin: the bar is how often you were right, the tick is what the predictor said. */
function CalibrationStrip({ bins }: { bins: CalibrationBin[] }): JSX.Element {
  const W = 14;
  const H = 24;
  const GAP = 2;
  return (
    <svg className="calib" width={bins.length * (W + GAP) - GAP} height={H} role="img" aria-label="Calibration by bin">
      {bins.map((b, i) => {
        const x = i * (W + GAP);
        const tip =
          b.count === 0
            ? `${Math.round(b.lo * 100)}–${Math.round(b.hi * 100)}%: no answers`
            : `Predicted ${pct(b.mean_predicted)} · you were right ${pct(b.observed)} · ${b.count} answer${b.count === 1 ? '' : 's'}`;
        return (
          <g key={i}>
            <title>{tip}</title>
            <rect className="calib-cell" x={x} y={0} width={W} height={H} rx={3} />
            {b.observed !== null ? (
              <rect className="calib-bar" x={x} y={H - b.observed * H} width={W} height={b.observed * H} rx={3} />
            ) : null}
            {b.mean_predicted !== null ? (
              <rect className="calib-tick" x={x} y={Math.min(H - 2, Math.max(0, H - b.mean_predicted * H - 1))} width={W} height={2} />
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

export default function ModelScoreboard(): JSX.Element {
  const [data, setData] = useState<ModelEvalOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .modelEval()
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  if (error) return <p className="muted small">Couldn’t load the scoreboard: {error}</p>;
  if (!data) return <Spinner label="Loading scoreboard" />;
  const c = data.controller;
  return (
    <div className="scoreboard">
      <div className="field-label">How well Pólya predicts you</div>
      <p className="muted small">
        Before each graded answer Pólya predicts whether you’ll get it right. Lower log-loss and Brier are better; AUC 0.5 is chance, 1.0 is perfect.
        {data.n === 0
          ? ' No answers yet.'
          : data.enough_data
            ? ` Based on ${data.n} answers.`
            : ` Not enough answers yet (${data.n} of ${data.min_answers}), so these numbers are noisy.`}
      </p>
      {data.n > 0 ? (
        <table className={`dtable${data.enough_data ? '' : ' greyed'}`}>
          <thead>
            <tr>
              <th>Predictor</th>
              <th className="num">Log-loss</th>
              <th className="num">Brier</th>
              <th className="num">AUC</th>
              <th>Calibration</th>
            </tr>
          </thead>
          <tbody>
            {data.predictors.map((p) => (
              <tr key={p.name}>
                <td>
                  {p.label}
                  {p.baseline ? <span className="muted small"> · baseline</span> : null}
                </td>
                <td className="num">{fmt(p.log_loss, 3)}</td>
                <td className="num">{fmt(p.brier, 3)}</td>
                <td className="num">{fmt(p.auc, 2)}</td>
                <td>
                  <CalibrationStrip bins={p.calibration_bins} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {data.n > 0 ? (
        <p className="muted small">Calibration: one cell per 20% band of prediction; the bar is how often you were right, the line is what was predicted.</p>
      ) : null}
      <p className="muted small">
        Difficulty target {pct(c.target)} · recent success {c.recent_success === null ? '— (no answers yet)' : `${pct(c.recent_success)} over the last ${c.window_n}`}
        {c.last_summary ? ` · last change: ${c.last_summary}` : ''}
      </p>
    </div>
  );
}
