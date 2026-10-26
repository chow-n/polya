/**
 * Ask Pólya: the session's side chat (docs/specs/explain). It follows the card on screen (the held result card, else the
 * active step): quick chips (Explain this · Explain differently · Simpler), any free-text question, the say-it-back box
 * under the latest explanation and the session's sources. Docked right on wide screens, a bottom sheet on phones.
 */
import { useCallback } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { StepPayload } from '../types/harness';
import { ChatMessages, Composer, SourcesList } from './ChatThread';
import { useEscape } from './kit';
import { useStepHeading } from './stepParts';

export default function AskPanel({ step }: { step: StepPayload }): JSX.Element {
  const chat = useHarnessStore((s) => s.chat);
  const busy = useHarnessStore((s) => Boolean(s.busy.explain));
  const st = useHarnessStore((s) => s.sessionState);
  const graph = useHarnessStore((s) => s.graph);
  const askPolya = useHarnessStore((s) => s.askPolya);
  const setChatOpen = useHarnessStore((s) => s.setChatOpen);
  const heading = useStepHeading(step);
  const close = useCallback(() => setChatOpen(false), [setChatOpen]);
  useEscape(close, true);

  const dividers = (stepIndex: number): string | null => {
    const hist = st?.session.history_steps.find((h) => h.step_index === stepIndex) as { node_id?: string } | undefined;
    const nid = hist?.node_id ?? (st?.active_step.step_index === stepIndex ? st.active_step.target_node_ids[0] : undefined);
    const title = nid ? graph?.nodes.find((n) => n.id === nid)?.title ?? st?.session.dependency_plan.find((p) => p.node_id === nid)?.title : null;
    return `Card ${stepIndex + 1}${title ? ` · ${title}` : ''}`;
  };

  return (
    <aside className="ask-panel" aria-label="Ask Pólya">
      <header className="ask-head">
        <div>
          <p className="ask-title">Ask Pólya</p>
          {heading ? <p className="ask-about">About: {heading}</p> : null}
        </div>
        <button className="text-btn" onClick={close} aria-label="Close Ask Pólya" title="Close (Esc)">
          Close
        </button>
      </header>
      <div className="ask-chips chips">
        <button className="chip" disabled={busy} onClick={() => void askPolya('EXPLAIN')}>
          Explain this
        </button>
        <button className="chip" disabled={busy} onClick={() => void askPolya('DIFFERENT')}>
          Explain differently
        </button>
        <button className="chip" disabled={busy} onClick={() => void askPolya('SIMPLER')}>
          Simpler
        </button>
      </div>
      <div className="ask-scroll" aria-live="polite">
        {chat.thread.length || chat.pending ? (
          <ChatMessages messages={chat.thread} pending={chat.pending} writing={busy} dividers={dividers} />
        ) : (
          <p className="ask-empty">
            Ask anything about this card, or press <b>Explain this</b>. Asking never changes your score.
          </p>
        )}
      </div>
      <Composer onSend={(t) => void askPolya('ASK', { message: t })} disabled={busy} placeholder="Ask a question…" autoFocus />
      <SourcesList sources={chat.sources} />
    </aside>
  );
}
