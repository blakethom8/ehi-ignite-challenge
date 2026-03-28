"""
FHIR R4 patient bundle parser.

Entry point: parse_bundle(file_path) -> PatientRecord

Loads a single-patient FHIR Bundle JSON file, partitions resources by type,
calls per-type extractors, builds cross-reference indexes, and returns a
fully resolved PatientRecord ready for catalog and view layers.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from .extractors import (
    extract_allergy,
    extract_claim,
    extract_condition,
    extract_diagnostic_report,
    extract_eob_insurer,
    extract_eob_payment,
    extract_encounter,
    extract_imaging_study,
    extract_immunization,
    extract_medication,
    extract_observation,
    extract_patient,
    extract_procedure,
    strip_ref,
)
from .models import PatientRecord


def parse_bundle(file_path: str | Path) -> PatientRecord:
    """
    Parse a FHIR R4 patient bundle JSON file into a PatientRecord.

    Args:
        file_path: Path to the .json bundle file.

    Returns:
        PatientRecord with all resources extracted and indexes built.
    """
    file_path = Path(file_path)
    record = PatientRecord()

    # --- Load ---
    file_size = os.path.getsize(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    entries = bundle.get("entry", [])

    # --- Single-pass partition by resourceType ---
    buckets: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "Unknown")
        buckets[rtype].append(resource)

    # Raw counts
    record.resource_type_counts = {k: len(v) for k, v in buckets.items()}

    # --- Extract Patient ---
    patients = buckets.get("Patient", [])
    if not patients:
        record.parse_warnings.append("No Patient resource found in bundle")
        return record
    record.summary = extract_patient(patients[0], str(file_path), file_size)

    # --- Extract all clinical resource types ---
    for raw in buckets.get("Encounter", []):
        try:
            record.encounters.append(extract_encounter(raw))
        except Exception as e:
            record.parse_warnings.append(f"Encounter {raw.get('id', '?')}: {e}")

    for raw in buckets.get("Observation", []):
        try:
            record.observations.append(extract_observation(raw))
        except Exception as e:
            record.parse_warnings.append(f"Observation {raw.get('id', '?')}: {e}")

    for raw in buckets.get("Condition", []):
        try:
            record.conditions.append(extract_condition(raw))
        except Exception as e:
            record.parse_warnings.append(f"Condition {raw.get('id', '?')}: {e}")

    for raw in buckets.get("MedicationRequest", []):
        try:
            record.medications.append(extract_medication(raw))
        except Exception as e:
            record.parse_warnings.append(f"MedicationRequest {raw.get('id', '?')}: {e}")

    for raw in buckets.get("Procedure", []):
        try:
            record.procedures.append(extract_procedure(raw))
        except Exception as e:
            record.parse_warnings.append(f"Procedure {raw.get('id', '?')}: {e}")

    for raw in buckets.get("DiagnosticReport", []):
        try:
            record.diagnostic_reports.append(extract_diagnostic_report(raw))
        except Exception as e:
            record.parse_warnings.append(f"DiagnosticReport {raw.get('id', '?')}: {e}")

    for raw in buckets.get("Immunization", []):
        try:
            record.immunizations.append(extract_immunization(raw))
        except Exception as e:
            record.parse_warnings.append(f"Immunization {raw.get('id', '?')}: {e}")

    for raw in buckets.get("AllergyIntolerance", []):
        try:
            record.allergies.append(extract_allergy(raw))
        except Exception as e:
            record.parse_warnings.append(f"AllergyIntolerance {raw.get('id', '?')}: {e}")

    for raw in buckets.get("ImagingStudy", []):
        try:
            record.imaging_studies.append(extract_imaging_study(raw))
        except Exception as e:
            record.parse_warnings.append(f"ImagingStudy {raw.get('id', '?')}: {e}")

    # Claims — extract first, then match with EOBs below
    raw_claims: dict[str, dict] = {}
    for raw in buckets.get("Claim", []):
        try:
            claim = extract_claim(raw)
            raw_claims[claim.claim_id] = claim
            record.claims.append(claim)
        except Exception as e:
            record.parse_warnings.append(f"Claim {raw.get('id', '?')}: {e}")

    # EOBs — extract insurer + payment, match back to Claim by ID
    for raw in buckets.get("ExplanationOfBenefit", []):
        try:
            eob_id = raw.get("id", "")
            insurer = extract_eob_insurer(raw)
            payment = extract_eob_payment(raw)
            # In Synthea, Claim ID == EOB ID
            if eob_id in raw_claims:
                raw_claims[eob_id].insurer = insurer
                raw_claims[eob_id].total_paid = payment
        except Exception as e:
            record.parse_warnings.append(f"EOB {raw.get('id', '?')}: {e}")

    # Lower-priority resources kept raw
    record.care_plans_raw = buckets.get("CarePlan", [])
    record.care_teams_raw = buckets.get("CareTeam", [])
    record.goals_raw = buckets.get("Goal", [])
    record.devices_raw = buckets.get("Device", [])

    # Warn on unexpected resource types
    known_types = {
        "Patient", "Encounter", "Observation", "Condition", "MedicationRequest",
        "Procedure", "DiagnosticReport", "Immunization", "AllergyIntolerance",
        "ImagingStudy", "Claim", "ExplanationOfBenefit", "CarePlan", "CareTeam",
        "Goal", "Device", "Organization", "Practitioner", "PractitionerRole",
        "Location", "Coverage", "MedicationAdministration",
    }
    for rtype in buckets:
        if rtype not in known_types:
            record.parse_warnings.append(f"Unknown resource type encountered: {rtype} ({len(buckets[rtype])} resources)")

    # --- Build indexes ---
    _build_indexes(record)

    return record


def _build_indexes(record: PatientRecord) -> None:
    """Post-process: build encounter-centric index and obs lookup indexes."""

    # Encounter index: encounter_id -> EncounterRecord
    for enc in record.encounters:
        record.encounter_index[enc.encounter_id] = enc

    # Obs index + obs_by_loinc
    for obs in record.observations:
        record.obs_index[obs.obs_id] = obs
        if obs.loinc_code:
            record.obs_by_loinc.setdefault(obs.loinc_code, []).append(obs.obs_id)

    # Link observations -> encounters
    for obs in record.observations:
        if obs.encounter_id and obs.encounter_id in record.encounter_index:
            record.encounter_index[obs.encounter_id].linked_observations.append(obs.obs_id)
            record.obs_by_encounter.setdefault(obs.encounter_id, []).append(obs.obs_id)

    # Link conditions -> encounters
    for cond in record.conditions:
        if cond.encounter_id and cond.encounter_id in record.encounter_index:
            record.encounter_index[cond.encounter_id].linked_conditions.append(cond.condition_id)

    # Link procedures -> encounters
    for proc in record.procedures:
        if proc.encounter_id and proc.encounter_id in record.encounter_index:
            record.encounter_index[proc.encounter_id].linked_procedures.append(proc.procedure_id)

    # Link medications -> encounters
    for med in record.medications:
        if med.encounter_id and med.encounter_id in record.encounter_index:
            record.encounter_index[med.encounter_id].linked_medications.append(med.med_id)

    # Link diagnostic reports -> encounters
    for dr in record.diagnostic_reports:
        if dr.encounter_id and dr.encounter_id in record.encounter_index:
            record.encounter_index[dr.encounter_id].linked_diagnostic_reports.append(dr.report_id)

    # Link immunizations -> encounters
    for imm in record.immunizations:
        if imm.encounter_id and imm.encounter_id in record.encounter_index:
            record.encounter_index[imm.encounter_id].linked_immunizations.append(imm.imm_id)

    # Link imaging studies -> encounters
    for study in record.imaging_studies:
        if study.encounter_id and study.encounter_id in record.encounter_index:
            record.encounter_index[study.encounter_id].linked_imaging_studies.append(study.study_id)


# ---------------------------------------------------------------------------
# CLI validation entry point
# ---------------------------------------------------------------------------

def _print_summary(record: PatientRecord) -> None:
    s = record.summary
    print(f"\n{'='*60}")
    print(f"  Patient: {s.name}")
    print(f"  ID:      {s.patient_id}")
    print(f"  DOB:     {s.birth_date}  |  Age: {s.age_years:.1f} yrs  |  Gender: {s.gender}")
    print(f"  Race:    {s.race}  |  Ethnicity: {s.ethnicity}")
    print(f"  Location: {s.city}, {s.state}")
    print(f"  Deceased: {s.deceased}" + (f"  ({s.deceased_date})" if s.deceased_date else ""))
    print(f"  File: {Path(s.file_path).name}  ({s.file_size_bytes / 1024:.1f} KB)")
    print(f"{'='*60}")

    total = sum(record.resource_type_counts.values())
    print(f"\n  Resource Type Counts (total: {total})")
    for rtype, count in sorted(record.resource_type_counts.items(), key=lambda x: -x[1]):
        print(f"    {rtype:<30} {count:>6}")

    print(f"\n  Encounters:    {len(record.encounters)}")
    print(f"  Conditions:    {len(record.conditions)}  ({sum(1 for c in record.conditions if c.is_active)} active)")
    print(f"  Medications:   {len(record.medications)}")
    print(f"  Observations:  {len(record.observations)}  ({len(record.obs_by_loinc)} unique LOINC codes)")
    print(f"  Procedures:    {len(record.procedures)}")
    print(f"  Diag Reports:  {len(record.diagnostic_reports)}")
    print(f"  Immunizations: {len(record.immunizations)}")
    print(f"  Allergies:     {len(record.allergies)}")
    print(f"  Claims:        {len(record.claims)}")
    print(f"  Imaging:       {len(record.imaging_studies)}")

    if record.conditions:
        print(f"\n  Active Conditions:")
        for c in sorted(record.conditions, key=lambda x: x.onset_dt or __import__('datetime').datetime.min):
            status = "ACTIVE" if c.is_active else "resolved"
            print(f"    [{status:8}] {c.code.label()}")

    if record.allergies:
        print(f"\n  Allergies:")
        for a in record.allergies:
            print(f"    {a.code.label()}  (criticality: {a.criticality or 'unknown'})")

    if record.parse_warnings:
        print(f"\n  Warnings ({len(record.parse_warnings)}):")
        for w in record.parse_warnings[:10]:
            print(f"    ⚠ {w}")
        if len(record.parse_warnings) > 10:
            print(f"    ... and {len(record.parse_warnings) - 10} more")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bundle_parser.py <path/to/patient_bundle.json>")
        sys.exit(1)

    import time
    path = sys.argv[1]
    print(f"Parsing: {path}")
    t0 = time.time()
    result = parse_bundle(path)
    elapsed = time.time() - t0
    print(f"Parsed in {elapsed:.3f}s")
    _print_summary(result)
