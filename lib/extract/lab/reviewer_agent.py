"""Reviewer agent — whole-bundle inconsistency check.

After the gold pipeline assembles its FHIR Bundle, this module asks
Claude Opus 4.7 (with extended thinking) to scrutinize it for issues
no individual extraction pass could catch:
  - Cross-resource date inconsistencies (med start before DOB, etc.)
  - Missing cross-references (encounter mentioned in note but not as
    Encounter resource)
  - Data quality issues (duplicate NPIs, orphaned refs)
  - Narrative findings probably present in the source but not extracted

Output: a list of BundleConcern objects, attached to bundle.meta.extension
under the URL .../reviewer-concerns as JSON. The reviewer-CLI (Step 2 /
REVIEW-* tasks) will surface these for human triage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["info", "warning", "error"]


class _ConcernEntry(BaseModel):
    """Pydantic for the LLM structured output."""

    severity: Severity = Field(..., description="info / warning / error")
    category: str = Field(..., description="Short category label")
    description: str = Field(..., description="One sentence")
    affected_resource_ids: list[str] = Field(default_factory=list)


class _ConcernsExtraction(BaseModel):
    concerns: list[_ConcernEntry] = Field(default_factory=list)


@dataclass(frozen=True)
class BundleConcern:
    """Frozen dataclass form returned by review_bundle()."""

    severity: Severity
    category: str
    description: str
    affected_resource_ids: list[str]


_REVIEWER_PROMPT = """You are a clinical-document quality reviewer. Below is a
FHIR Bundle extracted from a medical PDF by an automated pipeline. Your
job: scrutinize it for issues no individual extraction pass could catch.

What to look for:
  - Cross-resource DATE INCONSISTENCIES (e.g., a MedicationRequest with
    authoredOn before the Patient.birthDate; an Encounter.period.start
    after Encounter.period.end).
  - MISSING CROSS-REFERENCES (e.g., a clinical note mentions an encounter
    that isn't represented as an Encounter resource; an Observation
    references Patient/<id> that doesn't exist in the bundle).
  - DATA QUALITY ISSUES (duplicate NPIs on different Practitioner
    resources; orphaned subject references).
  - NARRATIVE FINDINGS PROBABLY PRESENT IN THE SOURCE but not extracted
    as structured resources (e.g., a Composition section mentions a
    diagnosis that wouldn't appear in the Conditions list).

Rules:
  - Do NOT add new facts to the bundle. Only flag concerns about what's
    there OR what's obviously missing.
  - Severity:
      error   = clinically wrong (e.g., medication started before DOB)
      warning = suspicious but plausible (e.g., 2 practitioners with
                identical NPI)
      info    = potentially incomplete (e.g., narrative mentions a lab
                that isn't in the Observations list)
  - Cite affected resource IDs in the bundle.
  - Be concise — one sentence per concern.
  - If the bundle looks clean, return an empty concerns list.
"""


def review_bundle(
    bundle: dict,
    *,
    backend: Any = None,
    thinking_budget_tokens: int = 8000,
    model: str = "claude-opus-4-7",
) -> list[BundleConcern]:
    """Scrutinize a FHIR Bundle for inconsistencies via Claude Opus.

    Args:
        bundle: The FHIR Bundle dict (the output of _merge_to_bundle).
        backend: Optional pre-configured backend; mostly for testing.
            When None, a default AnthropicBackend with thinking is used.
        thinking_budget_tokens: Extended-thinking budget for the review
            call. Default 8000 (smaller than per-pass since reviewer is
            quick scan, not deep extraction).
        model: Model identifier. Default Opus 4.7.

    Returns:
        List of BundleConcern. Empty list when bundle is clean.
    """
    if backend is None:
        from lib.extract.pdf import AnthropicBackend

        backend = AnthropicBackend(
            model=model, thinking_budget_tokens=thinking_budget_tokens
        )

    bundle_text = json.dumps(bundle, indent=2, default=str)
    # Truncate massive bundles to avoid massive prompt cost
    if len(bundle_text) > 100_000:
        bundle_text = bundle_text[:100_000] + "\n\n... (bundle truncated for reviewer)"

    user_prompt = f"FHIR Bundle to review:\n\n```json\n{bundle_text}\n```"

    response = backend.call_with_schema(
        system_prompt=_REVIEWER_PROMPT,
        user_prompt=user_prompt,
        schema=_ConcernsExtraction,
    )

    return [
        BundleConcern(
            severity=c.severity,
            category=c.category,
            description=c.description,
            affected_resource_ids=list(c.affected_resource_ids),
        )
        for c in response.concerns
    ]
