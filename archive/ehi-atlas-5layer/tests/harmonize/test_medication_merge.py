"""Tests for ehi_atlas.harmonize.medication — Medication episode reconciliation.

Coverage (15 tests):
  1.  test_episode_from_medication_request_extracts_rxcui_and_dates
  2.  test_episodes_same_ingredient_simvastatin_match
  3.  test_episodes_same_ingredient_simvastatin_vs_atorvastatin_returns_false
  4.  test_episodes_same_ingredient_unmapped_returns_false
  5.  test_merge_episodes_combines_same_ingredient
  6.  test_merge_episodes_picks_higher_priority_status
  7.  test_merge_episodes_preserves_period_end
  8.  test_merge_episodes_attaches_quality_score
  9.  test_merge_episodes_attaches_merge_rationale
  10. test_reconcile_episodes_passthrough_for_singleton_groups
  11. test_reconcile_episodes_groups_two_simvastatin_sources
  12. test_reconcile_episodes_keeps_simvastatin_and_atorvastatin_separate  [ARTIFACT 2 ANCHOR part 1]
  13. test_detect_cross_class_flags_simvastatin_vs_atorvastatin             [ARTIFACT 2 ANCHOR part 2]
  14. test_detect_cross_class_flags_no_flag_when_same_ingredient
  15. test_detect_cross_class_flags_no_flag_when_no_class_match
"""

from __future__ import annotations

import pytest

from ehi_atlas.harmonize.medication import (
    CrossClassFlag,
    EpisodeMergeResult,
    MedicationEpisode,
    detect_cross_class_flags,
    episode_from_medication_request,
    episodes_same_ingredient,
    merge_episodes,
    reconcile_episodes,
)
from ehi_atlas.harmonize.provenance import (
    EXT_MERGE_RATIONALE,
    EXT_QUALITY_SCORE,
    SYS_LIFECYCLE,
    SYS_SOURCE_TAG,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"
SNOMED_SYSTEM = "http://snomed.info/sct"

RXCUI_SIMVASTATIN = "36567"
RXCUI_ATORVASTATIN = "83367"
RXCUI_AMOXICILLIN = "723"  # an antibiotic — NOT a statin


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _synthea_simvastatin(
    req_id: str = "synthea-simva-001",
    status: str = "active",
    authored_on: str = "2024-01-01",
    period_start: str | None = None,
    period_end: str | None = None,
    quality: float | None = 0.85,
) -> dict:
    """Minimal FHIR MedicationRequest for simvastatin from Synthea source."""
    req: dict = {
        "resourceType": "MedicationRequest",
        "id": req_id,
        "status": status,
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": RXNORM_SYSTEM,
                    "code": RXCUI_SIMVASTATIN,
                    "display": "Simvastatin",
                }
            ],
            "text": "Simvastatin",
        },
        "subject": {"reference": "Patient/rhett759"},
        "authoredOn": authored_on,
        "meta": {
            "tag": [{"system": SYS_SOURCE_TAG, "code": "synthea"}],
            "extension": [],
        },
    }
    if period_start or period_end:
        vp: dict = {}
        if period_start:
            vp["start"] = period_start
        if period_end:
            vp["end"] = period_end
        req["dispenseRequest"] = {"validityPeriod": vp}
    if quality is not None:
        req["meta"]["extension"].append(
            {"url": EXT_QUALITY_SCORE, "valueDecimal": quality}
        )
    return req


def _epic_atorvastatin_discontinued(
    req_id: str = "epic-atorva-001",
    status: str = "stopped",
    authored_on: str = "2023-06-01",
    period_start: str | None = "2023-06-01",
    period_end: str | None = "2025-09-01",
    quality: float | None = 0.85,
) -> dict:
    """Minimal FHIR MedicationRequest for atorvastatin (discontinued) from Epic source.

    This represents the Artifact 2 Epic projection: atorvastatin discontinued 2025-09-01.
    """
    req: dict = {
        "resourceType": "MedicationRequest",
        "id": req_id,
        "status": status,
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": RXNORM_SYSTEM,
                    "code": RXCUI_ATORVASTATIN,
                    "display": "Atorvastatin",
                }
            ],
            "text": "Atorvastatin",
        },
        "subject": {"reference": "Patient/rhett759"},
        "authoredOn": authored_on,
        "dispenseRequest": {
            "validityPeriod": {
                "start": period_start,
                "end": period_end,
            }
        },
        "meta": {
            "tag": [{"system": SYS_SOURCE_TAG, "code": "epic-ehi"}],
            "extension": [],
        },
    }
    if quality is not None:
        req["meta"]["extension"].append(
            {"url": EXT_QUALITY_SCORE, "valueDecimal": quality}
        )
    return req


