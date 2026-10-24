/**
 * Tri-Modal Telemetry Input Dock (ARCHITECTURE_SPEC §6.2):
 *   1. LaTeX-aware textarea + live KaTeX preview strip + quick snippet toolbar + scratch.tex pull/push/live-sync
 *   2. Voice dictation (push-to-talk or Ctrl+Space) with a 12-bar level visualiser and live prosody metrics
 *   3. Epistemic confidence slider (0–100%) with the ≥75% hypercorrection warning
 */
import { useCallback, useRef, type ReactNode } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import { MathText, hasMathDelimiters, looksLikeBareTex } from '../utils/katexRenderer';
import { Spinner } from './ui';

export interface DockAction {
  label: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  title?: string;
  kind?: 'primary' | 'ghost' | 'danger';
}

export interface TelemetryInputDockProps {
  label: string;
  placeholder: string;
  actions?: DockAction[];
  /** Shift+Enter handler (practice chunk / duel message / submit). */
  onShiftEnter?: () => void;
  shiftEnterLabel?: string;
  showConfidence?: boolean;
  disabled?: boolean;
  rows?: number;
}

const SNIPPETS: { label: string; tex: string; caret?: number; title: string }[] = [
  { label: 'a/b', tex: '\\frac{}{}', caret: 6, title: '\\frac{}{}' },
  { label: 'Σ', tex: '\\sum_{i=1}^{n} ', title: '\\sum_{i=1}^{n}' },
  { label: '∫', tex: '\\int_{}^{} \\, d', caret: 6, title: '\\int_{}^{}' },
  { label: '𝔼[·]', tex: '\\mathbb{E}[]', caret: 11, title: '\\mathbb{E}[]' },
  { label: 'Var(·)', tex: '\\text{Var}()', caret: 11, title: '\\text{Var}()' },
  { label: '∇', tex: '\\nabla ', title: '\\nabla' },
  { label: '√', tex: '\\sqrt{}', caret: 6, title: '\\sqrt{}' },
  { label: 'xᵀ', tex: '^\\top ', title: '^\\top' },
  { label: '⟨·,·⟩', tex: '\\langle , \\rangle', caret: 8, title: '\\langle u, v \\rangle' },
  { label: '‖·‖', tex: '\\|\\|', caret: 2, title: '\\| x \\|' },
  { label: '[2×2]', tex: '\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}', title: '2×2 pmatrix' },
  { label: '[n×n]', tex: '\\begin{bmatrix} a_{11} & \\cdots & a_{1n} \\\\ \\vdots & \\ddots & \\vdots \\\\ a_{n1} & \\cdots & a_{nn} \\end{bmatrix}', title: 'n×n bmatrix' },
  { label: '$…$', tex: '$$', caret: 1, title: 'inline math delimiters' },
];

