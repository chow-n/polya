/**
 * Practice card (PRACTICE_CHUNK): the problem, one "Think out loud" thread (Shift+Enter sends a part, feedback appears
 * under it), hints one at a time in plain words, then "I'm done" with a confidence chip.
 * Also exports the assessment data (shown under Details) and the Advanced practice launcher.
 *  - chunks: POST /chunk · hints: POST /hint in order R0→R4 · final: POST /submit (payload unchanged)
 */
import { useMemo, useState } from 'react';
import { useHarnessStore, type HeldResult } from '../store/useHarnessStore';
import type { ChunkEvaluation, HintOut, LadderRung, StepPayload, StepResult } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { ConfidenceChips, DetailRow, Details, MathField, PrimaryButton, Spinner as Spin, isChipValue, usePrimaryAction } from './kit';
import { StepMedia } from './ReadingStreamBox';
import { CardHead, ResultBlock, StepDetails, cleanPrompt } from './stepParts';
import { Bar, C, Kv, OUTCOME_COLOR, Spinner, domainColor, fx, pct } from './ui';

// ------------------------------------------------------------------ hint ladder model (§4 Law 6 + §3.1 rating map)
export const RUNGS: { rung: LadderRung; label: string; blurb: string; cap: number; m: number }[] = [
  { rung: 'R0', label: 'Check the basics', blurb: 'Check shapes, domains, limits x→0, ∞.', cap: 3, m: 1.0 },
  { rung: 'R1', label: 'Where to look', blurb: 'Points at the exact expression to look at.', cap: 3, m: 1.0 },
  { rung: 'R2', label: 'A nudge', blurb: 'Reminds you of the idea underneath, without naming the move.', cap: 2, m: 0.55 },
  { rung: 'R3', label: 'Try a simpler case', blurb: 'Work the one-dimensional or two-by-two version first.', cap: 2, m: 0.55 },
  { rung: 'R4', label: 'A worked example', blurb: 'A short solved problem with the same shape.', cap: 2, m: 0.55 },
];
const RATING_NAME: Record<number, string> = { 1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy' };

// ------------------------------------------------------------------ assessment metadata card
export function AssessmentCard({ result, defaultOpen = true }: { result: StepResult; defaultOpen?: boolean }): JSX.Element {
  const graph = useHarnessStore((s) => s.graph);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const [open, setOpen] = useState(defaultOpen);
  const [json, setJson] = useState(false);
  const t = result.trace;
  const title = (id: string): string => graph?.nodes.find((n) => n.id === id)?.title ?? id;
  const correct = t.is_correct === 1;
  const metadata = useMemo(
    () => ({
      target_nodes: t.target_node_ids,
      cue_level: t.cue_level,
      outcome: t.outcome,
      max_hint_rung: t.max_hint_rung,
      miss_class: t.miss_class,
      trace_quality_score: t.trace_quality_score,
      confidence: t.confidence_slider,
      is_correct: t.is_correct,
      brier_score: t.brier_score,
      bkt_delta: t.bkt_mastery_after - t.bkt_mastery_before,
      fsrs_stability_delta_days: t.fsrs_stability_after - t.fsrs_stability_before,
      prosody: t.prosody_metrics,
      node_updates: result.node_updates,
      delta: { before: result.delta_before, after: result.delta_after },
      remedial_spliced: result.remedial_spliced,
      created_nodes: result.created_nodes,
    }),
    [t, result],
  );
  const bktDelta = t.bkt_mastery_after - t.bkt_mastery_before;
  const sDelta = t.fsrs_stability_after - t.fsrs_stability_before;

  return (
    <div className="assess legacy-skin">
      <button className="assess-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="outcome-tag mono" style={{ color: OUTCOME_COLOR[t.outcome], borderColor: OUTCOME_COLOR[t.outcome] }}>
          {t.outcome}
        </span>
        <span className="mono dim">
          {t.phase} · step {t.step_index + 1}
        </span>
        <span className="spacer" />
        <span className="mono">
          P(L) <b style={{ color: bktDelta >= 0 ? C.emerald : C.rose }}>{bktDelta >= 0 ? '+' : ''}{fx(bktDelta, 3)}</b> · S{' '}
          <b style={{ color: sDelta >= 0 ? C.emerald : C.rose }}>{sDelta >= 0 ? '+' : ''}{fx(sDelta, 2)}d</b>
        </span>
        <span className="dim mono">{open ? '▾' : '▸'}</span>
      </button>
      {open ? (
        <div className="assess-body">
          {result.feedback_markdown ? <MathText text={result.feedback_markdown} className="feedback" /> : null}
          {t.ai_diagnosis_markdown ? (
            <div className="diagnosis">
              <span className="mono tag rose">BUG-LIBRARY DIAGNOSIS</span>
              <MathText text={t.ai_diagnosis_markdown} />
            </div>
          ) : null}
          <div className="meta-grid">
            <Kv
              k="Target Nodes"
              mono={false}
              v={
                <span className="chips-inline">
                  {t.target_node_ids.map((id) => (
                    <button key={id} className="chip" onClick={() => focus(id)}>
                      {title(id)}
                    </button>
                  ))}
                </span>
              }
            />
            <Kv k="Cue Level" v={`L${t.cue_level}`} />
            <Kv k="Outcome" v={<span style={{ color: OUTCOME_COLOR[t.outcome] }}>{t.outcome}</span>} />
            <Kv k="Max Hint Rung" v={t.max_hint_rung} />
            <Kv k="Miss Class" v={<span style={{ color: t.miss_class === 'NONE' ? C.muted : C.amber }}>{t.miss_class}</span>} />
            <Kv k="Trace Quality Score" v={<>{fx(t.trace_quality_score)} <Bar value={t.trace_quality_score} /></>} />
            <Kv
              k="Confidence vs. Accuracy"
              v={
                <>
                  {pct(t.confidence_slider)} vs {correct ? '✓ correct' : '✗ wrong'} · Brier {fx(t.brier_score, 3)}
                </>
              }
            />
            <Kv k="BKT Delta" v={`${fx(t.bkt_mastery_before, 3)} → ${fx(t.bkt_mastery_after, 3)} (${bktDelta >= 0 ? '+' : ''}${fx(bktDelta, 3)})`} />
            <Kv
              k="FSRS Stability Delta"
              v={`${fx(t.fsrs_stability_before, 2)}d → ${fx(t.fsrs_stability_after, 2)}d (${sDelta >= 0 ? '+' : ''}${fx(sDelta, 2)} days)`}
            />
            <Kv k="Step velocity Δ" v={`${result.delta_before.toFixed(1)} → ${result.delta_after.toFixed(1)}`} />
            <Kv
              k="Prosody"
              v={`${t.prosody_metrics.engine} · lat ${t.prosody_metrics.initial_latency_ms}ms · ${t.prosody_metrics.hesitation_count} pauses · ${t.prosody_metrics.hedge_count} hedges · ${Math.round(t.prosody_metrics.wpm)} wpm`}
            />
            {result.remedial_spliced ? <Kv k="Remedial splice" v={<span style={{ color: C.amber }}>{title(result.remedial_spliced)}</span>} /> : null}
            {result.created_nodes.length ? (
              <Kv
                k="Created nodes"
                mono={false}
                v={
                  <span className="chips-inline">
                    {result.created_nodes.map((id) => (
                      <button key={id} className="chip rose" onClick={() => focus(id)}>
                        {title(id)}
                      </button>
                    ))}
                  </span>
                }
              />
            ) : null}
          </div>
          {result.node_updates.length ? (
            <table className="tbl compact">
              <thead>
                <tr>
                  <th>node</th>
                  <th className="num">G</th>
                  <th className="num">R@review</th>
                  <th className="num">P(L)</th>
                  <th className="num">S (days)</th>
                  <th className="num">D</th>
                  <th>cue dim</th>
                  <th>flags</th>
                </tr>
              </thead>
              <tbody>
                {result.node_updates.map((u) => (
                  <tr key={u.node_id}>
                    <td className="truncate">
                      <button className="link" onClick={() => focus(u.node_id)}>
                        {u.title}
                      </button>
                      {u.propagated_to.length ? <span className="dim small"> ⇢ {u.propagated_to.length} premises</span> : null}
                    </td>
                    <td className="num mono">
                      {u.rating} <span className="dim">{RATING_NAME[u.rating] ?? ''}</span>
                    </td>
                    <td className="num mono">{fx(u.retrievability_at_review, 3)}</td>
                    <td className="num mono">
                      {fx(u.bkt_before)}→{fx(u.bkt_after)}
                    </td>
                    <td className="num mono">
                      {fx(u.stability_before)}→{fx(u.stability_after)}
                    </td>
                    <td className="num mono">{fx(u.difficulty_after)}</td>
                    <td className="mono small">{u.cue_dimension ?? '—'}</td>
                    <td className="mono small">
                      {u.hypercorrection_bonus_applied ? <span style={{ color: C.emerald }}>1.25× hypercorrection</span> : null}
                      {u.hypercorrection_flag ? <span style={{ color: C.rose }}> ⚑ flagged</span> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <button className="btn tiny ghost" onClick={() => setJson((v) => !v)}>
            {json ? 'Hide' : 'Show'} exact JSON metadata
          </button>
          {json ? <pre className="code-block small">{JSON.stringify(metadata, null, 2)}</pre> : null}
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ launcher + queue
export function ArenaLauncher(): JSX.Element {
  const files = useHarnessStore((s) => s.workspaceFiles);
  const queue = useHarnessStore((s) => s.practiceQueue);
  const graph = useHarnessStore((s) => s.graph);
  const createSession = useHarnessStore((s) => s.createSession);
  const busy = useHarnessStore((s) => s.busy.create);
  const refreshQueue = useHarnessStore((s) => s.refreshQueue);
  const [cueLevel, setCueLevel] = useState(1);
  const [contrastive, setContrastive] = useState(false);
  const [problemFile, setProblemFile] = useState('');
  const [targetNode, setTargetNode] = useState('');
  const [showQueue, setShowQueue] = useState(true);
  const problems = files.filter((f) => f.path.startsWith('problems/'));
  const nodes = useMemo(() => [...(graph?.nodes ?? [])].sort((a, b) => a.title.localeCompare(b.title)), [graph]);
  const tTitle = nodes.find((n) => n.id === targetNode)?.title;

  const practice = (nodeId?: string, title?: string): void => {
    void createSession({
      mode: 'PRACTICE',
      target_goal: title
        ? `Cue-demand practice: ${title}`
        : problemFile
          ? `Practice from ${problemFile}`
          : tTitle
            ? `Cue-demand practice: ${tTitle}`
            : 'Interleaved Bjork-window practice',
      target_node_id: nodeId ?? (targetNode || null),
      cue_level: cueLevel,
      contrastive_pair: contrastive,
      problem_file: problemFile || null,
    });
  };
  const duel = (sub: 'PROOF_REFEREE' | 'FEYNMAN_STUDENT'): void => {
    void createSession({
      mode: 'REFEREE_DUEL',
      sub_mode: sub,
      target_goal: `${sub === 'PROOF_REFEREE' ? 'Proof-Referee duel' : 'Feynman student duel'}${tTitle ? `: ${tTitle}` : ''}`,
      target_node_id: targetNode || null,
      cue_level: Math.max(cueLevel, sub === 'PROOF_REFEREE' ? 4 : cueLevel),
    });
  };
  const maxScore = Math.max(1e-9, ...queue.map((q) => q.score));

  return (
    <div className="arena-launcher">
      <div className="arena-controls">
        <div className="seg" role="radiogroup" aria-label="Cue obfuscation level">
          <span className="seg-label">Cue level</span>
          {[1, 2, 3, 4].map((l) => (
            <button
              key={l}
              role="radio"
              aria-checked={cueLevel === l}
              className={`seg-btn${cueLevel === l ? ' on' : ''}`}
              onClick={() => setCueLevel(l)}
              title={['Canonical', 'Disguised notation', 'Synthesis / contrast', 'Violated premise'][l - 1]}
            >
              L{l}
            </button>
          ))}
        </div>
        <label className="toggle" title="Pair the target with its CONTRASTIVE peer so you must discriminate the boundary">
          <input type="checkbox" checked={contrastive} onChange={(e) => setContrastive(e.target.checked)} />
          <span className="toggle-track" />
          <span>Contrastive Pair Mode</span>
        </label>
        <select value={problemFile} onChange={(e) => setProblemFile(e.target.value)} title="Import a problem file from workspace/problems/">
          <option value="">import problem: none</option>
          {problems.map((f) => (
            <option key={f.path} value={f.path}>
              {f.path}
            </option>
          ))}
        </select>
        <select value={targetNode} onChange={(e) => setTargetNode(e.target.value)} title="Target node (blank = queue picks)">
          <option value="">target: practice queue</option>
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.title}
            </option>
          ))}
        </select>
        <span className="spacer" />
        <button className="btn primary" disabled={busy} onClick={() => practice()}>
          {busy ? <Spinner /> : null}Start Practice
        </button>
        <button className="btn" disabled={busy} onClick={() => duel('PROOF_REFEREE')} title="Find the camouflaged fallacy">
          ⚖ Proof-Referee
        </button>
        <button className="btn" disabled={busy} onClick={() => duel('FEYNMAN_STUDENT')} title="Teach a buggy-rule student">
          ☺ Feynman Duel
        </button>
      </div>
      <div className="queue">
        <button className="queue-head" onClick={() => setShowQueue((v) => !v)} aria-expanded={showQueue}>
          <span>Interleaved practice queue</span>
          <span className="mono dim">
            score = 0.35·Gauss(R; 0.78, 0.12) + 0.25·(1−R) + 0.20·(1−c̄) + 0.20·⚑ − interleave {showQueue ? '▾' : '▸'}
          </span>
        </button>
        {showQueue ? (
          <table className="tbl compact">
            <thead>
              <tr>
                <th>#</th>
                <th>node</th>
                <th className="num">R(t)</th>
                <th className="num">bjork</th>
                <th className="num">forget</th>
                <th className="num">cue gap</th>
                <th className="num">⚑</th>
                <th className="num">interleave</th>
                <th className="num">score</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {queue.length === 0 ? (
                <tr>
                  <td colSpan={10} className="dim">
                    Queue empty.{' '}
                    <button className="link" onClick={() => void refreshQueue()}>
                      Refresh
                    </button>
                  </td>
                </tr>
              ) : null}
              {queue.map((q, i) => (
                <tr key={q.node_id}>
                  <td className="mono dim">{i + 1}</td>
                  <td className="truncate">
                    <span className="dot-inline" style={{ background: domainColor(q.domain_cluster) }} />
                    {q.title}
                  </td>
                  <td className="num mono" style={{ color: q.retrievability >= 0.7 && q.retrievability <= 0.85 ? C.cyan : undefined }}>
                    {fx(q.retrievability, 3)}
                  </td>
                  <td className="num mono">{fx(q.bjork_component, 3)}</td>
                  <td className="num mono">{fx(q.forgetting_component, 3)}</td>
                  <td className="num mono">{fx(q.cue_gap_component, 3)}</td>
                  <td className="num mono">{fx(q.hypercorrection_component, 2)}</td>
                  <td className="num mono">{q.interleave_penalty ? `−${fx(q.interleave_penalty, 3)}` : '0'}</td>
                  <td className="num mono">
                    {fx(q.score, 3)} <Bar value={q.score / maxScore} color={C.indigo} />
                  </td>
                  <td>
                    <button className="btn tiny" disabled={busy} onClick={() => practice(q.node_id, q.title)}>
                      Practice ▸
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ hints (one at a time, plain labels)
function Hints({ step }: { step: StepPayload }): JSX.Element | null {
  const unlocked = new Map<LadderRung, HintOut>(step.hints_unlocked.map((h) => [h.rung, h]));
  const shown = RUNGS.filter((r) => unlocked.has(r.rung));
  if (!shown.length) return null;
  return (
    <div className="hints">
      {shown.map((r, i) => (
        <aside key={r.rung} className="hint">
          <p className="hint-k">
            Hint {i + 1} · {r.label}
          </p>
          <MathText text={unlocked.get(r.rung)?.hint_markdown ?? ''} />
        </aside>
      ))}
    </div>
  );
}

function HintButton({ step }: { step: StepPayload }): JSX.Element {
  const requestHint = useHarnessStore((s) => s.requestHint);
  const busy = useHarnessStore((s) => s.busy.hint);
  const unlocked = new Set(step.hints_unlocked.map((h) => h.rung));
  const next = RUNGS.find((r) => !unlocked.has(r.rung));
  return (
    <button
      className="btn-secondary"
      disabled={!next || busy}
      onClick={() => next && void requestHint(next.rung)}
      title={next ? `${next.label}. Hints make this count a little less toward your memory schedule.` : 'No more hints'}
    >
      {busy ? <Spin /> : null}
      {!next ? 'No more hints' : unlocked.size ? 'Another hint' : 'Hint'}
    </button>
  );
}

// ------------------------------------------------------------------ thread
function ThreadItem({ c }: { c: ChunkEvaluation }): JSX.Element {
  const tone = c.slip_detected ? 'bad' : c.demand_satisfied ? 'good' : 'plain';
  return (
    <li className={`thread-item tone-${tone}`}>
      <div className="thread-you">
        <MathText text={c.text} />
      </div>
      {c.feedback_markdown || tone !== 'plain' ? (
        <div className="thread-fb">
          {tone === 'good' ? <span className="fb-mark">✓ On the right track. </span> : tone === 'bad' ? <span className="fb-mark">Check this step. </span> : null}
          {c.feedback_markdown ? <MathText text={c.feedback_markdown.replace(/\bR[0-4]\s+/g, '')} inline /> : null}
        </div>
      ) : null}
    </li>
  );
}

function ChunkDetails({ chunks }: { chunks: ChunkEvaluation[] }): JSX.Element | null {
  if (!chunks.length) return null;
  return (
    <div className="dsec">
      <div className="dsec-k">Each part, as scored</div>
      {chunks.map((c) => (
        <DetailRow key={c.chunk_index} k={`Part ${c.chunk_index + 1}`}>
          quality ≈ {fx(c.quality_estimate)} · {c.demand_satisfied ? 'key step found' : 'key step open'}
          {c.slip_detected ? ' · slip' : ''}
          {c.matched_concepts.length ? ` · covered: ${c.matched_concepts.join(', ')}` : ''}
          {c.missing_concepts.length ? ` · missing: ${c.missing_concepts.join(', ')}` : ''}
          {c.verifier_summary ? ` · ∑ ${c.verifier_summary}` : ''}
        </DetailRow>
      ))}
    </div>
  );
}

export default function PracticeArena({ step, held }: { step: StepPayload; held?: HeldResult | null }): JSX.Element {
  const chunkLog = useHarnessStore((s) => s.chunkLog);
  const submitChunk = useHarnessStore((s) => s.submitChunk);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busyChunk = useHarnessStore((s) => s.busy.chunk);
  const busySubmit = useHarnessStore((s) => s.busy.submit);
  const liveText = useHarnessStore((s) => s.draft.text);
  const liveConfidence = useHarnessStore((s) => s.draft.confidence);
  const setDraft = useHarnessStore((s) => s.setDraft);
  const graph = useHarnessStore((s) => s.graph);
  const sessionId = useHarnessStore((s) => s.activeSessionId);
  const done = Boolean(held);
  const text = held ? held.draft.text : liveText;
  const confidence = held ? held.draft.confidence : liveConfidence;

  const chunks = useMemo(() => {
    const m = new Map<number, ChunkEvaluation>();
    step.chunks.forEach((c) => m.set(c.chunk_index, c));
    if (held) held.chunks.forEach((c) => m.set(c.chunk_index, c));
    else if (chunkLog.stepId === step.step_id) chunkLog.items.forEach((c) => m.set(c.chunk_index, c));
    return [...m.values()].sort((a, b) => a.chunk_index - b.chunk_index);
  }, [step.chunks, step.step_id, chunkLog, held]);

  const pair = step.contrastive_pair_node_id ? graph?.nodes.find((n) => n.id === step.contrastive_pair_node_id) : undefined;
  const canFinish = !done && !busySubmit && (chunks.length > 0 || text.trim().length > 0) && isChipValue(confidence);

  const finalSubmit = (): void => {
    if (!canFinish) return;
    const all = [...chunks.map((c) => c.text), text.trim()].filter(Boolean);
    void submitStep({
      raw_prediction_locked: chunks[0]?.text ?? text.trim(),
      verification_thinking: all.join('\n\n'),
    });
  };
  usePrimaryAction(finalSubmit, canFinish);

  return (
    <article className="card practice">
      <CardHead step={step} />
      <div className="prompt">
        <MathText text={cleanPrompt(step.prompt_latex)} />
      </div>
      {pair ? (
        <p className="aside-note">
          Compare it with <b>{pair.title}</b>, and say what separates the two.
        </p>
      ) : null}
      <StepMedia step={step} sessionId={sessionId} />

      {chunks.length || busyChunk ? (
        <ol className="thread" aria-label="Your thinking so far">
          {chunks.map((c) => (
            <ThreadItem key={c.chunk_index} c={c} />
          ))}
          {busyChunk ? (
            <li className="thread-item pending">
              <Spin /> Reading your thinking…
            </li>
          ) : null}
        </ol>
      ) : null}

      <Hints step={step} />

      {!done ? (
        <>
          <MathField
            label="Think out loud"
            placeholder="Write one step of your thinking at a time."
            value={text}
            onChange={(v) => setDraft({ text: v })}
            micTarget="dock"
            rows={3}
            autoFocus
            onShiftEnter={() => void submitChunk()}
            hint="Shift+Enter sends this part. Feedback appears under it."
          />
          <div className="row">
            <button className="btn-secondary" disabled={!text.trim() || busyChunk} onClick={() => void submitChunk()}>
              Send this part
            </button>
            <HintButton step={step} />
          </div>
        </>
      ) : null}

      <ConfidenceChips value={confidence} onChange={(v) => setDraft({ confidence: v })} disabled={done} label="How sure are you of your answer?" />
      {!done ? (
        <div className="actions">
          <PrimaryButton onClick={finalSubmit} disabled={!canFinish} busy={busySubmit} busyLabel="Checking…">
            I’m done
          </PrimaryButton>
          {!isChipValue(confidence) && (chunks.length > 0 || text.trim()) ? <span className="muted small">Say how sure you are first.</span> : null}
        </div>
      ) : null}

      {held ? <ResultBlock held={held} /> : null}

      <Details>
        <StepDetails step={step} held={held} extra={<ChunkDetails chunks={chunks} />} />
      </Details>
    </article>
  );
}
