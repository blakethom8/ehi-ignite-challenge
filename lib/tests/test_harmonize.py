"""Tests for lib.harmonize — cross-source Observation merge."""

from __future__ import annotations

from datetime import datetime

import pytest

from lib.harmonize import (
    MergedObservation,
    SourceBundle,
    merge_observations,
    mint_provenance,
)
from lib.harmonize.loinc_bridge import lookup_by_name, normalize_name
from lib.harmonize.units import convert


# ---------------------------------------------------------------------------
# Fixtures — realistic FHIR Observation snippets
# ---------------------------------------------------------------------------


def _cedars_obs(loinc: str, display: str, value: float, unit: str, date: str) -> dict:
    """A Cedars-style Observation: LOINC code present."""
    return {
        "resourceType": "Observation",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc, "display": display}],
            "text": display,
        },
        "valueQuantity": {"value": value, "unit": unit},
        "effectiveDateTime": date,
    }


def _function_obs(name: str, value: float | None, unit: str | None, date: str) -> dict:
    """A Function-Health-style Observation: text label only."""
    obs: dict = {
        "resourceType": "Observation",
        "code": {"text": name},
        "effectiveDateTime": date,
    }
    if value is not None:
        obs["valueQuantity"] = {"value": value, "unit": unit}
    return obs


# ---------------------------------------------------------------------------
# Bridge + units unit tests
# ---------------------------------------------------------------------------


def test_normalize_name_strips_punctuation():
    assert normalize_name("BUN/Creatinine Ratio") == "bun creatinine ratio"
    assert normalize_name("HDL  Cholesterol  ") == "hdl cholesterol"
    assert normalize_name("Hemoglobin A1c") == "hemoglobin a1c"


def test_lookup_by_name_resolves_common_labs():
    assert lookup_by_name("Hemoglobin A1c") == (
        "4548-4",
        "Hemoglobin A1c/Hemoglobin.total in Blood",
        "%",
    )
    assert lookup_by_name("HDL Cholesterol")[0] == "2085-9"
    assert lookup_by_name("Apolipoprotein B")[0] == "1884-6"


def test_lookup_by_name_returns_none_for_unknown():
    assert lookup_by_name("Some Made Up Lab") is None


def test_convert_handles_glucose_loinc_disambiguation():
    # Cholesterol uses 38.67; Glucose uses 18.0156. Loinc-aware override picks
    # glucose factor when LOINC for glucose is passed.
    chol_val, _ = convert(5.0, "mmol/L", "mg/dL", loinc="2093-3")
    glu_val, _ = convert(5.0, "mmol/L", "mg/dL", loinc="2345-7")
    assert abs(chol_val - 5.0 * 38.67) < 0.01
    assert abs(glu_val - 5.0 * 18.0156) < 0.01


def test_convert_no_op_when_units_match():
    v, u = convert(120.0, "mg/dL", "mg/dL")
    assert v == 120.0
    assert u == "mg/dL"


# ---------------------------------------------------------------------------
# Matcher tests
# ---------------------------------------------------------------------------


