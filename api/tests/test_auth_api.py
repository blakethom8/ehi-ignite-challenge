from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from api.core import auth as auth_core
from api.main import app


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_session_starts_anonymous(self) -> None:
        client = TestClient(app)
        response = client.get("/api/auth/session")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "anonymous")
        self.assertIsNone(body["active_demo_patient"])
        self.assertGreaterEqual(len(body["available_demo_patients"]), 3)
        self.assertIn("short_journey", body["available_demo_patients"][0])
        self.assertIn("metadata", body["available_demo_patients"][0])

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
        self.assertIsNone(body["active_demo_patient"])

        session = client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()["mode"], "authenticated")
        self.assertIsNone(session.json()["active_patient_id"])

    def test_signup_creates_consumer_session_and_hashes_password(self) -> None:
        client = TestClient(app)
        email = f"new-consumer-{uuid.uuid4().hex}@example.com"
        password = "correct-horse-battery"
        signup = client.post(
            "/api/auth/signup",
            json={"email": email.upper(), "password": password, "display_name": "  New Consumer  "},
        )
        self.assertEqual(signup.status_code, 200)
        self.assertIn(auth_core.SESSION_COOKIE_NAME, signup.cookies)
        body = signup.json()
        self.assertEqual(body["mode"], "authenticated")
        self.assertEqual(body["user"]["email"], email)
        self.assertEqual(body["user"]["display_name"], "New Consumer")
        self.assertEqual(body["user"]["role"], "consumer")

        session = client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()["mode"], "authenticated")
        self.assertEqual(session.json()["user"]["email"], email)

        session_id = auth_core._unsign_cookie_value(signup.cookies.get(auth_core.SESSION_COOKIE_NAME))
        self.assertIsNotNone(session_id)
        principal = auth_core._lookup_session(session_id or "")
        self.assertIsNotNone(principal)
        self.assertEqual(principal.to_user_identity().role, "consumer")

        with auth_core._connect() as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(row["password_hash"], password)
        self.assertTrue(row["password_hash"].startswith("scrypt$"))

    def test_signup_rejects_duplicate_normalized_email(self) -> None:
        client = TestClient(app)
        email = f"duplicate-consumer-{uuid.uuid4().hex}@example.com"
        first = client.post(
            "/api/auth/signup",
            json={"email": email, "password": "first-password", "display_name": "Duplicate Consumer"},
        )
        self.assertEqual(first.status_code, 200)

        duplicate = client.post(
            "/api/auth/signup",
            json={"email": email.upper(), "password": "second-password", "display_name": "Duplicate Consumer"},
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["detail"], "An account already exists for this email.")

    def test_demo_session_can_access_demo_patient(self) -> None:
        client = TestClient(app)
        start = client.post("/api/auth/demo", json={"patient_id": "demo-high-risk"})
        self.assertEqual(start.status_code, 200)
        body = start.json()
        self.assertEqual(body["mode"], "demo")
        self.assertEqual(body["active_patient_id"], "demo-high-risk")
        self.assertEqual(body["active_demo_patient"]["id"], "demo-high-risk")
        self.assertTrue(body["active_demo_patient"]["short_journey"])
        self.assertEqual(body["active_demo_patient"]["metadata"]["care_setting"], "Pre-op surgical review")
        self.assertIn("Peri-op", body["active_demo_patient"]["metadata"]["tags"])

        listing = client.get("/api/patients")
        self.assertEqual(listing.status_code, 200)
        patient_ids = [item["id"] for item in listing.json()]
        self.assertIn("demo-high-risk", patient_ids)
        self.assertNotIn("5cbc121b-cd71-4428-b8b7-31e53eba8184", patient_ids)

        overview = client.get("/api/patients/demo-high-risk/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["id"], "demo-high-risk")

    def test_demo_session_capabilities_include_harmonize(self) -> None:
        client = TestClient(app)
        start = client.post("/api/auth/demo", json={"patient_id": "demo-aggregate-icu"})
        self.assertEqual(start.status_code, 200)

        capabilities = client.get("/api/auth/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        body = capabilities.json()
        self.assertEqual(body["mode"], "demo")
        self.assertTrue(body["can_use_harmonize"])

    def test_authenticated_session_does_not_list_seeded_synthea_workspaces(self) -> None:
        client = TestClient(app)
        email = f"workspace-list-{uuid.uuid4().hex}@example.com"
        signup = client.post(
            "/api/auth/signup",
            json={"email": email, "password": "correct-horse-battery", "display_name": "Workspace List"},
        )
        self.assertEqual(signup.status_code, 200)

        listing = client.get("/api/patients")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json(), [])

    def test_authenticated_session_rejects_seeded_and_demo_patient_selection(self) -> None:
        client = TestClient(app)
        email = f"select-guard-{uuid.uuid4().hex}@example.com"
        signup = client.post(
            "/api/auth/signup",
            json={"email": email, "password": "correct-horse-battery", "display_name": "Select Guard"},
        )
        self.assertEqual(signup.status_code, 200)

        demo_alias_attempt = client.post("/api/auth/select-patient", json={"patient_id": "demo-high-risk"})
        self.assertEqual(demo_alias_attempt.status_code, 403)

        seeded_patient_attempt = client.post(
            "/api/auth/select-patient",
            json={"patient_id": auth_core.DEMO_PATIENTS[0].actual_patient_id},
        )
        self.assertEqual(seeded_patient_attempt.status_code, 403)

    def test_authenticated_session_clears_stale_seeded_patient_selection(self) -> None:
        client = TestClient(app)
        email = f"stale-session-{uuid.uuid4().hex}@example.com"
        password = "correct-horse-battery"
        signup = client.post(
            "/api/auth/signup",
            json={"email": email, "password": password, "display_name": "Stale Session"},
        )
        self.assertEqual(signup.status_code, 200)

        session_id = auth_core._unsign_cookie_value(signup.cookies.get(auth_core.SESSION_COOKIE_NAME))
        self.assertIsNotNone(session_id)

        with auth_core._connect() as conn:
            conn.execute(
                "UPDATE sessions SET active_patient_id = ?, active_patient_name = ? WHERE id = ?",
                (
                    auth_core.DEMO_PATIENTS[0].actual_patient_id,
                    "Shelly Corwin",
                    session_id,
                ),
            )
            conn.commit()

        session = client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        body = session.json()
        self.assertEqual(body["mode"], "authenticated")
        self.assertIsNone(body["active_patient_id"])
        self.assertIsNone(body["active_patient_name"])

    def test_authenticated_session_can_select_owned_workspace(self) -> None:
        client = TestClient(app)
        email = f"owned-workspace-{uuid.uuid4().hex}@example.com"
        signup = client.post(
            "/api/auth/signup",
            json={"email": email, "password": "correct-horse-battery", "display_name": "Owned Workspace"},
        )
        self.assertEqual(signup.status_code, 200)

        created = client.post(
            "/api/aggregation/profiles",
            json={"display_name": "My Workspace", "notes": ""},
        )
        self.assertEqual(created.status_code, 200)
        workspace_id = created.json()["profile"]["id"]

        selected = client.post("/api/auth/select-patient", json={"patient_id": workspace_id})
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json()["active_patient_id"], workspace_id)

    def test_logout_clears_guest_fallback_capabilities(self) -> None:
        client = TestClient(app)
        guest_run = client.post("/api/guest-harmonization/runs")
        self.assertEqual(guest_run.status_code, 201)

        signup = client.post(
            "/api/auth/signup",
            json={
                "email": f"guest-fallback-{uuid.uuid4().hex}@example.com",
                "password": "correct-horse-battery",
                "display_name": "Guest Fallback",
            },
        )
        self.assertEqual(signup.status_code, 200)

        logout = client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.json()["mode"], "anonymous")

        capabilities = client.get("/api/auth/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.json()["mode"], "anonymous")


if __name__ == "__main__":
    unittest.main()
