/**
 * Fast KaTeX renderer for mixed markdown-ish text (ARCHITECTURE_SPEC §1, §6).
 *
 *  - Math: $...$, $$...$$, \(...\), \[...\]  (escaped \$ is literal)
 *  - Markdown (deliberately minimal): paragraphs, **bold**, *italic* / _italic_, `code`, "- " / "1. " lists, "#" headings
 *  - Macros: \R \E \Var \Cov \N \P \1 \norm{.}   throwOnError: false (bad TeX renders red, never crashes)
 *  - Optional sentence anchoring + clickable math for ReadingStreamBox.
 */
import katex from 'katex';
import { Fragment, memo, useMemo, type ReactNode } from 'react';

export const KATEX_MACROS: Record<string, string> = {
  '\\R': '\\mathbb{R}',
  '\\E': '\\mathbb{E}',
  '\\Var': '\\operatorname{Var}',
  '\\Cov': '\\operatorname{Cov}',
  '\\N': '\\mathcal{N}',
  '\\P': '\\mathbb{P}',
  '\\1': '\\mathbf{1}',
  '\\norm': '\\left\\lVert #1 \\right\\rVert',
};

const cache = new Map<string, string>();
const CACHE_LIMIT = 3000;

/** Render a TeX string to HTML (memoised). Never throws. */
export function renderTex(tex: string, displayMode = false): string {
  const key = `${displayMode ? 'D' : 'I'}::${tex}`;
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  let html: string;
  try {
    html = katex.renderToString(tex, {
      displayMode,
      throwOnError: false,
      strict: 'ignore',
      trust: false,
      output: 'html',
      macros: { ...KATEX_MACROS },
    });
  } catch (e) {
    html = `<span class="katex-error" title="${escapeHtml(e instanceof Error ? e.message : String(e))}">${escapeHtml(tex)}</span>`;
  }
  if (cache.size > CACHE_LIMIT) cache.clear();
  cache.set(key, html);
  return html;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c);
}

// ------------------------------------------------------------------ tokeniser
export type Seg = { kind: 'text'; text: string } | { kind: 'math'; tex: string; display: boolean };

/** Split source into text and math segments. */
export function splitMath(src: string): Seg[] {
  const out: Seg[] = [];
  let buf = '';
  let i = 0;
  const n = src.length;
  const pushText = (): void => {
    if (buf) out.push({ kind: 'text', text: buf });
    buf = '';
  };
  while (i < n) {
    const c = src[i];
    if (c === '\\' && i + 1 < n) {
      const nx = src[i + 1];
      if (nx === '$') {
        buf += '$';
        i += 2;
        continue;
      }
      if (nx === '[' || nx === '(') {
        const close = nx === '[' ? '\\]' : '\\)';
        const end = src.indexOf(close, i + 2);
        if (end !== -1) {
          pushText();
          out.push({ kind: 'math', tex: src.slice(i + 2, end), display: nx === '[' });
          i = end + 2;
          continue;
        }
      }
      buf += c;
      i += 1;
      continue;
    }
    if (c === '$') {
      if (src[i + 1] === '$') {
        const end = src.indexOf('$$', i + 2);
        if (end !== -1) {
          pushText();
          out.push({ kind: 'math', tex: src.slice(i + 2, end), display: true });
          i = end + 2;
          continue;
        }
      } else {
        // inline $...$ : closing $ not preceded by backslash, same paragraph
        let j = i + 1;
        let found = -1;
        while (j < n) {
          if (src[j] === '\\') {
            j += 2;
            continue;
          }
          if (src[j] === '$') {
            found = j;
            break;
          }
          if (src[j] === '\n' && src[j + 1] === '\n') break;
          j += 1;
        }
        if (found > i + 1) {
          pushText();
          out.push({ kind: 'math', tex: src.slice(i + 1, found), display: false });
          i = found + 1;
          continue;
        }
      }
    }
    buf += c;
    i += 1;
  }
  pushText();
  return out;
}

