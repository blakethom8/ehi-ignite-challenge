"""Terminology resolution for the multipass-fhir post-pass layer.

After extraction emits Observations / Conditions / etc. with display names
but no codes, this module's matchers attach standard codes (LOINC, SNOMED,
RxNorm, CVX) deterministically — no LLM calls, no hallucination risk.

Public API:
    from lib.extract.terminology.loinc_matcher import match_loinc

The reference data lives at ``ehi-atlas/corpus/reference/<terminology>/`` and
is curated via the ``_curate.py`` scripts there.
"""

from lib.extract.terminology.loinc_matcher import (
    LoincMatch,
    lookup_clinical_category,
    match_loinc,
)

__all__ = ["LoincMatch", "lookup_clinical_category", "match_loinc"]
