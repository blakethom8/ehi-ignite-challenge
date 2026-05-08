"""Tests for _assign_encounter_references — the deterministic post-pass that
wires encounter: {reference: "Encounter/<id>"} onto encounter-scopable
resources after all per-resource emission loops have completed.

Two linkage strategies are tested:
1. Single-encounter shortcut — if exactly one Encounter exists, every linkable
   resource gets that reference regardless of date.
2. Date-match fallback — if multiple Encounters exist, each resource is matched
   to the Encounter whose period.start shares the same day (YYYY-MM-DD prefix)
   as the resource's type-appropriate date field.
"""

from __future__ import annotations

from lib.extract.pipelines.multipass_fhir import MultiPassFHIRPipeline


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    p = MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)
    p._patient_id = "test-patient"
    return p


def _make_entries(*resources: dict) -> list[dict]:
    return [{"resource": r} for r in resources]


# ---------------------------------------------------------------------------
# 1. No encounters — no linkage attempted, no exception
# ---------------------------------------------------------------------------


def test_no_encounters_no_linkage_attempted() -> None:
    """Entries with Observations but no Encounter → no encounter field added; no exception raised."""
    pipeline = _new_pipeline()
    obs1 = {"resourceType": "Observation", "code": {"text": "Glucose"}, "effectiveDateTime": "2025-12-12"}
    obs2 = {"resourceType": "Observation", "code": {"text": "BUN"}}
    entries = _make_entries(obs1, obs2)

    pipeline._assign_encounter_references(entries)

    assert "encounter" not in obs1
    assert "encounter" not in obs2


# ---------------------------------------------------------------------------
# 2. Single encounter — all Observations linked (no dates needed)
# ---------------------------------------------------------------------------


def test_single_encounter_links_all_observations() -> None:
    """1 Encounter + 3 Observations → all Observations get the encounter reference."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-abc123", "period": {"start": "2025-12-12"}}
    obs1 = {"resourceType": "Observation", "code": {"text": "Glucose"}}
    obs2 = {"resourceType": "Observation", "code": {"text": "BUN"}}
    obs3 = {"resourceType": "Observation", "code": {"text": "Creatinine"}}
    entries = _make_entries(enc, obs1, obs2, obs3)

    pipeline._assign_encounter_references(entries)

    assert obs1["encounter"]["reference"] == "Encounter/enc-abc123"
    assert obs2["encounter"]["reference"] == "Encounter/enc-abc123"
    assert obs3["encounter"]["reference"] == "Encounter/enc-abc123"


# ---------------------------------------------------------------------------
# 3. Single encounter — mixed resource types (Observation + Condition + MedicationRequest)
# ---------------------------------------------------------------------------


def test_single_encounter_links_condition_and_medication() -> None:
    """Single encounter links across Observation, Condition, and MedicationRequest."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-xyz789", "period": {"start": "2026-03-01"}}
    obs = {"resourceType": "Observation", "code": {"text": "HbA1c"}}
    cond = {"resourceType": "Condition", "code": {"text": "Diabetes"}}
    med = {"resourceType": "MedicationRequest", "medicationCodeableConcept": {"text": "Metformin"}}
    entries = _make_entries(enc, obs, cond, med)

    pipeline._assign_encounter_references(entries)

    assert obs["encounter"]["reference"] == "Encounter/enc-xyz789"
    assert cond["encounter"]["reference"] == "Encounter/enc-xyz789"
    assert med["encounter"]["reference"] == "Encounter/enc-xyz789"


# ---------------------------------------------------------------------------
# 4. Single encounter — Practitioner and Organization are NOT linked
# ---------------------------------------------------------------------------