def _amoxicillin_req(
    req_id: str = "synthea-amox-001",
    source_tag: str = "synthea",
) -> dict:
    """MedicationRequest for amoxicillin (an antibiotic — not in statin class)."""
    return {
        "resourceType": "MedicationRequest",
        "id": req_id,
        "status": "completed",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": RXNORM_SYSTEM,
                    "code": RXCUI_AMOXICILLIN,
                    "display": "Amoxicillin",
                }
            ]
        },
        "subject": {"reference": "Patient/rhett759"},
        "authoredOn": "2024-03-01",
        "meta": {
            "tag": [{"system": SYS_SOURCE_TAG, "code": source_tag}],
            "extension": [],
        },
    }


def _unmapped_req(req_id: str = "ccda-med-unknown-001") -> dict:
    """MedicationRequest coded only with a proprietary system — no RxNorm."""
    return {
        "resourceType": "MedicationRequest",
        "id": req_id,
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://proprietary.example/meds",
                    "code": "SIMVA40",
                    "display": "Simvastatin Tablet 40mg",
                }
            ]
        },
        "subject": {"reference": "Patient/rhett759"},
        "authoredOn": "2024-05-01",
        "meta": {"tag": [], "extension": []},
    }


# ---------------------------------------------------------------------------
# 1. episode_from_medication_request — extracts rxcui and dates
# ---------------------------------------------------------------------------


def test_episode_from_medication_request_extracts_rxcui_and_dates():
    """A simvastatin MedicationRequest yields rxcui=36567 and correct dates."""
    req = _synthea_simvastatin(
        authored_on="2024-01-01",
        period_start="2024-01-01",
        period_end=None,
    )
    ep = episode_from_medication_request(req)

    assert ep.rxcui == RXCUI_SIMVASTATIN
    assert ep.ingredient_label == "Simvastatin"
    assert ep.status == "active"
    assert ep.period_start == "2024-01-01"
    assert ep.period_end is None
    assert ep.source_resource_id == "synthea-simva-001"
    assert ep.source_tag == "synthea"


def test_episode_from_medication_request_falls_back_to_authored_on():
    """When no validityPeriod, period_start falls back to authoredOn."""
    req = _synthea_simvastatin(authored_on="2023-11-15")
    # No dispenseRequest set → falls back to authoredOn
    ep = episode_from_medication_request(req)
    assert ep.period_start == "2023-11-15"


def test_episode_from_medication_request_extracts_period_end():
    """MedicationRequest with validityPeriod.end → period_end populated."""
    req = _epic_atorvastatin_discontinued(period_end="2025-09-01")
    ep = episode_from_medication_request(req)
    assert ep.period_end == "2025-09-01"
    assert ep.rxcui == RXCUI_ATORVASTATIN


def test_episode_from_medication_request_none_when_no_rxnorm():
    """No RxNorm coding → rxcui=None."""
    req = _unmapped_req()
    ep = episode_from_medication_request(req)
    assert ep.rxcui is None


# ---------------------------------------------------------------------------
# 2. episodes_same_ingredient — simvastatin match
# ---------------------------------------------------------------------------


def test_episodes_same_ingredient_simvastatin_match():
    """Two simvastatin episodes (same RxCUI) → True."""
    ep_a = episode_from_medication_request(_synthea_simvastatin("simva-a"))
    ep_b = episode_from_medication_request(_synthea_simvastatin("simva-b"))
    assert episodes_same_ingredient(ep_a, ep_b) is True


# ---------------------------------------------------------------------------
# 3. episodes_same_ingredient — simvastatin vs atorvastatin → False
# ---------------------------------------------------------------------------


def test_episodes_same_ingredient_simvastatin_vs_atorvastatin_returns_false():
    """ARTIFACT 2 setup: simvastatin (36567) vs atorvastatin (83367) → False.

    Different ingredients must NOT merge, even though both are statins.
    The cross-source conflict is detected by detect_cross_class_flags, not here.
    """
    ep_simva = episode_from_medication_request(_synthea_simvastatin("simva-001"))
    ep_atorva = episode_from_medication_request(_epic_atorvastatin_discontinued("atorva-001"))
    assert episodes_same_ingredient(ep_simva, ep_atorva) is False


# ---------------------------------------------------------------------------
# 4. episodes_same_ingredient — unmapped → False
# ---------------------------------------------------------------------------


def test_episodes_same_ingredient_unmapped_returns_false():
    """Both rxcui=None → False (we never guess at unmapped codes)."""
    ep_a = episode_from_medication_request(_unmapped_req("unmapped-a"))
    ep_b = episode_from_medication_request(_unmapped_req("unmapped-b"))
    assert episodes_same_ingredient(ep_a, ep_b) is False


