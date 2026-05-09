"""PDF fact locator for Reference Review.

This module owns the narrow "find this extracted fact in this source PDF"
surface. It is intentionally independent from the review router so the locator
can evolve into an agent-assisted subsystem without tangling UI review state,
reference publishing, or pipeline-run artifact handling.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from pydantic import BaseModel, Field

LOCATOR_VERSION = "heuristic-text-v1"


class PdfLocatorBBox(BaseModel):
    """Normalized PDF page bbox, top-left origin, all values 0..1."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class PdfTextMatch(BaseModel):
    page_number: int
    bbox: PdfLocatorBBox
    text: str
    score: float
    confidence: str
    matched_terms: list[str]
    strategy: str = LOCATOR_VERSION


class FactLocatorInput(BaseModel):
    resource_ref: str
    resource_type: str
    display: str
    codes: list[str] = Field(default_factory=list)
    value: str | None = None
    date: str | None = None
    status: str | None = None


class FactLocationResult(BaseModel):
    resource_ref: str
    query: str
    locator_version: str = LOCATOR_VERSION
    matches: list[PdfTextMatch]


def locate_fact_in_pdf(
    *,
    pdf_path: Path,
    fact: FactLocatorInput,
    limit: int = 8,
) -> FactLocationResult:
    query = build_fact_search_query(fact)
    return FactLocationResult(
        resource_ref=fact.resource_ref,
        query=query,
        matches=find_pdf_matches(pdf_path, query, limit=limit),
    )


def build_fact_search_query(fact: FactLocatorInput) -> str:
    pieces = [
        fact.display.split(":", 1)[-1],
        fact.value or "",
        fact.date or "",
        fact.status or "",
        " ".join(fact.codes[:3]),
    ]
    return " ".join(piece for piece in pieces if piece).strip()


def find_pdf_matches(pdf_path: Path, query: str, *, limit: int = 12) -> list[PdfTextMatch]:
    tokens = _query_tokens(query)
    if not tokens:
        return []
    pages = _pdf_words_cached(str(pdf_path), pdf_path.stat().st_mtime_ns)
    candidates: list[PdfTextMatch] = []
    token_set = set(tokens)
    for page in pages:
        words = page["words"]
        if not words:
            continue
        window_size = min(max(len(tokens) + 3, 5), 14)
        for start in range(0, len(words)):
            window = words[start:start + window_size]
            hits = [word for word in window if word["norm"] in token_set]
            if not hits:
                continue
            unique_hits = {word["norm"] for word in hits}
            score = len(unique_hits) / max(len(token_set), 1)
            if len(hits) >= 2:
                score += 0.2
            if len(unique_hits) >= 2 and _has_adjacent_hits(window, token_set):
                score += 0.08
            if score < 0.28:
                continue
            bbox = _bbox_from_words(hits, float(page["width"]), float(page["height"]))
            text = " ".join(word["text"] for word in window).strip()
            candidates.append(
                PdfTextMatch(
                    page_number=int(page["page_number"]),
                    bbox=bbox,
                    text=text[:240],
                    score=round(min(score, 1.0), 3),
                    confidence=_confidence(score),
                    matched_terms=sorted(unique_hits),
                )
            )
    deduped: dict[tuple[int, int, int, int, int], PdfTextMatch] = {}
    for match in sorted(candidates, key=lambda item: item.score, reverse=True):
        key = (
            match.page_number,
            round(match.bbox.x * 100),
            round(match.bbox.y * 100),
            round(match.bbox.width * 100),
            round(match.bbox.height * 100),
        )
        deduped.setdefault(key, match)
    return sorted(deduped.values(), key=lambda item: item.score, reverse=True)[:limit]


@lru_cache(maxsize=64)
def _pdf_words_cached(pdf_path: str, mtime_ns: int) -> tuple[dict[str, Any], ...]:
    import pdfplumber

    del mtime_ns
    pages: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            words = []
            for word in page.extract_words() or []:
                text = str(word.get("text") or "")
                norm = _normalize_token(text)
                if not norm:
                    continue
                words.append({
                    "text": text,
                    "norm": norm,
                    "x0": float(word.get("x0") or 0),
                    "x1": float(word.get("x1") or 0),
                    "top": float(word.get("top") or 0),
                    "bottom": float(word.get("bottom") or 0),
                })
            pages.append({
                "page_number": page_number,
                "width": float(page.width),
                "height": float(page.height),
                "words": tuple(words),
            })
    return tuple(pages)


def _bbox_from_words(words: list[dict[str, Any]], page_width: float, page_height: float) -> PdfLocatorBBox:
    x0 = max(min(float(word["x0"]) for word in words) - 2, 0)
    x1 = min(max(float(word["x1"]) for word in words) + 2, page_width)
    y0 = max(min(float(word["top"]) for word in words) - 2, 0)
    y1 = min(max(float(word["bottom"]) for word in words) + 2, page_height)
    return PdfLocatorBBox(
        x=x0 / page_width,
        y=y0 / page_height,
        width=max((x1 - x0) / page_width, 0.002),
        height=max((y1 - y0) / page_height, 0.002),
    )


def _query_tokens(query: str) -> list[str]:
    stopwords = {
        "and", "the", "with", "for", "from", "final", "active", "unknown",
        "observation", "condition", "medicationrequest", "encounter", "patient",
        "procedure", "documentreference", "composition",
    }
    out: list[str] = []
    for raw in re.findall(r"[A-Za-z0-9][A-Za-z0-9./-]*", query.lower()):
        token = _normalize_token(raw)
        if len(token) < 3 or token in stopwords:
            continue
        out.append(token)
    return list(dict.fromkeys(out))[:12]


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _confidence(score: float) -> str:
    if score >= 0.78:
        return "high"
    if score >= 0.48:
        return "medium"
    return "low"


def _has_adjacent_hits(words: list[dict[str, Any]], token_set: set[str]) -> bool:
    last_hit = False
    for word in words:
        hit = word["norm"] in token_set
        if hit and last_hit:
            return True
        last_hit = hit
    return False
