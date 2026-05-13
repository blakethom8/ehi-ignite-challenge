"""Runnable walkthrough of the extraction pipeline data model.

Mirrors the worked example in docs/architecture/extraction/EXTRACTION-DATA-MODEL.md.
Constructs synthetic Pydantic outputs (as if the LLM had returned them),
runs them through the FHIR builders + post-passes, and prints the data
at each stage.

Run:
    uv run python -m lib.extract.examples.walkthrough

Output is structured so you can pipe to less, copy a single stage, or
diff before/after a code change.
"""

from __future__ import annotations

import json

from lib.extract.pipelines.multipass_fhir import (
    AllergyEntry,
    AllergyExtraction,
    ClinicalNoteEntry,
    ClinicalNoteExtraction,
    ClinicalNoteSection,
    ConditionEntry,
    ConditionExtraction,
    DocumentContext,
    EncounterEntry,
    EncounterExtraction,
    LabObservationEntry,
    LabObservationExtraction,
    MedicationEntry,
    MedicationExtraction,
    MultiPassFHIRPipeline,
    OrganizationEntry,
    OrganizationExtraction,
    PatientEntry,
    PatientExtraction,
    PractitionerEntry,
    PractitionerExtraction,
    VitalSignEntry,
    VitalSignExtraction,
)


SECTION = "=" * 78
SUB = "-" * 78


def header(title: str) -> None:
    print()
    print(SECTION)
    print(f"  {title}")
    print(SECTION)


def sub(title: str) -> None:
    print()
    print(SUB)
    print(f"  {title}")
    print(SUB)


def dump(obj) -> None:
    """Pretty-print a Pydantic BaseModel or a dict."""
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    else:
        data = obj
    print(json.dumps(data, indent=2, default=str))


