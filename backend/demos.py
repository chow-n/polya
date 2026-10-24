"""Interactive sandbox demos and SVG diagrams for LearnHarness.

Used by the ``SANDBOX_DEMO_BUILDER`` and ``SVG_DIAGRAM_MAKER`` sub-agents
(ARCHITECTURE_SPEC.md §5.4, §5.5) and by the seed dataset (§7.5).  Every HTML
demo is a complete, self-contained ``<!DOCTYPE html>`` document (no network,
no external fonts or scripts) with dark styling, 2-4 range sliders with live
readouts, a Goal-Directed Challenge Banner that turns green when the target is
met, devicePixelRatio-aware canvases, and throttled (~5/s) telemetry posted to
the parent window (§6.5 ``SandboxDemoViewer``)::

    window.parent.postMessage({type: 'HARNESS_DEMO_TELEMETRY', demoId,
        params: currentParams, challengeSolved: isTargetMet, summary}, '*')

Public API
----------
``DEMO_ATTENTION_HTML``, ``DEMO_SGD_HTML``, ``DEMO_ROPE_BELLMAN_HTML``,
``build_demo_html``, ``build_svg_diagram``, ``DEMO_SEED``.

Pure Python, standard library only.
"""

from __future__ import annotations

import html
import json
import math
import re

__all__ = [
    "DEMO_ATTENTION_HTML",
    "DEMO_SGD_HTML",
    "DEMO_ROPE_BELLMAN_HTML",
    "DEMO_SEED",
    "build_demo_html",
    "build_svg_diagram",
]


# ---------------------------------------------------------------------------
# Shared page shell
# ---------------------------------------------------------------------------

def _esc(text: object) -> str:
    """HTML/XML-escape arbitrary text and drop control characters."""
    s = "" if text is None else str(text)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    return html.escape(s, quote=True)


