/**
 * Epistemic Hypergraph Visualizer (ARCHITECTURE_SPEC §6.3) — hand-written HTML5 Canvas 2D renderer, no graph library.
 *
 *  - smooth pan (drag background), zoom (wheel, about the cursor), node dragging, double-click to fit
 *  - hover highlights the upstream (ancestors) / downstream (descendants) Markov blanket over directed edges
 *  - "Lock Y-Axis to Logical Depth": y = H − depth·130 px with spring relaxation along X; OFF → force-directed clusters
 *  - 4 colour modes: Domain Clusters · Bayesian Mastery P(L) · FSRS Retrievability & Bjork Window · Hypercorrection & Buggy Rules
 *  - hyperedge semantics: DEDUCTION (premises → ∧ diamond hub → bold arrow), CONTRASTIVE (dashed amber ⟷ with ⊥),
 *    ISOMORPHISM (glowing violet double line with ≅), CUE_TRIGGER (dotted cyan arrow)
 *  - slide-over inspector: KaTeX statement / intuition / proof sketch, BKT + FSRS stats, next-due (`harness-cli due` style),
 *    5D cue pentagon, premise chains, conclusions, contrastive peers, and the three session-launch actions
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useHarnessStore, type ColorMode } from '../store/useHarnessStore';
import type { EdgeType, GraphOut, HyperedgeOut, NodeOut, NodeType } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import {
  Bar,
  C,
  CUE_LABELS,
  CuePentagon,
  DOMAIN_COLORS,
  Kv,
  NODE_TYPE_GLYPH,
  OUTCOME_COLOR,
  Spinner,
  domainColor,
  dueRelative,
  fmtDateTime,
  fx,
  masteryColor,
  pct,
  timeAgo,
  withAlpha,
} from './ui';

// =================================================================== model
interface SimNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned: boolean;
}
interface Cam {
  x: number;
  y: number;
  k: number;
}
type Hit = { kind: 'node'; id: string } | { kind: 'edge'; id: string } | null;

const LAYER = 130;
const MIN_LAYER_GAP = 150; // px between neighbours in one depth layer (label width)
const NODE_R: Record<NodeType, number> = {
  AXIOM: 15,
  PROPOSITION: 16,
  MOVE: 15,
  COUNTEREXAMPLE: 14,
  INTUITION: 15,
  BUGGY_RULE: 14,
};
const EDGE_COLOR: Record<EdgeType, string> = {
  DEDUCTION: C.indigo,
  CONTRASTIVE: C.amber,
  ISOMORPHISM: C.violet,
  CUE_TRIGGER: C.cyan,
};
const COLOR_MODES: { id: ColorMode; label: string; title: string }[] = [
  { id: 'domain', label: '1. Domain Clusters', title: 'Colour by mathematical / CS domain' },
  { id: 'mastery', label: '2. Bayesian Mastery P(L)', title: 'Rose (<0.35) → Amber (0.55) → Emerald (≥0.85)' },
  { id: 'fsrs', label: '3. FSRS Retrievability & Bjork Window', title: 'Cyan ring = R∈[0.70,0.85]; slate-emerald = fresh; red pulse = decaying' },
  { id: 'hypercorrection', label: '4. Hypercorrection & Buggy Rules', title: 'Spotlight high-confidence errors and attached misconceptions' },
];
const SLATE_EMERALD = '#3d7a68';

interface Derived {
  byId: Map<string, NodeOut>;
  parents: Map<string, Set<string>>;
  children: Map<string, Set<string>>;
  buggyLinks: [string, string][];
  clusters: string[];
  maxDepth: number;
}

function derive(graph: GraphOut): Derived {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const parents = new Map<string, Set<string>>();
  const children = new Map<string, Set<string>>();
  const add = (m: Map<string, Set<string>>, k: string, v: string): void => {
    if (!m.has(k)) m.set(k, new Set());
    m.get(k)?.add(v);
  };
  const buggyLinks: [string, string][] = [];
  for (const e of graph.hyperedges) {
    if (e.edge_type === 'DEDUCTION' || e.edge_type === 'CUE_TRIGGER') {
      for (const p of e.premise_node_ids) {
        if (!byId.has(p) || !byId.has(e.conclusion_node_id)) continue;
        add(parents, e.conclusion_node_id, p);
        add(children, p, e.conclusion_node_id);
      }
    }
    const ends = [...e.premise_node_ids, e.conclusion_node_id].filter((id) => byId.has(id));
    const bugs = ends.filter((id) => byId.get(id)?.node_type === 'BUGGY_RULE');
    for (const b of bugs) for (const o of ends) if (o !== b && byId.get(o)?.node_type !== 'BUGGY_RULE') buggyLinks.push([o, b]);
  }
  const clusters = [...new Set(graph.nodes.map((n) => (n.node_type === 'BUGGY_RULE' ? 'Buggy Rules' : n.domain_cluster)))].sort();
  const maxDepth = Math.max(0, ...graph.nodes.map((n) => n.logical_depth));
  return { byId, parents, children, buggyLinks, clusters, maxDepth };
}

function reach(start: string, adj: Map<string, Set<string>>): Set<string> {
  const seen = new Set<string>();
  const stack = [...(adj.get(start) ?? [])];
  while (stack.length) {
    const v = stack.pop() as string;
    if (seen.has(v)) continue;
    seen.add(v);
    adj.get(v)?.forEach((w) => stack.push(w));
  }
  seen.delete(start);
  return seen;
}

function clusterOf(n: NodeOut): string {
  return n.node_type === 'BUGGY_RULE' ? 'Buggy Rules' : n.domain_cluster;
}

// =================================================================== physics
function tick(sim: Map<string, SimNode>, graph: GraphOut, d: Derived, depthLock: boolean, alpha: number): void {
  const nodes = [...sim.values()];
  const H = d.maxDepth * LAYER;
  const clusterIdx = new Map(d.clusters.map((c, i) => [c, i]));
  // cluster centroids
  const cent = new Map<string, { x: number; y: number; n: number }>();
  for (const s of nodes) {
    const n = d.byId.get(s.id);
    if (!n) continue;
    const c = clusterOf(n);
    const v = cent.get(c) ?? { x: 0, y: 0, n: 0 };
    v.x += s.x;
    v.y += s.y;
    v.n += 1;
    cent.set(c, v);
  }
  cent.forEach((v) => {
    v.x /= v.n;
    v.y /= v.n;
  });

  // pairwise repulsion
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j++) {
      const b = nodes[j];
      let dx = a.x - b.x;
      let dy = a.y - b.y;
      if (dx === 0 && dy === 0) {
        dx = Math.random() - 0.5;
        dy = Math.random() - 0.5;
      }
      if (depthLock) {
        // only same/adjacent layers push each other, and only along X
        if (Math.abs(dy) > LAYER * 0.75) continue;
        const adx = Math.max(12, Math.abs(dx));
        const f = Math.min(8, 3200 / (adx * adx)) * alpha;
        const sx = Math.sign(dx) || 1;
        a.vx += sx * f;
        b.vx -= sx * f;
      } else {
        const d2 = Math.max(400, dx * dx + dy * dy);
        const dist = Math.sqrt(d2);
        const f = Math.min(10, 11000 / d2) * alpha;
        a.vx += (dx / dist) * f;
        a.vy += (dy / dist) * f;
        b.vx -= (dx / dist) * f;
        b.vy -= (dy / dist) * f;
      }
    }
  }

  // edge springs
  for (const e of graph.hyperedges) {
    const c = sim.get(e.conclusion_node_id);
    if (!c) continue;
    for (const pid of e.premise_node_ids) {
      const p = sim.get(pid);
      if (!p) continue;
      const dx = c.x - p.x;
      const dy = c.y - p.y;
      if (depthLock) {
        const k = (e.edge_type === 'DEDUCTION' ? 0.03 : e.edge_type === 'ISOMORPHISM' ? 0.006 : 0.012) * alpha;
        p.vx += dx * k;
        c.vx -= dx * k;
      } else {
        const rest = e.edge_type === 'ISOMORPHISM' ? 220 : e.edge_type === 'CONTRASTIVE' ? 130 : 150;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const k = (e.edge_type === 'ISOMORPHISM' ? 0.006 : 0.02) * alpha;
        const f = (dist - rest) * k;
        p.vx += (dx / dist) * f;
        p.vy += (dy / dist) * f;
        c.vx -= (dx / dist) * f;
        c.vy -= (dy / dist) * f;
      }
    }
  }

  // cluster cohesion, layout anchors, integration
  for (const s of nodes) {
    const n = d.byId.get(s.id);
    if (!n) continue;
    const cc = cent.get(clusterOf(n));
    const ci = clusterIdx.get(clusterOf(n)) ?? 0;
    if (depthLock) {
      const lane = (ci - (d.clusters.length - 1) / 2) * 260;
      s.vx += (lane - s.x) * 0.0035 * alpha;
      if (cc) s.vx += (cc.x - s.x) * 0.004 * alpha;
      s.vx += -s.x * 0.0008 * alpha;
      if (!s.pinned) {
        const ty = H - n.logical_depth * LAYER;
        s.y += (ty - s.y) * 0.2;
        s.vy = 0;
      }
    } else {
      if (cc) {
        s.vx += (cc.x - s.x) * 0.008 * alpha;
        s.vy += (cc.y - s.y) * 0.008 * alpha;
      }
      s.vx += -s.x * 0.002 * alpha;
      s.vy += (H / 2 - s.y) * 0.002 * alpha;
    }
    if (s.pinned) {
      s.vx = 0;
      s.vy = 0;
      continue;
    }
    s.vx *= 0.82;
    s.vy *= 0.82;
    s.vx = Math.max(-40, Math.min(40, s.vx));
    s.vy = Math.max(-40, Math.min(40, s.vy));
    s.x += s.vx;
    if (!depthLock) s.y += s.vy;
  }

  // depth lock: hard minimum horizontal gap inside each layer so labels never collide
  if (depthLock) {
    const layers = new Map<number, SimNode[]>();
    for (const s of nodes) {
      const n = d.byId.get(s.id);
      if (!n) continue;
      const arr = layers.get(n.logical_depth) ?? [];
      arr.push(s);
      layers.set(n.logical_depth, arr);
    }
    layers.forEach((arr) => {
      arr.sort((a, b) => a.x - b.x);
      const before = arr.reduce((acc, s) => acc + s.x, 0) / arr.length;
      for (let i = 1; i < arr.length; i++) {
        if (arr[i].x - arr[i - 1].x < MIN_LAYER_GAP && !arr[i].pinned) arr[i].x = arr[i - 1].x + MIN_LAYER_GAP;
      }
      const shift = before - arr.reduce((acc, s) => acc + s.x, 0) / arr.length;
      for (const s of arr) if (!s.pinned) s.x += shift;
    });
  }
}

// =================================================================== drawing helpers
function shapePath(ctx: CanvasRenderingContext2D, type: NodeType, x: number, y: number, r: number): void {
  ctx.beginPath();
  switch (type) {
    case 'AXIOM': {
      const s = r * 0.9;
      const rr = 3;
      ctx.moveTo(x - s + rr, y - s);
      ctx.arcTo(x + s, y - s, x + s, y + s, rr);
      ctx.arcTo(x + s, y + s, x - s, y + s, rr);
      ctx.arcTo(x - s, y + s, x - s, y - s, rr);
      ctx.arcTo(x - s, y - s, x + s, y - s, rr);
      ctx.closePath();
      break;
    }
    case 'MOVE':
      ctx.moveTo(x, y - r * 1.05);
      ctx.lineTo(x + r * 1.0, y + r * 0.8);
      ctx.lineTo(x - r * 1.0, y + r * 0.8);
      ctx.closePath();
      break;
    case 'INTUITION':
      for (let i = 0; i < 6; i++) {
        const a = Math.PI / 6 + (i * Math.PI) / 3;
        const px = x + r * Math.cos(a);
        const py = y + r * Math.sin(a);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      break;
    case 'BUGGY_RULE':
      ctx.moveTo(x, y - r * 1.15);
      ctx.lineTo(x + r * 1.15, y);
      ctx.lineTo(x, y + r * 1.15);
      ctx.lineTo(x - r * 1.15, y);
      ctx.closePath();
      break;
    default:
      ctx.arc(x, y, r, 0, Math.PI * 2);
  }
}

function arrowHead(ctx: CanvasRenderingContext2D, x: number, y: number, ang: number, size: number, color: string): void {
  ctx.save();
  ctx.fillStyle = color;
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x - size * Math.cos(ang - 0.42), y - size * Math.sin(ang - 0.42));
  ctx.lineTo(x - size * Math.cos(ang + 0.42), y - size * Math.sin(ang + 0.42));
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function badge(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, color: string, k: number): void {
  const r = 8.5;
  ctx.save();
  ctx.setLineDash([]);
  ctx.shadowBlur = 0;
  ctx.fillStyle = C.panel;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  if (k > 0.35) {
    ctx.fillStyle = color;
    ctx.font = '600 11px "JetBrains Mono", ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x, y + 0.5);
  }
  ctx.restore();
}

function distToSeg(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax;
  const dy = by - ay;
  const l2 = dx * dx + dy * dy;
  let t = l2 ? ((px - ax) * dx + (py - ay) * dy) / l2 : 0;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function hubPos(e: HyperedgeOut, sim: Map<string, SimNode>): { x: number; y: number } | null {
  const c = sim.get(e.conclusion_node_id);
  const ps = e.premise_node_ids.map((id) => sim.get(id)).filter((p): p is SimNode => !!p);
  if (!c || ps.length < 2) return null;
  const mx = ps.reduce((a, p) => a + p.x, 0) / ps.length;
  const my = ps.reduce((a, p) => a + p.y, 0) / ps.length;
  return { x: mx + (c.x - mx) * 0.6, y: my + (c.y - my) * 0.6 };
}

function nodeFill(n: NodeOut, mode: ColorMode): string {
  switch (mode) {
    case 'domain':
      return domainColor(n.domain_cluster, n.node_type);
    case 'mastery':
      return masteryColor(n.bkt_p_mastery);
    case 'fsrs':
      if (n.retrievability > 0.85) return SLATE_EMERALD;
      if (n.retrievability >= 0.7) return '#0e7490';
      return '#3b2530';
    case 'hypercorrection':
      if (n.hypercorrection_flag === 1) return C.crimson;
      if (n.node_type === 'BUGGY_RULE') return C.rose;
      return '#26324a';
  }
}

// =================================================================== component
export default function HypergraphCanvas(): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const colorMode = useHarnessStore((s) => s.colorMode);
  const setColorMode = useHarnessStore((s) => s.setColorMode);
  const depthLock = useHarnessStore((s) => s.depthLock);
  const setDepthLock = useHarnessStore((s) => s.setDepthLock);
  const selectedNodeId = useHarnessStore((s) => s.selectedNodeId);
  const selectedEdgeId = useHarnessStore((s) => s.selectedEdgeId);
  const selectNode = useHarnessStore((s) => s.selectNode);
  const selectEdge = useHarnessStore((s) => s.selectEdge);
  const refreshGraph = useHarnessStore((s) => s.refreshGraph);

  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const simRef = useRef(new Map<string, SimNode>());
  const camRef = useRef<Cam>({ x: 0, y: 0, k: 1 });
  const camTarget = useRef<Cam | null>(null);
  const sizeRef = useRef({ w: 800, h: 600, dpr: 1 });
  const alphaRef = useRef(1);
  const hoverRef = useRef<Hit>(null);
  const hlRef = useRef<{ id: string; anc: Set<string>; desc: Set<string> } | null>(null);
  const dragRef = useRef<
    | { kind: 'node'; id: string; moved: boolean; sx: number; sy: number }
    | { kind: 'pan'; moved: boolean; sx: number; sy: number; cx: number; cy: number }
    | null
  >(null);
  const fittedRef = useRef(false);
  const measuredRef = useRef(false);
  const [search, setSearch] = useState('');
  const [legendOpen, setLegendOpen] = useState(true);

  const derived = useMemo(() => (graph ? derive(graph) : null), [graph]);

  // live props for the RAF loop
  const live = useRef({ graph, derived, colorMode, depthLock, selectedNodeId, selectedEdgeId });
  live.current = { graph, derived, colorMode, depthLock, selectedNodeId, selectedEdgeId };

  // ------------------------------------------------------------- camera helpers
  const fit = useCallback((animate = true) => {
    const sim = simRef.current;
    if (!sim.size) return;
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    sim.forEach((s) => {
      x0 = Math.min(x0, s.x);
      y0 = Math.min(y0, s.y);
      x1 = Math.max(x1, s.x);
      y1 = Math.max(y1, s.y);
    });
    const { w, h } = sizeRef.current;
    const pad = 90;
    const k = Math.max(0.2, Math.min(1.6, Math.min((w - pad * 2) / Math.max(1, x1 - x0), (h - pad * 2) / Math.max(1, y1 - y0))));
    const target = { x: (x0 + x1) / 2, y: (y0 + y1) / 2, k };
    if (animate) camTarget.current = target;
    else camRef.current = target;
  }, []);

  const centerOn = useCallback((id: string) => {
    const s = simRef.current.get(id);
    if (!s) return;
    camTarget.current = { x: s.x + 140 / camRef.current.k, y: s.y, k: Math.max(camRef.current.k, 0.9) };
  }, []);

  // ------------------------------------------------------------- graph → simulation
  useEffect(() => {
    if (!graph || !derived) return;
    const sim = simRef.current;
    const ids = new Set(graph.nodes.map((n) => n.id));
    [...sim.keys()].forEach((id) => {
      if (!ids.has(id)) sim.delete(id);
    });
    const H = derived.maxDepth * LAYER;
    let added = 0;
    graph.nodes.forEach((n, i) => {
      if (sim.has(n.id)) return;
      added++;
      // seed near an existing neighbour when possible
      const nb = [...(derived.parents.get(n.id) ?? []), ...(derived.children.get(n.id) ?? [])].map((id) => sim.get(id)).find(Boolean);
      const ci = derived.clusters.indexOf(clusterOf(n));
      const lane = (ci - (derived.clusters.length - 1) / 2) * 260;
      sim.set(n.id, {
        id: n.id,
        x: nb ? nb.x + (Math.random() - 0.5) * 60 : lane + (Math.random() - 0.5) * 120 + (i % 3) * 10,
        y: H - n.logical_depth * LAYER + (depthLock ? 0 : (Math.random() - 0.5) * 80),
        vx: 0,
        vy: 0,
        pinned: false,
      });
    });
    if (added > 0) {
      // settle synchronously so the first paint is already a clean layout (no visible explosion)
      const iters = fittedRef.current ? 60 : 320;
      for (let i = 0; i < iters; i++) tick(sim, graph, derived, depthLock, Math.max(0.15, 1 - i / iters));
      alphaRef.current = 0.5;
      if (!fittedRef.current) {
        fit(false);
        fittedRef.current = true;
      }
    } else alphaRef.current = Math.max(alphaRef.current, 0.25);
  }, [graph, derived]);

  // re-heat on layout toggle and refit once settled
  useEffect(() => {
    alphaRef.current = 1;
    if (!fittedRef.current) return;
    const t = window.setTimeout(() => fit(true), 650);
    return () => window.clearTimeout(t);
  }, [depthLock, fit]);

  // centre the camera on externally selected nodes (e.g. "open in graph")
  useEffect(() => {
    if (selectedNodeId) centerOn(selectedNodeId);
  }, [selectedNodeId, centerOn]);

  // ------------------------------------------------------------- resize
  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ro = new ResizeObserver(() => {
      const r = wrap.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      sizeRef.current = { w: r.width, h: r.height, dpr };
      canvas.width = Math.round(r.width * dpr);
      canvas.height = Math.round(r.height * dpr);
      canvas.style.width = `${r.width}px`;
      canvas.style.height = `${r.height}px`;
      // the graph may have been laid out before the first real measurement: refit once against true dimensions
      if (!measuredRef.current && r.width > 0) {
        measuredRef.current = true;
        if (simRef.current.size) fit(false);
      }
    });
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [fit]);

  // ------------------------------------------------------------- render loop
  useEffect(() => {
    let raf = 0;
    const draw = (t: number): void => {
      raf = requestAnimationFrame(draw);
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext('2d');
      const { graph: g, derived: d, colorMode: mode, depthLock: lock, selectedNodeId: selN, selectedEdgeId: selE } = live.current;
      if (!canvas || !ctx || !g || !d) return;
      const sim = simRef.current;

      // physics
      if (alphaRef.current > 0.02 || dragRef.current?.kind === 'node') {
        tick(sim, g, d, lock, Math.max(alphaRef.current, 0.08));
        alphaRef.current *= 0.985;
      }
      // camera easing
      if (camTarget.current) {
        const c = camRef.current;
        const tg = camTarget.current;
        c.x += (tg.x - c.x) * 0.16;
        c.y += (tg.y - c.y) * 0.16;
        c.k += (tg.k - c.k) * 0.16;
        if (Math.abs(tg.x - c.x) < 0.5 && Math.abs(tg.y - c.y) < 0.5 && Math.abs(tg.k - c.k) < 0.002) camTarget.current = null;
      }

      const { w, h, dpr } = sizeRef.current;
      const cam = camRef.current;
      const k = cam.k;
      const pulse = 0.5 + 0.5 * Math.sin(t / 260);

      // background + grid
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = C.bg;
      ctx.fillRect(0, 0, w, h);
      const toSx = (x: number): number => (x - cam.x) * k + w / 2;
      const toSy = (y: number): number => (y - cam.y) * k + h / 2;
      const grid = 40 * k;
      if (grid > 10) {
        ctx.strokeStyle = 'rgba(30,41,59,0.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        const ox = toSx(0) % grid;
        const oy = toSy(0) % grid;
        for (let x = ox; x < w; x += grid) {
          ctx.moveTo(x, 0);
          ctx.lineTo(x, h);
        }
        for (let y = oy; y < h; y += grid) {
          ctx.moveTo(0, y);
          ctx.lineTo(w, y);
        }
        ctx.stroke();
      }
      // depth layer guides
      if (lock) {
        const H = d.maxDepth * LAYER;
        ctx.font = '10px "JetBrains Mono", ui-monospace, monospace';
        ctx.textBaseline = 'bottom';
        for (let dep = 0; dep <= d.maxDepth; dep++) {
          const y = toSy(H - dep * LAYER);
          if (y < -20 || y > h + 20) continue;
          ctx.strokeStyle = dep === 0 ? 'rgba(99,102,241,0.35)' : 'rgba(51,65,85,0.45)';
          ctx.setLineDash(dep === 0 ? [] : [3, 6]);
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(w, y);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = C.dim;
          ctx.fillText(dep === 0 ? 'depth 0 · axioms / unconditional truths' : `depth ${dep}`, 10, y - 4);
        }
      }

      // world transform
      ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * (w / 2 - cam.x * k), dpr * (h / 2 - cam.y * k));
      const hl = hlRef.current;
      const inHl = (id: string): boolean => !hl || id === hl.id || hl.anc.has(id) || hl.desc.has(id);
      const nodeAlpha = (n: NodeOut): number => {
        if (hl) return inHl(n.id) ? 1 : 0.14;
        if (mode === 'hypercorrection') return n.hypercorrection_flag === 1 || n.node_type === 'BUGGY_RULE' ? 1 : 0.32;
        return 1;
      };
      const rOf = (n: NodeOut): number => NODE_R[n.node_type];
      const lw = (px: number): number => px / Math.max(0.35, k);

      // ---- hyperedges
      for (const e of g.hyperedges) {
        const c = sim.get(e.conclusion_node_id);
        const cn = d.byId.get(e.conclusion_node_id);
        if (!c || !cn) continue;
        const prem = e.premise_node_ids.map((id) => ({ s: sim.get(id), n: d.byId.get(id) })).filter((p) => p.s && p.n) as {
          s: SimNode;
          n: NodeOut;
        }[];
        if (!prem.length) continue;
        const touchesHl = !hl || (inHl(e.conclusion_node_id) && prem.some((p) => inHl(p.n.id)));
        const selected = selE === e.id;
        const baseA = hl ? (touchesHl ? 0.95 : 0.07) : mode === 'hypercorrection' ? 0.3 : 0.4 + 0.5 * e.edge_mastery;
        const color = EDGE_COLOR[e.edge_type];
        ctx.save();
        ctx.globalAlpha = selected ? 1 : baseA;
        ctx.lineCap = 'round';
        if (e.edge_type === 'DEDUCTION') {
          const hub = hubPos(e, sim);
          ctx.strokeStyle = color;
          ctx.setLineDash([]);
          if (hub) {
            ctx.lineWidth = lw(selected ? 2.2 : 1.3);
            for (const p of prem) {
              ctx.beginPath();
              ctx.moveTo(p.s.x, p.s.y);
              ctx.lineTo(hub.x, hub.y);
              ctx.stroke();
            }
            const ang = Math.atan2(c.y - hub.y, c.x - hub.x);
            const ex = c.x - Math.cos(ang) * (rOf(cn) + 3);
            const ey = c.y - Math.sin(ang) * (rOf(cn) + 3);
            ctx.lineWidth = lw(selected ? 3.6 : 2.6);
            ctx.beginPath();
            ctx.moveTo(hub.x, hub.y);
            ctx.lineTo(ex - Math.cos(ang) * 6, ey - Math.sin(ang) * 6);
            ctx.stroke();
            arrowHead(ctx, ex, ey, ang, 11, color);
            // ∧ conjunction hub
            const hs = 7.5;
            ctx.fillStyle = C.panel;
            ctx.lineWidth = lw(1.5);
            ctx.beginPath();
            ctx.moveTo(hub.x, hub.y - hs);
            ctx.lineTo(hub.x + hs, hub.y);
            ctx.lineTo(hub.x, hub.y + hs);
            ctx.lineTo(hub.x - hs, hub.y);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
            if (k > 0.45) {
              ctx.fillStyle = color;
              ctx.font = '700 9px "JetBrains Mono", ui-monospace, monospace';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillText('∧', hub.x, hub.y + 0.5);
            }
          } else {
            const p = prem[0];
            const ang = Math.atan2(c.y - p.s.y, c.x - p.s.x);
            const sx = p.s.x + Math.cos(ang) * (rOf(p.n) + 2);
            const sy = p.s.y + Math.sin(ang) * (rOf(p.n) + 2);
            const ex = c.x - Math.cos(ang) * (rOf(cn) + 3);
            const ey = c.y - Math.sin(ang) * (rOf(cn) + 3);
            ctx.lineWidth = lw(selected ? 3.4 : 2.4);
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(ex - Math.cos(ang) * 6, ey - Math.sin(ang) * 6);
            ctx.stroke();
            arrowHead(ctx, ex, ey, ang, 11, color);
          }
        } else {
          for (const p of prem) {
            const ang = Math.atan2(c.y - p.s.y, c.x - p.s.x);
            const sx = p.s.x + Math.cos(ang) * (rOf(p.n) + 3);
            const sy = p.s.y + Math.sin(ang) * (rOf(p.n) + 3);
            const ex = c.x - Math.cos(ang) * (rOf(cn) + 3);
            const ey = c.y - Math.sin(ang) * (rOf(cn) + 3);
            const mx = (sx + ex) / 2;
            const my = (sy + ey) / 2;
            ctx.strokeStyle = color;
            if (e.edge_type === 'CONTRASTIVE') {
              ctx.lineWidth = lw(selected ? 2.4 : 1.6);
              ctx.setLineDash([7, 5]);
              ctx.beginPath();
              ctx.moveTo(sx + Math.cos(ang) * 7, sy + Math.sin(ang) * 7);
              ctx.lineTo(ex - Math.cos(ang) * 7, ey - Math.sin(ang) * 7);
              ctx.stroke();
              arrowHead(ctx, ex, ey, ang, 9, color);
              arrowHead(ctx, sx, sy, ang + Math.PI, 9, color);
              badge(ctx, mx, my, '⊥', color, k);
            } else if (e.edge_type === 'ISOMORPHISM') {
              const off = 2.6;
              const nx = -Math.sin(ang) * off;
              const ny = Math.cos(ang) * off;
              ctx.shadowColor = C.violet;
              ctx.shadowBlur = 10;
              ctx.lineWidth = lw(selected ? 1.8 : 1.3);
              ctx.setLineDash([]);
              ctx.beginPath();
              ctx.moveTo(sx + nx, sy + ny);
              ctx.lineTo(ex + nx, ey + ny);
              ctx.moveTo(sx - nx, sy - ny);
              ctx.lineTo(ex - nx, ey - ny);
              ctx.stroke();
              ctx.shadowBlur = 0;
              badge(ctx, mx, my, '≅', color, k);
            } else {
              // CUE_TRIGGER  c ⇝ m
              ctx.lineWidth = lw(selected ? 2.6 : 1.9);
              ctx.setLineDash([0.5, 5]);
              ctx.beginPath();
              ctx.moveTo(sx, sy);
              ctx.lineTo(ex - Math.cos(ang) * 6, ey - Math.sin(ang) * 6);
              ctx.stroke();
              arrowHead(ctx, ex, ey, ang, 10, color);
            }
          }
        }
        ctx.restore();
      }

      // ---- mode 4: dashed crimson links to attached BUGGY_RULE misconceptions
      if (mode === 'hypercorrection') {
        ctx.save();
        ctx.strokeStyle = C.crimson;
        ctx.setLineDash([5, 4]);
        for (const [a, b] of d.buggyLinks) {
          const sa = sim.get(a);
          const sb = sim.get(b);
          const na = d.byId.get(a);
          if (!sa || !sb || !na) continue;
          const flagged = na.hypercorrection_flag === 1;
          ctx.globalAlpha = hl && !(inHl(a) && inHl(b)) ? 0.1 : flagged ? 0.95 : 0.5;
          ctx.lineWidth = lw(flagged ? 2.2 : 1.3);
          ctx.beginPath();
          ctx.moveTo(sa.x, sa.y);
          ctx.lineTo(sb.x, sb.y);
          ctx.stroke();
        }
        ctx.restore();
      }

      // ---- nodes
      const showLabels = k > 0.5;
      for (const n of g.nodes) {
        const s = sim.get(n.id);
        if (!s) continue;
        const r = rOf(n);
        const a = nodeAlpha(n);
        const fill = nodeFill(n, mode);
        ctx.save();
        ctx.globalAlpha = a;
        // halo rings per mode
        if (mode === 'fsrs') {
          if (n.retrievability >= 0.7 && n.retrievability <= 0.85) {
            ctx.shadowColor = C.cyan;
            ctx.shadowBlur = 16;
            ctx.strokeStyle = C.cyan;
            ctx.lineWidth = lw(2.5);
            shapePath(ctx, n.node_type, s.x, s.y, r + 6);
            ctx.stroke();
            ctx.shadowBlur = 0;
          } else if (n.retrievability < 0.7) {
            ctx.strokeStyle = withAlpha(C.rose, 0.35 + 0.6 * pulse);
            ctx.lineWidth = lw(2 + 1.5 * pulse);
            shapePath(ctx, n.node_type, s.x, s.y, r + 5 + 4 * pulse);
            ctx.stroke();
          }
        } else if (mode === 'hypercorrection' && n.hypercorrection_flag === 1) {
          ctx.shadowColor = C.crimson;
          ctx.shadowBlur = 22 + 10 * pulse;
          ctx.strokeStyle = withAlpha(C.crimson, 0.6 + 0.4 * pulse);
          ctx.lineWidth = lw(2.5);
          shapePath(ctx, n.node_type, s.x, s.y, r + 7);
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
        if (hl && n.id !== hl.id && (hl.anc.has(n.id) || hl.desc.has(n.id))) {
          ctx.strokeStyle = hl.anc.has(n.id) ? withAlpha(C.cyan, 0.85) : withAlpha(C.amber, 0.85);
          ctx.lineWidth = lw(1.6);
          ctx.setLineDash([3, 3]);
          shapePath(ctx, n.node_type, s.x, s.y, r + 5);
          ctx.stroke();
          ctx.setLineDash([]);
        }
        // body
        shapePath(ctx, n.node_type, s.x, s.y, r);
        ctx.fillStyle = withAlpha(fill.startsWith('#') ? fill : C.slate, 0.88);
        ctx.fill();
        ctx.strokeStyle = n.id === selN ? C.text : withAlpha(C.text, 0.28);
        ctx.lineWidth = lw(n.id === selN ? 2.6 : 1);
        ctx.stroke();
        if (n.node_type === 'COUNTEREXAMPLE') {
          ctx.strokeStyle = withAlpha(C.text, 0.85);
          ctx.lineWidth = lw(1.6);
          const q = r * 0.45;
          ctx.beginPath();
          ctx.moveTo(s.x - q, s.y - q);
          ctx.lineTo(s.x + q, s.y + q);
          ctx.moveTo(s.x + q, s.y - q);
          ctx.lineTo(s.x - q, s.y + q);
          ctx.stroke();
        }
        // P(L) arc in non-mastery modes
        if (mode !== 'mastery' && mode !== 'hypercorrection') {
          ctx.strokeStyle = masteryColor(n.bkt_p_mastery);
          ctx.lineWidth = lw(2);
          ctx.beginPath();
          ctx.arc(s.x, s.y, r + 3.2, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * n.bkt_p_mastery);
          ctx.stroke();
        }
        // labels
        const isHover = hoverRef.current?.kind === 'node' && hoverRef.current.id === n.id;
        if (showLabels || isHover || n.id === selN || (hl && inHl(n.id))) {
          const full = isHover || n.id === selN;
          const label = !full && n.title.length > 22 ? `${n.title.slice(0, 21)}…` : n.title;
          ctx.font = `${isHover || n.id === selN ? 600 : 500} 11px Inter, system-ui, sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          const tw = ctx.measureText(label).width;
          const ly = s.y + r + 7;
          ctx.fillStyle = 'rgba(7,10,18,0.78)';
          ctx.fillRect(s.x - tw / 2 - 3, ly - 1, tw + 6, 14);
          ctx.fillStyle = a < 1 ? C.muted : C.text;
          ctx.fillText(label, s.x, ly);
        }
        ctx.restore();
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  // ------------------------------------------------------------- interaction
  const toWorld = (clientX: number, clientY: number): { x: number; y: number } => {
    const r = canvasRef.current?.getBoundingClientRect();
    const { w, h } = sizeRef.current;
    const cam = camRef.current;
    const sx = clientX - (r?.left ?? 0);
    const sy = clientY - (r?.top ?? 0);
    return { x: (sx - w / 2) / cam.k + cam.x, y: (sy - h / 2) / cam.k + cam.y };
  };

  const hitTest = (wx: number, wy: number): Hit => {
    const { graph: g, derived: d } = live.current;
    if (!g || !d) return null;
    const sim = simRef.current;
    const k = camRef.current.k;
    let best: { id: string; dist: number } | null = null;
    for (const n of g.nodes) {
      const s = sim.get(n.id);
      if (!s) continue;
      const dist = Math.hypot(wx - s.x, wy - s.y);
      if (dist <= NODE_R[n.node_type] + 4 && (!best || dist < best.dist)) best = { id: n.id, dist };
    }
    if (best) return { kind: 'node', id: best.id };
    const tol = 6 / k;
    for (const e of g.hyperedges) {
      const c = sim.get(e.conclusion_node_id);
      if (!c) continue;
      const hub = e.edge_type === 'DEDUCTION' ? hubPos(e, sim) : null;
      if (hub) {
        if (Math.hypot(wx - hub.x, wy - hub.y) < 10) return { kind: 'edge', id: e.id };
        if (distToSeg(wx, wy, hub.x, hub.y, c.x, c.y) < tol) return { kind: 'edge', id: e.id };
        for (const pid of e.premise_node_ids) {
          const p = sim.get(pid);
          if (p && distToSeg(wx, wy, p.x, p.y, hub.x, hub.y) < tol) return { kind: 'edge', id: e.id };
        }
      } else {
        for (const pid of e.premise_node_ids) {
          const p = sim.get(pid);
          if (!p) continue;
          if (Math.hypot(wx - (p.x + c.x) / 2, wy - (p.y + c.y) / 2) < 11) return { kind: 'edge', id: e.id };
          if (distToSeg(wx, wy, p.x, p.y, c.x, c.y) < tol) return { kind: 'edge', id: e.id };
        }
      }
    }
    return null;
  };

  const setHover = (hit: Hit, clientX: number, clientY: number): void => {
    hoverRef.current = hit;
    const d = live.current.derived;
    const g = live.current.graph;
    if (hit?.kind === 'node' && d) {
      if (hlRef.current?.id !== hit.id) hlRef.current = { id: hit.id, anc: reach(hit.id, d.parents), desc: reach(hit.id, d.children) };
    } else hlRef.current = null;
    const canvas = canvasRef.current;
    if (canvas) canvas.style.cursor = dragRef.current?.kind === 'pan' && dragRef.current.moved ? 'grabbing' : hit ? 'pointer' : 'grab';
    const tip = tipRef.current;
    const wrapR = wrapRef.current?.getBoundingClientRect();
    if (!tip || !wrapR) return;
    if (!hit || !d || !g) {
      tip.style.opacity = '0';
      return;
    }
    let html = '';
    if (hit.kind === 'node') {
      const n = d.byId.get(hit.id);
      if (!n) return;
      const hl = hlRef.current;
      html = `<div class="tip-title">${escape(n.title)}</div><div class="tip-row mono">${n.node_type} · d${n.logical_depth} · ${escape(clusterOf(n))}</div><div class="tip-row mono">P(L) ${n.bkt_p_mastery.toFixed(2)} · R ${n.retrievability.toFixed(2)} · S ${n.fsrs_stability.toFixed(1)}d</div><div class="tip-row mono dim">▲ ${hl?.anc.size ?? 0} upstream · ▼ ${hl?.desc.size ?? 0} downstream</div>`;
    } else {
      const e = g.hyperedges.find((x) => x.id === hit.id);
      if (!e) return;
      const sym = { DEDUCTION: '⟹', CONTRASTIVE: '⊥', ISOMORPHISM: '≅', CUE_TRIGGER: '⇝' }[e.edge_type];
      const prem = e.premise_node_ids.map((id) => d.byId.get(id)?.title ?? id).join(' ∧ ');
      html = `<div class="tip-title">${e.edge_type} ${sym}</div><div class="tip-row">${escape(prem)} ${sym} ${escape(d.byId.get(e.conclusion_node_id)?.title ?? e.conclusion_node_id)}</div><div class="tip-row mono dim">edge mastery ${e.edge_mastery.toFixed(2)}</div>`;
    }
    tip.innerHTML = html;
    tip.style.opacity = '1';
    const x = clientX - wrapR.left + 14;
    const y = clientY - wrapR.top + 14;
    tip.style.transform = `translate(${Math.min(x, wrapR.width - 280)}px, ${Math.min(y, wrapR.height - 90)}px)`;
  };

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>): void => {
    (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
    const wpt = toWorld(e.clientX, e.clientY);
    const hit = hitTest(wpt.x, wpt.y);
    camTarget.current = null;
    if (hit?.kind === 'node') {
      const s = simRef.current.get(hit.id);
      if (s) s.pinned = true;
      dragRef.current = { kind: 'node', id: hit.id, moved: false, sx: e.clientX, sy: e.clientY };
    } else {
      dragRef.current = { kind: 'pan', moved: false, sx: e.clientX, sy: e.clientY, cx: camRef.current.x, cy: camRef.current.y };
    }
  };
  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>): void => {
    const drag = dragRef.current;
    if (drag) {
      const moved = Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4;
      if (moved) drag.moved = true;
      if (drag.kind === 'node' && drag.moved) {
        const s = simRef.current.get(drag.id);
        const wpt = toWorld(e.clientX, e.clientY);
        if (s) {
          s.x = wpt.x;
          s.y = wpt.y;
        }
        alphaRef.current = Math.max(alphaRef.current, 0.3);
        if (tipRef.current) tipRef.current.style.opacity = '0';
        return;
      }
      if (drag.kind === 'pan' && drag.moved) {
        const k = camRef.current.k;
        camRef.current.x = drag.cx - (e.clientX - drag.sx) / k;
        camRef.current.y = drag.cy - (e.clientY - drag.sy) / k;
        if (canvasRef.current) canvasRef.current.style.cursor = 'grabbing';
        if (tipRef.current) tipRef.current.style.opacity = '0';
        return;
      }
    }
    const wpt = toWorld(e.clientX, e.clientY);
    setHover(hitTest(wpt.x, wpt.y), e.clientX, e.clientY);
  };
  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>): void => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (!drag) return;
    if (drag.kind === 'node') {
      const s = simRef.current.get(drag.id);
      if (s) s.pinned = false;
      if (!drag.moved) selectNode(drag.id);
      return;
    }
    if (!drag.moved) {
      const wpt = toWorld(e.clientX, e.clientY);
      const hit = hitTest(wpt.x, wpt.y);
      if (hit?.kind === 'edge') selectEdge(hit.id);
      else if (!hit) {
        selectNode(null);
        selectEdge(null);
      }
    }
    if (canvasRef.current) canvasRef.current.style.cursor = 'grab';
  };
  const onWheel = (e: React.WheelEvent<HTMLCanvasElement>): void => {
    camTarget.current = null;
    const cam = camRef.current;
    const before = toWorld(e.clientX, e.clientY);
    const factor = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015));
    cam.k = Math.max(0.15, Math.min(3, cam.k * factor));
    const after = toWorld(e.clientX, e.clientY);
    cam.x += before.x - after.x;
    cam.y += before.y - after.y;
  };

  // native non-passive wheel listener so the page never scrolls under the canvas
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const prevent = (e: WheelEvent): void => e.preventDefault();
    c.addEventListener('wheel', prevent, { passive: false });
    return () => c.removeEventListener('wheel', prevent);
  }, []);

  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q || !graph) return [];
    return graph.nodes.filter((n) => n.title.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)).slice(0, 8);
  }, [search, graph]);

  const stats = useMemo(() => {
    if (!graph) return null;
    const by: Record<EdgeType, number> = { DEDUCTION: 0, CONTRASTIVE: 0, ISOMORPHISM: 0, CUE_TRIGGER: 0 };
    graph.hyperedges.forEach((e) => (by[e.edge_type] += 1));
    return by;
  }, [graph]);

  const inspectorOpen = Boolean(selectedNodeId || selectedEdgeId);

  return (
    <div className="hg">
      <div className="hg-toolbar">
        <label className="toggle" title="Pin logical_depth 0 at the bottom; derived propositions rise 130 px per depth level">
          <input type="checkbox" checked={depthLock} onChange={(e) => setDepthLock(e.target.checked)} />
          <span className="toggle-track" />
          <span>Lock Y-Axis to Logical Depth</span>
        </label>
        <div className="seg" role="radiogroup" aria-label="Colour mode">
          {COLOR_MODES.map((m) => (
            <button
              key={m.id}
              role="radio"
              aria-checked={colorMode === m.id}
              className={`seg-btn${colorMode === m.id ? ' on' : ''}`}
              onClick={() => setColorMode(m.id)}
              title={m.title}
            >
              {m.label}
            </button>
          ))}
        </div>
        <span className="spacer" />
        <div className="hg-search">
          <input
            placeholder="find node…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && matches[0]) {
                selectNode(matches[0].id);
                setSearch('');
              } else if (e.key === 'Escape') setSearch('');
            }}
          />
          {matches.length ? (
            <div className="hg-search-results">
              {matches.map((n) => (
                <button
                  key={n.id}
                  onClick={() => {
                    selectNode(n.id);
                    setSearch('');
                  }}
                >
                  <span className="dot-inline" style={{ background: domainColor(n.domain_cluster, n.node_type) }} />
                  {n.title}
                </button>
              ))}
            </div>
          ) : null}
        </div>
        <button className="btn small ghost" onClick={() => fit(true)} title="Fit graph (double-click background)">
          ⤢ Fit
        </button>
        <button className="btn small ghost" onClick={() => void refreshGraph()} title="Reload GET /api/graph">
          ↻
        </button>
        <span className="mono dim small">
          {graph ? `${graph.nodes.length} nodes · ${graph.hyperedges.length} hyperedges` : 'loading…'}
        </span>
      </div>

      <div className="hg-stage" ref={wrapRef}>
        <canvas
          ref={canvasRef}
          className="hg-canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={() => {
            hoverRef.current = null;
            hlRef.current = null;
            if (tipRef.current) tipRef.current.style.opacity = '0';
          }}
          onWheel={onWheel}
          onDoubleClick={(e) => {
            const wpt = toWorld(e.clientX, e.clientY);
            if (!hitTest(wpt.x, wpt.y)) fit(true);
          }}
        />
        <div className="hg-tip" ref={tipRef} />
        {!graph ? (
          <div className="hg-loading">
            <Spinner /> loading hypergraph…
          </div>
        ) : null}

        <div className={`hg-legend${legendOpen ? '' : ' closed'}`}>
          <button className="legend-head" onClick={() => setLegendOpen((v) => !v)}>
            Legend {legendOpen ? '▾' : '▸'}
          </button>
          {legendOpen ? (
            <>
              <div className="legend-sec">
                <LegendEdge type="DEDUCTION" label="Deduction {A,B} ∧→ C" count={stats?.DEDUCTION} />
                <LegendEdge type="CONTRASTIVE" label="Contrastive u ⊥ v" count={stats?.CONTRASTIVE} />
                <LegendEdge type="ISOMORPHISM" label="Isomorphism u ≅ v" count={stats?.ISOMORPHISM} />
                <LegendEdge type="CUE_TRIGGER" label="Cue trigger c ⇝ m" count={stats?.CUE_TRIGGER} />
              </div>
              <div className="legend-sec types mono">
                {(Object.keys(NODE_TYPE_GLYPH) as NodeType[]).map((t) => (
                  <span key={t}>
                    {NODE_TYPE_GLYPH[t]} {t.toLowerCase().replace('_', ' ')}
                  </span>
                ))}
              </div>
              <div className="legend-sec">
                {colorMode === 'domain'
                  ? Object.entries(DOMAIN_COLORS).map(([dname, col]) => (
                      <div key={dname} className="legend-row">
                        <span className="dot-inline" style={{ background: col }} />
                        {dname}
                      </div>
                    ))
                  : null}
                {colorMode === 'mastery' ? (
                  <>
                    <div className="legend-gradient" />
                    <div className="legend-scale mono">
                      <span>0.35</span>
                      <span>0.55</span>
                      <span>0.85 P(L)</span>
                    </div>
                  </>
                ) : null}
                {colorMode === 'fsrs' ? (
                  <>
                    <div className="legend-row">
                      <span className="ring-inline cyan" /> Bjork window 0.70 ≤ R ≤ 0.85
                    </div>
                    <div className="legend-row">
                      <span className="dot-inline" style={{ background: SLATE_EMERALD }} /> fresh R &gt; 0.85
                    </div>
                    <div className="legend-row">
                      <span className="ring-inline red" /> decaying R &lt; 0.70
                    </div>
                  </>
                ) : null}
                {colorMode === 'hypercorrection' ? (
                  <>
                    <div className="legend-row">
                      <span className="dot-inline" style={{ background: C.crimson }} /> hypercorrection flag (≥75% error)
                    </div>
                    <div className="legend-row">
                      <span className="dot-inline" style={{ background: C.rose }} /> buggy rule
                    </div>
                    <div className="legend-row">
                      <span className="dash-inline" /> attached misconception
                    </div>
                  </>
                ) : null}
                {colorMode !== 'mastery' && colorMode !== 'hypercorrection' ? (
                  <div className="legend-row dim">outer arc = P(L) mastery</div>
                ) : null}
              </div>
              <div className="legend-sec dim small">hover: ▲ upstream (cyan) · ▼ downstream (amber) · wheel zoom · drag pan/move</div>
            </>
          ) : null}
        </div>

        <div className={`inspector${inspectorOpen ? ' open' : ''}`} aria-hidden={!inspectorOpen}>
          {selectedNodeId ? <NodeInspector id={selectedNodeId} /> : null}
          {selectedEdgeId && graph ? <EdgeInspector edge={graph.hyperedges.find((e) => e.id === selectedEdgeId)} /> : null}
        </div>
      </div>
    </div>
  );
}

function escape(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c);
}

function LegendEdge({ type, label, count }: { type: EdgeType; label: string; count?: number }): JSX.Element {
  const col = EDGE_COLOR[type];
  return (
    <div className="legend-row">
      <svg width={40} height={12} aria-hidden="true">
        {type === 'DEDUCTION' ? (
          <>
            <line x1={2} y1={6} x2={30} y2={6} stroke={col} strokeWidth={2.4} />
            <path d="M 18 2 L 22 6 L 18 10 L 14 6 Z" fill={C.panel} stroke={col} />
            <path d="M 38 6 L 30 2 L 30 10 Z" fill={col} />
          </>
        ) : type === 'CONTRASTIVE' ? (
          <line x1={2} y1={6} x2={38} y2={6} stroke={col} strokeWidth={1.6} strokeDasharray="5 4" />
        ) : type === 'ISOMORPHISM' ? (
          <>
            <line x1={2} y1={4} x2={38} y2={4} stroke={col} strokeWidth={1.3} />
            <line x1={2} y1={8} x2={38} y2={8} stroke={col} strokeWidth={1.3} />
          </>
        ) : (
          <>
            <line x1={2} y1={6} x2={30} y2={6} stroke={col} strokeWidth={2} strokeDasharray="0.5 4" strokeLinecap="round" />
            <path d="M 38 6 L 30 2 L 30 10 Z" fill={col} />
          </>
        )}
      </svg>
      <span>{label}</span>
      <span className="mono dim">{count ?? 0}</span>
    </div>
  );
}

// =================================================================== inspector
function NodeChip({ id }: { id: string }): JSX.Element {
  const n = useHarnessStore((s) => s.graph?.nodes.find((x) => x.id === id));
  const selectNode = useHarnessStore((s) => s.selectNode);
  return (
    <button className={`chip${n?.node_type === 'BUGGY_RULE' ? ' rose' : ''}`} onClick={() => selectNode(id)} title={id}>
      <span className="dot-inline" style={{ background: n ? domainColor(n.domain_cluster, n.node_type) : C.dim }} />
      {n?.title ?? id}
    </button>
  );
}

function NodeInspector({ id }: { id: string }): JSX.Element {
  const detail = useHarnessStore((s) => s.nodeDetails[id]);
  const graphNode = useHarnessStore((s) => s.graph?.nodes.find((n) => n.id === id));
  const selectNode = useHarnessStore((s) => s.selectNode);
  const selectEdge = useHarnessStore((s) => s.selectEdge);
  const createSession = useHarnessStore((s) => s.createSession);
  const loadSession = useHarnessStore((s) => s.loadSession);
  const busy = useHarnessStore((s) => s.busy.create);
  const [proofOpen, setProofOpen] = useState(false);
  // NodeDetail is fetched by store.selectNode() and refreshed on graph_updated.

  const n = detail?.node ?? graphNode;
  if (!n) {
    return (
      <div className="insp-body">
        <Spinner /> loading node…
      </div>
    );
  }
  const sourceSession = n.created_in_session_id ?? detail?.traces[0]?.session_id ?? null;
  const inWindow = n.retrievability >= 0.7 && n.retrievability <= 0.85;

  return (
    <div className="insp-body">
      <div className="insp-head">
        <div className="insp-kind mono">
          <span style={{ color: domainColor(n.domain_cluster, n.node_type) }}>{NODE_TYPE_GLYPH[n.node_type]}</span> {n.node_type} · depth{' '}
          {n.logical_depth}
        </div>
        <button className="btn ghost icon" onClick={() => selectNode(null)} aria-label="Close inspector">
          ✕
        </button>
      </div>
      <h3 className="insp-title">{n.title}</h3>
      <div className="insp-domain">
        <span className="dot-inline" style={{ background: domainColor(n.domain_cluster, n.node_type) }} />
        {n.domain_cluster}
        {n.hypercorrection_flag === 1 ? <span className="tag rose mono">⚑ HYPERCORRECTION</span> : null}
        {n.last_miss_class && n.last_miss_class !== 'NONE' ? <span className="tag amber mono">{n.last_miss_class}</span> : null}
      </div>

      <div className="insp-actions">
        <button
          className="btn primary"
          disabled={busy}
          onClick={() => void createSession({ mode: 'PRACTICE', target_goal: `Practice: ${n.title}`, target_node_id: n.id, cue_level: 1 })}
        >
          Practice This Node Now
        </button>
        <button
          className="btn"
          disabled={busy}
          onClick={() =>
            void createSession({
              mode: 'REFEREE_DUEL',
              sub_mode: 'PROOF_REFEREE',
              target_goal: `Proof-Referee duel: ${n.title}`,
              target_node_id: n.id,
              cue_level: 4,
            })
          }
        >
          ⚖ Launch Proof-Referee Duel on This Node
        </button>
        <button
          className="btn ghost"
          disabled={!sourceSession}
          title={sourceSession ? `Open session ${sourceSession}` : 'Seeded node: no session has created or practised it yet'}
          onClick={() => sourceSession && void loadSession(sourceSession, 1)}
        >
          ↗ Jump to Source Session
        </button>
      </div>

      <section className="insp-sec">
        <div className="insp-label">Statement</div>
        <MathText text={n.statement_latex} latexField />
      </section>
      {n.intuition_summary ? (
        <section className="insp-sec">
          <div className="insp-label">Intuition</div>
          <MathText text={n.intuition_summary} />
        </section>
      ) : null}
      {n.formal_proof_sketch_latex ? (
        <section className="insp-sec">
          <button className="insp-label link" onClick={() => setProofOpen((v) => !v)}>
            Formal proof sketch {proofOpen ? '▾' : '▸'}
          </button>
          {proofOpen ? <MathText text={n.formal_proof_sketch_latex} latexField /> : null}
        </section>
      ) : null}

      <section className="insp-sec">
        <div className="insp-label">Memory & mastery</div>
        <div className="stat-grid">
          <div className="stat">
            <div className="stat-k">BKT P(L_t)</div>
            <div className="stat-v mono" style={{ color: masteryColor(n.bkt_p_mastery) }}>
              {fx(n.bkt_p_mastery, 3)}
            </div>
            <Bar value={n.bkt_p_mastery} />
          </div>
          <div className="stat">
            <div className="stat-k">Retrievability R(t)</div>
            <div className="stat-v mono" style={{ color: inWindow ? C.cyan : n.retrievability < 0.7 ? C.rose : C.emerald }}>
              {fx(n.retrievability, 3)}
            </div>
            <div className="stat-sub mono">{inWindow ? 'in Bjork window' : n.retrievability < 0.7 ? 'decaying' : 'fresh'}</div>
          </div>
          <div className="stat">
            <div className="stat-k">Stability S</div>
            <div className="stat-v mono">{fx(n.fsrs_stability, 2)}d</div>
            <div className="stat-sub mono">
              {n.fsrs_reps} reps · {n.fsrs_lapses} lapses
            </div>
          </div>
          <div className="stat">
            <div className="stat-k">Difficulty D</div>
            <div className="stat-v mono">{fx(n.fsrs_difficulty, 2)}</div>
            <Bar value={(n.fsrs_difficulty - 1) / 9} color={C.amber} />
          </div>
        </div>
        <div className="due-line mono" title="harness-cli due: next review when R falls to the desired retention 0.90">
          <span className="dim">next due</span> {fmtDateTime(n.next_due_at)}{' '}
          <span style={{ color: n.days_until_due <= 0 ? C.rose : C.muted }}>{dueRelative(n.days_until_due)}</span>
          <span className="dim"> · r=0.90 · last review {timeAgo(n.last_reviewed_at)}</span>
        </div>
        <div className="kv-grid">
          <Kv k="P(T) transit" v={fx(n.bkt_p_transit, 3)} />
          <Kv k="P(S) slip" v={fx(n.bkt_p_slip, 3)} />
          <Kv k="P(G) guess" v={fx(n.bkt_p_guess, 3)} />
          <Kv k="mean Brier" v={n.mean_brier === null ? '—' : `${fx(n.mean_brier, 3)} (n=${n.brier_count})`} />
        </div>
      </section>

      <section className="insp-sec">
        <div className="insp-label">5D cue breadth · mean {pct(n.cue_mean)}</div>
        <div className="cue-block">
          <CuePentagon cues={n.cues} />
          <div className="cue-bars">
            {(Object.keys(CUE_LABELS) as (keyof typeof CUE_LABELS)[]).map((k) => (
              <div key={k} className="cue-bar">
                <span className="cue-name">{CUE_LABELS[k]}</span>
                <Bar value={n.cues[k]} color={C.cyan} />
                <span className="mono">{fx(n.cues[k])}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {detail ? (
        <>
          <section className="insp-sec">
            <div className="insp-label">Incoming premise chains · {detail.incoming.length}</div>
            {detail.incoming.length === 0 ? <div className="dim small">No premises — an unconditional starting point.</div> : null}
            {detail.incoming.map((e) => (
              <div key={e.id} className="chain">
                <button className={`edge-tag mono e-${e.edge_type.toLowerCase()}`} onClick={() => selectEdge(e.id)}>
                  {e.edge_type}
                </button>
                <div className="chain-prem">
                  {e.premise_node_ids.map((p) => (
                    <NodeChip key={p} id={p} />
                  ))}
                  <span className="mono dim">⟹ this</span>
                </div>
                {e.reasoning_chain_latex ? <MathText text={e.reasoning_chain_latex} latexField className="chain-body" /> : null}
              </div>
            ))}
          </section>
          <section className="insp-sec">
            <div className="insp-label">Outgoing conclusions · {detail.outgoing.length}</div>
            {detail.outgoing.length === 0 ? <div className="dim small">Nothing derived from this node yet.</div> : null}
            <div className="chips-wrap">
              {detail.outgoing.map((e) => (
                <span key={e.id} className="out-edge">
                  <button className={`edge-tag mono e-${e.edge_type.toLowerCase()}`} onClick={() => selectEdge(e.id)}>
                    {e.edge_type === 'DEDUCTION' ? '⟹' : e.edge_type === 'CONTRASTIVE' ? '⊥' : e.edge_type === 'ISOMORPHISM' ? '≅' : '⇝'}
                  </button>
                  <NodeChip id={e.conclusion_node_id} />
                </span>
              ))}
            </div>
          </section>
          {detail.contrastive_peers.length ? (
            <section className="insp-sec">
              <div className="insp-label">Contrastive boundary peers</div>
              <div className="chips-wrap">
                {detail.contrastive_peers.map((p) => (
                  <NodeChip key={p} id={p} />
                ))}
              </div>
            </section>
          ) : null}
          {detail.buggy_rule_links.length ? (
            <section className="insp-sec">
              <div className="insp-label">Attached buggy rules</div>
              <div className="chips-wrap">
                {detail.buggy_rule_links.map((p) => (
                  <NodeChip key={p} id={p} />
                ))}
              </div>
            </section>
          ) : null}
          <section className="insp-sec">
            <div className="insp-label">
              Markov blanket · ▲ {detail.ancestors.length} ancestors · ▼ {detail.descendants.length} descendants
            </div>
            <div className="chips-wrap small">
              {detail.ancestors.slice(0, 12).map((p) => (
                <NodeChip key={`a${p}`} id={p} />
              ))}
            </div>
          </section>
          <section className="insp-sec">
            <div className="insp-label">Recent traces · {detail.traces.length}</div>
            {detail.traces.length === 0 ? <div className="dim small">Never assessed.</div> : null}
            {detail.traces.slice(0, 6).map((t) => (
              <button key={t.id} className="trace-row mono" onClick={() => void loadSession(t.session_id, 1)} title="Open the session">
                <span className="tl-cell" style={{ background: OUTCOME_COLOR[t.outcome] }} />
                <span>{t.phase}</span>
                <span style={{ color: OUTCOME_COLOR[t.outcome] }}>{t.outcome}</span>
                <span className="dim">
                  c{Math.round(t.confidence_slider * 100)} q{fx(t.trace_quality_score)}
                </span>
                <span className="dim">{timeAgo(t.created_at)}</span>
              </button>
            ))}
          </section>
        </>
      ) : (
        <div className="dim small">
          <Spinner /> loading premise chains…
        </div>
      )}
    </div>
  );
}

function EdgeInspector({ edge }: { edge: HyperedgeOut | undefined }): JSX.Element {
  const selectEdge = useHarnessStore((s) => s.selectEdge);
  const loadSession = useHarnessStore((s) => s.loadSession);
  const createSession = useHarnessStore((s) => s.createSession);
  const conclusion = useHarnessStore((s) => (edge ? s.graph?.nodes.find((n) => n.id === edge.conclusion_node_id) : undefined));
  const busy = useHarnessStore((s) => s.busy.create);
  if (!edge) return <div className="insp-body dim">Hyperedge no longer exists.</div>;
  const sym = { DEDUCTION: '⟹', CONTRASTIVE: '⊥', ISOMORPHISM: '≅', CUE_TRIGGER: '⇝' }[edge.edge_type];
  return (
    <div className="insp-body">
      <div className="insp-head">
        <div className="insp-kind mono" style={{ color: EDGE_COLOR[edge.edge_type] }}>
          {sym} {edge.edge_type} hyperedge
        </div>
        <button className="btn ghost icon" onClick={() => selectEdge(null)} aria-label="Close inspector">
          ✕
        </button>
      </div>
      <div className="chain-prem big">
        {edge.premise_node_ids.map((p, i) => (
          <span key={p} className="row">
            {i > 0 ? <span className="mono dim"> ∧ </span> : null}
            <NodeChip id={p} />
          </span>
        ))}
        <span className="mono" style={{ color: EDGE_COLOR[edge.edge_type] }}>
          {' '}
          {sym}{' '}
        </span>
        <NodeChip id={edge.conclusion_node_id} />
      </div>
      <section className="insp-sec">
        <div className="insp-label">{edge.edge_type === 'CONTRASTIVE' ? 'Boundary discriminator' : 'Reasoning chain'}</div>
        <MathText text={edge.reasoning_chain_latex} latexField />
      </section>
      {edge.discriminating_condition_latex ? (
        <section className="insp-sec">
          <div className="insp-label">Discriminating condition</div>
          <MathText text={edge.discriminating_condition_latex} latexField />
        </section>
      ) : null}
      <section className="insp-sec">
        <Kv k="Edge mastery" v={<>{fx(edge.edge_mastery)} <Bar value={edge.edge_mastery} /></>} />
        <Kv k="Created" v={fmtDateTime(edge.created_at)} />
        <Kv k="id" v={edge.id} />
      </section>
      <div className="insp-actions">
        <button
          className="btn primary"
          disabled={busy || !conclusion}
          onClick={() =>
            conclusion &&
            void createSession({
              mode: 'PRACTICE',
              target_goal: `Practice the link into ${conclusion.title}`,
              target_node_id: conclusion.id,
              contrastive_pair: edge.edge_type === 'CONTRASTIVE',
              cue_level: edge.edge_type === 'CONTRASTIVE' ? 3 : 2,
            })
          }
        >
          Practice this link
        </button>
        <button className="btn ghost" disabled={!edge.session_id} onClick={() => edge.session_id && void loadSession(edge.session_id, 1)}>
          ↗ Jump to Source Session
        </button>
      </div>
    </div>
  );
}
