"""Tests for ehi_atlas.harmonize.temporal — temporal alignment module.

Test plan (13 tests):
  1.  normalize_to_utc: date-only string → midnight UTC
  2.  normalize_to_utc: Z-suffix datetime
  3.  normalize_to_utc: offset datetime (-04:00) → UTC shift
  4.  normalize_to_utc: tz-naive datetime → assume UTC
  5.  Observation with effectiveDateTime → high confidence
  6.  Observation with effectivePeriod.start (no effectiveDateTime) → high confidence
  7.  Observation with no timing → uncertain
  8.  DocumentReference with context.period.start → medium confidence (Mandel rule, primary)
  9.  DocumentReference with no context.period.start but linked Encounter → medium confidence
 10.  DocumentReference with NEITHER context.period.start NOR linked Encounter → uncertain
       AND docRef.date is NEVER used (the load-bearing Mandel-rule test)
 11.  Condition prefers onsetDateTime over recordedDate
 12.  normalize_bundle_temporal attaches exactly 3 clinical-time extensions per resource
 13.  normalize_bundle_temporal is idempotent (re-running doesn't duplicate extensions)
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

from ehi_atlas.harmonize.temporal import (
    EXT_CLINICAL_TIME,
    EXT_CLINICAL_TIME_CONFIDENCE,
    EXT_CLINICAL_TIME_SOURCE,
    ClinicalTime,
    clinical_time,
    clinical_time_for_document_reference,
    normalize_bundle_temporal,
    normalize_to_utc,
)


# ---------------------------------------------------------------------------
# 1. normalize_to_utc: date-only string
# ---------------------------------------------------------------------------


def test_normalize_to_utc_handles_date_only():
    result = normalize_to_utc("2025-09-12")
    assert result == datetime(2025, 9, 12, 0, 0, 0, tzinfo=timezone.utc)
    assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# 2. normalize_to_utc: Z-suffix
# ---------------------------------------------------------------------------


def test_normalize_to_utc_handles_zulu():
    result = normalize_to_utc("2025-09-12T14:30:00Z")
    assert result == datetime(2025, 9, 12, 14, 30, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 3. normalize_to_utc: negative offset → shift to UTC
# ---------------------------------------------------------------------------


def test_normalize_to_utc_handles_offset():
    # 2025-09-12T14:30:00-04:00 → 18:30 UTC
    result = normalize_to_utc("2025-09-12T14:30:00-04:00")
    assert result == datetime(2025, 9, 12, 18, 30, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 4. normalize_to_utc: tz-naive datetime input → treated as UTC
# ---------------------------------------------------------------------------


def test_normalize_to_utc_assumes_naive_is_utc():
    naive = datetime(2025, 9, 12, 10, 0, 0)  # no tzinfo
    result = normalize_to_utc(naive)
    assert result.tzinfo is not None
    assert result == datetime(2025, 9, 12, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 5. Observation.effectiveDateTime → high confidence
# ---------------------------------------------------------------------------


def test_observation_effective_datetime_is_high_confidence():
    resource = {
        "resourceType": "Observation",
        "effectiveDateTime": "2025-09-12T08:00:00Z",
    }
    ct = clinical_time(resource)
    assert ct.confidence == "high"
    assert ct.timestamp == datetime(2025, 9, 12, 8, 0, 0, tzinfo=timezone.utc)
    assert "effectiveDateTime" in ct.source_field


# ---------------------------------------------------------------------------
# 6. Observation.effectivePeriod.start → high confidence (when no effectiveDateTime)
# ---------------------------------------------------------------------------


def test_observation_effective_period_start_is_high_confidence():
    resource = {
        "resourceType": "Observation",
        "effectivePeriod": {"start": "2025-09-12", "end": "2025-09-12"},
    }
    ct = clinical_time(resource)
    assert ct.confidence == "high"
    assert ct.timestamp == datetime(2025, 9, 12, tzinfo=timezone.utc)
    assert "effectivePeriod.start" in ct.source_field


# ---------------------------------------------------------------------------
# 7. Observation with no timing → uncertain
# ---------------------------------------------------------------------------


def test_observation_no_timing_returns_uncertain():
    resource = {"resourceType": "Observation", "status": "final"}
    ct = clinical_time(resource)
    assert ct.confidence == "uncertain"
    assert ct.timestamp is None


# ---------------------------------------------------------------------------
# 8. DocumentReference with context.period.start → medium confidence (primary)
# ---------------------------------------------------------------------------


def test_document_reference_uses_context_period_start_when_present():
    """Mandel rule: primary path — context.period.start is clinical time."""
    resource = {
        "resourceType": "DocumentReference",
        "date": "2026-01-15T10:30:00Z",  # index time — must NOT be used
        "context": {
            "period": {"start": "2026-01-15"},
        },
    }
    ct = clinical_time(resource)
    assert ct.confidence == "medium"
    assert ct.timestamp == datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert "context.period.start" in ct.source_field


# ---------------------------------------------------------------------------
# 9. DocumentReference → falls back to linked Encounter.period.start
# ---------------------------------------------------------------------------


def test_document_reference_falls_back_to_linked_encounter_period_start():
    """Mandel rule: secondary path — linked Encounter.period.start."""
    doc_ref = {
        "resourceType": "DocumentReference",
        "date": "2026-01-15T10:30:00Z",  # must NOT be used
        "context": {
            "encounter": [{"reference": "Encounter/enc-001"}],
            # No period here — forces fallback to linked Encounter
        },
    }
    encounter = {
        "resourceType": "Encounter",
        "id": "enc-001",
        "period": {"start": "2025-11-20T09:00:00Z"},
    }
    encounter_lookup = {"Encounter/enc-001": encounter}

    ct = clinical_time(doc_ref, encounter_lookup=encounter_lookup)
    assert ct.confidence == "medium"
    assert ct.timestamp == datetime(2025, 11, 20, 9, 0, 0, tzinfo=timezone.utc)
    assert "Encounter" in ct.source_field
    assert "enc-001" in ct.source_field


# ---------------------------------------------------------------------------
# 10. DocumentReference NEVER uses docRef.date — the load-bearing Mandel test
# ---------------------------------------------------------------------------


def test_document_reference_NEVER_uses_docref_date_as_clinical_time():
    """
    THE MANDEL RULE TEST.

    Even when context.period.start is absent AND no encounter lookup is provided
    (or the linked encounter doesn't exist), the result must be uncertain.
    docRef.date is INTENTIONALLY excluded — it is metadata time, not clinical time.
    """
    resource = {
        "resourceType": "DocumentReference",
        "date": "2026-01-15T10:30:00Z",  # present, but MUST NOT be used
        "status": "current",
        # No context.period.start
        # No context.encounter
    }

    # Test 1: no encounter_lookup at all
    ct_no_lookup = clinical_time(resource)
    assert ct_no_lookup.confidence == "uncertain", (
        "docRef.date MUST NOT be used as clinical time — "
        "result should be 'uncertain' when context.period.start and linked Encounter are absent"
    )
    assert ct_no_lookup.timestamp is None, (
        "timestamp must be None when uncertain — never docRef.date"
    )

    # Test 2: empty encounter_lookup (no matching encounter)
    ct_empty_lookup = clinical_time(resource, encounter_lookup={})
    assert ct_empty_lookup.confidence == "uncertain"
    assert ct_empty_lookup.timestamp is None

    # Sanity check: the docRef.date value must not appear anywhere in the result
    docref_date_utc = normalize_to_utc("2026-01-15T10:30:00Z")
    assert ct_no_lookup.timestamp != docref_date_utc
    assert ct_empty_lookup.timestamp != docref_date_utc


# ---------------------------------------------------------------------------
# 11. Condition prefers onsetDateTime over recordedDate
# ---------------------------------------------------------------------------


def test_condition_prefers_onset_datetime_over_recordedDate():
    resource = {
        "resourceType": "Condition",
        "onsetDateTime": "2020-03-01",
        "recordedDate": "2020-03-05",  # later, metadata — should NOT win
    }
    ct = clinical_time(resource)
    assert ct.confidence == "high"
    assert ct.timestamp == datetime(2020, 3, 1, tzinfo=timezone.utc)
    assert "onsetDateTime" in ct.source_field
    # recordedDate must not appear in source_field
    assert "recordedDate" not in ct.source_field


# ---------------------------------------------------------------------------
# 12. normalize_bundle_temporal adds exactly 3 extensions per resource
# ---------------------------------------------------------------------------


def test_normalize_bundle_temporal_adds_three_extensions_per_resource():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "effectiveDateTime": "2025-09-12T08:00:00Z",
                }
            },
            {
                "resource": {
                    "resourceType": "DocumentReference",
                    "date": "2026-01-15T10:30:00Z",
                    "context": {"period": {"start": "2026-01-15"}},
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "onsetDateTime": "2020-03-01",
                }
            },
        ],
    }

    result = normalize_bundle_temporal(bundle)

    for entry in result["entry"]:
        resource = entry["resource"]
        meta = resource.get("meta", {})
        extensions = meta.get("extension", [])

        urls = [ext["url"] for ext in extensions]
        assert EXT_CLINICAL_TIME_CONFIDENCE in urls, (
            f"{resource['resourceType']} missing confidence extension"
        )
        assert EXT_CLINICAL_TIME_SOURCE in urls, (
            f"{resource['resourceType']} missing source-field extension"
        )

        # Count only the three clinical-time extension URLs
        ct_ext_count = sum(
            1
            for u in urls
            if u in {EXT_CLINICAL_TIME, EXT_CLINICAL_TIME_CONFIDENCE, EXT_CLINICAL_TIME_SOURCE}
        )
        # Observation and Condition have timestamps → 3 extensions;
        # DocumentReference with context.period.start → timestamp present → 3 extensions
        assert ct_ext_count == 3, (
            f"{resource['resourceType']} has {ct_ext_count} clinical-time extensions (expected 3)"
        )

    # Verify specific values on Observation entry
    obs_meta = result["entry"][0]["resource"]["meta"]
    obs_exts = {e["url"]: e for e in obs_meta["extension"]}
    assert obs_exts[EXT_CLINICAL_TIME_CONFIDENCE]["valueCode"] == "high"
    assert "effectiveDateTime" in obs_exts[EXT_CLINICAL_TIME_SOURCE]["valueString"]
    assert "2025-09-12" in obs_exts[EXT_CLINICAL_TIME]["valueDateTime"]


# ---------------------------------------------------------------------------
# 13. normalize_bundle_temporal is idempotent
# ---------------------------------------------------------------------------


def test_normalize_bundle_temporal_is_idempotent():
    """Re-running normalize_bundle_temporal must not duplicate extensions."""
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "effectiveDateTime": "2025-09-12T08:00:00Z",
                }
            },
            {
                "resource": {
                    "resourceType": "DocumentReference",
                    "date": "2026-01-15T10:30:00Z",
                    # No context → uncertain on DocRef
                }
            },
        ],
    }

    first_pass = normalize_bundle_temporal(bundle)
    second_pass = normalize_bundle_temporal(first_pass)

    for entry in second_pass["entry"]:
        resource = entry["resource"]
        meta = resource.get("meta", {})
        extensions = meta.get("extension", [])

        # Count clinical-time URLs — must be at most 3 (confident) or 2 (uncertain)
        ct_urls = [
            ext["url"]
            for ext in extensions
            if ext["url"] in {EXT_CLINICAL_TIME, EXT_CLINICAL_TIME_CONFIDENCE, EXT_CLINICAL_TIME_SOURCE}
        ]
        # No duplicates
        assert len(ct_urls) == len(set(ct_urls)), (
            f"{resource['resourceType']}: duplicate clinical-time extensions after second pass"
        )

    # Confirm the bundle object returned is the same object (in-place mutation)
    assert second_pass is first_pass
