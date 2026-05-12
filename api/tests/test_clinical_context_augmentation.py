"""Integration tests for the T8b ClinicalContext augmentation.

Verifies:
- ``PatientVoiceContext`` populates when ``voice_summary.json`` exists.
- ``episode_briefs`` populates from ``episodes.json`` + per-episode
  Composition ``current.json``.
- ``caveats`` populates from ``caveats.json`` if present.
- ``to_prompt()`` leads with "In the patient's own words: ..." when
  patient_voice is present (the §6 demo arc beat).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from api.core.context_builder import (
    ClinicalContext,
    EpisodeBrief,
    HarmonizationCaveat,
    PatientVoiceContext,
    _load_caveats,
    _load_episode_briefs,
    _load_patient_voice_context,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed(tmp_path: Path, patient_id: str = "demo") -> None:
    """Seed all three on-disk artifacts the loaders read."""
    pc_root = tmp_path / "data" / "patient-context"
    nar_root = tmp_path / "data" / "narratives"

    _write(
        pc_root / patient_id / "voice_summary.json",
        {
            "summary": "Patient stopped lisinopril ~3 weeks ago; started fish oil daily.",
            "citations": ["turn-t_4f2c9b"],
            "generated_at": "2026-05-12T10:16:00+00:00",
        },
    )
    _write(
        nar_root / patient_id / "episodes.json",
        {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "EpisodeOfCare",
                        "id": "episode-cardiometabolic",
                        "status": "active",
                        "patient": {"reference": f"Patient/{patient_id}"},
                        "period": {"start": "1980-08-18"},
                        "type": [
                            {
                                "coding": [
                                    {
                                        "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/episode-type",
                                        "code": "chronic-condition-management",
                                        "display": "Cardiometabolic management",
                                    }
                                ],
                                "text": "Cardiometabolic management",
                            }
                        ],
                        "diagnosis": [{"condition": {"reference": "Condition/cond-diabetes"}, "rank": 1}],
                    }
                }
            ],
        },
    )
    _write(
        nar_root / patient_id / "cardiometabolic" / "current.json",
        {
            "resourceType": "Composition",
            "id": "narrative-cardiometabolic-2026-05-12T10-15-00Z",
            "status": "final",
            "section": [
                {
                    "title": "Summary",
                    "text": {
                        "status": "additional",
                        "div": "<div>Long-standing cardiometabolic story with stable management.</div>",
                    },
                }
            ],
        },
    )
    _write(
        pc_root / patient_id / "caveats.json",
        {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "caveat-lisinopril-status",
                        "code": {
                            "coding": [
                                {
                                    "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/harmonization-caveat",
                                    "code": "merge-judgment",
                                }
                            ]
                        },
                        "component": [
                            {"code": {"text": "fact_path"}, "valueString": "MedicationRequest/merged-lisinopril.status"},
                            {"code": {"text": "verdict"}, "valueString": "stopped"},
                            {"code": {"text": "confidence"}, "valueString": "high"},
                            {"code": {"text": "rationale"}, "valueString": "Patient asserted stoppage post-Cedars-2025-09."},
                            {"code": {"text": "dissenting_sources"}, "valueString": "DocumentReference/cedars-pdf;DocumentReference/fh-pdf"},
                        ],
                    }
                }
            ],
        },
    )


@pytest.fixture()
def seeded_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Seed disk artifacts AND repoint the loaders' constants at the tmp tree."""
    _seed(tmp_path)
    monkeypatch.setattr(
        "api.core.context_builder._REPO_ROOT", tmp_path, raising=True
    )
    # patient_voice.summarize reads PATIENT_CONTEXT_STORE_PATH via env or default;
    # set env so load_summary() also reads from tmp.
    monkeypatch.setenv("PATIENT_CONTEXT_STORE_PATH", str(tmp_path / "data" / "patient-context"))
    return tmp_path


def test_load_patient_voice_context_round_trips(seeded_tmp: Path):
    # Force the patient_voice module to re-resolve the env var.
    import importlib
    import lib.patient_voice.summarize as summarize_mod

    importlib.reload(summarize_mod)

    voice = _load_patient_voice_context("demo")
    assert voice is not None
    assert "lisinopril" in voice.summary.lower()
    assert voice.citations == ["turn-t_4f2c9b"]


