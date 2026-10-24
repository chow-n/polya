"""Read a paper's LaTeX source into a structured document (docs/specs/paper-reading D2, FR3). Pure: no network, no DB.

`parse_source(dir)` finds the main file, inlines \\input/\\include, strips comments, expands zero-argument macros and
returns a `PaperDoc`: title, abstract, sections, theorem-like blocks (with \\newtheorem aliases and attached proofs),
labelled equations, every \\cite with its sentence and section, and the bibliography from .bbl or .bib files.
`parse_pdf_text(pages)` gives the same shape, more coarsely, for a PDF.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

MAX_INCLUDE_DEPTH = 8
TEXT_SUFFIXES = (".tex", ".ltx")
THEOREM_KINDS = ("theorem", "lemma", "proposition", "corollary", "definition", "assumption", "remark", "example",
                 "claim", "conjecture", "hypothesis", "condition", "fact", "property", "observation", "problem")
SECTION_RX = re.compile(r"\\(section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\s*\{")
CITE_RX = re.compile(r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|autocite|parencite|textcite|footcite)"
                     r"\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}")
ARXIV_ID_RX = re.compile(r"(?:arXiv[:\s]*|arxiv\.org/(?:abs|pdf)/|\babs/)(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})", re.I)
DOI_RX = re.compile(r"\b(10\.\d{4,9}/[^\s{}\\,]+[^\s{}\\,.;])")
YEAR_RX = re.compile(r"\b(1[6-9]\d\d|20[0-4]\d)\b")


@dataclass
class Section:
    id: str
    title: str
    level: int
    text: str


@dataclass
class Block:
    kind: str           # theorem, lemma, definition, assumption, … or "equation"
    title: str
    label: str
    body: str
    section: str
    proof: str = ""


@dataclass
class CiteContext:
    sentence: str
    section: str


@dataclass
class BibEntry:
    key: str
    title: str = ""
    authors: str = ""
    year: str = ""
    arxiv_id: str = ""
    doi: str = ""
    raw: str = ""


@dataclass
class PaperDoc:
    title: str = ""
    abstract: str = ""
    sections: list[Section] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    citations: dict[str, list[CiteContext]] = field(default_factory=dict)
    bib: dict[str, BibEntry] = field(default_factory=dict)
    text_kind: str = "latex"     # latex | pdf_text

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "PaperDoc":
        return cls(title=d.get("title", ""), abstract=d.get("abstract", ""),
                   sections=[Section(**s) for s in d.get("sections", [])],
                   blocks=[Block(**b) for b in d.get("blocks", [])],
                   citations={k: [CiteContext(**c) for c in v] for k, v in d.get("citations", {}).items()},
                   bib={k: BibEntry(**v) for k, v in d.get("bib", {}).items()}, text_kind=d.get("text_kind", "latex"))

    def full_text(self) -> str:
        return "\n\n".join([self.abstract] + [f"{s.title}\n{s.text}" for s in self.sections])

    def section_titles(self) -> list[str]:
        return [s.title for s in self.sections]


# ------------------------------------------------------------------ low-level LaTeX helpers
def balanced(s: str, i: int, open_: str = "{", close: str = "}") -> tuple[str, int]:
    """s[i] == open_: return (contents, index just past the matching close). Unbalanced → rest of string."""
    depth, j = 0, i
    while j < len(s):
        ch = s[j]
        if ch == "\\":
            j += 2
            continue
        if ch == open_:
            depth += 1
        elif ch == close:
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def strip_comments(s: str) -> str:
    return re.sub(r"(?<!\\)%[^\n]*", "", s)


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\n":
        i += 1
    return i


def collect_macros(s: str) -> dict[str, str]:
    """Zero-argument \\newcommand / \\renewcommand / \\def / \\DeclareMathOperator definitions."""
    out: dict[str, str] = {}
    for m in re.finditer(r"\\(?:re)?newcommand\*?\s*\{?\s*(\\[A-Za-z]+)\s*\}?", s):
        i = _skip_ws(s, m.end())
        if i < len(s) and s[i] == "[":
            continue   # takes arguments: left alone
        if i < len(s) and s[i] == "{":
            out[m.group(1)] = balanced(s, i)[0]
    for m in re.finditer(r"\\def\s*(\\[A-Za-z]+)\s*\{", s):
        out[m.group(1)] = balanced(s, m.end() - 1)[0]
    for m in re.finditer(r"\\DeclareMathOperator\*?\s*\{\s*(\\[A-Za-z]+)\s*\}\s*\{", s):
        out[m.group(1)] = r"\operatorname{" + balanced(s, m.end() - 1)[0] + "}"
    return {k: v for k, v in out.items() if k not in ("\\section", "\\begin", "\\end", "\\cite", "\\label")}


def expand_macros(s: str, macros: dict[str, str], passes: int = 3) -> str:
    if not macros:
        return s
    rx = re.compile(r"(\\(?:" + "|".join(re.escape(k[1:]) for k in sorted(macros, key=len, reverse=True)) + r"))(?![A-Za-z])")
    for _ in range(passes):
        new = rx.sub(lambda m: macros[m.group(1)], s)
        if new == s:
            break
        s = new
    return s


ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "c": "\u0327", "=": "\u0304"}


def accents(s: str) -> str:
    """\\'e, \\'{e}, \\"{o}, \\c{c} … → é, ö, ç (outside math these are text accents)."""
    def sub(m: re.Match) -> str:
        return unicodedata.normalize("NFC", m.group(2) + ACCENTS[m.group(1)])
    return re.sub(r"\\(['`^\"~=]|c(?=\{))\{?([A-Za-z])\}?", sub, s)


