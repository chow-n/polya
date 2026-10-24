/**
 * Map: the idea graph with a minimal toolbar (search · colour by Topic / Mastery / Due · View menu · Graph | List).
 * Layering, connection-kind filters and Fit live in the View menu. List = the reasoning-chains tables and your notes.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { usePrefs } from '../store/prefs';
import { useHarnessStore, type ColorMode } from '../store/useHarnessStore';
import type { EdgeType } from '../types/harness';
import HypergraphCanvas, { ALL_EDGE_TYPES, EDGE_WORDS } from './HypergraphCanvas';
import { useEscape } from './kit';
import ReasoningChainsTable from './ReasoningChainsTable';

const COLOR_BY: { id: ColorMode; label: string; title: string }[] = [
  { id: 'domain', label: 'Topic', title: 'Colour each idea by its topic' },
  { id: 'mastery', label: 'Mastery', title: 'How well you know each idea' },
  { id: 'fsrs', label: 'Due', title: 'Which ideas are due for review' },
];

function ViewMenu({
  edgeTypes,
  setEdgeTypes,
  showMistakes,
  setShowMistakes,
  onFit,
  onClose,
}: {
  edgeTypes: Set<EdgeType>;
  setEdgeTypes: (s: Set<EdgeType>) => void;
  showMistakes: boolean;
  setShowMistakes: (v: boolean) => void;
  onFit: () => void;
  onClose: () => void;
}): JSX.Element {
  const depthLock = useHarnessStore((s) => s.depthLock);
  const setDepthLock = useHarnessStore((s) => s.setDepthLock);
  const colorMode = useHarnessStore((s) => s.colorMode);
  const setColorMode = useHarnessStore((s) => s.setColorMode);
  const advanced = usePrefs((s) => s.advanced);
  useEscape(onClose, true);
  return (
    <div className="menu" role="dialog" aria-label="View options">
      <p className="menu-k">Layout</p>
      <label className="check">
        <input type="checkbox" checked={depthLock} onChange={(e) => setDepthLock(e.target.checked)} />
        <span>Arrange in layers (basics at the bottom)</span>
      </label>
      <p className="menu-k">Show connections</p>
      {ALL_EDGE_TYPES.map((t) => (
        <label key={t} className="check">
          <input
            type="checkbox"
            checked={edgeTypes.has(t)}
            onChange={(e) => {
              const n = new Set(edgeTypes);
              if (e.target.checked) n.add(t);
              else n.delete(t);
              setEdgeTypes(n);
            }}
          />
          <span>{EDGE_WORDS[t]}</span>
        </label>
      ))}
      <label className="check">
        <input type="checkbox" checked={showMistakes} onChange={(e) => setShowMistakes(e.target.checked)} />
        <span>Common mistakes Pólya has noticed</span>
      </label>
      {advanced ? (
        <label className="check">
          <input type="checkbox" checked={colorMode === 'hypercorrection'} onChange={(e) => setColorMode(e.target.checked ? 'hypercorrection' : 'domain')} />
          <span>Highlight confident mistakes (hypercorrection)</span>
        </label>
      ) : null}
      <div className="menu-sep" />
      <button
        className="text-btn"
        onClick={() => {
          onFit();
          onClose();
        }}
      >
        Fit to screen
      </button>
    </div>
  );
}

export default function MapScreen(): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const colorMode = useHarnessStore((s) => s.colorMode);
  const setColorMode = useHarnessStore((s) => s.setColorMode);
  const selectNode = useHarnessStore((s) => s.selectNode);
  const [view, setView] = useState<'graph' | 'list'>('graph');
  const [search, setSearch] = useState('');
  const [menu, setMenu] = useState(false);
  const [edgeTypes, setEdgeTypes] = useState<Set<EdgeType>>(() => new Set(ALL_EDGE_TYPES));
  const [fitSignal, setFitSignal] = useState(0);
  const [showMistakes, setShowMistakes] = useState(false);
  const menuWrap = useRef<HTMLDivElement>(null);
  const selectedNodeId = useHarnessStore((s) => s.selectedNodeId);
  const selectedEdgeId = useHarnessStore((s) => s.selectedEdgeId);
  const advanced = usePrefs((s) => s.advanced);

  // picking an idea or connection in the list opens it on the graph
  useEffect(() => {
    if (selectedNodeId || selectedEdgeId) setView('graph');
  }, [selectedNodeId, selectedEdgeId]);
  // the misconception colouring is an Advanced view
  useEffect(() => {
    if (!advanced && colorMode === 'hypercorrection') setColorMode('domain');
  }, [advanced, colorMode, setColorMode]);

  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q || !graph) return [];
    return graph.nodes.filter((n) => (showMistakes || n.node_type !== 'BUGGY_RULE') && n.title.toLowerCase().includes(q)).slice(0, 8);
  }, [search, graph, showMistakes]);

  const choose = (id: string): void => {
    setView('graph');
    selectNode(id);
    setSearch('');
  };
  useEscape(() => setSearch(''), search !== '');

  return (
    <div className="map">
      <div className="map-bar">
        <div className="search">
          <input
            type="search"
            aria-label="Find an idea"
            placeholder="Find an idea"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && matches[0]) choose(matches[0].id);
            }}
          />
          {matches.length ? (
            <ul className="search-results" role="listbox" aria-label="Matching ideas">
              {matches.map((n) => (
                <li key={n.id}>
                  <button role="option" aria-selected={false} onClick={() => choose(n.id)}>
                    {n.title}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        {view === 'graph' ? (
          <div className="seg" role="radiogroup" aria-label="Colour by">
            <span className="seg-label">Colour by</span>
            {COLOR_BY.map((m) => (
              <button
                key={m.id}
                role="radio"
                aria-checked={colorMode === m.id}
                className={`seg-opt${colorMode === m.id ? ' on' : ''}`}
                onClick={() => setColorMode(m.id)}
                title={m.title}
              >
                {m.label}
              </button>
            ))}
          </div>
        ) : null}
        <span className="spacer" />
        {view === 'graph' ? (
          <div className="menu-wrap" ref={menuWrap}>
            <button className="btn-secondary" aria-expanded={menu} onClick={() => setMenu((v) => !v)}>
              View
            </button>
            {menu ? (
              <ViewMenu
                edgeTypes={edgeTypes}
                setEdgeTypes={setEdgeTypes}
                showMistakes={showMistakes}
                setShowMistakes={setShowMistakes}
                onFit={() => setFitSignal((n) => n + 1)}
                onClose={() => setMenu(false)}
              />
            ) : null}
          </div>
        ) : null}
        <div className="seg" role="radiogroup" aria-label="Show as">
          {(['graph', 'list'] as const).map((v) => (
            <button key={v} role="radio" aria-checked={view === v} className={`seg-opt${view === v ? ' on' : ''}`} onClick={() => setView(v)}>
              {v === 'graph' ? 'Graph' : 'List'}
            </button>
          ))}
        </div>
      </div>
      {menu ? <div className="menu-scrim" onMouseDown={() => setMenu(false)} /> : null}
      <div className="map-stage">{view === 'graph' ? <HypergraphCanvas edgeTypes={edgeTypes} fitSignal={fitSignal} showMistakes={showMistakes} /> : <ReasoningChainsTable />}</div>
    </div>
  );
}
