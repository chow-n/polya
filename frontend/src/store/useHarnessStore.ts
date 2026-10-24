/**
 * Central state + REST client + WebSocket event dispatcher (ARCHITECTURE_SPEC §1, docs/API.md).
 *
 * The store owns:
 *  - the /ws hub socket (auto-reconnect with exponential backoff, 15 s ping, resync on reconnect)
 *  - every REST call in the contract (exported as `api`)
 *  - the per-step telemetry drafts (raw prediction, reading notes, dock text, confidence, flagged proof step…)
 *  - the voice/prosody engine wiring (final transcript segments are appended to the focused field)
 */
import { create } from 'zustand';
import { prosodyEngine, BAR_COUNT, type VoiceState } from '../utils/prosodyAudioEngine';
import {
  ALL_AGENTS,
  type AgentName,
  type ArtifactOut,
  type ChunkEvaluation,
  type ChunkRequest,
  type CreateSessionRequest,
  type DemoTelemetry,
  type DemoTelemetryAck,
  type DueItem,
  type DuelReply,
  type DuelRequest,
  type DuelTurn,
  type GraphOut,
  type HealthOut,
  type HintOut,
  type HintRequest,
  type LadderRung,
  type NodeDetail,
  type PracticeQueueItem,
  type ReadingNote,
  type ScratchOut,
  type SessionOut,
  type SessionState,
  type SettingsOut,
  type SettingsUpdate,
  type StatsOut,
  type StepPayload,
  type StepResult,
  type StepSubmission,
  type SubagentRunRequest,
  type SubagentStatus,
  type WorkspaceFile,
  type WorkspaceFileContent,
  type WsClientMessage,
  type WsEvent,
  type WsPayloads,
} from '../types/harness';

// =================================================================== REST client
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, `Backend unreachable (${e instanceof Error ? e.message : String(e)})`);
  }
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    if (data && typeof data === 'object' && 'detail' in data) {
      const d = (data as { detail: unknown }).detail;
      detail = typeof d === 'string' ? d : JSON.stringify(d);
    } else if (typeof data === 'string' && data) detail = data.slice(0, 300);
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

const q = (params: Record<string, string | number | null | undefined>): string => {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') sp.set(k, String(v));
  const s = sp.toString();
  return s ? `?${s}` : '';
};

export const api = {
  health: () => request<HealthOut>('GET', '/api/health'),
  graph: () => request<GraphOut>('GET', '/api/graph'),
  node: (id: string) => request<NodeDetail>('GET', `/api/nodes/${encodeURIComponent(id)}`),
  stats: () => request<StatsOut>('GET', '/api/stats'),
  due: () => request<DueItem[]>('GET', '/api/due'),
  practiceQueue: (limit = 12) => request<PracticeQueueItem[]>('GET', `/api/practice/queue${q({ limit })}`),
  sessions: () => request<SessionOut[]>('GET', '/api/sessions'),
  createSession: (body: CreateSessionRequest) => request<SessionState>('POST', '/api/sessions', body),
  session: (id: string) => request<SessionState>('GET', `/api/sessions/${encodeURIComponent(id)}`),
  submit: (id: string, body: StepSubmission) =>
    request<StepResult>('POST', `/api/sessions/${encodeURIComponent(id)}/submit`, body),
  advance: (id: string) => request<SessionState>('POST', `/api/sessions/${encodeURIComponent(id)}/advance`),
  hint: (id: string, body: HintRequest) => request<HintOut>('POST', `/api/sessions/${encodeURIComponent(id)}/hint`, body),
  chunk: (id: string, body: ChunkRequest) =>
    request<ChunkEvaluation>('POST', `/api/sessions/${encodeURIComponent(id)}/chunk`, body),
  duel: (id: string, body: DuelRequest) => request<DuelReply>('POST', `/api/sessions/${encodeURIComponent(id)}/duel`, body),
  artifacts: (params: { session_id?: string | null; agent_name?: AgentName | null; limit?: number } = {}) =>
    request<ArtifactOut[]>('GET', `/api/artifacts${q(params)}`),
  artifact: (id: string) => request<ArtifactOut>('GET', `/api/artifacts/${encodeURIComponent(id)}`),
  runSubagent: (agent: AgentName, body: SubagentRunRequest) =>
    request<ArtifactOut>('POST', `/api/subagents/${agent}/run`, body),
  workspaceFiles: () => request<WorkspaceFile[]>('GET', '/api/workspace/files'),
  workspaceFile: (path: string) => request<WorkspaceFileContent>('GET', `/api/workspace/file${q({ path })}`),
  scratch: () => request<ScratchOut>('GET', '/api/scratch'),
  writeScratch: (content: string) => request<ScratchOut>('PUT', '/api/scratch', { content }),
  demoTelemetry: (body: DemoTelemetry) => request<DemoTelemetryAck>('POST', '/api/demo-telemetry', body),
  settings: () => request<SettingsOut>('GET', '/api/settings'),
  updateSettings: (body: SettingsUpdate) => request<SettingsOut>('PUT', '/api/settings', body),
};