def test_single_encounter_does_not_link_practitioner_or_organization() -> None:
    """Patient, Practitioner, and Organization resources must not get an encounter field."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-def456", "period": {"start": "2026-01-15"}}
    patient = {"resourceType": "Patient", "id": "pt-001"}
    practitioner = {"resourceType": "Practitioner", "id": "prac-001"}
    org = {"resourceType": "Organization", "id": "org-001", "name": "Test Clinic"}
    entries = _make_entries(enc, patient, practitioner, org)

    pipeline._assign_encounter_references(entries)

    assert "encounter" not in patient
    assert "encounter" not in practitioner
    assert "encounter" not in org


# ---------------------------------------------------------------------------
# 5. Multiple encounters — date-match routes each Observation to the correct encounter
# ---------------------------------------------------------------------------


def test_multiple_encounters_date_match() -> None:
    """2 Encounters with different dates; 2 Observations with matching effectiveDateTime → correct linkage."""
    pipeline = _new_pipeline()
    enc_a = {"resourceType": "Encounter", "id": "enc-2025-01", "period": {"start": "2025-01-10"}}
    enc_b = {"resourceType": "Encounter", "id": "enc-2025-06", "period": {"start": "2025-06-20"}}
    obs_jan = {"resourceType": "Observation", "code": {"text": "Creatinine"}, "effectiveDateTime": "2025-01-10"}
    obs_jun = {"resourceType": "Observation", "code": {"text": "Glucose"}, "effectiveDateTime": "2025-06-20"}
    entries = _make_entries(enc_a, enc_b, obs_jan, obs_jun)

    pipeline._assign_encounter_references(entries)

    assert obs_jan["encounter"]["reference"] == "Encounter/enc-2025-01"
    assert obs_jun["encounter"]["reference"] == "Encounter/enc-2025-06"


# ---------------------------------------------------------------------------
# 6. Multiple encounters — Observation with no date gets no link
# ---------------------------------------------------------------------------


def test_multiple_encounters_no_date_no_link() -> None:
    """Multiple encounters but Observation has no effectiveDateTime → no encounter field added."""
    pipeline = _new_pipeline()
    enc_a = {"resourceType": "Encounter", "id": "enc-aaa", "period": {"start": "2025-03-05"}}
    enc_b = {"resourceType": "Encounter", "id": "enc-bbb", "period": {"start": "2025-09-15"}}
    obs = {"resourceType": "Observation", "code": {"text": "Sodium"}}  # no effectiveDateTime
    entries = _make_entries(enc_a, enc_b, obs)

    pipeline._assign_encounter_references(entries)

    assert "encounter" not in obs


# ---------------------------------------------------------------------------
# 7. Existing encounter reference is preserved — no overwrite
# ---------------------------------------------------------------------------


def test_existing_encounter_reference_preserved() -> None:
    """Observation already has encounter set → helper does NOT overwrite it."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-new", "period": {"start": "2026-04-01"}}
    obs = {
        "resourceType": "Observation",
        "code": {"text": "TSH"},
        "encounter": {"reference": "Encounter/enc-original"},
    }
    entries = _make_entries(enc, obs)

    pipeline._assign_encounter_references(entries)

    # Original reference must be intact
    assert obs["encounter"]["reference"] == "Encounter/enc-original"


# ---------------------------------------------------------------------------
# 8. DocumentReference — single-encounter shortcut
# ---------------------------------------------------------------------------


def test_documentreference_single_encounter_shortcut() -> None:
    """1 Encounter + 1 DocumentReference (no date) → DocumentReference.context.encounter linked."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-doc-001", "period": {"start": "2026-01-10"}}
    doc = {"resourceType": "DocumentReference", "status": "current"}
    entries = _make_entries(enc, doc)

    pipeline._assign_encounter_references(entries)

    ctx = doc.get("context") or {}
    enc_refs = ctx.get("encounter") or []
    assert len(enc_refs) == 1
    assert enc_refs[0]["reference"] == "Encounter/enc-doc-001"


# ---------------------------------------------------------------------------
# 9. Composition — single-encounter shortcut
# ---------------------------------------------------------------------------


def test_composition_single_encounter_shortcut() -> None:
    """1 Encounter + 1 Composition → Composition.encounter.reference linked."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-comp-001", "period": {"start": "2026-02-15"}}
    comp = {"resourceType": "Composition", "title": "Discharge Summary", "date": "2026-02-15"}
    entries = _make_entries(enc, comp)

    pipeline._assign_encounter_references(entries)

    assert comp["encounter"]["reference"] == "Encounter/enc-comp-001"


