/**
 * Live voice/prosody meter (Advanced telemetry only): mic toggle, 12-bar level visualiser and the raw prosody numbers
 * (latency, pauses, hedges, WPM, silence). The everyday mic lives inside each text field (kit.tsx MicButton).
 */
import { useRef } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';

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