// =================================================================== state types
/** 1 Learn · 2 Review · 3 Map */
export type TabId = 1 | 2 | 3;
export type MicTarget = 'dock' | 'raw' | 'reading';
export type ColorMode = 'domain' | 'mastery' | 'fsrs' | 'hypercorrection';
export type WsStatus = 'connecting' | 'open' | 'closed';

export type ModalState =
  | { kind: 'artifact'; id: string }
  | { kind: 'scratch' }
  | { kind: 'settings' }
  | { kind: 'dispatch'; agent: AgentName }
  | null;

export interface Toast {
  id: number;
  kind: 'info' | 'error' | 'success';
  text: string;
}

export interface Drafts {
  stepId: string | null;
  stepShownAt: number; // epoch ms when this step became active
  rawPrediction: string;
  rawLockedAtMs: number | null; // epoch ms of "Lock In Raw Prediction"
  selectedOption: string;
  text: string; // dock textarea: verification thinking / chunk / duel message / referee explanation
  confidence: number;
  readingNotes: ReadingNote[];
  readingStream: string;
  flaggedStepIndex: number | null;
  counterexample: string;
}

export interface LauncherPreset {
  mode?: CreateSessionRequest['mode'];
  sub_mode?: CreateSessionRequest['sub_mode'];
  attached_files?: string[];
  target_node_id?: string | null;
  target_goal?: string;
  nonce: number;
}

export interface LastResult {
  sessionId: string;
  result: StepResult;
}

/** The step the learner just answered, kept on screen with its inline result until they press Continue. */
export interface HeldResult {
  sessionId: string;
  step: StepPayload;
  draft: Drafts;
  chunks: ChunkEvaluation[];
  result: StepResult;
}

type BusyKey = 'create' | 'submit' | 'advance' | 'hint' | 'chunk' | 'duel' | 'session' | 'settings' | 'scratch' | 'dispatch';

const blankDrafts = (stepId: string | null): Drafts => ({
  stepId,
  stepShownAt: Date.now(),
  rawPrediction: '',
  rawLockedAtMs: null,
  selectedOption: '',
  text: '',
  confidence: 0.5,
  readingNotes: [],
  readingStream: '',
  flaggedStepIndex: null,
  counterexample: '',
});

const idleAgents = (): Record<AgentName, SubagentStatus> =>
  Object.fromEntries(
    ALL_AGENTS.map((a) => [a, { agent_name: a, state: 'IDLE', message: 'idle', artifact_id: null, session_id: null }]),
  ) as Record<AgentName, SubagentStatus>;

const LS_SESSION = 'polya.activeSession';
const LS_UI = 'polya.ui';

function lsGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function lsSet(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: per-viewer convenience only */
  }
}

interface UiPrefs {
  tab: TabId;
  colorMode: ColorMode;
  depthLock: boolean;
  scratchLiveSync: boolean;
}
const uiPrefs: UiPrefs = (() => {
  const d: UiPrefs = { tab: 1, colorMode: 'domain', depthLock: true, scratchLiveSync: false };
  const raw = lsGet(LS_UI);
  if (!raw) return d;
  try {
    const p = { ...d, ...(JSON.parse(raw) as Partial<UiPrefs>) };
    if (p.tab !== 1 && p.tab !== 2 && p.tab !== 3) p.tab = 1;
    return p;
  } catch {
    return d;
  }
})();

