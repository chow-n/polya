/**
 * Pólya UI kit: the few primitives every screen shares.
 *  - usePrimaryAction / useEscape: one Cmd/Ctrl+Enter target and an Esc stack for the whole app
 *  - Details: the collapsed disclosure at the bottom of each card that holds every advanced number
 *  - ConfidenceChips: Guessing 0.15 · Unsure 0.4 · Fairly sure 0.7 · Certain 0.9
 *  - MathField: textarea with an inline mic, a "∑" snippet toolbar and a LaTeX preview that only appears for LaTeX
 */
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useHarnessStore, type MicTarget } from '../store/useHarnessStore';
import type { Outcome } from '../types/harness';
import { MathText, hasMathDelimiters, looksLikeBareTex } from '../utils/katexRenderer';

// ------------------------------------------------------------------ keyboard registries
interface Entry {
  fn: React.MutableRefObject<() => void>;
  on: React.MutableRefObject<boolean>;
}
const primaryStack: Entry[] = [];
const escapeStack: Entry[] = [];

function useStack(stack: Entry[], fn: () => void, enabled: boolean): void {
  const fnRef = useRef(fn);
  const onRef = useRef(enabled);
  fnRef.current = fn;
  onRef.current = enabled;
  useEffect(() => {
    const e: Entry = { fn: fnRef, on: onRef };
    stack.push(e);
    return () => {
      const i = stack.lastIndexOf(e);
      if (i >= 0) stack.splice(i, 1);
    };
  }, [stack]);
}

/** Registers the card's primary action for Cmd/Ctrl+Enter (the most recently mounted registration wins). */
export function usePrimaryAction(fn: () => void, enabled: boolean): void {
  useStack(primaryStack, fn, enabled);
}

/** Registers something Esc should close while `active` (most recently mounted first). */
export function useEscape(fn: () => void, active: boolean): void {
  useStack(escapeStack, fn, active);
}

export function runPrimaryAction(): boolean {
  const top = primaryStack[primaryStack.length - 1];
  if (!top) return false;
  if (top.on.current) top.fn.current();
  return true;
}

export function runEscape(): boolean {
  for (let i = escapeStack.length - 1; i >= 0; i--) {
    if (escapeStack[i].on.current) {
      escapeStack[i].fn.current();
      return true;
    }
  }
  return false;
}

export const MOD_KEY = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl';

// ------------------------------------------------------------------ small pieces
export function Spinner({ label }: { label?: string }): JSX.Element {
  return <span className="spin" role={label ? 'status' : undefined} aria-label={label} aria-hidden={label ? undefined : true} />;
}

export function PrimaryButton({
  children,
  onClick,
  disabled,
  busy,
  busyLabel,
  shortcut = true,
  title,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  busyLabel?: string;
  shortcut?: boolean;
  title?: string;
}): JSX.Element {
  return (
    <button className="btn-primary" onClick={onClick} disabled={disabled || busy} title={title} aria-busy={busy || undefined}>
      {busy ? (
        <>
          <Spinner />
          {busyLabel ?? children}
        </>
      ) : (
        children
      )}
      {shortcut && !busy ? <kbd className="kbd">{MOD_KEY} ↵</kbd> : null}
    </button>
  );
}

