"""Phase 4: Caspian file route + workspace mode-gate coverage.

These tests pin the post-refactor contract:
- demo can list + read seed files but never write
- guest is blocked from every caspian/files/* route
- authenticated users can write notes/ but not workflow-runs/ directly
- workflow_runner persists for auth, skips for demo
- save-as-note copies generated → notes/, with collision resolution
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.core import auth as auth_core
from api.core import caspian_workspace
from api.core.auth import SessionPrincipal
from api.core.guest_harmonization import GUEST_COOKIE_NAME, GuestCookieState, sign_cookie


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    """Fresh app client with isolated auth.db, session secret, and workspace root."""
    monkeypatch.setattr(auth_core, "AUTH_DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(
        auth_core, "SESSION_SECRET_PATH", tmp_path / "atlas-session.key"
    )
    # Redirect the on-disk workspace root so tests don't write into the repo.
    monkeypatch.setattr(
        caspian_workspace, "_WORKSPACES_ROOT", tmp_path / "caspian-workspaces"
    )
    # Re-import the app fresh so the patched auth path is used by the routes.
    from api.main import app

    return TestClient(app)


def _enter_demo(client: TestClient, alias: str = "demo-high-risk") -> None:
    response = client.post("/api/auth/demo", json={"patient_id": alias})
    assert response.status_code == 200, response.text


def _enter_authenticated(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
    )
    assert response.status_code == 200, response.text


def _make_auth_session(user_id: str = "user_test") -> SessionPrincipal:
    """Hand-build an authenticated principal for direct workspace-layer tests."""
    from datetime import timedelta

    return SessionPrincipal(
        session_id="sess_test_auth",
        mode="authenticated",
        user_id=user_id,
        email="user@test",
        display_name="Test User",
        role="clinician",
        active_patient_id=None,
        active_patient_name=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _make_demo_session() -> SessionPrincipal:
    from datetime import timedelta

    return SessionPrincipal(
        session_id="sess_test_demo",
        mode="demo",
        user_id=None,
        email=None,
        display_name=None,
        role="clinician",
        active_patient_id="demo-high-risk",
        active_patient_name="Demo Patient - Surgical Review",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


# ---------------------------------------------------------------------------
# HTTP route policy
# ---------------------------------------------------------------------------


def test_demo_can_list_and_read(client: TestClient) -> None:
    _enter_demo(client)
    listing = client.get("/api/caspian/files/list", params={"patient_id": "demo-high-risk"})
    assert listing.status_code == 200, listing.text
    body = listing.json()
    # The list endpoint surfaces capabilities + a tree; demo gets seed files.
    assert body["capabilities"]["mode"] == "demo"
    flat = []

    def _walk(nodes: list[dict]) -> None:
        for n in nodes:
            if n.get("type") == "folder":
                _walk(n.get("children", []))
            else:
                flat.append(n)

    _walk(body["tree"])
    # The demo-seed folder is virtual; at least the welcome.md exists.
    assert any(node.get("id") == "demo-seed/welcome.md" for node in flat)

    # Reading a demo-seed file returns kind="demo-seed", editable=False.
    read = client.get(
        "/api/caspian/files/read",
        params={"patient_id": "demo-high-risk", "path": "demo-seed/welcome.md"},
    )
    assert read.status_code == 200, read.text
    payload = read.json()
    assert payload["file_kind"] == "demo-seed"
    assert payload["editable"] is False


def test_demo_cannot_write(client: TestClient) -> None:
    _enter_demo(client)
    write = client.put(
        "/api/caspian/files/write",
        json={
            "patient_id": "demo-high-risk",
            "path": "notes/blocked.md",
            "content": "should not write",
        },
    )
    assert write.status_code == 403


def test_guest_blocked_from_caspian_files(client: TestClient) -> None:
    # Craft a signed guest cookie with one run id. Caspian routes should reject
    # the request because the guest principal is NOT a valid access session
    # (require_access_session is strict — demo or authenticated only).
    cookie_value = sign_cookie(GuestCookieState(run_ids=("guest_abc123",)))
    client.cookies.set(GUEST_COOKIE_NAME, cookie_value)

    listing = client.get(
        "/api/caspian/files/list", params={"patient_id": "demo-high-risk"}
    )
    # require_access_session 401s on absent/invalid session cookie. The guest
    # cookie is not honored by /caspian routes.
    assert listing.status_code in {401, 403}

    write = client.put(
        "/api/caspian/files/write",
        json={
            "patient_id": "demo-high-risk",
            "path": "notes/x.md",
            "content": "x",
        },
    )
    assert write.status_code in {401, 403}


def test_authenticated_can_write_notes(client: TestClient) -> None:
    _enter_authenticated(client)
    # An authenticated session needs an owned workspace to access. Create one.
    profile = client.post(
        "/api/aggregation/profiles",
        json={"display_name": "Tests", "notes": ""},
    )
    assert profile.status_code == 200, profile.text
    workspace_id = profile.json()["profile"]["id"]

    write = client.put(
        "/api/caspian/files/write",
        json={
            "patient_id": workspace_id,
            "path": "notes/scratch.md",
            "content": "# Scratch\n\nA note.",
        },
    )
    assert write.status_code == 200, write.text

    read = client.get(
        "/api/caspian/files/read",
        params={"patient_id": workspace_id, "path": "notes/scratch.md"},
    )
    assert read.status_code == 200, read.text
    payload = read.json()
    assert payload["content"] == "# Scratch\n\nA note."
    assert payload["file_kind"] == "user"
    assert payload["editable"] is True


def test_authenticated_cannot_write_workflow_runs_directly(client: TestClient) -> None:
    _enter_authenticated(client)
    profile = client.post(
        "/api/aggregation/profiles",
        json={"display_name": "Tests gen", "notes": ""},
    )
    workspace_id = profile.json()["profile"]["id"]

    write = client.put(
        "/api/caspian/files/write",
        json={
            "patient_id": workspace_id,
            "path": "workflow-runs/2026-05-12-preop.md",
            "content": "should not land here",
        },
    )
    # The route uses write_workspace_file which raises WorkspaceForbiddenError
    # for non-user-writable paths → 403.
    assert write.status_code == 403


# ---------------------------------------------------------------------------
# Workflow runner persistence behavior (in-process; LLM call mocked at layer)
# ---------------------------------------------------------------------------


def _make_artifact():
    from api.models import WorkflowArtifact, WorkflowBanner

    return WorkflowArtifact(
        artifact_id="art_test:abc123",
        workflow_id="preop_review_v1",
        workflow_title="Preop Review",
        workflow_type="preop_review",
        generated_at=datetime(2026, 5, 12, 12, tzinfo=UTC),
        banner=WorkflowBanner(
            status="clear",
            label="CLEAR · PROCEED",
            headline="No active medication holds detected for the planned procedure.",
            action_label="Acknowledge",
        ),
        fact_rail=[],
        sections=[],
        chat_narration="Test narration.",
        kind="generated",
    )


def test_workflow_runner_skips_demo_persistence(tmp_path: Path, monkeypatch) -> None:
    """``_persist_artifact_to_workspace`` returns None for demo sessions and
    leaves the on-disk workspace empty. We exercise the private helper directly
    so we don't have to mock the Anthropic call."""
    from api.core.workflow_runner import _persist_artifact_to_workspace

    monkeypatch.setattr(
        caspian_workspace, "_WORKSPACES_ROOT", tmp_path / "caspian-workspaces"
    )

    artifact = _make_artifact()
    session = _make_demo_session()
    rel = _persist_artifact_to_workspace(session, "demo-high-risk", artifact)
    assert rel is None

    workspace_root = caspian_workspace.workspace_root(session, "demo-high-risk")
    runs_dir = workspace_root / "workflow-runs"
    # Either the workspace dir wasn't created or workflow-runs/ is empty.
    if runs_dir.exists():
        assert list(runs_dir.iterdir()) == []


