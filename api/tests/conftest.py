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


@pytest.fixture(autouse=True)
def _clear_settings_cache_between_tests():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