def plain(s: str) -> str:
    """Readable text for quotes and prompts: math kept, markup and references dropped."""
    s = accents(s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:eq)?ref\{[^}]*\}", "(ref)", s)
    s = re.sub(r"\\(?:emph|textbf|textit|textsc|texttt|underline|mbox|text)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:footnote|thanks)\{[^{}]*\}", "", s)
    s = re.sub(r"\\(?:url|href)\{([^}]*)\}(?:\{([^}]*)\})?", lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"\\(?:vspace|hspace|vskip|hskip)\*?\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:noindent|centering|small|footnotesize|newline|par|medskip|bigskip|smallskip)\b", " ", s)
    s = s.replace("~", " ").replace("``", '"').replace("''", '"')
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", s)).strip()


def cite_to_text(s: str) -> str:
    return CITE_RX.sub(lambda m: "[" + ", ".join(k.strip() for k in m.group(1).split(",")) + "]", s)


# ------------------------------------------------------------------ files
def find_main(root: Path) -> Optional[Path]:
    cands = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
            t = p.read_text(errors="replace")
            if "\\begin{document}" in t:
                cands.append((("\\documentclass" in t), len(t), p))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return cands[0][2]


def inline_inputs(text: str, root: Path, depth: int = 0) -> str:
    if depth > MAX_INCLUDE_DEPTH:
        return text

    def sub(m: re.Match) -> str:
        name = m.group(2).strip()
        for cand in (name, name + ".tex"):
            p = (root / cand).resolve()
            if str(p).startswith(str(root.resolve())) and p.is_file():
                return inline_inputs(strip_comments(p.read_text(errors="replace")), root, depth + 1)
        return ""
    return re.sub(r"\\(input|include|subfile)\s*\{([^}]+)\}", sub, text)


# ------------------------------------------------------------------ bibliography
def _bbl_title(raw: str) -> tuple[str, str]:
    """natbib/plain .bbl: 'Authors.\\n\\newblock Title.\\n\\newblock Venue' → (authors, title)."""
    parts = [p.strip() for p in re.split(r"\\newblock", raw)]
    authors = " ".join(plain(parts[0]).split()).rstrip(".") if parts else ""
    title = " ".join(plain(parts[1]).split()).rstrip(".") if len(parts) > 1 else ""
    title = re.sub(r"[{}]", "", title)
    return authors, title