/** Collapsed disclosure at the bottom of a card. Everything technical lives in here. */
export function Details({ children, label = 'Details' }: { children: ReactNode; label?: string }): JSX.Element {
  const [open, setOpen] = useState(false);
  const id = useId();
  useEscape(() => setOpen(false), open);
  return (
    <div className={`details${open ? ' open' : ''}`}>
      <button className="details-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
        <span className="chev" aria-hidden="true" />
        {label}
      </button>
      {open ? (
        <div className="details-body" id={id}>
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function DetailRow({ k, children }: { k: ReactNode; children: ReactNode }): JSX.Element {
  return (
    <div className="drow">
      <span className="drow-k">{k}</span>
      <span className="drow-v">{children}</span>
    </div>
  );
}

// ------------------------------------------------------------------ confidence
export const CHIPS: { v: number; label: string; title: string }[] = [
  { v: 0.15, label: 'Guessing', title: 'About 15% sure' },
  { v: 0.4, label: 'Unsure', title: 'About 40% sure' },
  { v: 0.7, label: 'Fairly sure', title: 'About 70% sure' },
  { v: 0.9, label: 'Certain', title: 'About 90% sure. If you are certain and wrong, Pólya brings this idea back sooner.' },
];

export function isChipValue(c: number): boolean {
  return CHIPS.some((x) => Math.abs(x.v - c) < 1e-9);
}

export function ConfidenceChips({
  value,
  onChange,
  disabled,
  label = 'How sure are you?',
}: {
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
  label?: string;
}): JSX.Element {
  const id = useId();
  return (
    <div className="conf">
      <span className="conf-q" id={id}>
        {label}
      </span>
      <div className="chips" role="radiogroup" aria-labelledby={id}>
        {CHIPS.map((c) => {
          const on = Math.abs(c.v - value) < 1e-9;
          return (
            <button
              key={c.v}
              role="radio"
              aria-checked={on}
              className={`chip${on ? ' on' : ''}`}
              disabled={disabled}
              title={c.title}
              onClick={() => onChange(c.v)}
            >
              {c.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ voice
export function MicButton({ target }: { target: MicTarget }): JSX.Element {
  const voice = useHarnessStore((s) => s.voice);
  const micTarget = useHarnessStore((s) => s.micTarget);
  const setMicTarget = useHarnessStore((s) => s.setMicTarget);
  const toggleMic = useHarnessStore((s) => s.toggleMic);
  const levels = useHarnessStore((s) => s.voiceLevels);
  const live = voice.recording && micTarget === target;
  const level = live ? Math.min(1, (levels.reduce((a, b) => a + b, 0) / Math.max(1, levels.length)) * 2.4) : 0;
  const unsupported = voice.micAvailable === false && !voice.recognitionAvailable;

  const onClick = (): void => {
    if (voice.recording && micTarget !== target) {
      setMicTarget(target);
      return;
    }
    setMicTarget(target);
    void toggleMic();
  };

  return (
    <button
      type="button"
      className={`tool mic${live ? ' live' : ''}${voice.starting ? ' starting' : ''}`}
      style={live ? ({ '--lvl': level.toFixed(3) } as React.CSSProperties) : undefined}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      aria-pressed={live}
      aria-label={live ? 'Stop dictation' : 'Dictate'}
      title={unsupported ? 'No microphone available' : live ? 'Stop dictation (Ctrl+Space)' : 'Dictate (Ctrl+Space)'}
    >
      <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
        <rect x="7" y="2.5" width="6" height="10" rx="3" fill="currentColor" />
        <path d="M4.5 9.5a5.5 5.5 0 0 0 11 0M10 15v2.5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      </svg>
    </button>
  );
}

// ------------------------------------------------------------------ math field
const SNIPPETS: { label: string; tex: string; caret?: number }[] = [
  { label: 'a⁄b', tex: '\\frac{}{}', caret: 6 },
  { label: 'Σ', tex: '\\sum_{i=1}^{n} ' },
  { label: '∫', tex: '\\int_{}^{} \\, d', caret: 6 },
  { label: '𝔼[·]', tex: '\\mathbb{E}[]', caret: 11 },
  { label: 'Var', tex: '\\text{Var}()', caret: 11 },
  { label: '∇', tex: '\\nabla ' },
  { label: '√', tex: '\\sqrt{}', caret: 6 },
  { label: 'xᵀ', tex: '^\\top ' },
  { label: '⟨·,·⟩', tex: '\\langle , \\rangle', caret: 8 },
  { label: '‖·‖', tex: '\\|\\|', caret: 2 },
  { label: '2×2', tex: '\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}' },
  { label: '$…$', tex: '$$', caret: 1 },
];

export function hasLatex(s: string): boolean {
  return /[$\\]/.test(s);
}

export function MathField({
  value,
  onChange,
  label,
  placeholder,
  micTarget,
  rows = 3,
  readOnly,
  autoFocus,
  onShiftEnter,
  hint,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  placeholder?: string;
  micTarget: MicTarget;
  rows?: number;
  readOnly?: boolean;
  autoFocus?: boolean;
  onShiftEnter?: () => void;
  hint?: ReactNode;
}): JSX.Element {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [snips, setSnips] = useState(false);
  const setMicTarget = useHarnessStore((s) => s.setMicTarget);
  const micTargetNow = useHarnessStore((s) => s.micTarget);
  const voice = useHarnessStore((s) => s.voice);
  const id = useId();
  const valueRef = useRef(value);
  valueRef.current = value;

  const insert = useCallback(
    (tex: string, caret?: number) => {
      const ta = taRef.current;
      const cur = valueRef.current;
      const start = ta ? ta.selectionStart : cur.length;
      const end = ta ? ta.selectionEnd : cur.length;
      onChange(cur.slice(0, start) + tex + cur.slice(end));
      const pos = start + (caret ?? tex.length);
      requestAnimationFrame(() => {
        if (!ta) return;
        ta.focus();
        ta.setSelectionRange(pos, pos);
      });
    },
    [onChange],
  );

  const showPreview = !readOnly && value.trim() !== '' && hasLatex(value);
  const previewText = hasMathDelimiters(value) || !looksLikeBareTex(value) ? value : `$$${value}$$`;
  const listening = voice.recording && micTargetNow === micTarget && !readOnly;

  return (
    <div className={`field${readOnly ? ' readonly' : ''}${listening ? ' listening' : ''}`}>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {snips && !readOnly ? (
        <div className="snips" role="toolbar" aria-label="Math snippets">
          {SNIPPETS.map((s) => (
            <button key={s.label} type="button" className="snip" title={s.tex} onMouseDown={(e) => e.preventDefault()} onClick={() => insert(s.tex, s.caret)}>
              {s.label}
            </button>
          ))}
        </div>
      ) : null}
      <div className="field-box">
        <textarea
          id={id}
          ref={taRef}
          rows={rows}
          value={value}
          readOnly={readOnly}
          autoFocus={autoFocus}
          placeholder={placeholder}
          spellCheck
          onFocus={() => setMicTarget(micTarget)}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && e.shiftKey && onShiftEnter) {
              e.preventDefault();
              onShiftEnter();
            }
          }}
        />
        {!readOnly ? (
          <div className="field-tools">
            <button
              type="button"
              className={`tool sigma${snips ? ' on' : ''}`}
              aria-pressed={snips}
              aria-label="Math symbols"
              title="Math symbols"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => setSnips((v) => !v)}
            >
              ∑
            </button>
            <MicButton target={micTarget} />
          </div>
        ) : null}
      </div>
      {listening && (voice.interim || voice.error) ? (
        <div className="field-note" aria-live="polite">
          {voice.error ? <span className="warn">{voice.error}</span> : <span className="interim">{voice.interim}</span>}
        </div>
      ) : hint ? (
        <div className="field-note">{hint}</div>
      ) : null}
      {showPreview ? (
        <div className="preview" aria-live="polite">
          <MathText text={previewText} />
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ results
export function outcomeHeadline(o: Outcome, kind: string): { tone: 'good' | 'bad' | 'mid' | 'plain'; text: string } {
  switch (o) {
    case 'SOLVED_CLEAN':
      return { tone: 'good', text: kind === 'PROBE' || kind === 'CHECK' ? 'Correct' : kind === 'REFEREE' ? 'You found the flaw' : 'Solved' };
    case 'SOLVED_WITH_HINTS':
      return { tone: 'good', text: 'Solved, with hints' };
    case 'PARTIAL':
      return { tone: 'mid', text: 'Partly there' };
    case 'FAILED':
      return { tone: 'bad', text: 'Not quite' };
    case 'HIGH_CONFIDENCE_ERROR':
      return { tone: 'bad', text: 'Not quite, and you were sure' };
    case 'EXPLORATION_LOGGED':
      return { tone: 'plain', text: 'Saved' };
  }
}

const TECH = /hypercorrection|Δ|belief update|plan DAG|boundary conditions stated|violated-hypothesis|symbolic verifier|concept coverage|stability|reading note\(s\) captured|prediction locked|trace quality|miss class|shadow node|BUGGY_RULE|guess rate|slip penalty/i;

/** Plain-language rewrites for the server's technical feedback lines (the original always goes under Details). */
const PLAIN_LINES: [RegExp, (m: RegExpExecArray) => string | null][] = [
  [/^\*\*Node:\*\*/, () => null],
  [/^\*\*Objective result:\*\*/, () => null],
  [/^Recorded shadow node/, () => null],
  [/^Belief update over the plan DAG/, () => null],
  [/^⚠️\s*\*\*Right answer, weak reasoning/, () => 'Right answer, but your guess didn’t show the reasoning yet, so it counts a little less.'],
  [/^Benign miss/, () => 'This looks like a small slip, not a misunderstanding.'],
  [/^A premise of this node has low mastery/, () => 'Something this idea builds on needs work first, so Pólya will add a step for it.'],
  [/^Matched misconception: \*\*([^*]+)\*\*/, (m) => `This looks like a common mistake: **${m[1]}**.`],
  [/^🔥/, () => 'You were sure about this one, so Pólya will bring it back soon.'],
  [/^🎯\s*Hypercorrection resolved/, () => 'You fixed a mistake you were once sure about. That kind of correction tends to stick.'],
  [/^↩︎?\s*Δ dropped/, () => 'Pólya added a smaller step before coming back to this idea.'],
  [/^⏩/, () => 'You are getting most of these right, so the next steps will be a little harder.'],
  [/^⏪/, () => null],
  [/^Concept coverage (\d+)\/(\d+)\.\s*(.*)$/s, (m) => `You covered ${m[1]} of ${m[2]} key ideas.${m[3] ? ` ${m[3]}` : ''}`],
  [/^Boundary conditions stated: (\d+)\/(\d+)\.\s*(.*)$/s, (m) => `You covered ${m[1]} of ${m[2]} edge cases.${m[3] ? ` ${m[3]}` : ''}`],
  [/^Violated-hypothesis keywords named/, () => null],
];

/** Split server feedback into plain lines (shown inline) and technical ones (moved under Details). */
export function plainFeedback(md: string): { main: string[]; tech: string[] } {
  const main: string[] = [];
  const tech: string[] = [];
  const push = (t: string): void => {
    if (t && !main.includes(t)) main.push(t);
  };
  for (const para of md.split(/\n{2,}/)) {
    const keep: string[] = [];
    for (const raw of para.split('\n')) {
      let line = raw.trim();
      if (!line) continue;
      const rule = PLAIN_LINES.find(([re]) => re.test(line));
      if (rule) {
        tech.push(line);
        const plain = rule[1](rule[0].exec(line) as RegExpExecArray);
        if (plain) push(plain);
        continue;
      }
      line = line.replace(/^✅\s*/, '').replace(/^❌\s*Not quite\s*[—-]\s*the/, 'The').replace(/^❌\s*/, '').replace(/^Correct\.\s*/, '');
      if (!line) continue;
      if (TECH.test(line)) tech.push(line);
      else keep.push(line);
    }
    if (keep.length) push(keep.join('\n'));
  }
  return { main, tech };
}

/** Option id named in "the answer was **X**" feedback, if any. */
export function correctFromFeedback(md: string): string | null {
  const m = /answer was \*\*([^*]+)\*\*/.exec(md);
  return m ? m[1].trim() : null;
}
