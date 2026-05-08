"""Tests for MultiPassFHIRScoutPipeline (SCOUT-T02).

Covers:
- Registration in the pipeline registry
- Metadata distinctness (name, architecture)
- _augmented_passes() dispatch logic:
  - skips absent resource types
  - attaches page hints
  - attaches section hints
  - preserves pass metadata (schema, versions, backend, model)
  - returns empty list when all passes are absent
  - returns empty list when presence dict is empty
  - does not mutate the shared _PASSES list
- Pass 0 schema/prompt resolution returns DocumentMap and _DOCUMENT_MAP_PROMPT
"""

from __future__ import annotations

from lib.extract.pipelines.multipass_fhir import (
    _DOCUMENT_MAP_PROMPT,
    _PASSES,
    DocumentMap,
    MultiPassFHIRScoutPipeline,
    ResourcePresence,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _new_scout_pipeline() -> MultiPassFHIRScoutPipeline:
    """Instantiate MultiPassFHIRScoutPipeline without calling __init__
    (avoids setting up cache / backend dependencies)."""
    return MultiPassFHIRScoutPipeline.__new__(MultiPassFHIRScoutPipeline)


# ---------------------------------------------------------------------------
# Registration + metadata
# ---------------------------------------------------------------------------


def test_scout_pipeline_registered() -> None:
    """multipass-fhir-scout must appear in the global pipeline registry."""
    from lib.extract.pipelines import list_pipelines

    names = [p.name for p in list_pipelines()]
    assert "multipass-fhir-scout" in names


def test_scout_pipeline_metadata_distinct() -> None:
    """Scout pipeline metadata name and architecture must be correct."""
    assert MultiPassFHIRScoutPipeline.metadata.name == "multipass-fhir-scout"
    assert MultiPassFHIRScoutPipeline.metadata.architecture == "scout-then-specialist"


# ---------------------------------------------------------------------------
# _augmented_passes() — dispatch logic
# ---------------------------------------------------------------------------


def test_augmented_passes_skips_absent_resources() -> None:
    """_augmented_passes filters out passes where present=False."""
    pipeline = _new_scout_pipeline()
    doc_map = DocumentMap(
        document_type="other",
        presence={
            "vital_signs": ResourcePresence(present=True),
            "lab_observations": ResourcePresence(present=False),
        },
    )
    result = pipeline._augmented_passes(doc_map)
    assert len(result) == 1
    assert result[0].name == "vital_signs"


def test_augmented_passes_attaches_page_hints() -> None:
    """_augmented_passes appends page numbers to the system_prompt."""
    pipeline = _new_scout_pipeline()
    doc_map = DocumentMap(
        document_type="other",
        presence={
            "vital_signs": ResourcePresence(present=True, pages=[2, 3]),
        },
    )
    result = pipeline._augmented_passes(doc_map)
    assert len(result) == 1
    assert "page(s) [2, 3]" in result[0].system_prompt


def test_augmented_passes_attaches_section_hint() -> None:
    """_augmented_passes appends both page hint and section_hint to the prompt."""
    pipeline = _new_scout_pipeline()
    doc_map = DocumentMap(
        document_type="other",
        presence={
            "vital_signs": ResourcePresence(
                present=True,
                pages=[2],
                section_hint="Last Filed Vital Signs",
            ),
        },
    )
    result = pipeline._augmented_passes(doc_map)
    assert len(result) == 1
    prompt = result[0].system_prompt
    assert "page(s) [2]" in prompt
    assert "Last Filed Vital Signs" in prompt


def test_augmented_passes_preserves_pass_metadata() -> None:
    """schema, schema_version, backend_name, and model are copied unchanged;
    prompt_version gets '+scout' suffix."""
    pipeline = _new_scout_pipeline()
    # Use 'conditions' — a well-known pass in _PASSES
    original = next(p for p in _PASSES if p.name == "conditions")
    doc_map = DocumentMap(
        document_type="other",
        presence={
            "conditions": ResourcePresence(present=True, pages=[1]),
        },
    )
    result = pipeline._augmented_passes(doc_map)
    assert len(result) == 1
    aug = result[0]
    assert aug.schema is original.schema
    assert aug.schema_version == original.schema_version
    assert aug.backend_name == original.backend_name
    assert aug.model == original.model
    assert aug.prompt_version == f"{original.prompt_version}+scout"


def test_augmented_passes_when_all_absent_returns_empty() -> None:
    """No fallback: when no resource is marked present=True, the manifest
    is uninformative and the dispatcher returns an empty pass list. This
    is the visible-failure-mode the user requested — silent fallback was
    masking real Pass 0 failures.

    Discovered live on the cedars-myhealth run: scout was producing
    identical output to default because Pass 0 returned `presence: {}`,
    the dispatcher fell back to all _PASSES, and we paid for Pass 0
    without any cost savings. Strengthening the prompt + removing the
    fallback is the fix."""
    pipeline = _new_scout_pipeline()
    doc_map = DocumentMap(
        document_type="other",
        presence={
            "vital_signs": ResourcePresence(present=False),
            "medications": ResourcePresence(present=False),
            "conditions": ResourcePresence(present=False),
        },
    )
    result = pipeline._augmented_passes(doc_map)
    assert result == []


def test_augmented_passes_when_presence_dict_empty_returns_empty() -> None:
    """No fallback: empty presence dict → empty pass list. The LLM didn't
    fill in the manifest at all. Dispatcher trusts the manifest as-is so
    the failure is visible (bundle.entry == [])."""
    pipeline = _new_scout_pipeline()
    doc_map = DocumentMap(document_type="other")
    result = pipeline._augmented_passes(doc_map)
    assert result == []


def test_augmented_passes_partial_presence_skips_absent_only() -> None:
    """When SOME resources are marked present=True (manifest is informative),
    the dispatcher trusts it and skips the absent ones. Fallback only kicks
    in when the manifest provides NO useful signal."""
    pipeline = _new_scout_pipeline()
    doc_map = DocumentMap(
        document_type="other",
        presence={
            "vital_signs": ResourcePresence(present=True),
            "medications": ResourcePresence(present=False),
            "conditions": ResourcePresence(present=False),
        },
    )
    result = pipeline._augmented_passes(doc_map)
    # Only vital_signs is present — should NOT fall back to all 13
    assert len(result) == 1
    assert result[0].name == "vital_signs"


def test_augmented_passes_does_not_mutate_original_passes() -> None:
    """Calling _augmented_passes must not modify any prompt in _PASSES."""
    pipeline = _new_scout_pipeline()
    # Capture original prompts before calling _augmented_passes
    original_prompts = [p.system_prompt for p in _PASSES]

    doc_map = DocumentMap(
        document_type="other",
        presence={p.name: ResourcePresence(present=True, pages=[1]) for p in _PASSES[:3]},  # type: ignore[misc]
    )
    pipeline._augmented_passes(doc_map)

    # Verify _PASSES is unmodified
    for pass_, original_prompt in zip(_PASSES, original_prompts):
        assert pass_.system_prompt == original_prompt, (
            f"_PASSES[{pass_.name!r}].system_prompt was mutated by _augmented_passes"
        )


# ---------------------------------------------------------------------------
# Pass 0 hook methods
# ---------------------------------------------------------------------------


def test_pass_0_uses_document_map_for_scout() -> None:
    """Scout pipeline's hook methods return _DOCUMENT_MAP_PROMPT and DocumentMap."""
    pipeline = _new_scout_pipeline()
    assert pipeline._pass_0_prompt() is _DOCUMENT_MAP_PROMPT
    assert pipeline._pass_0_schema() is DocumentMap


def test_augmented_passes_logs_warning_when_falling_to_empty(caplog) -> None:
    """When _augmented_passes would return an empty list, it logs a WARN
    so the visible-failure-mode is loud rather than silent."""
    import logging
    pipeline = _new_scout_pipeline()
    doc_map = DocumentMap(document_type="other")
    with caplog.at_level(logging.WARNING):
        result = pipeline._augmented_passes(doc_map)
    assert result == []
    assert any("empty" in r.message.lower() or "absent" in r.message.lower()
               for r in caplog.records)
