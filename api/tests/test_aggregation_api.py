from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]
FHIR_DIR = REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"


class AggregationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        files = sorted(FHIR_DIR.glob("*.json"))
        if not files:
            raise RuntimeError(f"No patient bundles found in {FHIR_DIR}")
        cls.patient_id = files[0].stem
        cls.client = TestClient(app)

    def test_source_inventory_returns_synthetic_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.core.aggregation.STORE_ROOT", Path(tmpdir)):
                response = self.client.get(f"/api/aggregation/sources/{self.patient_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["patient_id"], self.patient_id)
        self.assertIn("medications", body["synthetic_resource_counts"])
        self.assertGreaterEqual(len(body["source_cards"]), 5)
        self.assertTrue(any(card["id"] == "synthea-fhir" for card in body["source_cards"]))

    def test_cleaning_queue_returns_review_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.core.aggregation.STORE_ROOT", Path(tmpdir)):
                response = self.client.get(f"/api/aggregation/cleaning-queue/{self.patient_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["issue_counts"]["total"], 3)
        self.assertTrue(any(issue["category"] == "medication_reality" for issue in body["issues"]))

    def test_readiness_returns_score_and_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.core.aggregation.STORE_ROOT", Path(tmpdir)):
                response = self.client.get(f"/api/aggregation/readiness/{self.patient_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["readiness_score"], 0)
        self.assertLessEqual(body["readiness_score"], 100)
        self.assertTrue(body["checklist"])
        self.assertIn("Proof-of-concept", body["posture"])

    def test_upload_stages_file_locally(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.core.aggregation.STORE_ROOT", Path(tmpdir)):
                response = self.client.post(
                    f"/api/aggregation/uploads/{self.patient_id}",
                    files={"file": ("example.pdf", b"%PDF-1.4 demo", "application/pdf")},
                    data={
                        "data_type": "Lab report",
                        "source_name": "Function Health",
                        "date_range": "April 2026",
                        "contains": '["Labs and observations", "Reference ranges"]',
                        "description": "Recent lab packet.",
                        "context_notes": "Patient says this was self-ordered.",
                    },
                )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["file"]["file_name"], "example.pdf")
            self.assertEqual(body["file"]["data_type"], "Lab report")
            self.assertEqual(body["file"]["contains"], ["Labs and observations", "Reference ranges"])
            self.assertEqual(body["file"]["extraction_confidence"], "medium")
            self.assertEqual(body["source_card"]["category"], "file_upload")
            self.assertTrue(any(Path(tmpdir).glob("*/*.metadata.json")))

    def test_multiple_uploads_are_returned_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.core.aggregation.STORE_ROOT", Path(tmpdir)):
                first = self.client.post(
                    f"/api/aggregation/uploads/{self.patient_id}",
                    files={"file": ("first.pdf", b"%PDF-1.4 demo", "application/pdf")},
                    data={"data_type": "PDF report", "description": "First upload."},
                )
                second = self.client.post(
                    f"/api/aggregation/uploads/{self.patient_id}",
                    files={"file": ("second.json", b'{"resourceType":"Bundle","entry":[]}', "application/json")},
                    data={"data_type": "FHIR JSON export", "description": "Second upload."},
                )
                inventory = self.client.get(f"/api/aggregation/sources/{self.patient_id}")

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            files = inventory.json()["uploaded_files"]
            self.assertGreaterEqual(len(files), 2)
            self.assertEqual(files[0]["file_name"], "second.json")
            self.assertEqual(files[0]["parse_status"], "structured")
            self.assertEqual(files[1]["file_name"], "first.pdf")

    def test_create_profile_persists_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch("api.core.aggregation.STORE_ROOT", root / "uploads"),
                patch("api.core.aggregation.PROFILE_ROOT", root / "profiles"),
                patch("api.core.aggregation.PROFILE_REGISTRY_PATH", root / "profiles" / "profiles.json"),
            ):
                response = self.client.post(
                    "/api/aggregation/profiles",
                    json={"display_name": "Demo upload patient", "notes": "Synthetic PDF test."},
                )
                patients = self.client.get("/api/patients").json()

            self.assertEqual(response.status_code, 200)
            body = response.json()
            profile = body["profile"]
            self.assertTrue(profile["id"].startswith("workspace-"))
            self.assertEqual(profile["display_name"], "Demo upload patient")
            self.assertTrue((root / "profiles" / "profiles.json").exists())
            self.assertIn(profile["id"], {item["id"] for item in patients})

    def test_delete_profile_removes_workspace_and_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch("api.core.aggregation.STORE_ROOT", root / "uploads"),
                patch("api.core.aggregation.PROFILE_ROOT", root / "profiles"),
                patch("api.core.aggregation.PROFILE_REGISTRY_PATH", root / "profiles" / "profiles.json"),
            ):
                response = self.client.post(
                    "/api/aggregation/profiles",
                    json={"display_name": "Delete me", "notes": "temporary"},
                )
                profile_id = response.json()["profile"]["id"]
                self.client.post(
                    f"/api/aggregation/uploads/{profile_id}",
                    files={"file": ("example.pdf", b"%PDF-1.4 demo", "application/pdf")},
                    data={"data_type": "PDF report", "description": "Temporary upload."},
                )
                delete_response = self.client.delete(f"/api/aggregation/profiles/{profile_id}")
                patients = self.client.get("/api/patients").json()

            self.assertEqual(delete_response.status_code, 200)
            self.assertTrue(delete_response.json()["deleted"])
            self.assertFalse((root / "uploads" / profile_id).exists())
            self.assertNotIn(profile_id, {item["id"] for item in patients})

    def test_update_profile_renames_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch("api.core.aggregation.STORE_ROOT", root / "uploads"),
                patch("api.core.aggregation.PROFILE_ROOT", root / "profiles"),
                patch("api.core.aggregation.PROFILE_REGISTRY_PATH", root / "profiles" / "profiles.json"),
            ):
                response = self.client.post(
                    "/api/aggregation/profiles",
                    json={"display_name": "Original name", "notes": "temporary"},
                )
                profile_id = response.json()["profile"]["id"]
                update_response = self.client.patch(
                    f"/api/aggregation/profiles/{profile_id}",
                    json={"display_name": "Renamed workspace", "notes": "Demo-ready profile."},
                )
                patients = self.client.get("/api/patients").json()

            self.assertEqual(update_response.status_code, 200)
            self.assertEqual(update_response.json()["profile"]["display_name"], "Renamed workspace")
            matching = [item for item in patients if item["id"] == profile_id]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["name"], "Renamed workspace")

    def test_delete_upload_removes_metadata_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.core.aggregation.STORE_ROOT", Path(tmpdir)):
                upload_response = self.client.post(
                    f"/api/aggregation/uploads/{self.patient_id}",
                    files={"file": ("example.csv", b"a,b\n1,2", "text/csv")},
                    data={"data_type": "Wearable export", "contains": '["Device metrics"]'},
                )
                file_id = upload_response.json()["file"]["file_id"]
                delete_response = self.client.delete(f"/api/aggregation/uploads/{self.patient_id}/{file_id}")

            self.assertEqual(delete_response.status_code, 200)
            self.assertTrue(delete_response.json()["deleted"])
            self.assertFalse(any(Path(tmpdir).glob("*/*example.csv")))
            self.assertFalse(any(Path(tmpdir).glob("*/*.metadata.json")))


if __name__ == "__main__":
    unittest.main()
