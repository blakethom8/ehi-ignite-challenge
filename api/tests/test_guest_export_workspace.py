"""Guest workspace export — produces the same ZIP shape as the auth path."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.core import guest_harmonization
from api.main import app


def _zip_root(payload: bytes) -> tuple[zipfile.ZipFile, str]:
    zf = zipfile.ZipFile(io.BytesIO(payload))
    roots = {name.split("/", 1)[0] for name in zf.namelist() if "/" in name}
    assert len(roots) == 1, f"expected single zip root, got {roots}"
    return zf, roots.pop()


class GuestWorkspaceExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="guest-export-test-"))
        self._old_root = guest_harmonization.GUEST_ROOT
        self._old_secret_path = guest_harmonization.GUEST_SECRET_PATH
        guest_harmonization.GUEST_ROOT = self._tmp / "runs"
        guest_harmonization.GUEST_SECRET_PATH = self._tmp / "guest.key"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        guest_harmonization.GUEST_ROOT = self._old_root
        guest_harmonization.GUEST_SECRET_PATH = self._old_secret_path
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _create_run(self) -> str:
        response = self.client.post("/api/guest-harmonization/runs")
        self.assertEqual(response.status_code, 201)
        return response.json()["run_id"]

    def _bundle_payload(self) -> dict:
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-guest-export",
                        "name": [{"given": ["Export"], "family": "Sample"}],
                        "gender": "male",
                        "birthDate": "1972-04-18",
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "lipid-1",
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "2085-9",
                                    "display": "HDL Cholesterol",
                                }
                            ],
                            "text": "HDL Cholesterol",
                        },
                        "valueQuantity": {"value": 56, "unit": "mg/dL"},
                        "effectiveDateTime": "2025-09-04",
                        "status": "final",
                    }
                },
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": "med-1",
                        "status": "active",
                        "intent": "order",
                        "medicationCodeableConcept": {"text": "Atorvastatin 20 MG"},
                        "authoredOn": "2024-12-01",
                    }
                },
                {
                    "resource": {
                        "resourceType": "AllergyIntolerance",
                        "id": "allergy-1",
                        "code": {"text": "Penicillin G"},
                        "clinicalStatus": {"text": "active"},
                    }
                },
            ],
        }

    def test_export_workspace_zip_for_guest_run(self) -> None:
        run_id = self._create_run()

        upload = self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("sample.json", json.dumps(self._bundle_payload()), "application/json")},
        )
        self.assertEqual(upload.status_code, 200)

        processed = self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        self.assertEqual(processed.status_code, 200)
        guest_harmonization.wait_for_processing(run_id)

        response = self.client.get(f"/api/guest-harmonization/runs/{run_id}/export-workspace")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/zip")

        zf, root = _zip_root(response.content)
        with zf:
            names = set(zf.namelist())
            for required in [
                f"{root}/MANIFEST.json",
                f"{root}/AGENT-INSTRUCTIONS.md",
                f"{root}/README.md",
                f"{root}/PATIENT-SUMMARY.md",
                f"{root}/sources/sources.json",
                f"{root}/evidence/canonical-facts.json",
                f"{root}/evidence/provenance.json",
                f"{root}/evidence/source-contributions.json",
                f"{root}/evidence/conflicts.json",
                f"{root}/evidence/missing-information.json",
                f"{root}/fhir/harmonized-bundle.json",
                f"{root}/packets/second-opinion.context.json",
                f"{root}/exports/clinician-handoff.md",
                f"{root}/exports/labs.csv",
                f"{root}/cli/atlas_workspace.py",
            ]:
                self.assertIn(required, names, f"missing {required} in guest export")

            manifest = json.loads(zf.read(f"{root}/MANIFEST.json"))
            self.assertTrue(manifest["workspace_id"].startswith("guest-"))
            self.assertGreater(manifest["canonical_fact_count"], 0)

            facts = json.loads(zf.read(f"{root}/evidence/canonical-facts.json"))["facts"]
            resource_types = {f["resource_type"] for f in facts}
            self.assertIn("Observation", resource_types)
            self.assertIn("MedicationRequest", resource_types)
            self.assertIn("AllergyIntolerance", resource_types)

    def test_export_workspace_requires_guest_cookie(self) -> None:
        run_id = self._create_run()
        # Upload and process so an output exists.
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("sample.json", json.dumps(self._bundle_payload()), "application/json")},
        )
        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        guest_harmonization.wait_for_processing(run_id)

        other = TestClient(app)
        response = other.get(f"/api/guest-harmonization/runs/{run_id}/export-workspace")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
