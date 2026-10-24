/**
 * Frontend-only preferences (SPEC ui-simplify: theme override, Advanced telemetry, first-run explainer).
 * Stored in localStorage with a safe fallback when storage is unavailable (private window, WKWebView quirks).
 */
import { create } from 'zustand';

export type ThemePref = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

const K = {
  theme: 'polya.theme',
  advanced: 'polya.advanced',
  intro: 'polya.introDismissed',
};

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the preference lasts for this window only */
  }
}

const media = (): MediaQueryList | null => {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)');
  } catch {
    return null;
  }
};

function resolve(pref: ThemePref): ResolvedTheme {
  if (pref !== 'system') return pref;
  return media()?.matches ? 'dark' : 'light';
}

function apply(pref: ThemePref): void {
  const root = document.documentElement;
  if (pref === 'system') delete root.dataset.theme;
  else root.dataset.theme = pref;
}

interface Prefs {
  theme: ThemePref;
  resolved: ResolvedTheme;
  advanced: boolean;
  introDismissed: boolean;
  setTheme: (t: ThemePref) => void;
  setAdvanced: (v: boolean) => void;
  dismissIntro: () => void;
}

const initialTheme = ((): ThemePref => {
  const t = read(K.theme);
  return t === 'light' || t === 'dark' ? t : 'system';
})();

export const usePrefs = create<Prefs>()((set, get) => ({
  theme: initialTheme,
  resolved: resolve(initialTheme),
  advanced: read(K.advanced) === '1',
  introDismissed: read(K.intro) === '1',
  setTheme: (t) => {
    write(K.theme, t);
    apply(t);
    set({ theme: t, resolved: resolve(t) });
  },
  setAdvanced: (v) => {
    write(K.advanced, v ? '1' : '0');
    set({ advanced: v });
  },
  dismissIntro: () => {
    write(K.intro, '1');
    if (!get().introDismissed) set({ introDismissed: true });
  },
}));

/** Call once at startup: applies the stored override and follows the system appearance. */
export function initTheme(): void {
  apply(usePrefs.getState().theme);
  const mq = media();
  const onChange = (): void => usePrefs.setState((s) => ({ resolved: resolve(s.theme) }));
  try {
    mq?.addEventListener('change', onChange);
  } catch {
    /* very old WebKit: no live updates, the next launch picks the change up */
  }
}

// ------------------------------------------------------------------ canvas palette (read from CSS custom properties)
export interface CanvasPalette {
  bg: string;
  ink: string;
  ink2: string;
  rule: string;
  labelBg: string;
  nodeStroke: string;
  accent: string;
  hub: string;
  deduction: string;
  contrast: string;
  iso: string;
  cue: string;
  good: string;
  mid: string;
  bad: string;
  fresh: string;
  window: string;
  decay: string;
  topics: string[];
}

export function readCanvasPalette(): CanvasPalette {
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string, fb: string): string => cs.getPropertyValue(name).trim() || fb;
  return {
    bg: v('--map-bg', '#f6f7f9'),
    ink: v('--ink', '#1c2026'),
    ink2: v('--ink-2', '#545d69'),
    rule: v('--rule', '#e4e7eb'),
    labelBg: v('--map-label-bg', 'rgba(246,247,249,0.85)'),
    nodeStroke: v('--map-node-stroke', 'rgba(28,32,38,0.35)'),
    accent: v('--accent', '#2f45a0'),
    hub: v('--surface', '#ffffff'),
    deduction: v('--map-deduction', '#5b6bb5'),
    contrast: v('--map-contrast', '#b7802a'),
    iso: v('--map-iso', '#8a5fb8'),
    cue: v('--map-cue', '#2f8a9a'),
    good: v('--map-good', '#2d7a57'),
    mid: v('--map-mid', '#c2902c'),
    bad: v('--map-bad', '#b03a2e'),
    fresh: v('--map-fresh', '#2d7a57'),
    window: v('--map-window', '#c2902c'),
    decay: v('--map-decay', '#b03a2e'),
    topics: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => v(`--map-topic-${i}`, '#5b6bb5')),
  };
}

const KNOWN_TOPICS: Record<string, number> = {
  'Measure-Theoretic Probability': 0,
  'Transformers & Attention': 1,
  'Reinforcement Learning': 2,
  'Linear Algebra & Functional Analysis': 3,
};

/** Stable topic colour from the theme palette (index 7 is reserved for misconceptions). */
export function topicColor(pal: CanvasPalette, domain: string, isMisconception = false): string {
  if (isMisconception) return pal.topics[7];
  const known = KNOWN_TOPICS[domain];
  if (known !== undefined) return pal.topics[known];
  let h = 0;
  for (let i = 0; i < domain.length; i++) h = (h * 31 + domain.charCodeAt(i)) >>> 0;
  return pal.topics[4 + (h % 3)];
}
