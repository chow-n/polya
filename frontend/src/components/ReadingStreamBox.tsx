/**
 * Explanation card (READING steps): a short text with its diagram or demo.
 *  - selecting any text offers "Add a thought" (an anchored thinking-while-reading note)
 *  - Continue: POST /submit with the notes when there are any, POST /advance otherwise (same as before)
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { ArtifactOut, StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { Details, MathField, PrimaryButton, Spinner, useEscape, usePrimaryAction } from './kit';
import SandboxDemoViewer from './SandboxDemoViewer';
import { CardHead, StepDetails, cleanPrompt } from './stepParts';

export function useArtifact(id: string | null): ArtifactOut | undefined {
  const art = useHarnessStore((s) => (id ? s.artifactCache[id] : undefined));
  const fetchArtifact = useHarnessStore((s) => s.fetchArtifact);
  useEffect(() => {
    if (id && !art) void fetchArtifact(id);
  }, [id, art, fetchArtifact]);
  return art;
}

/** The step's diagram (SVG) and/or interactive demo. */
export function StepMedia({ step, sessionId }: { step: StepPayload; sessionId: string | null }): JSX.Element | null {
  const demo = useArtifact(step.demo_artifact_id);
  const svg = useArtifact(step.svg_artifact_id);
  if (!step.demo_artifact_id && !step.svg_artifact_id) return null;
  return (
    <div className="media">
      {step.svg_artifact_id ? (
        svg ? (
          <figure className="figure">
            <img alt={svg.title} src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg.payload_text)}`} />
          </figure>
        ) : (
          <div className="figure loading">
            <Spinner /> Drawing a diagram…
          </div>
        )
      ) : null}
      {step.demo_artifact_id ? (
        demo ? (
          <SandboxDemoViewer artifact={demo} sessionId={sessionId} height={400} minimal />
        ) : (
          <div className="figure loading">
            <Spinner /> Loading the demo…
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
  const submitStep = useHarnessStore((s) => s.submitStep);
  const advanceStep = useHarnessStore((s) => s.advanceStep);
  const busySubmit = useHarnessStore((s) => s.busy.submit);
  const busyAdvance = useHarnessStore((s) => s.busy.advance);
  const sessionId = useHarnessStore((s) => s.activeSessionId);
  const bodyRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLElement>(null);
  /** null = composer closed; '' = a general thought; text = the selected quote */
  const [quote, setQuote] = useState<string | null>(null);
  const [offer, setOffer] = useState<{ text: string; x: number; y: number } | null>(null);

  const highlighted = useMemo(() => new Set(draft.readingNotes.map((n) => n.quote).filter(Boolean)), [draft.readingNotes]);
  const busy = busySubmit || busyAdvance;
  const hasTelemetry = draft.readingNotes.length > 0 || draft.readingStream.trim().length > 0;

  const onMouseUp = (): void => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !bodyRef.current || !cardRef.current) {
      setOffer(null);
      return;
    }
    const range = sel.getRangeAt(0);
    if (!bodyRef.current.contains(range.commonAncestorContainer)) return;
    const text = sel.toString().replace(/\s+/g, ' ').trim();
    if (text.length < 3) return;
    const r = range.getBoundingClientRect();
    const c = cardRef.current.getBoundingClientRect();
    setOffer({ text: text.slice(0, 500), x: Math.max(8, Math.min(c.width - 140, r.left - c.left + r.width / 2 - 60)), y: r.bottom - c.top + 8 });
  };

  const openComposer = (q: string): void => {
    setQuote(q);
    setOffer(null);
  };

  const commit = (): void => {
    const thought = draft.readingStream.trim();
    if (!thought) return;
    addNote({ quote: quote ?? '', thought });
    setDraft({ readingStream: '' });
    setQuote(null);
    window.getSelection()?.removeAllRanges();
  };

  const proceed = (): void => {
    if (busy) return;
    if (hasTelemetry) void submitStep();
    else void advanceStep();
  };

  useEscape(() => {
    setQuote(null);
    setOffer(null);
  }, quote !== null || offer !== null);
  usePrimaryAction(proceed, !busy);

  return (
    <article className="card reading" ref={cardRef}>
      <CardHead step={step} />
      {step.prompt_latex ? (
        <div className="prompt">
          <MathText text={cleanPrompt(step.prompt_latex)} />
        </div>
      ) : null}
      <div className="reading-body" ref={bodyRef} onMouseUp={onMouseUp}>
        <MathText text={step.body_markdown} highlighted={highlighted} />
      </div>
      {offer ? (
        <button
          className="thought-offer"
          style={{ left: offer.x, top: offer.y }}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => openComposer(offer.text)}
        >
          Add a thought
        </button>
      ) : null}

      <StepMedia step={step} sessionId={sessionId} />

      {draft.readingNotes.length ? (
        <ul className="notes" aria-label="Your thoughts">
          {draft.readingNotes.map((n, i) => (
            <li key={i} className="note">
              {n.quote ? (
                <blockquote>
                  <MathText text={n.quote} inline />
                </blockquote>
              ) : null}
              <p>{n.thought}</p>
              <button className="icon-btn" onClick={() => removeNote(i)} aria-label="Remove this thought" title="Remove">
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {quote !== null ? (
        <div className="composer">
          {quote ? (
            <blockquote>
              <MathText text={quote} inline />
            </blockquote>
          ) : null}
          <MathField
            label="Your thought"
            placeholder="What does this make you think? Confusions are especially useful."
            value={draft.readingStream}
            onChange={(v) => setDraft({ readingStream: v })}
            micTarget="reading"
            rows={2}
            autoFocus
          />
          <div className="row">
            <button className="btn-secondary" disabled={!draft.readingStream.trim()} onClick={commit}>
              Save thought
            </button>
            <button className="text-btn" onClick={() => setQuote(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      <div className="actions spread">
        {quote === null ? (
          <button className="text-btn" onClick={() => openComposer('')}>
            Add a thought
          </button>
        ) : (
          <span />
        )}
        <PrimaryButton onClick={proceed} busy={busy} busyLabel="Preparing your next step…">
          Continue
        </PrimaryButton>
      </div>

      <Details>
        <StepDetails step={step} />
      </Details>
    </article>
  );
}
