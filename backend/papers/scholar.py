"""Scholarly metadata services for the research loop (docs/specs/paper-reading D3, FR6).

  Semantic Scholar Graph API  references with citation intents and the "influential" flag (shared, rate-limited pool:
                              at most 1 request/s, one retry; enrichment only, never required)
  OpenAlex                    later papers that cite this one (by citation count), surveys/tutorials for a concept

Every function returns None / [] on any network or parsing failure, and does nothing when POLYA_OFFLINE=1.
Blocking; callers run them in a thread.
"""
from __future__ import annotations

import re
import threading
import time
import urllib.parse
from typing import Any, Optional

import httpx

from .. import config
from .fetch import USER_AGENT

S2 = "https://api.semanticscholar.org/graph/v1"
OPENALEX = "https://api.openalex.org"
TIMEOUT_S = 10.0
ARXIV_URL_RX = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})", re.I)
SURVEY_WORDS = ("survey", "tutorial", "review", "introduction", "primer", "overview", "lecture notes")

_s2_lock = threading.Lock()
_s2_last = 0.0


def _json(url: str, s2: bool = False) -> Optional[Any]:
    global _s2_last
    if config.env("OFFLINE") == "1":
        return None
    for attempt in range(2):
        if s2:
            with _s2_lock:
                wait = _s2_last + 1.05 - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                _s2_last = time.monotonic()
        try:
            r = httpx.get(url, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        except httpx.HTTPError:
            return None
        if r.status_code == 429 and attempt == 0:
            time.sleep(3.0)
            continue
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None
    return None


def s2_id_for(arxiv_id: str = "", doi: str = "") -> str:
    if arxiv_id:
        return "arXiv:" + re.sub(r"v\d+$", "", arxiv_id)
    if doi:
        return "DOI:" + doi
    return ""


def s2_paper(arxiv_id: str = "", doi: str = "") -> Optional[dict[str, Any]]:
    pid = s2_id_for(arxiv_id, doi)
    if not pid:
        return None
    return _json(f"{S2}/paper/{urllib.parse.quote(pid, safe=':/')}?fields=paperId,title,year,externalIds,"
                 "citationCount,influentialCitationCount", s2=True)


def s2_references(arxiv_id: str = "", doi: str = "", limit: int = 300) -> list[dict[str, Any]]:
    """[{title, year, arxiv_id, doi, s2_id, contexts, intents, influential, cited_by_count}]"""
    pid = s2_id_for(arxiv_id, doi)
    if not pid:
        return []
    d = _json(f"{S2}/paper/{urllib.parse.quote(pid, safe=':/')}/references?fields=title,year,externalIds,"
              f"citationCount,contexts,intents,isInfluential&limit={limit}", s2=True)
    out = []
    for row in (d or {}).get("data") or []:
        p = row.get("citedPaper") or {}
        if not p.get("title"):
            continue
        ext = p.get("externalIds") or {}
        out.append({"title": p["title"], "year": p.get("year"), "arxiv_id": ext.get("ArXiv") or "",
                    "doi": ext.get("DOI") or "", "s2_id": p.get("paperId") or "", "contexts": row.get("contexts") or [],
                    "intents": row.get("intents") or [], "influential": bool(row.get("isInfluential")),
                    "cited_by_count": p.get("citationCount")})
    return out


def _oa_row(w: dict[str, Any]) -> dict[str, Any]:
    arxiv = ""
    for loc in w.get("locations") or []:
        m = ARXIV_URL_RX.search(loc.get("landing_page_url") or "") or ARXIV_URL_RX.search(loc.get("pdf_url") or "")
        if m:
            arxiv = m.group(1)
            break
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    if not arxiv and doi.lower().startswith("10.48550/arxiv."):
        arxiv = doi[len("10.48550/arxiv."):]
    title = w.get("title") or w.get("display_name") or ""
    return {"title": title, "year": w.get("publication_year"), "arxiv_id": arxiv, "doi": doi,
            "openalex_id": (w.get("id") or "").rsplit("/", 1)[-1], "cited_by_count": w.get("cited_by_count"),
            "is_survey": w.get("type") == "review" or any(k in title.lower() for k in SURVEY_WORDS)}


SELECT = "id,title,display_name,publication_year,cited_by_count,doi,type,locations"


def openalex_work(arxiv_id: str = "", doi: str = "") -> Optional[dict[str, Any]]:
    key = f"doi:10.48550/arXiv.{re.sub(r'v[0-9]+$', '', arxiv_id)}" if arxiv_id else (f"doi:{doi}" if doi else "")
    if not key:
        return None
    w = _json(f"{OPENALEX}/works/{urllib.parse.quote(key, safe=':/')}?select={SELECT}")
    return _oa_row(w) if w and w.get("id") else None


def openalex_citing(openalex_id: str, n: int = 6, surveys: int = 3) -> list[dict[str, Any]]:
    """The most-cited later papers that cite this one, plus the most-cited surveys among them."""
    if not openalex_id:
        return []
    base = f"{OPENALEX}/works?select={SELECT}&sort=cited_by_count:desc"
    top = _json(f"{base}&filter=cites:{openalex_id}&per-page={n}") or {}
    rev = _json(f"{base}&filter=cites:{openalex_id},title.search:{urllib.parse.quote('survey|review|tutorial')}"
                f"&per-page={surveys}") or {}
    seen, out = set(), []
    for w in (top.get("results") or []) + (rev.get("results") or []):
        row = _oa_row(w)
        if row["openalex_id"] not in seen and row["title"]:
            seen.add(row["openalex_id"])
            out.append(row)
    return out


def openalex_explainers(concept: str, n: int = 2) -> list[dict[str, Any]]:
    """Highly cited surveys / tutorials / introductions whose title names the concept."""
    words = " ".join(re.findall(r"[A-Za-z0-9\-]+", concept))[:80]
    if not words:
        return []
    phrase = urllib.parse.quote(f'"{words}"')   # exact phrase: "layer normalization", not layer OR normalization
    filt = f"title.search:{phrase},title.search:{urllib.parse.quote('survey|tutorial|introduction|primer|overview')}"
    d = _json(f"{OPENALEX}/works?select={SELECT}&sort=cited_by_count:desc&per-page={n}&filter={filt}") or {}
    return [_oa_row(w) for w in d.get("results") or [] if (w.get("title") or "")]