def main() -> None:
    # ------------------------------------------------------------------
    # Pass 0 — DocumentContext (extracted once per PDF, propagates to all)
    # ------------------------------------------------------------------
    header("LAYER 1 — Pass 0 output (DocumentContext)")
    doc_context = DocumentContext(
        document_type="patient-summary",
        patient_name="Blake Thomson",
        patient_dob="1993-06-16",
        encounter_date="2026-04-22",
        ordering_provider="Ani Shirvanian, NP",
        facility_name="Beverly Hills Allergy",
    )
    dump(doc_context)

    # ------------------------------------------------------------------
    # Build a synthetic pipeline instance to call the builders.
    # _new_ skips the heavy __init__ (no LLM client needed).
    # ------------------------------------------------------------------
    pipeline = MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)
    pipeline._patient_id = "unknown"  # placeholder; rewritten by post-pass T10
    pipeline._backend_name = "anthropic"
    pipeline._model = "default"

    # ------------------------------------------------------------------
    # Per-pass Pydantic outputs (Layer 1)
    # ------------------------------------------------------------------
    header("LAYER 1 — Per-pass Pydantic outputs (selected)")

    sub("ConditionExtraction")
    cond_extraction = ConditionExtraction(
        conditions=[
            ConditionEntry(
                display="Allergic rhinitis due to American house dust mite",
                icd_10_cm_code="J30.81",
                snomed_ct_code="232353008",
                clinical_status="active",
                page=1,
                source_text="Allergic rhinitis due to American house dust mite",
            )
        ]
    )
    dump(cond_extraction)

    sub("VitalSignExtraction (BP emits as TWO entries — systolic + diastolic)")
    vs_extraction = VitalSignExtraction(
        vital_signs=[
            VitalSignEntry(vital_type="blood-pressure-systolic", value=119, unit="mm[Hg]", effective_date="2026-04-22", page=2),
            VitalSignEntry(vital_type="blood-pressure-diastolic", value=71, unit="mm[Hg]", effective_date="2026-04-22", page=2),
            VitalSignEntry(vital_type="heart-rate", value=58, unit="/min", effective_date="2026-04-22", page=2),
            VitalSignEntry(vital_type="body-weight", value=95.7, unit="kg", effective_date="2026-04-22", page=2),
        ]
    )
    dump(vs_extraction)

    sub("LabObservationExtraction (note: loinc_code is null — post-pass resolves)")
    lab_extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="Glucose",
                loinc_code=None,
                value_quantity=115,
                unit="mg/dL",
                reference_range_low=65,
                reference_range_high=99,
                flag="H",
                page=2,
            )
        ]
    )
    dump(lab_extraction)

    sub("EncounterExtraction")
    enc_extraction = EncounterExtraction(
        encounters=[
            EncounterEntry(
                status="finished",
                class_code="AMB",
                type_display="Office Visit",
                period_start="2026-04-22T14:15:00",
                service_provider_display="Beverly Hills Allergy",
                participant_display="Ani Shirvanian, NP",
                reason_text="Allergy follow-up",
                page=3,
                source_text="04/22/2026 Office Visit Beverly Hills Allergy",
            )
        ]
    )
    dump(enc_extraction)

    sub("PatientExtraction")
    pat_extraction = PatientExtraction(
        patients=[
            PatientEntry(
                patient_id="33224600",
                family_name="Thomson",
                given_names=["Blake"],
                gender="male",
                birth_sex="M",
                birth_date="1993-06-16",
                race_omb_code="2106-3",
                race_text="White",
                ethnicity_omb_code="2186-5",
                ethnicity_text="Not Hispanic or Latino",
                page=1,
            )
        ]
    )
    dump(pat_extraction)

    sub("ClinicalNoteExtraction (sectioned narrative)")
    note_extraction = ClinicalNoteExtraction(
        clinical_notes=[
            ClinicalNoteEntry(
                note_type="progress-note",
                note_type_loinc="11506-3",
                title="Allergy & Immunology Progress Note",
                author_name="Ani Shirvanian",
                author_role="NP",
                encounter_date="2026-04-22",
                sections=[
                    ClinicalNoteSection(
                        title="Subjective",
                        loinc_code="10164-2",
                        narrative_text="32 yo male with persistent sinus pressure...",
                    ),
                    ClinicalNoteSection(
                        title="Assessment and Plan",
                        loinc_code="51847-2",
                        narrative_text="Allergic rhinitis. Continue Flonase, add Astelin BID.",
                    ),
                ],
                page_start=3,
                page_end=3,
            )
        ]
    )
    dump(note_extraction)

    # ------------------------------------------------------------------
    # Layer 2 — Per-builder FHIR resources (BEFORE post-passes)
    # ------------------------------------------------------------------
    header("LAYER 2 — FHIR resources from builders (BEFORE post-passes)")
    common_meta = pipeline._common_meta_template(doc_context, "example-source-id")

    sub("Glucose Observation — note `subject: Patient/unknown` + missing LOINC")
    glucose_resource = pipeline._lab_observation_to_fhir(
        lab_extraction.observations[0],
        common_meta,
        layout=None,
        doc_context=doc_context,
    )
    dump(glucose_resource)

    sub("Encounter — content-addressed stable id")
    encounter_resource = pipeline._encounter_to_fhir(
        enc_extraction.encounters[0],
        common_meta,
        layout=None,
        doc_context=doc_context,
    )
    dump(encounter_resource)

    sub("Patient — US Core extensions")
    patient_resource = pipeline._patient_to_fhir(
        pat_extraction.patients[0],
        common_meta,
        layout=None,
        doc_context=doc_context,
    )
    dump(patient_resource)

    # ------------------------------------------------------------------
    # Layer 3 — Post-passes wire cross-references
    # ------------------------------------------------------------------
    header("LAYER 3 — Bundle assembly + post-passes")

    # Build entries list (mimicking _merge_to_bundle's resource emission)
    entries: list[dict] = []

    # Apply LOINC + interpretation post-passes to Lab observations
    loinc_sources = pipeline._apply_loinc_post_pass(lab_extraction)
    interp_sources = pipeline._apply_interpretation_post_pass(lab_extraction)
    cat_lookup = pipeline._lookup_clinical_categories(lab_extraction)
    for o in lab_extraction.observations:
        entries.append(
            {
                "resource": pipeline._lab_observation_to_fhir(
                    o,
                    common_meta,
                    layout=None,
                    doc_context=doc_context,
                    loinc_resolution_source=loinc_sources.get(id(o)),
                    interpretation_source=interp_sources.get(id(o)),
                    clinical_category=cat_lookup.get(id(o)),
                )
            }
        )

    # Vital signs (no extra post-passes)
    for vs in vs_extraction.vital_signs:
        entries.append(
            {"resource": pipeline._vital_sign_to_fhir(vs, common_meta, layout=None, doc_context=doc_context)}
        )

    # Encounter, Practitioner, Organization, Patient, Note, Condition...
    entries.append({"resource": encounter_resource})
    entries.append({"resource": patient_resource})
    for c in cond_extraction.conditions:
        entries.append({"resource": pipeline._condition_to_fhir(c, common_meta, layout=None)})
    for note in note_extraction.clinical_notes:
        for resource in pipeline._clinical_note_to_fhir_resources(note, common_meta, layout=None, doc_context=doc_context):
            entries.append({"resource": resource})

    # Run cross-resource post-passes
    pipeline._assign_encounter_references(entries)
    pipeline._rewrite_patient_references(entries)

    sub("Glucose Observation — AFTER post-passes (compare to Layer 2 above)")
    # Find the same Glucose resource in the now-mutated entries list
    final_glucose = next(
        e["resource"] for e in entries
        if e["resource"]["resourceType"] == "Observation"
        and e["resource"].get("code", {}).get("text") == "Glucose"
    )
    dump(final_glucose)

    sub("Bundle summary — resourceType counts")
    counts: dict[str, int] = {}
    for e in entries:
        rt = e["resource"]["resourceType"]
        counts[rt] = counts.get(rt, 0) + 1
    for rt, n in sorted(counts.items()):
        print(f"  {n:>3} × {rt}")

    sub("Cross-reference summary — what got wired")
    has_subject = sum(
        1 for e in entries
        if e["resource"].get("subject", {}).get("reference", "").startswith("Patient/pat-")
    )
    has_encounter = sum(
        1 for e in entries
        if e["resource"].get("encounter", {}).get("reference", "").startswith("Encounter/")
    )
    print(f"  resources with subject → Patient/pat-...: {has_subject}")
    print(f"  resources with encounter → Encounter/...: {has_encounter}")
    patient_refs = {
        e["resource"].get("subject", {}).get("reference")
        for e in entries
        if e["resource"].get("subject")
    }
    print(f"  unique subject references: {patient_refs}")
    encounter_refs = {
        e["resource"].get("encounter", {}).get("reference")
        for e in entries
        if e["resource"].get("encounter")
    }
    print(f"  unique encounter references: {encounter_refs}")

    print()
    print(SECTION)
    print("  Done.")
    print(SECTION)


if __name__ == "__main__":
    main()