export default function TelemetryInputDock({
  label,
  placeholder,
  actions = [],
  onShiftEnter,
  shiftEnterLabel,
  showConfidence = true,
  disabled = false,
  rows = 4,
}: TelemetryInputDockProps): JSX.Element {
  const text = useHarnessStore((s) => s.draft.text);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const setMicTarget = useHarnessStore((s) => s.setMicTarget);
  const micTarget = useHarnessStore((s) => s.micTarget);
  const liveSync = useHarnessStore((s) => s.scratchLiveSync);
  const setLiveSync = useHarnessStore((s) => s.setScratchLiveSync);
  const scratch = useHarnessStore((s) => s.scratch);
  const pushScratchWs = useHarnessStore((s) => s.pushScratchWs);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const insert = useCallback(
    (tex: string, caret?: number) => {
      const ta = taRef.current;
      const cur = useHarnessStore.getState().draft.text;
      const start = ta ? ta.selectionStart : cur.length;
      const end = ta ? ta.selectionEnd : cur.length;
      const next = cur.slice(0, start) + tex + cur.slice(end);
      setDraft({ text: next });
      const pos = start + (caret ?? tex.length);
      requestAnimationFrame(() => {
        if (!ta) return;
        ta.focus();
        ta.setSelectionRange(pos, pos);
      });
    },
    [setDraft],
  );

  const previewText = text.trim()
    ? hasMathDelimiters(text) || !looksLikeBareTex(text)
      ? text
      : `$$${text}$$`
    : '';

  return (
    <div className={`dock${disabled ? ' disabled' : ''}`}>
      <div className="dock-head">
        <span className="dock-label">{label}</span>
        {micTarget === 'dock' ? <span className="mic-target mono">● dictation → here</span> : null}
        <span className="spacer" />
        <label className="toggle small" title="Mirror workspace/scratch.tex into this box whenever it is saved in the terminal">
          <input type="checkbox" checked={liveSync} onChange={(e) => setLiveSync(e.target.checked)} />
          <span className="toggle-track" />
          <span>live-sync scratch.tex</span>
        </label>
        <button
          className="btn tiny ghost"
          disabled={!scratch}
          onClick={() => scratch && setDraft({ text: text ? `${text}\n${scratch.content}` : scratch.content })}
          title="Append the current contents of workspace/scratch.tex"
        >
          ⇣ pull
        </button>
        <button
          className="btn tiny ghost"
          disabled={!text.trim()}
          onClick={() => pushScratchWs(text)}
          title="Write this box to workspace/scratch.tex (scratch_write over WebSocket)"
        >
          ⇡ push
        </button>
      </div>

      <div className="snippets" role="toolbar" aria-label="Math snippets">
        {SNIPPETS.map((s) => (
          <button key={s.label} className="snip" title={s.title} onMouseDown={(e) => e.preventDefault()} onClick={() => insert(s.tex, s.caret)}>
            {s.label}
          </button>
        ))}
      </div>

      <textarea
        ref={taRef}
        className="dock-input"
        rows={rows}
        spellCheck={false}
        value={text}
        disabled={disabled}
        placeholder={placeholder}
        onFocus={() => setMicTarget('dock')}
        onChange={(e) => setDraft({ text: e.target.value })}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && e.shiftKey && onShiftEnter) {
            e.preventDefault();
            onShiftEnter();
          }
        }}
      />
      <div className="preview-strip" aria-live="polite">
        <span className="preview-tag mono">KaTeX</span>
        <div className="preview-body">{previewText ? <MathText text={previewText} /> : <span className="dim">live preview of your LaTeX appears here</span>}</div>
      </div>

      <VoiceRow />

      {showConfidence ? <ConfidenceSlider /> : null}

      <div className="dock-actions">
        {shiftEnterLabel ? <span className="kbd-hint mono">Shift+Enter · {shiftEnterLabel}</span> : null}
        <span className="spacer" />
        {actions.map((a, i) => (
          <button
            key={i}
            className={`btn ${a.kind ?? 'primary'}`}
            onClick={a.onClick}
            disabled={disabled || a.disabled || a.busy}
            title={a.title}
          >
            {a.busy ? <Spinner /> : null}
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ voice
export function VoiceRow(): JSX.Element {
  const voice = useHarnessStore((s) => s.voice);
  const toggleMic = useHarnessStore((s) => s.toggleMic);
  const micTarget = useHarnessStore((s) => s.micTarget);
  const downAt = useRef(0);
  const startedByPress = useRef(false);

  const onPointerDown = (): void => {
    downAt.current = performance.now();
    startedByPress.current = !voice.recording;
    if (!voice.recording) void toggleMic();
  };
  const onPointerUp = (): void => {
    const held = performance.now() - downAt.current;
    if (startedByPress.current && held > 380) {
      // push-to-talk: release ends the utterance
      void toggleMic();
    } else if (!startedByPress.current) {
      // click while recording: stop
      void toggleMic();
    }
    startedByPress.current = false;
  };

  const m = voice.metrics;
  const unsupported = voice.micAvailable === false && !voice.recognitionAvailable;
  return (
    <div className="voice-row">
      <button
        className={`mic-btn${voice.recording ? ' rec' : ''}${voice.starting ? ' starting' : ''}`}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            void toggleMic();
          }
        }}
        title={
          unsupported
            ? 'No microphone / speech recognition available in this browser'
            : 'Hold to talk, click to toggle (Ctrl+Space)'
        }
        aria-pressed={voice.recording}
      >
        <span className="mic-icon">{voice.recording ? '■' : '🎙'}</span>
        <span className="mono">{voice.starting ? 'arming…' : voice.recording ? 'REC' : 'MIC'}</span>
      </button>
      <LevelBars />
      <div className="prosody">
        <Metric k="Latency" v={`${m.initial_latency_ms}`} u="ms" title="Initial latency: mic start → first voiced frame" />
        <Metric k="Pauses" v={`${m.hesitation_count}`} title="Hesitation pauses: silences ≥ 600 ms after speech onset" warn={m.hesitation_count >= 4} />
        <Metric k="Hedges" v={`${m.hedge_count}`} u={m.hedge_density ? `${(m.hedge_density * 100).toFixed(0)}%` : ''} title='Hedge words: "uh", "um", "maybe", "guess", "wait", "i think", "probably", "not sure", "kind of"' warn={m.hedge_count > 0} />
        <Metric k="WPM" v={`${Math.round(m.wpm)}`} title="Words per minute over the speaking span" />
        <Metric k="Silence" v={`${(m.total_silence_ms / 1000).toFixed(1)}`} u="s" title="Total unvoiced time while recording" />
        <span className="engine-tag mono" title="Transcript engine">
          {voice.engine === 'none' ? (voice.recording ? 'acoustic-only' : 'idle') : voice.engine}
          {voice.recording ? ` · ${voice.dbfs.toFixed(0)}dB/${voice.thresholdDb.toFixed(0)}` : ''}
        </span>
      </div>
      <div className="transcript-line mono">
        {voice.error ? (
          <span className="warn-text">{voice.error}</span>
        ) : voice.interim ? (
          <span className="interim">… {voice.interim}</span>
        ) : voice.recording ? (
          <span className="dim">listening → dictating into {micTarget === 'raw' ? 'raw prediction' : micTarget === 'reading' ? 'reading stream' : 'dock'}</span>
        ) : (
          <span className="dim">Ctrl+Space toggles the mic · dictation goes to the last focused field</span>
        )}
      </div>
    </div>
  );
}

