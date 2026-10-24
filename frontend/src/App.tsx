/**
 * Pólya shell: header (wordmark · Learn · Review · Map · activity · ⚙) above one destination at a time, or the session
 * focus view. Advanced telemetry (Settings) adds the legacy status pills under the header and the helper/dependency rails.
 * Keys: Cmd/Ctrl+Enter = the current card's primary action · Esc closes Details, panels and sheets ·
 * 1/2/3 switch destinations when not typing · Ctrl+Space toggles dictation.
 */
import { useEffect } from 'react';
import AppHeader from './components/AppHeader';
import { runEscape, runPrimaryAction } from './components/kit';
import LearnHome from './components/LearnHome';
import MapScreen from './components/MapScreen';
import ReviewScreen from './components/ReviewScreen';
import SessionFocus from './components/SessionFocus';
import SettingsSheet from './components/SettingsSheet';
import { SubagentModals } from './components/SidebarSubagentDock';
import TelemetryPills, { ScratchModal } from './components/TopTelemetryBar';
import { isTypingTarget } from './components/ui';
import { usePrefs } from './store/prefs';
import { useHarnessStore, type TabId } from './store/useHarnessStore';

function Toasts(): JSX.Element {
  const toasts = useHarnessStore((s) => s.toasts);
  const dismiss = useHarnessStore((s) => s.dismissToast);
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <button key={t.id} className={`toast ${t.kind}`} onClick={() => dismiss(t.id)} title="Dismiss">
          {t.text}
        </button>
      ))}
    </div>
  );
}

export default function App(): JSX.Element {
  const init = useHarnessStore((s) => s.init);
  const tab = useHarnessStore((s) => s.tab);
  const focusOpen = useHarnessStore((s) => s.focusOpen);
  const modal = useHarnessStore((s) => s.modal);
  const openModal = useHarnessStore((s) => s.openModal);
  const advanced = usePrefs((s) => s.advanced);

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      const s = useHarnessStore.getState();
      // Ctrl+Space: toggle dictation anywhere (even while typing)
      if (e.ctrlKey && !e.metaKey && (e.code === 'Space' || e.key === ' ')) {
        e.preventDefault();
        void s.toggleMic();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        if (s.modal && s.modal.kind !== 'settings') return;
        e.preventDefault();
        runPrimaryAction();
        return;
      }
      if (e.key === 'Escape') {
        if (s.modal && s.modal.kind !== 'settings') return; // legacy modals close themselves
        if (runEscape()) {
          e.preventDefault();
          return;
        }
        if (s.selectedNodeId || s.selectedEdgeId) {
          s.selectNode(null);
          s.selectEdge(null);
        }
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target) || s.modal) return;
      if (e.key === '1' || e.key === '2' || e.key === '3') {
        e.preventDefault();
        s.setTab(Number(e.key) as TabId);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className={`app${focusOpen ? ' in-focus' : ''}${tab === 3 && !focusOpen ? ' on-map' : ''}`}>
      <AppHeader />
      {advanced ? <TelemetryPills /> : null}
      <main className="stage" id="main">
        {focusOpen ? <SessionFocus /> : tab === 1 ? <LearnHome /> : tab === 2 ? <ReviewScreen /> : <MapScreen />}
      </main>
      <div className="legacy-modals legacy-skin">
        <SubagentModals />
        {modal?.kind === 'scratch' ? <ScratchModal onClose={() => openModal(null)} /> : null}
      </div>
      {modal?.kind === 'settings' ? <SettingsSheet onClose={() => openModal(null)} /> : null}
      <Toasts />
    </div>
  );
}
