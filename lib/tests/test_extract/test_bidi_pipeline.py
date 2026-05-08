"""Tests for MultiPassFHIRBidiScoutPipeline (BIDI-T03).

Covers:
- Registration in the pipeline registry
- Metadata distinctness (name, architecture)
- Specialist-pass dispatch (regression: bidi subclass must not change logic)
- _doc_context_from_pass_0 runs two scouts and reconciles
- _merge_to_bundle attaches scout-reconciliation extension
- _merge_to_bundle does NOT add extension when reconciliation is absent
- Parent scout pipeline still works after _invoke_pass_0 factoring (T7)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from lib.extract.pipelines.multipass_fhir import (
    _DOCUMENT_MAP_PROMPT,
    _PASSES,
    DocumentContext,
    DocumentMap,
    MapReconciliation,
    MultiPassFHIRBidiScoutPipeline,
    MultiPassFHIRScoutPipeline,
    ResourcePresence,
    reconcile_document_maps,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_bidi() -> MultiPassFHIRBidiScoutPipeline:
    """Instantiate without __init__ (avoids cache/backend setup)."""
    inst = MultiPassFHIRBidiScoutPipeline.__new__(MultiPassFHIRBidiScoutPipeline)
    # Reset class-level stash so tests are independent
    inst._scout_reconciliation = None
    inst._doc_map = None
    return inst


def _synthetic_map(
    *,
    present_keys: list[str] | None = None,
    patient_name: str | None = None,
) -> DocumentMap:
    """Build a minimal DocumentMap for testing."""
    presence: dict[str, ResourcePresence] = {}
    for key in (present_keys or []):
        presence[key] = ResourcePresence(present=True, pages=[1])  # type: ignore[literal-required]
    return DocumentMap(
        document_type="other",
        patient_name=patient_name,
        presence=presence,  # type: ignore[arg-type]
    )


def _synthetic_reconciliation(
    map_a: DocumentMap | None = None,
    map_b: DocumentMap | None = None,
) -> MapReconciliation:
    """Build a synthetic MapReconciliation from two minimal maps."""
    if map_a is None:
        map_a = _synthetic_map(present_keys=["conditions"])
    if map_b is None:
        map_b = _synthetic_map(present_keys=["medications"])
    return reconcile_document_maps(map_a, map_b, strategy="union")


# ---------------------------------------------------------------------------
# Test 1 — registration
# ---------------------------------------------------------------------------


def test_bidi_pipeline_registered() -> None:
    """multipass-fhir-bidi-scout must appear in the global pipeline registry."""
    from lib.extract.pipelines import list_pipelines

    names = [p.name for p in list_pipelines()]
    assert "multipass-fhir-bidi-scout" in names


# ---------------------------------------------------------------------------
# Test 2 — metadata distinctness
# ---------------------------------------------------------------------------


def test_bidi_pipeline_metadata_distinct() -> None:
    """Bidi pipeline metadata architecture must differ from the parent scout."""
    assert (
        MultiPassFHIRBidiScoutPipeline.metadata.architecture
        == "bidirectional-scout-then-specialist"
    )
    assert (
        MultiPassFHIRBidiScoutPipeline.metadata.architecture
        != MultiPassFHIRScoutPipeline.metadata.architecture
    )
    assert MultiPassFHIRBidiScoutPipeline.metadata.name == "multipass-fhir-bidi-scout"
    assert MultiPassFHIRBidiScoutPipeline.metadata.name != MultiPassFHIRScoutPipeline.metadata.name


# ---------------------------------------------------------------------------
# Test 3 — specialist dispatch regression
# ---------------------------------------------------------------------------


def test_bidi_inherits_specialist_passes_logic() -> None:
    """_specialist_passes on the bidi subclass returns the same shape as the
    parent scout pipeline when a DocumentMap is supplied via _doc_map."""
    bidi = _new_bidi()
    scout = MultiPassFHIRScoutPipeline.__new__(MultiPassFHIRScoutPipeline)
    scout._doc_map = None

    # Supply a synthetic doc_map with a known presence entry on both
    doc_map = _synthetic_map(present_keys=["conditions", "medications"])
    bidi._doc_map = doc_map
    scout._doc_map = doc_map

    bidi_passes = bidi._specialist_passes(doc_map)
    scout_passes = scout._specialist_passes(doc_map)

    # Same number of passes
    assert len(bidi_passes) == len(scout_passes)
    # Same names in same order
    assert [p.name for p in bidi_passes] == [p.name for p in scout_passes]
    # Same schemas
    for bp, sp in zip(bidi_passes, scout_passes):
        assert bp.schema is sp.schema


# ---------------------------------------------------------------------------
# Test 4 — _doc_context_from_pass_0 invokes two scouts and reconciles
# ---------------------------------------------------------------------------


def test_doc_context_from_pass_0_invokes_two_scouts_and_reconciles() -> None:
    """_doc_context_from_pass_0 must call _invoke_pass_0 a second time and
    store the MapReconciliation on self._scout_reconciliation."""
    bidi = _new_bidi()

    # The first scout output (events flavor) — supplied as pass_0_output
    map_a = _synthetic_map(present_keys=["conditions"], patient_name="Alice")
    # The second scout output (tables flavor) — returned by the mock
    map_b = _synthetic_map(present_keys=["medications"], patient_name=None)

    # Provide the required attrs that extract() normally sets
    bidi._pass_0_pdf_bytes = b"fake-pdf-bytes"
    bidi._pass_0_pdf_hash = "abc123"
    bidi._pass_0_skip_cache = True

    with patch.object(bidi, "_invoke_pass_0", return_value=map_b) as mock_invoke:
        result = bidi._doc_context_from_pass_0(map_a)

    # Must have called the second scout
    mock_invoke.assert_called_once()
    call_kwargs = mock_invoke.call_args.kwargs
    assert call_kwargs["pdf_bytes"] == b"fake-pdf-bytes"
    assert call_kwargs["pdf_hash"] == "abc123"
    assert call_kwargs["skip_cache"] is True
    # Distinct prompt_version so cache keys don't collide
    assert "bidi" in call_kwargs.get("prompt_version", "")

    # Reconciliation must be stashed
    assert bidi._scout_reconciliation is not None
    rec = bidi._scout_reconciliation
    assert isinstance(rec, MapReconciliation)
    # Union: both conditions (from A) and medications (from B) should be present
    assert "conditions" in rec.reconciled.presence
    assert "medications" in rec.reconciled.presence
    # patient_name: prefer A
    assert rec.reconciled.patient_name == "Alice"

    # Return value must be the reconciled DocumentMap
    assert result is rec.reconciled


# ---------------------------------------------------------------------------
# Test 5 — _merge_to_bundle attaches reconciliation extension
# ---------------------------------------------------------------------------


def test_merge_to_bundle_attaches_reconciliation_extension() -> None:
    """When _scout_reconciliation is set, _merge_to_bundle appends a
    scout-reconciliation extension to bundle.meta.extension."""
    bidi = _new_bidi()

    # Set up a synthetic reconciliation
    rec = _synthetic_reconciliation()
    bidi._scout_reconciliation = rec
    bidi._doc_map = rec.reconciled

    # We need to call super()._merge_to_bundle but can't load a real PDF.
    # Patch the parent's _merge_to_bundle to return a minimal stub bundle.
    stub_bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [],
        "meta": {
            "source": "extracted://other/test",
            "extension": [
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-pipeline",
                    "valueString": "multipass-fhir",
                }
            ],
        },
    }

    with patch.object(
        MultiPassFHIRScoutPipeline, "_merge_to_bundle", return_value=stub_bundle
    ):
        bundle = bidi._merge_to_bundle(
            doc_context=DocumentContext(document_type="other"),
            per_pass={},
            pdf_path=Path("/fake/test.pdf"),
            layout=None,
        )

    extensions = bundle["meta"]["extension"]
    recon_exts = [
        e for e in extensions
        if e.get("url", "").endswith("scout-reconciliation")
    ]
    assert len(recon_exts) == 1, (
        f"expected 1 scout-reconciliation extension, got {len(recon_exts)}: {extensions}"
    )

    payload = json.loads(recon_exts[0]["valueString"])
    assert "agreement_count" in payload
    assert "disagreement_count" in payload
    assert "only_in_a" in payload
    assert "only_in_b" in payload
    assert "page_hint_overlap" in payload

    # Values should match the reconciliation object
    assert payload["agreement_count"] == rec.agreement_count
    assert payload["disagreement_count"] == rec.disagreement_count
    assert payload["only_in_a"] == rec.only_in_a
    assert payload["only_in_b"] == rec.only_in_b


# ---------------------------------------------------------------------------
# Test 6 — _merge_to_bundle does NOT add extension when reconciliation absent
# ---------------------------------------------------------------------------


def test_merge_to_bundle_no_extension_when_reconciliation_absent() -> None:
    """When _scout_reconciliation is not set (or None), _merge_to_bundle must
    not add a scout-reconciliation extension — regression check."""
    bidi = _new_bidi()
    # Explicitly absent
    bidi._scout_reconciliation = None

    stub_bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [],
        "meta": {
            "source": "extracted://other/test",
            "extension": [
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-pipeline",
                    "valueString": "multipass-fhir",
                }
            ],
        },
    }

    with patch.object(
        MultiPassFHIRScoutPipeline, "_merge_to_bundle", return_value=stub_bundle
    ):
        bundle = bidi._merge_to_bundle(
            doc_context=DocumentContext(document_type="other"),
            per_pass={},
            pdf_path=Path("/fake/test.pdf"),
            layout=None,
        )

    extensions = bundle["meta"]["extension"]
    recon_exts = [
        e for e in extensions
        if e.get("url", "").endswith("scout-reconciliation")
    ]
    assert len(recon_exts) == 0, (
        f"expected no scout-reconciliation extension, got {recon_exts}"
    )


# ---------------------------------------------------------------------------
# Test 7 — parent scout pipeline still works after _invoke_pass_0 factoring
# ---------------------------------------------------------------------------


def test_scout_pipeline_still_works_after_pass_0_factoring() -> None:
    """MultiPassFHIRScoutPipeline._pass_0_prompt() still returns
    _DOCUMENT_MAP_PROMPT after the _invoke_pass_0 refactor on the parent."""
    scout = MultiPassFHIRScoutPipeline.__new__(MultiPassFHIRScoutPipeline)
    assert scout._pass_0_prompt() is _DOCUMENT_MAP_PROMPT
    assert scout._pass_0_schema() is DocumentMap
