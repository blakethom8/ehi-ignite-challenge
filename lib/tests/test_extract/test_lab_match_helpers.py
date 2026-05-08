"""Tests for PERF-T01 — _normalize_display_tokens, _jaccard, and match_fact_lists helpers.

Focused unit tests on the fuzzy-match primitives added to compare.py.
No real LLMs, no real PDFs, no lab-root disk access.
"""

from __future__ import annotations

import pytest

from lib.extract.lab.compare import (
    FactSample,
    FactMatchResult,
    _normalize_display_tokens,
    _jaccard,
    match_fact_lists,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _sample(display: str, code: str | None = None, rt: str = "Observation") -> FactSample:
    return FactSample(resource_type=rt, display=display, code=code)


def _keys(samples: list[FactSample]) -> dict[tuple, FactSample]:
    """Build a fact-keys dict the same way _extract_fact_keys does."""
    return {
        (s.display.lower().strip(), (s.code or "").lower()): s
        for s in samples
    }


# ---------------------------------------------------------------------------
# 1. _normalize_display_tokens basic
# ---------------------------------------------------------------------------


def test_normalize_display_tokens_basic() -> None:
    assert _normalize_display_tokens("Glucose") == frozenset({"glucose"})
    assert _normalize_display_tokens("") == frozenset()
    assert _normalize_display_tokens(None) == frozenset()


# ---------------------------------------------------------------------------
# 2. _normalize_display_tokens strips punctuation
# ---------------------------------------------------------------------------


def test_normalize_display_tokens_strips_punctuation() -> None:
    result = _normalize_display_tokens("Bilirubin, Total")
    assert result == frozenset({"bilirubin", "total"})


# ---------------------------------------------------------------------------
# 3. _normalize_display_tokens drops stopwords
# ---------------------------------------------------------------------------


def test_normalize_display_tokens_drops_stopwords() -> None:
    assert _normalize_display_tokens("No Known Allergies") == frozenset({"allergies"})
    assert _normalize_display_tokens("No known active allergies") == frozenset({"allergies"})


# ---------------------------------------------------------------------------
# 4. _normalize_display_tokens drops single-letter tokens
# ---------------------------------------------------------------------------


def test_normalize_display_tokens_drops_short_tokens() -> None:
    result = _normalize_display_tokens("Glucose, Serum (A)")
    # "a" is a stopword AND single letter; "A" after lowercase+strip → "a" → dropped
    assert "a" not in result
    assert "glucose" in result
    assert "serum" in result


# ---------------------------------------------------------------------------
# 5. _jaccard basic cases
# ---------------------------------------------------------------------------


def test_jaccard_basic_cases() -> None:
    empty: frozenset[str] = frozenset()
    a = frozenset({"glucose", "serum"})
    b = frozenset({"glucose", "plasma"})

    assert _jaccard(empty, empty) == 1.0
    assert _jaccard(a, empty) == 0.0
    assert _jaccard(empty, a) == 0.0
    assert _jaccard(a, a) == 1.0
    # |a & b| = 1 (glucose), |a | b| = 3 (glucose, serum, plasma) → 1/3
    assert abs(_jaccard(a, b) - 1 / 3) < 1e-9


# ---------------------------------------------------------------------------
# 6. match_fact_lists — code match takes priority over display variance
# ---------------------------------------------------------------------------


def test_match_fact_lists_code_match_takes_priority() -> None:
    """Same LOINC code but different display strings → matched via Stage 1."""
    sa = _sample("Glucose", code="2345-7")
    sb = _sample("Glucose [Mass/volume] in Serum or Plasma", code="2345-7")

    result = match_fact_lists(_keys([sa]), _keys([sb]))

    assert result.overlap == 1
    assert result.fuzzy_matches == 0  # Stage 1, not Stage 2
    assert result.only_in_a == []
    assert result.only_in_b == []


# ---------------------------------------------------------------------------
# 7. match_fact_lists — fuzzy fallback for no-code facts
# ---------------------------------------------------------------------------


def test_match_fact_lists_fuzzy_fallback() -> None:
    """'Progress Note' vs 'Allergy & Immunology Progress Note' (no codes) → fuzzy match."""
    sa = _sample("Progress Note", code=None, rt="Composition")
    sb = _sample("Allergy & Immunology Progress Note", code=None, rt="Composition")

    result = match_fact_lists(_keys([sa]), _keys([sb]))

    assert result.overlap == 1
    assert result.fuzzy_matches == 1
    assert result.only_in_a == []
    assert result.only_in_b == []


# ---------------------------------------------------------------------------
# 8. match_fact_lists — allergy display variants match
# ---------------------------------------------------------------------------


def test_match_fact_lists_no_known_allergies_variants() -> None:
    """'No Known Allergies' vs 'No known active allergies' (no codes) → match."""
    sa = _sample("No Known Allergies", code=None, rt="AllergyIntolerance")
    sb = _sample("No known active allergies", code=None, rt="AllergyIntolerance")

    result = match_fact_lists(_keys([sa]), _keys([sb]))

    assert result.overlap == 1
    assert result.fuzzy_matches == 1


# ---------------------------------------------------------------------------
# 9. match_fact_lists — distinct things don't match
# ---------------------------------------------------------------------------


def test_match_fact_lists_distinct_things_dont_match() -> None:
    """'Glucose' vs 'Insulin' (no codes) → no match (Jaccard below threshold)."""
    sa = _sample("Glucose", code=None)
    sb = _sample("Insulin", code=None)

    result = match_fact_lists(_keys([sa]), _keys([sb]))

    assert result.overlap == 0
    assert result.fuzzy_matches == 0
    assert len(result.only_in_a) == 1
    assert len(result.only_in_b) == 1


# ---------------------------------------------------------------------------
# 10. match_fact_lists — each fact matched at most once
# ---------------------------------------------------------------------------


def test_match_fact_lists_each_fact_matched_at_most_once() -> None:
    """A has [Glucose (no code), Glucose (no code)] and B has [Glucose (no code)].
    Both Glucoses in A share the same dict key, so dict deduplication keeps one.
    Overlap should be 1, residues correctly sized."""
    # Note: _keys() deduplicates by (display.lower(), code.lower())
    # so two identical samples collapse to one key — that's correct FHIR semantics.
    sa1 = _sample("Glucose", code=None)
    sa2 = _sample("Glucose Serum", code=None)  # distinct display → distinct key
    sb = _sample("Glucose", code=None)

    result = match_fact_lists(_keys([sa1, sa2]), _keys([sb]))

    # sa1 and sb both normalize to {"glucose"} → match; sa2 is residue
    assert result.overlap == 1
    assert len(result.only_in_a) == 1   # sa2 unmatched
    assert len(result.only_in_b) == 0


# ---------------------------------------------------------------------------
# 11. match_fact_lists — residues land in only_in_a / only_in_b
# ---------------------------------------------------------------------------


def test_match_fact_lists_returns_residues_for_only_in_each() -> None:
    """Facts unique to A → only_in_a; facts unique to B → only_in_b."""
    sa = _sample("Hypertension", code="38341003", rt="Condition")
    sb = _sample("Diabetes mellitus", code="73211009", rt="Condition")

    result = match_fact_lists(_keys([sa]), _keys([sb]))

    assert result.overlap == 0
    assert len(result.only_in_a) == 1
    assert result.only_in_a[0].display == "Hypertension"
    assert len(result.only_in_b) == 1
    assert result.only_in_b[0].display == "Diabetes mellitus"
