/**
 * Dual-engine voice dictation + acoustic prosody tracker (ARCHITECTURE_SPEC §0.5, §6.2).
 *
 *  Acoustic channel: Web Audio AnalyserNode, RMS dBFS sampled once per animation frame (~60 Hz, 16.7 ms).
 *    - adaptive silence threshold (noise floor + 10 dB, clamped to [-58, -34] dBFS)
 *    - initial_latency_ms   : recording start -> first voiced frame
 *    - hesitation_count     : silences >= 600 ms that occur after speech onset and are followed by more speech
 *    - total_silence_ms     : all unvoiced frame time while recording
 *    - 12-bar log-spaced spectrum levels for the visualiser
 *  Lexical channel: transcript from /ws/dictation (Deepgram nova-3 relay) unless the server replies
 *    `unavailable`, else browser SpeechRecognition / webkitSpeechRecognition.
 *    - wpm                  : transcript words / speaking span
 *    - hedge_count/density  : "uh","um","maybe","guess","wait","i think","probably","not sure","kind of"
 *
 * Degrades gracefully: no mic -> recognition-only (no levels); no recognition -> levels/prosody only;
 * neither -> a clear error state, never a thrown exception.
 */
import type { DictationMessage, ProsodyMetrics } from '../types/harness';

export const HEDGE_PHRASES = ['uh', 'um', 'maybe', 'guess', 'wait', 'i think', 'probably', 'not sure', 'kind of'];
export const BAR_COUNT = 12;
export const HESITATION_MS = 600;
const FRAME_CAP_MS = 100;

export type TranscriptEngine = ProsodyMetrics['engine'];

export interface VoiceState {
  recording: boolean;
  starting: boolean;
  engine: TranscriptEngine;
  metrics: ProsodyMetrics;
  interim: string;
  transcript: string;
  error: string | null;
  micAvailable: boolean | null;
  recognitionAvailable: boolean;
  dbfs: number;
  thresholdDb: number;
  voiced: boolean;
}