# ---------------------------------------------------------------------------
# 5. merge_episodes — combines two same-ingredient requests
# ---------------------------------------------------------------------------


def test_merge_episodes_combines_same_ingredient():
    """Merging two simvastatin requests produces a single resource with both source tags."""
    req_a = _synthea_simvastatin("simva-s1")
    req_b = _synthea_simvastatin("simva-s2")
    # Simulate second request from a different source
    req_b["meta"]["tag"] = [{"system": SYS_SOURCE_TAG, "code": "ccda"}]

    result = merge_episodes([req_a, req_b], canonical_id="merged-simva-0")
    merged = result.merged

    assert merged["id"] == "merged-simva-0"
    assert merged["resourceType"] == "MedicationRequest"

    tags = merged["meta"]["tag"]
    source_codes = {t["code"] for t in tags if t.get("system") == SYS_SOURCE_TAG}
    assert "synthea" in source_codes
    assert "ccda" in source_codes

    lifecycle_codes = {t["code"] for t in tags if t.get("system") == SYS_LIFECYCLE}
    assert "harmonized" in lifecycle_codes

    id_values = {ident.get("value") for ident in merged.get("identifier", [])}
    assert "simva-s1" in id_values
    assert "simva-s2" in id_values

    assert "MedicationRequest/simva-s1" in result.sources
    assert "MedicationRequest/simva-s2" in result.sources


# ---------------------------------------------------------------------------
# 6. merge_episodes — picks higher-priority status (stopped > active)
# ---------------------------------------------------------------------------


def test_merge_episodes_picks_higher_priority_status():
    """active + stopped → merged status is 'stopped' (higher STATUS_PRIORITY)."""
    active_req = _synthea_simvastatin("simva-active", status="active")
    stopped_req = _synthea_simvastatin("simva-stopped", status="stopped")
    # Make second req look like it came from a different source
    stopped_req["meta"]["tag"] = [{"system": SYS_SOURCE_TAG, "code": "epic-ehi"}]

    result = merge_episodes([active_req, stopped_req], canonical_id="merged-status-0")
    assert result.merged["status"] == "stopped"


# ---------------------------------------------------------------------------
# 7. merge_episodes — preserves period_end
# ---------------------------------------------------------------------------


def test_merge_episodes_preserves_period_end():
    """When one input has period_end 2025-09-01, the merged resource must carry it."""
    req_a = _synthea_simvastatin("simva-ongoing", period_start="2024-01-01")
    req_b = _synthea_simvastatin(
        "simva-ended", period_start="2023-06-01", period_end="2025-09-01"
    )
    req_b["meta"]["tag"] = [{"system": SYS_SOURCE_TAG, "code": "epic-ehi"}]

    result = merge_episodes([req_a, req_b], canonical_id="merged-end-0")
    merged = result.merged

    # period_end must propagate to dispenseRequest.validityPeriod.end
    vp = merged.get("dispenseRequest", {}).get("validityPeriod", {})
    assert vp.get("end") == "2025-09-01"


# ---------------------------------------------------------------------------
# 8. merge_episodes — attaches quality score
# ---------------------------------------------------------------------------


def test_merge_episodes_attaches_quality_score():
    """Merged resource carries EXT_QUALITY_SCORE = max of inputs."""
    req_a = _synthea_simvastatin("simva-q1", quality=0.70)
    req_b = _synthea_simvastatin("simva-q2", quality=0.94)
    req_b["meta"]["tag"] = [{"system": SYS_SOURCE_TAG, "code": "epic-ehi"}]

    result = merge_episodes([req_a, req_b], canonical_id="merged-q-0")
    merged = result.merged

    quality_exts = [
        ext
        for ext in merged.get("meta", {}).get("extension", [])
        if isinstance(ext, dict) and ext.get("url") == EXT_QUALITY_SCORE
    ]
    assert len(quality_exts) == 1
    assert quality_exts[0]["valueDecimal"] == pytest.approx(0.94)


# ---------------------------------------------------------------------------
# 9. merge_episodes — attaches merge rationale
# ---------------------------------------------------------------------------


