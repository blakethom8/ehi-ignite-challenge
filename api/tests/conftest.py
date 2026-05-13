"""Shared test fixtures.

The settings module (``api.settings.get_settings``) is ``@lru_cache``-d, so
tests that mutate ``os.environ`` after import (via ``monkeypatch.setenv``,
``patch.dict``, or manual assignment) must invalidate the cache before the
code under test re-reads any settings value.

The ``autouse`` fixture below clears the cache after every test so the next
test starts from a clean slate. Tests that mutate env vars *during* a test
should call ``get_settings.cache_clear()`` themselves immediately after the
mutation — there's no way to invalidate the cache automatically when env
vars change.
"""

from __future__ import annotations

import pytest

from api.settings import get_settings


# Fixed fixture patient ids used by tests that pre-date the workspace-ownership
# gate introduced in bfb6563. The gate restricts authenticated sessions to
# workspaces they own; these ids are Synthea showcase patients and plugin
# demo fixtures that no test user can plausibly own. Allowlisting them here
# keeps the production gate untouched while letting the legacy tests pass.
# test_auth_api's gate-coverage tests use *different* ids (demo aliases and
# DEMO_PATIENTS[0].actual_patient_id), so the allowlist doesn't shadow them.
_TEST_WORKSPACE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "8.4127.881",                            # plugin Hollister fixture
        "92c9a4f3-162d-4979-96fa-d81bf4641125",  # surgical-risk Synthea showcase
        "workspace-downstream",                  # harmonize publish test
        "workspace-clinical-artifacts",          # harmonize publish test
        "workspace-assistant",                   # harmonize publish test
    }
)


@pytest.fixture(autouse=True)
def _clear_settings_cache_between_tests():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _allow_test_workspace_ids():
    from api.core import auth as auth_module

    original = auth_module._authenticated_workspace_access_allowed

    def patched(user_id, patient_id):
        if patient_id in _TEST_WORKSPACE_ALLOWLIST:
            return True
        return original(user_id, patient_id)

    auth_module._authenticated_workspace_access_allowed = patched
    try:
        yield
    finally:
        auth_module._authenticated_workspace_access_allowed = original