// ---- minimal Web Speech API typings (not in lib.dom for TS 5.6)
interface SRAlternative {
  transcript: string;
}
interface SRResult {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: SRAlternative;
}
interface SRResultList {
  readonly length: number;
  [index: number]: SRResult;
}
interface SREvent {
  resultIndex: number;
  results: SRResultList;
}
interface SRErrorEvent {
  error: string;
}
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: SRErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SRCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SRCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function countWords(text: string): number {
  const m = text.trim().match(/[A-Za-z0-9À-ɏ']+/g);
  return m ? m.length : 0;
}

export function countHedges(text: string): number {
  const t = ` ${text.toLowerCase().replace(/[^a-z0-9'\s]/g, ' ').replace(/\s+/g, ' ')} `;
  let n = 0;
  for (const phrase of HEDGE_PHRASES) {
    const re = new RegExp(`(?<=\\s)${phrase.replace(/\s+/g, '\\s+')}(?=\\s)`, 'g');
    const m = t.match(re);
    if (m) n += m.length;
  }
  return n;
}

export function emptyMetrics(engine: TranscriptEngine = 'none'): ProsodyMetrics {
  return {
    initial_latency_ms: 0,
    total_silence_ms: 0,
    hesitation_count: 0,
    hedge_count: 0,
    wpm: 0,
    hedge_density: 0,
    engine,
  };
}

type Listener<T> = (v: T) => void;

export class ProsodyAudioEngine {
  // audio graph
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private timeBuf: Float32Array | null = null;
  private freqBuf: Uint8Array | null = null;
  private raf: number | null = null;
  private lastFrameAt = 0;
  // transcript engines
  private dictationWs: WebSocket | null = null;
  private recorder: MediaRecorder | null = null;
  private recognition: SpeechRecognitionLike | null = null;
  private wantRecognition = false;
  /** Server hint from GET /api/settings (deepgram_available). null = unknown -> probe the relay. */
  deepgramHint: boolean | null = null;
  /** Which engine answered on /ws/dictation (`ready` frame); Deepgram unless the server says otherwise. */
  private relayEngine: TranscriptEngine = 'deepgram';

  // measurement window (reset per step)
  private recordingStartedAt = 0;
  private firstVoiceAt: number | null = null;
  private initialLatencyMs = 0;
  private silenceRunMs = 0;
  private inSpeech = false;
  private hesitations = 0;
  private totalSilenceMs = 0;
  private recordingMs = 0;
  private noiseFloorDb = -60;
  private thresholdDb = -46;
  private dbfs = -100;
  private voiced = false;
  private finalText = '';
  private interimText = '';
  private engine: TranscriptEngine = 'none';
  private levels: number[] = new Array(BAR_COUNT).fill(0);

  private recording = false;
  private starting = false;
  /** Bumped by stop(); an in-flight start() that sees a different token aborts (push-to-talk released while arming). */
  private startToken = 0;
  private error: string | null = null;
  private micAvailable: boolean | null = null;

  private stateListeners = new Set<Listener<VoiceState>>();
  private levelListeners = new Set<Listener<number[]>>();
  private finalListeners = new Set<Listener<string>>();
  private lastStateEmit = 0;

  // ---------------------------------------------------------------- subscriptions
  onState(fn: Listener<VoiceState>): () => void {
    this.stateListeners.add(fn);
    fn(this.snapshot());
    return () => this.stateListeners.delete(fn);
  }
  onLevels(fn: Listener<number[]>): () => void {
    this.levelListeners.add(fn);
    return () => this.levelListeners.delete(fn);
  }
  /** Fired once per finalised transcript segment (used to append dictation into the focused field). */
  onFinalTranscript(fn: Listener<string>): () => void {
    this.finalListeners.add(fn);
    return () => this.finalListeners.delete(fn);
  }

  get isRecording(): boolean {
    return this.recording;
  }

  snapshot(): VoiceState {
    return {
      recording: this.recording,
      starting: this.starting,
      engine: this.engine,
      metrics: this.getMetrics(),
      interim: this.interimText,
      transcript: this.finalText,
      error: this.error,
      micAvailable: this.micAvailable,
      recognitionAvailable: getRecognitionCtor() !== null,
      dbfs: this.dbfs,
      thresholdDb: this.thresholdDb,
      voiced: this.voiced,
    };
  }

  private emitState(force = false): void {
    const now = performance.now();
    if (!force && now - this.lastStateEmit < 120) return; // ~8 Hz for metric text, 60 Hz for bars
    this.lastStateEmit = now;
    const s = this.snapshot();
    this.stateListeners.forEach((fn) => fn(s));
  }

  // ---------------------------------------------------------------- metrics
  getMetrics(): ProsodyMetrics {
    const text = `${this.finalText} ${this.interimText}`.trim();
    const words = countWords(text);
    const hedges = countHedges(text);
    const liveMs = this.recording ? performance.now() - this.recordingStartedAt : 0;
    const totalMs = this.recordingMs + liveMs;
    const speakingSpanMs = Math.max(2000, totalMs - this.initialLatencyMs);
    const wpm = words > 0 ? words / (speakingSpanMs / 60000) : 0;
    return {
      initial_latency_ms: Math.round(this.initialLatencyMs),
      total_silence_ms: Math.round(this.totalSilenceMs),
      hesitation_count: this.hesitations,
      hedge_count: hedges,
      wpm: Math.round(wpm * 10) / 10,
      hedge_density: words > 0 ? Math.round((hedges / words) * 1000) / 1000 : 0,
      engine: this.engine,
    };
  }

  /** Start a fresh measurement window (called when a new step becomes active). */
  resetWindow(): void {
    this.firstVoiceAt = null;
    this.initialLatencyMs = 0;
    this.silenceRunMs = 0;
    this.inSpeech = false;
    this.hesitations = 0;
    this.totalSilenceMs = 0;
    this.recordingMs = 0;
    this.finalText = '';
    this.interimText = '';
    if (this.recording) this.recordingStartedAt = performance.now();
    if (!this.recording) this.engine = 'none';
    this.emitState(true);
  }

  // ---------------------------------------------------------------- lifecycle
  async toggle(): Promise<void> {
    if (this.recording || this.starting) this.stop();
    else await this.start();
  }

  async start(): Promise<void> {
    if (this.recording || this.starting) return;
    this.starting = true;
    this.error = null;
    const token = ++this.startToken;
    const aborted = (): boolean => {
      if (token === this.startToken) return false;
      this.wantRecognition = false;
      try {
        this.recognition?.abort();
      } catch {
        /* ignore */
      }
      if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop();
      this.recorder = null;
      this.dictationWs?.close();
      this.dictationWs = null;
      this.teardownAudio();
      return true;
    };
    this.emitState(true);

    // 1. microphone + analyser
    const hasGUM = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
    if (hasGUM) {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        this.micAvailable = true;
      } catch (e) {
        this.stream = null;
        this.micAvailable = false;
        this.error = `Microphone unavailable (${e instanceof Error ? e.name || e.message : 'denied'}); prosody meter disabled.`;
      }
    } else {
      this.micAvailable = false;
      this.error = 'This browser exposes no getUserMedia (insecure origin?); prosody meter disabled.';
    }

    if (aborted()) return;
    if (this.stream) {
      try {
        const Ctor =
          window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (!Ctor) throw new Error('no AudioContext');
        this.ctx = new Ctor();
        if (this.ctx.state === 'suspended') await this.ctx.resume();
        this.analyser = this.ctx.createAnalyser();
        this.analyser.fftSize = 1024;
        this.analyser.smoothingTimeConstant = 0.55;
        this.source = this.ctx.createMediaStreamSource(this.stream);
        this.source.connect(this.analyser);
        this.timeBuf = new Float32Array(this.analyser.fftSize);
        this.freqBuf = new Uint8Array(this.analyser.frequencyBinCount);
      } catch (e) {
        this.error = `Web Audio unavailable (${e instanceof Error ? e.message : String(e)}).`;
        this.teardownAudio();
      }
    }

    // 2. transcript engine: server relay first (Deepgram, or on-device macOS speech inside Pólya.app),
    //    browser recognition as fallback
    let engine: TranscriptEngine = 'none';
    if (this.stream && this.deepgramHint !== false && typeof MediaRecorder !== 'undefined') {
      const ok = await this.tryDeepgram(this.stream);
      if (ok) engine = this.relayEngine;
    }
    if (aborted()) return;
    if (engine === 'none' && this.startRecognition()) engine = 'browser';

    if (!this.stream && engine === 'none') {
      this.starting = false;
      this.recording = false;
      this.error =
        this.error ?? 'No microphone and no SpeechRecognition in this browser: voice telemetry is unavailable.';
      if (!getRecognitionCtor()) this.error += ' (SpeechRecognition unsupported)';
      this.emitState(true);
      return;
    }
    if (engine === 'none' && this.stream && !getRecognitionCtor()) {
      this.error = 'No transcript engine (Deepgram unavailable, SpeechRecognition unsupported): measuring acoustics only.';
    }

    this.engine = engine;
    this.recording = true;
    this.starting = false;
    this.recordingStartedAt = performance.now();
    this.lastFrameAt = this.recordingStartedAt;
    this.inSpeech = this.firstVoiceAt !== null; // resumed windows keep their speech onset
    this.silenceRunMs = 0;
    this.noiseFloorDb = -60;
    if (this.analyser) this.raf = requestAnimationFrame(this.frame);
    this.emitState(true);
  }

  stop(): void {
    if (!this.recording && !this.starting) return;
    this.startToken += 1;
    if (this.recording) this.recordingMs += performance.now() - this.recordingStartedAt;
    this.recording = false;
    this.starting = false;
    if (this.raf !== null) cancelAnimationFrame(this.raf);
    this.raf = null;
    // recognition
    this.wantRecognition = false;
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch {
        /* already stopped */
      }
    }
    // deepgram: stop recorder, keep socket briefly so trailing finals arrive
    if (this.recorder && this.recorder.state !== 'inactive') {
      try {
        this.recorder.stop();
      } catch {
        /* ignore */
      }
    }
    this.recorder = null;
    const ws = this.dictationWs;
    this.dictationWs = null;
    if (ws) window.setTimeout(() => ws.close(), 900);
    // promote any interim text so it is not lost
    if (this.interimText.trim()) {
      this.commitFinal(this.interimText);
      this.interimText = '';
    }
    this.teardownAudio();
    this.levels = new Array(BAR_COUNT).fill(0);
    this.levelListeners.forEach((fn) => fn(this.levels));
    this.voiced = false;
    this.emitState(true);
  }

  private teardownAudio(): void {
    try {
      this.source?.disconnect();
    } catch {
      /* ignore */
    }
    this.source = null;
    this.analyser = null;
    if (this.ctx) void this.ctx.close().catch(() => undefined);
    this.ctx = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }

  // ---------------------------------------------------------------- 60 Hz acoustic loop
  private frame = (): void => {
    if (!this.recording || !this.analyser || !this.timeBuf || !this.freqBuf) return;
    const now = performance.now();
    const dt = Math.min(FRAME_CAP_MS, Math.max(0, now - this.lastFrameAt));
    this.lastFrameAt = now;

    this.analyser.getFloatTimeDomainData(this.timeBuf);
    let sum = 0;
    for (let i = 0; i < this.timeBuf.length; i++) sum += this.timeBuf[i] * this.timeBuf[i];
    const rms = Math.sqrt(sum / this.timeBuf.length);
    const db = 20 * Math.log10(Math.max(rms, 1e-8));
    this.dbfs = db;

    // adaptive noise floor (only learns from quiet frames)
    if (db < this.thresholdDb) this.noiseFloorDb = this.noiseFloorDb * 0.97 + db * 0.03;
    this.thresholdDb = Math.min(-34, Math.max(-58, this.noiseFloorDb + 10));
    const voiced = db > this.thresholdDb;
    this.voiced = voiced;

    if (voiced) {
      if (this.firstVoiceAt === null) {
        this.firstVoiceAt = now;
        this.initialLatencyMs = now - this.recordingStartedAt;
      }
      if (this.inSpeech && this.silenceRunMs >= HESITATION_MS) this.hesitations += 1;
      this.inSpeech = true;
      this.silenceRunMs = 0;
    } else {
      this.totalSilenceMs += dt;
      if (this.inSpeech) this.silenceRunMs += dt;
    }

    // 12 log-spaced bands from ~80 Hz to ~6 kHz
    this.analyser.getByteFrequencyData(this.freqBuf);
    const nyquist = (this.ctx?.sampleRate ?? 48000) / 2;
    const bins = this.freqBuf.length;
    const lo = 80;
    const hi = Math.min(6000, nyquist);
    const next: number[] = [];
    for (let b = 0; b < BAR_COUNT; b++) {
      const f0 = lo * Math.pow(hi / lo, b / BAR_COUNT);
      const f1 = lo * Math.pow(hi / lo, (b + 1) / BAR_COUNT);
      const i0 = Math.max(0, Math.floor((f0 / nyquist) * bins));
      const i1 = Math.min(bins - 1, Math.max(i0 + 1, Math.ceil((f1 / nyquist) * bins)));
      let acc = 0;
      for (let i = i0; i < i1; i++) acc += this.freqBuf[i];
      const v = acc / Math.max(1, i1 - i0) / 255;
      next.push(this.levels[b] * 0.45 + v * 0.55);
    }
    this.levels = next;
    this.levelListeners.forEach((fn) => fn(next));
    this.emitState();
    this.raf = requestAnimationFrame(this.frame);
  };

  // ---------------------------------------------------------------- transcript engines
  private commitFinal(text: string): void {
    const t = text.trim();
    if (!t) return;
    this.finalText = `${this.finalText} ${t}`.trim();
    this.finalListeners.forEach((fn) => fn(t));
  }

  private tryDeepgram(stream: MediaStream): Promise<boolean> {
    return new Promise((resolve) => {
      let settled = false;
      const done = (ok: boolean): void => {
        if (settled) return;
        settled = true;
        resolve(ok);
      };
      let ws: WebSocket;
      try {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${proto}://${location.host}/ws/dictation`);
      } catch {
        done(false);
        return;
      }
      ws.binaryType = 'arraybuffer';
      const openTimer = window.setTimeout(() => {
        try {
          ws.close();
        } catch {
          /* ignore */
        }
        done(false);
      }, 2500);
      let graceTimer = 0;

      ws.onmessage = (ev: MessageEvent) => {
        if (typeof ev.data !== 'string') return;
        let msg: DictationMessage;
        try {
          msg = JSON.parse(ev.data) as DictationMessage;
        } catch {
          return;
        }
        if (msg.type === 'unavailable') {
          window.clearTimeout(openTimer);
          window.clearTimeout(graceTimer);
          this.deepgramHint = false;
          try {
            ws.close();
          } catch {
            /* ignore */
          }
          done(false);
          return;
        }
        if (msg.type === 'ready') {
          // server-side engine: Deepgram relay or on-device macOS speech (Pólya.app)
          this.relayEngine = msg.engine;
          if (settled && this.dictationWs === ws) {
            this.engine = msg.engine;
            this.emitState(true);
          }
          return;
        }
        if (msg.type === 'transcript') {
          if (msg.is_final) {
            this.commitFinal(msg.text);
            this.interimText = '';
          } else {
            this.interimText = msg.text;
          }
          this.emitState(true);
        }
      };
      ws.onerror = () => {
        window.clearTimeout(openTimer);
        window.clearTimeout(graceTimer);
        done(false);
      };
      ws.onclose = () => {
        window.clearTimeout(openTimer);
        window.clearTimeout(graceTimer);
        if (!settled) done(false);
        else if (this.dictationWs === ws && this.recording) {
          // relay dropped mid-utterance -> fall back to the browser engine
          this.dictationWs = null;
          this.recorder?.stop();
          this.recorder = null;
          if (this.startRecognition()) this.engine = 'browser';
          else this.engine = 'none';
          this.emitState(true);
        }
      };
      ws.onopen = () => {
        window.clearTimeout(openTimer);
        // grace period for the server to say `unavailable`
        graceTimer = window.setTimeout(() => {
          if (settled) return;
          try {
            const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
              ? 'audio/webm;codecs=opus'
              : MediaRecorder.isTypeSupported('audio/webm')
                ? 'audio/webm'
                : '';
            const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
            rec.ondataavailable = (e: BlobEvent) => {
              if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(e.data);
            };
            rec.start(250);
            this.recorder = rec;
            this.dictationWs = ws;
            this.deepgramHint = true;
            done(true);
          } catch {
            try {
              ws.close();
            } catch {
              /* ignore */
            }
            done(false);
          }
        }, 650);
      };
    });
  }

  private startRecognition(): boolean {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return false;
    try {
      const rec = new Ctor();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = navigator.language || 'en-US';
      rec.onresult = (e: SREvent) => {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          const text = r[0]?.transcript ?? '';
          if (r.isFinal) this.commitFinal(text);
          else interim += text;
        }
        this.interimText = interim;
        this.emitState(true);
      };
      rec.onerror = (e: SRErrorEvent) => {
        if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
          this.wantRecognition = false;
          this.error = 'Speech recognition permission denied; acoustic prosody still recording.';
          if (!this.stream) this.stop();
        } else if (e.error === 'network') {
          this.error = 'Speech recognition network error (browser engine needs connectivity).';
        }
        this.emitState(true);
      };
      rec.onend = () => {
        // Chrome ends continuous recognition after long silences; keep it alive while recording.
        if (this.wantRecognition && this.recording) {
          try {
            rec.start();
          } catch {
            /* already started */
          }
        }
      };
      rec.start();
      this.recognition = rec;
      this.wantRecognition = true;
      return true;
    } catch {
      return false;
    }
  }
}

/** App-wide singleton (one microphone, one analyser). */
export const prosodyEngine = new ProsodyAudioEngine();
