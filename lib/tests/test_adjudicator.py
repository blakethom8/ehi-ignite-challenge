"""Tests for ``lib.harmonize.adjudicator`` (T7)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import json

from lib.harmonize.adjudicator import (
    CAVEAT_BLOCKER_URL,
    CAVEAT_CODE_SYSTEM,
    Caveat,
    Disagreement,
    FakeConflictAdjudicator,
    adjudicate_merged_record,
    write_caveats,
)
from lib.harmonize.medications import merge_medications
from lib.harmonize.observations import SourceBundle


def _med(
    request_id: str,
    rxnorm: str,
    display: str,
    status: str,
    authored: datetime,
    meta_source: str | None = None,
) -> dict:
    res: dict = {
        "resourceType": "MedicationRequest",
        "id": request_id,
        "status": status,
        "authoredOn": authored.isoformat(),
        "medicationCodeableConcept": {
            "text": display,
            "coding": [
                {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": rxnorm}
            ],
        },
    }
    if meta_source:
        res["meta"] = {"source": meta_source}
    return res


def _bundle(label: str, *resources: dict) -> SourceBundle:
    return SourceBundle(label=label, observations=list(resources))


# ---------------------------------------------------------------------------
# Patient-voice status override caveat (the headline §6 beat-6 path)
# ---------------------------------------------------------------------------


def test_patient_voice_status_override_emits_caveat():
    cedars = _bundle(
        "Cedars",
        _med("mr-cedars", "29046", "Lisinopril 10mg", "active", datetime(2025, 9, 1, tzinfo=timezone.utc)),
    )
    fh = _bundle(
        "FH",
        _med("mr-fh", "29046", "Lisinopril 10mg", "active", datetime(2025, 11, 1, tzinfo=timezone.utc)),
    )
    patient = _bundle(
        "Patient",
        _med(
            "mr-pv",
            "29046",
            "lisinopril",
            "stopped",
            datetime(2026, 5, 11, tzinfo=timezone.utc),
            meta_source="patient-context://sess_a91c",
        ),
    )
    merged_list = merge_medications([cedars, fh, patient])

    caveats = adjudicate_merged_record(
        "demo",
        merged_medications=merged_list,
    )
    assert len(caveats) == 1
    c = caveats[0]
    assert c.fact_path.endswith(".status")
    assert "lisinopril" in c.fact_path.lower() or "rxnorm" in c.fact_path.lower()
    assert c.verdict == "stopped"
    assert c.confidence == "high"
    assert "Patient asserted" in c.rationale
    # Cedars + FH should both be in the dissenting list (they each carried active status).
    assert any("mr-cedars" in s for s in c.dissenting_sources)
    assert any("mr-fh" in s for s in c.dissenting_sources)


def test_no_caveat_when_sources_agree():
    cedars = _bundle(
        "Cedars",
        _med("mr-c", "29046", "Lisinopril 10mg", "stopped", datetime(2025, 9, 1, tzinfo=timezone.utc)),
    )
    patient = _bundle(
        "Patient",
        _med(
            "mr-p",
            "29046",
            "lisinopril",
            "stopped",
            datetime(2026, 5, 11, tzinfo=timezone.utc),
            meta_source="patient-context://sess_a91c",
        ),
    )
    merged = merge_medications([cedars, patient])
    caveats = adjudicate_merged_record("demo", merged_medications=merged)
    assert caveats == []


def test_no_caveat_when_no_patient_voice_source():
    cedars = _bundle(
        "Cedars",
        _med("mr-c", "29046", "Lisinopril 10mg", "active", datetime(2025, 9, 1, tzinfo=timezone.utc)),
    )
    fh = _bundle(
        "FH",
        _med("mr-f", "29046", "Lisinopril 10mg", "stopped", datetime(2025, 11, 1, tzinfo=timezone.utc)),
    )
    merged = merge_medications([cedars, fh])
    caveats = adjudicate_merged_record("demo", merged_medications=merged)
    # No patient voice override fired; no dose disagreement (same display) → no caveat.
    assert caveats == []


def test_dose_disagreement_uses_fake_adjudicator():
    """Two non-patient sources disagreeing on display string → fake adjudicates."""
    cedars = _bundle(
        "Cedars",
        _med("mr-c", "29046", "Lisinopril 10mg", "active", datetime(2025, 9, 1, tzinfo=timezone.utc)),
    )
    fh = _bundle(
        "FH",
        _med("mr-f", "29046", "Lisinopril 20mg", "active", datetime(2025, 11, 1, tzinfo=timezone.utc)),
    )
    merged = merge_medications([cedars, fh])
    caveats = adjudicate_merged_record(
        "demo",
        merged_medications=merged,
        adjudicator=FakeConflictAdjudicator(rationale_template="most recent wins (smoke)"),
    )
    assert len(caveats) == 1
    c = caveats[0]
    assert c.fact_path.endswith(".dose")
    # FH (2025-11) wins by recency under the fake adjudicator.
    assert c.verdict == "Lisinopril 20mg"


# ---------------------------------------------------------------------------
# FHIR Caveat serialization
# ---------------------------------------------------------------------------


def test_caveat_to_fhir_matches_plan_shape():
    c = Caveat(
        fact_path="MedicationRequest/merged-lisinopril.status",
        verdict="stopped",
        confidence="high",
        rationale="Patient asserted; Cedars stale.",
        dissenting_sources=["DocumentReference/cedars", "DocumentReference/fh"],
        blocker=False,
    )
    fhir = c.to_fhir()
    assert fhir["resourceType"] == "Observation"
    assert fhir["status"] == "final"
    coding = fhir["code"]["coding"][0]
    assert coding["system"] == CAVEAT_CODE_SYSTEM
    assert coding["code"] == "merge-judgment"
    comps = {c["code"]["text"]: c["valueString"] for c in fhir["component"]}
    assert comps["fact_path"] == c.fact_path
    assert comps["verdict"] == "stopped"
    assert comps["confidence"] == "high"
    assert comps["rationale"] == c.rationale
    assert comps["dissenting_sources"] == "DocumentReference/cedars;DocumentReference/fh"
    blocker_ext = next(e for e in fhir["extension"] if e["url"] == CAVEAT_BLOCKER_URL)
    assert blocker_ext["valueBoolean"] is False


def test_write_caveats_persists_bundle(tmp_path: Path):
    caveats = [
        Caveat(
            fact_path="MedicationRequest/merged-lisinopril.status",
            verdict="stopped",
            confidence="high",
            rationale="demo",
        )
    ]
    path = write_caveats("demo", caveats, store_root=tmp_path)
    assert path.exists()
    bundle = json.loads(path.read_text(encoding="utf-8"))
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(bundle["entry"]) == 1
    res = bundle["entry"][0]["resource"]
    assert res["component"][0]["valueString"] == "MedicationRequest/merged-lisinopril.status"


def test_write_caveats_with_no_entries_yields_empty_bundle(tmp_path: Path):
    path = write_caveats("demo", [], store_root=tmp_path)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    assert bundle["entry"] == []
