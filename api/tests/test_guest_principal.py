"""Phase 4: guest cookie → SessionPrincipal adapter.

The guest harmonization cookie is the only persistent representation of a
guest session. Phase 1 added a request-boundary adapter so the rest of the
codebase can treat a guest just like any other session principal.
"""

from __future__ import annotations

from fastapi import Request

from api.core import auth as auth_core
from api.core.guest_harmonization import (
    GUEST_COOKIE_NAME,
    GuestCookieState,
    sign_cookie,
)


def _request_with_cookies(cookies: dict[str, str]) -> Request:
    """Build a minimal ASGI scope so we can construct a Request with cookies."""
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = []
    if cookie_header:
        headers.append((b"cookie", cookie_header.encode("ascii")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


def test_guest_principal_from_cookie() -> None:
    state = GuestCookieState(run_ids=("guest_run_abc",))
    cookie_value = sign_cookie(state)
    request = _request_with_cookies({GUEST_COOKIE_NAME: cookie_value})

    principal = auth_core._guest_principal_from_request(request)
    assert principal is not None
    assert principal.mode == "guest"
    assert principal.is_guest is True
    assert principal.is_demo is False
    assert principal.is_authenticated is False
    assert principal.user_id is None
    assert principal.role == "consumer"
    assert principal.guest_run_ids == ("guest_run_abc",)


def test_guest_principal_missing_cookie() -> None:
    request = _request_with_cookies({})
    principal = auth_core._guest_principal_from_request(request)
    assert principal is None


def test_guest_principal_invalid_signature() -> None:
    """A tampered signature should fall back to no principal."""
    request = _request_with_cookies({GUEST_COOKIE_NAME: "garbage.notavalidsig"})
    principal = auth_core._guest_principal_from_request(request)
    assert principal is None


def test_current_session_including_guest_falls_back(tmp_path, monkeypatch) -> None:
    """When the auth cookie is absent but the guest cookie is present,
    ``current_session_including_guest`` returns the synthesized guest."""
    monkeypatch.setattr(auth_core, "AUTH_DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(
        auth_core, "SESSION_SECRET_PATH", tmp_path / "atlas-session.key"
    )

    cookie_value = sign_cookie(GuestCookieState(run_ids=("guest_xyz",)))
    request = _request_with_cookies({GUEST_COOKIE_NAME: cookie_value})

    principal = auth_core.current_session_including_guest(request)
    assert principal is not None
    assert principal.is_guest is True
    assert principal.session_id.startswith("guest-")