def test_merge_episodes_attaches_merge_rationale():
    """Merged resource carries EXT_MERGE_RATIONALE in top-level extension."""
    req_a = _synthea_simvastatin("simva-r1")
    req_b = _synthea_simvastatin("simva-r2")
    req_b["meta"]["tag"] = [{"system": SYS_SOURCE_TAG, "code": "epic-ehi"}]

    result = merge_episodes([req_a, req_b], canonical_id="merged-rat-0")
    merged = result.merged

    rationale_exts = [
        ext
        for ext in merged.get("extension", [])
        if isinstance(ext, dict) and ext.get("url") == EXT_MERGE_RATIONALE
    ]
    assert len(rationale_exts) == 1
    rationale_text = rationale_exts[0].get("valueString", "")
    assert isinstance(rationale_text, str)
    assert len(rationale_text) > 0
    assert RXCUI_SIMVASTATIN in rationale_text


# ---------------------------------------------------------------------------
# 10. reconcile_episodes — passthrough for singleton groups
# ---------------------------------------------------------------------------


def test_reconcile_episodes_passthrough_for_singleton_groups():
    """Each unique RxCUI with only one source resource passes through unchanged."""
    req_simva = _synthea_simvastatin("simva-solo")
    req_atorva = _epic_atorvastatin_discontinued("atorva-solo")

    result_reqs, merges = reconcile_episodes({
        "synthea": [req_simva],
        "epic-ehi": [req_atorva],
    })

    # Two distinct ingredients → two pass-through resources, zero merges
    assert len(merges) == 0
    assert len(result_reqs) == 2
    ids = {r.get("id") for r in result_reqs}
    assert "simva-solo" in ids
    assert "atorva-solo" in ids


# ---------------------------------------------------------------------------
# 11. reconcile_episodes — groups two simvastatin sources
# ---------------------------------------------------------------------------


def test_reconcile_episodes_groups_two_simvastatin_sources():
    """Two simvastatin requests from different sources → one merged resource + one merge result."""
    req_a = _synthea_simvastatin("simva-a", quality=0.80)
    req_b = _synthea_simvastatin("simva-b", quality=0.90)

    result_reqs, merges = reconcile_episodes({
        "synthea": [req_a],
        "epic-ehi": [req_b],
    })

    assert len(merges) == 1
    assert len(result_reqs) == 1
    merged = result_reqs[0]
    assert merged["resourceType"] == "MedicationRequest"

    # Check RxCUI preserved through medicationCodeableConcept
    codings = merged.get("medicationCodeableConcept", {}).get("coding", [])
    rxcuis = {c.get("code") for c in codings if c.get("system") == "http://www.nlm.nih.gov/research/umls/rxnorm"}
    assert RXCUI_SIMVASTATIN in rxcuis


# ---------------------------------------------------------------------------
# 12. ARTIFACT 2 ANCHOR (part 1) — simvastatin and atorvastatin stay separate
# ---------------------------------------------------------------------------


def test_reconcile_episodes_keeps_simvastatin_and_atorvastatin_separate():
    """ARTIFACT 2 ANCHOR: Synthea has simvastatin (active), Epic has atorvastatin
    (discontinued 2025-09-01). reconcile_episodes must produce TWO output
    MedicationRequests — NOT one merged resource.

    Simvastatin and atorvastatin are DIFFERENT ingredients; they share a
    therapeutic class (statin) but must never be merged. The cross-source
    discrepancy is surfaced by detect_cross_class_flags → 3.8 conflict narration.
    """
    synthea_simvastatin = _synthea_simvastatin(
        req_id="synthea-rhett759-simvastatin",
        status="active",
        authored_on="2022-03-01",
        quality=0.85,
    )
    epic_atorvastatin = _epic_atorvastatin_discontinued(
        req_id="epic-rhett759-atorvastatin",
        status="stopped",
        authored_on="2021-05-01",
        period_start="2021-05-01",
        period_end="2025-09-01",
        quality=0.85,
    )

    result_reqs, merges = reconcile_episodes({
        "synthea": [synthea_simvastatin],
        "epic-ehi": [epic_atorvastatin],
    })

    # Must have TWO output resources
    assert len(result_reqs) == 2, (
        f"Expected 2 episodes (simvastatin + atorvastatin), got {len(result_reqs)}: "
        f"{[r.get('id') for r in result_reqs]}"
    )

    # Zero merges — these are different ingredients
    assert len(merges) == 0, (
        "simvastatin and atorvastatin must NOT be merged (different ingredients)"
    )

    # Simvastatin episode is present and still active
    rxcuis_in_output = set()
    for req in result_reqs:
        for coding in req.get("medicationCodeableConcept", {}).get("coding", []):
            if coding.get("system") == "http://www.nlm.nih.gov/research/umls/rxnorm":
                rxcuis_in_output.add(coding.get("code"))

    assert RXCUI_SIMVASTATIN in rxcuis_in_output, "Simvastatin episode missing from output"
    assert RXCUI_ATORVASTATIN in rxcuis_in_output, "Atorvastatin episode missing from output"

    # Atorvastatin episode preserves its period_end
    atorva_req = next(
        r for r in result_reqs
        if any(
            c.get("code") == RXCUI_ATORVASTATIN
            for c in r.get("medicationCodeableConcept", {}).get("coding", [])
        )
    )
    vp = atorva_req.get("dispenseRequest", {}).get("validityPeriod", {})
    assert vp.get("end") == "2025-09-01", (
        "Atorvastatin discontinuation date 2025-09-01 must be preserved"
    )


