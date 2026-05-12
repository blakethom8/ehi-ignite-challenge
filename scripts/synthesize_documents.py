"""
Generate synthetic multi-source clinical documents for each demo persona.

Each persona's FHIR Bundle is the ground truth. This script extracts a
compact persona summary, then asks Claude to draft each document in the
voice and shape of a specific source — discharge summary, pathology
report, anticoag clinic letter, C-CDA, pacemaker interrogation, etc.

A handful of deliberate inconsistencies between sources is baked in per
persona; those are flagged in each persona's sources.md so demo viewers
can see why Atlas's job is to resolve them.

Run:
    uv run python scripts/synthesize_documents.py
    uv run python scripts/synthesize_documents.py --persona icu-mimic
    uv run python scripts/synthesize_documents.py --persona icu-mimic --doc discharge_summary
    uv run python scripts/synthesize_documents.py --force          # re-generate everything

Generated files land in:
    data/demo-profiles/<persona>/documents/<doc-name>.<pdf|xml|json>
    data/demo-profiles/<persona>/documents/_cache/<doc-name>.html  (raw LLM output)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
# override=True because the parent shell often has ANTHROPIC_API_KEY="" set,
# which would otherwise beat the real value in .env.
load_dotenv(REPO_ROOT / ".env", override=True)

import anthropic

CLIENT = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"
# Use streaming below so we can ask for as many output tokens as we need;
# Sonnet 4.5 will happily emit 30K-token C-CDAs that would be truncated at 16K.
MAX_TOKENS = 32000

OutputFormat = Literal["pdf", "xml", "json"]


# -----------------------------------------------------------------------------
# Persona context extraction
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class PersonaContext:
    persona_id: str
    bundle_path: Path
    display_name: str
    sex: str
    birth_date: str
    deceased_date: str | None
    encounters: list[dict]
    conditions: list[str]
    medications: list[str]
    procedures: list[str]
    observations_sample: list[str]

    def summary_block(self) -> str:
        """Compact human-readable summary to drop into LLM prompts."""
        lines = [
            f"Patient: {self.display_name}",
            f"Sex: {self.sex}",
            f"Birth date: {self.birth_date}",
        ]
        if self.deceased_date:
            lines.append(f"Deceased: {self.deceased_date}")
        else:
            lines.append("Status: alive")

        if self.encounters:
            lines.append("\nRecent encounters (most recent first):")
            for e in self.encounters[:8]:
                lines.append(f"  - {e['period']}  {e['type']}")

        if self.conditions:
            lines.append("\nActive / problem-list conditions:")
            for c in self.conditions[:25]:
                lines.append(f"  - {c}")

        if self.medications:
            lines.append("\nMedications (current or recent):")
            for m in self.medications[:25]:
                lines.append(f"  - {m}")

        if self.procedures:
            lines.append("\nNotable procedures:")
            for p in self.procedures[:15]:
                lines.append(f"  - {p}")

        return "\n".join(lines)


def _safe_text(d: dict | None) -> str | None:
    if not isinstance(d, dict):
        return None
    if d.get("text"):
        return d["text"]
    coding = d.get("coding")
    if isinstance(coding, list) and coding:
        return coding[0].get("display") or coding[0].get("code")
    return None


def load_persona_context(persona_id: str, bundle_path: Path, display_name: str) -> PersonaContext:
    """Parse a FHIR Bundle (transaction or otherwise) and pull the facts that
    matter for grounding document generation. Keeps everything to strings —
    we never paste raw resources into the LLM."""

    with bundle_path.open() as f:
        bundle = json.load(f)

    patient: dict | None = None
    encounters: list[dict] = []
    condition_counts: Counter[str] = Counter()
    medication_counts: Counter[str] = Counter()
    procedure_counts: Counter[str] = Counter()
    observation_examples: list[str] = []
    medications_by_id: dict[str, str] = {}

    for entry in bundle.get("entry", []):
        r = entry.get("resource") or entry
        rt = r.get("resourceType")
        if rt == "Patient":
            patient = r
        elif rt == "Encounter":
            period = r.get("period") or {}
            start = (period.get("start") or "")[:10]
            end = (period.get("end") or "")[:10]
            typ = ""
            if r.get("type"):
                typ = _safe_text(r["type"][0]) or ""
            elif r.get("class"):
                typ = r["class"].get("display") or r["class"].get("code", "")
            encounters.append({"period": f"{start} → {end}", "type": typ})
        elif rt == "Condition":
            name = _safe_text(r.get("code"))
            if name:
                condition_counts[name] += 1
        elif rt == "MedicationRequest" or rt == "MedicationAdministration":
            name = _safe_text(r.get("medicationCodeableConcept"))
            if not name:
                mref = (r.get("medicationReference") or {}).get("reference", "")
                if mref.startswith("Medication/"):
                    name = medications_by_id.get(mref[len("Medication/") :])
            if name:
                medication_counts[name] += 1
        elif rt == "Medication":
            mname = _safe_text(r.get("code"))
            if mname:
                medications_by_id[r["id"]] = mname
        elif rt == "Procedure":
            name = _safe_text(r.get("code"))
            if name:
                procedure_counts[name] += 1
        elif rt == "Observation" and len(observation_examples) < 6:
            name = _safe_text(r.get("code"))
            value = r.get("valueQuantity")
            if name and value:
                observation_examples.append(f"{name}: {value.get('value')} {value.get('unit','')}".strip())

    # Resolve any meds that were referenced by id but we didn't have a name for yet
    # (handled inline above, so this just passes)

    if patient is None:
        raise RuntimeError(f"No Patient resource in {bundle_path}")

    sex = patient.get("gender") or "unknown"
    birth_date = patient.get("birthDate") or "unknown"
    deceased = patient.get("deceasedDateTime")

    encounters.sort(key=lambda e: e["period"], reverse=True)

    return PersonaContext(
        persona_id=persona_id,
        bundle_path=bundle_path,
        display_name=display_name,
        sex=sex,
        birth_date=birth_date,
        deceased_date=deceased,
        encounters=encounters,
        conditions=[c for c, _ in condition_counts.most_common(30)],
        medications=[m for m, _ in medication_counts.most_common(30)],
        procedures=[p for p, _ in procedure_counts.most_common(20)],
        observations_sample=observation_examples,
    )


# -----------------------------------------------------------------------------
# Document specs
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class DocSpec:
    name: str  # output filename stem
    title: str  # human-readable
    format: OutputFormat
    source: str  # what kind of source it is (used in prompts + sources.md)
    instructions: str  # what to write
    inconsistency: str | None = None  # optional deliberate contradiction directive

    @property
    def output_extension(self) -> str:
        return {"pdf": "pdf", "xml": "xml", "json": "json"}[self.format]


# Persona-level registry mapping persona_id -> bundle metadata + document menu
PERSONAS: dict[str, dict] = {
    "icu-mimic": {
        "display_name": "MIMIC patient cb70e6ae (male, ~62, complex peri-op chart)",
        "bundle": "data/demo-profiles/icu-mimic/fhir/mimic-cb70e6ae-90b1-562b-8ab0-467c65d18d5e.json",
        "documents_dir": "data/demo-profiles/icu-mimic/documents",
        "era": "2148",  # MIMIC date-shifted era
        "docs": [
            DocSpec(
                name="discharge_summary_icu",
                title="Inpatient Discharge Summary — Medical ICU",
                format="pdf",
                source="Beth Israel Deaconess Medical Center, Internal Medicine ICU",
                instructions=(
                    "Write a complete hospital discharge summary for the patient's "
                    "most recent ICU admission (July 2148, ~3-day stay). Include: "
                    "Admission Diagnosis, Hospital Course (narrative paragraph), "
                    "Discharge Diagnoses (problem list), Discharge Medications "
                    "(reconciled list with doses), Pending Studies, Follow-Up "
                    "Appointments, and a Discharge Planning summary. Sign by a "
                    "fictional Hospitalist MD."
                ),
            ),
            DocSpec(
                name="anticoag_clinic_letter",
                title="Anticoagulation Management Clinic — Letter to PCP",
                format="pdf",
                source="BIDMC Anticoagulation Clinic",
                instructions=(
                    "Write a letter from the Anticoagulation Clinic to the primary "
                    "care provider summarizing this patient's apixaban (Eliquis) "
                    "management over the last 6 months. The patient is on apixaban "
                    "5mg BID for paroxysmal atrial fibrillation. Include a small "
                    "table of recent dosing changes if any, peri-procedural hold "
                    "instructions given before his recent cardioversion, bleeding "
                    "history (none significant), and the next scheduled visit. "
                    "Sign by a Clinical Pharmacist PharmD, CACP."
                ),
            ),
            DocSpec(
                name="pacemaker_interrogation",
                title="Cardiac Device Interrogation Report",
                format="pdf",
                source="BIDMC EP Lab — Medtronic CareLink",
                instructions=(
                    "Write a Medtronic-style dual-chamber pacemaker interrogation "
                    "report. Fabricate a plausible model (e.g., Medtronic Azure "
                    "XT DR W2DR01), serial number, implant date ~2144. Include "
                    "battery status (ERI not reached, est. 4.2 yrs remaining), "
                    "lead measurements (RA + RV impedance, capture thresholds), "
                    "% pacing in each chamber (RA 18%, RV 4%), mode-switch "
                    "episodes consistent with paroxysmal AFib, and a final "
                    "interpretation block. Sign by a fictional Electrophysiologist MD."
                ),
            ),
            DocSpec(
                name="sleep_study_polysomnography",
                title="Polysomnography Report",
                format="pdf",
                source="BIDMC Sleep Disorders Center",
                instructions=(
                    "Write a polysomnography (sleep study) report for this patient. "
                    "Set the study date ~2 years before the most recent ICU admission. "
                    "Include sleep architecture (TST, sleep efficiency, stage "
                    "percentages), respiratory events (AHI consistent with severe "
                    "OSA, e.g., AHI 41/hr, lowest SpO2 78%), oxygen desaturation "
                    "index, periodic limb movements, and a final interpretation + "
                    "recommendation for CPAP titration. Sign by a fictional "
                    "Sleep Medicine MD."
                ),
            ),
            DocSpec(
                name="preop_anesthesia_questionnaire",
                title="Pre-Operative Anesthesia Questionnaire (Patient-Completed)",
                format="pdf",
                source="BIDMC Pre-Admission Testing — Patient self-report",
                instructions=(
                    "Render a SCANNED-looking pre-op questionnaire as if a patient "
                    "filled it in by hand. Use a form layout with question/answer "
                    "pairs: full name, DOB, height/weight, allergies, current "
                    "medications (the patient writes these in his own words — "
                    "abbreviating, omitting doses, getting some names slightly wrong), "
                    "past surgeries, family anesthesia history (mention an uncle who "
                    "'didn't wake up right' from anesthesia — malignant hyperthermia "
                    "concern), tobacco/alcohol use (former smoker 30 pack-years, quit "
                    "2143; social ETOH), recent dental work. Make it feel like a "
                    "real patient form: slightly informal wording, minor "
                    "inconsistencies with the formal chart."
                ),
                inconsistency=(
                    "Patient lists in own writing that he STOPPED his Eliquis 'about "
                    "2 weeks ago' — even though the anticoag clinic letter and the "
                    "discharge summary both show him as still actively on apixaban. "
                    "This is the kind of self-report that Atlas should surface as a "
                    "red flag for the surgeon."
                ),
            ),
            DocSpec(
                name="outside_oncology_fhir_feed",
                title="Outside Hematology/Oncology — FHIR R4 Bundle",
                format="json",
                source="Dana-Farber Cancer Institute — FHIR API (outside provider)",
                instructions=(
                    "Generate a FHIR R4 Bundle (type=collection) representing what "
                    "Dana-Farber's outpatient hematology service would return when "
                    "queried for this patient. Include ~30 entries: 1 Patient (with "
                    "Dana-Farber's own MRN — NOT the in-house identifier), 3-4 "
                    "Encounter resources for oncology visits over the past 18 "
                    "months, the Condition for CLL (use SNOMED 92814006), 8-12 "
                    "Observation resources covering serial CBC (WBC, ALC, "
                    "hemoglobin, platelets, LDH) with LOINC codes, 3-4 "
                    "MedicationStatement resources for oncology-related drugs, "
                    "and 2-3 DiagnosticReport resources for flow cytometry and "
                    "imaging. Use Practitioner resources for the Dana-Farber "
                    "oncologists. Reference resources by urn:uuid in fullUrl."
                ),
                inconsistency=(
                    "Two deliberate inconsistencies to bake in for harmonization "
                    "testing:\n"
                    "1) The CLL Condition resource here has clinicalStatus = "
                    "'remission' (using FHIR's condition-clinical ValueSet) — "
                    "directly contradicting the in-house chart which codes CLL "
                    "as ACTIVE / not-in-remission. This is the structured-data "
                    "twin of the C-CDA's narrative inconsistency.\n"
                    "2) Include an active MedicationStatement for IBRUTINIB "
                    "(RxNorm 1442968) — a drug that does NOT appear ANYWHERE in "
                    "the in-house FHIR record. The outside oncologist started it "
                    "but the news never reached the inpatient team. Critical "
                    "drug-interaction risk that harmonization should surface."
                ),
            ),
            DocSpec(
                name="outside_oncology_records_ccda",
                title="Outside Records — Continuity of Care Document",
                format="xml",
                source="Dana-Farber Cancer Institute — Hematology/Oncology (outside provider)",
                instructions=(
                    "Generate a valid HL7 C-CDA R2.1 Continuity of Care Document (CCD) "
                    "XML excerpt for this patient as it would be returned by an "
                    "outside hematology/oncology provider (Dana-Farber). Include "
                    "the standard sections: header (recordTarget, author, custodian, "
                    "documentationOf), Problem List (focus on CLL and related "
                    "hematologic findings), Medications (only the oncology-related "
                    "agents — ibrutinib if any, rituximab history), Allergies "
                    "(NKDA), Results (recent CBC values for WBC, lymphocyte %, "
                    "platelets, hemoglobin), and Encounters (oncology visits over "
                    "the past 18 months). Use real LOINC / SNOMED / RxNorm codes "
                    "where possible. Keep XML well-formed and human-readable."
                ),
                inconsistency=(
                    "The Problem List entry for CLL uses status 'completed' with a "
                    "comment 'patient has achieved complete response after FCR "
                    "regimen' — even though the in-house chart still codes CLL as "
                    "'not having achieved remission'. This is exactly the kind of "
                    "outside-records-vs-inhouse-records discrepancy that Atlas "
                    "should reconcile."
                ),
            ),
        ],
    },
    "oncology-breast-mcode": {
        "display_name": "Jenny M, 55F, breast cancer (mCODE Jenny M)",
        "bundle": "data/demo-profiles/oncology-breast-mcode/fhir/Bundle-mcode-patient-bundle-jenny-m.json",
        "documents_dir": "data/demo-profiles/oncology-breast-mcode/documents",
        "era": "2024",
        "docs": [
            DocSpec(
                name="mammography_report",
                title="Screening Mammography Report",
                format="pdf",
                source="Outpatient Imaging Center — Breast Imaging",
                instructions=(
                    "Write a screening mammography report dated February 2024 that "
                    "describes the initial finding that led to Jenny M's breast "
                    "cancer workup. Use standard BI-RADS structure: Indication, "
                    "Comparison (prior 2023 mammogram, BI-RADS 1), Technique "
                    "(digital with tomosynthesis), Findings (a suspicious 1.4 cm "
                    "spiculated mass in the upper outer quadrant of the right "
                    "breast at 10 o'clock, 4 cm from the nipple, with associated "
                    "pleomorphic microcalcifications), Impression (BI-RADS 4C — "
                    "high suspicion for malignancy), and Recommendation (image-"
                    "guided core needle biopsy). Sign by a fictional Breast "
                    "Imaging Radiologist."
                ),
            ),
            DocSpec(
                name="pathology_report",
                title="Surgical Pathology Report — Core Needle Biopsy",
                format="pdf",
                source="Hospital Department of Pathology",
                instructions=(
                    "Write a surgical pathology report for a stereotactic-guided "
                    "core needle biopsy of the right breast mass found on the "
                    "screening mammogram. Include: Specimen Source (4 cores, "
                    "right breast 10 o'clock), Gross Description, Microscopic "
                    "Diagnosis (Invasive Ductal Carcinoma, Nottingham grade 2, "
                    "associated DCIS), and an Ancillary Studies / Biomarkers "
                    "block with ER (positive, ~95%), PR (positive, ~80%), HER2 "
                    "(equivocal by IHC 2+, reflex FISH negative — so HER2-"
                    "negative overall), and Ki-67 (~22%). Sign by a fictional "
                    "Pathologist MD."
                ),
            ),
            DocSpec(
                name="tumor_board_summary",
                title="Multidisciplinary Breast Tumor Board Summary",
                format="pdf",
                source="Cancer Center — Breast Multidisciplinary Tumor Board",
                instructions=(
                    "Write a tumor board summary documenting the multidisciplinary "
                    "discussion of Jenny M's newly diagnosed invasive ductal "
                    "carcinoma. Sections: Presenter, Clinical Summary (age, "
                    "tumor characteristics, biomarker profile), Imaging Review, "
                    "Pathology Review, Discussion (surgical vs neoadjuvant "
                    "approach, role of MRI staging, sentinel node mapping), "
                    "Consensus Recommendation (lumpectomy + sentinel lymph "
                    "node biopsy, followed by adjuvant therapy decision based "
                    "on Oncotype DX), and Attendees (~6 fictional clinicians). "
                    "Date ~2 weeks after the pathology report."
                ),
            ),
            DocSpec(
                name="genetic_counseling_letter",
                title="Genetic Counseling Consultation Letter",
                format="pdf",
                source="Cancer Center — Cancer Genetics Program",
                instructions=(
                    "Write a letter from a genetic counselor to the patient "
                    "summarizing the genetic counseling visit. Include: "
                    "Indication for consult (breast cancer at age 55, family "
                    "history of cancer per the FamilyMemberHistory in the chart), "
                    "Family history review (drill into who in the family had what "
                    "cancer and at what age), Risk assessment (mention NCCN "
                    "criteria for BRCA testing), Recommendation (multi-gene panel "
                    "testing including BRCA1/2, PALB2, CHEK2, ATM, and a few "
                    "others), informed-consent discussion, and next steps "
                    "(sample collection, results in ~3 weeks). Sign by a "
                    "fictional Licensed Certified Genetic Counselor MS, LCGC."
                ),
                inconsistency=(
                    "In recounting the family history, the genetic counselor "
                    "lists the maternal AUNT as having had breast cancer at age "
                    "48 — but the structured FamilyMemberHistory resources in "
                    "the FHIR record actually attribute that breast cancer to "
                    "the maternal GRANDMOTHER. The family-history narrative in "
                    "the letter and the structured FHIR disagree on the "
                    "relationship — Atlas should surface this."
                ),
            ),
            DocSpec(
                name="patient_app_symptom_tracker_fhir",
                title="Patient-Generated Health Data — Symptom Tracker FHIR Feed",
                format="json",
                source="OncoLife patient symptom-tracker app (consumer health platform)",
                instructions=(
                    "Generate a FHIR R4 Bundle (type=collection) representing 8 "
                    "weeks of patient-generated health data from a consumer "
                    "symptom-tracker app that Jenny M uses during chemotherapy. "
                    "Include: 1 Patient resource (with the app's own identifier "
                    "system), and ~25-30 Observation resources representing "
                    "daily patient self-reports of nausea (LOINC 80288-4), "
                    "fatigue (LOINC 89224-8), pain intensity 0-10 (LOINC "
                    "38208-5), and weekly step count (LOINC 41950-7). For each "
                    "Observation set performer to reference the Patient (not a "
                    "Practitioner) and category to 'survey' or 'activity'. "
                    "Effective dates span the 8-week window. Show plausible "
                    "patterns — peak nausea on days 2-4 post-cycle, fatigue "
                    "highest mid-cycle, step count dropping during nausea peaks."
                ),
                inconsistency=(
                    "Two deliberate inconsistencies for harmonization testing:\n"
                    "1) TEMPORAL CONTRADICTION: This Bundle implies Jenny M is "
                    "ACTIVELY UNDERGOING CHEMOTHERAPY — but the in-house mCODE "
                    "FHIR record shows her at the DIAGNOSIS stage with NO active "
                    "chemo MedicationRequest yet. Either the app data is from a "
                    "future treatment cycle the in-house chart hasn't caught up "
                    "to, OR she's getting treatment elsewhere we don't know "
                    "about. Harmonization should flag the temporal mismatch.\n"
                    "2) PATIENT-IDENTITY DRIFT: The app's Patient.identifier uses "
                    "a DIFFERENT email and a DIFFERENT spelling of the patient's "
                    "name from the in-house record. Force the consuming platform "
                    "to do fuzzy identity matching across systems rather than "
                    "trust the identifier blindly."
                ),
            ),
            DocSpec(
                name="outside_records_ccda",
                title="Outside Records — Continuity of Care Document",
                format="xml",
                source="Prior gynecologist (community practice)",
                instructions=(
                    "Generate a valid HL7 C-CDA R2.1 Continuity of Care Document "
                    "XML excerpt for Jenny M as it would arrive from a prior "
                    "community-based gynecologist. Sections: standard CDA header, "
                    "Problem List (prior benign findings — fibrocystic changes, "
                    "previous BI-RADS 3 mass that resolved, history of HPV "
                    "infection), Medications (oral contraceptives years ago, "
                    "now off), Allergies (sulfa drugs — rash), Encounters "
                    "(annual gyn exams 2018-2023), Results (recent Pap, mammogram "
                    "results from prior years). Use real LOINC / SNOMED codes "
                    "where possible. Well-formed XML."
                ),
            ),
        ],
    },
    "cardiac-coherent": {
        "display_name": "Brady998 Hickle134, 96M, cardiac arrest survivor + prostate cancer",
        "bundle": "data/demo-profiles/cardiac-coherent/fhir/Brady998_Hickle134_fec6d99f-1cfd-f397-e740-e3952410ea2a.json",
        "documents_dir": "data/demo-profiles/cardiac-coherent/documents",
        "era": "2020",
        "docs": [
            DocSpec(
                name="cardiology_post_arrest_consult",
                title="Inpatient Cardiology Consultation — Post-Arrest",
                format="pdf",
                source="Inpatient Cardiology Service",
                instructions=(
                    "Write a cardiology consult note documenting the workup after "
                    "Brady998's cardiac arrest. Include: Reason for consult, HPI "
                    "(arrest event details — bystander CPR, ROSC in field, "
                    "transported to ED), pertinent PMH (CHD, hypertension, "
                    "diabetes, history of stroke), Exam, EKG (sinus rhythm with "
                    "old anteroseptal infarct), Echocardiogram (LV systolic "
                    "dysfunction, EF 30%, regional wall motion abnormalities, "
                    "moderate MR), Coronary angiography (multivessel CAD already "
                    "stented), Assessment & Plan (post-arrest care: targeted "
                    "temperature management, amiodarone, dual antiplatelet, ICD "
                    "evaluation when stable). Sign by a fictional Cardiologist."
                ),
            ),
            DocSpec(
                name="stroke_discharge_summary",
                title="Hospital Discharge Summary — Stroke",
                format="pdf",
                source="Stroke Service / Neurology",
                instructions=(
                    "Write a hospital discharge summary for Brady998's stroke "
                    "admission (~1 year before the cardiac arrest). Include: "
                    "Admission Dx (Acute ischemic stroke — small-vessel lacunar, "
                    "right MCA distribution, presenting with left arm "
                    "monoparesis), Hospital Course (received IV alteplase within "
                    "tPA window, partial improvement, MRI showed acute infarct "
                    "+ silent microhemorrhages noted), Workup (carotid Doppler, "
                    "echo, telemetry), Discharge Dx, Medications (mention "
                    "atorvastatin, antiplatelet, BP control), Functional Status "
                    "(modified Rankin Scale 2), Follow-Up. Sign by a Neurologist."
                ),
            ),
            DocSpec(
                name="prostate_pathology_report",
                title="Surgical Pathology Report — Prostate Biopsy",
                format="pdf",
                source="Hospital Department of Pathology",
                instructions=(
                    "Write a urologic pathology report for a transrectal ultrasound-"
                    "guided prostate biopsy (12 cores). Include: Specimen Source, "
                    "Gross Description, Microscopic findings with per-core "
                    "breakdown (some cores benign, others with adenocarcinoma — "
                    "Gleason 3+4=7, 3 of 12 cores positive, ~15% involvement, "
                    "no perineural invasion seen, no extraprostatic extension on "
                    "the cores), and Comment. Sign by a fictional Pathologist."
                ),
            ),
            DocSpec(
                name="oncology_chemo_plan",
                title="Medical Oncology Treatment Plan Letter",
                format="pdf",
                source="Medical Oncology / Genitourinary",
                instructions=(
                    "Write a medical oncology treatment plan letter to the primary "
                    "care provider outlining Brady998's planned therapy for "
                    "metastatic castration-sensitive prostate cancer. Cover: "
                    "Indication / staging summary, Treatment Plan (combination "
                    "ADT — leuprolide 22.5 mg IM every 3 months — plus docetaxel "
                    "75 mg/m² IV every 3 weeks for 6 cycles), Pre-treatment "
                    "labs needed, expected side effects, monitoring plan "
                    "(PSA q3 months), and a discussion of cardiac considerations "
                    "given his post-arrest status (anthracycline contraindication, "
                    "docetaxel is acceptable with monitoring). Sign by an Oncologist."
                ),
                inconsistency=(
                    "The letter clearly states docetaxel will be given EVERY 3 "
                    "WEEKS — but the MedicationRequest resources in Brady998's "
                    "FHIR record have been coded with a dispensing interval of "
                    "every 4 weeks. Atlas should surface this dosing-frequency "
                    "discrepancy between the narrative plan and the structured "
                    "medication order."
                ),
            ),
            DocSpec(
                name="pacemaker_telemetry_fhir",
                title="Pacemaker Remote Monitoring — Device Telemetry FHIR Feed",
                format="json",
                source="Medtronic CareLink remote monitoring (implanted device feed)",
                instructions=(
                    "Generate a FHIR R4 Bundle (type=collection) representing 6 "
                    "months of remote pacemaker telemetry. NOTE: Brady998 in the "
                    "in-house chart already has a 'Presence of cardiac pacemaker' "
                    "code — this Bundle is the device-side feed. Include: 1 "
                    "Patient resource (with the device platform's own "
                    "identifier), 1 Device resource (model 'Medtronic Azure XT "
                    "DR W2DR01', serial fabricated), and ~25 Observation "
                    "resources. Observations should cover: weekly atrial pacing "
                    "% (LOINC 79735-7 or device-specific code), ventricular "
                    "pacing %, AT/AF burden % (this is the headline metric), "
                    "right atrial lead impedance, right ventricular lead "
                    "impedance, mode-switch episode count, battery voltage. "
                    "Each Observation MUST set device = Device/<id> (NOT a "
                    "Practitioner performer) — it's a device-generated reading. "
                    "Values should show realistic trends across the 6-month "
                    "window."
                ),
                inconsistency=(
                    "Two deliberate inconsistencies for harmonization testing:\n"
                    "1) QUANTITATIVE-vs-QUALITATIVE: This telemetry shows AT/AF "
                    "burden trending up over the 6 months from ~5% to ~22% — "
                    "consistent with WORSENING atrial fibrillation. The in-house "
                    "chart will still code AF as 'paroxysmal' qualitatively with "
                    "no quantification. Harmonization should reconcile the "
                    "numerical trend with the textual diagnosis.\n"
                    "2) RV PACING DRIFT: The most recent telemetry shows RV "
                    "pacing at ~38% — substantially higher than the 4% reported "
                    "in the pacemaker_interrogation.pdf (which was an in-office "
                    "interrogation ~6 months earlier). This is a real-world "
                    "scenario where the device function has shifted between two "
                    "data sources at different time points. Harmonization should "
                    "surface the temporal version conflict, not silently pick one."
                ),
            ),
            DocSpec(
                name="cardiac_mri_report",
                title="Cardiac MRI Radiology Report",
                format="pdf",
                source="Hospital Radiology / Cardiac Imaging",
                instructions=(
                    "Write a cardiac MRI radiology report that is the human-"
                    "readable companion to the DICOM file already in this "
                    "persona's imaging/ directory. Use standard structure: "
                    "Indication (evaluation of LV function after cardiac "
                    "arrest, ischemic burden), Technique (1.5T scanner, gated "
                    "cine SSFP, T1/T2 mapping, late gadolinium enhancement "
                    "with gadobutrol), Findings (LV size, LVEF, regional wall "
                    "motion, scar burden / LGE pattern consistent with prior "
                    "infarct, RV findings, valves, pericardium), Impression "
                    "(severely reduced LVEF ~28%, transmural inferoseptal LGE "
                    "consistent with prior MI, no acute features). Sign by a "
                    "Cardiothoracic Radiologist."
                ),
            ),
        ],
    },
    "polypharmacy-synthea": {
        "display_name": "Ester635 Echevarría842, 99F, A-fib + Alzheimer's + colorectal",
        "bundle": "data/demo-profiles/polypharmacy-synthea/fhir/Ester635_Echevarría842_d36b57d2-052b-4b7a-9978-d4bac3f59c36.json",
        "documents_dir": "data/demo-profiles/polypharmacy-synthea/documents",
        "era": "2022",
        "docs": [
            DocSpec(
                name="discharge_summary_recent",
                title="Hospital Discharge Summary — Most Recent Admission",
                format="pdf",
                source="Hospital Internal Medicine Service",
                instructions=(
                    "Write a hospital discharge summary for Ester635's most recent "
                    "admission. The admission was for a brief observation stay "
                    "after a fall at home (no fracture) complicated by a UTI. "
                    "Include the standard discharge-summary sections, a thorough "
                    "discharge medication reconciliation list (cover warfarin, "
                    "digoxin, verapamil, galantamine, insulin, simvastatin, "
                    "epoetin alfa for CKD-related anemia), goals-of-care "
                    "discussion (the patient is 99, on FOLFOX for colorectal, "
                    "DNR/DNI established with the family), follow-up. Sign by a "
                    "Hospitalist."
                ),
            ),
            DocSpec(
                name="anticoag_clinic_letter",
                title="Anticoagulation Clinic — INR Monitoring Letter",
                format="pdf",
                source="Coumadin Clinic — Outpatient Pharmacy",
                instructions=(
                    "Write a coumadin (warfarin) clinic letter summarizing the "
                    "last 6 months of INR monitoring for Ester635. Include a "
                    "small table of INR values, target range (2.0-3.0 for "
                    "AFib), dose adjustments (this is a HIGH-RISK warfarin "
                    "patient — concurrent FOLFOX, advanced age, falls risk), "
                    "any held-doses during chemo cycles, bleeding/bruising "
                    "history (mention easy bruising), and the plan for the "
                    "next interval. Sign by a Clinical Pharmacist."
                ),
            ),
            DocSpec(
                name="neurology_dementia_consult",
                title="Neurology Consultation — Cognitive Assessment",
                format="pdf",
                source="Neurology / Memory Disorders Clinic",
                instructions=(
                    "Write a neurology consult note evaluating Ester635 for "
                    "cognitive decline. Include: HPI (family reports increasing "
                    "forgetfulness, getting lost in familiar settings, "
                    "occasional confusion with medications), cognitive testing "
                    "(MMSE score, drawing/clock, recall), neuro exam, MRI "
                    "findings (mild generalized atrophy, periventricular white "
                    "matter changes — small vessel disease, no acute findings), "
                    "Assessment (Alzheimer's disease, mild-to-moderate stage), "
                    "Plan (initiate galantamine, low-dose start with titration; "
                    "safety planning; caregiver education; medication "
                    "supervision given polypharmacy). Sign by a Neurologist."
                ),
            ),
            DocSpec(
                name="colonoscopy_pathology",
                title="Colonoscopy Report + Surgical Pathology",
                format="pdf",
                source="GI / Endoscopy Center + Pathology",
                instructions=(
                    "Combine a colonoscopy procedure note and the surgical "
                    "pathology of the biopsied lesions into one report. Cover: "
                    "Indication (rectal bleeding), Procedure details (sedation, "
                    "scope to cecum, prep quality), Findings (multiple polyps — "
                    "a few diminutive hyperplastic, one ~25 mm sessile lesion in "
                    "the rectum biopsied), Pathology (invasive moderately "
                    "differentiated adenocarcinoma in the rectal mass biopsy; "
                    "tubular adenoma with low-grade dysplasia in the others), "
                    "Recommendation (oncology referral, staging CT, surgical "
                    "consultation). Sign by a Gastroenterologist + Pathologist."
                ),
            ),
            DocSpec(
                name="home_monitoring_fhir_feed",
                title="Home Monitoring — Connected-Care FHIR Feed",
                format="json",
                source="Lively Care home-monitoring platform (connected BP cuff + glucometer)",
                instructions=(
                    "Generate a FHIR R4 Bundle (type=collection) representing 60 "
                    "days of patient-collected home monitoring for Ester635. "
                    "Include: 1 Patient resource (with the home-monitoring "
                    "platform's identifier system), 2 Device resources (a "
                    "connected Omron BP cuff, an iHealth glucometer), and ~30 "
                    "Observation resources covering: daily home blood pressure "
                    "(LOINC 85354-9 with components 8480-6 systolic, 8462-4 "
                    "diastolic), home blood glucose (LOINC 2339-0), and weight "
                    "(LOINC 29463-7). Observation.device should reference the "
                    "appropriate Device; performer references Patient (she takes "
                    "the readings). Values should show clinically plausible "
                    "patterns — see the inconsistency directive for the "
                    "specific signal to bake in."
                ),
                inconsistency=(
                    "Two deliberate inconsistencies for harmonization testing:\n"
                    "1) UNCONTROLLED HTN despite 'controlled' qualitative coding: "
                    "Home BP readings should show a 60-day average systolic of "
                    "~165 mmHg with frequent readings >170. The in-house chart "
                    "lists 'Essential (primary) hypertension' as a problem WITHOUT "
                    "any 'uncontrolled' modifier — the quantitative home data "
                    "shows she is in fact uncontrolled. Harmonization should "
                    "surface that the qualitative diagnosis status is wrong.\n"
                    "2) GLUCOSE-INSULIN MISMATCH: Home glucose readings should "
                    "frequently exceed 250 mg/dL despite the chart listing her "
                    "on Humulin 70/30 insulin. Suggests dose inadequacy or "
                    "compliance issues that the in-house record (which only sees "
                    "her at appointments) misses. Harmonization should flag the "
                    "medication-effectiveness gap."
                ),
            ),
            DocSpec(
                name="outside_pcp_ccda",
                title="Outside Records — PCP Continuity of Care Document",
                format="xml",
                source="Community primary care practice (referring PCP)",
                instructions=(
                    "Generate a valid HL7 C-CDA R2.1 Continuity of Care Document "
                    "XML excerpt as it would be sent over by Ester635's "
                    "community primary care provider when she established at "
                    "the new specialist office. Sections: header, Problem List "
                    "(hypertension — controlled; atrial fibrillation — chronic; "
                    "type 2 diabetes; osteoarthritis), Medications (CRITICAL: "
                    "this older record lists aspirin 81 mg daily and does NOT "
                    "list warfarin — it's a stale record from before warfarin "
                    "was started), Allergies (NKDA), Results (recent A1c, BMP, "
                    "lipid panel), Encounters (annual visits over the past 3 "
                    "years). Use real LOINC / SNOMED / RxNorm codes."
                ),
                inconsistency=(
                    "The PCP's outside CCDA lists ASPIRIN 81 mg daily as the "
                    "patient's antithrombotic — but the in-house FHIR record "
                    "shows her on WARFARIN 5 mg. This is a stale outside "
                    "record from before warfarin was started, and conflicts "
                    "with the current medication list. Atlas should flag the "
                    "ASA-vs-warfarin discrepancy and the elevated bleeding "
                    "risk if both were ever co-administered."
                ),
            ),
        ],
    },
}


# -----------------------------------------------------------------------------
# Prompting + LLM
# -----------------------------------------------------------------------------


HTML_SYSTEM_PROMPT = """You are a meticulous clinical-document drafter generating SYNTHETIC documents for a healthcare-application demo. The patient is fictional or de-identified. Your job is to write a single document that looks and reads like the real thing — formal medical voice, plausible details, realistic provider names and addresses (fabricated).

