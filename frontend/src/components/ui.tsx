/** Legacy presentational primitives + formatting helpers used by the Advanced (instrument) panels and Details. */
import { useEffect, useRef, type ReactNode } from 'react';
import type { CueVector, NodeType, Outcome, SessionMode, SubMode } from '../types/harness';

// ------------------------------------------------------------------ palette
export const C = {
  bg: '#070a12',
  panel: '#0f172a',
  border: '#1e293b',
  text: '#f8fafc',
  muted: '#94a3b8',
  dim: '#64748b',
  indigo: '#6366f1',
  emerald: '#10b981',
  amber: '#f59e0b',
  cyan: '#06b6d4',
  rose: '#f43f5e',
  violet: '#a78bfa',
  crimson: '#dc2626',
  slate: '#334155',
};

const DOMAIN_COLORS: Record<string, string> = {
  'Measure-Theoretic Probability': C.indigo,
  'Transformers & Attention': C.emerald,
  'Reinforcement Learning': C.amber,
  'Linear Algebra & Functional Analysis': C.cyan,
  'Buggy Rules': C.rose,
};
const EXTRA_DOMAIN = ['#a78bfa', '#38bdf8', '#f472b6', '#84cc16', '#fb923c', '#2dd4bf'];

export function domainColor(domain: string, nodeType?: NodeType): string {
  if (nodeType === 'BUGGY_RULE') return C.rose;
  const known = DOMAIN_COLORS[domain];
  if (known) return known;
  let h = 0;
  for (let i = 0; i < domain.length; i++) h = (h * 31 + domain.charCodeAt(i)) >>> 0;
  return EXTRA_DOMAIN[h % EXTRA_DOMAIN.length];
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function mix(a: string, b: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(a);
  const [r2, g2, b2] = hexToRgb(b);
  const k = Math.max(0, Math.min(1, t));
  const r = Math.round(r1 + (r2 - r1) * k);
  const g = Math.round(g1 + (g2 - g1) * k);
  const bb = Math.round(b1 + (b2 - b1) * k);
  return `#${[r, g, bb].map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}
export function withAlpha(hex: string, a: number): string {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r},${g},${b},${a})`;
}

/** Rose (<0.35) -> Amber (0.55) -> Emerald (>=0.85) heatmap for P(L). */
export function masteryColor(p: number): string {
  if (p <= 0.35) return C.rose;
  if (p < 0.55) return mix(C.rose, C.amber, (p - 0.35) / 0.2);
  if (p < 0.85) return mix(C.amber, C.emerald, (p - 0.55) / 0.3);
  return C.emerald;
}

export const NODE_TYPE_GLYPH: Record<NodeType, string> = {
  AXIOM: '■',
  PROPOSITION: '●',
  MOVE: '▲',
  COUNTEREXAMPLE: '✕',
  INTUITION: '⬢',
  BUGGY_RULE: '◆',
};

export const OUTCOME_COLOR: Record<Outcome, string> = {
  SOLVED_CLEAN: C.emerald,
  SOLVED_WITH_HINTS: '#34d399',
  PARTIAL: C.amber,
  FAILED: C.rose,
  HIGH_CONFIDENCE_ERROR: C.crimson,
  EXPLORATION_LOGGED: C.indigo,
};

export function modeLabel(mode: SessionMode, sub: SubMode): string {
  switch (mode) {
    case 'PROBE':
      return 'Probe → Teach';
    case 'PRODUCTIVE_FAILURE':
      return 'Productive Failure → Teach';
    case 'TEACH':
      return 'Teach';
    case 'PRACTICE':
      return 'Adaptive Practice';
    case 'REFEREE_DUEL':
      return sub === 'FEYNMAN_STUDENT' ? 'Feynman Student Duel' : 'Proof-Referee Duel';
  }
}

export const CUE_LABELS: Record<keyof CueVector, string> = {
  cue_symbolic: 'Symbolic',
  cue_disguised_notation: 'Disguised Notation',
  cue_geometric: 'Geometric',
  cue_computational: 'Computational',
  cue_adversarial: 'Adversarial',
};

// ------------------------------------------------------------------ formatting
export const pct = (x: number, d = 0): string => `${(x * 100).toFixed(d)}%`;
export const fx = (x: number | null | undefined, d = 2): string =>
  x === null || x === undefined || Number.isNaN(x) ? '—' : x.toFixed(d);

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number): string => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

/** `harness-cli due` style relative due string. */
export function dueRelative(days: number): string {
  if (days <= 0) return `OVERDUE ${Math.abs(days).toFixed(1)}d`;
  if (days < 1) return `in ${(days * 24).toFixed(1)}h`;
  return `in ${days.toFixed(1)}d`;
}

// ------------------------------------------------------------------ primitives
export function Bar({ value, color, title }: { value: number; color?: string; title?: string }): JSX.Element {
  const v = Math.max(0, Math.min(1, value));
  return (
    <span className="bar" title={title}>
      <span className="bar-fill" style={{ width: `${v * 100}%`, background: color ?? masteryColor(v) }} />
    </span>
  );
}

export function Kv({ k, v, mono = true, title }: { k: ReactNode; v: ReactNode; mono?: boolean; title?: string }): JSX.Element {
  return (
    <div className="kv" title={title}>
      <span className="kv-k">{k}</span>
      <span className={`kv-v${mono ? ' mono' : ''}`}>{v}</span>
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide,
  footer,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
  footer?: ReactNode;
}): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey, true);
    ref.current?.focus();
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onClose]);
  return (
    <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? ' wide' : ''}`} role="dialog" aria-modal="true" tabIndex={-1} ref={ref}>
        <div className="modal-head">
          <div className="modal-title">{title}</div>
          <button className="btn ghost icon" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-foot">{footer}</div> : null}
      </div>
    </div>
  );
}

/** 5D cue-breadth pentagon (radar) in SVG. */
export function CuePentagon({ cues, size = 168 }: { cues: CueVector; size?: number }): JSX.Element {
  const keys = Object.keys(CUE_LABELS) as (keyof CueVector)[];
  const cx = size / 2;
  const cy = size / 2 + 4;
  const R = size / 2 - 26;
  const pt = (i: number, r: number): [number, number] => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const ring = (f: number): string => keys.map((_, i) => pt(i, R * f).join(',')).join(' ');
  const poly = keys.map((k, i) => pt(i, R * Math.max(0.02, Math.min(1, cues[k]))).join(',')).join(' ');
  return (
    <svg className="pentagon" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="5D cue breadth">
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon key={f} points={ring(f)} fill="none" stroke={C.border} strokeWidth={1} />
      ))}
      {keys.map((_, i) => {
        const [x, y] = pt(i, R);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={C.border} />;
      })}
      <polygon points={poly} fill={withAlpha(C.cyan, 0.22)} stroke={C.cyan} strokeWidth={1.5} />
      {keys.map((k, i) => {
        const [x, y] = pt(i, R * Math.max(0.02, Math.min(1, cues[k])));
        return <circle key={k} cx={x} cy={y} r={2.5} fill={C.cyan} />;
      })}
      {keys.map((k, i) => {
        const [x, y] = pt(i, R + 14);
        return (
          <text key={k} x={x} y={y} fill={C.muted} fontSize={9} textAnchor="middle" dominantBaseline="middle" fontFamily="var(--mono)">
            {CUE_LABELS[k].split(' ')[0].slice(0, 6).toUpperCase()}
          </text>
        );
      })}
    </svg>
  );
}

export function Spinner(): JSX.Element {
  return <span className="spinner" aria-hidden="true" />;
}

export function isTypingTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  const tag = t.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable;
}
