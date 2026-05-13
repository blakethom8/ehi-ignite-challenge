"""Thin facade over the auth submodules.

Implementation lives in:

* :mod:`api.core.auth_demo`    — demo-patient catalogue + alias helpers
* :mod:`api.core.auth_session` — cookie/token mechanics, SessionPrincipal,
                                 audit log, ``require_*`` dependencies
* :mod:`api.core.auth_account` — password hashing, signup, login
* :mod:`api.core.auth_admin`   — admin user/session management + self-service

This module re-exports the public surface so existing callers keep working:
``from api.core.auth import current_session, login_user, …``.

Module-level configuration constants (``AUTH_DB_PATH``, ``SESSION_SECRET_PATH``,
``SESSION_COOKIE_NAME``, etc.) are defined *here* so tests that
``monkeypatch.setattr(auth, "AUTH_DB_PATH", …)`` continue to work — the
submodules look these values up on this facade at call time.
"""

from __future__ import annotations

from pathlib import Path

from api.settings import get_settings

# ---------------------------------------------------------------------------
# Module-level configuration. Defined BEFORE the submodule imports below so
# that auth_session can read these via ``api.core.auth.AUTH_DB_PATH`` (etc.)
# at module-load time without races. Keeping them here is what makes
# ``monkeypatch.setattr(auth, "AUTH_DB_PATH", tmp_path / "auth.db")`` continue
# to drive the live runtime in tests.
# ---------------------------------------------------------------------------
_settings = get_settings()
REPO_ROOT: Path = Path(__file__).resolve().parents[2]
AUTH_DB_PATH: Path = _settings.ehi_auth_db_path
SESSION_SECRET_PATH: Path = _settings.ehi_session_secret_path
SESSION_COOKIE_NAME: str = "atlas_session"
SESSION_IDLE_HOURS: int = _settings.ehi_auth_session_idle_hours
SESSION_MAX_DAYS: int = _settings.ehi_auth_session_max_days
SESSION_SECURE: bool = _settings.is_production


# ---------------------------------------------------------------------------
# Re-exports — order matters for the import cycle (auth_session imports
# ``api.core.auth`` to look up the constants above, so the constants must
# already be bound on this module object before auth_session executes).
# ---------------------------------------------------------------------------
from api.core.auth_demo import (  # noqa: E402
    DEMO_PATIENT_BY_ALIAS,
    DEMO_PATIENTS,
    DemoPatientConfig,
    demo_patient_label,
    demo_patient_option,
    demo_patient_options,
    is_demo_alias,
    resolve_demo_patient_alias,
)
from api.core.auth_session import (  # noqa: E402
    AccessSessionDep,
    AuthenticatedSessionDep,
    SessionPrincipal,
    _VALID_ROLES,
    _accessible_authenticated_workspace_ids,
    _authenticated_workspace_access_allowed,
    _connect,
    _create_session,
    _ensure_parent,
    _guest_principal_from_request,
    _ip_hash,
    _is_production,
    _known_patient_name,
    _lookup_session,
    _now,
    _row_to_principal,
    _seed_bootstrap_user,
    _session_patient_allowed,
    _session_secret,
    _sign_session_id,
    _unsign_cookie_value,
    _user_agent,
    audit_event,
    authorize_patient_access,
    begin_demo_session,
    clear_session_cookie,
    current_session,
    current_session_including_guest,
    init_auth_store,
    optional_session_response,
    patient_exists,
    require_access_session,
    require_access_session_dep,
    require_authenticated_session,
    require_authenticated_session_dep,
    require_role,
    require_session_or_guest,
    revoke_session,
    select_patient,
    set_session_cookie,
)
from api.core.auth_account import (  # noqa: E402
    _hash_password,
    _verify_password,
    login_user,
    signup_user,
)
from api.core.auth_admin import (  # noqa: E402
    _AdminAuditEvent,
    _AdminSessionRow,
    _AdminUserRow,
    _revoke_user_sessions,
    _row_to_admin_user,
    admin_delete_user,
    admin_get_user,
    admin_list_sessions,
    admin_list_user_activity,
    admin_list_users,
    admin_patch_user,
    admin_revoke_session,
    change_own_password,
    delete_own_account,
    list_own_sessions,
    revoke_other_sessions,
    revoke_own_session,
    update_own_display_name,
)


__all__ = [
    # configuration
    "REPO_ROOT",
    "AUTH_DB_PATH",
    "SESSION_SECRET_PATH",
    "SESSION_COOKIE_NAME",
    "SESSION_IDLE_HOURS",
    "SESSION_MAX_DAYS",
    "SESSION_SECURE",
    # demo
    "DemoPatientConfig",
    "DEMO_PATIENTS",
    "DEMO_PATIENT_BY_ALIAS",
    "demo_patient_options",
    "demo_patient_option",
    "is_demo_alias",
    "resolve_demo_patient_alias",
    "demo_patient_label",
    # session model + cookie mechanics
    "SessionPrincipal",
    "set_session_cookie",
    "clear_session_cookie",
    "audit_event",
    "init_auth_store",
    "current_session",
    "current_session_including_guest",
    "require_session_or_guest",
    "optional_session_response",
    "begin_demo_session",
    "revoke_session",
    "require_access_session",
    "require_authenticated_session",
    "require_role",
    "select_patient",
    "authorize_patient_access",
    "patient_exists",
    "require_access_session_dep",
    "require_authenticated_session_dep",
    "AccessSessionDep",
    "AuthenticatedSessionDep",
    # account lifecycle
    "login_user",
    "signup_user",
    # admin + self-service
    "admin_list_users",
    "admin_get_user",
    "admin_list_user_activity",
    "admin_patch_user",
    "admin_delete_user",
    "admin_list_sessions",
    "admin_revoke_session",
    "update_own_display_name",
    "change_own_password",
    "list_own_sessions",
    "revoke_own_session",
    "revoke_other_sessions",
    "delete_own_account",
]