export function hasMathDelimiters(s: string): boolean {
  return /\$|\\\(|\\\[/.test(s);
}

/**
 * `*_latex` fields are sometimes pure TeX without delimiters. Treat a delimiter-free string as math when it
 * contains TeX commands / scripts and does not read like prose (no run of 4+ plain words).
 */
export function looksLikeBareTex(s: string): boolean {
  if (!s.trim() || hasMathDelimiters(s)) return false;
  if (!/\\[a-zA-Z]+|[\^_]\{|[\^_][a-zA-Z0-9]/.test(s)) return false;
  const stripped = s.replace(/\\(text|mathrm|operatorname|textbf|emph)\{[^}]*\}/g, ' ').replace(/\\[a-zA-Z]+/g, ' ');
  return !/[A-Za-z]{2,}\s+[A-Za-z]{2,}\s+[A-Za-z]{2,}\s+[A-Za-z]{2,}/.test(stripped);
}

// ------------------------------------------------------------------ inline markdown
interface FmtState {
  bold: boolean;
  italic: boolean;
}

function renderInlineText(text: string, st: FmtState, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let buf = '';
  let k = 0;
  const flush = (): void => {
    if (!buf) return;
    let node: ReactNode = buf;
    if (st.italic) node = <em key={`${keyBase}-i${k}`}>{node}</em>;
    if (st.bold) node = <strong key={`${keyBase}-b${k}`}>{node}</strong>;
    nodes.push(<Fragment key={`${keyBase}-t${k++}`}>{node}</Fragment>);
    buf = '';
  };
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === '`') {
      const end = text.indexOf('`', i + 1);
      if (end > i) {
        flush();
        nodes.push(
          <code key={`${keyBase}-c${k++}`} className="md-code">
            {text.slice(i + 1, end)}
          </code>,
        );
        i = end + 1;
        continue;
      }
    }
    if (c === '*' && text[i + 1] === '*') {
      flush();
      st.bold = !st.bold;
      i += 2;
      continue;
    }
    if (c === '*' || c === '_') {
      const prev = i > 0 ? text[i - 1] : ' ';
      const next = i + 1 < text.length ? text[i + 1] : ' ';
      const opening = !st.italic && /\S/.test(next) && (c === '*' ? !/[A-Za-z0-9*]/.test(prev) : /[\s(]/.test(prev));
      const closing = st.italic && /\S/.test(prev) && (c === '*' || /[\s.,;:!?)]/.test(next));
      if (opening || closing) {
        flush();
        st.italic = !st.italic;
        i += 1;
        continue;
      }
    }
    buf += c;
    i += 1;
  }
  flush();
  return nodes;
}

// ------------------------------------------------------------------ block structure
type Line = Seg[];
type Block =
  | { kind: 'para'; lines: Line[] }
  | { kind: 'list'; ordered: boolean; items: Line[] }
  | { kind: 'heading'; level: number; line: Line }
  | { kind: 'display'; tex: string };

function segsToLines(segs: Seg[]): Line[] {
  const lines: Line[] = [[]];
  for (const s of segs) {
    if (s.kind === 'math') {
      lines[lines.length - 1].push(s);
      continue;
    }
    const parts = s.text.split('\n');
    parts.forEach((p, idx) => {
      if (idx > 0) lines.push([]);
      if (p) lines[lines.length - 1].push({ kind: 'text', text: p });
    });
  }
  return lines;
}

