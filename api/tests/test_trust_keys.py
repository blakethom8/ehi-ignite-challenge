"""H0.2 regression: production must refuse the file-based secret fallback.

The Atlas signing key roots the plugin trust chain; the session secret
roots cookie signing. Both already check env vars first and only fall
back to a plaintext file in ``data/``. The fix is to make production
explicitly refuse the file fallback so a missing env var fails fast
instead of silently materializing a key on disk.
"""

from __future__ import annotations

import importlib

import pytest

from api.core import auth as auth_core
from api.trust import keys as trust_keys


# ============================================================
# Atlas signing key
# ============================================================


def test_atlas_keypair_raises_when_production_and_no_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Settings refuses to boot in production without ANTHROPIC_API_KEY;
    # supply a placeholder so the test can exercise the signing-key gate.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("ATLAS_SIGNING_KEY", raising=False)
    # Point at a non-existent file so we'd fall back to generation if the
    # production gate were absent.
    fresh_path = tmp_path / "atlas-signing.key"
    assert not fresh_path.exists()

    with pytest.raises(RuntimeError, match="ATLAS_SIGNING_KEY"):
        trust_keys.atlas_keypair(path=fresh_path, reset=True)

    # The file gate must not have written a key as a side effect of failing.
    assert not fresh_path.exists()


def test_atlas_keypair_falls_back_in_development(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ATLAS_SIGNING_KEY", raising=False)
    fresh_path = tmp_path / "atlas-signing.key"

    sk, pk = trust_keys.atlas_keypair(path=fresh_path, reset=True)

    assert sk is not None
    assert pk is not None
    # Dev path is allowed to materialize the key on disk.
    assert fresh_path.exists()


def test_atlas_keypair_uses_env_in_production(monkeypatch, tmp_path):
    # Generate a key out-of-band so we can present a real b64 value to the env.
    from api.trust.signatures import generate_keypair, private_key_to_b64

    sk_seed, _ = generate_keypair()
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Settings refuses to boot in production without ANTHROPIC_API_KEY;
    # supply a placeholder so the test can exercise the signing-key gate.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ATLAS_SIGNING_KEY", private_key_to_b64(sk_seed))
    fresh_path = tmp_path / "atlas-signing.key"

    sk, pk = trust_keys.atlas_keypair(path=fresh_path, reset=True)
    assert sk is not None
    assert pk is not None
    # Env-provided key must not write to disk.
    assert not fresh_path.exists()


# ============================================================
# Session signing secret
# ============================================================


def test_session_secret_raises_when_production_and_no_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Settings refuses to boot in production without ANTHROPIC_API_KEY;
    # supply a placeholder so the test can exercise the signing-key gate.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("EHI_SESSION_SECRET", raising=False)
    fresh_path = tmp_path / "atlas-session.key"
    monkeypatch.setattr(auth_core, "SESSION_SECRET_PATH", fresh_path)
    assert not fresh_path.exists()

    with pytest.raises(RuntimeError, match="EHI_SESSION_SECRET"):
        auth_core._session_secret()

    assert not fresh_path.exists()


def test_session_secret_falls_back_in_development(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("EHI_SESSION_SECRET", raising=False)
    fresh_path = tmp_path / "atlas-session.key"
    monkeypatch.setattr(auth_core, "SESSION_SECRET_PATH", fresh_path)

    secret = auth_core._session_secret()

    assert isinstance(secret, bytes)
    assert len(secret) >= 16
    assert fresh_path.exists()


def test_session_secret_uses_env_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Settings refuses to boot in production without ANTHROPIC_API_KEY;
    # supply a placeholder so the test can exercise the signing-key gate.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("EHI_SESSION_SECRET", "prod-supplied-secret-value")
    fresh_path = tmp_path / "atlas-session.key"
    monkeypatch.setattr(auth_core, "SESSION_SECRET_PATH", fresh_path)

    secret = auth_core._session_secret()

    assert secret == b"prod-supplied-secret-value"
    assert not fresh_path.exists()


# ============================================================
# Guest harmonization secret (H0.14 — mirror of H0.2 for the third key)
# ============================================================


def test_guest_secret_raises_when_production_and_no_env(monkeypatch, tmp_path):
    from api.core import guest_harmonization as guest_mod

    monkeypatch.setenv("ENVIRONMENT", "production")
    # Settings refuses to boot in production without ANTHROPIC_API_KEY;
    # supply a placeholder so the test can exercise the signing-key gate.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("GUEST_HARMONIZATION_SECRET", raising=False)
    fresh_path = tmp_path / "atlas-guest-harmonization.key"
    monkeypatch.setattr(guest_mod, "GUEST_SECRET_PATH", fresh_path)

    with pytest.raises(RuntimeError, match="GUEST_HARMONIZATION_SECRET"):
        guest_mod._guest_secret()

    assert not fresh_path.exists()


def test_guest_secret_falls_back_in_development(monkeypatch, tmp_path):
    from api.core import guest_harmonization as guest_mod

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("GUEST_HARMONIZATION_SECRET", raising=False)
    fresh_path = tmp_path / "atlas-guest-harmonization.key"
    monkeypatch.setattr(guest_mod, "GUEST_SECRET_PATH", fresh_path)

    secret = guest_mod._guest_secret()

    assert isinstance(secret, bytes)
    assert len(secret) >= 16
    assert fresh_path.exists()


def test_guest_secret_uses_env_in_production(monkeypatch, tmp_path):
    from api.core import guest_harmonization as guest_mod

    monkeypatch.setenv("ENVIRONMENT", "production")
    # Settings refuses to boot in production without ANTHROPIC_API_KEY;
    # supply a placeholder so the test can exercise the signing-key gate.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("GUEST_HARMONIZATION_SECRET", "prod-supplied-guest-secret")
    fresh_path = tmp_path / "atlas-guest-harmonization.key"
    monkeypatch.setattr(guest_mod, "GUEST_SECRET_PATH", fresh_path)

    secret = guest_mod._guest_secret()

    assert secret == b"prod-supplied-guest-secret"
    assert not fresh_path.exists()
