/**
 * Right pane (ARCHITECTURE_SPEC §6.2): live vertical dependency tree of the active session.
 * Goal at the top, prerequisites below (logical depth flows upward like the hypergraph), DEDUCTION arcs between
 * plan nodes, Δ-branching remedial sub-nodes spliced by the step-size controller, the Step Velocity Δ gauge, and
 * the session's outcome timeline.
 */
import { useMemo } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { PlanItem, PlanStatus } from '../types/harness';
import { C, OUTCOME_COLOR, fx, masteryColor, withAlpha } from './ui';

const STATUS_COLOR: Record<PlanStatus, string> = {
  pending: C.slate,
  active: C.cyan,
  done: C.emerald,
  probed_mastered: C.emerald,
  probed_unmastered: C.rose,
  skipped: '#475569',
};

const ROW = 42;
const X_MAIN = 26;
const X_REM = 54;

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

export function DeltaGauge({ delta }: { delta: number }): JSX.Element {
  const W = 232;
  const x = (v: number): number => 10 + ((v - 0.5) / 2) * (W - 20);
  const d = Math.max(0.5, Math.min(2.5, delta));
  return (
    <div className="delta-gauge">
      <div className="delta-head">
        <span>Step Velocity Δ</span>
        <span className="mono delta-val" style={{ color: d <= 0.5 ? C.amber : d >= 2 ? C.emerald : C.cyan }}>
          {d.toFixed(1)}
        </span>
      </div>
      <svg width={W} height={34} viewBox={`0 0 ${W} 34`} role="img" aria-label={`Delta ${d}`}>
        <defs>
          <linearGradient id="dg" x1="0" x2="1">
            <stop offset="0" stopColor={C.amber} />
            <stop offset="0.25" stopColor={C.cyan} />
            <stop offset="1" stopColor={C.emerald} />
          </linearGradient>
        </defs>
        <rect x={10} y={10} width={W - 20} height={5} rx={2.5} fill="url(#dg)" opacity={0.35} />
        <rect x={10} y={10} width={Math.max(0, x(d) - 10)} height={5} rx={2.5} fill="url(#dg)" />
        {[0.5, 1, 1.5, 2, 2.5].map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={17} y2={21} stroke={C.dim} />
            <text x={x(t)} y={31} fill={C.dim} fontSize={9} textAnchor="middle" fontFamily="var(--mono)">
              {t.toFixed(1)}
            </text>
          </g>
        ))}
        <path d={`M ${x(d)} 8 l -4 -6 h 8 z`} fill={C.text} />
      </svg>
      <div className="dim small">
        {d <= 0.5
          ? 'Remedial pace: one micro-implication per step.'
          : d >= 2
            ? 'High leap: trivial bridges compressed, synthesis predictions.'
            : 'Nominal pace. Two clean, confident, high-quality steps raise Δ by 0.5.'}
      </div>
    </div>
  );
}

