"""
ehi_atlas.extract.schemas
~~~~~~~~~~~~~~~~~~~~~~~~~

Pydantic v2 schemas for vision-extraction outputs.

These are the **contract between Layer 2-B (extract) and Layer 3 (harmonize)**.
The vision LLM (Claude) returns a JSON payload that must validate against
``ExtractionResult``; the harmonizer then calls ``to_fhir`` to convert each
extracted record into a FHIR resource dict.

Two-stage philosophy
--------------------
1. LLM emits a constrained intermediate format validated here.
2. ``to_fhir.py`` converts that intermediate format to FHIR deterministically.

This separation lets prompt authors iterate on extraction quality without
touching FHIR serialization, and gives us deterministic FHIR output.

Field descriptions are intentionally terse — they become part of the JSON Schema
that ``instructor`` / structured-output modes embed in the system prompt at
runtime.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


class BBox(BaseModel):
    """Bounding box in PDF user units (points), bottom-left origin."""

    page: int = Field(..., ge=1, description="1-indexed page number")
    x1: float
    y1: float
    x2: float
    y2: float

    def to_locator_string(self) -> str:
        """The string format placed in meta.extension(.../source-locator).

        Example: ``"page=2;bbox=72,574,540,590"``
        """
        return (
            f"page={self.page};"
            f"bbox={self.x1:.0f},{self.y1:.0f},{self.x2:.0f},{self.y2:.0f}"
        )


# ---------------------------------------------------------------------------
# Lab report
# ---------------------------------------------------------------------------


class ExtractedLabResult(BaseModel):
    """A single lab result extracted from a lab report PDF.

    Maps to FHIR Observation with us-core-observation-lab profile.
    """

    test_name: str = Field(
        ...,
        description=(
            "The lab test name as it appears on the page (e.g. 'Creatinine')"
        ),
    )
    loinc_code: str | None = Field(
        None,
        description=(
            "LOINC code if confidently identified; null if not in the showcase subset"
        ),
    )
    value_quantity: float | None = Field(
        None, description="The numeric result value"
    )
    value_string: str | None = Field(
        None,
        description="Free-text result if not numeric (e.g. 'Negative')",
    )
    unit: str | None = Field(
        None, description="UCUM-conformant unit (e.g. 'mg/dL', 'mmol/L')"
    )
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    flag: Literal["H", "L", "N", "HH", "LL", "A", None] = Field(
        None, description="Interpretation flag"
    )
    effective_date: str | None = Field(
        None,
        description="ISO 8601 date when the test was performed/observed",
    )
    bbox: BBox = Field(
        ...,
        description="Where on the source PDF this result was lifted from",
    )


class ExtractedLabReport(BaseModel):
    """A whole lab report PDF's extracted contents.

    The vision LLM returns this top-level model; the harmonizer converts each
    ``ExtractedLabResult`` to a FHIR Observation.
    """

    document_type: Literal["lab-report"] = "lab-report"
    document_date: str | None = Field(
        None, description="ISO 8601 date the report was issued"
    )
    ordering_provider: str | None = None
    lab_name: str | None = Field(
        None, description="The lab company (e.g. 'Quest Diagnostics')"
    )
    patient_name_seen: str | None = Field(
        None,
        description=(
            "The patient name as it appears on the report (for identity-resolution "
            "sanity check, NOT for extraction into the record)"
        ),
    )
    results: list[ExtractedLabResult]


# ---------------------------------------------------------------------------
# Clinical note
# ---------------------------------------------------------------------------


class ExtractedCondition(BaseModel):
    """A condition extracted from clinical-note text.

    Maps to FHIR Condition.
    """

    label: str = Field(
        ...,
        description=(
            "The condition as the LLM understood it "
            "(e.g. 'Chest tightness on exertion')"
        ),
    )
    snomed_ct_code: str | None = None
    icd_10_cm_code: str | None = None
    onset_date: str | None = Field(
        None,
        description="ISO 8601 date when the condition began, if mentioned",
    )
    source_text: str = Field(
        ...,
        description=(
            "The exact phrase from the note that justified this extraction"
        ),
    )
    bbox: BBox | None = Field(
        None,
        description=(
            "If the source layout has bbox info; null for text-only attachments"
        ),
    )


class ExtractedSymptom(BaseModel):
    """A symptom mentioned in clinical-note text.

    Maps to FHIR Observation with social-history or symptom-related profiles,
    depending on context.
    """

    label: str
    snomed_ct_code: str | None = None
    onset_date: str | None = None
    source_text: str
    bbox: BBox | None = None


class ExtractedClinicalNote(BaseModel):
    """A clinical-note progress note's extracted *facts* (not full text).

    For Artifact 4: the planted free-text fact is lifted into a Condition or
    Symptom. The full note text is preserved separately as a Binary; this
    schema describes the *structured facts* the LLM extracted.
    """

    document_type: Literal["clinical-note"] = "clinical-note"
    note_date: str | None = None
    author: str | None = None
    extracted_conditions: list[ExtractedCondition] = []
    extracted_symptoms: list[ExtractedSymptom] = []


# ---------------------------------------------------------------------------
# Top-level wrapper
# ---------------------------------------------------------------------------


class ExtractionResult(BaseModel):
    """The top-level wrapper the LLM returns.

    Carries the extraction itself plus the model's confidence and the prompt
    version used. These map directly to the ``meta.extension`` URLs we mint
    (extraction-model, extraction-confidence, extraction-prompt-version).
    """

    document: Annotated[
        ExtractedLabReport | ExtractedClinicalNote,
        Field(discriminator="document_type"),
    ]
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)
    extraction_model: str = Field(
        ..., description="e.g. 'claude-opus-4-7'"
    )
    extraction_prompt_version: str = Field(
        ..., description="e.g. 'v0.1.0'"
    )
