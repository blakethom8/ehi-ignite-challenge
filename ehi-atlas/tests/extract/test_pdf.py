"""Tests for ehi_atlas.extract.pdf — vision-LLM extraction wrapper.

All tests mock the Anthropic client. No real API calls are made. The suite
runs fully offline without ANTHROPIC_API_KEY.

Covered scenarios:
  1. Cache hit → API is NOT called; cached value is returned.
  2. Cache miss → API IS called once; cache entry exists after.
  3. skip_cache=True → API called even when cache is populated; result re-cached.
  4. Return type is validated ExtractionResult with correct fields.
  5. Model emits text block instead of tool_use → RuntimeError with message.
  6. Different prompt_version → different cache keys → API called both times.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from anthropic.types import Message

from ehi_atlas.extract.cache import CacheKey, ExtractionCache, hash_file
from ehi_atlas.extract.pdf import (
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    DEFAULT_PROMPT_VERSION,
    DEFAULT_SCHEMA_VERSION,
    extract_from_pdf,
    extract_lab_pdf,
)
from ehi_atlas.extract.schemas import ExtractionResult

# After the backend-abstraction refactor the cache key embeds the backend
# identifier as well, so tests build the same composite that pdf.py uses
# internally: ``"<backend-name>/<model-name>"``.
_DEFAULT_CACHE_MODEL_ID = f"{DEFAULT_BACKEND}/{DEFAULT_MODEL}"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# A minimal valid ExtractionResult dict matching the discriminated union schema.
# Covers the "lab-report" branch so document_type selects ExtractedLabReport.
_SAMPLE_EXTRACTION: dict[str, Any] = {
    "document": {
        "document_type": "lab-report",
        "document_date": "2025-09-12",
        "ordering_provider": "Dr. Smith",
        "lab_name": "Quest Diagnostics",
        "patient_name_seen": "Rhett Thomson",
        "results": [
            {
                "test_name": "Creatinine",
                "loinc_code": "2160-0",
                "value_quantity": 1.4,
                "value_string": None,
                "unit": "mg/dL",
                "reference_range_low": 0.6,
                "reference_range_high": 1.3,
                "flag": "H",
                "effective_date": "2025-09-12",
                "bbox": {"page": 2, "x1": 72.0, "y1": 574.0, "x2": 540.0, "y2": 590.0},
            }
        ],
    },
    "extraction_confidence": 0.97,
    "extraction_model": "claude-opus-4-7",
    "extraction_prompt_version": "v0.1.0",
}


def _make_mock_api_client(tool_input: dict | None = None) -> Mock:
    """Return a mock Anthropic client whose messages.create returns a tool_use block."""
    if tool_input is None:
        tool_input = _SAMPLE_EXTRACTION

    mock_tool_use = Mock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = tool_input

    mock_message = Mock(spec=Message)
    mock_message.content = [mock_tool_use]
    mock_message.stop_reason = "tool_use"

    api_client = Mock()
    api_client.messages.create.return_value = mock_message
    return api_client


def _make_pdf(tmp_path: Path, content: bytes = b"%PDF-1.4 fake") -> Path:
    """Write a minimal fake PDF file and return its path."""
    p = tmp_path / "data.pdf"
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------
# 1. Cache hit — API is NOT called
# ---------------------------------------------------------------------------


def test_extract_uses_cache_on_hit(tmp_path: Path) -> None:
    """Pre-populate the cache; extract_from_pdf must return cached value without
    calling the API at all."""
    pdf_path = _make_pdf(tmp_path)
    cache = ExtractionCache(cache_dir=tmp_path / "cache")

    # Pre-populate
    file_hash = hash_file(pdf_path)
    key = CacheKey(
        file_sha256=file_hash,
        prompt_version=DEFAULT_PROMPT_VERSION,
        schema_version=DEFAULT_SCHEMA_VERSION,
        model_name=_DEFAULT_CACHE_MODEL_ID,
    )
    cache.put(key, _SAMPLE_EXTRACTION)

    api_client = _make_mock_api_client()

    result = extract_from_pdf(
        pdf_path,
        cache=cache,
        api_client=api_client,
        skip_cache=False,
    )

    # API must NOT have been called
    api_client.messages.create.assert_not_called()

    # Result is valid ExtractionResult
    assert isinstance(result, ExtractionResult)
    assert result.extraction_confidence == pytest.approx(0.97)


# ---------------------------------------------------------------------------
# 2. Cache miss — API IS called; cache entry exists after
# ---------------------------------------------------------------------------


def test_extract_calls_api_on_miss_and_caches(tmp_path: Path) -> None:
    """On a cache miss, extract_from_pdf must call the API exactly once and
    then write the result to the cache."""
    pdf_path = _make_pdf(tmp_path)
    cache = ExtractionCache(cache_dir=tmp_path / "cache")
    api_client = _make_mock_api_client()

    result = extract_from_pdf(
        pdf_path,
        cache=cache,
        api_client=api_client,
        skip_cache=False,
    )

    # API was called exactly once
    api_client.messages.create.assert_called_once()

    # Cache entry now exists
    file_hash = hash_file(pdf_path)
    key = CacheKey(
        file_sha256=file_hash,
        prompt_version=DEFAULT_PROMPT_VERSION,
        schema_version=DEFAULT_SCHEMA_VERSION,
        model_name=_DEFAULT_CACHE_MODEL_ID,
    )
    assert cache.has(key), "Cache entry should exist after a successful API call"

    # Result is valid
    assert isinstance(result, ExtractionResult)
    assert result.document.document_type == "lab-report"


# ---------------------------------------------------------------------------
# 3. skip_cache=True — API called even when cache is populated; re-cached
# ---------------------------------------------------------------------------


def test_extract_skip_cache_forces_api_call(tmp_path: Path) -> None:
    """When skip_cache=True, extract_from_pdf must call the API regardless of
    whether a cache entry is present, and must overwrite it afterwards."""
    pdf_path = _make_pdf(tmp_path)
    cache = ExtractionCache(cache_dir=tmp_path / "cache")

    # Pre-populate with stale data
    file_hash = hash_file(pdf_path)
    key = CacheKey(
        file_sha256=file_hash,
        prompt_version=DEFAULT_PROMPT_VERSION,
        schema_version=DEFAULT_SCHEMA_VERSION,
        model_name=_DEFAULT_CACHE_MODEL_ID,
    )
    stale = dict(_SAMPLE_EXTRACTION)
    stale["extraction_confidence"] = 0.50  # stale value
    cache.put(key, stale)

    api_client = _make_mock_api_client()  # returns 0.97

    result = extract_from_pdf(
        pdf_path,
        cache=cache,
        api_client=api_client,
        skip_cache=True,
    )

    # API was called (not skipped)
    api_client.messages.create.assert_called_once()

    # The result reflects the fresh API response, not the stale cache
    assert result.extraction_confidence == pytest.approx(0.97)

    # Cache was updated with fresh result
    cached = cache.get(key)
    assert cached is not None
    assert cached["extraction_confidence"] == pytest.approx(0.97)


# ---------------------------------------------------------------------------
# 4. Return type — validated ExtractionResult with correct fields
# ---------------------------------------------------------------------------


def test_extract_validates_against_schema(tmp_path: Path) -> None:
    """The returned object must be a fully validated ExtractionResult instance
    with the correct nested fields populated."""
    pdf_path = _make_pdf(tmp_path)
    cache = ExtractionCache(cache_dir=tmp_path / "cache")
    api_client = _make_mock_api_client()

    result = extract_from_pdf(pdf_path, cache=cache, api_client=api_client)

    assert isinstance(result, ExtractionResult)
    # extraction_model is now overridden by the orchestrator to the canonical
    # "<backend>/<model>" identifier so models can't hallucinate their own name
    # into the output (Gemma 4 was caught doing this).
    assert result.extraction_model == _DEFAULT_CACHE_MODEL_ID
    assert result.extraction_prompt_version == "v0.1.0"
    assert result.extraction_confidence == pytest.approx(0.97)

    # Document is a lab report with one result
    from ehi_atlas.extract.schemas import ExtractedLabReport, ExtractedLabResult, BBox
    assert isinstance(result.document, ExtractedLabReport)
    assert result.document.lab_name == "Quest Diagnostics"
    assert len(result.document.results) == 1

    creatinine = result.document.results[0]
    assert isinstance(creatinine, ExtractedLabResult)
    assert creatinine.test_name == "Creatinine"
    assert creatinine.loinc_code == "2160-0"
    assert creatinine.value_quantity == pytest.approx(1.4)
    assert creatinine.unit == "mg/dL"
    assert creatinine.flag == "H"

    # BBox is populated and correct
    assert isinstance(creatinine.bbox, BBox)
    assert creatinine.bbox.page == 2
    assert creatinine.bbox.to_locator_string() == "page=2;bbox=72,574,540,590"


# ---------------------------------------------------------------------------
# 5. Model fails to emit tool_use — RuntimeError with descriptive message
# ---------------------------------------------------------------------------


def test_extract_raises_when_model_fails_to_emit_tool(tmp_path: Path) -> None:
    """When the model returns a text block instead of a tool_use block,
    extract_from_pdf must raise RuntimeError with a descriptive message."""
    pdf_path = _make_pdf(tmp_path)
    cache = ExtractionCache(cache_dir=tmp_path / "cache")

    # Mock returns a text block, not a tool_use block
    mock_text_block = Mock()
    mock_text_block.type = "text"
    mock_text_block.text = "I cannot process this document."

    mock_message = Mock(spec=Message)
    mock_message.content = [mock_text_block]
    mock_message.stop_reason = "end_turn"

    api_client = Mock()
    api_client.messages.create.return_value = mock_message

    with pytest.raises(RuntimeError) as exc_info:
        extract_from_pdf(pdf_path, cache=cache, api_client=api_client)

    err = str(exc_info.value)
    assert "emit_extraction" in err or "tool" in err.lower(), (
        f"Error message should mention the missing tool call; got: {err!r}"
    )
    assert "stop_reason" in err, (
        f"Error message should include stop_reason; got: {err!r}"
    )


# ---------------------------------------------------------------------------
# 6. Different prompt_version → different cache keys → API called both times
# ---------------------------------------------------------------------------


def test_cache_key_changes_with_prompt_version(tmp_path: Path) -> None:
    """Extracting the same PDF twice with different prompt_versions must use
    different cache keys and therefore call the API both times."""
    pdf_path = _make_pdf(tmp_path)
    cache = ExtractionCache(cache_dir=tmp_path / "cache")
    api_client = _make_mock_api_client()

    # First extraction with v0.1.0
    extract_from_pdf(
        pdf_path,
        cache=cache,
        api_client=api_client,
        prompt_version="v0.1.0",
    )

    # Second extraction with v0.2.0 (bumped)
    extract_from_pdf(
        pdf_path,
        cache=cache,
        api_client=api_client,
        prompt_version="v0.2.0",
    )

    # API was called exactly twice (different keys → both were cache misses)
    assert api_client.messages.create.call_count == 2, (
        "Each distinct prompt_version must result in a fresh API call"
    )

    # Both keys exist in the cache
    file_hash = hash_file(pdf_path)
    key_v1 = CacheKey(
        file_sha256=file_hash,
        prompt_version="v0.1.0",
        schema_version=DEFAULT_SCHEMA_VERSION,
        model_name=_DEFAULT_CACHE_MODEL_ID,
    )
    key_v2 = CacheKey(
        file_sha256=file_hash,
        prompt_version="v0.2.0",
        schema_version=DEFAULT_SCHEMA_VERSION,
        model_name=_DEFAULT_CACHE_MODEL_ID,
    )
    assert key_v1.digest() != key_v2.digest(), "Cache keys must differ"
    assert cache.has(key_v1)
    assert cache.has(key_v2)
