/**
 * Cue-Demand Practice Stream (ARCHITECTURE_SPEC §6.4.1).
 *  - header controls: cue obfuscation level 1–4, contrastive-pair mode, problem import from workspace/problems/, duel launchers
 *  - interleaved practice queue (Bjork window × forgetting × cue gap × hypercorrection − interleave penalty)
 *  - chunked stream-of-consciousness submission (Shift+Enter → POST /chunk)
 *  - 5-rung Socratic hint ladder R0→R4 (POST /hint, in order) with its FSRS stability-multiplier impact
 *  - collapsible assessment metadata card wired back into the hypergraph (StepResult)
 */
import { useMemo, useState } from 'react';
import { useHarnessStore } from '../store/useHarnessStore';
import type { ChunkEvaluation, HintOut, LadderRung, StepPayload, StepResult } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { StepHeader } from './EpistemicLockBox';
import { StepMedia } from './ReadingStreamBox';
import TelemetryInputDock from './TelemetryInputDock';
import { Bar, C, Kv, OUTCOME_COLOR, Spinner, domainColor, fx, pct } from './ui';

// ------------------------------------------------------------------ hint ladder model (§4 Law 6 + §3.1 rating map)
export const RUNGS: { rung: LadderRung; label: string; blurb: string; cap: number; m: number }[] = [
  { rung: 'R0', label: 'R0 Dimensional Check', blurb: 'Check shapes, domains, limits x→0, ∞.', cap: 3, m: 1.0 },
  { rung: 'R1', label: 'R1 Attention Pointer', blurb: 'Quotes the exact expression where the slip sits.', cap: 3, m: 1.0 },
  { rung: 'R2', label: 'R2 Cue Prime', blurb: 'Primes the upstream node without naming the move.', cap: 2, m: 0.55 },
  { rung: 'R3', label: 'R3 Scalar/2D Base Case', blurb: 'Compute the d=1 or n=2 version first.', cap: 2, m: 0.55 },
  { rung: 'R4', label: 'R4 Worked Analog', blurb: '3-line isomorphic worked solution to transfer.', cap: 2, m: 0.55 },
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
    <div className="assess">
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

// ------------------------------------------------------------------ hint ladder
function HintLadder({ step }: { step: StepPayload }): JSX.Element {
  const requestHint = useHarnessStore((s) => s.requestHint);
  const busy = useHarnessStore((s) => s.busy.hint);
  const unlocked = new Map<LadderRung, HintOut>(step.hints_unlocked.map((h) => [h.rung, h]));
  const nextIdx = RUNGS.findIndex((r) => !unlocked.has(r.rung));
  const highest = [...RUNGS].reverse().find((r) => unlocked.has(r.rung));
  const capNow = highest ? (unlocked.get(highest.rung)?.fsrs_rating_cap ?? highest.cap) : 4;
  const mNow = highest ? (unlocked.get(highest.rung)?.stability_multiplier ?? highest.m) : 1.38;
  const [openRung, setOpenRung] = useState<LadderRung | null>(null);
  const shown = openRung ?? highest?.rung ?? null;

  return (
    <div className="ladder">
      <div className="ladder-head">
        <span>Socratic hint ladder</span>
        <span className="mono dim">
          best reachable rating: <b style={{ color: capNow >= 4 ? C.emerald : capNow === 3 ? C.cyan : C.amber }}>G={capNow} {RATING_NAME[capNow]}</b> · stability ×
          {mNow.toFixed(2)}
        </span>
      </div>
      <div className="ladder-steps">
        {RUNGS.map((r, i) => {
          const h = unlocked.get(r.rung);
          const isNext = i === nextIdx;
          return (
            <button
              key={r.rung}
              className={`rung${h ? ' unlocked' : ''}${isNext ? ' next' : ''}${shown === r.rung ? ' shown' : ''}`}
              disabled={(!h && !isNext) || busy}
              onClick={() => {
                if (h) setOpenRung(r.rung);
                else
                  void requestHint(r.rung).then((res) => {
                    if (res) setOpenRung(res.rung);
                  });
              }}
              title={`${r.blurb}\nUnlocking caps the FSRS rating at G=${h?.fsrs_rating_cap ?? r.cap} (stability ×${(h?.stability_multiplier ?? r.m).toFixed(2)})`}
            >
              <span className="rung-id mono">{r.rung}</span>
              <span className="rung-label">{(h?.label ?? r.label).replace(/^R\d\s*/, '')}</span>
              <span className="rung-m mono">
                G≤{h?.fsrs_rating_cap ?? r.cap} · ×{(h?.stability_multiplier ?? r.m).toFixed(2)}
              </span>
              {busy && isNext ? <Spinner /> : null}
            </button>
          );
        })}
      </div>
      {shown && unlocked.get(shown) ? (
        <div className="hint-body">
          <span className="mono tag amber">{unlocked.get(shown)?.label}</span>
          <MathText text={unlocked.get(shown)?.hint_markdown ?? ''} />
        </div>
      ) : (
        <div className="dim small">
          No hints used: a clean solve can still earn G=4 (Easy, stability ×1.38). R0–R1 cap at Good (×1.00); R2–R4 cap at Hard (×0.55).
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ chunk stream
function ChunkCard({ c }: { c: ChunkEvaluation }): JSX.Element {
  return (
    <div className={`chunk${c.demand_satisfied ? ' ok' : ''}${c.slip_detected ? ' slip' : ''}`}>
      <div className="chunk-head mono">
        <span>chunk {c.chunk_index + 1}</span>
        <span className={`tag ${c.demand_satisfied ? 'emerald' : 'slate'}`}>{c.demand_satisfied ? 'DEMAND MET' : 'demand open'}</span>
        {c.slip_detected ? <span className="tag rose">SLIP</span> : null}
        <span className="spacer" />
        <span>q≈{fx(c.quality_estimate)}</span>
        <Bar value={c.quality_estimate} />
      </div>
      <div className="chunk-text">
        <MathText text={c.text} />
      </div>
      {c.feedback_markdown ? (
        <div className="chunk-feedback">
          <MathText text={c.feedback_markdown} />
        </div>
      ) : null}
      <div className="chunk-concepts">
        {c.matched_concepts.map((m) => (
          <span key={`m-${m}`} className="concept ok">
            ✓ {m}
          </span>
        ))}
        {c.missing_concepts.map((m) => (
          <span key={`x-${m}`} className="concept miss">
            ○ {m}
          </span>
        ))}
      </div>
      {c.verifier_summary ? <div className="verifier mono small">∑ {c.verifier_summary}</div> : null}
    </div>
  );
}

export default function PracticeArena({ step }: { step: StepPayload }): JSX.Element {
  const chunkLog = useHarnessStore((s) => s.chunkLog);
  const submitChunk = useHarnessStore((s) => s.submitChunk);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const busyChunk = useHarnessStore((s) => s.busy.chunk);
  const busySubmit = useHarnessStore((s) => s.busy.submit);
  const text = useHarnessStore((s) => s.draft.text);
  const graph = useHarnessStore((s) => s.graph);
  const focus = useHarnessStore((s) => s.focusNodeInGraph);
  const sessionId = useHarnessStore((s) => s.activeSessionId);

  const chunks = useMemo(() => {
    const m = new Map<number, ChunkEvaluation>();
    step.chunks.forEach((c) => m.set(c.chunk_index, c));
    if (chunkLog.stepId === step.step_id) chunkLog.items.forEach((c) => m.set(c.chunk_index, c));
    return [...m.values()].sort((a, b) => a.chunk_index - b.chunk_index);
  }, [step.chunks, step.step_id, chunkLog]);

  const pair = step.contrastive_pair_node_id ? graph?.nodes.find((n) => n.id === step.contrastive_pair_node_id) : undefined;
  const satisfied = chunks.some((c) => c.demand_satisfied);

  const finalSubmit = (): void => {
    const all = [...chunks.map((c) => c.text), text.trim()].filter(Boolean);
    void submitStep({
      raw_prediction_locked: chunks[0]?.text ?? text.trim(),
      verification_thinking: all.join('\n\n'),
    });
  };

  return (
    <div className="stream-card practice">
      <StepHeader step={step} />
      <div className="prompt cue-demand">
        <MathText text={step.prompt_latex} />
      </div>
      {pair ? (
        <div className="contrast-note">
          <span className="tag amber mono">⊥ CONTRASTIVE PAIR</span> Discriminate against{' '}
          <button className="link" onClick={() => focus(pair.id)}>
            {pair.title}
          </button>{' '}
          — state the condition that separates them.
        </div>
      ) : null}
      <StepMedia step={step} sessionId={sessionId} />

      <div className="chunk-stream">
        {chunks.length === 0 ? (
          <div className="dim small">
            Think out loud in small chunks. Each Shift+Enter is evaluated by the Bug-Library Diagnostician and Symbolic Verifier.
          </div>
        ) : null}
        {chunks.map((c) => (
          <ChunkCard key={c.chunk_index} c={c} />
        ))}
        {busyChunk ? (
          <div className="chunk pending">
            <Spinner /> evaluating chunk…
          </div>
        ) : null}
      </div>

      <HintLadder step={step} />

      <TelemetryInputDock
        label={`Thinking chunk ${chunks.length + 1}`}
        placeholder="Next chunk of raw thinking — what cue do you recognise, which move does it trigger? (Shift+Enter to submit chunk)"
        onShiftEnter={() => void submitChunk()}
        shiftEnterLabel="submit chunk"
        actions={[
          { label: 'Submit chunk', kind: 'ghost', onClick: () => void submitChunk(), disabled: !text.trim(), busy: busyChunk },
          {
            label: satisfied ? 'Submit final answer ✓' : 'Submit final answer',
            onClick: finalSubmit,
            disabled: chunks.length === 0 && !text.trim(),
            busy: busySubmit,
            title: 'POST /submit with every chunk as verification thinking',
          },
        ]}
      />
    </div>
  );
}
