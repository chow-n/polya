/**
 * Advanced telemetry strip (legacy status pills, shown only when Settings → Advanced telemetry is on):
 * scratch.tex live-sync pill (+ view/edit) · Bjork window counter · due · hypercorrection badge ·
 * Brier calibration badge (Murphy 1973 decomposition popover + reliability diagram) · LLM engine + WebSocket latency.
 * Also exports the scratch.tex editor used by Settings → Workspace.
 */
import { useEffect, useRef, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { CalibrationOut } from '../types/harness';
import { C, Kv, Modal, fmtDateTime, fx, pct, timeAgo, withAlpha } from './ui';

export default function TelemetryPills(): JSX.Element {
  const stats = useHarnessStore((s) => s.stats);
  const wsStatus = useHarnessStore((s) => s.wsStatus);
  const wsLatency = useHarnessStore((s) => s.wsLatencyMs);
  const llmEngine = useHarnessStore((s) => s.llmEngine);
  const scratch = useHarnessStore((s) => s.scratch);
  const scratchEventAt = useHarnessStore((s) => s.scratchEventAt);
  const openModal = useHarnessStore((s) => s.openModal);
  const backendOk = useHarnessStore((s) => s.backendOk);
  const [calOpen, setCalOpen] = useState(false);
  const calRef = useRef<HTMLDivElement>(null);
  const [, forceTick] = useState(0);

  // re-render every 5 s so "synced Ns ago" stays truthful
  useEffect(() => {
    const t = window.setInterval(() => forceTick((x) => x + 1), 5000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    if (!calOpen) return;
    const onDown = (e: MouseEvent): void => {
      if (calRef.current && !calRef.current.contains(e.target as Node)) setCalOpen(false);
    };
    window.addEventListener('mousedown', onDown);
    return () => window.removeEventListener('mousedown', onDown);
  }, [calOpen]);

  const syncedIso = stats?.scratch_synced_at ?? scratch?.modified_at ?? null;
  const recentlySynced = scratchEventAt !== null && Date.now() - scratchEventAt < 4000;
  const cal = stats?.calibration;
  const calColor =
    !cal || cal.label === 'NO_DATA'
      ? C.dim
      : cal.label === 'WELL_CALIBRATED'
        ? C.emerald
        : cal.label === 'OVERCONFIDENT'
          ? C.rose
          : C.amber;

  return (
    <div className="pills-strip legacy-skin" aria-label="Advanced telemetry">
      <div className="pills">
        <button
          className={`pill sync${wsStatus === 'open' ? ' live' : ''}${recentlySynced ? ' flash' : ''}`}
          onClick={() => openModal({ kind: 'scratch' })}
          title={`workspace/scratch.tex live sync — click to view/edit.\nLast change: ${fmtDateTime(syncedIso)}`}
        >
          <span className="dot" />
          <span className="mono">scratch.tex</span>
          <span className="pill-sub mono">{syncedIso ? timeAgo(syncedIso) : wsStatus === 'open' ? 'watching' : 'offline'}</span>
        </button>

        <div className="pill" title="Nodes with retrievability R(t) in Bjork's desirable-difficulty window [0.70, 0.85]">
          <span className="pill-k">Bjork 0.70–0.85</span>
          <span className="pill-v mono" style={{ color: C.cyan }}>
            {stats ? stats.bjork_window_count : '—'}
          </span>
        </div>

        <div className="pill" title="Nodes due now at desired retention 0.90">
          <span className="pill-k">Due</span>
          <span className="pill-v mono" style={{ color: stats && stats.due_count > 0 ? C.amber : C.muted }}>
            {stats ? stats.due_count : '—'}
          </span>
        </div>

        <div
          className={`pill${stats && stats.hypercorrection_count > 0 ? ' alert' : ''}`}
          title="Hypercorrection flags: high-confidence (≥75%) errors awaiting clean resolution (1.25× stability bonus)"
        >
          <span className="pill-k">Hypercorrection</span>
          <span className="pill-v mono" style={{ color: stats && stats.hypercorrection_count > 0 ? C.rose : C.muted }}>
            {stats ? stats.hypercorrection_count : '—'}
          </span>
        </div>

        <div className="pill-wrap" ref={calRef}>
          <button
            className="pill"
            onClick={() => setCalOpen((v) => !v)}
            title="Metacognitive calibration (mean Brier score). Click for the Murphy decomposition."
            aria-expanded={calOpen}
          >
            <span className="pill-k">Brier</span>
            <span className="pill-v mono">{cal ? fx(cal.mean_brier, 3) : '—'}</span>
            <span className="pill-tag mono" style={{ color: calColor, borderColor: withAlpha(calColor, 0.5) }}>
              {calLabelShort(cal)}
            </span>
          </button>
          {calOpen && cal ? <CalibrationPopover cal={cal} meanMastery={stats?.mean_mastery ?? 0} /> : null}
        </div>

        <div className="pill" title="LLM engine · WebSocket">
          <span className={`dot ws-${backendOk === false ? 'closed' : wsStatus}`} />
          <span className="pill-k">LLM</span>
          <span className="pill-v mono engine">{llmEngine}</span>
          <span className="pill-sub mono">{wsStatus === 'open' && wsLatency !== null ? `${wsLatency}ms` : wsStatus}</span>
        </div>
      </div>
    </div>
  );
}

function calLabelShort(cal: CalibrationOut | undefined): string {
  if (!cal) return '—';
  switch (cal.label) {
    case 'NO_DATA':
      return 'NO DATA';
    case 'WELL_CALIBRATED':
      return 'CALIBRATED';
    case 'OVERCONFIDENT':
      return `OVER +${pct(Math.abs(cal.overconfidence))}`;
    case 'UNDERCONFIDENT':
      return `UNDER −${pct(Math.abs(cal.overconfidence))}`;
  }
}

function CalibrationPopover({ cal, meanMastery }: { cal: CalibrationOut; meanMastery: number }): JSX.Element {
  const recomposed = cal.reliability - cal.resolution + cal.uncertainty;
  const W = 220;
  const H = 150;
  const pad = 22;
  const sx = (x: number): number => pad + x * (W - pad - 8);
  const sy = (y: number): number => H - pad - y * (H - pad - 8);
  const maxCount = Math.max(1, ...cal.bins.map((b) => b.count));
  return (
    <div className="popover cal-pop" role="dialog">
      <div className="pop-title">Metacognitive calibration · Murphy (1973) decomposition</div>
      <div className="mono cal-eq">
        BS = REL − RES + UNC
        <br />
        {fx(cal.mean_brier, 4)} ≈ {fx(cal.reliability, 4)} − {fx(cal.resolution, 4)} + {fx(cal.uncertainty, 4)}
        <span className="dim"> (= {fx(recomposed, 4)})</span>
      </div>
      <div className="cal-grid">
        <Kv k="Reliability (↓ better)" v={fx(cal.reliability, 4)} title="Mean squared gap between stated confidence and observed accuracy per confidence bin" />
        <Kv k="Resolution (↑ better)" v={fx(cal.resolution, 4)} title="How much bin accuracies vary from the base rate — ability to discriminate knowns from unknowns" />
        <Kv k="Uncertainty" v={fx(cal.uncertainty, 4)} title="Base-rate variance ā(1−ā); not under the learner's control" />
        <Kv k="n judgements" v={cal.n} />
        <Kv k="Mean confidence" v={pct(cal.mean_confidence, 1)} />
        <Kv k="Accuracy" v={pct(cal.accuracy, 1)} />
        <Kv
          k="Over/under-confidence"
          v={<span style={{ color: cal.overconfidence > 0.05 ? C.rose : cal.overconfidence < -0.05 ? C.amber : C.emerald }}>{cal.overconfidence >= 0 ? '+' : ''}{pct(cal.overconfidence, 1)}</span>}
        />
        <Kv k="Mean P(L) over graph" v={pct(meanMastery, 1)} />
      </div>
      <svg width={W} height={H} className="reliability" role="img" aria-label="Reliability diagram">
        <rect x={pad} y={8} width={W - pad - 8} height={H - pad - 8} fill="none" stroke={C.border} />
        <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} stroke={C.slate} strokeDasharray="3 3" />
        {cal.bins
          .filter((b) => b.count > 0)
          .map((b, i) => (
            <g key={i}>
              <line x1={sx(b.mean_confidence)} y1={sy(b.mean_confidence)} x2={sx(b.mean_confidence)} y2={sy(b.accuracy)} stroke={withAlpha(C.rose, 0.5)} />
              <circle cx={sx(b.mean_confidence)} cy={sy(b.accuracy)} r={2.5 + 4 * (b.count / maxCount)} fill={withAlpha(C.cyan, 0.75)} stroke={C.cyan}>
                <title>{`conf ${pct(b.mean_confidence)} → acc ${pct(b.accuracy)} (n=${b.count})`}</title>
              </circle>
            </g>
          ))}
        <text x={pad} y={H - 6} fill={C.dim} fontSize={9} fontFamily="var(--mono)">
          confidence →
        </text>
        <text x={4} y={14} fill={C.dim} fontSize={9} fontFamily="var(--mono)">
          acc
        </text>
      </svg>
      <div className="pop-foot">
        {cal.label === 'NO_DATA'
          ? 'No graded judgements yet. Every confidence slider you submit feeds this.'
          : cal.label === 'OVERCONFIDENT'
            ? 'Stated confidence exceeds accuracy. Errors at ≥75% confidence raise hypercorrection flags.'
            : cal.label === 'UNDERCONFIDENT'
              ? 'You know more than you claim — raise confidence when the structure is clear.'
              : 'Confidence tracks accuracy. Keep resolution high by discriminating knowns from unknowns.'}
      </div>
    </div>
  );
}

export function ScratchModal({ onClose }: { onClose: () => void }): JSX.Element {
  const scratch = useHarnessStore((s) => s.scratch);
  const writeScratch = useHarnessStore((s) => s.writeScratch);
  const refreshScratch = useHarnessStore((s) => s.refreshScratch);
  const busy = useHarnessStore((s) => s.busy.scratch);
  const [content, setContent] = useState(scratch?.content ?? '');
  const [dirty, setDirty] = useState(false);
  const [copied, setCopied] = useState(false);
  const cmd = 'nvim workspace/scratch.tex';

  useEffect(() => {
    void refreshScratch();
  }, [refreshScratch]);
  // follow external saves unless the user is mid-edit
  useEffect(() => {
    if (!dirty && scratch) setContent(scratch.content);
  }, [scratch, dirty]);

  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Modal
      title={
        <>
          <span className="mono">{scratch?.path ?? 'workspace/scratch.tex'}</span>
          <span className="dim"> · modified {fmtDateTime(scratch?.modified_at)}</span>
        </>
      }
      onClose={onClose}
      wide
      footer={
        <>
          <button className="btn ghost" onClick={() => void copy()} title="Copy terminal command">
            <span className="mono">$ {cmd}</span> {copied ? '✓ copied' : '⧉'}
          </button>
          <span className="spacer" />
          {dirty ? <span className="dim">unsaved changes</span> : <span className="dim">in sync with disk</span>}
          <button
            className="btn ghost"
            onClick={() => {
              setDirty(false);
              setContent(scratch?.content ?? '');
            }}
            disabled={!dirty}
          >
            Revert
          </button>
          <button
            className="btn primary"
            disabled={!dirty || busy}
            onClick={() => {
              void writeScratch(content).then(() => setDirty(false));
            }}
          >
            {busy ? 'Saving…' : 'Save to disk'}
          </button>
        </>
      }
    >
      <textarea
        className="code-editor"
        spellCheck={false}
        value={content}
        onChange={(e) => {
          setContent(e.target.value);
          setDirty(true);
        }}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 's') {
            e.preventDefault();
            void writeScratch(content).then(() => setDirty(false));
          }
        }}
      />
      <div className="hint-line">
        Saved edits are broadcast to every client via the <span className="mono">scratch_update</span> WebSocket event; edits made in
        the terminal appear here live. Cmd/Ctrl+S saves.
      </div>
    </Modal>
  );
}
