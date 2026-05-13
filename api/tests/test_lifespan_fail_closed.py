"""Lifespan fail-closed regression: plugin trust bootstrap must refuse boot in prod.

The FastAPI ``lifespan`` runs four startup steps. Two of them are security
invariants:

- ``plugin_runtime.reload_manifests`` — signature-verifies every installed
  plugin manifest. A failure here means unsigned / tampered manifests could
  reach the same "no plugins loaded" silent-degrade state as legitimate
  ones.
- ``plugin_runtime.reload_revoked_runs`` — rehydrates the revoked-run set
  from ``runs.db`` so consent revocations survive the restart. A failure
  here means a revoked plugin would regain tool access on the next deploy.

In production these must fail-closed: the lifespan re-raises and the API
refuses to start. In development they log-and-continue so local workflows
aren't blocked by transient breakage.

The non-security startup steps (``seed_demo_aggregate_uploads``,
``purge_events_older_than``) keep their best-effort log-and-continue
contract regardless of environment.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


def _raise_runtime_error(*_args, **_kwargs):
    """Helper monkeypatch target that always raises."""
    raise RuntimeError("simulated plugin trust bootstrap failure")


def _reload_main():
    """Reload ``api.main`` so the module-level ``_settings`` / ``_IS_PRODUCTION``
    snapshot picks up the patched ``ENVIRONMENT``. The lifespan also re-reads
    settings inside, but reloading keeps the test isolated from import order.
    """
    import api.main as api_main

    importlib.reload(api_main)
    return api_main


# ============================================================
# Production: refuse to boot when the trust chain can't be rehydrated
# ============================================================


def test_lifespan_refuses_to_start_when_manifest_load_fails_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Settings refuses to boot in production without ANTHROPIC_API_KEY;
    # supply a placeholder so the test can reach the lifespan gate.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    api_main = _reload_main()
    monkeypatch.setattr(
        api_main.plugin_runtime, "reload_manifests", _raise_runtime_error
    )

    with pytest.raises(RuntimeError, match="simulated plugin trust bootstrap failure"):
        with TestClient(api_main.app):
            # Entering the context manager triggers the lifespan startup;
            # the failure surfaces before the body runs.
            pass


def test_lifespan_refuses_to_start_when_revoked_runs_load_fails_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    api_main = _reload_main()
    # Let reload_manifests succeed; only revoked-runs rehydration fails.
    monkeypatch.setattr(
        api_main.plugin_runtime, "reload_revoked_runs", _raise_runtime_error
    )

    with pytest.raises(RuntimeError, match="simulated plugin trust bootstrap failure"):
        with TestClient(api_main.app):
            pass


# ============================================================
# Development: log-and-continue so local workflows aren't blocked
# ============================================================


def test_lifespan_starts_in_dev_when_manifest_load_fails(monkeypatch, caplog):
    monkeypatch.setenv("ENVIRONMENT", "development")

    api_main = _reload_main()
    monkeypatch.setattr(
        api_main.plugin_runtime, "reload_manifests", _raise_runtime_error
    )

    caplog.set_level("ERROR")
    with TestClient(api_main.app) as client:
        # Boot completed — the health endpoint is reachable.
        res = client.get("/api/health")
        assert res.status_code == 200

    # The failure was logged (via logger.exception) even though boot continued.
    assert any(
        "reload_manifests failed" in record.message for record in caplog.records
    )


def test_lifespan_starts_in_dev_when_revoked_runs_load_fails(monkeypatch, caplog):
    monkeypatch.setenv("ENVIRONMENT", "development")

    api_main = _reload_main()
    monkeypatch.setattr(
        api_main.plugin_runtime, "reload_revoked_runs", _raise_runtime_error
    )

    caplog.set_level("ERROR")
    with TestClient(api_main.app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200

    assert any(
        "reload_revoked_runs failed" in record.message for record in caplog.records
    )


# ============================================================
# Non-security steps stay best-effort even in production
# ============================================================


def test_lifespan_starts_in_prod_when_seeder_fails(monkeypatch, caplog):
    """Seed/purge failures must NEVER block boot, in any environment."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    api_main = _reload_main()
    monkeypatch.setattr(api_main, "seed_demo_aggregate_uploads", _raise_runtime_error)

    caplog.set_level("ERROR")
    with TestClient(api_main.app) as client:
        # Boot completes even though the seeder raised.
        res = client.get("/api/health")
        assert res.status_code == 200

    assert any(
        "seed_demo_aggregate_uploads failed" in record.message
        for record in caplog.records
    )
