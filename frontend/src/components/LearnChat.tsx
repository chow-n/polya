/**
 * Learning chat (docs/specs/learn-chat): ideas you have never studied are taught as a conversation before any recall.
 * Pólya opens with "what do you already know?", then explains idea by idea (sourced, cited [n]) and ends each turn with
 * one small question. Your answers move each idea's predicted recall; at ≥ 70 % (or after 4 exchanges) it moves on.
 * When every idea is covered, Start recall submits the step and recall begins with the idea learned first.
 */
import { useHarnessStore } from '../store/useHarnessStore';
import type { LearnIdea, StepPayload } from '../types/harness';
import { MathText } from '../utils/katexRenderer';
import { ChatMessages, Composer, SourcesList } from './ChatThread';
import { Details, PrimaryButton, usePrimaryAction } from './kit';
import { CardHead, StepDetails } from './stepParts';

const STATUS_WORD: Record<LearnIdea['status'], string> = {
  todo: 'coming up',
  current: 'now',
  covered: 'ready to recall',
  moved_on: 'moved on; recall will check it',
};

function IdeaChips({ ideas }: { ideas: LearnIdea[] }): JSX.Element {
  return (
    <ol className="idea-chips" aria-label="Ideas in this conversation">
      {ideas.map((i) => (
        <li
          key={i.node_id}
          className={`idea-chip ${i.status}`}
          title={`${i.title}: ${STATUS_WORD[i.status]} · ready to recall: ${Math.round(i.p_recall * 100)}%`}
        >
          <span className="idea-fill" style={{ width: `${Math.round(Math.min(1, i.p_recall / 0.7) * 100)}%` }} aria-hidden="true" />
          <span className="idea-name">{i.title}</span>
        </li>
      ))}
    </ol>
  );
}

export default function LearnChat({ step }: { step: StepPayload }): JSX.Element {
  const chat = useHarnessStore((s) => s.chat);
  const writing = useHarnessStore((s) => Boolean(s.busy.learn));
  const submitting = useHarnessStore((s) => Boolean(s.busy.submit));
  const learnAction = useHarnessStore((s) => s.learnAction);
  const submitStep = useHarnessStore((s) => s.submitStep);
  const ideas = step.learn_ideas;
  const ready = ideas.length > 0 && ideas.every((i) => i.status === 'covered' || i.status === 'moved_on');
  const messages = chat.thread.filter((m) => m.step_index === step.step_index);
  const opened = messages.some((m) => m.role === 'polya');
  const start = (): void => void submitStep({});
  usePrimaryAction(start, ready && !submitting);

  const send = (text: string): void => {
    if (!opened) void learnAction('OPEN_REPLY', text);
    else void learnAction(text.trim().endsWith('?') ? 'ASK' : 'REPLY', text);
  };

  return (
    <article className="card learn-card">
      <CardHead step={step} />
      <IdeaChips ideas={ideas} />
      <div className="learn-thread" aria-live="polite">
        <div className="msg polya">
          <MathText text={step.prompt_latex} className="msg-body" />
        </div>
        <ChatMessages messages={messages} pending={chat.pending} writing={writing} showSayBack={false} />
      </div>
      {ready ? (
        <div className="actions">
          <PrimaryButton onClick={start} busy={submitting} busyLabel="Preparing recall…">
            Start recall
          </PrimaryButton>
          <button className="text-btn" disabled={writing} onClick={() => void learnAction('ASK', 'Can you sum up the main idea once more?')}>
            One more question first
          </button>
        </div>
      ) : (
        <>
          <Composer
            onSend={send}
            disabled={writing}
            placeholder={opened ? 'Answer, or ask anything (end with ?)…' : 'What you already know (optional)…'}
            autoFocus
          />
          <div className="row learn-btns">
            {opened ? (
              <>
                <button className="btn-secondary" disabled={writing} onClick={() => void learnAction('GO_ON')}>
                  Go on
                </button>
                <button className="text-btn" disabled={writing} onClick={() => void learnAction('QUIZ_ME')}>
                  Quiz me now
                </button>
              </>
            ) : (
              <button className="btn-secondary" disabled={writing} onClick={() => void learnAction('SKIP')}>
                Skip, just start
              </button>
            )}
          </div>
        </>
      )}
      <SourcesList sources={chat.sources} />
      <Details>
        <StepDetails step={step} />
      </Details>
    </article>
  );
}
