"""Tests for lib.extract.lab.reviewer_agent (GOLD-T03).

Covers:
1. test_review_bundle_returns_list_of_concerns
2. test_review_bundle_severity_categorization_preserved
3. test_review_bundle_empty_bundle
4. test_review_bundle_truncates_huge_bundles
5. test_review_bundle_handles_dataclass_to_json
6. test_gold_pipeline_attaches_reviewer_concerns_to_meta
7. test_gold_pipeline_handles_reviewer_failure_gracefully
8. test_gold_pipeline_no_extension_when_concerns_empty
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub backend — never invokes a real LLM
# ---------------------------------------------------------------------------


class _StubBackend:
    """A deterministic stub for AnthropicBackend.

    Records the last call's arguments as ``last_system_prompt`` and
    ``last_user_prompt`` so tests can inspect what the reviewer agent sent.
    """

    def __init__(self, concerns_payload: list[dict]) -> None:
        from lib.extract.lab.reviewer_agent import _ConcernsExtraction, _ConcernEntry

        self._concerns_payload = concerns_payload
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    def call_with_schema(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema,
        **kwargs: Any,
    ):
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt

        from lib.extract.lab.reviewer_agent import _ConcernsExtraction

        return _ConcernsExtraction.model_validate(
            {"concerns": self._concerns_payload}
        )


# ---------------------------------------------------------------------------
# Minimal bundle fixture
# ---------------------------------------------------------------------------


def _minimal_bundle() -> dict:
    return {"resourceType": "Bundle", "type": "document", "entry": []}


def _concern_dict(
    severity: str = "warning",
    category: str = "DateInconsistency",
    description: str = "Encounter date is before patient birthdate.",
    affected_resource_ids: list | None = None,
) -> dict:
    return {
        "severity": severity,
        "category": category,
        "description": description,
        "affected_resource_ids": affected_resource_ids or [],
    }


# ---------------------------------------------------------------------------
# Test 1 — stub returns concerns → review_bundle returns BundleConcern list
# ---------------------------------------------------------------------------


def test_review_bundle_returns_list_of_concerns() -> None:
    """Stub returns 2 concern dicts → review_bundle returns 2 BundleConcern instances."""
    from lib.extract.lab.reviewer_agent import BundleConcern, review_bundle

    stub = _StubBackend(
        [
            _concern_dict(severity="error", category="DateError", description="Med before DOB."),
            _concern_dict(severity="info", category="MissingRef", description="Note references missing encounter."),
        ]
    )
    result = review_bundle(_minimal_bundle(), backend=stub)

    assert len(result) == 2, f"Expected 2 concerns, got {len(result)}"
    assert all(isinstance(c, BundleConcern) for c in result), (
        f"Expected all BundleConcern, got {[type(c).__name__ for c in result]}"
    )
    assert result[0].severity == "error"
    assert result[0].category == "DateError"
    assert result[1].severity == "info"
    assert result[1].category == "MissingRef"


# ---------------------------------------------------------------------------
# Test 2 — severity categorization preserved end-to-end
# ---------------------------------------------------------------------------


def test_review_bundle_severity_categorization_preserved() -> None:
    """Concerns with severity error / warning / info are all preserved correctly."""
    from lib.extract.lab.reviewer_agent import review_bundle

    severities = ["error", "warning", "info"]
    stub = _StubBackend(
        [_concern_dict(severity=s, category=f"Cat{s}", description=f"Desc {s}.") for s in severities]
    )
    result = review_bundle(_minimal_bundle(), backend=stub)

    assert len(result) == 3
    returned_severities = [c.severity for c in result]
    assert returned_severities == severities, (
        f"Expected {severities}, got {returned_severities}"
    )


# ---------------------------------------------------------------------------
# Test 3 — empty bundle input works without crashing
# ---------------------------------------------------------------------------


def test_review_bundle_empty_bundle() -> None:
    """Input {'resourceType': 'Bundle', 'entry': []} works without crashing.
    Reviewer agent can return empty concerns when the bundle is clean.
    """
    from lib.extract.lab.reviewer_agent import review_bundle

    stub = _StubBackend([])  # Clean bundle → no concerns
    result = review_bundle({"resourceType": "Bundle", "entry": []}, backend=stub)

    assert result == [], f"Expected empty list for clean bundle, got {result}"


# ---------------------------------------------------------------------------
# Test 4 — huge bundles get truncated before being sent to the reviewer
# ---------------------------------------------------------------------------


def test_review_bundle_truncates_huge_bundles() -> None:
    """When the bundle JSON serializes to > 100k chars, the user_prompt sent
    to the backend is truncated and includes the truncation notice.
    """
    from lib.extract.lab.reviewer_agent import review_bundle

    # Build a bundle that will serialize to well over 100k chars
    huge_bundle = {
        "resourceType": "Bundle",
        "entry": [{"resource": {"data": "x" * 200_000}}],
    }

    stub = _StubBackend([])
    review_bundle(huge_bundle, backend=stub)

    user_prompt = stub.last_user_prompt
    assert user_prompt is not None, "Backend was not called"
    assert "bundle truncated for reviewer" in user_prompt, (
        f"Expected truncation notice in user_prompt; got (first 300 chars): "
        f"{user_prompt[:300]!r}"
    )
    # The truncated portion must not exceed 100k chars of bundle JSON
    # (plus the surrounding template text which is small)
    assert len(user_prompt) < 110_000, (
        f"user_prompt after truncation is too long: {len(user_prompt)} chars"
    )


# ---------------------------------------------------------------------------
# Test 5 — BundleConcern dataclass serializes cleanly via asdict
# ---------------------------------------------------------------------------


def test_review_bundle_handles_dataclass_to_json() -> None:
    """review_bundle returns frozen dataclass instances; asdict + json.dumps
    round-trip must produce valid JSON with the expected fields.
    """
    from lib.extract.lab.reviewer_agent import review_bundle

    stub = _StubBackend(
        [
            _concern_dict(
                severity="warning",
                category="DuplicateNPI",
                description="Two practitioners share NPI 1234567890.",
                affected_resource_ids=["Practitioner/abc", "Practitioner/def"],
            )
        ]
    )
    concerns = review_bundle(_minimal_bundle(), backend=stub)

    assert len(concerns) == 1
    raw = asdict(concerns[0])
    serialized = json.dumps(raw)  # must not raise
    restored = json.loads(serialized)

    assert restored["severity"] == "warning"
    assert restored["category"] == "DuplicateNPI"
    assert "Practitioner/abc" in restored["affected_resource_ids"]


# ---------------------------------------------------------------------------
# Test 6 — gold pipeline attaches reviewer concerns to bundle.meta.extension
# ---------------------------------------------------------------------------


def test_gold_pipeline_attaches_reviewer_concerns_to_meta() -> None:
    """End-to-end: gold pipeline's _merge_to_bundle produces a bundle with
    meta.extension containing reviewer-concerns when the reviewer agent
    returns non-empty concerns.

    Both specialist passes AND the reviewer agent are mocked — no real LLM
    calls happen.
    """
    from lib.extract.pipelines.multipass_fhir import (
        DocumentContext,
        MultiPassFHIRGoldPipeline,
    )
    from lib.extract.lab.reviewer_agent import BundleConcern

    pipeline = MultiPassFHIRGoldPipeline.__new__(MultiPassFHIRGoldPipeline)

    # Build a minimal "super()._merge_to_bundle" return value
    base_bundle: dict = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [],
        "meta": {
            "source": "extracted://other/test",
            "extension": [],
        },
    }

    fake_concern = BundleConcern(
        severity="error",
        category="DateError",
        description="MedicationRequest authored before Patient.birthDate.",
        affected_resource_ids=["MedicationRequest/r1"],
    )

    from unittest.mock import patch
    from pathlib import Path

    with (
        patch.object(
            MultiPassFHIRGoldPipeline.__bases__[0],
            "_merge_to_bundle",
            return_value=base_bundle,
        ),
        patch(
            "lib.extract.lab.reviewer_agent.review_bundle",
            return_value=[fake_concern],
        ),
    ):
        result = pipeline._merge_to_bundle(
            doc_context=DocumentContext(document_type="other"),
            per_pass={},
            pdf_path=Path("fake.pdf"),
            layout=None,
        )

    extensions = result.get("meta", {}).get("extension", [])
    reviewer_exts = [
        e for e in extensions
        if e.get("url", "").endswith("reviewer-concerns")
    ]
    assert len(reviewer_exts) == 1, (
        f"Expected 1 reviewer-concerns extension, found {len(reviewer_exts)}. "
        f"All extensions: {extensions}"
    )

    parsed = json.loads(reviewer_exts[0]["valueString"])
    assert len(parsed) == 1
    assert parsed[0]["severity"] == "error"
    assert parsed[0]["category"] == "DateError"


# ---------------------------------------------------------------------------
# Test 7 — reviewer failure doesn't kill the pipeline run
# ---------------------------------------------------------------------------


def test_gold_pipeline_handles_reviewer_failure_gracefully() -> None:
    """When review_bundle raises, the bundle still returns successfully.
    The reviewer-concerns extension is absent, but no exception propagates.
    """
    from lib.extract.pipelines.multipass_fhir import (
        DocumentContext,
        MultiPassFHIRGoldPipeline,
    )
    from pathlib import Path

    pipeline = MultiPassFHIRGoldPipeline.__new__(MultiPassFHIRGoldPipeline)

    base_bundle: dict = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [],
        "meta": {"extension": []},
    }

    with (
        patch.object(
            MultiPassFHIRGoldPipeline.__bases__[0],
            "_merge_to_bundle",
            return_value=base_bundle,
        ),
        patch(
            "lib.extract.lab.reviewer_agent.review_bundle",
            side_effect=RuntimeError("Simulated reviewer crash"),
        ),
    ):
        result = pipeline._merge_to_bundle(
            doc_context=DocumentContext(document_type="other"),
            per_pass={},
            pdf_path=Path("fake.pdf"),
            layout=None,
        )

    # Must return a bundle without raising
    assert result["resourceType"] == "Bundle"

    extensions = result.get("meta", {}).get("extension", [])
    reviewer_exts = [
        e for e in extensions
        if e.get("url", "").endswith("reviewer-concerns")
    ]
    assert len(reviewer_exts) == 0, (
        f"Expected no reviewer-concerns extension after failure, found {reviewer_exts}"
    )


# ---------------------------------------------------------------------------
# Test 8 — no extension when concerns list is empty
# ---------------------------------------------------------------------------


def test_gold_pipeline_no_extension_when_concerns_empty() -> None:
    """When review_bundle returns [], the bundle has NO reviewer-concerns
    extension (don't litter meta with empty entries).
    """
    from lib.extract.pipelines.multipass_fhir import (
        DocumentContext,
        MultiPassFHIRGoldPipeline,
    )
    from pathlib import Path

    pipeline = MultiPassFHIRGoldPipeline.__new__(MultiPassFHIRGoldPipeline)

    base_bundle: dict = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [],
        "meta": {"extension": []},
    }

    with (
        patch.object(
            MultiPassFHIRGoldPipeline.__bases__[0],
            "_merge_to_bundle",
            return_value=base_bundle,
        ),
        patch(
            "lib.extract.lab.reviewer_agent.review_bundle",
            return_value=[],
        ),
    ):
        result = pipeline._merge_to_bundle(
            doc_context=DocumentContext(document_type="other"),
            per_pass={},
            pdf_path=Path("fake.pdf"),
            layout=None,
        )

    extensions = result.get("meta", {}).get("extension", [])
    reviewer_exts = [
        e for e in extensions
        if e.get("url", "").endswith("reviewer-concerns")
    ]
    assert len(reviewer_exts) == 0, (
        f"Expected no reviewer-concerns extension for empty concerns, found {reviewer_exts}"
    )