def test_workflow_runner_persists_for_auth(tmp_path: Path, monkeypatch) -> None:
    from api.core.workflow_runner import _persist_artifact_to_workspace

    monkeypatch.setattr(
        caspian_workspace, "_WORKSPACES_ROOT", tmp_path / "caspian-workspaces"
    )

    artifact = _make_artifact()
    session = _make_auth_session()
    rel = _persist_artifact_to_workspace(session, "patient-xyz", artifact)
    assert rel is not None
    assert rel.startswith("workflow-runs/")

    workspace_root = caspian_workspace.workspace_root(session, "patient-xyz")
    landed = workspace_root / rel
    assert landed.exists()
    assert landed.is_file()


# ---------------------------------------------------------------------------
# Save-as-note
# ---------------------------------------------------------------------------


def test_save_as_note(client: TestClient, tmp_path: Path) -> None:
    _enter_authenticated(client)
    profile = client.post(
        "/api/aggregation/profiles",
        json={"display_name": "Tests note", "notes": ""},
    )
    workspace_id = profile.json()["profile"]["id"]

    # Seed a workflow-runs/ artifact directly via the workspace layer.
    session = _make_auth_session()
    # The route uses a different workspace key (based on the authenticated
    # session_id from the cookie). Easier: write via the helper using the
    # real authenticated session that the client cookie represents.
    # We can do this by reading the session out of the auth DB and using
    # the workspace_root for that session. Simpler: trigger save-as-note
    # against a manually-placed file under the same workspace key the
    # session is currently using by going through the actual request layer.

    # Step 1: locate the live session in auth.db.
    raw_cookie = client.cookies.get(auth_core.SESSION_COOKIE_NAME)
    session_id = auth_core._unsign_cookie_value(raw_cookie)
    assert session_id is not None
    principal = auth_core._lookup_session(session_id)
    assert principal is not None

    # Step 2: write a generated artifact under the live workspace.
    caspian_workspace.write_generated_artifact(
        principal,
        workspace_id,
        "workflow-runs/2026-05-12-preop-abc.md",
        "# Preop briefing\n\nGenerated content.",
    )

    # Step 3: save-as-note via the route.
    resp = client.post(
        "/api/caspian/files/save-as-note",
        json={
            "patient_id": workspace_id,
            "source_path": "workflow-runs/2026-05-12-preop-abc.md",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["path"] == "notes/2026-05-12-preop-abc.md"

    # Step 4: confirm the copy is editable.
    read = client.get(
        "/api/caspian/files/read",
        params={"patient_id": workspace_id, "path": "notes/2026-05-12-preop-abc.md"},
    )
    assert read.status_code == 200
    payload = read.json()
    assert payload["file_kind"] == "user"
    assert payload["editable"] is True
    assert "Generated content." in payload["content"]


def test_save_as_note_demo_blocked(client: TestClient) -> None:
    _enter_demo(client)
    resp = client.post(
        "/api/caspian/files/save-as-note",
        json={
            "patient_id": "demo-high-risk",
            "source_path": "workflow-runs/some-run.md",
        },
    )
    assert resp.status_code == 403


def test_save_as_note_collision_resolution(client: TestClient) -> None:
    _enter_authenticated(client)
    profile = client.post(
        "/api/aggregation/profiles",
        json={"display_name": "Collision", "notes": ""},
    )
    workspace_id = profile.json()["profile"]["id"]

    raw_cookie = client.cookies.get(auth_core.SESSION_COOKIE_NAME)
    session_id = auth_core._unsign_cookie_value(raw_cookie)
    principal = auth_core._lookup_session(session_id or "")
    assert principal is not None

    # Pre-seed notes/x.md AND notes/x-2.md so the next save-as-note lands at
    # notes/x-3.md.
    caspian_workspace.write_workspace_file(principal, workspace_id, "notes/x.md", "existing 1")
    caspian_workspace.write_workspace_file(principal, workspace_id, "notes/x-2.md", "existing 2")
    caspian_workspace.write_generated_artifact(
        principal, workspace_id, "workflow-runs/x.md", "generated source"
    )

    resp = client.post(
        "/api/caspian/files/save-as-note",
        json={"patient_id": workspace_id, "source_path": "workflow-runs/x.md"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["path"] == "notes/x-3.md"