def parse_bbl(text: str) -> dict[str, BibEntry]:
    out: dict[str, BibEntry] = {}
    if "\\entry{" in text:   # biblatex
        for m in re.finditer(r"\\entry\{([^}]*)\}\{[^}]*\}\{[^}]*\}(.*?)\\endentry", text, re.S):
            key, body = m.group(1), m.group(2)

            def field_(name: str) -> str:
                f = re.search(r"\\field\{" + name + r"\}\{", body)
                return plain(balanced(body, f.end() - 1)[0]) if f else ""
            fam = re.findall(r"family=\{([^}]*)\}", body)
            out[key] = BibEntry(key=key, title=re.sub(r"[{}]", "", field_("title")), authors=", ".join(fam[:4]),
                                year=field_("year") or (YEAR_RX.search(body).group(1) if YEAR_RX.search(body) else ""),
                                arxiv_id=field_("eprint") if "arxiv" in body.lower() else "",
                                doi=(re.search(r"\\verb\{doi\}\s*\\verb (\S+)", body) or [None, ""])[1] if "doi" in body else "",
                                raw=plain(body)[:500])
        return out
    items = list(re.finditer(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", text))
    for i, m in enumerate(items):
        end = items[i + 1].start() if i + 1 < len(items) else text.find("\\end{thebibliography}", m.end())
        raw = text[m.end():end if end > 0 else None]
        authors, title = _bbl_title(raw)
        ax = ARXIV_ID_RX.search(raw)
        doi = DOI_RX.search(raw)
        yr = YEAR_RX.search(raw)
        out[m.group(1).strip()] = BibEntry(key=m.group(1).strip(), title=title, authors=authors,
                                           year=yr.group(1) if yr else "", arxiv_id=ax.group(1) if ax else "",
                                           doi=doi.group(1) if doi else "", raw=plain(raw)[:500])
    return out


def parse_bib(text: str) -> dict[str, BibEntry]:
    out: dict[str, BibEntry] = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        if m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        start = text.rfind("{", m.start(), m.end())
        body = balanced(text, start)[0]
        fields: dict[str, str] = {}
        for f in re.finditer(r"(\w+)\s*=\s*", body):
            j = f.end()
            if j < len(body) and body[j] == "{":
                val = balanced(body, j)[0]
            elif j < len(body) and body[j] == '"':
                k = body.find('"', j + 1)
                val = body[j + 1:k if k > 0 else None]
            else:
                val = re.match(r"[^,\n]*", body[j:]).group(0)
            fields.setdefault(f.group(1).lower(), val.strip())
        key = m.group(2)
        eprint = fields.get("eprint", "")
        ax = ARXIV_ID_RX.search(" ".join(fields.values())) or (re.match(r"\d{4}\.\d{4,5}", eprint) and re.match(r"(\d{4}\.\d{4,5})", eprint))
        out[key] = BibEntry(key=key, title=plain(re.sub(r"[{}]", "", fields.get("title", ""))),
                            authors=plain(fields.get("author", "")).replace(" and ", ", "), year=fields.get("year", ""),
                            arxiv_id=ax.group(1) if ax else "", doi=fields.get("doi", ""), raw="")
    return out


# ------------------------------------------------------------------ document structure
def _sections(body: str) -> list[tuple[int, str, int, int]]:
    """[(level, title, start_of_text, end_of_text)] over the body."""
    heads = []
    for m in SECTION_RX.finditer(body):
        title, end = balanced(body, m.end() - 1)
        heads.append(({"section": 1, "subsection": 2, "subsubsection": 3}[m.group(1)], plain(title), m.start(), end))
    out = []
    for i, (lvl, title, start, end) in enumerate(heads):
        nxt = heads[i + 1][2] if i + 1 < len(heads) else len(body)
        out.append((lvl, title, end, nxt))
    return out


def _theorem_aliases(preamble: str) -> dict[str, str]:
    """\\newtheorem{thm}{Theorem} → {"thm": "theorem"}; unknown display names keep their own first word."""
    out = {k: k for k in THEOREM_KINDS}
    for m in re.finditer(r"\\(?:newtheorem|declaretheorem)\*?\s*\{([^}]*)\}\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", preamble):
        disp = m.group(2).strip().lower().split()[0] if m.group(2).strip() else m.group(1)
        out[m.group(1).strip()] = disp if disp in THEOREM_KINDS else disp
    return out


def _sentence_around(text: str, i: int, j: int) -> str:
    left = max(text.rfind(". ", 0, i), text.rfind("\n\n", 0, i), text.rfind(".\n", 0, i))
    right_c = [k for k in (text.find(". ", j), text.find(".\n", j), text.find("\n\n", j)) if k >= 0]
    right = min(right_c) + 1 if right_c else len(text)
    return plain(cite_to_text(text[left + 1 if left >= 0 else 0:right]))[:600]


def parse_document(src: str, bib: dict[str, BibEntry] | None = None) -> PaperDoc:
    src = strip_comments(src)
    macros = collect_macros(src)
    b, e = src.find("\\begin{document}"), src.find("\\end{document}")
    preamble = src[:b] if b >= 0 else ""
    body = src[b + len("\\begin{document}"):e if e > b else None] if b >= 0 else src
    body = expand_macros(body, macros)
    body = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", "", body, flags=re.S)
    body = re.sub(r"\\bibliography\{[^}]*\}|\\printbibliography(?:\[[^\]]*\])?", "", body)
    doc = PaperDoc(bib=dict(bib or {}))
    t = re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{", src)
    if t:
        doc.title = plain(re.sub(r"\\\\", " ", balanced(src, t.end() - 1)[0]))
    a = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
    if a:
        doc.abstract = plain(cite_to_text(a.group(1)))
    elif (a2 := re.search(r"\\abstract\s*\{", body)):
        doc.abstract = plain(balanced(body, a2.end() - 1)[0])

    secs = _sections(body)
    for k, (lvl, title, start, end) in enumerate(secs):
        text = body[start:end]
        doc.sections.append(Section(id=f"s{k + 1}", title=title, level=lvl, text=plain(cite_to_text(text))[:20000]))

    def section_at(pos: int) -> str:
        cur = ""
        for lvl, title, start, _ in secs:
            if start <= pos and lvl == 1:
                cur = title
            elif start <= pos:
                cur = f"{cur.split(' › ')[0]} › {title}" if cur else title
        return cur or "Preamble"

    aliases = _theorem_aliases(preamble + body[:2000])
    placed: list[tuple[int, Block]] = []
    env_rx = re.compile(r"\\begin\{(" + "|".join(re.escape(k) for k in sorted(aliases, key=len, reverse=True)) +
                        r")\*?\}(\[[^\]]*\])?(.*?)\\end\{\1\*?\}", re.S)
    for m in env_rx.finditer(body):
        inner = m.group(3)
        lab = re.search(r"\\label\{([^}]*)\}", inner)
        blk = Block(kind=aliases[m.group(1)], title=plain((m.group(2) or "")[1:-1]), label=lab.group(1) if lab else "",
                    body=plain(cite_to_text(inner))[:3000], section=section_at(m.start()))
        pr = re.match(r"\s*\\begin\{proof\}(\[[^\]]*\])?(.*?)\\end\{proof\}", body[m.end():m.end() + 20000], re.S)
        if pr:
            blk.proof = plain(cite_to_text(pr.group(2)))[:4000]
        placed.append((m.start(), blk))
    for m in re.finditer(r"\\begin\{(equation|align|gather|multline)\*?\}(.*?)\\end\{\1\*?\}", body, re.S):
        lab = re.search(r"\\label\{([^}]*)\}", m.group(2))
        if lab:
            placed.append((m.start(), Block(kind="equation", title="", label=lab.group(1), body=plain(m.group(2))[:1500],
                                            section=section_at(m.start()))))
    doc.blocks = [blk for _, blk in sorted(placed, key=lambda x: x[0])]

    for m in CITE_RX.finditer(body):
        ctx = CiteContext(sentence=_sentence_around(body, m.start(), m.end()), section=section_at(m.start()))
        for key in (k.strip() for k in m.group(1).split(",")):
            if key and len(doc.citations.setdefault(key, [])) < 8:
                doc.citations[key].append(ctx)
    return doc


def parse_source(root: Path) -> Optional[PaperDoc]:
    """Parse an extracted arXiv source tree. None when no main .tex file exists."""
    main = find_main(root)
    if not main:
        return None
    src = inline_inputs(strip_comments(main.read_text(errors="replace")), main.parent)
    bib: dict[str, BibEntry] = {}
    for p in sorted(root.rglob("*.bbl")):
        bib.update(parse_bbl(p.read_text(errors="replace")))
    if not bib:
        inline_bbl = re.search(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", src, re.S)
        if inline_bbl:
            bib.update(parse_bbl(inline_bbl.group(0)))
    if not bib:
        for p in sorted(root.rglob("*.bib")):
            bib.update(parse_bib(p.read_text(errors="replace")))
    return parse_document(src, bib)


# ------------------------------------------------------------------ PDF text
def parse_pdf_text(pages: list[str]) -> PaperDoc:
    """Coarse structure from PDF page text: title (first line), abstract heuristic, one section per page,
    and a reference list when a References heading exists."""
    doc = PaperDoc(text_kind="pdf_text")
    first = pages[0] if pages else ""
    lines = [ln.strip() for ln in first.splitlines() if ln.strip()]
    doc.title = lines[0][:200] if lines else ""
    allt = "\n".join(pages)
    starts = [0]
    for p in pages:
        starts.append(starts[-1] + len(p) + 1)
    m = re.search(r"\bAbstract\b[\s.:—-]*(.*?)(?:\n\s*(?:1\.?\s+)?Introduction\b|\n\s*Keywords)", allt, re.S | re.I)
    if m:
        doc.abstract = " ".join(m.group(1).split())[:3000]
    for i, p in enumerate(pages):
        doc.sections.append(Section(id=f"p{i + 1}", title=f"Page {i + 1}", level=1, text=" ".join(p.split())[:20000]))
    refs = re.split(r"\n\s*(?:References|Bibliography|REFERENCES)\s*\n", allt)
    if len(refs) > 1:
        chunk = refs[-1][:60000]
        items = re.split(r"\n\s*\[(\d+)\]\s*", "\n" + chunk)
        if len(items) > 3:
            for k in range(1, len(items) - 1, 2):
                raw = " ".join(items[k + 1].split())
                ax = ARXIV_ID_RX.search(raw)
                yr = YEAR_RX.search(raw)
                doc.bib[items[k]] = BibEntry(key=items[k], title=_pdf_ref_title(raw), year=yr.group(1) if yr else "",
                                             arxiv_id=ax.group(1) if ax else "", raw=raw[:500])
    for m in re.finditer(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]", allt[:len(refs[0])]):
        for key in re.split(r"\s*,\s*", m.group(1)):
            if key in doc.bib and len(doc.citations.setdefault(key, [])) < 8:
                pg = max(i for i, st in enumerate(starts[:-1]) if st <= m.start())
                doc.citations[key].append(CiteContext(sentence=_sentence_around(allt, m.start(), m.end()), section=f"Page {pg + 1}"))
    return doc


def _pdf_ref_title(raw: str) -> str:
    """'A. Author, B. Author. Title of paper. In Venue, 2020.' → the second sentence, roughly."""
    parts = [p.strip() for p in re.split(r"(?<=[a-z0-9\)])\.\s+", raw) if p.strip()]
    return parts[1][:250] if len(parts) > 1 else raw[:200]
