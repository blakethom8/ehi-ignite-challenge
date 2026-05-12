"""Tests for ``lib.patient_voice.summarize`` (T8a)."""

from __future__ import annotations

import json
from pathlib import Path

from lib.patient_voice.summarize import (
    FakeVoiceSummarizer,
    PatientVoiceSummary,
    load_summary,
    regenerate_voice_summary,
    summary_path_for,
    write_summary,
)


def _bundle_with_turn(content: str, turn_id: str) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"source": "patient-context://sess_a91c"},
        "entry": [
            {
                "resource": {
                    "resourceType": "MedicationStatement",
                    "id": f"pv-sess_a91c-{turn_id}-0",
                    "status": "stopped",
                    "medicationCodeableConcept": {"text": "lisinopril"},
                    "subject": {"reference": "Patient/demo"},
                    "note": [{"text": content}],
                    "meta": {
                        "source": "patient-context://sess_a91c",
                        "extension": [
                            {
                                "url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-locator",
                                "valueString": f"session=sess_a91c;turn={turn_id};gap=medication-reality",
                            }
                        ],
                    },
                }
            }
        ],
    }


def _write_bundle(store: Path, patient_id: str, session_id: str, bundle: dict) -> None:
    fhir_dir = store / patient_id / "fhir"
    fhir_dir.mkdir(parents=True, exist_ok=True)
    (fhir_dir / f"{session_id}.json").write_text(json.dumps(bundle, indent=2))


def test_write_then_load_round_trips(tmp_path: Path):
    s = PatientVoiceSummary(summary="hello world", citations=["turn-x"], generated_at="2026-05-12T00:00:00+00:00")
    path = write_summary("demo", s, store_root=tmp_path)
    assert path.exists()
    loaded = load_summary("demo", store_root=tmp_path)
    assert loaded is not None
    assert loaded.summary == "hello world"
    assert loaded.citations == ["turn-x"]


def test_summary_path_uses_safe_id(tmp_path: Path):
    path = summary_path_for("Pat ient/ID*1", store_root=tmp_path)
    # No raw special chars in the directory name.
    assert "*" not in str(path)
    assert path.name == "voice_summary.json"


def test_load_missing_summary_returns_none(tmp_path: Path):
    assert load_summary("nobody", store_root=tmp_path) is None


def test_regenerate_voice_summary_with_fake_backend(tmp_path: Path):
    _write_bundle(
        tmp_path,
        "demo",
        "sess_a91c",
        _bundle_with_turn(
            "I stopped lisinopril about 3 weeks ago — was making me cough.", "t_4f2c9b"
        ),
    )
    fake = FakeVoiceSummarizer(
        summary="Patient stopped lisinopril ~3 weeks ago.",
        citations=["turn-t_4f2c9b"],
    )
    summary = regenerate_voice_summary("demo", summarizer=fake, store_root=tmp_path)
    assert summary is not None
    assert "lisinopril" in summary.summary.lower()
    # Written to disk so the context builder can read it.
    on_disk = load_summary("demo", store_root=tmp_path)
    assert on_disk is not None
    assert on_disk.summary == summary.summary


def test_regenerate_with_no_turns_returns_none(tmp_path: Path):
    """No FHIR directory → nothing to summarize."""
    assert regenerate_voice_summary("demo", store_root=tmp_path) is None


def test_regenerate_collects_turns_across_multiple_sessions(tmp_path: Path):
    _write_bundle(tmp_path, "demo", "sess-one", _bundle_with_turn("Stopped lisinopril.", "t1"))
    _write_bundle(tmp_path, "demo", "sess-two", _bundle_with_turn("Started fish oil.", "t2"))
    fake = FakeVoiceSummarizer()
    summary = regenerate_voice_summary("demo", summarizer=fake, store_root=tmp_path)
    assert summary is not None
    # Fake summarizer cites every turn it sees.
    assert len(summary.citations) == 2