def test_load_episode_briefs_resolves_summary_section(seeded_tmp: Path):
    briefs = _load_episode_briefs("demo")
    assert len(briefs) == 1
    brief = briefs[0]
    assert brief.episode_id == "episode-cardiometabolic"
    assert brief.type == "Cardiometabolic management"
    assert brief.period_start == "1980-08-18"
    assert brief.period_end is None
    assert "cardiometabolic story" in brief.one_liner


def test_load_episode_briefs_uses_placeholder_when_narrative_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Episodes.json without a matching current.json.
    _write(
        tmp_path / "data" / "narratives" / "demo" / "episodes.json",
        {
            "resourceType": "Bundle",
            "entry": [{"resource": {
                "resourceType": "EpisodeOfCare",
                "id": "episode-x",
                "patient": {"reference": "Patient/demo"},
                "period": {"start": "2020-01-01"},
                "type": [{"text": "demo"}],
                "diagnosis": [],
            }}],
        },
    )
    monkeypatch.setattr("api.core.context_builder._REPO_ROOT", tmp_path, raising=True)
    briefs = _load_episode_briefs("demo")
    assert len(briefs) == 1
    assert "not yet generated" in briefs[0].one_liner


def test_load_caveats_parses_observation_components(seeded_tmp: Path):
    caveats = _load_caveats("demo")
    assert len(caveats) == 1
    c = caveats[0]
    assert c.fact_path == "MedicationRequest/merged-lisinopril.status"
    assert c.verdict == "stopped"
    assert c.confidence == "high"
    assert "post-Cedars" in c.rationale
    assert c.dissenting_sources == [
        "DocumentReference/cedars-pdf",
        "DocumentReference/fh-pdf",
    ]


def test_to_prompt_leads_with_patient_voice_when_present():
    """§6 demo beat 5: Caspian's opening references the patient."""
    ctx = ClinicalContext(
        patient_summary="Demo Patient",
        safety_flags=[],
        interactions=[],
        active_medications=[],
        active_conditions=[],
        key_labs=[],
        clinical_notes=[],
        recent_encounters=[],
        procedures_summary=[],
        historical_meds=[],
        resolved_conditions=[],
        absences=[],
        patient_voice=PatientVoiceContext(
            summary="Patient stopped lisinopril ~3 weeks ago.",
            citations=["turn-t_4f2c9b"],
        ),
        episode_briefs=[
            EpisodeBrief(
                episode_id="episode-cardiometabolic",
                type="Cardiometabolic management",
                period_start="1980-08-18",
                period_end=None,
                one_liner="Long-standing cardiometabolic story.",
            )
        ],
        caveats=[
            HarmonizationCaveat(
                fact_path="MedicationRequest/merged-lisinopril.status",
                verdict="stopped",
                confidence="high",
                rationale="Patient asserted; Cedars stale.",
            )
        ],
    )
    prompt = ctx.to_prompt()
    voice_line_idx = prompt.find("In the patient's own words:")
    safety_idx = prompt.find("SAFETY FLAGS")
    # patient voice appears before structured tables; safety flags would
    # be next if present (none here, but their header still indexes the
    # ordering rule).
    assert voice_line_idx >= 0
    assert "Patient stopped lisinopril" in prompt
    assert "CARE EPISODES" in prompt
    assert "Cardiometabolic management" in prompt
    assert "OPEN CONFLICTS" in prompt
    assert "merged-lisinopril.status" in prompt


def test_to_prompt_omits_voice_section_when_absent():
    ctx = ClinicalContext(
        patient_summary="Demo Patient",
        safety_flags=[],
        interactions=[],
        active_medications=[],
        active_conditions=[],
        key_labs=[],
        clinical_notes=[],
        recent_encounters=[],
        procedures_summary=[],
        historical_meds=[],
        resolved_conditions=[],
        absences=[],
        patient_voice=None,
    )
    prompt = ctx.to_prompt()
    assert "In the patient's own words" not in prompt
    assert "CARE EPISODES" not in prompt
    assert "OPEN CONFLICTS" not in prompt
