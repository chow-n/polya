/**
 * Inline sentence & equation anchoring + margin stream (ARCHITECTURE_SPEC §6.2) for READING steps.
 *  - click a sentence, drag-select any text, or click an equation → anchored Thinking-While-Reading note
 *  - persistent "Thinking while reading (stream of consciousness)..." field (typed or dictated)
 *  - attached SANDBOX_DEMO_BUILDER demo / SVG_DIAGRAM_MAKER diagram for dual coding
 *  - Continue: POST /submit with notes (Channel 2 telemetry) or POST /advance when there is nothing to log
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { ArtifactOut, StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { StepHeader } from './EpistemicLockBox';
import SandboxDemoViewer from './SandboxDemoViewer';
import { VoiceRow } from './TelemetryInputDock';
import { Spinner } from './ui';

export function useArtifact(id: string | null): ArtifactOut | undefined {
  const art = useHarnessStore((s) => (id ? s.artifactCache[id] : undefined));
  const fetchArtifact = useHarnessStore((s) => s.fetchArtifact);
  useEffect(() => {
    if (id && !art) void fetchArtifact(id);
  }, [id, art, fetchArtifact]);
  return art;
}

export function StepMedia({ step, sessionId }: { step: StepPayload; sessionId: string | null }): JSX.Element | null {
  const demo = useArtifact(step.demo_artifact_id);
  const svg = useArtifact(step.svg_artifact_id);
  if (!step.demo_artifact_id && !step.svg_artifact_id) return null;
  return (
    <div className="step-media">
      {step.svg_artifact_id ? (
        svg ? (
          <figure className="svg-frame">
            <img alt={svg.title} src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg.payload_text)}`} />
            <figcaption className="dim small">{svg.title}</figcaption>
          </figure>
        ) : (
          <div className="media-loading">
            <Spinner /> loading diagram…
          </div>
        )
      ) : null}
      {step.demo_artifact_id ? (
        demo ? (
          <SandboxDemoViewer artifact={demo} sessionId={sessionId} height={420} />
        ) : (
          <div className="media-loading">
            <Spinner /> loading demo…
          </div>
        )
      ) : null}
    </div>
  );
}

export default function ReadingStreamBox({ step }: { step: StepPayload }): JSX.Element {
  const draft = useHarnessStore((s) => s.draft);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const addNote = useHarnessStore((s) => s.addReadingNote);
  const removeNote = useHarnessStore((s) => s.removeReadingNote);
  const setMicTarget = useHarnessStore((s) => s.setMicTarget);
  const micTarget = useHarnessStore((s) => s.micTarget);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const advanceStep = useHarnessStore((s) => s.advanceStep);
  const busySubmit = useHarnessStore((s) => s.busy.submit);
  const busyAdvance = useHarnessStore((s) => s.busy.advance);
  const sessionId = useHarnessStore((s) => s.activeSessionId);
  const bodyRef = useRef<HTMLDivElement>(null);
  const thoughtRef = useRef<HTMLTextAreaElement>(null);
  const [quote, setQuote] = useState<string | null>(null);
  const [thought, setThought] = useState('');

  const highlighted = useMemo(() => new Set(draft.readingNotes.map((n) => n.quote).filter(Boolean)), [draft.readingNotes]);
  const words = useMemo(() => step.body_markdown.split(/\s+/).filter(Boolean).length, [step.body_markdown]);

  const beginAnchor = (q: string): void => {
    setQuote(q.trim().slice(0, 500));
    requestAnimationFrame(() => thoughtRef.current?.focus());
  };

  const onMouseUp = (): void => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !bodyRef.current) return;
    const range = sel.getRangeAt(0);
    if (!bodyRef.current.contains(range.commonAncestorContainer)) return;
    const text = sel.toString().replace(/\s+/g, ' ').trim();
    if (text.length >= 3) beginAnchor(text);
  };

  const commit = (): void => {
    if (!quote || !thought.trim()) return;
    addNote({ quote, thought: thought.trim() });
    setQuote(null);
    setThought('');
    window.getSelection()?.removeAllRanges();
  };

  const hasTelemetry = draft.readingNotes.length > 0 || draft.readingStream.trim().length > 0;
  const fmtT = (ms: number): string => `${Math.floor(ms / 60000)}:${String(Math.floor((ms % 60000) / 1000)).padStart(2, '0')}`;

  return (
    <div className="stream-card reading">
      <StepHeader step={step} />
      <div className="reading-grid">
        <div className="reading-main">
          {step.prompt_latex ? (
            <div className="prompt subtle">
              <MathText text={step.prompt_latex} />
            </div>
          ) : null}
          <div className="reading-body" ref={bodyRef} onMouseUp={onMouseUp}>
            <MathText
              text={step.body_markdown}
              onSentenceClick={beginAnchor}
              onMathClick={(tex, display) => beginAnchor(display ? `$$${tex}$$` : `$${tex}$`)}
              highlighted={highlighted}
            />
          </div>
          <div className="reading-meta mono dim small">
            {words} words · click a sentence or equation, or select any text, to anchor a note
          </div>
          <StepMedia step={step} sessionId={sessionId} />
        </div>

        <div className="margin-stream">
          <div className="margin-head">
            <span>Margin stream</span>
            <span className="mono dim">{draft.readingNotes.length} anchored</span>
          </div>
          {quote !== null ? (
            <div className="anchor-composer">
              <div className="anchor-quote">
                <MathText text={quote} inline />
              </div>
              <textarea
                ref={thoughtRef}
                rows={3}
                value={thought}
                placeholder="What does this make you think? Confusions are the most valuable telemetry."
                onFocus={() => setMicTarget('reading')}
                onChange={(e) => setThought(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    commit();
                  } else if (e.key === 'Escape') {
                    e.stopPropagation();
                    setQuote(null);
                  }
                }}
              />
              <div className="row gap">
                <button className="btn small primary" disabled={!thought.trim()} onClick={commit}>
                  Anchor note ↵
                </button>
                <button className="btn small ghost" onClick={() => setQuote(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
          <div className="notes">
            {draft.readingNotes.length === 0 && quote === null ? (
              <div className="dim small">No anchored notes yet.</div>
            ) : null}
            {draft.readingNotes.map((n, i) => (
              <div key={i} className="note">
                <div className="note-quote">
                  <MathText text={n.quote} inline />
                </div>
                <div className="note-thought">{n.thought}</div>
                <div className="note-foot mono dim">
                  +{fmtT(n.timestamp_ms)}
                  <button className="btn tiny ghost" onClick={() => removeNote(i)} aria-label="Remove note">
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="reading-stream">
        <div className="raw-head">
          <span className="raw-title">Thinking while reading</span>
          {micTarget === 'reading' ? <span className="mic-target mono">● dictation → here</span> : null}
        </div>
        <textarea
          rows={3}
          value={draft.readingStream}
          placeholder="Thinking while reading (stream of consciousness)..."
          onFocus={() => setMicTarget('reading')}
          onChange={(e) => setDraft({ readingStream: e.target.value })}
        />
        <VoiceRow />
      </div>

      <div className="dock-actions">
        <span className="kbd-hint mono">Channel 2 telemetry: {draft.readingNotes.length} notes · {draft.readingStream.trim().split(/\s+/).filter(Boolean).length} streamed words</span>
        <span className="spacer" />
        <button className="btn ghost" disabled={busyAdvance || busySubmit} onClick={() => void advanceStep()} title="POST /advance without logging notes">
          {busyAdvance ? <Spinner /> : null}Skip notes →
        </button>
        <button
          className="btn primary"
          disabled={!hasTelemetry || busySubmit || busyAdvance}
          onClick={() => void submitStep()}
          title="POST /submit with thinking_while_reading"
        >
          {busySubmit ? <Spinner /> : null}Submit notes &amp; continue →
        </button>
      </div>
    </div>
  );
}