Output requirements:
- Output ONE complete, valid HTML5 document (DOCTYPE html, html, head, body).
- Inline a <style> block in the <head> with CSS that styles the document like a real printed medical record — serif body font, clear letterhead at the top, dated sections, signature blocks, no images or external resources.
- Use semantic HTML (h1/h2/h3 for sections, dl/dt/dd for label-value pairs, table for results).
- Page width is 8.5x11 in; assume the HTML will be rendered to PDF via WeasyPrint with @page margins of 0.6in.
- Do NOT include any code fences, commentary, or wrapper text — output the HTML and nothing else.
- Keep the document realistic but invent provider names, phone numbers, MRNs, etc. These are SYNTHETIC documents."""

FHIR_SYSTEM_PROMPT = """You are generating a SYNTHETIC FHIR R4 Bundle (JSON) for a healthcare-application demo. The patient is fictional or de-identified. This Bundle represents data arriving from an outside source (a specialty clinic, patient-generated app, implanted device telemetry, or home-monitoring platform) — distinctly different from a primary EHR export.

Output requirements:
- Output ONE complete, well-formed JSON document — a FHIR R4 Bundle.
- Bundle.type MUST be "collection" (this is an outside data feed, not an in-house transaction).
- Bundle.id is a fabricated UUID.
- Bundle.meta.source identifies the originating system (e.g. "https://dana-farber.example/fhir", "urn:device:medtronic-carelink", "urn:patient-app:oncolife/v3", "urn:home-monitoring:lively-bp/v2").
- Bundle.entry[*].fullUrl uses urn:uuid:<uuid> form; resources reference each other via these urn:uuid: forms.
- Every resource MUST have a Patient reference, but use a SECONDARY patient identifier (Patient.identifier with system that matches the outside source — NOT the in-house MRN). This forces the consuming platform to do identity matching across systems.
- Use real LOINC, SNOMED, RxNorm, NPI, and FHIR R4 ValueSet codes. Different outside sources legitimately use different code systems for the same concept — that's the point.
- For patient-generated or device-generated Observations, set Observation.performer or Observation.device appropriately (Patient reference, or Device reference) — NOT the in-house Practitioner.
- Use ISO 8601 dates aligned with the persona's chart timeline.
- The Bundle should contain on the order of 20-40 entries — a focused, plausible feed, not a complete chart.
- JSON CORRECTNESS:
  * Valid JSON throughout: properly quoted strings, escaped special chars, no trailing commas, no comments.
  * Every opened brace/bracket must close.
  * No truncation — finish the document.
