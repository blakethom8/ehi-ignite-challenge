"""SinglePassVisionPipeline — baseline that wraps the original extract_lab_pdf.

This is the *current* code path packaged as a Pipeline so the bake-off
harness has something to compare other architectures against. It makes
ONE vision-LLM call per PDF, returning either an ``ExtractedLabReport``
or an ``ExtractedClinicalNote``, then converts to FHIR via the existing
``to_fhir`` deterministic converters.

Why this is the baseline (not the recommendation)
-------------------------------------------------
This pipeline embodies the design we explicitly moved away from in
Decision 1 of ``docs/architecture/PDF-PROCESSOR.md``: a bespoke
intermediate format (``ExtractionResult``) rather than direct FHIR.
We keep it as the baseline because:

  - It establishes a known-good lower bound on F1
  - It validates the Pipeline Protocol works end-to-end
  - It gives the bake-off harness a concrete first row
  - The eval harness already comparing against it for the rhett759
    fixture surfaced the schema-gap finding in the first place

When other pipelines (multi-pass FHIR, OCR-then-text) ship and beat
this baseline on F1, this pipeline becomes a regression-detection tool
rather than a production candidate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ehi_atlas.extract.pdf import extract_lab_pdf
from ehi_atlas.extract.pipelines.base import (
    ExtractionPipeline,
    PipelineMetadata,
    register,
)
from ehi_atlas.extract.schemas import (
    ExtractedClinicalNote,
    ExtractedLabReport,
    ExtractionResult,
)
from ehi_atlas.extract.to_fhir import (
    condition_to_fhir,
    lab_result_to_observation,
)


@register
class SinglePassVisionPipeline:
    """One vision-LLM call → ExtractionResult → FHIR Bundle.

    Configuration
    -------------
    The backend (``anthropic`` vs ``gemma-google-ai-studio``) is selected
    via the ``EHI_VISION_BACKEND`` environment variable, same as direct
    ``extract_lab_pdf`` callers. We do not surface backend selection on
    the constructor today — the bake-off harness varies backend by
    swapping env between runs and re-instantiating.

    Caching
    -------
    Reuses the existing ``ExtractionCache`` keyed on
    ``(pdf_sha256, prompt_version, schema_version, backend/model)``.
    Pass ``skip_cache=True`` to force a live run.
    """

    metadata = PipelineMetadata(
        name="single-pass-vision",
        description=(
            "Baseline. One vision-LLM call returns an ExtractionResult "
            "(lab-report XOR clinical-note); deterministic to_fhir converters "
            "produce a FHIR Bundle. Documents the schema-gap floor."
        ),
        architecture="single-pass-vision",
        primary_backends=["anthropic"],  # default; works with any VisionBackend
        estimated_cost_per_pdf_usd=0.05,  # rough — Claude Opus, 1 call per PDF
    )

    def __init__(self, *, patient_id: str = "unknown") -> None:
        # patient_id is used in FHIR resource references. The harmonizer
        # later overwrites this with the real Patient/<id> after identity
        # resolution; for the bake-off it just needs to be stable.
        self._patient_id = patient_id

    def extract(
        self,
        pdf_path: Path,
        *,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        """Run the pipeline. Returns a FHIR Bundle dict."""
        result = extract_lab_pdf(pdf_path, skip_cache=skip_cache)
        return _extraction_result_to_bundle(
            result,
            patient_id=self._patient_id,
            source_attachment_id=pdf_path.stem,
        )


# ---------------------------------------------------------------------------
# ExtractionResult → FHIR Bundle bridge
# ---------------------------------------------------------------------------


def _extraction_result_to_bundle(
    result: ExtractionResult,
    *,
    patient_id: str,
    source_attachment_id: str,
) -> dict[str, Any]:
    """Convert an ``ExtractionResult`` (intermediate format) to a FHIR Bundle.

    The intermediate format only knows about a few resource types
    (lab results, conditions, symptoms). This converter emits whatever
    those translate to in FHIR — Observations for lab results,
    Conditions for conditions, no Symptoms (FHIR has no direct mapping;
    they'd be Observations with category=symptom in a fuller schema).

    The Bundle ships with Provenance metadata on every resource via
    the existing ``to_fhir._meta`` helper. Bbox calibration was already
    applied upstream by ``extract_from_pdf``.
    """
    entries: list[dict[str, Any]] = []

    doc = result.document
    if isinstance(doc, ExtractedLabReport):
        for lab in doc.results:
            obs = lab_result_to_observation(
                result=lab,
                patient_id=patient_id,
                source_attachment_id=source_attachment_id,
                model=result.extraction_model,
                prompt_version=result.extraction_prompt_version,
                confidence=result.extraction_confidence,
            )
            entries.append({"resource": obs})
    elif isinstance(doc, ExtractedClinicalNote):
        for cond in doc.extracted_conditions:
            condition = condition_to_fhir(
                extracted=cond,
                patient_id=patient_id,
                source_attachment_id=source_attachment_id,
                model=result.extraction_model,
                confidence=result.extraction_confidence,
                prompt_version=result.extraction_prompt_version,
            )
            entries.append({"resource": condition})
        # Symptoms have no direct FHIR mapping in the current to_fhir
        # converters — we surface them as nothing. Future schema-direct
        # pipelines emit these as Observation(category=symptom).
        # Today this is a known recall gap on clinical-note PDFs.

    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": entries,
        "meta": {
            "source": f"extracted://{result.document.document_type}/{source_attachment_id}",
            "extension": [
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-pipeline",
                    "valueString": SinglePassVisionPipeline.metadata.name,
                },
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-model",
                    "valueString": result.extraction_model,
                },
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-confidence",
                    "valueDecimal": result.extraction_confidence,
                },
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version",
                    "valueString": result.extraction_prompt_version,
                },
            ],
        },
    }

    return bundle
