"""Tests for lib.extract.terminology.loinc_matcher.

Verifies:
- Exact match on canonical display
- Alias match for common abbreviations
- Unit tiebreaker
- Fuzzy fallback for known variants
- Null on nonsense input
- ≥95% match rate on the 58 tests in our Function Health comparison PDF
  (the "real-world coverage" gate from the CODE-T02 brief)
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.extract.terminology import LoincMatch, match_loinc


REPO_ROOT = Path(__file__).resolve().parents[3]
FUNCTION_HEALTH_OUR_OUTPUT = (
    REPO_ROOT
    / "pdf-review/blake-functionhealth-2025-11-19/our-outputs/function-lab-results-11-19-2025.pdf.prepared.json"
)


def test_exact_match_glucose() -> None:
    m = match_loinc("Glucose")
    assert m is not None
    assert m.code == "2345-7"
    assert m.match_type in ("exact", "alias")
    assert m.confidence >= 0.9


def test_alias_match_bun() -> None:
    m = match_loinc("BUN")
    assert m is not None
    assert m.code == "3094-0"
    assert m.match_type == "alias"


def test_alias_match_egfr() -> None:
    m = match_loinc("eGFR")
    assert m is not None
    assert m.code == "33914-3"


def test_alias_match_hgb() -> None:
    m = match_loinc("Hgb")
    assert m is not None
    assert m.code == "718-7"


def test_alias_match_a1c() -> None:
    m = match_loinc("A1c")
    assert m is not None
    assert m.code == "4548-4"


def test_alias_match_apob() -> None:
    m = match_loinc("ApoB")
    assert m is not None
    assert m.code == "1884-6"


def test_alias_match_bun_creatinine_ratio() -> None:
    m = match_loinc("BUN/Creatinine Ratio")
    assert m is not None
    assert m.code == "3097-3"


def test_unit_tiebreaker_passes_through() -> None:
    """When unit is supplied and matches, the matcher returns the same code.

    This covers the contract; the v1 table doesn't yet have multiple entries
    sharing a normalized display, so this is a smoke test for the parameter.
    """
    m = match_loinc("Glucose", unit="mg/dL")
    assert m is not None
    assert m.code == "2345-7"


def test_fuzzy_match_handles_typos_and_variants() -> None:
    """Realistic variant with 2-of-3 tokens overlapping should fuzzy-match.

    Real-world parser output usually emits clean canonical names; the fuzzy
    fallback handles cases where Pass-0 emits a variant with a small extra
    qualifier (e.g. specimen type appended to the test name).
    """
    m = match_loinc("Aspartate Aminotransferase Serum")
    assert m is not None
    assert m.code == "1920-8"
    assert m.match_type in ("alias", "fuzzy")
    assert m.confidence >= 0.5


def test_null_on_empty_input() -> None:
    assert match_loinc("") is None
    assert match_loinc("   ") is None


def test_null_on_nonsense_input() -> None:
    assert match_loinc("xyzzy") is None
    assert match_loinc("foo bar baz") is None


def test_ige_allergens_resolve_via_alias() -> None:
    """The cedars-myhealth Allergen Profile produces names like
    'Egg White (F001) IgE'. After the LOINC table extension, these should
    resolve via alias match."""
    for name, expected in [
        ("Egg White (F001) IgE", "6106-9"),
        ("Peanut (F013) IgE", "6206-7"),
        ("D pteronyssinus (D001) IgE", "6095-4"),
        ("Cat Dander (E001) IgE", "6098-8"),
        ("Dog Dander (E005) IgE", "6099-6"),
    ]:
        m = match_loinc(name)
        assert m is not None, f"{name} should match"
        assert m.code == expected, f"{name} expected {expected}, got {m.code}"


def test_class_score_entries_never_resolve() -> None:
    """IgE Class scores are ordinal interpretations (0-6) of the underlying
    quantitative IgE test. They have NO standard LOINC code — Function
    Health emits null for them, and we should too. Without this guard
    they would fuzzy-match to the IgE quantitative LOINC, which would
    be wrong (different concept)."""
    for name in [
        "Egg White (F001) IgE Class",
        "Peanut (F013) IgE Class",
        "Egg White (F001) IgE - Class",
        "Wheat IgE - class",  # case-insensitive
        "Eggs IgE Class 0",
    ]:
        assert match_loinc(name) is None, f"{name!r} should NOT resolve"


def test_loinc_match_dataclass_shape() -> None:
    m = match_loinc("Glucose")
    assert isinstance(m, LoincMatch)
    assert isinstance(m.code, str)
    assert isinstance(m.display, str)
    assert isinstance(m.confidence, float)
    assert m.match_type in ("exact", "alias", "fuzzy")


def test_real_world_coverage_function_health_pdf() -> None:
    """≥95% of the 58 tests in our Function Health comparison PDF must match.

    This is the acceptance gate from the CODE-T02 brief.
    """
    if not FUNCTION_HEALTH_OUR_OUTPUT.exists():
        return  # not in this checkout (e.g. clean clone) — skip silently

    bundle = json.loads(FUNCTION_HEALTH_OUR_OUTPUT.read_text())
    observations = [
        e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation"
    ]
    assert len(observations) > 0

    total = len(observations)
    matched = 0
    misses: list[str] = []

    for obs in observations:
        display = obs.get("code", {}).get("text", "")
        unit = obs.get("valueQuantity", {}).get("unit") if obs.get("valueQuantity") else None
        result = match_loinc(display, unit)
        if result is not None and result.confidence >= 0.5:
            matched += 1
        else:
            misses.append(display)

    coverage = matched / total
    assert coverage >= 0.95, (
        f"coverage {coverage:.0%} below 95% target. "
        f"Matched {matched}/{total}. Misses: {misses}"
    )
