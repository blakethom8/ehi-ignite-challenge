import time
from datetime import datetime, timedelta, timezone

import pytest

from api.plugins.consent import (
    ConsentError,
    ConsentExpired,
    ConsentRevoked,
    mint_consent_token,
    new_approval_id,
    verify_consent_token,
)


def _mint(**kw):
    base = dict(
        plugin_id="trial-finder",
        run_id="r_x",
        scope=["diagnoses.active"],
        approver_id="u_clinician_42",
        ttl_seconds=3600,
    )
    base.update(kw)
    return mint_consent_token(**base)


def test_mint_then_verify_roundtrip():
    token = _mint()
    verify_consent_token(token, plugin_id="trial-finder", run_id="r_x")


def test_verify_rejects_plugin_mismatch():
    token = _mint()
    with pytest.raises(ConsentError):
        verify_consent_token(token, plugin_id="med-access", run_id="r_x")


def test_verify_rejects_run_mismatch():
    token = _mint()
    with pytest.raises(ConsentError):
        verify_consent_token(token, plugin_id="trial-finder", run_id="r_y")


def test_verify_rejects_expired():
    past = datetime.now(timezone.utc) - timedelta(seconds=7200)
    token = _mint(ttl_seconds=1, issued_at=past)
    with pytest.raises(ConsentExpired):
        verify_consent_token(token, plugin_id="trial-finder", run_id="r_x")


def test_verify_rejects_tampered_scope():
    token = _mint()
    token.scope.append("medications.active")  # widen scope after signing
    with pytest.raises(ConsentError):
        verify_consent_token(token, plugin_id="trial-finder", run_id="r_x")


def test_revoked_run_id_rejected():
    token = _mint()
    with pytest.raises(ConsentRevoked):
        verify_consent_token(
            token, plugin_id="trial-finder", run_id="r_x", revoked_ids={"r_x"}
        )


def test_approval_id_is_sortable_over_time():
    a = new_approval_id()
    time.sleep(0.005)
    b = new_approval_id()
    assert a < b
