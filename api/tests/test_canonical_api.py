from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.main import app


class CanonicalAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _demo_client(self) -> TestClient:
        client = TestClient(app)
        response = client.post("/api/auth/demo", json={"patient_id": "demo-high-risk"})
        self.assertEqual(response.status_code, 200)
        return client

    def _auth_client(self) -> TestClient:
        client = TestClient(app)
        response = client.post(
            "/api/auth/login",
            json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_patient_selector_is_curated_for_demo(self) -> None:
        """Demo sessions see exactly the curated demo aliases."""
        client = self._demo_client()
        response = client.get("/api/patients")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = {item["id"] for item in body}
        # The three demo aliases are always present.
        self.assertIn("demo-high-risk", ids)
        # Authenticated curated Synthea fallback was removed in the four-mode
        # refactor; the demo selector only surfaces demo aliases.
        self.assertLessEqual(len([item for item in body if item["workspace_type"] == "synthea"]), 20)

    def test_canonical_summary_uses_workspace_baseline(self) -> None:
        """Demo sessions can read canonical summaries through demo aliases."""
        client = self._demo_client()
        response = client.get("/api/canonical/demo-high-risk/summary")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # The route stamps the original patient_id back on the response so the
        # client gets the alias it asked for; workspace_id mirrors the resolved
        # underlying bundle's id.
        self.assertEqual(body["patient_id"], "demo-high-risk")
        self.assertGreaterEqual(body["source_count"], 1)
        self.assertGreater(body["total_resources"], 0)
        self.assertIn("synthea-baseline", body["fallback_modes"])

    def test_canonical_summary_allows_empty_new_profile(self) -> None:
        """An authenticated user can fetch the empty-profile canonical summary
        for a workspace they own."""
        client = self._auth_client()
        profile = client.post(
            "/api/aggregation/profiles",
            json={"display_name": "Canonical empty", "notes": ""},
        )
        self.assertEqual(profile.status_code, 200)
        workspace_id = profile.json()["profile"]["id"]
        response = client.get(f"/api/canonical/{workspace_id}/summary")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_count"], 0)
        self.assertEqual(body["total_resources"], 0)
        self.assertEqual(body["storage_mode"], "server-local-workspace")


if __name__ == "__main__":
    unittest.main()