export interface HarnessState {
  // connection
  wsStatus: WsStatus;
  wsLatencyMs: number | null;
  backendOk: boolean | null;
  llmEngine: string;
  // data
  graph: GraphOut | null;
  stats: StatsOut | null;
  due: DueItem[];
  practiceQueue: PracticeQueueItem[];
  sessions: SessionOut[];
  artifacts: ArtifactOut[];
  artifactCache: Record<string, ArtifactOut>;
  subagents: Record<AgentName, SubagentStatus>;
  scratch: ScratchOut | null;
  scratchEventAt: number | null;
  scratchLiveSync: boolean;
  workspaceFiles: WorkspaceFile[];
  openFile: WorkspaceFileContent | null;
  settings: SettingsOut | null;
  nodeDetails: Record<string, NodeDetail>;
  // session
  activeSessionId: string | null;
  sessionState: SessionState | null;
  lastResult: LastResult | null;
  /** Focus view (one step card at a time) is open. */
  focusOpen: boolean;
  /** Goal text of a session being created (shown in the skeleton while the engine prepares it). */
  creatingGoal: string | null;
  held: HeldResult | null;
  chunkLog: { stepId: string; items: ChunkEvaluation[] };
  duelLog: { stepId: string; turns: DuelTurn[]; reply: DuelReply | null };
  busy: Partial<Record<BusyKey, boolean>>;
  // ui
  tab: TabId;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  colorMode: ColorMode;
  depthLock: boolean;
  modal: ModalState;
  launcherPreset: LauncherPreset | null;
  toasts: Toast[];
  // telemetry drafts + voice
  draft: Drafts;
  micTarget: MicTarget;
  voice: VoiceState;
  voiceLevels: number[];

  // ---- actions
  init: () => void;
  setTab: (t: TabId) => void;
  toast: (kind: Toast['kind'], text: string) => void;
  dismissToast: (id: number) => void;
  openModal: (m: ModalState) => void;
  setColorMode: (m: ColorMode) => void;
  setDepthLock: (v: boolean) => void;
  selectNode: (id: string | null) => void;
  selectEdge: (id: string | null) => void;
  focusNodeInGraph: (id: string) => void;
  setLauncherPreset: (p: Omit<LauncherPreset, 'nonce'>) => void;

  refreshGraph: () => Promise<void>;
  refreshStats: () => Promise<void>;
  refreshDue: () => Promise<void>;
  refreshQueue: () => Promise<void>;
  refreshSessions: () => Promise<void>;
  refreshArtifacts: () => Promise<void>;
  refreshFiles: () => Promise<void>;
  refreshScratch: () => Promise<void>;
  refreshSettings: () => Promise<void>;
  fetchNodeDetail: (id: string) => Promise<NodeDetail | null>;
  fetchArtifact: (id: string) => Promise<ArtifactOut | null>;
  openWorkspaceFile: (path: string) => Promise<void>;

  loadSession: (id: string, open?: boolean) => Promise<void>;
  clearSession: () => void;
  exitFocus: () => void;
  continueFromResult: () => void;
  createSession: (req: CreateSessionRequest) => Promise<SessionState | null>;
  submitStep: (overrides?: Partial<StepSubmission>) => Promise<StepResult | null>;
  advanceStep: () => Promise<void>;
  requestHint: (rung: LadderRung) => Promise<HintOut | null>;
  submitChunk: () => Promise<ChunkEvaluation | null>;
  sendDuel: () => Promise<DuelReply | null>;
  runSubagent: (agent: AgentName, req: SubagentRunRequest) => Promise<ArtifactOut | null>;
  writeScratch: (content: string) => Promise<void>;
  pushScratchWs: (content: string) => void;
  setScratchLiveSync: (v: boolean) => void;
  postDemoTelemetry: (t: DemoTelemetry) => Promise<DemoTelemetryAck | null>;
  updateSettings: (u: SettingsUpdate) => Promise<SettingsOut | null>;

  setDraft: (patch: Partial<Drafts>) => void;
  lockRawPrediction: () => boolean;
  addReadingNote: (note: Omit<ReadingNote, 'timestamp_ms'>) => void;
  removeReadingNote: (index: number) => void;
  setMicTarget: (t: MicTarget) => void;
  toggleMic: () => Promise<void>;
}

// =================================================================== WebSocket plumbing (module scope)
let socket: WebSocket | null = null;
let retry = 0;
let pingTimer: number | null = null;
let reconnectTimer: number | null = null;
let pingSentAt = 0;
let initialised = false;
let toastSeq = 1;
let refreshTimer: number | null = null;
type RefreshKey = 'graph' | 'stats' | 'due' | 'queue' | 'sessions' | 'session' | 'files' | 'node' | 'artifacts';
const pendingRefresh = new Set<RefreshKey>();

export function sendWs(msg: WsClientMessage): boolean {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(msg));
    return true;
  }
  return false;
}