def _js_str(value: object) -> str:
    """JSON-encode a value so it is safe to embed inside a <script> block."""
    return (
        json.dumps(value, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


_CSS = r"""
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:#0b0f19;color:#f8fafc;font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
body.inverted{filter:invert(1) hue-rotate(180deg)}
.wrap{max-width:1000px;margin:0 auto;padding:12px 14px 18px}
#challenge{border:1px solid #f59e0b;background:rgba(245,158,11,0.10);color:#fde68a;border-radius:10px;padding:9px 12px;margin-bottom:10px;transition:background .25s,border-color .25s,color .25s}
#challenge.met{border-color:#10b981;background:rgba(16,185,129,0.20);color:#d1fae5}
#challenge .tag{display:inline-block;font-weight:700;letter-spacing:.07em;font-size:10.5px;text-transform:uppercase;padding:1px 7px;border-radius:999px;background:rgba(245,158,11,0.25);margin-right:6px}
#challenge.met .tag{background:rgba(16,185,129,0.35)}
#challenge .goal{font-weight:600}
#challenge-status{display:block;margin-top:4px;font-size:12.5px;font-variant-numeric:tabular-nums;opacity:.95}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}
header h1{font-size:17px;margin:2px 0 2px;font-weight:650}
.sub{color:#94a3b8;font-size:12.5px}
.toolbar{display:flex;gap:6px}
button{background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:5px 10px;font:inherit;font-size:12px;cursor:pointer}
button:hover{border-color:#6366f1}
details.stmt{margin-top:4px;color:#cbd5e1;font-size:12.5px}
details.stmt code{white-space:pre-wrap;word-break:break-word;color:#c7d2fe;font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;font-size:12px}
.controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px 18px;background:#111827;border:1px solid #1e293b;border-radius:10px;padding:10px 12px;margin:10px 0}
.ctl label{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;color:#cbd5e1}
.ctl output{font-variant-numeric:tabular-nums;color:#a5b4fc;font-weight:650}
input[type=range]{width:100%;accent-color:#6366f1;margin:4px 0 0}
.panel{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:8px 10px;margin-top:10px;min-width:0}
.panel h3{margin:0 0 6px;font-size:13px;font-weight:600;color:#e2e8f0}
canvas{display:block;width:100%;height:260px}
canvas.short{height:170px}
canvas.strip{height:140px}
svg.fig{display:block;width:100%;height:auto}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.grid2 > .panel{margin-top:0}
.row{margin-top:10px}
@media (max-width:680px){.grid2{grid-template-columns:1fr}}
.stats{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12.5px;color:#cbd5e1;margin-top:8px;font-variant-numeric:tabular-nums}
.stats b{color:#f8fafc;font-weight:650}
.warn{display:none;margin-top:8px;border:1px solid #ef4444;background:rgba(239,68,68,0.14);color:#fecaca;border-radius:8px;padding:6px 10px;font-size:12.5px}
.warn.on{display:block}
.hint{color:#94a3b8;font-size:12px;margin-top:6px}
.telemetry{margin-top:10px;color:#64748b;font-size:11px;font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;word-break:break-word}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:11.5px;color:#94a3b8;margin-top:4px}
.sw{display:inline-block;width:12px;height:3px;border-radius:2px;vertical-align:middle;margin-right:5px}
"""

# Shared JavaScript runtime: seeded RNG, canvas DPR handling, plotting
# helpers, the challenge banner and throttled telemetry.
_PRELUDE_JS = r"""
'use strict';
const DEMO_ID = __DEMO_ID__;
const DEMO_TITLE = __DEMO_TITLE__;
const COLORS = {indigo:'#6366f1', emerald:'#10b981', amber:'#f59e0b', violet:'#8b5cf6', cyan:'#22d3ee', red:'#ef4444', text:'#f8fafc', muted:'#94a3b8', grid:'#1e293b', axis:'#334155', fill:'#1e293b'};
function $(id) { return document.getElementById(id); }
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function makeGauss(rng) {
  let spare = null;
  return function () {
    if (spare !== null) { const s = spare; spare = null; return s; }
    let u = rng();
    while (u <= 1e-300) u = rng();
    const v = rng();
    const r = Math.sqrt(-2 * Math.log(u));
    spare = r * Math.sin(2 * Math.PI * v);
    return r * Math.cos(2 * Math.PI * v);
  };
}
function fitCanvas(cv) {
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const rect = cv.getBoundingClientRect();
  const w = Math.max(40, rect.width || cv.clientWidth || 300);
  const h = Math.max(40, rect.height || cv.clientHeight || 150);
  const pw = Math.round(w * dpr), ph = Math.round(h * dpr);
  if (cv.width !== pw) cv.width = pw;
  if (cv.height !== ph) cv.height = ph;
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return { ctx: ctx, w: w, h: h };
}
function fx(v, d) {
  if (!isFinite(v)) return v > 0 ? '∞' : (v < 0 ? '-∞' : 'NaN');
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e5 || a < Math.pow(10, -d))) return v.toExponential(Math.max(1, d - 1));
  return v.toFixed(d);
}
function niceTicks(a, b, n) {
  const span = b - a;
  if (!(span > 0) || !isFinite(span)) return [a];
  const raw = span / Math.max(1, n);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const r = raw / mag;
  const step = mag * (r >= 7.5 ? 10 : r >= 3.5 ? 5 : r >= 1.5 ? 2 : 1);
  const out = [];
  for (let v = Math.ceil(a / step) * step; v <= b + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return out;
}
function tickLabel(v) {
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e4 || a < 1e-3)) return v.toExponential(0);
  return String(+v.toPrecision(4));
}
function makePlot(w, h, xr, yr, pad) {
  pad = pad || { l: 46, r: 12, t: 12, b: 30 };
  const X = function (x) { return pad.l + (x - xr[0]) / (xr[1] - xr[0]) * (w - pad.l - pad.r); };
  const Y = function (y) { return h - pad.b - (y - yr[0]) / (yr[1] - yr[0]) * (h - pad.t - pad.b); };
  return { X: X, Y: Y, pad: pad, w: w, h: h, xr: xr, yr: yr };
}
function drawAxes(ctx, P, opt) {
  opt = opt || {};
  const xf = opt.xfmt || tickLabel, yf = opt.yfmt || tickLabel;
  ctx.save();
  ctx.font = '11px Inter, system-ui, sans-serif';
  ctx.lineWidth = 1;
  const x0 = P.pad.l, x1 = P.w - P.pad.r, y0 = P.pad.t, y1 = P.h - P.pad.b;
  const xt = opt.xticks || niceTicks(P.xr[0], P.xr[1], Math.max(2, Math.floor((x1 - x0) / 70)));
  const yt = opt.yticks || niceTicks(P.yr[0], P.yr[1], Math.max(2, Math.floor((y1 - y0) / 40)));
  ctx.strokeStyle = COLORS.grid; ctx.fillStyle = COLORS.muted;
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  xt.forEach(function (v) { const x = P.X(v); if (x < x0 - 0.5 || x > x1 + 0.5) return; ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y1); ctx.stroke(); ctx.fillText(xf(v), x, y1 + 5); });
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  yt.forEach(function (v) { const y = P.Y(v); if (y < y0 - 0.5 || y > y1 + 0.5) return; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke(); ctx.fillText(yf(v), x0 - 5, y); });
  ctx.strokeStyle = COLORS.axis;
  ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
  ctx.fillStyle = '#cbd5e1';
  if (opt.xlabel) { ctx.textAlign = 'right'; ctx.textBaseline = 'bottom'; ctx.fillText(opt.xlabel, x1, P.h - 1); }
  if (opt.ylabel) { ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillText(opt.ylabel, x0 + 5, y0 + 3); }
  ctx.restore();
}
function clampPx(v) { return Math.max(-1e4, Math.min(1e4, v)); }
function polyline(ctx, P, xs, ys, color, width, dash) {
  ctx.save();
  ctx.beginPath();
  ctx.rect(P.pad.l, P.pad.t, P.w - P.pad.l - P.pad.r, P.h - P.pad.t - P.pad.b);
  ctx.clip();
  ctx.strokeStyle = color; ctx.lineWidth = width || 2; ctx.setLineDash(dash || []);
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < xs.length; i++) {
    if (!isFinite(ys[i]) || !isFinite(xs[i])) { started = false; continue; }
    const x = clampPx(P.X(xs[i])), y = clampPx(P.Y(ys[i]));
    if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.restore();
}
function setChallenge(met, status) {
  const b = $('challenge');
  b.classList.toggle('met', !!met);
  $('challenge-tag').textContent = met ? 'Target met' : 'Challenge';
  $('challenge-status').textContent = status;
}
const Telemetry = (function () {
  const MIN_GAP_MS = 200;
  let last = 0, timer = null, latest = null, solvedOnce = false;
  function post() {
    if (!latest) return;
    last = Date.now();
    const msg = { type: 'HARNESS_DEMO_TELEMETRY', demoId: DEMO_ID, params: latest.params, challengeSolved: latest.solved, summary: latest.summary };
    try { window.parent.postMessage(msg, '*'); } catch (e) { /* parent unavailable: telemetry is best-effort */ }
    const log = $('telemetry-log');
    if (log) log.textContent = 'telemetry → parent: ' + latest.summary + (latest.solved ? '  [challengeSolved]' : '');
  }
  function emit(params, solved, summary) {
    latest = { params: JSON.parse(JSON.stringify(params)), solved: !!solved, summary: String(summary) };
    if (solved && !solvedOnce) {
      solvedOnce = true;
      if (timer) { clearTimeout(timer); timer = null; }
      post();
      return;
    }
    const wait = MIN_GAP_MS - (Date.now() - last);
    if (wait <= 0) {
      if (timer) { clearTimeout(timer); timer = null; }
      post();
    } else if (!timer) {
      timer = setTimeout(function () { timer = null; post(); }, wait);
    }
  }
  return { emit: emit };
})();
function bindSliders(formatters, onInput) {
  Object.keys(formatters).forEach(function (id) {
    const el = $(id), out = $(id + '_out');
    if (!el) return;
    const upd = function () { if (out) out.textContent = formatters[id](parseFloat(el.value)); };
    upd();
    el.addEventListener('input', function () { upd(); onInput(true); });
  });
}
function frameScheduler(fn) {
  let pending = false, userFlag = false;
  return function (fromUser) {
    userFlag = userFlag || !!fromUser;
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; const u = userFlag; userFlag = false; fn(u); });
  };
}
(function () {
  const btn = $('invertBtn');
  if (btn) btn.addEventListener('click', function () {
    document.body.classList.toggle('inverted');
    btn.textContent = document.body.classList.contains('inverted') ? 'Restore colors' : 'Invert colors';
  });
})();
"""


def _slider(sid: str, label: str, mn: float, mx: float, step: float, value: float) -> str:
    return (
        f'<div class="ctl"><label for="{sid}"><span>{label}</span>'
        f'<output id="{sid}_out" for="{sid}"></output></label>'
        f'<input type="range" id="{sid}" min="{mn}" max="{mx}" step="{step}" value="{value}"></div>'
    )


def _page(
    *,
    demo_id: str,
    title: str,
    subtitle: str,
    goal_html: str,
    controls: list[str],
    body: str,
    script: str,
    topic: str = "",
    statement: str = "",
) -> str:
    sub = subtitle
    if topic:
        sub = f"Topic: {_esc(topic)} &middot; " + subtitle
    stmt = ""
    if statement:
        stmt = f'<details class="stmt"><summary>Statement</summary><code>{_esc(statement)}</code></details>'
    prelude = _PRELUDE_JS.replace("__DEMO_ID__", _js_str(demo_id)).replace("__DEMO_TITLE__", _js_str(title))
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n<style>{_CSS}</style>\n</head>\n"
        f'<body data-demo-id="{_esc(demo_id)}">\n<div class="wrap">\n'
        '<div id="challenge" role="status" aria-live="polite"><span class="tag" id="challenge-tag">Challenge</span>'
        f'<span class="goal">{goal_html}</span><span id="challenge-status">Adjust the sliders to begin.</span></div>\n'
        f'<header><div><h1>{_esc(title)}</h1><div class="sub">{sub}</div>{stmt}</div>'
        '<div class="toolbar"><button type="button" id="invertBtn" title="Dark-mode guard">Invert colors</button></div></header>\n'
        f'<div class="controls">{"".join(controls)}</div>\n'
        f"{body}\n"
        '<div class="telemetry" id="telemetry-log">telemetry → parent: (waiting for first slider input)</div>\n'
        "</div>\n"
        f"<script>\n{prelude}\n{script}\n</script>\n"
        "</body>\n</html>\n"
    )


# ---------------------------------------------------------------------------
# Demo 1 - attention logit variance and softmax saturation
# ---------------------------------------------------------------------------

_ATTENTION_JS = r"""
const N_ROWS = 128, N_KEYS = 16, DK_TARGET = 256, J_TARGET = 0.28;
const H_UNIFORM = Math.log(N_KEYS), H_MAX = 0.9 * Math.log(N_KEYS);
const LT_MIN = -1, LT_MAX = 7;
let seed = 1337;
let rawCache = { key: '', data: null };

function readParams() {
  return { d_k: parseInt($('dk').value, 10), tau: Math.pow(2, parseFloat($('logtau').value)), sigma2: parseFloat($('sigma2').value) };
}
// Raw dot products q.k for standard-normal q, k (sigma = 1); the real logits are raw * sigma2 / tau,
// because q_i = sigma z_i and k_i = sigma w_i give q.k = sigma^2 * z.w.
function rawDots(dk) {
  const key = dk + ':' + seed;
  if (rawCache.key === key) return rawCache.data;
  const g = makeGauss(mulberry32(seed));
  const out = new Float64Array(N_ROWS * N_KEYS);
  const q = new Float64Array(dk);
  for (let r = 0; r < N_ROWS; r++) {
    for (let i = 0; i < dk; i++) q[i] = g();
    for (let j = 0; j < N_KEYS; j++) {
      let s = 0;
      for (let i = 0; i < dk; i++) s += q[i] * g();
      out[r * N_KEYS + j] = s;
    }
  }
  rawCache = { key: key, data: out };
  return out;
}
// Mean over rows of ||diag(p) - p p^T||_F and of the softmax entropy.
// ||diag(p) - pp^T||_F^2 = sum p^2 - 2 sum p^3 + (sum p^2)^2.
function softmaxStats(raw, scale, probsOut) {
  const p = new Float64Array(N_KEYS);
  let jSum = 0, hSum = 0;
  for (let r = 0; r < N_ROWS; r++) {
    const o = r * N_KEYS;
    let m = -Infinity;
    for (let j = 0; j < N_KEYS; j++) { const z = raw[o + j] * scale; if (z > m) m = z; }
    let Z = 0;
    for (let j = 0; j < N_KEYS; j++) { const e = Math.exp(raw[o + j] * scale - m); p[j] = e; Z += e; }
    let s2 = 0, s3 = 0, h = 0;
    for (let j = 0; j < N_KEYS; j++) {
      const pj = p[j] / Z; p[j] = pj;
      s2 += pj * pj; s3 += pj * pj * pj;
      if (pj > 0) h -= pj * Math.log(pj);
    }
    jSum += Math.sqrt(Math.max(0, s2 - 2 * s3 + s2 * s2));
    hSum += h;
    if (r === 0 && probsOut) for (let j = 0; j < N_KEYS; j++) probsOut[j] = p[j];
  }
  return { jac: jSum / N_ROWS, ent: hSum / N_ROWS };
}
function compute() {
  const P = readParams();
  const raw = rawDots(P.d_k);
  const scale = P.sigma2 / P.tau;
  const n = raw.length;
  const logits = new Float64Array(n);
  let mean = 0;
  for (let i = 0; i < n; i++) { logits[i] = raw[i] * scale; mean += logits[i]; }
  mean /= n;
  let v = 0;
  for (let i = 0; i < n; i++) v += (logits[i] - mean) * (logits[i] - mean);
  v /= (n - 1);
  const varTheory = P.d_k * P.sigma2 * P.sigma2 / (P.tau * P.tau);
  const probs = new Float64Array(N_KEYS);
  const st = softmaxStats(raw, scale, probs);
  const sweep = [];
  for (let i = 0; i <= 80; i++) {
    const lt = LT_MIN + (LT_MAX - LT_MIN) * i / 80;
    const s = softmaxStats(raw, P.sigma2 / Math.pow(2, lt), null);
    sweep.push({ lt: lt, jac: s.jac, ent: s.ent });
  }
  const met = P.d_k === DK_TARGET && st.jac >= J_TARGET && st.ent <= H_MAX;
  return { P: P, logits: logits, mean: mean, varEmp: v, varTheory: varTheory, probs: probs, jac: st.jac, ent: st.ent, sweep: sweep, met: met };
}
function drawHistogram(S) {
  const c = fitCanvas($('histCanvas')), ctx = c.ctx;
  const sd = Math.sqrt(Math.max(S.varTheory, S.varEmp, 1e-12));
  const R = Math.max(5, 3.6 * sd);
  const nb = 48, bw = 2 * R / nb, counts = new Array(nb).fill(0);
  let overflow = 0;
  for (let i = 0; i < S.logits.length; i++) {
    const b = Math.floor((S.logits[i] + R) / bw);
    if (b < 0 || b >= nb) overflow++; else counts[b]++;
  }
  const pdfPeak = S.logits.length * bw / (Math.sqrt(2 * Math.PI * Math.max(S.varTheory, 1e-12)));
  const ymax = Math.max(1, Math.max.apply(null, counts), Math.min(pdfPeak, 1.6 * Math.max.apply(null, counts) + 1)) * 1.12;
  const P = makePlot(c.w, c.h, [-R, R], [0, ymax]);
  // softmax-sensitive band |logit| <= 3
  ctx.fillStyle = 'rgba(16,185,129,0.10)';
  const bx0 = P.X(Math.max(-3, -R)), bx1 = P.X(Math.min(3, R));
  ctx.fillRect(bx0, P.pad.t, bx1 - bx0, c.h - P.pad.t - P.pad.b);
  drawAxes(ctx, P, { xlabel: 'logit  q·k / τ', ylabel: 'count (' + S.logits.length + ' logits)' });
  ctx.fillStyle = 'rgba(99,102,241,0.75)';
  for (let b = 0; b < nb; b++) {
    if (!counts[b]) continue;
    const x0 = P.X(-R + b * bw), x1 = P.X(-R + (b + 1) * bw);
    const y = P.Y(counts[b]);
    ctx.fillRect(x0 + 0.5, y, Math.max(1, x1 - x0 - 1), P.Y(0) - y);
  }
  const xs = [], ys = [];
  for (let i = 0; i <= 200; i++) {
    const x = -R + 2 * R * i / 200;
    xs.push(x);
    ys.push(S.logits.length * bw * Math.exp(-x * x / (2 * S.varTheory)) / Math.sqrt(2 * Math.PI * S.varTheory));
  }
  polyline(ctx, P, xs, ys, COLORS.amber, 2);
  ctx.fillStyle = COLORS.emerald; ctx.font = '11px Inter, system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.fillText('|logit| ≤ 3', (bx0 + bx1) / 2, P.pad.t + 4);
  if (overflow > 0) { ctx.fillStyle = COLORS.muted; ctx.textAlign = 'right'; ctx.fillText(overflow + ' outside view', c.w - P.pad.r - 4, P.pad.t + 4); }
}
function drawSweep(S) {
  const c = fitCanvas($('sweepCanvas')), ctx = c.ctx;
  const P = makePlot(c.w, c.h, [LT_MIN, LT_MAX], [0, 1.0], { l: 40, r: 10, t: 12, b: 30 });
  drawAxes(ctx, P, { xlabel: 'log₂ τ', ylabel: '' , xticks: [-1, 0, 1, 2, 3, 4, 5, 6, 7] });
  // challenge-feasible tau band (computed from the sampled curves)
  ctx.fillStyle = 'rgba(16,185,129,0.10)';
  for (let i = 0; i < S.sweep.length - 1; i++) {
    const a = S.sweep[i];
    if (a.jac >= J_TARGET && a.ent <= H_MAX) { const x0 = P.X(a.lt), x1 = P.X(S.sweep[i + 1].lt); ctx.fillRect(x0, P.pad.t, x1 - x0, c.h - P.pad.t - P.pad.b); }
  }
  const xs = S.sweep.map(function (s) { return s.lt; });
  polyline(ctx, P, [LT_MIN, LT_MAX], [J_TARGET / 0.5, J_TARGET / 0.5], COLORS.amber, 1.2, [5, 4]);
  polyline(ctx, P, xs, S.sweep.map(function (s) { return s.jac / 0.5; }), COLORS.indigo, 2.2);
  polyline(ctx, P, xs, S.sweep.map(function (s) { return s.ent / H_UNIFORM; }), COLORS.emerald, 2);
  const xc = P.X(Math.log2(S.P.tau));
  ctx.strokeStyle = COLORS.text; ctx.lineWidth = 1.2; ctx.setLineDash([3, 3]);
  ctx.beginPath(); ctx.moveTo(xc, P.pad.t); ctx.lineTo(xc, c.h - P.pad.b); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = COLORS.indigo; ctx.beginPath(); ctx.arc(xc, P.Y(S.jac / 0.5), 4, 0, 2 * Math.PI); ctx.fill();
  ctx.fillStyle = COLORS.emerald; ctx.beginPath(); ctx.arc(xc, P.Y(S.ent / H_UNIFORM), 4, 0, 2 * Math.PI); ctx.fill();
  const xIdeal = Math.log2(Math.sqrt(S.P.d_k) * S.P.sigma2);
  if (xIdeal >= LT_MIN && xIdeal <= LT_MAX) {
    ctx.fillStyle = COLORS.amber; ctx.font = '10.5px Inter, system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.fillText('√dₖ·σ²', P.X(xIdeal), c.h - P.pad.b - 14);
  }
}
function drawBars(S) {
  const c = fitCanvas($('barCanvas')), ctx = c.ctx;
  const P = makePlot(c.w, c.h, [0, N_KEYS], [0, 1], { l: 40, r: 10, t: 12, b: 30 });
  drawAxes(ctx, P, { xlabel: 'key j (row 0)', ylabel: 'p_j', xticks: [0, 4, 8, 12, 16] });
  for (let j = 0; j < N_KEYS; j++) {
    const x0 = P.X(j), x1 = P.X(j + 1), y = P.Y(S.probs[j]);
    ctx.fillStyle = S.probs[j] > 0.5 ? COLORS.amber : COLORS.emerald;
    ctx.fillRect(x0 + 1.5, y, Math.max(1, x1 - x0 - 3), P.Y(0) - y);
  }
  polyline(ctx, P, [0, N_KEYS], [1 / N_KEYS, 1 / N_KEYS], COLORS.muted, 1, [4, 4]);
}
function summaryOf(S) {
  return 'User tuned d_k=' + S.P.d_k + ', tau=' + S.P.tau.toFixed(2) + ', sigma2=' + S.P.sigma2.toFixed(2) +
    ' -> Var(q.k/tau)=' + fx(S.varEmp, 3) + ' (theory d_k*sigma^4/tau^2=' + fx(S.varTheory, 3) + '), mean ||J_softmax||_F=' +
    S.jac.toFixed(3) + ', entropy=' + S.ent.toFixed(2) + ' nats' + (S.met ? ' [challenge met]' : '');
}
function render(fromUser) {
  const S = compute();
  drawHistogram(S); drawSweep(S); drawBars(S);
  $('st_var').textContent = fx(S.varEmp, 3);
  $('st_vth').textContent = fx(S.varTheory, 3);
  $('st_jac').textContent = S.jac.toFixed(3);
  $('st_ent').textContent = S.ent.toFixed(2) + ' / ' + H_UNIFORM.toFixed(2);
  $('st_ideal').textContent = (Math.sqrt(S.P.d_k) * S.P.sigma2).toFixed(2);
  const dkOk = S.P.d_k === DK_TARGET, jOk = S.jac >= J_TARGET, hOk = S.ent <= H_MAX;
  setChallenge(S.met, (dkOk ? '✓' : '✗') + ' d_k = ' + S.P.d_k + ' (need 256)   ' +
    (jOk ? '✓' : '✗') + ' mean ‖J‖_F = ' + S.jac.toFixed(3) + ' (need ≥ ' + J_TARGET + ')   ' +
    (hOk ? '✓' : '✗') + ' H = ' + S.ent.toFixed(2) + ' nats (need ≤ ' + H_MAX.toFixed(2) + ')');
  if (fromUser) Telemetry.emit(S.P, S.met, summaryOf(S));
}
const schedule = frameScheduler(render);
bindSliders({
  dk: function (v) { return String(v | 0); },
  logtau: function (v) { return 'τ = ' + Math.pow(2, v).toFixed(2); },
  sigma2: function (v) { return v.toFixed(2); }
}, schedule);
$('resample').addEventListener('click', function () { seed = (seed * 1103515245 + 12345) >>> 0; schedule(true); });
window.addEventListener('resize', function () { schedule(false); });
render(false);
"""


def _attention_html(demo_id: str, title: str, topic: str = "", statement: str = "") -> str:
    goal = (
        "At <b>d<sub>k</sub> = 256</b>, restore non-vanishing softmax gradients: make the mean "
        "&#8214;diag(p) &minus; pp<sup>T</sup>&#8214;<sub>F</sub> &ge; 0.28 (saturated rows give &asymp; 0.10) "
        "while attention stays non-uniform (entropy H &le; 0.9&middot;ln 16). "
        "Hint: Var(q&middot;k/&tau;) = d<sub>k</sub>&sigma;<sup>4</sup>/&tau;<sup>2</sup>."
    )
    controls = [
        _slider("dk", "key dimension d<sub>k</sub>", 1, 512, 1, 64),
        _slider("logtau", "temperature (log<sub>2</sub> &tau;)", -1, 7, 0.01, 0),
        _slider("sigma2", "input variance &sigma;<sup>2</sup>", 0.25, 4, 0.05, 1),
    ]
    body = (
        '<div class="panel"><h3>Empirical distribution of logits q&middot;k/&tau; '
        "(q, k &sim; N(0, &sigma;<sup>2</sup>I) i.i.d., seeded) with the N(0, d<sub>k</sub>&sigma;<sup>4</sup>/&tau;<sup>2</sup>) density</h3>"
        '<canvas id="histCanvas"></canvas>'
        '<div class="stats"><span>Var empirical <b id="st_var"></b></span>'
        '<span>Var theory <b id="st_vth"></b></span>'
        '<span>mean &#8214;J&#8214;<sub>F</sub> <b id="st_jac"></b></span>'
        '<span>mean entropy <b id="st_ent"></b> nats</span>'
        '<span>&radic;d<sub>k</sub>&middot;&sigma;<sup>2</sup> = <b id="st_ideal"></b></span>'
        '<button type="button" id="resample">Resample</button></div></div>'
        '<div class="grid2 row"><div class="panel"><h3>Softmax Jacobian norm and entropy across &tau; '
        "(16-way rows, 128 rows averaged)</h3>"
        '<canvas id="sweepCanvas" class="short"></canvas>'
        '<div class="legend"><span><i class="sw" style="background:#6366f1"></i>&#8214;J&#8214;<sub>F</sub> / 0.5</span>'
        '<span><i class="sw" style="background:#10b981"></i>H / ln 16</span>'
        '<span><i class="sw" style="background:#f59e0b"></i>target &#8214;J&#8214;<sub>F</sub> = 0.28; green band: challenge-feasible &tau;</span></div></div>'
        '<div class="panel"><h3>Softmax probabilities of one row (16 keys)</h3>'
        '<canvas id="barCanvas" class="short"></canvas>'
        '<div class="hint">Saturated rows collapse to one-hot (amber bar), so diag(p) &minus; pp<sup>T</sup> &rarr; 0 and gradients vanish.</div></div></div>'
    )
    return _page(
        demo_id=demo_id,
        title=title,
        subtitle="Scaled dot-product attention: why we divide by &radic;d<sub>k</sub>",
        goal_html=goal,
        controls=controls,
        body=body,
        script=_ATTENTION_JS,
        topic=topic,
        statement=statement,
    )


# ---------------------------------------------------------------------------
# Demo 2 - heavy-ball momentum on an anisotropic quadratic
# ---------------------------------------------------------------------------

_SGD_JS = r"""
const X0 = [-4, 2], TOL_REL = 1e-3, T_MAX = 600, KAPPA_TARGET = 50, N_TARGET = 60;
let sim = null, shown = 0, animHandle = 0;

function readParams() {
  return { eta: parseFloat($('eta').value), beta: parseFloat($('beta').value), kappa: parseFloat($('kappa').value) };
}
// Heavy ball: v_{t+1} = beta v_t - eta grad f(x_t), x_{t+1} = x_t + v_{t+1}, f = 0.5 (x^2 + kappa y^2).
function simulate(P) {
  let x = X0[0], y = X0[1], vx = 0, vy = 0;
  const n0 = Math.hypot(x, y);
  const pts = [[x, y]], fs = [0.5 * (x * x + P.kappa * y * y)];
  let diverged = false, lastOut = 0;
  for (let t = 1; t <= T_MAX; t++) {
    vx = P.beta * vx - P.eta * x;
    vy = P.beta * vy - P.eta * P.kappa * y;
    x += vx; y += vy;
    const n = Math.hypot(x, y);
    pts.push([x, y]); fs.push(0.5 * (x * x + P.kappa * y * y));
    if (!isFinite(n) || n > 1e6) { diverged = true; lastOut = t; break; }
    if (n >= TOL_REL * n0) lastOut = t;
  }
  const converged = !diverged && lastOut < T_MAX;
  const bound = 2 * (1 + P.beta) / P.kappa;
  return { P: P, pts: pts, fs: fs, diverged: diverged, converged: converged, iters: converged ? lastOut + 1 : null, bound: bound, unstable: P.eta > bound };
}
function iterText(s) {
  if (s.diverged) return 'diverged';
  if (!s.converged) return 'not converged in ' + T_MAX;
  return s.iters + ' iterations';
}
function isMet(s) { return s.P.kappa === KAPPA_TARGET && s.converged && s.iters <= N_TARGET; }
function drawContour() {
  const c = fitCanvas($('contourCanvas')), ctx = c.ctx;
  const sc = Math.min(c.w / 10.6, c.h / 6.4), cx = c.w / 2, cy = c.h / 2;
  const toX = function (x) { return clampPx(cx + x * sc); }, toY = function (y) { return clampPx(cy - y * sc); };
  const k = sim.P.kappa;
  ctx.save();
  ctx.strokeStyle = COLORS.grid; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(c.w, cy); ctx.moveTo(cx, 0); ctx.lineTo(cx, c.h); ctx.stroke();
  for (let j = 0; j < 22; j++) {
    const r = 0.35 * Math.pow(1.33, j);
    const t = j / 21;
    ctx.strokeStyle = 'rgba(' + Math.round(99 + 146 * t) + ',' + Math.round(102 + 56 * t) + ',' + Math.round(241 - 230 * t) + ',0.55)';
    ctx.beginPath(); ctx.ellipse(cx, cy, r * sc, r / Math.sqrt(k) * sc, 0, 0, 2 * Math.PI); ctx.stroke();
  }
  ctx.fillStyle = COLORS.muted; ctx.font = '11px Inter, system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  ctx.fillText('f(x, y) = ½(x² + κ y²),  κ = ' + k, 8, 6);
  const upto = Math.min(shown, sim.pts.length - 1);
  ctx.strokeStyle = sim.diverged ? COLORS.red : COLORS.amber; ctx.lineWidth = 1.8;
  ctx.beginPath(); ctx.moveTo(toX(sim.pts[0][0]), toY(sim.pts[0][1]));
  for (let i = 1; i <= upto; i++) ctx.lineTo(toX(sim.pts[i][0]), toY(sim.pts[i][1]));
  ctx.stroke();
  ctx.fillStyle = sim.diverged ? COLORS.red : COLORS.amber;
  const dotStep = Math.max(1, Math.ceil(upto / 80));
  for (let i = 0; i <= upto; i += dotStep) { ctx.beginPath(); ctx.arc(toX(sim.pts[i][0]), toY(sim.pts[i][1]), 2, 0, 2 * Math.PI); ctx.fill(); }
  ctx.fillStyle = COLORS.emerald; ctx.beginPath(); ctx.arc(cx, cy, 4, 0, 2 * Math.PI); ctx.fill();
  ctx.fillStyle = COLORS.text; ctx.beginPath(); ctx.arc(toX(X0[0]), toY(X0[1]), 4, 0, 2 * Math.PI); ctx.fill();
  ctx.fillText('x₀', toX(X0[0]) + 6, toY(X0[1]) - 4);
  ctx.textAlign = 'right'; ctx.fillStyle = COLORS.muted;
  ctx.fillText('t = ' + upto, c.w - 8, 6);
  ctx.restore();
}
function drawLoss() {
  const c = fitCanvas($('lossCanvas')), ctx = c.ctx;
  const n = sim.fs.length;
  const lf = sim.fs.map(function (f) { return Math.log10(Math.max(f, 1e-30)); });
  const ymax = Math.max(2, Math.ceil(Math.max.apply(null, lf.slice(0, Math.min(n, 400)))));
  const P = makePlot(c.w, c.h, [0, Math.max(20, Math.min(T_MAX, sim.converged ? sim.iters + 20 : n - 1))], [-12, Math.min(ymax, 14)], { l: 40, r: 10, t: 12, b: 30 });
  drawAxes(ctx, P, { xlabel: 'iteration t', ylabel: 'log₁₀ f(xₜ)' });
  const tolF = Math.log10(0.5 * Math.pow(TOL_REL * Math.hypot(X0[0], X0[1]), 2));
  polyline(ctx, P, [0, T_MAX], [tolF, tolF], COLORS.emerald, 1, [4, 4]);
  polyline(ctx, P, [N_TARGET, N_TARGET], [-12, 14], COLORS.muted, 1, [2, 4]);
  const upto = Math.min(shown, n - 1);
  const xs = [], ys = [];
  for (let i = 0; i <= upto; i++) { xs.push(i); ys.push(lf[i]); }
  polyline(ctx, P, xs, ys, sim.diverged ? COLORS.red : COLORS.indigo, 2);
}
function draw() { drawContour(); drawLoss(); }
function animate() {
  cancelAnimationFrame(animHandle);
  shown = 0;
  const end = sim.diverged ? sim.pts.length - 1 : (sim.converged ? Math.min(sim.pts.length - 1, sim.iters + 10) : Math.min(sim.pts.length - 1, 300));
  const stepPerFrame = Math.max(1, Math.ceil(end / 110));
  const tick = function () {
    shown = Math.min(end, shown + stepPerFrame);
    draw();
    if (shown < end) animHandle = requestAnimationFrame(tick);
  };
  animHandle = requestAnimationFrame(tick);
}
function summaryOf(s) {
  return 'User tuned eta=' + s.P.eta.toFixed(3) + ', beta=' + s.P.beta.toFixed(2) + ', kappa=' + s.P.kappa +
    ' -> ' + (s.diverged ? 'diverged' : (s.converged ? 'converged in ' + s.iters + ' iterations' : 'not converged within ' + T_MAX + ' iterations')) +
    ' (stability bound 2(1+beta)/kappa=' + s.bound.toFixed(4) + (s.unstable ? ', eta exceeds it' : '') + ')' + (isMet(s) ? ' [challenge met]' : '');
}
function update(fromUser) {
  const P = readParams();
  sim = simulate(P);
  const met = isMet(sim);
  $('st_iters').textContent = iterText(sim);
  $('st_bound').textContent = sim.bound.toFixed(4);
  const sk = Math.sqrt(P.kappa);
  $('st_eta_opt').textContent = (4 / Math.pow(sk + 1, 2)).toFixed(4);
  $('st_beta_opt').textContent = Math.pow((sk - 1) / (sk + 1), 2).toFixed(3);
  $('st_rate').textContent = Math.max(Math.abs(1 - P.eta), Math.abs(1 - P.eta * P.kappa)).toFixed(4);
  const w = $('divWarn');
  w.classList.toggle('on', sim.unstable);
  w.textContent = sim.unstable ? ('Divergence warning: η = ' + P.eta.toFixed(3) + ' > 2(1+β)/κ = ' + sim.bound.toFixed(4) +
    '. The stiff y-direction (curvature κ) has |eigenvalue| > 1 and the iterates blow up.') : '';
  const kOk = P.kappa === KAPPA_TARGET, nOk = sim.converged && sim.iters <= N_TARGET;
  setChallenge(met, (kOk ? '✓' : '✗') + ' κ = ' + P.kappa + ' (need 50)   ' +
    (nOk ? '✓' : '✗') + ' converged: ' + iterText(sim) + ' (need ≤ ' + N_TARGET + ')');
  animate();
  if (fromUser) Telemetry.emit(P, met, summaryOf(sim));
}
const schedule = frameScheduler(update);
bindSliders({
  eta: function (v) { return v.toFixed(3); },
  beta: function (v) { return v.toFixed(2); },
  kappa: function (v) { return String(v | 0); }
}, schedule);
$('replay').addEventListener('click', function () { animate(); });
window.addEventListener('resize', function () { if (sim) draw(); });
update(false);
"""


def _sgd_html(demo_id: str, title: str, topic: str = "", statement: str = "") -> str:
    goal = (
        "On the ill-conditioned bowl <b>&kappa; = 50</b>, reach &#8214;x<sub>t</sub>&#8214; &le; 10<sup>&minus;3</sup>&#8214;x<sub>0</sub>&#8214; "
        "(and stay there) within <b>60 iterations</b>. Plain gradient descent needs about 170 at best &mdash; use momentum."
    )
    controls = [
        _slider("eta", "learning rate &eta;", 0.001, 0.25, 0.001, 0.03),
        _slider("beta", "momentum &beta;", 0, 0.99, 0.01, 0),
        _slider("kappa", "Hessian condition number &kappa;", 1, 100, 1, 10),
    ]
    body = (
        '<div class="panel"><h3>Heavy-ball trajectory on the level sets of f '
        "(each ellipse is a level set {f = c}: the covector df stacks them more densely along the stiff axis)</h3>"
        '<canvas id="contourCanvas"></canvas>'
        '<div class="warn" id="divWarn"></div>'
        '<div class="stats"><span>iterations to converge <b id="st_iters"></b></span>'
        '<span>stability bound 2(1+&beta;)/&kappa; <b id="st_bound"></b></span>'
        '<span>plain-GD contraction factor max|1&minus;&eta;&lambda;| <b id="st_rate"></b></span>'
        '<button type="button" id="replay">Replay</button></div>'
        '<details class="hint"><summary>Theory hint (Polyak heavy ball)</summary>'
        'For eigenvalues in [1, &kappa;] the optimal parameters are &eta;* = 4/(&radic;&kappa;+1)<sup>2</sup> = <b id="st_eta_opt"></b> '
        'and &beta;* = ((&radic;&kappa;&minus;1)/(&radic;&kappa;+1))<sup>2</sup> = <b id="st_beta_opt"></b>, giving rate &radic;&beta;* '
        'instead of (&kappa;&minus;1)/(&kappa;+1) for gradient descent.</details></div>'
        '<div class="panel"><h3>Loss curve log<sub>10</sub> f(x<sub>t</sub>) (green dashed: convergence tolerance, grey dotted: t = 60)</h3>'
        '<canvas id="lossCanvas" class="short"></canvas></div>'
    )
    return _page(
        demo_id=demo_id,
        title=title,
        subtitle="Gradient descent with momentum on f(x, y) = &frac12;(x<sup>2</sup> + &kappa;y<sup>2</sup>)",
        goal_html=goal,
        controls=controls,
        body=body,
        script=_SGD_JS,
        topic=topic,
        statement=statement,
    )


# ---------------------------------------------------------------------------
# Demo 3 - RoPE relative rotation + Bellman sup-norm contraction funnel
# ---------------------------------------------------------------------------

_ROPE_BELLMAN_JS = r"""
const MODE = __MODE__;
const HAS_ROPE = MODE !== 'bellman', HAS_BELLMAN = MODE !== 'rope';
const QA = 15 * Math.PI / 180, KA = 60 * Math.PI / 180, QN = 1.0, KN = 0.85;
const ROPE_M_MIN = 5, ROPE_COS_TOL = 0.03;
const GAMMA_MIN = 0.75, K_CHECK = 20, RATIO_TARGET = 0.01, K_MAX = 40;
// 3-state, 2-action MDP: R[s][a], P[s][a][s'].
const R = [[1.0, 0.0], [0.0, 2.0], [-1.0, 0.5]];
const PT = [
  [[0.9, 0.1, 0.0], [0.2, 0.8, 0.0]],
  [[0.0, 0.6, 0.4], [0.1, 0.0, 0.9]],
  [[0.5, 0.0, 0.5], [0.0, 0.3, 0.7]]
];
const STATE_COLORS = [COLORS.indigo, COLORS.emerald, COLORS.amber];

function num(id, dflt) { const el = $(id); return el ? parseFloat(el.value) : dflt; }
function readParams() {
  const p = {};
  if (HAS_ROPE) { p.m = num('m', 0) | 0; p.n = num('n', 0) | 0; p.theta = num('theta', 0.3); }
  if (HAS_BELLMAN) { p.gamma = num('gamma', 0.9); if ($('v0')) p.v0 = num('v0', 0); }
  return p;
}
function ang(a) { let d = a % (2 * Math.PI); if (d > Math.PI) d -= 2 * Math.PI; if (d <= -Math.PI) d += 2 * Math.PI; return d; }
function ropeState(P) {
  const aq = QA + P.m * P.theta, ak = KA + P.n * P.theta;
  const d = ang(ak - aq);
  const delta = P.n - P.m;
  return { aq: aq, ak: ak, d: d, delta: delta, cos: Math.cos(d), dot: QN * KN * Math.cos(ak - aq),
    refDot: QN * KN * Math.cos(KA + delta * P.theta - QA), angDeg: Math.abs(d) * 180 / Math.PI };
}
function bellmanOp(V, gamma) {
  const out = [0, 0, 0];
  for (let s = 0; s < 3; s++) {
    let best = -Infinity;
    for (let a = 0; a < 2; a++) {
      let q = R[s][a];
      for (let s2 = 0; s2 < 3; s2++) q += gamma * PT[s][a][s2] * V[s2];
      if (q > best) best = q;
    }
    out[s] = best;
  }
  return out;
}
function supNorm(U, V) { let m = 0; for (let i = 0; i < U.length; i++) m = Math.max(m, Math.abs(U[i] - V[i])); return m; }
function bellmanState(P) {
  let V = [0, 0, 0];
  for (let i = 0; i < 100000; i++) { const W = bellmanOp(V, P.gamma); const d = supNorm(W, V); V = W; if (d < 1e-13) break; }
  const vstar = V;
  const c = P.v0 || 0;
  const traj = [[c, c, c]];
  for (let k = 1; k <= K_MAX; k++) traj.push(bellmanOp(traj[k - 1], P.gamma));
  const errs = traj.map(function (Vk) { return supNorm(Vk, vstar); });
  const e0 = errs[0];
  const ratio = e0 > 0 ? errs[K_CHECK] / e0 : 0;
  return { vstar: vstar, traj: traj, errs: errs, e0: e0, ratio: ratio, env: Math.pow(P.gamma, K_CHECK) };
}
function svgArrowDefs() {
  const mk = function (id, col) { return '<marker id="' + id + '" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="' + col + '"/></marker>'; };
  return '<defs>' + mk('ah-indigo', COLORS.indigo) + mk('ah-emerald', COLORS.emerald) + mk('ah-amber', COLORS.amber) + mk('ah-muted', '#64748b') + '</defs>';
}
function vec(cx, cy, r, a, col, marker, dash, width) {
  return '<line x1="' + cx + '" y1="' + cy + '" x2="' + (cx + r * Math.cos(a)).toFixed(2) + '" y2="' + (cy - r * Math.sin(a)).toFixed(2) +
    '" stroke="' + col + '" stroke-width="' + (width || 2.6) + '"' + (dash ? ' stroke-dasharray="' + dash + '"' : '') + ' marker-end="url(#' + marker + ')"/>';
}
function label(x, y, txt, col, size, anchor) {
  return '<text x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" fill="' + col + '" font-size="' + (size || 12) + '" text-anchor="' + (anchor || 'middle') + '" font-family="Inter, system-ui, sans-serif">' + txt + '</text>';
}
function drawRope(P, S) {
  const cx = 180, cy = 140, Rr = 100;
  const parts = [svgArrowDefs()];
  parts.push('<rect x="0" y="0" width="360" height="300" fill="#0f172a"/>');
  parts.push('<circle cx="' + cx + '" cy="' + cy + '" r="' + Rr + '" fill="none" stroke="#1e293b" stroke-width="1.5"/>');
  parts.push('<line x1="' + (cx - Rr - 12) + '" y1="' + cy + '" x2="' + (cx + Rr + 12) + '" y2="' + cy + '" stroke="#334155"/>');
  parts.push('<line x1="' + cx + '" y1="' + (cy - Rr - 12) + '" x2="' + cx + '" y2="' + (cy + Rr + 12) + '" stroke="#334155"/>');
  // reference pair at positions (0, n - m)
  parts.push(vec(cx, cy, Rr * QN, QA, '#64748b', 'ah-muted', '4 3', 1.6));
  parts.push(vec(cx, cy, Rr * KN, KA + S.delta * P.theta, COLORS.amber, 'ah-amber', '5 4', 1.8));
  // rotated pair at positions (m, n)
  parts.push(vec(cx, cy, Rr * QN, S.aq, COLORS.indigo, 'ah-indigo'));
  parts.push(vec(cx, cy, Rr * KN, S.ak, COLORS.emerald, 'ah-emerald'));
  const ra = 30, a0 = S.aq, a1 = S.aq + S.d;
  const sweep = S.d > 0 ? 0 : 1;
  parts.push('<path d="M' + (cx + ra * Math.cos(a0)).toFixed(2) + ',' + (cy - ra * Math.sin(a0)).toFixed(2) + ' A' + ra + ',' + ra + ' 0 0 ' + sweep + ' ' +
    (cx + ra * Math.cos(a1)).toFixed(2) + ',' + (cy - ra * Math.sin(a1)).toFixed(2) + '" fill="none" stroke="#f8fafc" stroke-width="1.5"/>');
  const am = S.aq + S.d / 2;
  parts.push(label(cx + 46 * Math.cos(am), cy - 46 * Math.sin(am) + 4, S.angDeg.toFixed(1) + '°', '#f8fafc', 11));
  parts.push(label(cx + (Rr * QN + 16) * Math.cos(S.aq), cy - (Rr * QN + 16) * Math.sin(S.aq) + 4, 'Rₘq', COLORS.indigo, 12));
  parts.push(label(cx + (Rr * KN + 16) * Math.cos(S.ak), cy - (Rr * KN + 16) * Math.sin(S.ak) + 4, 'Rₙk', COLORS.emerald, 12));
  parts.push(label(10, 262, '⟨Rₘq, Rₙk⟩ = ' + S.dot.toFixed(4), COLORS.text, 12, 'start'));
  parts.push(label(10, 280, '⟨q, Rₙ₋ₘk⟩ = ' + S.refDot.toFixed(4) + '   (n−m = ' + S.delta + ')', COLORS.amber, 12, 'start'));
  parts.push(label(350, 18, 'm=' + P.m + ', n=' + P.n + ', θ=' + P.theta.toFixed(3), COLORS.muted, 11, 'end'));
  parts.push(label(10, 18, 'grey/amber: positions (0, n−m)', COLORS.muted, 10.5, 'start'));
  $('ropeSvg').innerHTML = parts.join('');
}
function drawRopeStrip(P, S) {
  const c = fitCanvas($('ropeCanvas')), ctx = c.ctx;
  const Pl = makePlot(c.w, c.h, [-20, 20], [-1, 1], { l: 40, r: 10, t: 10, b: 28 });
  drawAxes(ctx, Pl, { xlabel: 'relative offset n − m', ylabel: 'q·k after RoPE', yticks: [-1, -0.5, 0, 0.5, 1] });
  const xs = [], ys = [];
  for (let i = 0; i <= 400; i++) { const d = -20 + 40 * i / 400; xs.push(d); ys.push(QN * KN * Math.cos(KA - QA + d * P.theta)); }
  polyline(ctx, Pl, xs, ys, COLORS.violet, 1.6);
  for (let d = -20; d <= 20; d++) {
    const y = QN * KN * Math.cos(KA - QA + d * P.theta);
    ctx.fillStyle = d === S.delta ? COLORS.amber : '#475569';
    ctx.beginPath(); ctx.arc(Pl.X(d), Pl.Y(y), d === S.delta ? 5 : 2.4, 0, 2 * Math.PI); ctx.fill();
  }
  polyline(ctx, Pl, [-20, 20], [0, 0], COLORS.emerald, 1, [3, 3]);
}
function drawBellman(P, B) {
  const x0 = 50, x1 = 346, y0 = 28, y1 = 246;
  const top = Math.ceil(Math.log10(Math.max(B.e0, 1e-6) * 1.05)), bot = top - 8;
  const X = function (k) { return x0 + (x1 - x0) * k / K_MAX; };
  const Y = function (e) { const l = Math.log10(Math.max(e, Math.pow(10, bot))); return y1 - (y1 - y0) * (l - bot) / (top - bot); };
  const parts = ['<rect x="0" y="0" width="360" height="300" fill="#0f172a"/>'];
  for (let d = bot; d <= top; d++) {
    const y = Y(Math.pow(10, d));
    parts.push('<line x1="' + x0 + '" y1="' + y.toFixed(1) + '" x2="' + x1 + '" y2="' + y.toFixed(1) + '" stroke="#1e293b"/>');
    parts.push(label(x0 - 5, y + 4, '1e' + d, COLORS.muted, 10, 'end'));
  }
  for (let k = 0; k <= K_MAX; k += 10) {
    parts.push('<line x1="' + X(k) + '" y1="' + y0 + '" x2="' + X(k) + '" y2="' + y1 + '" stroke="#1e293b"/>');
    parts.push(label(X(k), y1 + 15, String(k), COLORS.muted, 10));
  }
  // funnel: region under the gamma^k envelope
  const env = [];
  for (let k = 0; k <= K_MAX; k++) env.push([X(k), Y(B.e0 * Math.pow(P.gamma, k))]);
  const poly = env.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ') + ' ' + X(K_MAX) + ',' + y1 + ' ' + X(0) + ',' + y1;
  parts.push('<polygon points="' + poly + '" fill="rgba(139,92,246,0.16)" stroke="none"/>');
  parts.push('<polyline points="' + env.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ') + '" fill="none" stroke="' + COLORS.violet + '" stroke-width="2"/>');
  const yT = Y(B.e0 * RATIO_TARGET);
  parts.push('<line x1="' + x0 + '" y1="' + yT.toFixed(1) + '" x2="' + x1 + '" y2="' + yT.toFixed(1) + '" stroke="' + COLORS.emerald + '" stroke-dasharray="5 4"/>');
  parts.push('<line x1="' + X(K_CHECK) + '" y1="' + y0 + '" x2="' + X(K_CHECK) + '" y2="' + y1 + '" stroke="#64748b" stroke-dasharray="2 4"/>');
  const pts = B.errs.map(function (e, k) { return X(k).toFixed(1) + ',' + Y(e).toFixed(1); });
  parts.push('<polyline points="' + pts.join(' ') + '" fill="none" stroke="' + COLORS.indigo + '" stroke-width="2"/>');
  B.errs.forEach(function (e, k) { parts.push('<circle cx="' + X(k).toFixed(1) + '" cy="' + Y(e).toFixed(1) + '" r="' + (k === K_CHECK ? 4.5 : 2.4) + '" fill="' + (k === K_CHECK ? COLORS.amber : COLORS.indigo) + '"/>'); });
  parts.push('<rect x="' + x0 + '" y="' + y0 + '" width="' + (x1 - x0) + '" height="' + (y1 - y0) + '" fill="none" stroke="#334155"/>');
  parts.push(label(x1, 18, 'γ = ' + P.gamma.toFixed(2) + '   envelope γᵏ‖V₀−V*‖∞', COLORS.violet, 11, 'end'));
  parts.push(label(x0, 18, '‖Vₖ − V*‖∞', COLORS.indigo, 11, 'start'));
  parts.push(label((x0 + x1) / 2, 278, 'value-iteration step k', COLORS.muted, 11));
  parts.push(label(10, 296, 'k=20: ratio ' + fx(B.ratio, 4) + ' vs γ²⁰ = ' + fx(B.env, 4), COLORS.text, 11, 'start'));
  $('bellmanSvg').innerHTML = parts.join('');
}
function drawBellmanStrip(P, B) {
  const c = fitCanvas($('bellmanCanvas')), ctx = c.ctx;
  let lo = Infinity, hi = -Infinity;
  B.traj.forEach(function (V) { V.forEach(function (v) { lo = Math.min(lo, v); hi = Math.max(hi, v); }); });
  B.vstar.forEach(function (v) { lo = Math.min(lo, v); hi = Math.max(hi, v); });
  const padv = Math.max(0.5, 0.08 * (hi - lo));
  const Pl = makePlot(c.w, c.h, [0, K_MAX], [lo - padv, hi + padv], { l: 44, r: 10, t: 10, b: 28 });
  drawAxes(ctx, Pl, { xlabel: 'k', ylabel: 'Vₖ(s) → V*(s)' });
  for (let s = 0; s < 3; s++) {
    polyline(ctx, Pl, [0, K_MAX], [B.vstar[s], B.vstar[s]], STATE_COLORS[s], 1, [4, 4]);
    const xs = [], ys = [];
    for (let k = 0; k <= K_MAX; k++) { xs.push(k); ys.push(B.traj[k][s]); }
    polyline(ctx, Pl, xs, ys, STATE_COLORS[s], 2);
  }
}
function evaluate(P) {
  const out = { P: P, met: true, parts: [], summary: [] };
  if (HAS_ROPE) {
    const S = ropeState(P);
    const ok = P.m >= ROPE_M_MIN && Math.abs(S.cos) < ROPE_COS_TOL;
    out.rope = S; out.ropeOk = ok; out.met = out.met && ok;
    out.parts.push((ok ? '✓' : '✗') + ' RoPE: m = ' + P.m + ' (need ≥ ' + ROPE_M_MIN + '), cos∠(Rₘq, Rₙk) = ' + S.cos.toFixed(3) + ' (need |cos| < ' + ROPE_COS_TOL + ')');
    out.summary.push('m=' + P.m + ', n=' + P.n + ', theta=' + P.theta.toFixed(3) + ' (n-m=' + S.delta + ') -> q.k=' + S.dot.toFixed(4) + ', angle=' + S.angDeg.toFixed(1) + ' deg (same as positions 0,' + S.delta + ': ' + S.refDot.toFixed(4) + ')');
  }
  if (HAS_BELLMAN) {
    const B = bellmanState(P);
    const ok = P.gamma >= GAMMA_MIN - 1e-9 && B.ratio <= RATIO_TARGET;
    out.bell = B; out.bellOk = ok; out.met = out.met && ok;
    out.parts.push((ok ? '✓' : '✗') + ' Bellman: γ = ' + P.gamma.toFixed(2) + ' (need ≥ ' + GAMMA_MIN + '), ‖V₂₀−V*‖/‖V₀−V*‖ = ' + fx(B.ratio, 4) + ' (need ≤ ' + RATIO_TARGET + ')');
    out.summary.push('gamma=' + P.gamma.toFixed(2) + (P.v0 !== undefined ? ', V0=' + P.v0.toFixed(1) : '') + ' -> ||V_20-V*||/||V_0-V*||=' + fx(B.ratio, 4) + ' (envelope gamma^20=' + fx(B.env, 4) + ')');
  }
  return out;
}
function render(fromUser) {
  const P = readParams();
  const E = evaluate(P);
  if (HAS_ROPE) {
    drawRope(P, E.rope); drawRopeStrip(P, E.rope);
    $('st_dot').textContent = E.rope.dot.toFixed(4);
    $('st_ref').textContent = E.rope.refDot.toFixed(4);
    $('st_angle').textContent = E.rope.angDeg.toFixed(2) + '°';
  }
  if (HAS_BELLMAN) {
    drawBellman(P, E.bell); drawBellmanStrip(P, E.bell);
    $('st_vstar').textContent = '(' + E.bell.vstar.map(function (v) { return v.toFixed(3); }).join(', ') + ')';
    $('st_ratio').textContent = fx(E.bell.ratio, 4);
    $('st_env').textContent = fx(E.bell.env, 4);
  }
  setChallenge(E.met, E.parts.join('   '));
  if (fromUser) Telemetry.emit(P, E.met, 'User set ' + E.summary.join('; ') + (E.met ? ' [challenge met]' : ''));
}
const schedule = frameScheduler(render);
bindSliders({
  m: function (v) { return String(v | 0); },
  n: function (v) { return String(v | 0); },
  theta: function (v) { return v.toFixed(3) + ' rad'; },
  gamma: function (v) { return v.toFixed(2); },
  v0: function (v) { return v.toFixed(1); }
}, schedule);
window.addEventListener('resize', function () { schedule(false); });
render(false);
"""


def _rope_bellman_html(
    demo_id: str, title: str, mode: str = "both", topic: str = "", statement: str = ""
) -> str:
    if mode not in ("both", "rope", "bellman"):
        raise ValueError(f"unknown mode {mode!r}")
    has_rope = mode != "bellman"
    has_bell = mode != "rope"
    goals = []
    controls = []
    panels = []
    if has_rope:
        goals.append(
            "<b>RoPE:</b> with the query at position <b>m &ge; 5</b>, choose n and &theta; so the rotated vectors are "
            "orthogonal (|cos&ang;(R<sub>m</sub>q, R<sub>n</sub>k)| &lt; 0.03). Then shift m and n together and watch q&middot;k stay fixed."
        )
        controls += [
            _slider("m", "query position m", 0, 32, 1, 2),
            _slider("n", "key position n", 0, 32, 1, 6),
            _slider("theta", "rotation frequency &theta;", 0.05, 1.6, 0.005, 0.3),
        ]
        panels.append(
            '<div class="panel"><h3>RoPE: R<sub>m</sub>q and R<sub>n</sub>k on the unit circle '
            "(&lang;R<sub>m</sub>q, R<sub>n</sub>k&rang; = q<sup>T</sup>R<sub>n&minus;m</sub>k)</h3>"
            '<svg id="ropeSvg" class="fig" viewBox="0 0 360 300" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="RoPE rotation diagram"></svg>'
            '<canvas id="ropeCanvas" class="strip"></canvas>'
            '<div class="stats"><span>&lang;R<sub>m</sub>q, R<sub>n</sub>k&rang; <b id="st_dot"></b></span>'
            '<span>&lang;q, R<sub>n&minus;m</sub>k&rang; <b id="st_ref"></b></span>'
            '<span>angle <b id="st_angle"></b></span></div></div>'
        )
    if has_bell:
        goals.append(
            "<b>Bellman:</b> pick a discount <b>&gamma; &ge; 0.75</b> for which value iteration certifies 1% accuracy in 20 sweeps: "
            "&#8214;V<sub>20</sub> &minus; V*&#8214;<sub>&infin;</sub> &le; 0.01&middot;&#8214;V<sub>0</sub> &minus; V*&#8214;<sub>&infin;</sub>."
        )
        controls.append(_slider("gamma", "discount &gamma;", 0.1, 0.99, 0.01, 0.95))
        if not has_rope:
            controls.append(_slider("v0", "initial guess V<sub>0</sub> = c&middot;&#120793;", -20, 20, 0.5, 0))
        panels.append(
            '<div class="panel"><h3>Bellman &#8467;<sub>&infin;</sub> contraction funnel on a 3-state, 2-action MDP '
            "(log scale; violet: &gamma;<sup>k</sup> envelope, green dashed: 1% target)</h3>"
            '<svg id="bellmanSvg" class="fig" viewBox="0 0 360 300" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Bellman contraction funnel"></svg>'
            '<canvas id="bellmanCanvas" class="strip"></canvas>'
            '<div class="stats"><span>V* <b id="st_vstar"></b></span>'
            '<span>ratio at k=20 <b id="st_ratio"></b></span>'
            '<span>&gamma;<sup>20</sup> <b id="st_env"></b></span></div></div>'
        )
    body = f'<div class="grid2">{"".join(panels)}</div>' if len(panels) == 2 else panels[0]
    goal_html = " ".join(goals)
    subtitle = {
        "both": "Orthogonal rotations preserve inner products; &gamma;-contractions converge geometrically",
        "rope": "Rotary positional embeddings: inner products depend only on n &minus; m",
        "bellman": "Banach fixed point: the Bellman optimality operator is a &gamma;-contraction in &#8214;&middot;&#8214;<sub>&infin;</sub>",
    }[mode]
    script = _ROPE_BELLMAN_JS.replace("__MODE__", _js_str(mode))
    return _page(
        demo_id=demo_id,
        title=title,
        subtitle=subtitle,
        goal_html=goal_html,
        controls=controls,
        body=body,
        script=script,
        topic=topic,
        statement=statement,
    )


# ---------------------------------------------------------------------------
# Jensen / maximization-bias demo: E[max] vs max E
# ---------------------------------------------------------------------------

_JENSEN_JS = r"""
const A_MAX = 32, TRIALS = 4000, A_TARGET = 10, BIAS_TARGET = 0.5, BIAS_TOL = 0.05;
let seed = 4242, noiseCache = null;
function noise() {
  if (noiseCache && noiseCache.seed === seed) return noiseCache;
  const g = makeGauss(mulberry32(seed));
  const e1 = new Float64Array(TRIALS * A_MAX), e2 = new Float64Array(TRIALS * A_MAX);
  for (let i = 0; i < e1.length; i++) { e1[i] = g(); e2[i] = g(); }
  noiseCache = { seed: seed, e1: e1, e2: e2 };
  return noiseCache;
}
function readParams() { return { actions: parseInt($('actions').value, 10), sigma: parseFloat($('sigma').value), gap: parseFloat($('gap').value) }; }
// mu_a = -gap * a, so max_a E[Q_a] = mu_0 = 0. Single estimator: max_a (mu_a + sigma e1). Double estimator:
// select a* with e1, evaluate with the independent e2 (Double Q-learning / Double DQN decoupling).
function compute(P) {
  const N = noise();
  const runMax = new Float64Array(TRIALS).fill(-Infinity), runArg = new Int32Array(TRIALS);
  const single = [], dbl = [];
  let lastMaxes = null;
  for (let a = 0; a < A_MAX; a++) {
    const mu = -P.gap * a;
    let sS = 0, sD = 0;
    for (let t = 0; t < TRIALS; t++) {
      const z = mu + P.sigma * N.e1[t * A_MAX + a];
      if (z > runMax[t]) { runMax[t] = z; runArg[t] = a; }
      sS += runMax[t];
      sD += -P.gap * runArg[t] + P.sigma * N.e2[t * A_MAX + runArg[t]];
    }
    single.push(sS / TRIALS); dbl.push(sD / TRIALS);
    if (a + 1 === P.actions) lastMaxes = Float64Array.from(runMax);
  }
  const emax = single[P.actions - 1];
  const bias = emax;  // max_a E[Q_a] = mu_0 = 0
  const met = P.actions >= A_TARGET && Math.abs(bias - BIAS_TARGET) <= BIAS_TOL;
  return { P: P, single: single, dbl: dbl, maxes: lastMaxes, emax: emax, bias: bias, dblBias: dbl[P.actions - 1], met: met };
}
function drawHist(S) {
  const c = fitCanvas($('histCanvas')), ctx = c.ctx;
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < S.maxes.length; i++) { lo = Math.min(lo, S.maxes[i]); hi = Math.max(hi, S.maxes[i]); }
  lo = Math.min(lo, -0.5); hi = Math.max(hi, 0.5);
  const nb = 40, bw = (hi - lo) / nb, counts = new Array(nb).fill(0);
  for (let i = 0; i < S.maxes.length; i++) counts[Math.min(nb - 1, Math.floor((S.maxes[i] - lo) / bw))]++;
  const P = makePlot(c.w, c.h, [lo, hi], [0, Math.max.apply(null, counts) * 1.15 + 1]);
  drawAxes(ctx, P, { xlabel: 'maxₐ Q̂(a)', ylabel: 'count (' + TRIALS + ' trials)' });
  ctx.fillStyle = 'rgba(99,102,241,0.75)';
  for (let b = 0; b < nb; b++) { if (!counts[b]) continue; const x0 = P.X(lo + b * bw), x1 = P.X(lo + (b + 1) * bw), y = P.Y(counts[b]); ctx.fillRect(x0 + 0.5, y, Math.max(1, x1 - x0 - 1), P.Y(0) - y); }
  polyline(ctx, P, [0, 0], P.yr, COLORS.amber, 2);
  polyline(ctx, P, [S.emax, S.emax], P.yr, COLORS.emerald, 2, [5, 4]);
  ctx.font = '11px Inter, system-ui, sans-serif'; ctx.textBaseline = 'top';
  ctx.fillStyle = COLORS.amber; ctx.textAlign = 'right'; ctx.fillText('maxₐ E = 0', P.X(0) - 4, P.pad.t + 4);
  ctx.fillStyle = COLORS.emerald; ctx.textAlign = 'left'; ctx.fillText('E[max] = ' + S.emax.toFixed(3), P.X(S.emax) + 4, P.pad.t + 18);
}
function drawCurve(S) {
  const c = fitCanvas($('curveCanvas')), ctx = c.ctx;
  const xs = []; for (let a = 1; a <= A_MAX; a++) xs.push(a);
  const all = S.single.concat(S.dbl, [BIAS_TARGET + BIAS_TOL, 0]);
  const P = makePlot(c.w, c.h, [1, A_MAX], [Math.min.apply(null, all) - 0.1, Math.max.apply(null, all) + 0.1], { l: 44, r: 10, t: 12, b: 30 });
  drawAxes(ctx, P, { xlabel: 'number of actions', ylabel: 'bias vs maxₐ E' });
  ctx.fillStyle = 'rgba(16,185,129,0.12)';
  const yb0 = P.Y(BIAS_TARGET + BIAS_TOL), yb1 = P.Y(BIAS_TARGET - BIAS_TOL);
  ctx.fillRect(P.X(A_TARGET), yb0, P.X(A_MAX) - P.X(A_TARGET), yb1 - yb0);
  polyline(ctx, P, [1, A_MAX], [0, 0], COLORS.muted, 1, [3, 3]);
  polyline(ctx, P, xs, S.single, COLORS.indigo, 2.2);
  polyline(ctx, P, xs, S.dbl, COLORS.cyan, 2, [6, 3]);
  ctx.fillStyle = COLORS.amber; ctx.beginPath(); ctx.arc(P.X(S.P.actions), P.Y(S.bias), 5, 0, 2 * Math.PI); ctx.fill();
}
function summaryOf(S) {
  return 'User tuned actions=' + S.P.actions + ', sigma=' + S.P.sigma.toFixed(2) + ', gap=' + S.P.gap.toFixed(2) +
    ' -> E[max_a Q]=' + S.emax.toFixed(3) + ' vs max_a E[Q]=0, maximization bias=' + S.bias.toFixed(3) +
    ' (double estimator bias=' + S.dblBias.toFixed(3) + ')' + (S.met ? ' [challenge met]' : '');
}
function render(fromUser) {
  const P = readParams();
  const S = compute(P);
  drawHist(S); drawCurve(S);
  $('st_emax').textContent = S.emax.toFixed(3);
  $('st_bias').textContent = S.bias.toFixed(3);
  $('st_dbl').textContent = S.dblBias.toFixed(3);
  const aOk = P.actions >= A_TARGET, bOk = Math.abs(S.bias - BIAS_TARGET) <= BIAS_TOL;
  setChallenge(S.met, (aOk ? '✓' : '✗') + ' actions = ' + P.actions + ' (need ≥ ' + A_TARGET + ')   ' +
    (bOk ? '✓' : '✗') + ' bias = ' + S.bias.toFixed(3) + ' (need ' + BIAS_TARGET + ' ± ' + BIAS_TOL + ')');
  if (fromUser) Telemetry.emit(P, S.met, summaryOf(S));
}
const schedule = frameScheduler(render);
bindSliders({
  actions: function (v) { return String(v | 0); },
  sigma: function (v) { return v.toFixed(2); },
  gap: function (v) { return v.toFixed(2); }
}, schedule);
$('resample').addEventListener('click', function () { seed = (seed * 1103515245 + 12345) >>> 0; schedule(true); });
window.addEventListener('resize', function () { schedule(false); });
render(false);
"""


def _jensen_html(demo_id: str, title: str, topic: str = "", statement: str = "") -> str:
    goal = (
        "With <b>at least 10 actions</b>, tune the estimation noise so the maximization bias "
        "E[max<sub>a</sub> Q&#770;(a)] &minus; max<sub>a</sub> E[Q&#770;(a)] equals <b>0.50 &plusmn; 0.05</b>."
    )
    controls = [
        _slider("actions", "number of actions", 1, 32, 1, 4),
        _slider("sigma", "estimation noise &sigma;", 0, 3, 0.01, 1),
        _slider("gap", "gap &Delta; between true action values", 0, 1, 0.01, 0),
    ]
    body = (
        '<div class="panel"><h3>Monte-Carlo distribution of max<sub>a</sub> Q&#770;(a), Q&#770;(a) = &mu;<sub>a</sub> + &sigma;&epsilon;<sub>a</sub>, '
        "&mu;<sub>a</sub> = &minus;&Delta;&middot;a (so max<sub>a</sub> &mu;<sub>a</sub> = 0)</h3>"
        '<canvas id="histCanvas"></canvas>'
        '<div class="stats"><span>E[max] <b id="st_emax"></b></span><span>bias (Jensen gap) <b id="st_bias"></b></span>'
        '<span>double-estimator bias <b id="st_dbl"></b></span><button type="button" id="resample">Resample</button></div></div>'
        '<div class="panel"><h3>Bias vs number of actions (indigo: single max estimator, cyan dashed: double estimator)</h3>'
        '<canvas id="curveCanvas" class="short"></canvas>'
        '<div class="hint">max is convex, so Jensen gives E[max<sub>a</sub> Z<sub>a</sub>] &ge; max<sub>a</sub> E[Z<sub>a</sub>]; '
        "decoupling selection from evaluation removes the upward bias.</div></div>"
    )
    return _page(
        demo_id=demo_id,
        title=title,
        subtitle="Jensen's inequality and the maximization bias of Q-learning",
        goal_html=goal,
        controls=controls,
        body=body,
        script=_JENSEN_JS,
        topic=topic,
        statement=statement,
    )


# ---------------------------------------------------------------------------
# Generic parametric function explorer
# ---------------------------------------------------------------------------

_GENERIC_JS = r"""
const TARGET = __TARGET__;
const RMSE_TARGET = 0.08, XL = -4, XR = 4, NS = 241;
function f(p, x) { return p.a * Math.sin(p.b * x) + p.c * x * x; }
function readParams() { return { a: parseFloat($('a').value), b: parseFloat($('b').value), c: parseFloat($('c').value) }; }
function compute(P) {
  const xs = [], ys = [], ts = [];
  let se = 0;
  for (let i = 0; i < NS; i++) {
    const x = XL + (XR - XL) * i / (NS - 1);
    const y = f(P, x), t = f(TARGET, x);
    xs.push(x); ys.push(y); ts.push(t); se += (y - t) * (y - t);
  }
  const rmse = Math.sqrt(se / NS);
  return { P: P, xs: xs, ys: ys, ts: ts, rmse: rmse, met: rmse < RMSE_TARGET };
}
function draw(S) {
  const c = fitCanvas($('fnCanvas')), ctx = c.ctx;
  const all = S.ys.concat(S.ts);
  const lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = Math.max(0.5, 0.1 * (hi - lo));
  const P = makePlot(c.w, c.h, [XL, XR], [lo - pad, hi + pad]);
  drawAxes(ctx, P, { xlabel: 'x', ylabel: 'f(x)' });
  ctx.save();
  ctx.beginPath(); ctx.rect(P.pad.l, P.pad.t, c.w - P.pad.l - P.pad.r, c.h - P.pad.t - P.pad.b); ctx.clip();
  ctx.fillStyle = 'rgba(239,68,68,0.18)';
  ctx.beginPath();
  for (let i = 0; i < S.xs.length; i++) { const x = P.X(S.xs[i]), y = P.Y(S.ys[i]); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
  for (let i = S.xs.length - 1; i >= 0; i--) ctx.lineTo(P.X(S.xs[i]), P.Y(S.ts[i]));
  ctx.closePath(); ctx.fill();
  ctx.restore();
  polyline(ctx, P, S.xs, S.ts, COLORS.amber, 2.2, [6, 4]);
  polyline(ctx, P, S.xs, S.ys, COLORS.indigo, 2.4);
}
function render(fromUser) {
  const P = readParams();
  const S = compute(P);
  draw(S);
  $('st_rmse').textContent = S.rmse.toFixed(4);
  setChallenge(S.met, (S.met ? '✓' : '✗') + ' RMSE on [−4, 4] = ' + S.rmse.toFixed(4) + ' (need < ' + RMSE_TARGET + ')');
  if (fromUser) Telemetry.emit(P, S.met, 'User tuned a=' + P.a.toFixed(2) + ', b=' + P.b.toFixed(2) + ', c=' + P.c.toFixed(2) +
    ' -> RMSE to target curve=' + S.rmse.toFixed(4) + (S.met ? ' [challenge met]' : ''));
}
const schedule = frameScheduler(render);
bindSliders({ a: function (v) { return v.toFixed(2); }, b: function (v) { return v.toFixed(2); }, c: function (v) { return v.toFixed(2); } }, schedule);
window.addEventListener('resize', function () { schedule(false); });
render(false);
"""


def _fnv1a(text: str) -> int:
    h = 0x811C9DC5
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _generic_target(demo_id: str) -> dict[str, float]:
    """Deterministic hidden target (a, b, c) on the slider grids, derived from the demo id."""
    h = _fnv1a(demo_id or "demo")
    a = 0.5 + 0.05 * (h % 31)            # 0.50 .. 2.00, multiple of 0.05
    b = 0.5 + 0.05 * ((h >> 5) % 51)     # 0.50 .. 3.00
    c = -0.2 + 0.01 * ((h >> 11) % 41)   # -0.20 .. 0.20
    return {"a": round(a, 2), "b": round(b, 2), "c": round(c, 2)}


def _generic_html(demo_id: str, title: str, topic: str = "", statement: str = "") -> str:
    target = _generic_target(demo_id)
    goal = (
        "Match the hidden target curve (amber, dashed) with f(x) = a&middot;sin(bx) + c&middot;x<sup>2</sup>: "
        "drive the RMSE on [&minus;4, 4] below <b>0.08</b>. Start with c (the bowl), then b (frequency), then a (amplitude)."
    )
    controls = [
        _slider("a", "amplitude a", -3, 3, 0.05, 1),
        _slider("b", "frequency b", 0, 4, 0.05, 1),
        _slider("c", "curvature c", -0.5, 0.5, 0.01, 0),
    ]
    body = (
        '<div class="panel"><h3>f(x) = a&middot;sin(bx) + c&middot;x<sup>2</sup> (indigo) vs target (amber); red area = mismatch</h3>'
        '<canvas id="fnCanvas"></canvas>'
        '<div class="stats"><span>RMSE <b id="st_rmse"></b></span></div></div>'
    )
    script = _GENERIC_JS.replace("__TARGET__", _js_str(target))
    return _page(
        demo_id=demo_id,
        title=title,
        subtitle="Parametric function explorer",
        goal_html=goal,
        controls=controls,
        body=body,
        script=script,
        topic=topic,
        statement=statement,
    )


# ---------------------------------------------------------------------------
# Template selection
# ---------------------------------------------------------------------------

_TEMPLATE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("attention", [r"variance", r"\bvar\b", r"softmax", r"attention", r"scaled", r"dot[- ]product", r"\bd_k\b", r"\bd_\{?k\}?"]),
    ("sgd", [r"gradient", r"\bsgd\b", r"momentum", r"learning[- ]rate", r"hessian", r"descent", r"condition number"]),
    ("rope", [r"\brope\b", r"rotation", r"rotary", r"orthogonal"]),
    ("bellman", [r"bellman", r"contraction", r"fixed[- ]point", r"banach", r"q-learning", r"value iteration"]),
    ("jensen", [r"jensen", r"\bmax(?![a-z])", r"overestimat", r"maximi[sz]ation bias", r"double dqn", r"e\[\s*\\?max"]),
]


