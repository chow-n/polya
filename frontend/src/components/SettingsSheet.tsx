/**
 * Settings (⚙): appearance (System / Light / Dark), AI engine + API keys (PUT /api/settings), workspace (open and edit
 * scratch.tex via /api/scratch) and Advanced (the Advanced telemetry toggle that restores the legacy panels, plus
 * per-provider model overrides).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { usePrefs, type ThemePref } from '../store/prefs';
import { useHarnessStore } from '../store/useHarnessStore';
import { LLM_PROVIDERS, type LLMProvider, type SettingsUpdate } from '../types/harness';
import { Details, MOD_KEY, Spinner, useEscape } from './kit';

const PROVIDER_LABEL: Record<LLMProvider, string> = {
  auto: 'Automatic (best available)',
  anthropic: 'Anthropic API',
  gemini: 'Gemini API',
  openai: 'OpenAI API',
  openrouter: 'OpenRouter',
  claude_cli: 'Claude app on this Mac',
  deterministic: 'Offline (built in, no AI)',
};

const KEY_FIELDS: { field: keyof SettingsUpdate; label: string; presentKey: string }[] = [
  { field: 'anthropic_api_key', label: 'Anthropic', presentKey: 'anthropic' },
  { field: 'gemini_api_key', label: 'Gemini', presentKey: 'gemini' },
  { field: 'openai_api_key', label: 'OpenAI', presentKey: 'openai' },
  { field: 'openrouter_api_key', label: 'OpenRouter', presentKey: 'openrouter' },
  { field: 'deepgram_api_key', label: 'Deepgram (voice dictation)', presentKey: 'deepgram' },
];

function keyPresent(present: Record<string, boolean>, k: string): boolean {
  return Boolean(present[k] ?? present[`${k}_api_key`] ?? present[`${k.toUpperCase()}_API_KEY`]);
}

function ScratchEditor(): JSX.Element {
  const scratch = useHarnessStore((s) => s.scratch);
  const writeScratch = useHarnessStore((s) => s.writeScratch);
  const refreshScratch = useHarnessStore((s) => s.refreshScratch);
  const busy = useHarnessStore((s) => s.busy.scratch);
  const [content, setContent] = useState(scratch?.content ?? '');
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    void refreshScratch();
  }, [refreshScratch]);
  useEffect(() => {
    if (!dirty && scratch) setContent(scratch.content);
  }, [scratch, dirty]);
  const save = (): void => {
    void writeScratch(content).then(() => setDirty(false));
  };
  return (
    <div className="scratch-editor">
      <textarea
        aria-label="scratch.tex"
        spellCheck={false}
        value={content}
        onChange={(e) => {
          setContent(e.target.value);
          setDirty(true);
        }}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 's') {
            e.preventDefault();
            save();
          }
        }}
      />
      <div className="row">
        <span className="muted small">{dirty ? 'Unsaved changes' : 'Saved. Edits made in your editor appear here live.'}</span>
        <button className="btn-secondary" disabled={!dirty || busy} onClick={save}>
          {busy ? <Spinner /> : null}Save
        </button>
      </div>
    </div>
  );
}

export default function SettingsSheet({ onClose }: { onClose: () => void }): JSX.Element {
  const settings = useHarnessStore((s) => s.settings);
  const refreshSettings = useHarnessStore((s) => s.refreshSettings);
  const updateSettings = useHarnessStore((s) => s.updateSettings);
  const busy = useHarnessStore((s) => s.busy.settings);
  const scratch = useHarnessStore((s) => s.scratch);
  const files = useHarnessStore((s) => s.workspaceFiles);
  const theme = usePrefs((s) => s.theme);
  const setTheme = usePrefs((s) => s.setTheme);
  const advanced = usePrefs((s) => s.advanced);
  const setAdvanced = usePrefs((s) => s.setAdvanced);
  const [provider, setProvider] = useState<LLMProvider>(settings?.provider ?? 'auto');
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [overrides, setOverrides] = useState('');
  const [editScratch, setEditScratch] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEscape(onClose, true);
  useEffect(() => {
    void refreshSettings();
    panelRef.current?.focus();
  }, [refreshSettings]);
  useEffect(() => {
    if (!settings) return;
    setProvider(settings.provider);
    setOverrides(
      Object.entries(settings.model_overrides)
        .map(([k, v]) => `${k}=${v}`)
        .join('\n'),
    );
  }, [settings]);

  const parsedOverrides = useMemo(() => {
    const out: Record<string, string> = {};
    overrides
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      .forEach((l) => {
        const i = l.indexOf('=');
        if (i > 0) out[l.slice(0, i).trim()] = l.slice(i + 1).trim();
      });
    return out;
  }, [overrides]);

  const save = async (): Promise<void> => {
    const body: SettingsUpdate = { provider, model_overrides: parsedOverrides };
    for (const f of KEY_FIELDS) {
      const v = keys[f.field]?.trim();
      if (v) (body as Record<string, unknown>)[f.field] = v;
    }
    const res = await updateSettings(body);
    if (res) setKeys({});
  };

  const present = settings?.keys_present ?? {};
  const workspaceDir = scratch?.path ? scratch.path.replace(/\/?scratch\.tex$/, '') || 'workspace' : 'workspace';

  return (
    <div className="sheet-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="settings-h" tabIndex={-1} ref={panelRef}>
        <header className="sheet-head">
          <h2 id="settings-h">Settings</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close settings" title="Close (Esc)">
            ×
          </button>
        </header>

        <section className="sheet-sec" aria-labelledby="s-appearance">
          <h3 id="s-appearance">Appearance</h3>
          <div className="seg" role="radiogroup" aria-labelledby="s-appearance">
            {(['system', 'light', 'dark'] as ThemePref[]).map((t) => (
              <button key={t} role="radio" aria-checked={theme === t} className={`seg-opt${theme === t ? ' on' : ''}`} onClick={() => setTheme(t)}>
                {t === 'system' ? 'System' : t === 'light' ? 'Light' : 'Dark'}
              </button>
            ))}
          </div>
        </section>

        <section className="sheet-sec" aria-labelledby="s-engine">
          <h3 id="s-engine">AI engine</h3>
          <p className="muted small">
            Pólya writes questions and reads your answers with this engine. Now using: <b>{settings?.active_engine ?? '…'}</b>
          </p>
          <label className="plain-field">
            <span className="field-label">Engine</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value as LLMProvider)}>
              {LLM_PROVIDERS.map((p) => (
                <option key={p} value={p} disabled={p === 'claude_cli' && settings !== null && !settings.claude_cli_available}>
                  {PROVIDER_LABEL[p]}
                  {p === 'claude_cli' && settings && !settings.claude_cli_available ? ' (not found)' : ''}
                </option>
              ))}
            </select>
          </label>
          {KEY_FIELDS.filter((f) => f.presentKey === provider).map((f) => {
            const set = keyPresent(present, f.presentKey);
            return (
              <label key={f.field} className="plain-field">
                <span className="field-label">
                  {f.label} key <span className="muted small">{set ? '· saved' : ''}</span>
                </span>
                <input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={set ? 'Saved. Leave blank to keep it.' : 'Paste a key'}
                  value={keys[f.field] ?? ''}
                  onChange={(e) => setKeys((k) => ({ ...k, [f.field]: e.target.value }))}
                />
              </label>
            );
          })}
          <Details label="All API keys">
            {KEY_FIELDS.filter((f) => f.presentKey !== provider).map((f) => {
              const set = keyPresent(present, f.presentKey);
              return (
                <label key={f.field} className="plain-field">
                  <span className="field-label">
                    {f.label} key <span className="muted small">{set ? '· saved' : ''}</span>
                  </span>
                  <input
                    type="password"
                    autoComplete="off"
                    spellCheck={false}
                    placeholder={set ? 'Saved. Leave blank to keep it.' : 'Paste a key'}
                    value={keys[f.field] ?? ''}
                    onChange={(e) => setKeys((k) => ({ ...k, [f.field]: e.target.value }))}
                  />
                </label>
              );
            })}
          </Details>
          <p className="muted small">Keys go to the Pólya engine on this Mac only and are never shown again.</p>
          <div className="row end">
            <button className="btn-primary" onClick={() => void save()} disabled={busy}>
              {busy ? <Spinner /> : null}Save engine settings
            </button>
          </div>
        </section>

        <section className="sheet-sec" aria-labelledby="s-workspace">
          <h3 id="s-workspace">Workspace</h3>
          <p className="muted small">
            Your notes and scratch file live in <code>{workspaceDir}</code>. {files.length} {files.length === 1 ? 'file' : 'files'} found.
          </p>
          <button className="btn-secondary" aria-expanded={editScratch} onClick={() => setEditScratch((v) => !v)}>
            {editScratch ? 'Close scratch.tex' : 'Open scratch.tex'}
          </button>
          {editScratch ? <ScratchEditor /> : null}
        </section>

        <section className="sheet-sec" aria-labelledby="s-advanced">
          <h3 id="s-advanced">Advanced</h3>
          <label className="switch">
            <input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />
            <span className="switch-track" aria-hidden="true" />
            <span>
              Advanced telemetry
              <span className="muted small block">
                Shows the sub-agent (helper) activity panel, status pills (Bjork window, Brier, hypercorrection), the dependency tree with its
                Δ gauge, live prosody numbers and the full tables on the Map.
              </span>
            </span>
          </label>
          {advanced ? (
            <label className="plain-field">
              <span className="field-label">Model overrides (provider=model, one per line)</span>
              <textarea
                className="code"
                rows={3}
                spellCheck={false}
                value={overrides}
                placeholder={'anthropic=<model-id>\nopenrouter=<vendor/model-id>'}
                onChange={(e) => setOverrides(e.target.value)}
              />
            </label>
          ) : null}
        </section>

        <section className="sheet-sec" aria-labelledby="s-keys">
          <h3 id="s-keys">Keyboard</h3>
          <dl className="keys">
            <dt>
              <kbd className="kbd">{MOD_KEY} ↵</kbd>
            </dt>
            <dd>The main button on any screen</dd>
            <dt>
              <kbd className="kbd">Shift ↵</kbd>
            </dt>
            <dd>Send a part of your thinking, or a message</dd>
            <dt>
              <kbd className="kbd">1</kbd> <kbd className="kbd">2</kbd> <kbd className="kbd">3</kbd>
            </dt>
            <dd>Learn, Review, Map</dd>
            <dt>
              <kbd className="kbd">Ctrl Space</kbd>
            </dt>
            <dd>Start or stop dictation</dd>
            <dt>
              <kbd className="kbd">Esc</kbd>
            </dt>
            <dd>Close Details, panels and this sheet</dd>
          </dl>
        </section>
      </div>
    </div>
  );
}
