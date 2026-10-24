/**
 * Sandboxed interactive demo viewer (ARCHITECTURE_SPEC §6.5).
 *  - iframe sandbox="allow-scripts" (opaque origin: no cookies, no parent DOM, no same-origin API access)
 *  - srcdoc from the SANDBOX_DEMO_BUILDER artifact payload, with a default dark-theme injection
 *  - "Invert Colors / Dark-Mode Guard" anti-flashbang toggle
 *  - listens for HARNESS_DEMO_TELEMETRY postMessage, shows a "Sandbox Telemetry Captured" pill,
 *    and POSTs it (debounced; immediately on challenge solve) to /api/demo-telemetry
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { ArtifactOut, DemoTelemetryAck } from '../types/harness';
import { fmtDateTime } from './ui';

interface DemoMessage {
  type: 'HARNESS_DEMO_TELEMETRY';
  demoId?: string;
  params?: Record<string, unknown>;
  challengeSolved?: boolean;
  summary?: string;
}

const DARK_GUARD = `<style id="harness-dark-guard">:root{color-scheme:dark}html,body{background:#0b0f19;color:#f8fafc;font-family:Inter,system-ui,sans-serif;margin:0}</style>`;

function injectDarkGuard(html: string): string {
  const src = html.trim();
  if (/<head[^>]*>/i.test(src)) return src.replace(/<head[^>]*>/i, (m) => `${m}${DARK_GUARD}`);
  if (/<html[^>]*>/i.test(src)) return src.replace(/<html[^>]*>/i, (m) => `${m}<head>${DARK_GUARD}</head>`);
  return `<!DOCTYPE html><html><head><meta charset="utf-8">${DARK_GUARD}</head><body>${src}</body></html>`;
}

function fmtParam(v: unknown): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toPrecision(3);
  if (typeof v === 'string' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

export default function SandboxDemoViewer({
  artifact,
  sessionId,
  height = 460,
}: {
  artifact: ArtifactOut;
  sessionId?: string | null;
  height?: number;
}): JSX.Element {
  const postDemoTelemetry = useHarnessStore((s) => s.postDemoTelemetry);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [inverted, setInverted] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [last, setLast] = useState<DemoMessage | null>(null);
  const [events, setEvents] = useState(0);
  const [ack, setAck] = useState<DemoTelemetryAck | null>(null);
  const [posting, setPosting] = useState(false);
  const pendingRef = useRef<DemoMessage | null>(null);
  const timerRef = useRef<number | null>(null);
  const solvedRef = useRef(false);

  const srcDoc = useMemo(() => injectDarkGuard(artifact.payload_text), [artifact.payload_text]);

  useEffect(() => {
    const flush = (): void => {
      timerRef.current = null;
      const m = pendingRef.current;
      pendingRef.current = null;
      if (!m) return;
      setPosting(true);
      // demo_id is the artifact id: the backend resolves the demo's target nodes via db.get_artifact(demo_id).
      // The iframe's own slug (m.demoId, e.g. "demo_prop_x") is display-only.
      void postDemoTelemetry({
        demo_id: artifact.id,
        session_id: sessionId ?? artifact.session_id ?? null,
        params: m.params ?? {},
        challenge_solved: Boolean(m.challengeSolved),
        summary: m.summary ?? '',
      }).then((r) => {
        setPosting(false);
        if (r) setAck(r);
      });
    };
    const onMsg = (e: MessageEvent): void => {
      if (!iframeRef.current || e.source !== iframeRef.current.contentWindow) return;
      const d = e.data as Partial<DemoMessage> | null;
      if (!d || typeof d !== 'object' || d.type !== 'HARNESS_DEMO_TELEMETRY') return;
      const msg = d as DemoMessage;
      setLast(msg);
      setEvents((n) => n + 1);
      pendingRef.current = msg;
      const newlySolved = Boolean(msg.challengeSolved) && !solvedRef.current;
      if (msg.challengeSolved) solvedRef.current = true;
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(flush, newlySolved ? 0 : 700);
    };
    window.addEventListener('message', onMsg);
    return () => {
      window.removeEventListener('message', onMsg);
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        flush(); // never drop the final slider position
      }
    };
  }, [artifact.id, artifact.session_id, sessionId, postDemoTelemetry]);

  const params = last?.params ? Object.entries(last.params) : [];

  return (
    <div className="demo">
      <div className="demo-head">
        <div className="demo-title">
          <span className="tag violet mono">SANDBOX</span>
          <span className="truncate">{artifact.title}</span>
        </div>
        <div className="demo-actions">
          <span className={`pill small telemetry-pill${last ? ' on' : ''}`} title={last?.summary || 'Waiting for slider telemetry from the sandbox'}>
            <span className="dot" />
            {last ? (
              <>
                Sandbox Telemetry Captured <span className="mono dim">×{events}</span>
              </>
            ) : (
              'awaiting telemetry'
            )}
          </span>
          <button
            className={`btn small${inverted ? ' on' : ''}`}
            onClick={() => setInverted((v) => !v)}
            aria-pressed={inverted}
            title="Anti-flashbang: invert a light-themed demo so it stays dark"
          >
            ◐ Invert Colors / Dark-Mode Guard
          </button>
          <button className="btn small ghost" onClick={() => setReloadKey((k) => k + 1)} title="Reload demo">
            ↻
          </button>
        </div>
      </div>
      <div className="demo-frame" style={{ height }}>
        <iframe
          key={reloadKey}
          ref={iframeRef}
          title={artifact.title}
          sandbox="allow-scripts"
          srcDoc={srcDoc}
          style={{ filter: inverted ? 'invert(1) hue-rotate(180deg)' : 'none' }}
        />
      </div>
      <div className="demo-telemetry">
        {last ? (
          <>
            <div className="param-row">
              {params.map(([k, v]) => (
                <span key={k} className="param mono">
                  {k}=<b>{fmtParam(v)}</b>
                </span>
              ))}
              {last.demoId ? <span className="param mono dim">demo={last.demoId}</span> : null}
              <span className={`param mono ${last.challengeSolved ? 'ok' : ''}`}>
                challenge={last.challengeSolved ? 'SOLVED ✓' : 'open'}
              </span>
              {posting ? <span className="dim mono">posting…</span> : null}
            </div>
            {last.summary ? <div className="dim small">{last.summary}</div> : null}
            {ack ? (
              <div className="small mono dim">
                recorded={String(ack.recorded)}
                {ack.cue_updates.length ? ` · cue updates: ${ack.cue_updates.join(', ')}` : ''}
              </div>
            ) : null}
          </>
        ) : (
          <span className="dim small">
            Drag the demo's sliders: parameters are captured via postMessage and logged as geometric-cue telemetry. Built{' '}
            {fmtDateTime(artifact.created_at)}.
          </span>
        )}
      </div>
    </div>
  );
}