def _select_template(text: str) -> str:
    lowered = (text or "").lower()
    best, best_score = "generic", 0
    for name, patterns in _TEMPLATE_KEYWORDS:
        score = sum(len(re.findall(p, lowered)) for p in patterns)
        if score > best_score:
            best, best_score = name, score
    return best


def build_demo_html(demo_id: str, title: str, topic: str, statement_latex: str = "") -> str:
    """Return a complete interactive HTML demo whose template is chosen by keyword.

    variance/softmax/attention/scaled -> attention explorer; gradient/sgd/momentum/
    learning rate/hessian -> heavy-ball SGD; rope/rotation/orthogonal -> RoPE panel;
    bellman/contraction/fixed point/banach/q-learning -> contraction funnel;
    jensen/max/overestimation/maximization bias -> E[max] vs max E Monte Carlo;
    anything else -> parametric function explorer with a target-matching challenge.
    """
    demo_id = str(demo_id or "demo")
    title = str(title or "Interactive demo")
    template = _select_template(" ".join([title, str(topic or ""), str(statement_latex or "")]))
    kwargs = {"topic": str(topic or ""), "statement": str(statement_latex or "")}
    if template == "attention":
        return _attention_html(demo_id, title, **kwargs)
    if template == "sgd":
        return _sgd_html(demo_id, title, **kwargs)
    if template == "rope":
        return _rope_bellman_html(demo_id, title, mode="rope", **kwargs)
    if template == "bellman":
        return _rope_bellman_html(demo_id, title, mode="bellman", **kwargs)
    if template == "jensen":
        return _jensen_html(demo_id, title, **kwargs)
    return _generic_html(demo_id, title, **kwargs)


