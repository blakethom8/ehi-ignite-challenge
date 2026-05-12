"""Tests for /api/admin/* and self-service auth endpoints.

Covers:
- require_role gating (anon, demo, non-admin authenticated → 403)
- listing users, getting detail with workspaces, listing activity
- patching role/status, with the self-demotion lock-out guard
- deleting a user and the workspace cascade
- listing and revoking sessions
- self-service: change display name, change password (rejects wrong current,
  revokes other sessions), delete own account
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from api.core import auth as auth_core
from api.core import aggregation as agg_core
from api.main import app


def _signup(client: TestClient, email: str, password: str = "correct-horse-battery", name: str = "Test User") -> str:
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "display_name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]["id"]


def _login(client: TestClient, email: str, password: str = "correct-horse-battery") -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _promote_to_admin(user_id: str) -> None:
    """Bypass the role API to set up an admin user for the tests."""
    with auth_core._connect() as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
        conn.commit()


class AdminApiTests(unittest.TestCase):
    def _new_admin_client(self) -> tuple[TestClient, str]:
        client = TestClient(app)
        email = f"admin-{uuid.uuid4().hex}@example.com"
        admin_id = _signup(client, email)
        _promote_to_admin(admin_id)
        # Refresh the session so principal.role reflects the DB change.
        client.post("/api/auth/logout")
        _login(client, email)
        return client, admin_id

    # ------------------------------------------------------------------
    # require_role gate
    # ------------------------------------------------------------------

    def test_admin_users_blocks_anonymous(self) -> None:
        client = TestClient(app)
        response = client.get("/api/admin/users")
        self.assertEqual(response.status_code, 401)

    def test_admin_users_blocks_demo_session(self) -> None:
        client = TestClient(app)
        client.post("/api/auth/demo", json={"patient_id": "demo-high-risk"})
        response = client.get("/api/admin/users")
        self.assertEqual(response.status_code, 403)

    def test_admin_users_blocks_non_admin_authenticated(self) -> None:
        client = TestClient(app)
        _signup(client, f"consumer-{uuid.uuid4().hex}@example.com")
        response = client.get("/api/admin/users")
        self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------------------
    # listing + detail
    # ------------------------------------------------------------------

    def test_admin_can_list_users(self) -> None:
        client, admin_id = self._new_admin_client()
        response = client.get("/api/admin/users")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertIn(admin_id, ids)

    def test_admin_user_detail_shows_workspaces_and_storage(self) -> None:
        client, _ = self._new_admin_client()
        # Create another user and a workspace for them
        target_email = f"target-{uuid.uuid4().hex}@example.com"
        other_client = TestClient(app)
        target_id = _signup(other_client, target_email)
        # Create a workspace as the target user (their session is set in other_client).
        create = other_client.post("/api/aggregation/profiles", json={"display_name": "Target Workspace"})
        self.assertEqual(create.status_code, 200, create.text)
        workspace_id = create.json()["profile"]["id"]

        detail = client.get(f"/api/admin/users/{target_id}")
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertEqual(body["id"], target_id)
        self.assertEqual(body["workspace_count"], 1)
        workspace_ids = [w["id"] for w in body["workspaces"]]
        self.assertIn(workspace_id, workspace_ids)

    def test_admin_get_user_activity_returns_audit_events(self) -> None:
        client, admin_id = self._new_admin_client()
        # The admin's own audit trail includes signup + login.
        activity = client.get(f"/api/admin/users/{admin_id}/activity")
        self.assertEqual(activity.status_code, 200)
        event_types = {event["event_type"] for event in activity.json()["events"]}
        # signup is always present; login may be present depending on bootstrap.
        self.assertTrue(event_types & {"auth.signup_succeeded", "auth.login_succeeded"})

    # ------------------------------------------------------------------
    # patch user
    # ------------------------------------------------------------------

    def test_admin_can_change_role(self) -> None:
        client, _ = self._new_admin_client()
        target_id = _signup(TestClient(app), f"role-target-{uuid.uuid4().hex}@example.com")
        response = client.patch(f"/api/admin/users/{target_id}", json={"role": "clinician"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "clinician")

    def test_admin_cannot_demote_self_from_admin(self) -> None:
        client, admin_id = self._new_admin_client()
        response = client.patch(f"/api/admin/users/{admin_id}", json={"role": "consumer"})
        self.assertEqual(response.status_code, 409)

    def test_admin_disable_user_revokes_their_sessions(self) -> None:
        client, _ = self._new_admin_client()
        target_email = f"disable-{uuid.uuid4().hex}@example.com"
        target_client = TestClient(app)
        target_id = _signup(target_client, target_email)
        # Target should currently be able to hit /me-ish endpoints (e.g., session)
        before = target_client.get("/api/auth/session")
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()["mode"], "authenticated")
        # Disable from admin
        response = client.patch(f"/api/admin/users/{target_id}", json={"status": "disabled"})
        self.assertEqual(response.status_code, 200)
        # The target's session should now be revoked (mode anonymous on next probe)
        after = target_client.get("/api/auth/session")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json()["mode"], "anonymous")

    # ------------------------------------------------------------------
    # delete user with workspace cascade
    # ------------------------------------------------------------------

    def test_admin_delete_user_cascades_workspaces(self) -> None:
        client, _ = self._new_admin_client()
        target_client = TestClient(app)
        target_id = _signup(target_client, f"casc-{uuid.uuid4().hex}@example.com")
        target_client.post("/api/aggregation/profiles", json={"display_name": "Cascade"})

        # Verify the workspace exists on disk before the delete
        before_workspaces = agg_core.list_profiles_for_user(target_id)
        self.assertEqual(len(before_workspaces), 1)

        response = client.delete(f"/api/admin/users/{target_id}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["ok"])

        # User row gone, workspace gone
        self.assertEqual(agg_core.list_profiles_for_user(target_id), [])
        missing = client.get(f"/api/admin/users/{target_id}")
        self.assertEqual(missing.status_code, 404)

    def test_admin_cannot_delete_self_via_admin_endpoint(self) -> None:
        client, admin_id = self._new_admin_client()
        response = client.delete(f"/api/admin/users/{admin_id}")
        self.assertEqual(response.status_code, 409)

    # ------------------------------------------------------------------
    # sessions
    # ------------------------------------------------------------------

    def test_admin_sessions_lists_and_revokes(self) -> None:
        client, _ = self._new_admin_client()
        sessions = client.get("/api/admin/sessions")
        self.assertEqual(sessions.status_code, 200)
        body = sessions.json()
        self.assertGreater(len(body), 0)

        # Find a session that is not the admin's (we will create one fresh)
        other = TestClient(app)
        _signup(other, f"sess-{uuid.uuid4().hex}@example.com")
        sessions = client.get("/api/admin/sessions")
        target = next((s for s in sessions.json() if s["user_id"] is not None), None)
        self.assertIsNotNone(target)
        revoke = client.delete(f"/api/admin/sessions/{target['id']}")
        self.assertEqual(revoke.status_code, 200)


class SelfServiceAccountTests(unittest.TestCase):
    def test_update_display_name(self) -> None:
        client = TestClient(app)
        email = f"name-{uuid.uuid4().hex}@example.com"
        _signup(client, email, name="Old Name")
        response = client.patch("/api/auth/me", json={"display_name": "Fresh Name"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user"]["display_name"], "Fresh Name")

    def test_change_password_rejects_wrong_current(self) -> None:
        client = TestClient(app)
        email = f"pw-{uuid.uuid4().hex}@example.com"
        _signup(client, email)
        response = client.post(
            "/api/auth/change-password",
            json={"current_password": "wrong-password", "new_password": "new-correct-pw"},
        )
        self.assertEqual(response.status_code, 401)

    def test_change_password_succeeds_and_revokes_other_sessions(self) -> None:
        client_a = TestClient(app)
        email = f"pw-rev-{uuid.uuid4().hex}@example.com"
        _signup(client_a, email)

        # Sign in from a second client with the same credentials → two live sessions.
        client_b = TestClient(app)
        _login(client_b, email)
        ok = client_b.get("/api/auth/session")
        self.assertEqual(ok.json()["mode"], "authenticated")

        # Change password from client_a
        change = client_a.post(
            "/api/auth/change-password",
            json={"current_password": "correct-horse-battery", "new_password": "next-very-good-pw"},
        )
        self.assertEqual(change.status_code, 200, change.text)

        # client_a stays authenticated; client_b becomes anonymous
        still_a = client_a.get("/api/auth/session")
        self.assertEqual(still_a.json()["mode"], "authenticated")
        after_b = client_b.get("/api/auth/session")
        self.assertEqual(after_b.json()["mode"], "anonymous")

        # New password works for fresh login.
        relogin = client_b.post(
            "/api/auth/login",
            json={"email": email, "password": "next-very-good-pw"},
        )
        self.assertEqual(relogin.status_code, 200)

    def test_delete_own_account_cascades_workspaces(self) -> None:
        client = TestClient(app)
        email = f"selfdel-{uuid.uuid4().hex}@example.com"
        user_id = _signup(client, email)
        client.post("/api/aggregation/profiles", json={"display_name": "Mine"})
        self.assertEqual(len(agg_core.list_profiles_for_user(user_id)), 1)

        response = client.delete("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "anonymous")
        self.assertEqual(agg_core.list_profiles_for_user(user_id), [])

        # Cannot log back in
        relogin = client.post(
            "/api/auth/login",
            json={"email": email, "password": "correct-horse-battery"},
        )
        self.assertEqual(relogin.status_code, 401)


if __name__ == "__main__":
    unittest.main()