def test_loinc_match_across_sources():
    """Two sources both with LOINC codes merge into one fact."""
    a = SourceBundle(
        "Cedars",
        [_cedars_obs("4548-4", "Hemoglobin A1C", 5.1, "%", "2025-11-07")],
    )
    b = SourceBundle(
        "Quest",
        [_cedars_obs("4548-4", "Hemoglobin A1c", 5.2, "%", "2025-11-29")],
    )
    merged = merge_observations([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert m.loinc_code == "4548-4"
    assert len(m.sources) == 2
    assert [s.value for s in m.sources] == [5.1, 5.2]


def test_name_bridge_merges_text_only_with_loinc_source():
    """Cedars (LOINC) + Function Health (text only) merge via the bridge."""
    cedars = SourceBundle(
        "Cedars",
        [_cedars_obs("4548-4", "Hemoglobin A1C", 5.1, "%", "2025-11-07")],
    )
    function = SourceBundle(
        "Function Health",
        [_function_obs("Hemoglobin A1c", 5.2, "%", "2025-11-29")],
    )
    merged = merge_observations([cedars, function])
    assert len(merged) == 1
    m = merged[0]
    assert m.loinc_code == "4548-4"
    assert {s.source_label for s in m.sources} == {"Cedars", "Function Health"}


def test_unit_normalization_converts_mmol_to_mg_dl():
    """Cedars in mg/dL + an mmol/L source unify to mg/dL."""
    cedars = SourceBundle(
        "Cedars",
        [_cedars_obs("2093-3", "Cholesterol", 220, "mg/dL", "2025-11-07")],
    )
    metric = SourceBundle(
        "EU-Lab",
        [_function_obs("Total Cholesterol", 5.69, "mmol/L", "2025-08-01")],
    )
    merged = merge_observations([cedars, metric])
    assert len(merged) == 1
    m = merged[0]
    assert m.canonical_unit == "mg/dL"
    eu_source = next(s for s in m.sources if s.source_label == "EU-Lab")
    # 5.69 mmol/L × 38.67 ≈ 220 mg/dL
    assert eu_source.unit == "mg/dL"
    assert abs(eu_source.value - 5.69 * 38.67) < 0.01
    assert eu_source.raw_value == 5.69
    assert eu_source.raw_unit == "mmol/L"


def test_passthrough_for_unbridged_text_labels():
    """Two sources with text-only names not in the bridge still merge by name."""
    a = SourceBundle("A", [_function_obs("Some Custom Lab", 1.0, "U", "2025-01-01")])
    b = SourceBundle("B", [_function_obs("some custom lab", 2.0, "U", "2025-02-01")])
    merged = merge_observations([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert m.loinc_code is None
    assert len(m.sources) == 2


def test_chronological_order_within_merged():
    a = SourceBundle("A", [_cedars_obs("4548-4", "A1C", 5.0, "%", "2024-07-29")])
    b = SourceBundle("B", [_cedars_obs("4548-4", "A1C", 5.1, "%", "2025-11-07")])
    c = SourceBundle("C", [_cedars_obs("4548-4", "A1C", 5.2, "%", "2025-11-29")])
    merged = merge_observations([a, b, c])
    assert [s.value for s in merged[0].sources] == [5.0, 5.1, 5.2]


def test_latest_picks_most_recent():
    a = SourceBundle("A", [_cedars_obs("4548-4", "A1C", 5.0, "%", "2024-07-29")])
    b = SourceBundle("B", [_cedars_obs("4548-4", "A1C", 5.2, "%", "2025-11-29")])
    merged = merge_observations([a, b])
    assert merged[0].latest.value == 5.2


def test_conflict_detection_same_day_disagreement():
    """Two sources on the same day with >10% spread → conflict."""
    a = SourceBundle("A", [_cedars_obs("2093-3", "Cholesterol", 200, "mg/dL", "2025-11-07")])
    b = SourceBundle("B", [_cedars_obs("2093-3", "Cholesterol", 240, "mg/dL", "2025-11-07")])
    merged = merge_observations([a, b])
    # Spread = 40 / 220 = 18% > 10%
    assert merged[0].has_conflict is True


def test_no_conflict_for_longitudinal_change():
    """Same-LOINC values on different days don't trigger conflict."""
    a = SourceBundle("A", [_cedars_obs("2085-9", "HDL", 81, "mg/dL", "2024-07-29")])
    b = SourceBundle("B", [_cedars_obs("2085-9", "HDL", 67, "mg/dL", "2025-11-07")])
    merged = merge_observations([a, b])
    assert merged[0].has_conflict is False


# ---------------------------------------------------------------------------
# Provenance tests
# ---------------------------------------------------------------------------


def test_mint_provenance_emits_one_entity_per_source():
    cedars = SourceBundle(
        "Cedars",
        [_cedars_obs("4548-4", "A1C", 5.1, "%", "2025-11-07")],
    )
    function = SourceBundle(
        "Function Health",
        [_function_obs("Hemoglobin A1c", 5.2, "%", "2025-11-29")],
    )
    merged = merge_observations([cedars, function])
    prov = mint_provenance(merged[0])
    assert prov["resourceType"] == "Provenance"
    assert len(prov["entity"]) == 2
    labels = {
        next(e["valueString"] for e in entity["extension"] if e["url"].endswith("source-label"))
        for entity in prov["entity"]
    }
    assert labels == {"Cedars", "Function Health"}


def test_mint_provenance_records_top_activity():
    """When LOINC and name-bridge both fire, the resource activity rolls up to loinc-match."""
    cedars = SourceBundle(
        "Cedars",
        [_cedars_obs("4548-4", "A1C", 5.1, "%", "2025-11-07")],
    )
    function = SourceBundle(
        "Function Health",
        [_function_obs("Hemoglobin A1c", 5.2, "%", "2025-11-29")],
    )
    merged = merge_observations([cedars, function])
    prov = mint_provenance(merged[0])
    activity_code = prov["activity"]["coding"][0]["code"]
    # loinc-match (Cedars edge) ranks above name-match (Function edge).
    assert activity_code == "loinc-match"


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


def test_empty_sources_returns_empty():
    assert merge_observations([]) == []


def test_observation_without_code_text_skipped():
    a = SourceBundle("A", [{"resourceType": "Observation", "code": {}}])
    assert merge_observations([a]) == []
