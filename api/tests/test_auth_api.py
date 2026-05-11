from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.main import app


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_session_starts_anonymous(self) -> None:
        client = TestClient(app)
        response = client.get("/api/auth/session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "anonymous")

    def test_patient_list_requires_session(self) -> None:
        client = TestClient(app)
        response = client.get("/api/patients")
        self.assertEqual(response.status_code, 401)

    def test_login_bootstraps_authenticated_session(self) -> None:
        client = TestClient(app)
        login = client.post(
            "/api/auth/login",
            json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
        )
        self.assertEqual(login.status_code, 200)
        body = login.json()
        self.assertEqual(body["mode"], "authenticated")
        self.assertEqual(body["user"]["email"], "clinician@atlas.local")

        session = client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()["mode"], "authenticated")

    def test_demo_session_can_access_demo_patient(self) -> None:
        client = TestClient(app)
        start = client.post("/api/auth/demo", json={"patient_id": "demo-high-risk"})
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["mode"], "demo")
        self.assertEqual(start.json()["active_patient_id"], "demo-high-risk")

        listing = client.get("/api/patients")
        self.assertEqual(listing.status_code, 200)
        patient_ids = [item["id"] for item in listing.json()]
        self.assertIn("demo-high-risk", patient_ids)
        self.assertNotIn("5cbc121b-cd71-4428-b8b7-31e53eba8184", patient_ids)

        overview = client.get("/api/patients/demo-high-risk/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["id"], "demo-high-risk")


if __name__ == "__main__":
    unittest.main()