# ---------------------------------------------------------------------------
# 10. DocumentReference — date match with multiple encounters on different days
# ---------------------------------------------------------------------------


def test_documentreference_date_match_with_multiple_encounters() -> None:
    """2 Encounters on different dates, 1 DocumentReference with date matching one → linked correctly."""
    pipeline = _new_pipeline()
    enc_a = {"resourceType": "Encounter", "id": "enc-2026-03", "period": {"start": "2026-03-10"}}
    enc_b = {"resourceType": "Encounter", "id": "enc-2026-07", "period": {"start": "2026-07-22"}}
    doc = {"resourceType": "DocumentReference", "status": "current", "date": "2026-07-22"}
    entries = _make_entries(enc_a, enc_b, doc)

    pipeline._assign_encounter_references(entries)

    ctx = doc.get("context") or {}
    enc_refs = ctx.get("encounter") or []
    assert len(enc_refs) == 1
    assert enc_refs[0]["reference"] == "Encounter/enc-2026-07"


# ---------------------------------------------------------------------------
# 11. DocumentReference — author disambiguates same-day encounters
# ---------------------------------------------------------------------------


def test_documentreference_author_disambiguates_same_day_encounters() -> None:
    """2 Encounters on the same date with different participant.individual.display;
    DocumentReference with matching author → resolved to the correct encounter."""
    pipeline = _new_pipeline()
    enc_a = {
        "resourceType": "Encounter",
        "id": "enc-smith",
        "period": {"start": "2026-04-05"},
        "participant": [{"individual": {"display": "Dr. Smith"}}],
    }
    enc_b = {
        "resourceType": "Encounter",
        "id": "enc-jones",
        "period": {"start": "2026-04-05"},
        "participant": [{"individual": {"display": "Dr. Jones"}}],
    }
    doc = {
        "resourceType": "DocumentReference",
        "status": "current",
        "date": "2026-04-05",
        "author": [{"display": "Dr. Jones"}],
    }
    entries = _make_entries(enc_a, enc_b, doc)

    pipeline._assign_encounter_references(entries)

    ctx = doc.get("context") or {}
    enc_refs = ctx.get("encounter") or []
    assert len(enc_refs) == 1
    assert enc_refs[0]["reference"] == "Encounter/enc-jones"


# ---------------------------------------------------------------------------
# 12. Composition — existing encounter reference preserved
# ---------------------------------------------------------------------------


def test_composition_existing_encounter_reference_preserved() -> None:
    """Composition already has encounter field → helper does NOT overwrite it."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-new-comp", "period": {"start": "2026-05-01"}}
    comp = {
        "resourceType": "Composition",
        "title": "Progress Note",
        "date": "2026-05-01",
        "encounter": {"reference": "Encounter/enc-original-comp"},
    }
    entries = _make_entries(enc, comp)

    pipeline._assign_encounter_references(entries)

    assert comp["encounter"]["reference"] == "Encounter/enc-original-comp"


# ---------------------------------------------------------------------------
# 13. DocumentReference — existing context.encounter preserved
# ---------------------------------------------------------------------------


def test_documentreference_existing_context_encounter_preserved() -> None:
    """DocumentReference already has context.encounter → helper does NOT overwrite it."""
    pipeline = _new_pipeline()
    enc = {"resourceType": "Encounter", "id": "enc-new-doc", "period": {"start": "2026-06-10"}}
    doc = {
        "resourceType": "DocumentReference",
        "status": "current",
        "date": "2026-06-10",
        "context": {
            "encounter": [{"reference": "Encounter/enc-original-doc"}],
        },
    }
    entries = _make_entries(enc, doc)

    pipeline._assign_encounter_references(entries)

    ctx = doc.get("context") or {}
    enc_refs = ctx.get("encounter") or []
    assert len(enc_refs) == 1
    assert enc_refs[0]["reference"] == "Encounter/enc-original-doc"
