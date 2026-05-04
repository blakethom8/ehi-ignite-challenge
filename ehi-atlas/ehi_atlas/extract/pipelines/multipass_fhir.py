"""MultiPassFHIRPipeline — schema-direct multi-pass extraction.

The architectural test. Replaces the bespoke ExtractionResult intermediate
format with per-resource-type passes that emit FHIR-shaped output directly.
Per ``docs/architecture/PDF-PROCESSOR.md`` decisions 1–4:

  1. **No intermediate format.** Each pass emits resources that go straight
     into a FHIR Bundle. Adding a new resource type = adding a new pass +
     its mini-schema; no changes to the pipeline core.

  2. **Multi-task → single-task.** The single-pass baseline asks one LLM
     call to handle Conditions, Symptoms (and implicitly nothing else).
     Multi-pass dispatches one focused call per FHIR resource type. Each
     prompt is targeted; each schema is small.

  3. **Pass 0 establishes document context.** Patient, encounter date,
     facility, ordering provider — extracted ONCE per PDF. Every per-
     resource pass receives that context so emitted resources carry
     consistent metadata even when source content spans pages.

  4. **Per-pass model selection.** Each ``ExtractionPass`` declares its
     backend + model. Cheap models for tabular passes (labs,
     immunizations); smarter models for narrative passes (conditions,
     allergies). The bake-off harness measures whether downgrading
     specific passes preserves F1.

What this pipeline ships today
-------------------------------
- Five resource passes: Conditions, Medications, AllergyIntolerance,
  Immunizations, Lab Observations. Procedures and Vitals are deferred
  until the eval harness scores them.
- Parallel dispatch via ThreadPoolExecutor (the AnthropicBackend is sync;
  asyncio bridging adds complexity for no real gain at 5–6 concurrent
  requests).
- Per-pass cache via the existing :class:`ExtractionCache`, keyed on
  (pdf_sha, pass_name, prompt_version, schema_version, backend/model).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Type

from pydantic import BaseModel, Field

from ehi_atlas.extract.cache import CacheKey, ExtractionCache, hash_file
from ehi_atlas.extract.layout import extract_layout, find_text_bbox
from ehi_atlas.extract.pdf import VisionBackend, get_backend
from ehi_atlas.extract.pipelines.base import (
    ExtractionPipeline,
    PipelineMetadata,
    register,
)


# ---------------------------------------------------------------------------
# Per-pass schemas (Pydantic) — small, focused, no discriminated unions
# ---------------------------------------------------------------------------


class DocumentContext(BaseModel):
    """Pass 0 output. Document-level metadata that propagates to every other pass.

    Extracted ONCE per PDF; cached as part of the pipeline's overall result.
    """

    document_type: Literal[
        "lab-report",
        "clinical-note",
        "discharge-summary",
        "imaging-report",
        "patient-summary",
        "other",
    ] = Field(..., description="Best guess at the document's primary type")
    patient_name: str | None = Field(None, description="Patient name as it appears")
    patient_dob: str | None = Field(None, description="Patient DOB ISO 8601 YYYY-MM-DD")
    encounter_date: str | None = Field(
        None, description="Date the document was issued / effective ISO 8601"
    )
    ordering_provider: str | None = None
    facility_name: str | None = Field(
        None,
        description="Lab name, hospital, clinic, or 'Patient Health Summary' for portal exports",
    )


class ConditionEntry(BaseModel):
    display: str = Field(..., description="Condition as it appears on the page")
    icd_10_cm_code: str | None = None
    snomed_ct_code: str | None = None
    onset_date: str | None = Field(None, description="ISO 8601 if mentioned")
    clinical_status: Literal[
        "active", "resolved", "remission", "recurrence", "relapse", "inactive"
    ] = "active"
    page: int | None = Field(None, description="1-indexed page number where this appeared")
    source_text: str | None = Field(
        None, description="Short verbatim phrase from the document (≤120 chars)"
    )


class ConditionExtraction(BaseModel):
    conditions: list[ConditionEntry] = Field(default_factory=list)


class MedicationEntry(BaseModel):
    display: str = Field(
        ...,
        description="Full medication name including dose form (e.g. 'Fluticasone propionate 50 mcg nasal spray')",
    )
    rxnorm_code: str | None = None
    dose: str | None = Field(None, description="Strength + units (e.g. '500 mg')")
    frequency: str | None = Field(None, description="Schedule (e.g. 'BID', 'once daily')")
    status: Literal[
        "active",
        "completed",
        "stopped",
        "on-hold",
        "cancelled",
        "draft",
        "unknown",
    ] = "active"
    page: int | None = None
    source_text: str | None = None


class MedicationExtraction(BaseModel):
    medications: list[MedicationEntry] = Field(default_factory=list)


class AllergyEntry(BaseModel):
    display: str = Field(..., description="Allergen as it appears (e.g. 'Penicillin', 'Peanuts')")
    snomed_ct_code: str | None = None
    reaction: str | None = Field(None, description="Reaction description if present")
    severity: Literal["mild", "moderate", "severe"] | None = None
    page: int | None = None
    source_text: str | None = None


class AllergyExtraction(BaseModel):
    allergies: list[AllergyEntry] = Field(default_factory=list)


class ImmunizationEntry(BaseModel):
    vaccine_display: str = Field(
        ..., description="Vaccine name (e.g. 'Influenza, QUAD, Preservative Free')"
    )
    cvx_code: str | None = None
    administration_date: str | None = Field(None, description="ISO 8601 if visible")
    page: int | None = None
    source_text: str | None = None


class ImmunizationExtraction(BaseModel):
    immunizations: list[ImmunizationEntry] = Field(default_factory=list)


class LabObservationEntry(BaseModel):
    test_name: str = Field(..., description="Test name as printed (e.g. 'Creatinine')")
    loinc_code: str | None = Field(
        None, description="LOINC code if confidently identified, else null"
    )
    value_quantity: float | None = None
    value_string: str | None = Field(
        None, description="Free-text value if non-numeric (e.g. 'Negative')"
    )
    unit: str | None = Field(None, description="UCUM unit if available")
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    flag: Literal["H", "L", "N", "HH", "LL", "A"] | None = None
    effective_date: str | None = None
    page: int | None = None


class LabObservationExtraction(BaseModel):
    observations: list[LabObservationEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pass definitions — declarative table of what runs and how
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionPass:
    """Declarative description of one extraction pass.

    Each pass has its own prompt, schema, and (eventually) backend. Adding
    a new fact type is a new ExtractionPass + a converter function in
    :func:`_resource_converters`.
    """

    name: str
    schema: Type[BaseModel]
    system_prompt: str
    backend_name: str = "anthropic"
    model: str | None = None


_PASS_0_PROMPT = """You are reading a single medical document. Extract the
document's top-level metadata: what kind of document it is, who the patient
is, when it was issued, and which facility/lab/clinic produced it.

