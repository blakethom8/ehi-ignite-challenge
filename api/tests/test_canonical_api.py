from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.core.loader import list_patient_files, patient_id_from_path
from api.main import app


class CanonicalAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _sample_patient_id(self) -> str:
        files = list_patient_files()
        if not files:
            self.skipTest("No Synthea patient bundles available")
        return patient_id_from_path(files[0])

    def test_patient_selector_is_curated_for_demo(self) -> None:
        response = self.client.get("/api/patients")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertLessEqual(len([item for item in body if item["workspace_type"] == "synthea"]), 20)
        self.assertIn("763b6101-133a-44bb-ac60-3c097d6c0ba1", {item["id"] for item in body})

    def test_canonical_summary_uses_workspace_baseline(self) -> None:
        patient_id = self._sample_patient_id()
        response = self.client.get(f"/api/canonical/{patient_id}/summary")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["workspace_id"], f"workspace-{patient_id}")
        self.assertGreaterEqual(body["source_count"], 1)
        self.assertGreater(body["total_resources"], 0)
        self.assertIn("synthea-baseline", body["fallback_modes"])

    def test_canonical_summary_allows_empty_new_profile(self) -> None:
        response = self.client.get("/api/canonical/workspace-new-profile/summary")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_count"], 0)
        self.assertEqual(body["total_resources"], 0)
        self.assertEqual(body["storage_mode"], "server-local-workspace")


if __name__ == "__main__":
    unittest.main()
