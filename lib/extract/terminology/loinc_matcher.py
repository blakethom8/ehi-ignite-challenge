"""Display-name → LOINC code resolution.

Reference data: ``ehi-atlas/corpus/reference/loinc/common-labs.json`` (curated;
see ``_curate.py`` in that directory). v1 covers ~60 codes hand-picked + API-
verified for the long tail of common CMP / CBC / lipid / urinalysis tests.

Lookup strategy (in order; first hit wins):

    1. Exact match on normalized display string
    2. Alias match against any entry's ``aliases`` list
    3. Jaccard token-overlap fuzzy match (threshold 0.6)

When ``unit`` is supplied, it acts as a tiebreaker — preferred matches share
the unit string with the input.

This is deterministic. No LLM calls. No network. Confidence scores reflect the
match type, not statistical certainty.

Example:
    >>> from lib.extract.terminology.loinc_matcher import match_loinc
    >>> m = match_loinc("Glucose", unit="mg/dL")
    >>> m.code, m.match_type, m.confidence
    ('2345-7', 'exact', 1.0)
    >>> match_loinc("Hgb").code
    '718-7'
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TABLE_PATH = (
    _REPO_ROOT / "ehi-atlas" / "corpus" / "reference" / "loinc" / "common-labs.json"
)

MatchType = Literal["exact", "alias", "fuzzy"]
_FUZZY_THRESHOLD = 0.6


@dataclass(frozen=True)
class LoincMatch:
    """One matcher result. ``confidence`` reflects the match type."""

    code: str
    display: str
    confidence: float
    match_type: MatchType
    unit: str | None = None


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9 /\-%]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str) -> set[str]:
    return {t for t in _normalize(text).split() if len(t) > 1}


@lru_cache(maxsize=1)
def _load_table(path: str | None = None) -> dict:
    """Load and index the LOINC table. Cached after first call."""
    table_path = Path(path) if path else _DEFAULT_TABLE_PATH
    if not table_path.exists():
        raise FileNotFoundError(
            f"LOINC reference table not found at {table_path}. "
            f"Run ehi-atlas/corpus/reference/loinc/_curate.py to build it."
        )
    raw = json.loads(table_path.read_text())
    entries = raw["codes"]

    # Build alias lookup: normalized alias → list of (code, display, unit)
    alias_index: dict[str, list[tuple[str, str, str | None]]] = {}
    for entry in entries:
        code = entry["code"]
        display = entry["display"]
        unit = entry.get("unit")
        # The canonical display itself is the strongest alias
        for alias in [display] + entry.get("aliases", []):
            key = _normalize(alias)
            if not key:
                continue
            alias_index.setdefault(key, []).append((code, display, unit))

    return {"entries": entries, "alias_index": alias_index}


def _pick_unit_match(
    candidates: list[tuple[str, str, str | None]], unit: str | None
) -> tuple[str, str, str | None]:
    """When multiple entries share a normalized display, prefer the one whose unit matches."""
    if unit is None or len(candidates) == 1:
        return candidates[0]
    norm_unit = _normalize(unit)
    for cand in candidates:
        cand_unit = cand[2]
        if cand_unit and _normalize(cand_unit) == norm_unit:
            return cand
    return candidates[0]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_loinc(
    display: str,
    unit: str | None = None,
    *,
    table_path: str | None = None,
) -> LoincMatch | None:
    """Match a display name to a LOINC code.

    Args:
        display: Test display name as extracted from a PDF (e.g. "Glucose",
            "Urea Nitrogen (BUN)", "WBC Count").
        unit: Optional unit string for tiebreaking when multiple entries
            share a display (e.g. "mg/dL" vs "mmol/L" glucose).
        table_path: Optional override for the reference table location.
            Used by tests; production callers should use the default.

    Returns:
        A :class:`LoincMatch` on hit, or ``None`` if nothing meets the
        fuzzy-match threshold.
    """
    if not display or not display.strip():
        return None

    table = _load_table(table_path)
    norm_input = _normalize(display)

    # 1. Exact match (the canonical display itself)
    if norm_input in table["alias_index"]:
        candidates = table["alias_index"][norm_input]
        # If the canonical display normalizes to this key, exact; else alias.
        for entry in table["entries"]:
            if _normalize(entry["display"]) == norm_input:
                code, disp, u = _pick_unit_match(candidates, unit)
                return LoincMatch(
                    code=code, display=disp, confidence=1.0, match_type="exact", unit=u
                )
        # Falls through to alias match
        code, disp, u = _pick_unit_match(candidates, unit)
        return LoincMatch(
            code=code, display=disp, confidence=0.9, match_type="alias", unit=u
        )

    # 2. Fuzzy: Jaccard token overlap against all aliases
    input_tokens = _tokens(display)
    if not input_tokens:
        return None

    best_score = 0.0
    best_match: tuple[str, str, str | None] | None = None
    for alias_key, candidates in table["alias_index"].items():
        score = _jaccard(input_tokens, set(alias_key.split()))
        if score > best_score:
            best_score = score
            best_match = _pick_unit_match(candidates, unit)

    if best_match and best_score >= _FUZZY_THRESHOLD:
        code, disp, u = best_match
        # Map score 0.6-1.0 → confidence 0.5-0.8
        confidence = 0.5 + (best_score - _FUZZY_THRESHOLD) * 0.75
        return LoincMatch(
            code=code,
            display=disp,
            confidence=round(confidence, 2),
            match_type="fuzzy",
            unit=u,
        )

    return None
