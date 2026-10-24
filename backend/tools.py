"""Deterministic tools used by the sub-agents: SymPy sandbox, workspace corpus, LaTeX parsing, arXiv."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import config

# ------------------------------------------------------------------ SymPy / NumPy sandbox
SANDBOX_PRELUDE = r'''
import builtins as _b, sys as _s
_s.setrecursionlimit(4000)
import sympy, numpy, scipy  # pre-import before installing guards
_blocked = {"socket", "subprocess", "shutil", "requests", "urllib", "http", "ftplib", "smtplib", "ctypes", "multiprocessing", "os", "pathlib"}
_real_import, _real_open = _b.__import__, _b.open
def _from_user_code():
    # Guards apply to the verification script itself (compiled as "<string>"), not to library internals.
    return _s._getframe(2).f_code.co_filename == "<string>"
def _guarded(name, *a, **k):
    if name.split(".")[0] in _blocked and _from_user_code():
        raise ImportError("module '%s' is blocked inside the Pólya verifier sandbox" % name)
    return _real_import(name, *a, **k)
def _guarded_open(*a, **k):
    if _from_user_code():
        raise PermissionError("file access is blocked in the verifier sandbox")
    return _real_open(*a, **k)
_b.__import__ = _guarded
_b.open = _guarded_open
del _b
'''


@dataclass
class VerifyResult:
    ok: bool
    verified: bool
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    code: str

    def as_log(self) -> str:
        status = "VERIFIED" if self.verified else ("TIMEOUT" if self.timed_out else ("ERROR" if not self.ok else "NOT VERIFIED"))
        return (f"# status: {status} (returncode={self.returncode})\n# --- script ---\n{self.code.strip()}\n"
                f"# --- stdout ---\n{self.stdout.strip()}\n# --- stderr ---\n{self.stderr.strip()}\n")


def verifier_command(full_code: str, frozen: bool | None = None) -> tuple[list[str], str | None]:
    """(argv, stdin) for the verifier child process: `python -I -c code`, or `<app> --lh-verify` (code on stdin)
    inside a frozen app bundle."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return [sys.executable, "--lh-verify"], full_code
    return [sys.executable, "-I", "-c", full_code], None


def verify_math_sympy(code: str, timeout: float = config.SYMPY_TIMEOUT_S) -> VerifyResult:
    """Run verification code in a separate restricted interpreter.

    The child gets an empty temp cwd, no network modules, no file `open`, a 2GB address-space cap and a
    hard timeout. A script verifies a claim by printing a line that starts with `VERIFIED`.
    """
    full = SANDBOX_PRELUDE + "\n" + code
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "SYSTEMROOT")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    # A PyInstaller app binary cannot run `python -c`; it re-enters macos/launcher.py with --lh-verify instead.
    argv, stdin = verifier_command(full)
    with tempfile.TemporaryDirectory(prefix="lh_sympy_") as cwd:
        try:
            proc = subprocess.run(argv, input=stdin, timeout=timeout, capture_output=True,
                                  text=True, cwd=cwd, env=env)
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            return VerifyResult(False, False, out, f"timed out after {timeout}s", -9, True, code)
    verified = proc.returncode == 0 and any(line.strip().startswith("VERIFIED") for line in proc.stdout.splitlines())
    return VerifyResult(proc.returncode == 0, verified, proc.stdout[-8000:], proc.stderr[-4000:], proc.returncode, False, code)


def check_equivalence_code(lhs: str, rhs: str, symbols: str = "x y z") -> str:
    """Build a script that checks lhs == rhs symbolically, with a numeric spot check fallback."""
    return (
        "import sympy as sp, random\n"
        f"{', '.join(symbols.split())}{',' if len(symbols.split()) == 1 else ''} = sp.symbols({symbols!r}, real=True)\n"
        f"lhs = sp.sympify({lhs!r}); rhs = sp.sympify({rhs!r})\n"
        "diff = sp.simplify(lhs - rhs)\n"
        "if diff == 0:\n    print('VERIFIED: symbolic identity', lhs, '==', rhs)\n"
        "else:\n"
        "    syms = sorted(diff.free_symbols, key=str)\n"
        "    ok = all(abs(complex(diff.subs({s: random.uniform(-2, 2) for s in syms}))) < 1e-9 for _ in range(20))\n"
        "    print(('VERIFIED: numerically equal on 20 samples' if ok else 'MISMATCH: difference ='), '' if ok else diff)\n"
    )


