"""Tests for temporary guest harmonization runs."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from api.core import guest_harmonization
from api.main import app


class GuestHarmonizationAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="guest-harmonization-test-"))
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
        body = response.json()
        self.assertEqual(body["mode"], "guest")
        self.assertEqual(body["status"], "ready")
        self.assertTrue(body["run_id"].startswith("guest_"))
        self.assertIn("automatically deleted", body["disclosure"])
        self.assertTrue((guest_harmonization.GUEST_ROOT / body["run_id"] / "manifest.json").exists())
        return body["run_id"]

    def test_create_run_sets_manifest_and_cookie(self) -> None:
        run_id = self._create_run()
        response = self.client.get(f"/api/guest-harmonization/runs/{run_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run_id"], run_id)

    def test_upload_process_and_output_fhir_json(self) -> None:
        run_id = self._create_run()
        payload = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-guest-1",
                        "name": [{"given": ["Guest"], "family": "Upload"}],
                        "gender": "female",
                        "birthDate": "1984-03-02",
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "a1c-1",
                        "code": {
                            "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}],
                            "text": "A1C",
                        },
                        "valueQuantity": {"value": 5.2, "unit": "%"},
                        "effectiveDateTime": "2025-11-29",
                        "status": "final",
                    }
                },
            ],
        }

        upload = self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("sample.json", json.dumps(payload), "application/json")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(len(upload.json()["uploaded_files"]), 1)

        processed = self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        self.assertEqual(processed.status_code, 200)
        # /process is now async — initial response carries "processing" + a
        # seeded progress block; the daemon thread completes the work.
        self.assertEqual(processed.json()["status"], "processing")
        self.assertIsNotNone(processed.json().get("progress"))

        guest_harmonization.wait_for_processing(run_id)
        final = self.client.get(f"/api/guest-harmonization/runs/{run_id}").json()
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["outputs"][0]["file_name"], "harmonized-record.json")
        self.assertEqual(final["progress"]["status"], "complete")

        output = self.client.get(f"/api/guest-harmonization/runs/{run_id}/output")
        self.assertEqual(output.status_code, 200)
        body = output.json()
        self.assertEqual(body["schema_version"], "atlas.harmonized_record.v1")
        self.assertEqual(body["patient"]["name"], "Guest Upload")
        self.assertEqual(body["facts"][0]["resource_type"], "Observation")
        self.assertEqual(body["facts"][0]["label"], "A1C")
        self.assertEqual(body["provenance"][0]["method"], "guest_fhir_json_mvp")

    def test_guest_run_is_scoped_to_cookie_session(self) -> None:
        run_id = self._create_run()
        other_client = TestClient(app)

        response = other_client.get(f"/api/guest-harmonization/runs/{run_id}")
        self.assertEqual(response.status_code, 403)

        upload = other_client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("sample.json", "{}", "application/json")},
        )
        self.assertEqual(upload.status_code, 403)

    def test_expired_run_returns_gone(self) -> None:
        run_id = self._create_run()
        path = guest_harmonization.GUEST_ROOT / run_id / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        path.write_text(json.dumps(manifest))

        response = self.client.get(f"/api/guest-harmonization/runs/{run_id}")
        self.assertEqual(response.status_code, 410)
        self.assertEqual(json.loads(path.read_text())["status"], "expired")

    def test_delete_removes_temporary_workspace(self) -> None:
        run_id = self._create_run()
        response = self.client.delete(f"/api/guest-harmonization/runs/{run_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True, "run_id": run_id})
        self.assertFalse((guest_harmonization.GUEST_ROOT / run_id).exists())

    def test_upload_rejects_unsupported_file_type(self) -> None:
        run_id = self._create_run()
        response = self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("malware.exe", b"nope", "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
