/**
 * Learn (home): one question, one field, Start. Below it: the review entry, up to three sessions to continue, the
 * first-run "How Pólya works" note and a small "Use my notes…" link for attaching workspace files.
 * Start creates a probe-then-teach session (POST /api/sessions, mode PROBE, target_goal = the text).
 */
import { useEffect, useId, useMemo, useState } from 'react';
import { usePrefs } from '../store/prefs';
import { useHarnessStore } from '../store/useHarnessStore';
import type { SessionOut } from '../types/harness';
import { PrimaryButton, useEscape, usePrimaryAction } from './kit';

function sessionKind(s: SessionOut): string {
  if (s.mode === 'PRACTICE') return 'Review';
  if (s.mode === 'REFEREE_DUEL') return s.sub_mode === 'FEYNMAN_STUDENT' ? 'Explain it' : 'Find the flaw';
  return 'Learning';
}

function progressWords(s: SessionOut): string {
  const total = s.dependency_plan.length;
  const done = s.dependency_plan.filter((p) => p.status === 'done' || p.status === 'probed_mastered').length;
  return total ? `${done} of ${total} ${total === 1 ? 'idea' : 'ideas'}` : '';
}

export function NotesPicker({
  selected,
  onChange,
  onClose,
}: {
  selected: string[];
  onChange: (files: string[]) => void;
  onClose: () => void;
}): JSX.Element {
  const files = useHarnessStore((s) => s.workspaceFiles);
  const refreshFiles = useHarnessStore((s) => s.refreshFiles);
  const attachable = files.filter((f) => f.kind === 'tex' || f.kind === 'pdf' || f.kind === 'md');
  useEffect(() => {
    void refreshFiles();
  }, [refreshFiles]);
  useEscape(onClose, true);
  return (
    <div className="notes-picker" role="group" aria-label="Your notes">
      <p className="muted small">Pólya reads the files you tick and builds the session around them.</p>
      {attachable.length === 0 ? <p className="muted small">No notes yet. Put .tex, .md or .pdf files in the workspace notes folder.</p> : null}
      <ul>
        {attachable.map((f) => {
          const on = selected.includes(f.path);
          return (
            <li key={f.path}>
              <label className="check">
                <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked ? [...selected, f.path] : selected.filter((p) => p !== f.path))} />
                <span>{f.path.split('/').pop()}</span>
                <span className="muted small">{f.path.split('/').slice(0, -1).join('/')}</span>
              </label>
            </li>
          );
        })}
      </ul>
      <button className="text-btn" onClick={onClose}>
        Done
      </button>
    </div>
  );
}

export default function LearnHome(): JSX.Element {
  const createSession = useHarnessStore((s) => s.createSession);
  const busy = useHarnessStore((s) => s.busy.create);
  const sessions = useHarnessStore((s) => s.sessions);
  const loadSession = useHarnessStore((s) => s.loadSession);
  const stats = useHarnessStore((s) => s.stats);
  const setTab = useHarnessStore((s) => s.setTab);
  const preset = useHarnessStore((s) => s.launcherPreset);
  const introDismissed = usePrefs((s) => s.introDismissed);
  const dismissIntro = usePrefs((s) => s.dismissIntro);
  const [topic, setTopic] = useState('');
  const [attached, setAttached] = useState<string[]>([]);
  const [picking, setPicking] = useState(false);
  const fieldId = useId();

  // "Use for a new session" from the Map's notes list arrives as a launcher preset.
  useEffect(() => {
    if (preset?.attached_files) setAttached(preset.attached_files);
    if (preset?.target_goal) setTopic(preset.target_goal);
  }, [preset]);

  // First run stays extra quiet (at most six controls): one Continue row until the explainer is dismissed.
  const active = useMemo(() => sessions.filter((s) => s.status === 'ACTIVE').slice(0, introDismissed ? 3 : 1), [sessions, introDismissed]);
  const due = stats?.due_count ?? 0;
  const goal = topic.trim();

  const start = (): void => {
    if (!goal || busy) return;
    void createSession({
      mode: 'PROBE',
      sub_mode: 'STANDARD',
      target_goal: goal,
      attached_files: attached,
      target_node_id: null,
      cue_level: 1,
    }).then((st) => {
      if (st) {
        setTopic('');
        setAttached([]);
        dismissIntro();
      }
    });
  };
  usePrimaryAction(start, goal.length > 0 && !busy);

  return (
    <div className="page home">
      <section className="ask">
        <label className="ask-q" htmlFor={fieldId}>
          What do you want to understand?
        </label>
        <textarea
          id={fieldId}
          className="ask-field"
          rows={1}
          value={topic}
          autoFocus
          placeholder="For example: why attention divides by √d"
          onChange={(e) => {
            setTopic(e.target.value);
            // grow with the text: one ruled line until the question needs more
            e.target.style.height = 'auto';
            e.target.style.height = `${e.target.scrollHeight}px`;
          }}
        />
        <div className="ask-row">
          <button className="text-btn" aria-expanded={picking} onClick={() => setPicking((v) => !v)}>
            {attached.length ? `Using ${attached.length} ${attached.length === 1 ? 'note' : 'notes'}` : 'Use my notes…'}
          </button>
          <PrimaryButton onClick={start} disabled={!goal} busy={busy} busyLabel="Starting…">
            Start
          </PrimaryButton>
        </div>
        {picking ? <NotesPicker selected={attached} onChange={setAttached} onClose={() => setPicking(false)} /> : null}
      </section>

      {due > 0 || active.length ? (
        <section className="next" aria-label="Pick up where you left off">
          {due > 0 ? (
            <button className="next-row review" onClick={() => setTab(2)}>
              <span className="next-title">
                Review · {due} due <span aria-hidden="true">→</span>
              </span>
              <span className="next-meta">Ideas you are about to forget</span>
            </button>
          ) : null}
          {active.map((s) => (
            <button key={s.id} className="next-row" onClick={() => void loadSession(s.id)}>
              <span className="next-title">
                <span className="muted">Continue · </span>
                {s.target_goal}
              </span>
              <span className="next-meta">{[sessionKind(s), progressWords(s)].filter(Boolean).join(', ')}</span>
            </button>
          ))}
        </section>
      ) : null}

      {!introDismissed ? (
        <section className="intro" aria-labelledby="intro-h">
          <h2 id="intro-h">How Pólya works</h2>
          <ol>
            <li>Guess before you see answers.</li>
            <li>Read a short explanation, then check yourself.</li>
            <li>Pólya brings ideas back right before you’d forget them.</li>
          </ol>
          <button className="text-btn" onClick={dismissIntro}>
            Got it
          </button>
        </section>
      ) : null}
    </div>
  );
}
