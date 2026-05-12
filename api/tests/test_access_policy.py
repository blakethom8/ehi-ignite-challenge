"""Phase 4: capability policy coverage.

The four-mode capability surface is the contract the frontend consumes via
``GET /api/auth/capabilities`` — locking it down here keeps anyone from
silently widening (or narrowing) what a mode can do without a test edit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.core import auth as auth_core
from api.core.access_policy import Capabilities, capabilities_for
from api.core.auth import SessionPrincipal


def _make_session(
    *,
    mode: str,
    user_id: str | None = None,
    session_id: str = "sess_test",
    guest_run_ids: tuple[str, ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id=session_id,
        mode=mode,  # type: ignore[arg-type]
        user_id=user_id,
        email=None,
        display_name=None,
        role="clinician",
        active_patient_id=None,
        active_patient_name=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        guest_run_ids=guest_run_ids,
    )


def test_capabilities_for_anonymous() -> None:
    caps = capabilities_for(None)
    assert caps.mode == "anonymous"
    assert caps.can_use_caspian is False
    assert caps.can_edit_caspian_user_files is False
    assert caps.can_write_caspian_notes is False
    assert caps.can_run_workflows is False
    assert caps.show_caspian_seed_files is False
    assert caps.persistence_scope == "none"


def test_capabilities_for_demo() -> None:
    session = _make_session(mode="demo")
    caps = capabilities_for(session)
    assert caps.mode == "demo"
    assert caps.can_use_caspian is True
    assert caps.can_run_workflows is True
    assert caps.show_caspian_seed_files is True
    assert caps.can_edit_caspian_user_files is False
    assert caps.can_write_caspian_notes is False
    assert caps.persistence_scope == "browser-ephemeral"


def test_capabilities_for_authenticated() -> None:
    session = _make_session(mode="authenticated", user_id="user_x")
    caps = capabilities_for(session)
    assert caps.mode == "authenticated"
    assert caps.can_use_caspian is True
    assert caps.can_edit_caspian_user_files is True
    assert caps.can_write_caspian_notes is True
    assert caps.can_run_workflows is True
    assert caps.can_use_aggregation_uploads is True
    assert caps.can_use_aggregation_profiles is True
    assert caps.can_use_harmonize is True
    assert caps.can_use_assistant_tools_write is True
    assert caps.persistence_scope == "browser-persistent"


def test_capabilities_for_guest() -> None:
    session = _make_session(mode="guest", guest_run_ids=("guest_abc",))
    caps = capabilities_for(session)
    assert caps.mode == "guest"
    assert caps.can_use_guest_harmonization is True
    assert caps.can_use_caspian is False
    assert caps.can_run_workflows is False
    assert caps.can_edit_caspian_user_files is False
    assert caps.can_write_caspian_notes is False
    assert caps.show_caspian_seed_files is False
    assert caps.persistence_scope == "browser-ephemeral"


def test_capabilities_endpoint_anonymous(tmp_path: Path, monkeypatch) -> None:
    """`GET /api/auth/capabilities` always 200s and returns anonymous shape
    for an un-cookied caller."""
    monkeypatch.setattr(auth_core, "AUTH_DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(
        auth_core, "SESSION_SECRET_PATH", tmp_path / "atlas-session.key"
    )
    # Important: re-import the app AFTER monkeypatching the DB path so any
    # startup hooks pick up the test root. The TestClient already lazily
    # initializes the route, and capabilities is a pure-function endpoint.
    from api.main import app

    client = TestClient(app)
    response = client.get("/api/auth/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "anonymous"
    assert body["can_use_caspian"] is False
    assert body["persistence_scope"] == "none"
    # Schema sanity: every field in the pydantic model is present.
    expected_keys = set(Capabilities.model_fields.keys())
    assert expected_keys.issubset(body.keys())
