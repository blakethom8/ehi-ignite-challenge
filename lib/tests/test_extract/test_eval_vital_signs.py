"""Tests for vital-sign FactType support in eval.py (T02).

Covers:
  1. "vital-sign" is a valid FactType Literal value.
  2. Observation with category=vital-signs → fact_type "vital-sign".
  3. Observation with category=laboratory → fact_type "lab" (no regression).
  4. Observation with no category → fact_type "lab" (backwards compat).
"""

from __future__ import annotations

from typing import get_args

from lib.extract.eval import FactType, facts_from_fhir_resources


# ---------------------------------------------------------------------------
# Helper: minimal synthetic Observation resource
# ---------------------------------------------------------------------------


def _obs(category_code: str | None = None, obs_id: str = "obs-1") -> dict:
    """Build a minimal synthetic FHIR Observation resource.

    If category_code is None, the resource has no category field at all,
    simulating an older bundle that predates category tagging.
    """
    resource: dict = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "8480-6",
                    "display": "Systolic blood pressure",
                }
            ],
            "text": "Systolic blood pressure",
        },
    }
    if category_code is not None:
        resource["category"] = [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": category_code,
                    }
                ]
            }
        ]
    return resource


def _bundle_facts(obs: dict) -> list:
    """Run facts_from_fhir_resources with a single Observation and return the facts list."""
    return facts_from_fhir_resources({"Observation": [obs]})


# ---------------------------------------------------------------------------
# 1. "vital-sign" is in the FactType Literal
# ---------------------------------------------------------------------------


def test_vital_sign_facttype_in_literal() -> None:
    """'vital-sign' must be a valid member of the FactType Literal."""
    assert "vital-sign" in get_args(FactType)


# ---------------------------------------------------------------------------
# 2. Observation with category=vital-signs → fact_type "vital-sign"
# ---------------------------------------------------------------------------


def test_facts_from_fhir_observation_vital_signs_category() -> None:
    """Observation carrying category='vital-signs' must produce fact_type='vital-sign'."""
    obs = _obs(category_code="vital-signs")
    facts = _bundle_facts(obs)
    assert len(facts) == 1, f"Expected exactly 1 fact, got {len(facts)}"
    assert facts[0].fact_type == "vital-sign", (
        f"Expected fact_type='vital-sign', got {facts[0].fact_type!r}"
    )


# ---------------------------------------------------------------------------
# 3. Observation with category=laboratory → fact_type "lab" (no regression)
# ---------------------------------------------------------------------------


def test_facts_from_fhir_observation_lab_category_still_lab() -> None:
    """Observation carrying category='laboratory' must still produce fact_type='lab'."""
    obs = _obs(category_code="laboratory")
    facts = _bundle_facts(obs)
    assert len(facts) == 1, f"Expected exactly 1 fact, got {len(facts)}"
    assert facts[0].fact_type == "lab", (
        f"Expected fact_type='lab', got {facts[0].fact_type!r}"
    )


# ---------------------------------------------------------------------------
# 4. Observation with no category → fact_type "lab" (backwards compat)
# ---------------------------------------------------------------------------


def test_facts_from_fhir_observation_no_category_defaults_to_lab() -> None:
    """Observation without a category field must default to fact_type='lab'."""
    obs = _obs(category_code=None)
    facts = _bundle_facts(obs)
    assert len(facts) == 1, f"Expected exactly 1 fact, got {len(facts)}"
    assert facts[0].fact_type == "lab", (
        f"Expected fact_type='lab', got {facts[0].fact_type!r}"
    )