const BULLET_RE = /^\s*([-*•])\s+/;
const ORDERED_RE = /^\s*(\d+)[.)]\s+/;
const HEADING_RE = /^\s*(#{1,4})\s+/;

function stripLead(line: Line, re: RegExp): Line {
  const first = line[0];
  if (!first || first.kind !== 'text') return line;
  return [{ kind: 'text', text: first.text.replace(re, '') }, ...line.slice(1)];
}

function lineLead(line: Line): string {
  const first = line[0];
  return first && first.kind === 'text' ? first.text : '';
}

function isBlankLine(line: Line): boolean {
  return line.every((s) => s.kind === 'text' && !s.text.trim());
}

export function parseBlocks(src: string): Block[] {
  const segs = splitMath(src.replace(/\r\n/g, '\n'));
  const blocks: Block[] = [];
  let pending: Seg[] = [];
  const flushPending = (): void => {
    if (!pending.length) return;
    const lines = segsToLines(pending);
    pending = [];
    let para: Line[] = [];
    let list: { ordered: boolean; items: Line[] } | null = null;
    const endPara = (): void => {
      if (para.length) blocks.push({ kind: 'para', lines: para });
      para = [];
    };
    const endList = (): void => {
      if (list) blocks.push({ kind: 'list', ordered: list.ordered, items: list.items });
      list = null;
    };
    for (const line of lines) {
      if (isBlankLine(line)) {
        endPara();
        endList();
        continue;
      }
      const lead = lineLead(line);
      const h = HEADING_RE.exec(lead);
      if (h) {
        endPara();
        endList();
        blocks.push({ kind: 'heading', level: h[1].length, line: stripLead(line, HEADING_RE) });
        continue;
      }
      const isBullet = BULLET_RE.test(lead) && !/^\s*\*\*/.test(lead);
      const isOrdered = ORDERED_RE.test(lead);
      if (isBullet || isOrdered) {
        endPara();
        const ordered = !isBullet;
        if (list && list.ordered !== ordered) endList();
        if (!list) list = { ordered, items: [] };
        list.items.push(stripLead(line, ordered ? ORDERED_RE : BULLET_RE));
        continue;
      }
      if (list) {
        // continuation line of the last list item
        const items: Line[] = (list as { items: Line[] }).items;
        items[items.length - 1] = [...items[items.length - 1], { kind: 'text', text: ' ' }, ...line];
        continue;
      }
      para.push(line);
    }
    endPara();
    endList();
  };
  for (const s of segs) {
    if (s.kind === 'math' && s.display) {
      flushPending();
      blocks.push({ kind: 'display', tex: s.tex });
    } else pending.push(s);
  }
  flushPending();
  return blocks;
}

// ------------------------------------------------------------------ React components
export interface MathTextProps {
  text: string;
  className?: string;
  /** Render as a single inline run (no <p>/<ul> wrappers). */
  inline?: boolean;
  /** Treat delimiter-free TeX-looking strings as math (for *_latex fields). */
  latexField?: boolean;
  /** Wrap each sentence in a clickable span (ReadingStreamBox anchoring). */
  onSentenceClick?: (sentence: string) => void;
  highlighted?: Set<string>;
  /** Make math clickable (equation anchoring). */
  onMathClick?: (tex: string, display: boolean) => void;
}

function MathSpan({
  tex,
  display,
  onClick,
  highlighted,
}: {
  tex: string;
  display: boolean;
  onClick?: (tex: string, display: boolean) => void;
  highlighted?: boolean;
}): JSX.Element {
  const html = renderTex(tex, display);
  const cls = `${display ? 'math-display' : 'math-inline'}${onClick ? ' math-clickable' : ''}${highlighted ? ' anchored' : ''}`;
  if (display) {
    return (
      <div
        className={cls}
        onClick={onClick ? () => onClick(tex, true) : undefined}
        title={onClick ? 'Click to anchor a thinking-while-reading note to this equation' : undefined}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }
  return (
    <span
      className={cls}
      onClick={
        onClick
          ? (e) => {
              e.stopPropagation();
              onClick(tex, false);
            }
          : undefined
      }
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function segPlain(s: Seg): string {
  return s.kind === 'text' ? s.text : `$${s.tex}$`;
}

/** Group a line's segments into sentences, splitting text at [.!?] followed by whitespace. */
function sentenceGroups(line: Line): Seg[][] {
  const groups: Seg[][] = [[]];
  for (const s of line) {
    if (s.kind === 'math') {
      groups[groups.length - 1].push(s);
      continue;
    }
    const parts = s.text.split(/(?<=[.!?])\s+/);
    parts.forEach((p, idx) => {
      if (idx > 0) groups.push([]);
      if (p) groups[groups.length - 1].push({ kind: 'text', text: idx < parts.length - 1 ? `${p} ` : p });
    });
  }
  return groups.filter((g) => g.some((s) => s.kind === 'math' || s.text.trim()));
}

export function sentencePlain(group: Seg[]): string {
  return group.map(segPlain).join('').trim();
}

function renderLine(line: Line, props: MathTextProps, st: FmtState, keyBase: string): ReactNode[] {
  const renderSegs = (segs: Seg[], kb: string): ReactNode[] =>
    segs.map((s, i) =>
      s.kind === 'math' ? (
        <MathSpan
          key={`${kb}-m${i}`}
          tex={s.tex}
          display={false}
          onClick={props.onMathClick}
          highlighted={props.highlighted?.has(`$${s.tex}$`)}
        />
      ) : (
        <Fragment key={`${kb}-s${i}`}>{renderInlineText(s.text, st, `${kb}-s${i}`)}</Fragment>
      ),
    );
  if (!props.onSentenceClick) return renderSegs(line, keyBase);
  const click = props.onSentenceClick;
  return sentenceGroups(line).map((g, gi) => {
    const plain = sentencePlain(g);
    const hl = props.highlighted?.has(plain);
    return (
      <span
        key={`${keyBase}-g${gi}`}
        className={`sentence${hl ? ' anchored' : ''}`}
        onClick={(e) => {
          const sel = window.getSelection();
          if (sel && sel.toString().trim().length > 0) return; // a drag-selection is handled by the container
          e.stopPropagation();
          click(plain);
        }}
      >
        {renderSegs(g, `${keyBase}-g${gi}`)}{' '}
      </span>
    );
  });
}

function MathTextImpl(props: MathTextProps): JSX.Element {
  const { text, className, inline, latexField } = props;
  const blocks = useMemo(() => {
    if (latexField && looksLikeBareTex(text)) {
      return [{ kind: 'display', tex: text } as Block];
    }
    return parseBlocks(text ?? '');
  }, [text, latexField]);

  const st: FmtState = { bold: false, italic: false };

  if (inline) {
    const nodes: ReactNode[] = [];
    blocks.forEach((b, bi) => {
      if (bi > 0) nodes.push(' ');
      if (b.kind === 'display') {
        nodes.push(<MathSpan key={`d${bi}`} tex={b.tex} display={false} onClick={props.onMathClick} />);
      } else if (b.kind === 'para') {
        b.lines.forEach((l, li) => {
          if (li > 0) nodes.push(' ');
          nodes.push(<Fragment key={`p${bi}-${li}`}>{renderLine(l, props, st, `p${bi}-${li}`)}</Fragment>);
        });
      } else if (b.kind === 'heading') {
        nodes.push(<strong key={`h${bi}`}>{renderLine(b.line, props, st, `h${bi}`)}</strong>);
      } else {
        b.items.forEach((it, ii) => {
          nodes.push(<Fragment key={`l${bi}-${ii}`}>{ii > 0 ? ' · ' : ''}{renderLine(it, props, st, `l${bi}-${ii}`)}</Fragment>);
        });
      }
    });
    return <span className={`mathtext inline ${className ?? ''}`}>{nodes}</span>;
  }

  return (
    <div className={`mathtext ${className ?? ''}`}>
      {blocks.map((b, bi) => {
        switch (b.kind) {
          case 'display':
            return (
              <MathSpan
                key={bi}
                tex={b.tex}
                display
                onClick={props.onMathClick}
                highlighted={props.highlighted?.has(`$$${b.tex}$$`)}
              />
            );
          case 'heading':
            return (
              <div key={bi} className={`md-h md-h${b.level}`}>
                {renderLine(b.line, props, st, `h${bi}`)}
              </div>
            );
          case 'list': {
            const items = b.items.map((it, ii) => <li key={ii}>{renderLine(it, props, st, `l${bi}-${ii}`)}</li>);
            return b.ordered ? <ol key={bi}>{items}</ol> : <ul key={bi}>{items}</ul>;
          }
          default:
            return (
              <p key={bi}>
                {b.lines.map((l, li) => (
                  <Fragment key={li}>
                    {li > 0 ? ' ' : null}
                    {renderLine(l, props, st, `p${bi}-${li}`)}
                  </Fragment>
                ))}
              </p>
            );
        }
      })}
    </div>
  );
}

export const MathText = memo(MathTextImpl);

/** Pure TeX (no markdown parsing). */
export function Tex({ tex, display = false, className }: { tex: string; display?: boolean; className?: string }): JSX.Element {
  const html = useMemo(() => renderTex(tex, display), [tex, display]);
  const Tag = display ? 'div' : 'span';
  return <Tag className={`${display ? 'math-display' : 'math-inline'} ${className ?? ''}`} dangerouslySetInnerHTML={{ __html: html }} />;
}