Be conservative. If a field isn't clearly visible, return null for that field.
The document_type field is required — pick the closest match from the enum."""


_CONDITIONS_PROMPT = """You are extracting clinical conditions/diagnoses from a
medical document.

Rules:
- Extract every condition/diagnosis explicitly mentioned (problem list, past
  medical history, assessment, ICD-coded diagnoses).
- Include ICD-10-CM and SNOMED-CT codes when they're printed on the document
  alongside the condition. If a code isn't shown, set it to null — never
  fabricate codes.
- Use the condition's display name verbatim from the document.
- Set clinical_status based on context: active by default, resolved if the
  document says so, remission/recurrence/relapse only when explicitly stated.
- Include source_text — a short verbatim excerpt (≤120 chars) showing where
  this condition appeared.
- If no conditions are present, return an empty list. Do not invent."""


_MEDICATIONS_PROMPT = """You are extracting medications from a medical document.

Rules:
- Extract every medication mentioned in current/active med lists, prescription
  records, or inpatient admin lists.
- Use the full medication name including dose form (e.g. "fluticasone propionate
  50 mcg nasal spray", not just "fluticasone").
- Include RxNorm code only if printed on the document. Don't fabricate.
- Include dose (strength) and frequency when stated.
- Status defaults to active; mark completed/stopped/cancelled only when explicit.
- Skip medications that are merely mentioned in narrative ("the patient was
  previously on X") unless the document treats them as part of the structured
  med list.
- If no medications are present, return an empty list."""


_ALLERGIES_PROMPT = """You are extracting allergies and intolerances from a
medical document.

Rules:
- Extract every allergen explicitly listed in an allergy section.
- Include "No Known Allergies" / "NKDA" / similar — that's still an
  AllergyIntolerance entry with display="No Known Allergies".
- Include reaction and severity when stated.
- Include SNOMED-CT code only if printed on the document.
- If the document has no allergy section at all (vs "no known allergies"),
  return an empty list."""


_IMMUNIZATIONS_PROMPT = """You are extracting immunizations/vaccines from a
medical document.

Rules:
- Extract every vaccine administration explicitly recorded.
- Use the vaccine name as printed (e.g. "Influenza, QUAD, Preservative Free").
- Include CVX code only if printed.
- administration_date should be ISO 8601 (YYYY-MM-DD) if a date is shown.
- Don't extract vaccines merely recommended or counseled-on but not given.
- If no immunization section is present, return an empty list."""


_LAB_OBSERVATIONS_PROMPT = """You are extracting individual lab/diagnostic
results from a medical document.

Rules:
- Extract every result row in detailed-results tables. Include the test name,
  numeric value (or string value for non-numeric like "Negative"), unit,
  reference range, and flag (H/L/N/HH/LL/A).
- LOINC codes only if printed on the document.
- effective_date is the date the lab was performed, if stated. Often this
  is at the document level; in that case set it to the document_date supplied
  via context.
- Do NOT extract narrative text or summary statements about labs ("kidney
  function was normal") — only extract structured result rows.
- If no lab tables are present (e.g. this is a pure clinical note), return
  an empty list."""


_PASSES: list[ExtractionPass] = [
    ExtractionPass(
        name="conditions",
        schema=ConditionExtraction,
        system_prompt=_CONDITIONS_PROMPT,
    ),
    ExtractionPass(
        name="medications",
        schema=MedicationExtraction,
        system_prompt=_MEDICATIONS_PROMPT,
    ),
    ExtractionPass(
        name="allergies",
        schema=AllergyExtraction,
        system_prompt=_ALLERGIES_PROMPT,
    ),
    ExtractionPass(
        name="immunizations",
        schema=ImmunizationExtraction,
        system_prompt=_IMMUNIZATIONS_PROMPT,
    ),
    ExtractionPass(
        name="lab_observations",
        schema=LabObservationExtraction,
        system_prompt=_LAB_OBSERVATIONS_PROMPT,
    ),
]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


_PROMPT_VERSION = "multipass-v0.1.0"
_SCHEMA_VERSION = "multipass-v0.1.0"


@register
class MultiPassFHIRPipeline:
    """Schema-direct multi-pass extraction. See module docstring for the *why*."""

    metadata = PipelineMetadata(
        name="multipass-fhir",
        description=(
            "Document-context pass + 5 per-resource-type passes (parallel). "
            "Each pass emits FHIR-shaped output directly. Eliminates the "
            "ExtractedClinicalNote schema-gap that was the dominant failure "
            "mode of single-pass-vision."
        ),
        architecture="multipass-vision",
        primary_backends=["anthropic"],  # default; per-pass override possible
        estimated_cost_per_pdf_usd=0.30,  # 6 calls × ~$0.05 each, rough
    )

    def __init__(
        self,
        *,
        patient_id: str = "unknown",
        backend_name: str = "anthropic",
        model: str | None = None,
        max_workers: int = 6,
    ) -> None:
        self._patient_id = patient_id
        self._backend_name = backend_name
        self._model = model
        self._max_workers = max_workers
        self._cache = ExtractionCache()

    def extract(
        self,
        pdf_path: Path,
        *,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        """Run document-context pass + per-resource passes in parallel; merge to Bundle."""
        pdf_bytes = pdf_path.read_bytes()
        pdf_hash = hash_file(pdf_path)

        # Pass 0 — document context
        doc_context = self._run_pass(
            pass_name="document_context",
            schema=DocumentContext,
            system_prompt=_PASS_0_PROMPT,
            pdf_bytes=pdf_bytes,
            pdf_hash=pdf_hash,
            skip_cache=skip_cache,
            extra_user_text=None,
        )

        # Build context-augmented prompt suffix for the rest of the passes
        context_suffix = (
            f"\n\n--- DOCUMENT CONTEXT (provided to ensure consistency across "
            f"resources) ---\n"
            f"document_type: {doc_context.document_type}\n"
            f"patient_name: {doc_context.patient_name}\n"
            f"patient_dob: {doc_context.patient_dob}\n"
            f"encounter_date: {doc_context.encounter_date}\n"
            f"ordering_provider: {doc_context.ordering_provider}\n"
            f"facility_name: {doc_context.facility_name}\n"
            f"--- end context ---"
        )

        # Per-resource passes — parallel
        per_pass_outputs: dict[str, BaseModel] = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(
                    self._run_pass,
                    pass_name=p.name,
                    schema=p.schema,
                    system_prompt=p.system_prompt + context_suffix,
                    pdf_bytes=pdf_bytes,
                    pdf_hash=pdf_hash,
                    skip_cache=skip_cache,
                    extra_user_text=None,
                ): p
                for p in _PASSES
            }
            for future in as_completed(futures):
                p = futures[future]
                try:
                    per_pass_outputs[p.name] = future.result()
                except Exception as e:
                    # Per-pass failure is captured but doesn't kill the pipeline.
                    # Empty output for that pass; pipeline still emits a
                    # partial Bundle. The bake-off cell will reflect lower
                    # recall but completes successfully.
                    per_pass_outputs[p.name] = p.schema()  # empty instance
                    print(f"[multipass-fhir] pass {p.name!r} failed: {type(e).__name__}: {e}")

        # Merger — convert per-pass outputs to FHIR resources, build Bundle
        layout = self._safe_extract_layout(pdf_path)
        bundle = self._merge_to_bundle(
            doc_context=doc_context,
            per_pass=per_pass_outputs,
            pdf_path=pdf_path,
            layout=layout,
        )
        return bundle

    # ------------------------------------------------------------------
    # Pass machinery
    # ------------------------------------------------------------------

    def _run_pass(
        self,
        *,
        pass_name: str,
        schema: Type[BaseModel],
        system_prompt: str,
        pdf_bytes: bytes,
        pdf_hash: str,
        skip_cache: bool,
        extra_user_text: str | None,
    ) -> BaseModel:
        """Execute one pass with caching + validation."""
        backend = get_backend(name=self._backend_name, model=self._model)
        cache_model_id = f"multipass-fhir/{pass_name}/{backend.name}/{backend.model}"
        key = CacheKey(
            file_sha256=pdf_hash,
            prompt_version=_PROMPT_VERSION,
            schema_version=_SCHEMA_VERSION,
            model_name=cache_model_id,
        )

        if not skip_cache:
            cached = self._cache.get(key)
            if cached is not None:
                try:
                    return schema.model_validate(cached)
                except Exception:
                    # Cached entry doesn't validate against current schema —
                    # treat as miss and re-extract.
                    pass

        raw = backend.extract(
            pdf_bytes=pdf_bytes,
            system_prompt=system_prompt,
            schema_json=schema.model_json_schema(),
        )
        # Apply the same coercions extract_from_pdf uses, in case backends
        # emit string-wrapped sub-objects or extra envelope keys.
        from ehi_atlas.extract.pdf import (
            _coerce_stringified_subobjects,
            _unwrap_extraction_envelope,
        )

        raw = _coerce_stringified_subobjects(raw)
        raw = _unwrap_extraction_envelope(raw)
        validated = schema.model_validate(raw)
        self._cache.put(key, raw)
        return validated

    def _safe_extract_layout(self, pdf_path: Path):
        """Return DocumentLayout or None if the PDF has no extractable text layer."""
        try:
            return extract_layout(pdf_path)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Per-pass FHIR converters
    # ------------------------------------------------------------------

    def _merge_to_bundle(
        self,
        *,
        doc_context: DocumentContext,
        per_pass: dict[str, BaseModel],
        pdf_path: Path,
        layout: Any,  # DocumentLayout | None
    ) -> dict[str, Any]:
        """Convert per-pass outputs into a single FHIR Bundle dict."""
        entries: list[dict[str, Any]] = []
        source_attachment_id = pdf_path.stem
        common_meta_template = self._common_meta_template(doc_context, source_attachment_id)

        # Conditions
        cond_extraction: ConditionExtraction = per_pass.get("conditions") or ConditionExtraction()
        for c in cond_extraction.conditions:
            entries.append({"resource": self._condition_to_fhir(c, common_meta_template, layout)})

        # Medications
        med_extraction: MedicationExtraction = per_pass.get("medications") or MedicationExtraction()
        for m in med_extraction.medications:
            entries.append({"resource": self._medication_to_fhir(m, common_meta_template, layout)})

        # Allergies
        allergy_extraction: AllergyExtraction = per_pass.get("allergies") or AllergyExtraction()
        for a in allergy_extraction.allergies:
            entries.append({"resource": self._allergy_to_fhir(a, common_meta_template, layout)})

        # Immunizations
        imm_extraction: ImmunizationExtraction = per_pass.get("immunizations") or ImmunizationExtraction()
        for i in imm_extraction.immunizations:
            entries.append({"resource": self._immunization_to_fhir(i, common_meta_template, layout)})

        # Lab Observations
        obs_extraction: LabObservationExtraction = per_pass.get("lab_observations") or LabObservationExtraction()
        for o in obs_extraction.observations:
            entries.append({"resource": self._lab_observation_to_fhir(o, common_meta_template, layout, doc_context)})

        bundle: dict[str, Any] = {
            "resourceType": "Bundle",
            "type": "document",
            "entry": entries,
            "meta": {
                "source": f"extracted://{doc_context.document_type}/{source_attachment_id}",
                "extension": [
                    {
                        "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-pipeline",
                        "valueString": MultiPassFHIRPipeline.metadata.name,
                    },
                    {
                        "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version",
                        "valueString": _PROMPT_VERSION,
                    },
                    {
                        "url": "https://ehi-atlas.example/fhir/StructureDefinition/document-context",
                        "valueString": doc_context.model_dump_json(),
                    },
                ],
            },
        }
        return bundle

    def _common_meta_template(
        self,
        doc_context: DocumentContext,
        source_attachment_id: str,
    ) -> dict[str, Any]:
        """Build a meta-extension template every emitted resource carries."""
        backend_id = f"{self._backend_name}/{self._model or 'default'}"
        return {
            "source": f"extracted://{doc_context.document_type}/{source_attachment_id}",
            "extension": [
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-model",
                    "valueString": backend_id,
                },
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version",
                    "valueString": _PROMPT_VERSION,
                },
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-attachment",
                    "valueString": source_attachment_id,
                },
            ],
        }

    def _bbox_locator_for(
        self,
        anchor_text: str | None,
        page: int | None,
        layout,
    ) -> str | None:
        """Look up a bbox via pdfplumber for a given anchor text + page."""
        if not anchor_text or not layout:
            return None
        try:
            result = find_text_bbox(layout, anchor_text, page=page)
        except Exception:
            return None
        if result is None:
            return None
        bbox = result.to_schemas_bbox()
        return bbox.to_locator_string()

    def _add_bbox_to_meta(
        self,
        meta: dict[str, Any],
        bbox_locator: str | None,
    ) -> dict[str, Any]:
        if not bbox_locator:
            return meta
        meta = {**meta, "extension": [*meta.get("extension", [])]}
        meta["extension"].append(
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-locator",
                "valueString": bbox_locator,
            }
        )
        return meta

    def _condition_to_fhir(
        self,
        c: ConditionEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(c.source_text or c.display, c.page, layout)
        codings: list[dict[str, Any]] = []
        if c.icd_10_cm_code:
            codings.append({"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": c.icd_10_cm_code})
        if c.snomed_ct_code:
            codings.append({"system": "http://snomed.info/sct", "code": c.snomed_ct_code})
        resource: dict[str, Any] = {
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": c.clinical_status,
                    }
                ]
            },
            "code": {"text": c.display, **({"coding": codings} if codings else {})},
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if c.onset_date:
            resource["onsetDateTime"] = c.onset_date
        if c.source_text:
            resource["note"] = [{"text": c.source_text}]
        return resource

    def _medication_to_fhir(
        self,
        m: MedicationEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(m.display, m.page, layout)
        codings: list[dict[str, Any]] = []
        if m.rxnorm_code:
            codings.append(
                {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": m.rxnorm_code}
            )
        resource: dict[str, Any] = {
            "resourceType": "MedicationRequest",
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "status": m.status,
            "intent": "order",
            "medicationCodeableConcept": {
                "text": m.display,
                **({"coding": codings} if codings else {}),
            },
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if m.dose or m.frequency:
            instruction: dict[str, Any] = {}
            if m.dose:
                instruction["text"] = (
                    f"{m.dose}" + (f" {m.frequency}" if m.frequency else "")
                )
            elif m.frequency:
                instruction["text"] = m.frequency
            resource["dosageInstruction"] = [instruction]
        return resource

    def _allergy_to_fhir(
        self,
        a: AllergyEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(a.display, a.page, layout)
        codings: list[dict[str, Any]] = []
        if a.snomed_ct_code:
            codings.append({"system": "http://snomed.info/sct", "code": a.snomed_ct_code})
        resource: dict[str, Any] = {
            "resourceType": "AllergyIntolerance",
            "patient": {"reference": f"Patient/{self._patient_id}"},
            "code": {"text": a.display, **({"coding": codings} if codings else {})},
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if a.severity:
            resource["criticality"] = (
                "high" if a.severity == "severe" else "low" if a.severity == "mild" else "unable-to-assess"
            )
        if a.reaction:
            resource["reaction"] = [{"description": a.reaction}]
        return resource

    def _immunization_to_fhir(
        self,
        imm: ImmunizationEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(imm.vaccine_display, imm.page, layout)
        codings: list[dict[str, Any]] = []
        if imm.cvx_code:
            codings.append({"system": "http://hl7.org/fhir/sid/cvx", "code": imm.cvx_code})
        resource: dict[str, Any] = {
            "resourceType": "Immunization",
            "patient": {"reference": f"Patient/{self._patient_id}"},
            "status": "completed",
            "vaccineCode": {
                "text": imm.vaccine_display,
                **({"coding": codings} if codings else {}),
            },
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if imm.administration_date:
            resource["occurrenceDateTime"] = imm.administration_date
        return resource

    def _lab_observation_to_fhir(
        self,
        o: LabObservationEntry,
        common_meta: dict[str, Any],
        layout,
        doc_context: DocumentContext,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(o.test_name, o.page, layout)
        codings: list[dict[str, Any]] = []
        if o.loinc_code:
            codings.append({"system": "http://loinc.org", "code": o.loinc_code})
        resource: dict[str, Any] = {
            "resourceType": "Observation",
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory",
                        }
                    ]
                }
            ],
            "code": {"text": o.test_name, **({"coding": codings} if codings else {})},
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if o.value_quantity is not None:
            resource["valueQuantity"] = {
                "value": o.value_quantity,
                "unit": o.unit or "",
                "system": "http://unitsofmeasure.org",
                "code": o.unit or "",
            }
        elif o.value_string is not None:
            resource["valueString"] = o.value_string
        if o.reference_range_low is not None or o.reference_range_high is not None:
            rr: dict[str, Any] = {}
            if o.reference_range_low is not None:
                rr["low"] = {"value": o.reference_range_low, "unit": o.unit or ""}
            if o.reference_range_high is not None:
                rr["high"] = {"value": o.reference_range_high, "unit": o.unit or ""}
            resource["referenceRange"] = [rr]
        if o.flag:
            resource["interpretation"] = [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": o.flag,
                        }
                    ]
                }
            ]
        if o.effective_date:
            resource["effectiveDateTime"] = o.effective_date
        elif doc_context.encounter_date:
            resource["effectiveDateTime"] = doc_context.encounter_date
        return resource
