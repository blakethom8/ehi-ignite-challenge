"""Tests for ehi_atlas.extract.cache — content-hash deterministic cache."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ehi_atlas.extract.cache import CacheKey, ExtractionCache, hash_file


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_key(
    file_sha: str = "abc123",
    prompt_version: str = "v0.1.0",
    schema_version: str = "extraction-result-v0.1.0",
    model_name: str = "claude-opus-4-7",
) -> CacheKey:
    return CacheKey(
        file_sha256=file_sha,
        prompt_version=prompt_version,
        schema_version=schema_version,
        model_name=model_name,
    )


_SAMPLE_VALUE: dict = {
    "observations": [
        {"code": "2160-0", "display": "Creatinine", "value": 1.4, "unit": "mg/dL"}
    ]
}


# ---------------------------------------------------------------------------
# 1. Cache miss returns None
# ---------------------------------------------------------------------------


def test_cache_miss_returns_none(tmp_path: Path) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    key = _make_key()
    assert cache.get(key) is None


# ---------------------------------------------------------------------------
# 2. put() / get() roundtrip
# ---------------------------------------------------------------------------


def test_cache_put_then_get_roundtrip(tmp_path: Path) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    key = _make_key()
    cache.put(key, _SAMPLE_VALUE)
    result = cache.get(key)
    assert result == _SAMPLE_VALUE


# ---------------------------------------------------------------------------
# 3. Different prompt_version → different cache file (no collision)
# ---------------------------------------------------------------------------


def test_cache_key_with_different_prompt_version_does_not_collide(
    tmp_path: Path,
) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    key_v1 = _make_key(prompt_version="v0.1.0")
    key_v2 = _make_key(prompt_version="v0.2.0")

    assert key_v1.digest() != key_v2.digest(), (
        "Different prompt versions must yield different digests"
    )

    cache.put(key_v1, {"version": "v1"})
    # v2 has not been stored — must be a miss
    assert cache.get(key_v2) is None
    # v1 is still retrievable
    assert cache.get(key_v1) == {"version": "v1"}


# ---------------------------------------------------------------------------
# 4. Different model_name → different cache file (no collision)
# ---------------------------------------------------------------------------


def test_cache_key_with_different_model_name_does_not_collide(
    tmp_path: Path,
) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    key_opus = _make_key(model_name="claude-opus-4-7")
    key_sonnet = _make_key(model_name="claude-sonnet-4-6")

    assert key_opus.digest() != key_sonnet.digest(), (
        "Different model names must yield different digests"
    )

    cache.put(key_opus, {"model": "opus"})
    assert cache.get(key_sonnet) is None
    assert cache.get(key_opus) == {"model": "opus"}


# ---------------------------------------------------------------------------
# 5. invalidate() removes exactly one entry; others unaffected
# ---------------------------------------------------------------------------


def test_cache_invalidate_removes_single_entry(tmp_path: Path) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    key_a = _make_key(file_sha="sha-a")
    key_b = _make_key(file_sha="sha-b")

    cache.put(key_a, {"entry": "a"})
    cache.put(key_b, {"entry": "b"})

    removed = cache.invalidate(key_a)
    assert removed is True

    # key_a is gone
    assert cache.get(key_a) is None
    # key_b is unaffected
    assert cache.get(key_b) == {"entry": "b"}

    # Invalidating an already-absent key returns False
    assert cache.invalidate(key_a) is False


# ---------------------------------------------------------------------------
# 6. clear_all() returns correct count; has() returns False for all
# ---------------------------------------------------------------------------


def test_cache_clear_all_returns_count(tmp_path: Path) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    keys = [_make_key(file_sha=f"sha-{i}") for i in range(3)]

    for k in keys:
        cache.put(k, {"i": k.file_sha256})

    count = cache.clear_all()
    assert count == 3

    for k in keys:
        assert cache.has(k) is False


# ---------------------------------------------------------------------------
# 7. hash_file() is stable across two calls
# ---------------------------------------------------------------------------


def test_hash_file_is_stable(tmp_path: Path) -> None:
    fixture = tmp_path / "sample.bin"
    fixture.write_bytes(b"\x00\x01\x02\x03" * 1024)

    digest_1 = hash_file(fixture)
    digest_2 = hash_file(fixture)

    assert digest_1 == digest_2
    assert len(digest_1) == 64, "SHA-256 hex digest is 64 characters"


# ---------------------------------------------------------------------------
# 8. Atomic write leaves no .tmp files behind
# ---------------------------------------------------------------------------


def test_atomic_write_does_not_leave_tmp_files(tmp_path: Path) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    key = _make_key()
    cache.put(key, _SAMPLE_VALUE)

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Unexpected .tmp files remain: {tmp_files}"