function Metric({ k, v, u, title, warn }: { k: string; v: string; u?: string; title: string; warn?: boolean }): JSX.Element {
  return (
    <span className={`metric${warn ? ' warn' : ''}`} title={title}>
      <span className="metric-k">{k}</span>
      <span className="metric-v mono">{v}</span>
      {u ? <span className="metric-u mono">{u}</span> : null}
    </span>
  );
}

function LevelBars(): JSX.Element {
  const levels = useHarnessStore((s) => s.voiceLevels);
  const voiced = useHarnessStore((s) => s.voice.voiced);
  return (
    <div className={`bars${voiced ? ' voiced' : ''}`} aria-hidden="true">
      {levels.map((l, i) => (
        <span key={i} className="lvl" style={{ transform: `scaleY(${Math.max(0.06, Math.min(1, l * 1.6))})` }} />
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ confidence
const CONF_STOPS: { at: number; label: string }[] = [
  { at: 0, label: 'Pure Guess' },
  { at: 0.25, label: 'Doubtful' },
  { at: 0.5, label: 'Coin Flip' },
  { at: 0.75, label: 'Fairly Confident' },
  { at: 0.95, label: 'Certain' },
];

export function confidenceLabel(c: number): string {
  let best = CONF_STOPS[0].label;
  for (const s of CONF_STOPS) if (c >= s.at - 0.06) best = s.label;
  return c >= 0.95 ? '95%+ Certain' : best;
}

export function ConfidenceSlider(): JSX.Element {
  const confidence = useHarnessStore((s) => s.draft.confidence);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const hot = confidence >= 0.75;
  return (
    <div className={`confidence${hot ? ' hot' : ''}`}>
      <div className="conf-head">
        <span className="conf-label">Epistemic confidence</span>
        <span className="conf-value mono">{Math.round(confidence * 100)}%</span>
        <span className="conf-word">{confidenceLabel(confidence)}</span>
        <span className={`hyper-warn${hot ? ' on' : ''}`} title="An error at ≥75% confidence raises a hypercorrection flag (and a 1.25× stability bonus when later fixed)">
          ⚠ wrong at ≥75% → Hypercorrection Flag
        </span>
      </div>
      <input
        type="range"
        className="conf-range"
        min={0}
        max={100}
        step={1}
        value={Math.round(confidence * 100)}
        onChange={(e) => setDraft({ confidence: Number(e.target.value) / 100 })}
        aria-label="Confidence"
      />
      <div className="conf-ticks mono">
        {CONF_STOPS.map((s) => (
          <button
            key={s.at}
            className="conf-tick"
            style={{ left: `${s.at * 100}%` }}
            onClick={() => setDraft({ confidence: s.at })}
            title={`Set ${Math.round(s.at * 100)}%`}
          >
            {Math.round(s.at * 100)}% {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