# ---------------------------------------------------------------------------
# 13. ARTIFACT 2 ANCHOR (part 2) — cross-class flag emitted for statin pair
# ---------------------------------------------------------------------------


def test_detect_cross_class_flags_simvastatin_vs_atorvastatin():
    """ARTIFACT 2 ANCHOR: simvastatin (synthea) + atorvastatin (epic-ehi) both
    tagged class_label=statin → one CrossClassFlag emitted.

    This is the signal that 3.8 conflict detection will consume to narrate:
    'patient was on simvastatin per Synthea FHIR but switched to atorvastatin
    per Epic EHI (discontinued 2025-09-01).'
    """
    ep_simva = MedicationEpisode(
        rxcui=RXCUI_SIMVASTATIN,
        ingredient_label="Simvastatin",
        status="active",
        period_start="2022-03-01",
        period_end=None,
        source_resource_id="synthea-simvastatin",
        source_tag="synthea",
    )
    ep_atorva = MedicationEpisode(
        rxcui=RXCUI_ATORVASTATIN,
        ingredient_label="Atorvastatin",
        status="stopped",
        period_start="2021-05-01",
        period_end="2025-09-01",
        source_resource_id="epic-atorvastatin",
        source_tag="epic-ehi",
    )

    flags = detect_cross_class_flags([ep_simva, ep_atorva])

    assert len(flags) == 1, f"Expected 1 CrossClassFlag, got {len(flags)}: {flags}"

    flag = flags[0]
    assert flag.common_class_label == "statin"
    assert RXCUI_SIMVASTATIN in (flag.ingredient_a, flag.ingredient_b)
    assert RXCUI_ATORVASTATIN in (flag.ingredient_a, flag.ingredient_b)
    # Sources correctly attributed
    all_sources = set(flag.sources_a) | set(flag.sources_b)
    assert "synthea" in all_sources
    assert "epic-ehi" in all_sources


# ---------------------------------------------------------------------------
# 14. detect_cross_class_flags — no flag when same ingredient
# ---------------------------------------------------------------------------


def test_detect_cross_class_flags_no_flag_when_same_ingredient():
    """Two simvastatin episodes (same RxCUI) from different sources → no cross-class flag.

    Same ingredient from multiple sources should merge (test 11), not flag.
    """
    ep_a = MedicationEpisode(
        rxcui=RXCUI_SIMVASTATIN,
        ingredient_label="Simvastatin",
        status="active",
        period_start="2022-03-01",
        period_end=None,
        source_resource_id="synthea-simva",
        source_tag="synthea",
    )
    ep_b = MedicationEpisode(
        rxcui=RXCUI_SIMVASTATIN,
        ingredient_label="Simvastatin",
        status="active",
        period_start="2022-04-01",
        period_end=None,
        source_resource_id="ccda-simva",
        source_tag="ccda",
    )

    flags = detect_cross_class_flags([ep_a, ep_b])
    assert flags == [], f"Expected no flags for same-ingredient pair, got: {flags}"


# ---------------------------------------------------------------------------
# 15. detect_cross_class_flags — no flag when no class match
# ---------------------------------------------------------------------------


def test_detect_cross_class_flags_no_flag_when_no_class_match():
    """An antibiotic episode + a statin episode share no therapeutic class → no flag."""
    ep_statin = MedicationEpisode(
        rxcui=RXCUI_SIMVASTATIN,
        ingredient_label="Simvastatin",
        status="active",
        period_start="2022-03-01",
        period_end=None,
        source_resource_id="synthea-simva",
        source_tag="synthea",
    )
    ep_antibiotic = MedicationEpisode(
        rxcui=RXCUI_AMOXICILLIN,
        ingredient_label="Amoxicillin",
        status="completed",
        period_start="2024-03-01",
        period_end="2024-03-14",
        source_resource_id="epic-amox",
        source_tag="epic-ehi",
    )

    flags = detect_cross_class_flags([ep_statin, ep_antibiotic])
    assert flags == [], (
        f"Antibiotic vs statin should produce no cross-class flag, got: {flags}"
    )
