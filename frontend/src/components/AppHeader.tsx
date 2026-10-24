/**
 * Header: wordmark · Learn · Review · Map · a quiet activity line while helpers run · ⚙. Nothing else.
 * The activity line is driven by the request in flight and by `subagent_status` WebSocket events, in plain words.
 */
import { useHarnessStore, type TabId } from '../store/useHarnessStore';
import { ALL_AGENTS, type AgentName } from '../types/harness';

const NAV: { id: TabId; label: string }[] = [
  { id: 1, label: 'Learn' },
  { id: 2, label: 'Review' },
  { id: 3, label: 'Map' },
];

const AGENT_WORDS: Record<AgentName, string> = {
  SYMBOLIC_VERIFIER: 'Checking your math…',
  BUG_LIBRARY_DIAGNOSTICIAN: 'Looking at your reasoning…',
  COUNTEREXAMPLE_SYNTHESIZER: 'Testing your claim…',
  SANDBOX_DEMO_BUILDER: 'Building a demo…',
  SVG_DIAGRAM_MAKER: 'Drawing a diagram…',
  LOCAL_CORPUS_RAG: 'Reading your notes…',
  LITERATURE_RESEARCHER: 'Looking up sources…',
  ONTOLOGIST_EXTRACTOR: 'Mapping the ideas…',
};

function useActivity(): { text: string; warn: boolean } | null {
  const busy = useHarnessStore((s) => s.busy);
  const subagents = useHarnessStore((s) => s.subagents);
  const backendOk = useHarnessStore((s) => s.backendOk);
  if (backendOk === false) return { text: 'Can’t reach the Pólya engine. Retrying…', warn: true };
  if (busy.create) return { text: 'Preparing your session…', warn: false };
  if (busy.submit) return { text: 'Checking your answer…', warn: false };
  if (busy.advance) return { text: 'Preparing your next step…', warn: false };
  if (busy.chunk) return { text: 'Reading your thinking…', warn: false };
  if (busy.hint) return { text: 'Finding a hint…', warn: false };
  if (busy.duel) return { text: 'The student is thinking…', warn: false };
  const running = ALL_AGENTS.find((a) => subagents[a].state === 'RUNNING');
  if (running) return { text: AGENT_WORDS[running], warn: false };
  return null;
}

export default function AppHeader(): JSX.Element {
  const tab = useHarnessStore((s) => s.tab);
  const focusOpen = useHarnessStore((s) => s.focusOpen);
  const setTab = useHarnessStore((s) => s.setTab);
  const openModal = useHarnessStore((s) => s.openModal);
  const activity = useActivity();

  return (
    <header className="header">
      <div className="header-inner">
        <span className="wordmark" aria-label="Pólya">
          Pólya
        </span>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => {
            const current = tab === n.id && !focusOpen;
            return (
              <button
                key={n.id}
                className={`nav-item${current ? ' on' : ''}${tab === n.id && focusOpen ? ' within' : ''}`}
                aria-current={current ? 'page' : undefined}
                onClick={() => setTab(n.id)}
                title={`${n.label} (${n.id})`}
              >
                {n.label}
              </button>
            );
          })}
        </nav>
        <span className="spacer" />
        <span className={`activity${activity ? ' on' : ''}${activity?.warn ? ' warn' : ''}`} role="status" aria-live="polite">
          {activity ? (
            <>
              <span className="pulse" aria-hidden="true" />
              {activity.text}
            </>
          ) : null}
        </span>
        <button className="icon-btn gear" onClick={() => openModal({ kind: 'settings' })} aria-label="Settings" title="Settings">
          <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor">
            <circle cx="10" cy="10" r="7.1" strokeWidth="2.6" strokeDasharray="2.79 2.79" />
            <circle cx="10" cy="10" r="5.2" strokeWidth="1.8" />
            <circle cx="10" cy="10" r="1.9" strokeWidth="1.6" />
          </svg>
        </button>
      </div>
    </header>
  );
}
