/**
 * The conversation shared by Ask Pólya (side chat) and the learning chat (LEARN card): messages, the "say it back"
 * box under the latest explanation, the composer and the Sources list (docs/specs/explain, docs/specs/learn-chat).
 */
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { ExplainMsg, SourceOut } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { Spinner } from './kit';

function MsgNote({ m }: { m: ExplainMsg }): JSX.Element | null {
  const notes: string[] = [];
  if (m.engine === 'deterministic') notes.push('offline explanation');
  if (m.meta.engine_note) notes.push(m.meta.engine_note);
  if (!notes.length) return null;
  return <p className="msg-note">{notes.join(' · ')}</p>;
}

function SayBackBox({ m }: { m: ExplainMsg }): JSX.Element {
  const sayBack = useHarnessStore((s) => s.sayBack);
  const busy = useHarnessStore((s) => s.busy.sayBack);
  const [text, setText] = useState('');
  const [skipped, setSkipped] = useState(false);
  if (skipped) return <></>;
  const send = (): void => {
    if (text.trim().length < 8) return;
    void sayBack(text.trim(), m.id).then((r) => {
      if (r) setText('');
    });
  };
  return (
    <div className="sayback">
      <p className="sayback-q">
        <span className="sayback-k">Say it back in one line</span>
        <MathText text={m.meta.say_back_prompt ?? ''} inline />
      </p>
      <div className="sayback-row">
        <input
          className="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Say it back…"
          aria-label="Say it back in one line"
          disabled={busy}
        />
        <button className="btn-secondary" onClick={send} disabled={busy || text.trim().length < 8}>
          {busy ? <Spinner /> : 'Check'}
        </button>
        <button className="text-btn" onClick={() => setSkipped(true)}>
          Skip
        </button>
      </div>
    </div>
  );
}

export function ChatMessages({ messages, pending, writing, showSayBack = true, dividers }: {
  messages: ExplainMsg[];
  pending: string | null;
  writing: boolean;
  showSayBack?: boolean;
  /** Title for a step's messages, shown where the conversation moves to another card. */
  dividers?: (stepIndex: number) => string | null;
}): JSX.Element {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // inside the side panel scroll only the panel; on the learning card bring the newest message into view
    const box = end.current?.closest('.ask-scroll');
    if (box) box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
    else end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [messages.length, pending, writing]);
  const answered = new Set(messages.filter((m) => m.role === 'say_back').map((m) => m.meta.answering));
  const lastPolya = [...messages].reverse().find((m) => m.role === 'polya');
  let lastStep = -1;
  return (
    <div className="chat-msgs">
      {messages.map((m) => {
        const div = dividers && m.step_index !== lastStep ? dividers(m.step_index) : null;
        lastStep = m.step_index;
        return (
          <div key={m.id} className="msg-row">
            {div ? <p className="chat-divider">{div}</p> : null}
            {m.role === 'polya' ? (
              <div className="msg polya">
                <MathText text={m.text} className="msg-body" />
                <MsgNote m={m} />
                {showSayBack && m === lastPolya && m.meta.say_back_prompt && !answered.has(m.id) && !writing ? (
                  <SayBackBox m={m} />
                ) : null}
              </div>
            ) : (
              <div className={`msg learner${m.role === 'say_back' ? ' sayback-msg' : ''}`}>
                <p className="msg-body">{m.text}</p>
                {m.role === 'say_back' && m.meta.verdict ? (
                  <p className={`msg-verdict ${m.meta.is_correct ? 'good' : 'mid'}`}>
                    <MathText text={m.meta.verdict} inline />
                  </p>
                ) : null}
              </div>
            )}
          </div>
        );
      })}
      {pending ? (
        <div className="msg-row">
          <div className="msg learner">
            <p className="msg-body">{pending}</p>
          </div>
        </div>
      ) : null}
      {writing ? (
        <p className="msg-writing" role="status">
          <Spinner /> Pólya is writing… (up to ~30 s)
        </p>
      ) : null}
      <div ref={end} />
    </div>
  );
}

export function Composer({ onSend, disabled, placeholder, autoFocus }: {
  onSend: (text: string) => void;
  disabled: boolean;
  placeholder: string;
  autoFocus?: boolean;
}): JSX.Element {
  const [text, setText] = useState('');
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (autoFocus) box.current?.focus({ preventScroll: true });   // never scroll the page to reach the composer
  }, [autoFocus]);
  const send = (): void => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText('');
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      send();
    }
  };
  return (
    <div className="composer">
      <textarea
        className="chat-input"
        rows={2}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        placeholder={placeholder}
        aria-label={placeholder}
        ref={box}
      />
      <button className="btn-secondary" onClick={send} disabled={disabled || !text.trim()}>
        Send
      </button>
    </div>
  );
}

const KIND_LABEL: Record<SourceOut['kind'], string> = { notes: 'your notes', paper: 'paper', wikipedia: 'Wikipedia', arxiv: 'arXiv' };

export function SourcesList({ sources }: { sources: SourceOut[] }): JSX.Element | null {
  if (!sources.length) return null;
  return (
    <details className="sources">
      <summary>Sources ({sources.length})</summary>
      <ol>
        {sources.map((s) => (
          <li key={s.n} value={s.n}>
            {s.url ? (
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
            ) : (
              <code>{s.title}</code>
            )}{' '}
            <span className="muted">{KIND_LABEL[s.kind]}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}