- Do NOT include code fences, commentary, or wrapper text — output the JSON object and nothing else."""


XML_SYSTEM_PROMPT = """You are generating a SYNTHETIC HL7 C-CDA R2.1 Continuity of Care Document (CCD) for a healthcare-application demo. The patient is fictional or de-identified.

Output requirements:
- Output ONE complete, WELL-FORMED XML document starting with <?xml version="1.0" encoding="UTF-8"?>.
- Root element is <ClinicalDocument xmlns="urn:hl7-org:v3" ...> with the canonical CCD templateId.
- Include realistic sections (recordTarget, author, custodian, componentOf, structuredBody with Problem List, Medications, Allergies, Results, Encounters as specified).
- Use real LOINC, SNOMED, and RxNorm codes where possible. Codes for sections (e.g., 11450-4 problem list, 10160-0 medications).
- Provider, organization, and address details are fabricated.
- XML CORRECTNESS IS MANDATORY:
  * Escape & as &amp; in EVERY attribute value and text node (e.g. "Hematology &amp; Oncology", NEVER "Hematology & Oncology").
  * Escape < as &lt;, > as &gt; inside attribute values and text where they aren't tag delimiters.
  * Every opened element must have a matching close tag. No truncation.
  * Self-closing tags use <tag/>, not <tag />.
