"""Patient context flows into the authenticated workspace bundle."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.core import patient_context as patient_context_module
from api.main import app


SYNTHEA_DEMO_PATIENT_ID = "7978d71c-094b-459e-92be-2b62f4cf5e6c"


def _zip_root(payload: bytes) -> tuple[zipfile.ZipFile, str]:
    zf = zipfile.ZipFile(io.BytesIO(payload))
    roots = {name.split("/", 1)[0] for name in zf.namelist() if "/" in name}
    assert len(roots) == 1, f"expected single zip root, got {roots}"
    return zf, roots.pop()


def _authenticated_client() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
    )
    assert response.status_code == 200, response.text
    return client


class PatientContextBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="ctx-bundle-test-"))
        self._old_root = patient_context_module.STORE_ROOT
        patient_context_module.STORE_ROOT = self._tmp / "patient-context"

        # Seed one session for the synthea-demo patient.
        safe_pid = patient_context_module._safe_id(SYNTHEA_DEMO_PATIENT_ID)
        session_id = "session-test-001"
        session_dir = patient_context_module.STORE_ROOT / safe_pid / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        self.session_json = {
            "session_id": session_id,
            "patient_id": SYNTHEA_DEMO_PATIENT_ID,
            "patient_label": "Adria Ankunding",
            "source_mode": "selected_patient",
            "source_posture": "Synthetic FHIR chart",
            "created_at": "2026-05-11T18:00:00+00:00",
            "gap_cards": [],
            "turns": [],
            "facts": [
                {
                    "id": "fact-1",
                    "summary": "Patient reports daily morning headaches for two weeks.",
                    "statement": "I've had a headache every morning for the last two weeks.",
                    "created_at": "2026-05-11T18:05:00+00:00",
                },
                {
                    "id": "fact-2",
                    "summary": "Patient pauses Warfarin 24h before any procedure.",
                    "statement": "I always stop my blood thinner the day before any procedure.",
                    "created_at": "2026-05-11T18:07:00+00:00",
                },
            ],
            "export_status": None,
        }
        (session_dir / "session.json").write_text(
            json.dumps(self.session_json, indent=2), encoding="utf-8"
        )
        (session_dir / "PATIENT_CONTEXT.md").write_text(
            "# Patient Context\n\nMorning headaches for two weeks.\n",
            encoding="utf-8",
        )
        (session_dir / "QUESTIONS.md").write_text("# Questions\n", encoding="utf-8")
        (session_dir / "SOURCES.md").write_text("# Sources\n", encoding="utf-8")
        (session_dir / "AGENT.md").write_text("# Agent Instructions\n", encoding="utf-8")

        # Seed a tiny FHIR voice bundle so it gets injected as a source.
        fhir_dir = patient_context_module.STORE_ROOT / safe_pid / "fhir"
        fhir_dir.mkdir(parents=True, exist_ok=True)
        voice_bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "voice-obs-1",
                        "status": "preliminary",
                        "code": {"text": "Headache (patient-reported)"},
                        "effectiveDateTime": "2026-05-11",
                    }
                }
            ],
        }
        (fhir_dir / f"{patient_context_module._safe_id(session_id)}.json").write_text(
            json.dumps(voice_bundle, indent=2), encoding="utf-8"
        )

        self.client = _authenticated_client()

    def tearDown(self) -> None:
        patient_context_module.STORE_ROOT = self._old_root
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_export_includes_context_md_and_patient_voice(self) -> None:
        response = self.client.get("/api/harmonize/synthea-demo/export-workspace")
        self.assertEqual(response.status_code, 200, response.text)

        zf, root = _zip_root(response.content)
        with zf:
            names = set(zf.namelist())
            self.assertIn(f"{root}/context/PATIENT_CONTEXT.md", names)
            self.assertIn(f"{root}/context/QUESTIONS.md", names)
            self.assertIn(f"{root}/context/SOURCES.md", names)
            self.assertIn(f"{root}/context/AGENT.md", names)
            self.assertIn(f"{root}/context/session.json", names)

            patient_summary = json.loads(
                zf.read(f"{root}/packets/patient-summary.context.json")
            )
            self.assertIn("morning headaches", patient_summary["patient_voice"].lower())
            self.assertEqual(
                {fact["id"] for fact in patient_summary["patient_context_facts"]},
                {"fact-1", "fact-2"},
            )

            # The voice FHIR Bundle is injected as a source — its facts should
            # appear with provenance method patient_context_voice.
            provenance = json.loads(
                zf.read(f"{root}/evidence/provenance.json")
            )["provenance"]
            methods = {entry["method"] for entry in provenance}
            self.assertIn("patient_context_voice", methods)

            # The manifest must reference the new files.
            manifest = json.loads(zf.read(f"{root}/MANIFEST.json"))
            manifest_paths = {
                entry["path"] for entry in manifest["files"] if isinstance(entry, dict)
            }
            self.assertIn("context/PATIENT_CONTEXT.md", manifest_paths)
            self.assertIn("context/session.json", manifest_paths)

    def test_export_without_session_is_unchanged(self) -> None:
        # Empty out the seeded session by pointing STORE_ROOT at an empty dir.
        patient_context_module.STORE_ROOT = self._tmp / "empty"
        patient_context_module.STORE_ROOT.mkdir(parents=True, exist_ok=True)

        response = self.client.get("/api/harmonize/synthea-demo/export-workspace")
        self.assertEqual(response.status_code, 200, response.text)

        zf, root = _zip_root(response.content)
        with zf:
            names = set(zf.namelist())
            self.assertFalse(
                any(name.startswith(f"{root}/context/") for name in names),
                f"context/ directory should be absent when no session, got: "
                f"{[n for n in names if 'context/' in n]}",
            )
            patient_summary = json.loads(
                zf.read(f"{root}/packets/patient-summary.context.json")
            )
            self.assertEqual(patient_summary["patient_voice"], "")
            self.assertEqual(patient_summary["patient_context_facts"], [])


if __name__ == "__main__":
    unittest.main()
