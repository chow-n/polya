"""Fetch a paper from arXiv (docs/specs/paper-reading D2, FR1, FR2): metadata from the arXiv API, the LaTeX source
from /e-print (safely extracted), else the PDF. Blocking functions; callers run them in a thread.
"""
from __future__ import annotations

import gzip
import io
import re
import tarfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import httpx

from .. import config

USER_AGENT = "Polya/0.5 (local-first learning app; https://github.com/chow-n/polya)"
TIMEOUT_S = 20.0
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_TEXT_FILE_BYTES = 5 * 1024 * 1024
KEPT_SUFFIXES = {".tex", ".ltx", ".bbl", ".bib", ".sty", ".cls", ".txt"}

NEW_ID = r"\d{4}\.\d{4,5}"
OLD_ID = r"[a-z][a-z\-]+(?:\.[A-Z]{2})?/\d{7}"
REF_RXS = [
    re.compile(rf"arxiv\.org/(?:abs|pdf|html|format|e-print)/({NEW_ID}|{OLD_ID})(v\d+)?", re.I),
    re.compile(rf"\barxiv\s*:\s*({NEW_ID}|{OLD_ID})(v\d+)?", re.I),
    re.compile(rf"^\s*({NEW_ID}|{OLD_ID})(v\d+)?(?:\.pdf)?\s*$"),
]


class FetchError(RuntimeError):
    pass


def parse_arxiv_ref(text: str) -> Optional[str]:
    """'2401.01234', 'arXiv:2401.01234v2', 'https://arxiv.org/pdf/2401.01234v2.pdf', 'math/0211159' → the id
    (with its version when one was given). None for anything else."""
    t = (text or "").strip()
    for rx in REF_RXS:
        m = rx.search(t)
        if m:
            return m.group(1) + (m.group(2) or "")
    return None


def _offline() -> None:
    if config.env("OFFLINE") == "1":
        raise FetchError("offline mode (POLYA_OFFLINE=1): network access disabled")


def _get(url: str, max_bytes: int = MAX_ARCHIVE_BYTES, retries: int = 1) -> bytes:
    _offline()
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as c:
                with c.stream("GET", url) as r:
                    if r.status_code in (429, 503) and attempt < retries:
                        time.sleep(3.0)
                        continue
                    r.raise_for_status()
                    chunks, size = [], 0
                    for ch in r.iter_bytes():
                        size += len(ch)
                        if size > max_bytes:
                            raise FetchError(f"download larger than {max_bytes // (1024 * 1024)} MB")
                        chunks.append(ch)
                    return b"".join(chunks)
        except httpx.HTTPError as e:
            if attempt >= retries:
                raise FetchError(f"{url}: {e}") from e
            time.sleep(2.0)
    raise FetchError(f"{url}: rate limited")


def arxiv_metadata(arxiv_id: str) -> dict[str, Any]:
    xml = _get(f"https://export.arxiv.org/api/query?id_list={arxiv_id}", max_bytes=2_000_000)
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(xml)
    e = root.find("a:entry", ns)
    if e is None or not (e.findtext("a:title", "", ns) or "").strip() or (e.findtext("a:id", "", ns) or "").endswith("api/errors"):
        raise FetchError(f"arXiv has no paper {arxiv_id}")
    return {
        "arxiv_id": arxiv_id,
        "title": " ".join((e.findtext("a:title", "", ns) or "").split()),
        "authors": [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
        "year": int((e.findtext("a:published", "", ns) or "0")[:4] or 0) or None,
        "abstract": " ".join((e.findtext("a:summary", "", ns) or "").split()),
        "doi": (e.findtext("arxiv:doi", "", ns) or "").strip(),
    }


def safe_extract(data: bytes, dest: Path) -> list[Path]:
    """Extract an arXiv e-print (tar.gz, tar, or one gzipped .tex) keeping only text files, refusing absolute paths,
    '..', links and devices, and capping each file's size. Returns the files written."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    raw = data
    if data[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(data)
        except OSError as e:
            raise FetchError(f"corrupt gzip: {e}") from e
        if len(raw) > MAX_ARCHIVE_BYTES * 4:
            raise FetchError("source archive too large")
    written: list[Path] = []
    try:
        tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")
    except tarfile.TarError:
        if raw[:4] == b"%PDF":
            raise FetchError("pdf-only")
        p = dest / "main.tex"      # a single gzipped .tex file
        p.write_bytes(raw[:MAX_TEXT_FILE_BYTES])
        return [p]
    with tf:
        for m in tf.getmembers():
            name = m.name
            parts = Path(name).parts
            if not m.isfile() or name.startswith("/") or ".." in parts or Path(name).suffix.lower() not in KEPT_SUFFIXES:
                continue
            if m.size > MAX_TEXT_FILE_BYTES:
                continue
            target = (root / name).resolve()
            if not str(target).startswith(str(root) + "/"):
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f.read(MAX_TEXT_FILE_BYTES))
            written.append(target)
    return written


def fetch_arxiv_source(arxiv_id: str, dest: Path) -> str:
    """'latex' when a source tree was extracted into dest/source, 'pdf' when arXiv only has a PDF (saved to
    dest/paper.pdf)."""
    data = _get(f"https://arxiv.org/e-print/{arxiv_id}")
    if data[:4] == b"%PDF":
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "paper.pdf").write_bytes(data)
        return "pdf"
    try:
        files = safe_extract(data, dest / "source")
    except FetchError as e:
        if str(e) == "pdf-only":
            return fetch_arxiv_pdf(arxiv_id, dest)
        raise
    if not any(p.suffix.lower() in (".tex", ".ltx") for p in files):
        return fetch_arxiv_pdf(arxiv_id, dest)
    return "latex"


def fetch_arxiv_pdf(arxiv_id: str, dest: Path) -> str:
    data = _get(f"https://arxiv.org/pdf/{arxiv_id}")
    if data[:4] != b"%PDF":
        raise FetchError("arXiv did not return a PDF")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "paper.pdf").write_bytes(data)
    return "pdf"


def pdf_pages(path: Path, max_pages: int = 60) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return [(pg.extract_text() or "") for pg in reader.pages[:max_pages]]