# ---------------------------------------------------------------------------
# SVG diagram maker
# ---------------------------------------------------------------------------

_SVG_W, _SVG_H = 720, 340
_C_FILL, _C_BG, _C_LABEL, _C_MUTED = "#1e293b", "#0b0f19", "#f8fafc", "#94a3b8"
_C_INDIGO, _C_EMERALD, _C_AMBER, _C_VIOLET, _C_CYAN = "#6366f1", "#10b981", "#f59e0b", "#8b5cf6", "#22d3ee"

_NODE_STROKES = {
    "AXIOM": _C_INDIGO,
    "DEFINITION": _C_INDIGO,
    "PROPOSITION": _C_EMERALD,
    "THEOREM": _C_EMERALD,
    "LEMMA": _C_EMERALD,
    "MOVE": _C_EMERALD,
    "INTUITION": _C_INDIGO,
    "COUNTEREXAMPLE": _C_AMBER,
    "BUGGY_RULE": _C_AMBER,
    "MISCONCEPTION": _C_AMBER,
}


def _truncate(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    max_chars = max(2, int(max_chars))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _clip_to_box(cx: float, cy: float, w: float, h: float, tx: float, ty: float) -> tuple[float, float]:
    """Point where the segment from the box centre towards (tx, ty) leaves the box."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else math.inf
    sy = (h / 2) / abs(dy) if dy else math.inf
    s = min(sx, sy, 1.0)
    return cx + dx * s, cy + dy * s


def _f(v: float) -> str:
    return f"{v:.1f}"


def build_svg_diagram(title: str, nodes: list[dict], edges: list[dict]) -> str:
    """Render a hypergraph excerpt as a standalone dark-mode SVG (viewBox 0 0 720 340).

    Nodes (``id``, ``title``, ``node_type``, ``logical_depth``) are laid out in depth
    layers bottom-to-top. Edges (``edge_type``, ``premise_node_ids``,
    ``conclusion_node_id``) use: DEDUCTION solid arrows through an and-diamond hub,
    CONTRASTIVE dashed amber with a perpendicular mark, ISOMORPHISM violet double
    line with a congruence mark, CUE_TRIGGER dotted cyan arrow.
    """
    # -- normalise nodes ---------------------------------------------------
    norm: list[dict] = []
    seen: set[str] = set()
    for raw in nodes or []:
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or raw.get("node_id") or f"node_{len(norm)}")
        if nid in seen:
            continue
        seen.add(nid)
        try:
            depth = int(raw.get("logical_depth") or 0)
        except (TypeError, ValueError):
            depth = 0
        norm.append({
            "id": nid,
            "title": str(raw.get("title") or nid),
            "type": str(raw.get("node_type") or "PROPOSITION").upper(),
            "depth": max(0, depth),
        })

    # -- normalise edges ---------------------------------------------------
    norm_edges: list[dict] = []
    for raw in edges or []:
        if not isinstance(raw, dict):
            continue
        prem = raw.get("premise_node_ids") or []
        if isinstance(prem, str):
            try:
                parsed = json.loads(prem)
                prem = parsed if isinstance(parsed, list) else [prem]
            except ValueError:
                prem = [p.strip() for p in prem.split(",") if p.strip()]
        concl = str(raw.get("conclusion_node_id") or "")
        prem_ids = [str(p) for p in prem if str(p) in seen and str(p) != concl]
        if concl not in seen or not prem_ids:
            continue
        norm_edges.append({"type": str(raw.get("edge_type") or "DEDUCTION").upper(), "premises": prem_ids, "conclusion": concl})

    # -- layout --------------------------------------------------------------
    depths = sorted({n["depth"] for n in norm})
    layer_count = len(depths)
    top_y, bottom_y = 92.0, 304.0
    if layer_count <= 1:
        layer_y = {d: (top_y + bottom_y) / 2 for d in depths}
        box_h = 42.0
    else:
        step = (bottom_y - top_y) / (layer_count - 1)
        layer_y = {d: bottom_y - i * step for i, d in enumerate(depths)}
        box_h = max(20.0, min(42.0, step - 10.0))
    layers: dict[int, list[dict]] = {d: [n for n in norm if n["depth"] == d] for d in depths}

    # barycentre ordering (bottom-up) to reduce crossings
    neighbours: dict[str, set[str]] = {n["id"]: set() for n in norm}
    for e in norm_edges:
        for p in e["premises"]:
            neighbours[p].add(e["conclusion"])
            neighbours[e["conclusion"]].add(p)
    margin, gap = 14.0, 10.0
    pos: dict[str, dict] = {}

    def place(layer_nodes: list[dict], y: float) -> None:
        count = len(layer_nodes)
        slot = (_SVG_W - 2 * margin) / count
        width = max(40.0, min(170.0, slot - gap))
        for i, node in enumerate(layer_nodes):
            pos[node["id"]] = {"x": margin + slot * (i + 0.5), "y": y, "w": width, "h": box_h, "node": node}

    def reorder(layer_nodes: list[dict]) -> list[dict]:
        """Sort a layer by the mean x of already-placed neighbours (stable; unconnected nodes keep their slot)."""
        def key(item: tuple[int, dict]) -> tuple[float, int]:
            idx, node = item
            xs = [pos[nb]["x"] for nb in neighbours[node["id"]] if nb in pos]
            own = pos[node["id"]]["x"] if node["id"] in pos else math.inf
            return (sum(xs) / len(xs) if xs else own, idx)
        return [n for _, n in sorted(enumerate(layer_nodes), key=key)]

    # bottom-up initial pass, then top-down and bottom-up barycentre sweeps
    for li, d in enumerate(depths):
        layers[d] = reorder(layers[d]) if li > 0 else layers[d]
        place(layers[d], layer_y[d])
    for sweep in (list(reversed(depths)), depths):
        for d in sweep:
            layers[d] = reorder(layers[d])
            place(layers[d], layer_y[d])

    # -- svg ---------------------------------------------------------------------
    out: list[str] = []
    out.append(
        f'<svg viewBox="0 0 {_SVG_W} {_SVG_H}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{_esc(_truncate(title, 120))}" font-family="Inter, system-ui, sans-serif" '
        'preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;display:block">'
    )
    out.append(f"<title>{_esc(_truncate(title, 160))}</title>")
    out.append("<defs>")
    for name, col in (("ded", _C_INDIGO), ("cue", _C_CYAN), ("gen", _C_MUTED)):
        out.append(
            f'<marker id="lh-arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>'
        )
    out.append("</defs>")
    out.append(f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" rx="12" fill="{_C_BG}"/>')
    out.append(
        f'<text x="16" y="26" fill="{_C_LABEL}" font-size="14" font-weight="700">{_esc(_truncate(title, 88))}</text>'
    )
    # legend
    legend = [
        ("DEDUCTION", f'<line x1="0" y1="0" x2="22" y2="0" stroke="{_C_INDIGO}" stroke-width="2"/>', "∧ deduction"),
        ("CONTRASTIVE", f'<line x1="0" y1="0" x2="22" y2="0" stroke="{_C_AMBER}" stroke-width="2" stroke-dasharray="5 3"/>', "⊥ contrastive"),
        ("ISOMORPHISM", f'<line x1="0" y1="-2" x2="22" y2="-2" stroke="{_C_VIOLET}" stroke-width="1.5"/><line x1="0" y1="2" x2="22" y2="2" stroke="{_C_VIOLET}" stroke-width="1.5"/>', "≅ isomorphism"),
        ("CUE_TRIGGER", f'<line x1="0" y1="0" x2="22" y2="0" stroke="{_C_CYAN}" stroke-width="2" stroke-dasharray="1.5 3.5" stroke-linecap="round"/>', "cue trigger"),
    ]
    lx = 16.0
    for _, sample, text in legend:
        out.append(f'<g transform="translate({_f(lx)},46)">{sample}<text x="27" y="4" fill="{_C_MUTED}" font-size="10.5">{_esc(text)}</text></g>')
        lx += 27.0 + len(text) * 6.0 + 18.0

    if not norm:
        out.append(f'<text x="{_SVG_W / 2}" y="{_SVG_H / 2}" fill="{_C_MUTED}" font-size="13" text-anchor="middle">No nodes to display</text>')
        out.append("</svg>")
        return "".join(out)

    edge_layer: list[str] = []
    glyph_layer: list[str] = []

    def anchor(nid: str, tx: float, ty: float) -> tuple[float, float]:
        p = pos[nid]
        return _clip_to_box(p["x"], p["y"], p["w"] + 4, p["h"] + 4, tx, ty)

    def glyph(x: float, y: float, sym: str, col: str) -> str:
        return (
            f'<circle cx="{_f(x)}" cy="{_f(y)}" r="8" fill="{_C_BG}" stroke="{col}" stroke-width="1.4"/>'
            f'<text x="{_f(x)}" y="{_f(y + 4)}" fill="{col}" font-size="11" font-weight="700" text-anchor="middle">{sym}</text>'
        )

    for e in norm_edges:
        c = pos[e["conclusion"]]
        etype = e["type"]
        if etype == "DEDUCTION":
            px = sum(pos[p]["x"] for p in e["premises"]) / len(e["premises"])
            py = sum(pos[p]["y"] for p in e["premises"]) / len(e["premises"])
            hx, hy = px + 0.6 * (c["x"] - px), py + 0.6 * (c["y"] - py)
            for p in e["premises"]:
                ax, ay = anchor(p, hx, hy)
                edge_layer.append(f'<line x1="{_f(ax)}" y1="{_f(ay)}" x2="{_f(hx)}" y2="{_f(hy)}" stroke="{_C_INDIGO}" stroke-width="1.6"/>')
            bx, by = anchor(e["conclusion"], hx, hy)
            edge_layer.append(
                f'<line x1="{_f(hx)}" y1="{_f(hy)}" x2="{_f(bx)}" y2="{_f(by)}" stroke="{_C_INDIGO}" stroke-width="1.8" marker-end="url(#lh-arrow-ded)"/>'
            )
            r = 8.0
            glyph_layer.append(
                f'<polygon points="{_f(hx)},{_f(hy - r)} {_f(hx + r)},{_f(hy)} {_f(hx)},{_f(hy + r)} {_f(hx - r)},{_f(hy)}" '
                f'fill="{_C_FILL}" stroke="{_C_INDIGO}" stroke-width="1.5"/>'
                f'<text x="{_f(hx)}" y="{_f(hy + 3.5)}" fill="{_C_LABEL}" font-size="10" font-weight="700" text-anchor="middle">∧</text>'
            )
        else:
            for p in e["premises"]:
                q = pos[p]
                ax, ay = anchor(p, c["x"], c["y"])
                bx, by = anchor(e["conclusion"], q["x"], q["y"])
                # glyph sits 35% along the edge so it does not collide with a DEDUCTION hub (placed at 60%)
                mx, my = ax + 0.35 * (bx - ax), ay + 0.35 * (by - ay)
                if etype == "CONTRASTIVE":
                    edge_layer.append(
                        f'<line x1="{_f(ax)}" y1="{_f(ay)}" x2="{_f(bx)}" y2="{_f(by)}" stroke="{_C_AMBER}" stroke-width="1.7" stroke-dasharray="6 4"/>'
                    )
                    glyph_layer.append(glyph(mx, my, "⊥", _C_AMBER))
                elif etype == "ISOMORPHISM":
                    length = math.hypot(bx - ax, by - ay) or 1.0
                    nx, ny = -(by - ay) / length * 2.2, (bx - ax) / length * 2.2
                    for sgn in (1, -1):
                        edge_layer.append(
                            f'<line x1="{_f(ax + sgn * nx)}" y1="{_f(ay + sgn * ny)}" x2="{_f(bx + sgn * nx)}" y2="{_f(by + sgn * ny)}" '
                            f'stroke="{_C_VIOLET}" stroke-width="1.3"/>'
                        )
                    glyph_layer.append(glyph(mx, my, "≅", _C_VIOLET))
                elif etype == "CUE_TRIGGER":
                    edge_layer.append(
                        f'<line x1="{_f(ax)}" y1="{_f(ay)}" x2="{_f(bx)}" y2="{_f(by)}" stroke="{_C_CYAN}" stroke-width="1.8" '
                        'stroke-dasharray="1.5 4" stroke-linecap="round" marker-end="url(#lh-arrow-cue)"/>'
                    )
                else:
                    edge_layer.append(
                        f'<line x1="{_f(ax)}" y1="{_f(ay)}" x2="{_f(bx)}" y2="{_f(by)}" stroke="{_C_MUTED}" stroke-width="1.4" marker-end="url(#lh-arrow-gen)"/>'
                    )

    out.append('<g class="edges">' + "".join(edge_layer) + "</g>")

    node_layer: list[str] = []
    for nid, p in pos.items():
        node = p["node"]
        stroke = _NODE_STROKES.get(node["type"], _C_EMERALD)
        x0, y0 = p["x"] - p["w"] / 2, p["y"] - p["h"] / 2
        title_fs = 11.0 if p["w"] >= 90 else 9.5
        max_chars = (p["w"] - 12) / (title_fs * 0.56)
        dash = ' stroke-dasharray="4 3"' if node["type"] == "INTUITION" else ""
        parts = [
            f'<g class="node"><title>{_esc(nid)}: {_esc(node["title"])}</title>',
            f'<rect x="{_f(x0)}" y="{_f(y0)}" width="{_f(p["w"])}" height="{_f(p["h"])}" rx="8" fill="{_C_FILL}" stroke="{stroke}" stroke-width="1.6"{dash}/>',
        ]
        if p["h"] >= 32:
            type_txt = _truncate(f'{node["type"]} · d{node["depth"]}', (p["w"] - 12) / (8.5 * 0.6))
            parts.append(
                f'<text x="{_f(p["x"])}" y="{_f(y0 + 13)}" fill="{stroke}" font-size="8.5" font-weight="600" '
                f'letter-spacing="0.04em" text-anchor="middle">{_esc(type_txt)}</text>'
            )
            ty = y0 + p["h"] - 10
        else:
            ty = p["y"] + title_fs * 0.36
        parts.append(
            f'<text x="{_f(p["x"])}" y="{_f(ty)}" fill="{_C_LABEL}" font-size="{title_fs}" text-anchor="middle">'
            f'{_esc(_truncate(node["title"], max_chars))}</text></g>'
        )
        node_layer.append("".join(parts))
    out.append('<g class="nodes">' + "".join(node_layer) + "</g>")
    out.append('<g class="glyphs">' + "".join(glyph_layer) + "</g>")
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Pre-built seed demos (§7.5)
# ---------------------------------------------------------------------------

_ATTENTION_TITLE = "Attention Logit Variance & Softmax Entropy Saturation Explorer"
_SGD_TITLE = "SGD & Momentum Trajectory on Anisotropic Quadratic Loss Surface"
_ROPE_BELLMAN_TITLE = "RoPE Block-2D Relative Rotation & Bellman ℓ∞ Contraction Funnel"

DEMO_ATTENTION_HTML: str = _attention_html("demo_attention_softmax", _ATTENTION_TITLE)
DEMO_SGD_HTML: str = _sgd_html("demo_sgd_momentum", _SGD_TITLE)
DEMO_ROPE_BELLMAN_HTML: str = _rope_bellman_html("demo_rope_bellman", _ROPE_BELLMAN_TITLE, mode="both")

DEMO_SEED: list[dict] = [
    {
        "id": "demo_attention_softmax",
        "title": _ATTENTION_TITLE,
        "content_type": "html_demo",
        "payload_text": DEMO_ATTENTION_HTML,
        "target_node_ids": ["prop_scaled_dot_product_variance", "prop_var_indep_sum"],
    },
    {
        "id": "demo_sgd_momentum",
        "title": _SGD_TITLE,
        "content_type": "html_demo",
        "payload_text": DEMO_SGD_HTML,
        "target_node_ids": ["int_covector_hyperplanes", "prop_banach_contraction"],
    },
    {
        "id": "demo_rope_bellman",
        "title": _ROPE_BELLMAN_TITLE,
        "content_type": "html_demo",
        "payload_text": DEMO_ROPE_BELLMAN_HTML,
        "target_node_ids": ["prop_rope_relative_invariance", "prop_bellman_sup_norm_contraction"],
    },
]