- KEEP IT CONCISE: this is a demo C-CDA, not a real-world transfer document. Limit Problem List to ~6 problems, Medications to ~5 entries, Allergies to ~3, Results to ~6 most-recent panels, Encounters to ~4. A complete and well-formed 500-line CCD is infinitely better than a truncated 1000-line one.
- Do NOT include code fences, commentary, or wrapper text — output XML and nothing else."""


def build_user_prompt(ctx: PersonaContext, doc: DocSpec) -> str:
    parts = [
        f"DOCUMENT TYPE: {doc.title}",
        f"SOURCE / LETTERHEAD: {doc.source}",
        "",
        "PATIENT CONTEXT (ground truth — keep clinical facts consistent with this):",
        ctx.summary_block(),
        "",
        "INSTRUCTIONS FOR THIS DOCUMENT:",
        doc.instructions.strip(),
    ]
    if doc.inconsistency:
        parts += [
            "",
            "DELIBERATE INCONSISTENCY (bake into this document — this is intentional and "
            "exists to drive the demo's reconciliation feature):",
            doc.inconsistency.strip(),
        ]
    return "\n".join(parts)


def call_claude(system: str, user: str) -> str:
    """One streamed API call; returns the assistant text. Streaming lets us
    request >21K output tokens without the SDK's long-request guard rejecting
    the call."""
    chunks: list[str] = []
    with CLIENT.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)
    return "".join(chunks).strip()


# -----------------------------------------------------------------------------
# Rendering
# -----------------------------------------------------------------------------


WEASYPRINT_BIN = "/Library/Frameworks/Python.framework/Versions/3.14/bin/weasyprint"


def render_pdf_from_html(html_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    # WeasyPrint needs pango/glib/cairo from Homebrew at /opt/homebrew/lib on
    # Apple Silicon; ensure ctypes can find them.
    env = os.environ.copy()
    env["DYLD_FALLBACK_LIBRARY_PATH"] = (
        "/opt/homebrew/lib:" + env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    )
    result = subprocess.run(
        [WEASYPRINT_BIN, str(html_path), str(pdf_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"weasyprint failed for {html_path}:\n{result.stderr}")


def strip_fences(text: str) -> str:
    """Strip markdown code fences if the model emitted any."""
    t = text.strip()
    if t.startswith("```"):
        # remove the first line (```html or ```xml) and the trailing ```
        lines = t.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


# -----------------------------------------------------------------------------
# Per-document orchestration
# -----------------------------------------------------------------------------


def output_path(persona_cfg: dict, doc: DocSpec) -> Path:
    return Path(persona_cfg["documents_dir"]) / f"{doc.name}.{doc.output_extension}"


def cache_html_path(persona_cfg: dict, doc: DocSpec) -> Path:
    return Path(persona_cfg["documents_dir"]) / "_cache" / f"{doc.name}.html"


def generate_one(persona_id: str, persona_cfg: dict, doc: DocSpec, ctx: PersonaContext, force: bool) -> tuple[str, str]:
    """Generate a single document. Returns (status, output_path_str)."""
    out_path = output_path(persona_cfg, doc)
    if out_path.exists() and not force:
        return ("skip", str(out_path))

    system = {
        "pdf": HTML_SYSTEM_PROMPT,
        "xml": XML_SYSTEM_PROMPT,
        "json": FHIR_SYSTEM_PROMPT,
    }[doc.format]
    user = build_user_prompt(ctx, doc)
    raw = call_claude(system, user)
    body = strip_fences(raw)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if doc.format == "pdf":
        html_path = cache_html_path(persona_cfg, doc)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(body)
        render_pdf_from_html(html_path, out_path)
    elif doc.format == "xml":
        out_path.write_text(body)
    elif doc.format == "json":
        out_path.write_text(body)
    else:
        raise ValueError(f"unknown format {doc.format}")

    return ("generated", str(out_path))


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--persona", default=None, help="persona id to generate (default: all)")
    p.add_argument("--doc", default=None, help="doc name within the chosen persona")
    p.add_argument("--force", action="store_true", help="re-generate even if output exists")
    p.add_argument("--workers", type=int, default=3, help="parallel API workers")
    args = p.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set (check .env)", file=sys.stderr)
        return 2

    if args.persona:
        persona_ids = [args.persona]
    else:
        persona_ids = list(PERSONAS.keys())

    total_generated, total_skipped, total_failed = 0, 0, 0

    for pid in persona_ids:
        cfg = PERSONAS[pid]
        bundle_path = REPO_ROOT / cfg["bundle"]
        if not bundle_path.exists():
            print(f"  ! missing bundle: {bundle_path}", file=sys.stderr)
            continue

        print(f"\n=== {pid} :: {cfg['display_name']} ===")
        print(f"  bundle: {bundle_path}")
        ctx = load_persona_context(pid, bundle_path, cfg["display_name"])
        print(f"  context: {len(ctx.conditions)} conditions, {len(ctx.medications)} meds, {len(ctx.encounters)} encounters")

        docs = cfg["docs"]
        if args.doc:
            docs = [d for d in docs if d.name == args.doc]
            if not docs:
                print(f"  ! no doc named {args.doc} in persona {pid}", file=sys.stderr)
                continue

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(generate_one, pid, cfg, d, ctx, args.force): d for d in docs}
            for fut in as_completed(futures):
                doc = futures[fut]
                try:
                    status, path = fut.result()
                except Exception as e:  # noqa: BLE001
                    print(f"  ✗ {doc.name} ({doc.format}): {e}", file=sys.stderr)
                    total_failed += 1
                    continue
                if status == "skip":
                    print(f"  · {doc.name} ({doc.format}): exists, skipped")
                    total_skipped += 1
                else:
                    print(f"  ✓ {doc.name} ({doc.format}) → {path}")
                    total_generated += 1

    print(f"\nDone. Generated {total_generated}, skipped {total_skipped}, failed {total_failed}.")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