export default function DependencyMiniMap(): JSX.Element {
  const st = useHarnessStore((s) => s.sessionState);
  const graph = useHarnessStore((s) => s.graph);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);

  const plan: PlanItem[] = st?.session.dependency_plan ?? [];
  const activeIds = new Set(st?.active_step.target_node_ids ?? []);
  const nodeById = useMemo(() => new Map((graph?.nodes ?? []).map((n) => [n.id, n])), [graph]);

  // goal on top: reverse plan order
  const rows = useMemo(() => [...plan].reverse(), [plan]);
  const rowOf = useMemo(() => {
    const m = new Map<string, number>();
    rows.forEach((p, i) => {
      if (!m.has(p.node_id)) m.set(p.node_id, i);
    });
    return m;
  }, [rows]);

  const arcs = useMemo(() => {
    const out: { from: number; to: number; type: string }[] = [];
    for (const e of graph?.hyperedges ?? []) {
      if (e.edge_type !== 'DEDUCTION' && e.edge_type !== 'CUE_TRIGGER') continue;
      const to = rowOf.get(e.conclusion_node_id);
      if (to === undefined) continue;
      for (const p of e.premise_node_ids) {
        const from = rowOf.get(p);
        if (from !== undefined && from !== to) out.push({ from, to, type: e.edge_type });
      }
    }
    return out;
  }, [graph, rowOf]);

  if (!st) {
    return (
      <aside className="minimap">
        <div className="panel-title">Session dependency tree</div>
        <div className="dim small pad">Start or load a session to see its live prerequisite plan.</div>
      </aside>
    );
  }

  const H = Math.max(ROW, rows.length * ROW) + 12;
  const W = 268;
  const xOf = (p: PlanItem): number => (p.remedial ? X_REM : X_MAIN);
  const yOf = (i: number): number => 18 + i * ROW;
  const traces = st.traces;

  return (
    <aside className="minimap">
      <div className="panel-title">
        <span>Session dependency tree</span>
        <span className="mono dim">
          {plan.filter((p) => p.status === 'done' || p.status === 'probed_mastered').length}/{plan.length}
        </span>
      </div>
      <div className="goal-line small">
        <span className="dim">goal</span> {st.session.target_goal}
      </div>
      <DeltaGauge delta={st.session.step_velocity_delta} />
      <div className="tree-scroll">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="tree">
          {/* sequential spine between main nodes */}
          {rows.map((p, i) => {
            if (i === 0 || p.remedial) return null;
            let j = i - 1;
            while (j >= 0 && rows[j].remedial) j--;
            if (j < 0) return null;
            return <line key={`sp${i}`} x1={X_MAIN} y1={yOf(j) + 7} x2={X_MAIN} y2={yOf(i) - 7} stroke={C.border} strokeWidth={2} />;
          })}
          {/* Δ-branch: remedial node feeds the plan item it was spliced before (the row above it) */}
          {rows.map((p, i) => {
            if (!p.remedial) return null;
            let j = i - 1;
            while (j >= 0 && rows[j].remedial) j--;
            const y2 = j >= 0 ? yOf(j) : yOf(i) - ROW;
            return (
              <path
                key={`rb${i}`}
                d={`M ${X_REM} ${yOf(i) - 7} C ${X_REM} ${y2 + 14}, ${X_MAIN + 10} ${y2 + 6}, ${X_MAIN + 7} ${y2 + 3}`}
                fill="none"
                stroke={C.amber}
                strokeDasharray="4 3"
                strokeWidth={1.5}
              />
            );
          })}
          {/* DEDUCTION / CUE arcs from the hypergraph */}
          {arcs.map((a, k) => {
            const y1 = yOf(a.from);
            const y2 = yOf(a.to);
            const bend = 8 + Math.min(16, Math.abs(a.from - a.to) * 4);
            return (
              <path
                key={`arc${k}`}
                d={`M ${X_MAIN - 7} ${y1} C ${X_MAIN - 7 - bend} ${y1}, ${X_MAIN - 7 - bend} ${y2}, ${X_MAIN - 8} ${y2}`}
                fill="none"
                stroke={a.type === 'DEDUCTION' ? withAlpha(C.indigo, 0.7) : withAlpha(C.cyan, 0.6)}
                strokeDasharray={a.type === 'CUE_TRIGGER' ? '1 3' : undefined}
                strokeWidth={1.2}
                markerEnd="url(#mm-arrow)"
              />
            );
          })}
          <defs>
            <marker id="mm-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="5" markerHeight="5" orient="auto">
              <path d="M0,0 L6,3 L0,6 z" fill={C.indigo} />
            </marker>
          </defs>
          {rows.map((p, i) => {
            const n = nodeById.get(p.node_id);
            const active = p.status === 'active' || activeIds.has(p.node_id);
            const col = active ? C.cyan : STATUS_COLOR[p.status];
            const x = xOf(p);
            const y = yOf(i);
            const pl = n?.bkt_p_mastery ?? 0;
            return (
              <g key={`${p.node_id}-${i}`} className="tree-row" onClick={() => focus(p.node_id)} style={{ cursor: 'pointer' }}>
                <title>
                  {`${p.title}\nstatus: ${p.status}${p.remedial ? `\nremedial: ${p.spliced_reason}` : ''}\nP(L) ${fx(pl)} · depth ${p.depth}`}
                </title>
                <rect x={0} y={y - ROW / 2 + 2} width={W} height={ROW - 4} fill={active ? withAlpha(C.cyan, 0.07) : 'transparent'} rx={4} />
                {active ? <circle cx={x} cy={y} r={11} fill="none" stroke={C.cyan} strokeOpacity={0.5} className="pulse-ring" /> : null}
                <circle
                  cx={x}
                  cy={y}
                  r={7}
                  fill={p.status === 'probed_mastered' || p.status === 'pending' ? C.panel : col}
                  stroke={col}
                  strokeWidth={2}
                  strokeDasharray={p.remedial ? '2 2' : undefined}
                />
                <text
                  x={x + 14}
                  y={y - 2}
                  fill={p.status === 'skipped' ? C.dim : C.text}
                  fontSize={11.5}
                  textDecoration={p.status === 'skipped' ? 'line-through' : undefined}
                >
                  {truncate(p.title, p.remedial ? 27 : 31)}
                </text>
                <text x={x + 14} y={y + 11} fill={C.dim} fontSize={9.5} fontFamily="var(--mono)">
                  {p.remedial ? '⤷ remedial · ' : ''}d{p.depth} · {p.status.replace('_', ' ')}
                </text>
                <rect x={W - 44} y={y + 4} width={36} height={3} fill={C.border} rx={1.5} />
                <rect x={W - 44} y={y + 4} width={36 * Math.max(0, Math.min(1, pl))} height={3} fill={masteryColor(pl)} rx={1.5} />
                <text x={W - 8} y={y - 1} fill={masteryColor(pl)} fontSize={9.5} textAnchor="end" fontFamily="var(--mono)">
                  {fx(pl)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      {plan.some((p) => p.remedial) ? (
        <div className="remedial-list small">
          {plan
            .filter((p) => p.remedial)
            .map((p) => (
              <div key={p.node_id} className="remedial-item">
                <span className="tag amber mono">Δ-SPLICE</span> {p.title}
                {p.spliced_reason ? <span className="dim"> — {p.spliced_reason}</span> : null}
              </div>
            ))}
        </div>
      ) : null}
      <div className="timeline">
        <div className="panel-sub">Outcome timeline · {traces.length} traces</div>
        <div className="timeline-cells">
          {traces.length === 0 ? <span className="dim small">no graded steps yet</span> : null}
          {traces.map((t) => (
            <span
              key={t.id}
              className="tl-cell"
              style={{ background: OUTCOME_COLOR[t.outcome] }}
              title={`${t.phase} step ${t.step_index + 1}: ${t.outcome}\nconf ${Math.round(t.confidence_slider * 100)}% · q ${fx(t.trace_quality_score)} · Brier ${fx(t.brier_score, 3)}`}
            />
          ))}
        </div>
      </div>
    </aside>
  );
}