// =================================================================== store
export const useHarnessStore = create<HarnessState>()((set, get) => {
  const persistUi = (): void => {
    const s = get();
    lsSet(LS_UI, JSON.stringify({ tab: s.tab, colorMode: s.colorMode, depthLock: s.depthLock, scratchLiveSync: s.scratchLiveSync }));
  };

  const setBusy = (k: BusyKey, v: boolean): void => set((s) => ({ busy: { ...s.busy, [k]: v } }));

  /** Run an API call; maps failures to a toast (or the offline banner for status 0). */
  async function guard<T>(fn: () => Promise<T>, label: string, busyKey?: BusyKey): Promise<T | null> {
    if (busyKey) setBusy(busyKey, true);
    try {
      const out = await fn();
      if (get().backendOk !== true) set({ backendOk: true });
      return out;
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) {
        set({ backendOk: false });
      } else {
        get().toast('error', `${label}: ${e instanceof Error ? e.message : String(e)}`);
      }
      return null;
    } finally {
      if (busyKey) setBusy(busyKey, false);
    }
  }

  /** Apply a SessionState; reset drafts + prosody window when the active step changes. */
  const applySession = (state: SessionState): void => {
    const s = get();
    const stepId = state.active_step.step_id;
    const patch: Partial<HarnessState> = { sessionState: state, activeSessionId: state.session.id };
    if (s.draft.stepId !== stepId) {
      const keepLive = s.scratchLiveSync && s.scratch ? s.scratch.content : '';
      patch.draft = { ...blankDrafts(stepId), text: keepLive };
      patch.chunkLog = { stepId, items: [] };
      patch.duelLog = { stepId, turns: [], reply: null };
      prosodyEngine.resetWindow();
    }
    set(patch);
    lsSet(LS_SESSION, state.session.id);
  };

  const scheduleRefresh = (...keys: RefreshKey[]): void => {
    keys.forEach((k) => pendingRefresh.add(k));
    if (refreshTimer !== null) return;
    refreshTimer = window.setTimeout(() => {
      refreshTimer = null;
      const ks = new Set(pendingRefresh);
      pendingRefresh.clear();
      const s = get();
      if (ks.has('graph')) void s.refreshGraph();
      if (ks.has('stats')) void s.refreshStats();
      if (ks.has('due')) void s.refreshDue();
      if (ks.has('queue')) void s.refreshQueue();
      if (ks.has('sessions')) void s.refreshSessions();
      if (ks.has('files')) void s.refreshFiles();
      if (ks.has('artifacts')) void s.refreshArtifacts();
      if (ks.has('session') && s.activeSessionId) {
        void guard(() => api.session(s.activeSessionId as string), 'Refresh session').then((st) => {
          if (st && st.session.id === get().activeSessionId) applySession(st);
        });
      }
      if (ks.has('node') && s.selectedNodeId) void s.fetchNodeDetail(s.selectedNodeId);
    }, 140);
  };

  const dispatch = (ev: WsEvent): void => {
    const s = get();
    switch (ev.type) {
      case 'hello': {
        const p = ev.payload as unknown as WsPayloads['hello'];
        set({ llmEngine: p.llm_engine ?? s.llmEngine, backendOk: true });
        break;
      }
      case 'subagent_status': {
        const p = ev.payload as unknown as WsPayloads['subagent_status'];
        if (!p.agent_name) break;
        set((st) => ({ subagents: { ...st.subagents, [p.agent_name]: { ...p } } }));
        if ((p.state === 'COMPLETED' || p.state === 'FAILED') && p.artifact_id && !s.artifactCache[p.artifact_id]) {
          void s.fetchArtifact(p.artifact_id);
        }
        break;
      }
      case 'artifact': {
        const a = ev.payload as unknown as WsPayloads['artifact'];
        if (!a.id) break;
        set((st) => ({
          artifacts: [a, ...st.artifacts.filter((x) => x.id !== a.id)].slice(0, 200),
          artifactCache: { ...st.artifactCache, [a.id]: a },
        }));
        break;
      }
      case 'scratch_update': {
        const p = ev.payload as unknown as WsPayloads['scratch_update'];
        set({ scratch: p, scratchEventAt: Date.now() });
        if (get().scratchLiveSync) get().setDraft({ text: p.content });
        break;
      }
      case 'graph_updated':
        scheduleRefresh('graph', 'stats', 'due', 'queue', 'node');
        break;
      case 'session_updated': {
        const p = ev.payload as unknown as WsPayloads['session_updated'];
        scheduleRefresh('sessions');
        if (p.session_id && p.session_id === s.activeSessionId) scheduleRefresh('session');
        break;
      }
      case 'stats':
        set({ stats: ev.payload as unknown as StatsOut });
        break;
      case 'notes_changed': {
        const p = ev.payload as unknown as WsPayloads['notes_changed'];
        scheduleRefresh('files');
        if (s.openFile && p.path && (p.path === s.openFile.path || p.path.endsWith(s.openFile.path))) {
          void s.openWorkspaceFile(s.openFile.path);
        }
        break;
      }
      case 'pong':
        if (pingSentAt) set({ wsLatencyMs: Math.round(performance.now() - pingSentAt) });
        break;
      case 'error': {
        const p = ev.payload as unknown as WsPayloads['error'];
        s.toast('error', `Server: ${p.message ?? 'unknown error'}`);
        break;
      }
    }
  };

  const connect = (): void => {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    set({ wsStatus: 'connecting' });
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    let ws: WebSocket;
    try {
      ws = new WebSocket(`${proto}://${location.host}/ws`);
    } catch {
      set({ wsStatus: 'closed' });
      reconnectTimer = window.setTimeout(connect, Math.min(10000, 500 * 2 ** retry++));
      return;
    }
    socket = ws;
    ws.onopen = () => {
      const wasReconnect = retry > 0;
      retry = 0;
      set({ wsStatus: 'open', backendOk: true });
      if (pingTimer !== null) window.clearInterval(pingTimer);
      const ping = (): void => {
        pingSentAt = performance.now();
        sendWs({ type: 'ping' });
      };
      ping();
      pingTimer = window.setInterval(ping, 15000);
      // resync anything we may have missed while disconnected
      if (wasReconnect) scheduleRefresh('graph', 'stats', 'due', 'queue', 'sessions', 'session', 'files', 'artifacts');
    };
    ws.onmessage = (e: MessageEvent) => {
      if (typeof e.data !== 'string') return;
      try {
        const ev = JSON.parse(e.data) as WsEvent;
        if (ev && typeof ev.type === 'string') dispatch({ ...ev, payload: ev.payload ?? {} });
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onerror = () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => {
      if (socket === ws) socket = null;
      if (pingTimer !== null) window.clearInterval(pingTimer);
      pingTimer = null;
      set({ wsStatus: 'closed' });
      reconnectTimer = window.setTimeout(connect, Math.min(10000, 500 * 2 ** retry++));
    };
  };

  return {
    wsStatus: 'connecting',
    wsLatencyMs: null,
    backendOk: null,
    llmEngine: '…',
    graph: null,
    stats: null,
    due: [],
    practiceQueue: [],
    sessions: [],
    artifacts: [],
    artifactCache: {},
    subagents: idleAgents(),
    scratch: null,
    scratchEventAt: null,
    scratchLiveSync: uiPrefs.scratchLiveSync,
    workspaceFiles: [],
    openFile: null,
    settings: null,
    nodeDetails: {},
    activeSessionId: null,
    sessionState: null,
    lastResult: null,
    focusOpen: false,
    creatingGoal: null,
    held: null,
    chunkLog: { stepId: '', items: [] },
    duelLog: { stepId: '', turns: [], reply: null },
    busy: {},
    tab: uiPrefs.tab,
    selectedNodeId: null,
    selectedEdgeId: null,
    colorMode: uiPrefs.colorMode,
    depthLock: uiPrefs.depthLock,
    modal: null,
    launcherPreset: null,
    toasts: [],
    draft: blankDrafts(null),
    micTarget: 'dock',
    voice: prosodyEngine.snapshot(),
    voiceLevels: new Array(BAR_COUNT).fill(0),

    // ------------------------------------------------------------- lifecycle
    init: () => {
      if (initialised) return;
      initialised = true;
      prosodyEngine.onState((v) => set({ voice: v }));
      prosodyEngine.onLevels((lv) => set({ voiceLevels: lv }));
      prosodyEngine.onFinalTranscript((text) => {
        const s = get();
        const d = s.draft;
        const join = (a: string): string => (a && !/\s$/.test(a) ? `${a} ${text}` : `${a}${text}`);
        if (s.micTarget === 'raw' && d.rawLockedAtMs === null) s.setDraft({ rawPrediction: join(d.rawPrediction) });
        else if (s.micTarget === 'reading') s.setDraft({ readingStream: join(d.readingStream) });
        else s.setDraft({ text: join(d.text) });
      });
      connect();
      void guard(() => api.health(), 'Health').then((h) => {
        if (h) set({ llmEngine: h.llm_engine, backendOk: h.status === 'ok' });
      });
      const s = get();
      void s.refreshGraph();
      void s.refreshStats();
      void s.refreshSessions();
      void s.refreshArtifacts();
      void s.refreshFiles();
      void s.refreshScratch();
      void s.refreshSettings();
      void s.refreshDue();
      void s.refreshQueue();
      const last = lsGet(LS_SESSION);
      if (last) {
        void api
          .session(last)
          .then((st) => applySession(st))
          .catch(() => lsSet(LS_SESSION, null));
      }
    },

    setTab: (t) => {
      set({ tab: t, focusOpen: false });
      persistUi();
    },
    toast: (kind, text) => {
      const id = toastSeq++;
      set((s) => ({ toasts: [...s.toasts.slice(-4), { id, kind, text }] }));
      window.setTimeout(() => get().dismissToast(id), kind === 'error' ? 7000 : 4000);
    },
    dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
    openModal: (m) => set({ modal: m }),
    setColorMode: (m) => {
      set({ colorMode: m });
      persistUi();
    },
    setDepthLock: (v) => {
      set({ depthLock: v });
      persistUi();
    },
    selectNode: (id) => {
      set({ selectedNodeId: id, selectedEdgeId: null });
      if (id) void get().fetchNodeDetail(id);
    },
    selectEdge: (id) => set({ selectedEdgeId: id, selectedNodeId: null }),
    focusNodeInGraph: (id) => {
      get().selectNode(id);
      get().setTab(3);
    },
    setLauncherPreset: (p) => set({ launcherPreset: { ...p, nonce: Date.now() } }),

    // ------------------------------------------------------------- fetchers
    refreshGraph: async () => {
      const g = await guard(() => api.graph(), 'Load graph');
      if (g) set({ graph: g });
    },
    refreshStats: async () => {
      const st = await guard(() => api.stats(), 'Load stats');
      if (st) set({ stats: st, llmEngine: st.llm_engine || get().llmEngine });
    },
    refreshDue: async () => {
      const d = await guard(() => api.due(), 'Load due list');
      if (d) set({ due: d });
    },
    refreshQueue: async () => {
      const pq = await guard(() => api.practiceQueue(12), 'Load practice queue');
      if (pq) set({ practiceQueue: pq });
    },
    refreshSessions: async () => {
      const ss = await guard(() => api.sessions(), 'Load sessions');
      if (ss) set({ sessions: ss });
    },
    refreshArtifacts: async () => {
      const arts = await guard(() => api.artifacts({ limit: 120 }), 'Load artifacts');
      if (arts) {
        set((s) => {
          const cache = { ...s.artifactCache };
          arts.forEach((a) => (cache[a.id] = a));
          return { artifacts: arts, artifactCache: cache };
        });
      }
    },
    refreshFiles: async () => {
      const f = await guard(() => api.workspaceFiles(), 'Load workspace files');
      if (f) set({ workspaceFiles: f });
    },
    refreshScratch: async () => {
      const sc = await guard(() => api.scratch(), 'Load scratch.tex');
      if (sc) set({ scratch: sc });
    },
    refreshSettings: async () => {
      const st = await guard(() => api.settings(), 'Load settings');
      if (st) {
        set({ settings: st, llmEngine: st.active_engine || get().llmEngine });
        prosodyEngine.deepgramHint = st.deepgram_available || st.native_dictation_available;
      }
    },
    fetchNodeDetail: async (id) => {
      const d = await guard(() => api.node(id), 'Load node');
      if (d) set((s) => ({ nodeDetails: { ...s.nodeDetails, [id]: d } }));
      return d;
    },
    fetchArtifact: async (id) => {
      const cached = get().artifactCache[id];
      if (cached && cached.status !== 'RUNNING') return cached;
      const a = await guard(() => api.artifact(id), 'Load artifact');
      if (a) {
        set((s) => ({
          artifactCache: { ...s.artifactCache, [a.id]: a },
          artifacts: s.artifacts.some((x) => x.id === a.id)
            ? s.artifacts.map((x) => (x.id === a.id ? a : x))
            : [a, ...s.artifacts],
        }));
      }
      return a;
    },
    openWorkspaceFile: async (path) => {
      const f = await guard(() => api.workspaceFile(path), 'Open file');
      if (f) set({ openFile: f });
    },

    // ------------------------------------------------------------- sessions & steps
    loadSession: async (id, open = true) => {
      const st = await guard(() => api.session(id), 'Load session', 'session');
      if (st) {
        if (get().held?.sessionId !== st.session.id) set({ held: null });
        applySession(st);
        if (open) set({ focusOpen: true });
      }
    },
    clearSession: () => {
      set({ activeSessionId: null, sessionState: null, draft: blankDrafts(null), held: null, focusOpen: false });
      lsSet(LS_SESSION, null);
    },
    exitFocus: () => set({ focusOpen: false, held: null }),
    continueFromResult: () => set({ held: null }),
    createSession: async (req) => {
      const wasOpen = get().focusOpen;
      set({ focusOpen: true, creatingGoal: req.target_goal, held: null });
      const st = await guard(() => api.createSession(req), 'Create session', 'create');
      set({ creatingGoal: null });
      if (st) {
        applySession(st);
        set({ lastResult: null, focusOpen: true });
        scheduleRefresh('sessions');
      } else set({ focusOpen: wasOpen });
      return st;
    },
    submitStep: async (overrides) => {
      const s = get();
      const st = s.sessionState;
      if (!st) return null;
      const d = s.draft;
      const notes = [...d.readingNotes];
      if (d.readingStream.trim()) {
        notes.push({ quote: '', thought: d.readingStream.trim(), timestamp_ms: Date.now() - d.stepShownAt });
      }
      const body: StepSubmission = {
        step_id: st.active_step.step_id,
        raw_prediction_locked: d.rawLockedAtMs !== null || !st.active_step.options_locked ? d.rawPrediction.trim() : '',
        raw_prediction_locked_at_ms: d.rawLockedAtMs ?? 0,
        thinking_while_reading: notes,
        verification_thinking: d.text.trim(),
        selected_answer: d.selectedOption,
        confidence: d.confidence,
        prosody: prosodyEngine.getMetrics(),
        flagged_step_index: d.flaggedStepIndex,
        counterexample_text: d.counterexample.trim(),
        ...overrides,
      };
      const sid = st.session.id;
      const res = await guard(() => api.submit(sid, body), 'Submit step', 'submit');
      if (res) {
        // Keep the answered card on screen with its inline result (graded kinds, or when a counterexample was found).
        const kind = st.active_step.kind;
        const graded = kind !== 'PREDICT' && kind !== 'READING';
        const chunks = s.chunkLog.stepId === st.active_step.step_id ? s.chunkLog.items : [];
        const held: HeldResult | null =
          graded || res.created_nodes.length > 0 ? { sessionId: sid, step: st.active_step, draft: d, chunks, result: res } : null;
        set({ lastResult: { sessionId: sid, result: res }, held });
        applySession(res.state);
        scheduleRefresh('graph', 'stats', 'due', 'queue', 'sessions', 'node');
      }
      return res;
    },
    advanceStep: async () => {
      const st = get().sessionState;
      if (!st) return;
      const next = await guard(() => api.advance(st.session.id), 'Advance', 'advance');
      if (next) applySession(next);
    },
    requestHint: async (rung) => {
      const st = get().sessionState;
      if (!st) return null;
      const chunks = get().chunkLog.items.map((c) => c.text);
      const current = [...chunks, get().draft.text].filter(Boolean).join('\n');
      const h = await guard(() => api.hint(st.session.id, { rung, current_thinking: current }), 'Hint', 'hint');
      if (h) {
        set((s) => {
          if (!s.sessionState) return {};
          const step = s.sessionState.active_step;
          const hints = [...step.hints_unlocked.filter((x) => x.rung !== h.rung), h];
          return { sessionState: { ...s.sessionState, active_step: { ...step, hints_unlocked: hints } } };
        });
      }
      return h;
    },
    submitChunk: async () => {
      const s = get();
      const st = s.sessionState;
      const text = s.draft.text.trim();
      if (!st || !text) return null;
      const ev = await guard(() => api.chunk(st.session.id, { text, confidence: s.draft.confidence }), 'Submit chunk', 'chunk');
      if (ev) {
        set((x) => ({
          chunkLog: {
            stepId: st.active_step.step_id,
            items: [...x.chunkLog.items.filter((c) => c.chunk_index !== ev.chunk_index), ev],
          },
          draft: { ...x.draft, text: '' },
        }));
      }
      return ev;
    },
    sendDuel: async () => {
      const s = get();
      const st = s.sessionState;
      const message = s.draft.text.trim();
      if (!st || !message) return null;
      const t0 = Date.now() - s.draft.stepShownAt;
      set((x) => ({
        duelLog: {
          stepId: st.active_step.step_id,
          turns: [...x.duelLog.turns, { role: 'learner', text: message, timestamp_ms: t0 }],
          reply: x.duelLog.reply,
        },
        draft: { ...x.draft, text: '' },
      }));
      const r = await guard(() => api.duel(st.session.id, { message }), 'Feynman duel', 'duel');
      if (r) {
        set((x) => ({
          duelLog: {
            stepId: st.active_step.step_id,
            turns: [...x.duelLog.turns, { role: 'student', text: r.student_message, timestamp_ms: Date.now() - x.draft.stepShownAt }],
            reply: r,
          },
        }));
      } else {
        // restore the unsent message so nothing typed is lost
        set((x) => ({
          duelLog: { ...x.duelLog, turns: x.duelLog.turns.slice(0, -1) },
          draft: { ...x.draft, text: message },
        }));
      }
      return r;
    },
    runSubagent: async (agent, req) => {
      set((s) => ({
        subagents: { ...s.subagents, [agent]: { ...s.subagents[agent], state: 'RUNNING', message: 'dispatched…' } },
      }));
      const a = await guard(() => api.runSubagent(agent, req), `Run ${agent}`, 'dispatch');
      if (a) {
        set((s) => ({
          artifacts: [a, ...s.artifacts.filter((x) => x.id !== a.id)],
          artifactCache: { ...s.artifactCache, [a.id]: a },
          subagents: {
            ...s.subagents,
            [agent]: {
              ...s.subagents[agent],
              state: a.status === 'FAILED' ? 'FAILED' : a.status === 'RUNNING' ? 'RUNNING' : 'COMPLETED',
              message: a.title,
              artifact_id: a.id,
            },
          },
        }));
      } else {
        set((s) => ({ subagents: { ...s.subagents, [agent]: { ...s.subagents[agent], state: 'FAILED', message: 'dispatch failed' } } }));
      }
      return a;
    },
    writeScratch: async (content) => {
      const sc = await guard(() => api.writeScratch(content), 'Save scratch.tex', 'scratch');
      if (sc) {
        set({ scratch: sc, scratchEventAt: Date.now() });
        get().toast('success', `Saved ${sc.path}`);
      }
    },
    pushScratchWs: (content) => {
      if (!sendWs({ type: 'scratch_write', content })) void get().writeScratch(content);
      else get().toast('info', 'Pushed dock text to scratch.tex');
    },
    setScratchLiveSync: (v) => {
      set({ scratchLiveSync: v });
      persistUi();
      const sc = get().scratch;
      if (v && sc) get().setDraft({ text: sc.content });
    },
    postDemoTelemetry: async (t) => guard(() => api.demoTelemetry(t), 'Demo telemetry'),
    updateSettings: async (u) => {
      const st = await guard(() => api.updateSettings(u), 'Save settings', 'settings');
      if (st) {
        set({ settings: st, llmEngine: st.active_engine });
        prosodyEngine.deepgramHint = st.deepgram_available || st.native_dictation_available;
        get().toast('success', 'Settings saved');
        scheduleRefresh('stats');
      }
      return st;
    },

    // ------------------------------------------------------------- drafts & voice
    setDraft: (patch) => set((s) => ({ draft: { ...s.draft, ...patch } })),
    lockRawPrediction: () => {
      const d = get().draft;
      if (d.rawLockedAtMs !== null) return true;
      if (d.rawPrediction.trim().length < 15) {
        get().toast('info', 'Write a little more first: one sentence is enough.');
        return false;
      }
      get().setDraft({ rawLockedAtMs: Date.now() });
      if (get().micTarget === 'raw') set({ micTarget: 'dock' });
      return true;
    },
    addReadingNote: (note) =>
      set((s) => ({
        draft: {
          ...s.draft,
          readingNotes: [...s.draft.readingNotes, { ...note, timestamp_ms: Date.now() - s.draft.stepShownAt }],
        },
      })),
    removeReadingNote: (index) =>
      set((s) => ({ draft: { ...s.draft, readingNotes: s.draft.readingNotes.filter((_, i) => i !== index) } })),
    setMicTarget: (t) => set({ micTarget: t }),
    toggleMic: async () => {
      await prosodyEngine.toggle();
    },
  };
});