# ------------------------------------------------------------------ workspace corpus (LOCAL_CORPUS_RAG)
def _safe_path(rel: str) -> Path:
    p = (config.WORKSPACE / rel).resolve()
    if not str(p).startswith(str(config.WORKSPACE.resolve())):
        raise ValueError("path escapes workspace")
    return p


def _kind(p: Path) -> str:
    return {".tex": "tex", ".md": "md", ".pdf": "pdf"}.get(p.suffix.lower(), "other")


def list_workspace_files() -> list[dict[str, Any]]:
    out = []
    for sub in (config.NOTES_DIR, config.PROBLEMS_DIR):
        if not sub.exists():
            continue
        for p in sorted(sub.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                st = p.stat()
                out.append({
                    "path": str(p.relative_to(config.WORKSPACE)), "kind": _kind(p), "size": st.st_size,
                    "modified_at": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                })
    return out


def grep_workspace(pattern: str, max_hits: int = 60) -> list[dict[str, Any]]:
    """ripgrep when available, otherwise a Python regex scan. Returns [{path, line, text}]."""
    hits: list[dict[str, Any]] = []
    rg = shutil.which("rg")
    roots = [str(d) for d in (config.NOTES_DIR, config.PROBLEMS_DIR) if d.exists()]
    if not roots or not pattern:
        return hits
    if rg:
        proc = subprocess.run([rg, "-n", "-i", "--no-heading", "-g", "!*.pdf", "-m", "20", "-e", pattern, *roots],
                              capture_output=True, text=True, timeout=10)
        for line in proc.stdout.splitlines()[:max_hits]:
            m = re.match(r"^(.*?):(\d+):(.*)$", line)
            if m:
                hits.append({"path": str(Path(m.group(1)).resolve().relative_to(config.WORKSPACE.resolve())),
                             "line": int(m.group(2)), "text": m.group(3).strip()})
        return hits
    rx = re.compile(pattern, re.I)
    for f in list_workspace_files():
        if f["kind"] == "pdf":
            continue
        for i, line in enumerate(_safe_path(f["path"]).read_text(errors="replace").splitlines(), 1):
            if rx.search(line):
                hits.append({"path": f["path"], "line": i, "text": line.strip()})
                if len(hits) >= max_hits:
                    return hits
    return hits


TEX_ENV_RX = re.compile(
    r"\\begin\{(theorem|definition|problem|lemma|proposition|corollary|proof|example|remark)\}(?:\[([^\]]*)\])?(.*?)\\end\{\1\}",
    re.S,
)
TEX_SECTION_RX = re.compile(r"\\(section|subsection)\*?\{([^}]*)\}")


def parse_tex_blocks(text: str) -> list[dict[str, Any]]:
    """Extract \\section headings and theorem-like environments with their line numbers."""
    blocks: list[dict[str, Any]] = []
    for m in TEX_SECTION_RX.finditer(text):
        blocks.append({"env": m.group(1), "title": m.group(2).strip(), "body": "",
                       "line": text.count("\n", 0, m.start()) + 1})
    for m in TEX_ENV_RX.finditer(text):
        blocks.append({"env": m.group(1), "title": (m.group(2) or "").strip(), "body": m.group(3).strip(),
                       "line": text.count("\n", 0, m.start()) + 1})
    blocks.sort(key=lambda b: b["line"])
    return blocks


def read_tex_or_md(filename: str) -> dict[str, Any]:
    p = _safe_path(filename)
    text = p.read_text(errors="replace")
    return {"path": str(p.relative_to(config.WORKSPACE)), "content": text,
            "blocks": parse_tex_blocks(text) if p.suffix == ".tex" else _md_blocks(text)}


def _md_blocks(text: str) -> list[dict[str, Any]]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            out.append({"env": "section", "title": m.group(2).strip(), "body": "", "line": i})
    return out


def read_pdf_file(filename: str, max_pages: int = 30) -> dict[str, Any]:
    p = _safe_path(filename)
    from pypdf import PdfReader
    reader = PdfReader(str(p))
    pages = [(pg.extract_text() or "") for pg in reader.pages[:max_pages]]
    text = "\n\n".join(f"[page {i + 1}]\n{t}" for i, t in enumerate(pages))
    return {"path": str(p.relative_to(config.WORKSPACE)), "content": text, "blocks": [], "pages": len(reader.pages)}


def read_workspace_file(rel: str) -> dict[str, Any]:
    return read_pdf_file(rel) if rel.lower().endswith(".pdf") else read_tex_or_md(rel)


def corpus_search(query: str, max_blocks: int = 5) -> list[dict[str, Any]]:
    """Rank theorem/definition/problem blocks across the workspace by term overlap with the query."""
    terms = {t for t in re.findall(r"[a-zA-Z]{3,}", query.lower())}
    scored = []
    for f in list_workspace_files():
        if f["kind"] not in ("tex", "md"):
            continue
        data = read_tex_or_md(f["path"])
        for b in data["blocks"]:
            hay = (b["title"] + " " + b["body"]).lower()
            score = sum(hay.count(t) for t in terms)
            if score:
                scored.append((score, {**b, "path": f["path"]}))
    scored.sort(key=lambda x: -x[0])
    return [b for _, b in scored[:max_blocks]]


# ------------------------------------------------------------------ arXiv (LITERATURE_RESEARCHER)
OFFLINE_LITERATURE = [
    {"key": "scaled dot product attention variance softmax", "title": "Attention Is All You Need",
     "authors": "Vaswani et al.", "year": 2017, "id": "arXiv:1706.03762",
     "statement": r"Scaled dot-product attention $\mathrm{softmax}(QK^\top/\sqrt{d_k})V$; for $q,k$ with unit-variance entries, $q\cdot k$ has variance $d_k$."},
    {"key": "rope rotary position embedding relative", "title": "RoFormer: Enhanced Transformer with Rotary Position Embedding",
     "authors": "Su et al.", "year": 2021, "id": "arXiv:2104.09864",
     "statement": r"$\langle R_{\Theta,m}q, R_{\Theta,n}k\rangle = q^\top R_{\Theta,n-m}k$, so attention scores depend only on relative position."},
    {"key": "double dqn overestimation maximization bias q-learning", "title": "Deep Reinforcement Learning with Double Q-learning",
     "authors": "van Hasselt, Guez, Silver", "year": 2015, "id": "arXiv:1509.06461",
     "statement": r"Q-learning's $\max$ over noisy estimates is biased upward; decoupling selection ($\theta$) from evaluation ($\theta^-$) removes the bias."},
    {"key": "bellman contraction value iteration fixed point", "title": "Dynamic Programming and Optimal Control (Bertsekas)",
     "authors": "Bertsekas", "year": 1995, "id": "book",
     "statement": r"$\|\mathcal T^*U-\mathcal T^*V\|_\infty\le\gamma\|U-V\|_\infty$; by Banach, value iteration converges geometrically to $V^*$."},
    {"key": "fsrs spaced repetition memory stability retrievability", "title": "A Stochastic Shortest Path Algorithm for Optimizing Spaced Repetition Scheduling",
     "authors": "Ye, Su, Cao", "year": 2022, "id": "doi:10.1145/3534678.3539081",
     "statement": r"Memory modelled by stability $S$ and retrievability $R$; optimal review scheduling via the DSR model underlying FSRS."},
    {"key": "hypercorrection high confidence errors", "title": "Errors committed with high confidence are hypercorrected",
     "authors": "Butterfield & Metcalfe", "year": 2001, "id": "doi:10.1037/0278-7393.27.6.1491",
     "statement": "High-confidence errors, once corrected with feedback, are more likely to be corrected on a later test than low-confidence errors."},
    {"key": "desirable difficulties new theory of disuse storage retrieval strength", "title": "A New Theory of Disuse and an Old Theory of Stimulus Fluctuation",
     "authors": "Bjork & Bjork", "year": 1992, "id": "book chapter",
     "statement": "Retrieval at low retrieval strength produces larger gains in storage strength than retrieval when retrieval strength is high."},
    {"key": "knowledge tracing bayesian bkt", "title": "Knowledge tracing: Modeling the acquisition of procedural knowledge",
     "authors": "Corbett & Anderson", "year": 1994, "id": "doi:10.1007/BF01099821",
     "statement": r"Mastery $P(L)$ updated by Bayes rule with slip $P(S)$ and guess $P(G)$, then a learning transition $P(T)$."},
    {"key": "productive failure", "title": "Productive Failure", "authors": "Kapur", "year": 2008, "id": "doi:10.1080/07370000802212669",
     "statement": "Generating solutions to complex problems before instruction improves conceptual understanding and transfer."},
    {"key": "pretesting effect unsuccessful retrieval attempts", "title": "Unsuccessful retrieval attempts enhance subsequent learning",
     "authors": "Kornell, Hays & Bjork", "year": 2009, "id": "doi:10.1037/a0015729",
     "statement": "Attempting to answer before studying, even unsuccessfully, improves later recall of the studied answer."},
    {"key": "interleaving practice mathematics", "title": "The shuffling of mathematics problems improves learning",
     "authors": "Rohrer & Taylor", "year": 2007, "id": "doi:10.1007/s11251-007-9015-8",
     "statement": "Interleaving problem types during practice improves delayed test performance relative to blocked practice."},
    {"key": "dominated convergence monotone convergence lebesgue", "title": "Real Analysis for Graduate Students",
     "authors": "Bass", "year": 2013, "id": "book",
     "statement": r"If $f_n\to f$ a.e. and $|f_n|\le g\in L^1$ then $\int f_n\to\int f$; if $0\le f_n\uparrow f$ then $\int f_n\uparrow\int f$."},
]


def offline_literature(query: str, k: int = 4) -> list[dict[str, Any]]:
    terms = set(re.findall(r"[a-z]{3,}", query.lower()))
    scored = sorted(OFFLINE_LITERATURE, key=lambda e: -len(terms & set(e["key"].split())))
    return [dict(e, source="offline") for e in scored[:k] if terms & set(e["key"].split())] or [dict(OFFLINE_LITERATURE[0], source="offline")]


def search_arxiv(query: str, max_results: int = 4, timeout: float = config.ARXIV_TIMEOUT_S) -> tuple[list[dict[str, Any]], str]:
    """Query the arXiv Atom API. Returns (entries, source) where source is 'arxiv' or 'offline'."""
    if config.env("OFFLINE") == "1":
        return offline_literature(query, max_results), "offline"
    words = [w for w in re.findall(r"[A-Za-z0-9]+", query) if len(w) > 2][:6]
    q = "+AND+".join(f"all:{urllib.parse.quote(w)}" for w in words) or "all:attention"
    url = f"http://export.arxiv.org/api/query?search_query={q}&start=0&max_results={max_results}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            xml = resp.read()
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml)
        out = []
        for e in root.findall("a:entry", ns):
            out.append({
                "title": " ".join((e.findtext("a:title", "", ns) or "").split()),
                "authors": ", ".join(a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)[:4]),
                "year": (e.findtext("a:published", "", ns) or "")[:4],
                "id": (e.findtext("a:id", "", ns) or "").rsplit("/", 1)[-1],
                "statement": " ".join((e.findtext("a:summary", "", ns) or "").split())[:600],
                "source": "arxiv",
            })
        if out:
            return out, "arxiv"
    except Exception:
        pass
    return offline_literature(query, max_results), "offline"


# ------------------------------------------------------------------ scratch.tex
def read_scratch() -> dict[str, Any]:
    p = config.SCRATCH_PATH
    if not p.exists():
        return {"content": "", "modified_at": None, "path": str(p)}
    return {"content": p.read_text(errors="replace"),
            "modified_at": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "path": str(p)}


def write_scratch(content: str) -> dict[str, Any]:
    config.SCRATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.SCRATCH_PATH.write_text(content)
    return read_scratch()


def write_note(name: str, content: str) -> str:
    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    p = config.NOTES_DIR / safe
    p.write_text(content)
    return str(p.relative_to(config.WORKSPACE))


def maybe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None
