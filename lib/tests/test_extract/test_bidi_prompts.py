"""Tests for BIDI-T02 bidirectional-scout prompt flavors.

Verifies that the two new scout-prompt constants and the get_scout_prompt()
helper behave correctly and that the existing _DOCUMENT_MAP_PROMPT is
unchanged.
"""

import pytest

from lib.extract.pipelines.multipass_fhir import (
    _DOCUMENT_MAP_PROMPT,
    _DOCUMENT_MAP_PROMPT_EVENTS,
    _DOCUMENT_MAP_PROMPT_TABLES,
    get_scout_prompt,
)

_EXPECTED_RESOURCE_TYPES = [
    "conditions",
    "medications",
    "allergies",
    "immunizations",
    "lab_observations",
    "vital_signs",
    "encounter",
    "practitioner",
    "organization",
    "clinical_notes",
    "patient_demographics",
    "coverage",
    "social_history",
]


def test_scout_flavor_returns_distinct_prompts() -> None:
    """events and tables flavors must produce different prompt strings."""
    assert get_scout_prompt("events") != get_scout_prompt("tables")


def test_scout_flavor_unknown_raises() -> None:
    """An unrecognised flavor must raise ValueError."""
    with pytest.raises(ValueError, match="unknown scout flavor"):
        get_scout_prompt("random")  # type: ignore[arg-type]


def test_both_prompts_share_resource_type_enumeration() -> None:
    """Both flavors must enumerate all 13 known resource type names."""
    events_prompt = get_scout_prompt("events")
    tables_prompt = get_scout_prompt("tables")
    for name in _EXPECTED_RESOURCE_TYPES:
        assert name in events_prompt, f"events prompt missing resource type: {name!r}"
        assert name in tables_prompt, f"tables prompt missing resource type: {name!r}"


def test_events_flavor_emphasizes_encounters_or_narrative() -> None:
    """events prompt stresses encounters/narrative; tables prompt stresses structured data."""
    events_prompt = get_scout_prompt("events")
    tables_prompt = get_scout_prompt("tables")

    # events flavor must mention narrative and/or encounter emphasis
    assert any(
        kw in events_prompt for kw in ("narrative", "NARRATIVE", "encounter", "ENCOUNTER")
    ), "events prompt should emphasize narrative/encounter content"

    # tables flavor must mention structured-table emphasis and exhaustive enumeration
    assert any(
        kw in tables_prompt for kw in ("STRUCTURED", "structured", "exhaustive", "EXHAUSTIVE")
    ), "tables prompt should emphasize structured/exhaustive table content"


def test_default_scout_prompt_unchanged() -> None:
    """_DOCUMENT_MAP_PROMPT must still be importable and contain the resource enumeration."""
    assert isinstance(_DOCUMENT_MAP_PROMPT, str), "_DOCUMENT_MAP_PROMPT should be a string"
    assert len(_DOCUMENT_MAP_PROMPT) > 0, "_DOCUMENT_MAP_PROMPT should be non-empty"
    for name in _EXPECTED_RESOURCE_TYPES:
        assert name in _DOCUMENT_MAP_PROMPT, (
            f"default scout prompt missing resource type: {name!r} — "
            "this is a regression; the default prompt must not be modified"
        )
