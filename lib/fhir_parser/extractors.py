"""
Per-resource-type extraction functions.

Each function takes a raw FHIR resource dict and returns a typed model.
All date parsing, reference stripping, and value-type handling lives here.
"""

from __future__ import annotations

import base64
from datetime import datetime, date
from typing import Any

from .models import (
    AllergyRecord,
    ClaimRecord,
    CodeableConcept,
    ConditionRecord,
    DiagnosticReportRecord,
    EncounterRecord,
    ImagingStudyRecord,
    ImmunizationRecord,
    MedicationRecord,
    ObservationComponent,
    ObservationRecord,
    PatientSummary,
    Period,
    ProcedureRecord,
)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def strip_ref(ref: str) -> str:
    """Normalize a FHIR reference string to a bare UUID.

    Handles:
      "urn:uuid:abc123"  -> "abc123"
      "Patient/abc123"   -> "abc123"
      "abc123"           -> "abc123"
    """
    if not ref:
        return ""
    if ref.startswith("urn:uuid:"):
        return ref[len("urn:uuid:"):]
    if "/" in ref:
        return ref.split("/")[-1]
    return ref


def parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string, returning None on failure."""
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value[:len(fmt) + 6], fmt)
        except ValueError:
            pass
    # Fallback: let fromisoformat handle it (Python 3.11+ handles timezone offset)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def get_codeable_concept(obj: dict, key: str) -> CodeableConcept:
    """Extract the first coding from a CodeableConcept field."""
    cc = obj.get(key, {})
    if not cc:
        return CodeableConcept()
    codings = cc.get("coding", [])
    text = cc.get("text", "")
    if codings:
        c = codings[0]
        return CodeableConcept(
            system=c.get("system", ""),
            code=c.get("code", ""),
            display=c.get("display", ""),
            text=text,
        )
    return CodeableConcept(text=text)


def get_status_code(obj: dict, key: str) -> str:
    """Extract a status code from a CodeableConcept (e.g. clinicalStatus)."""
    cc = obj.get(key, {})
    codings = cc.get("coding", [])
    if codings:
        return codings[0].get("code", "")
    return cc.get("code", "")


def get_period(obj: dict, key: str = "period") -> Period:
    p = obj.get(key, {})
    return Period(
        start=parse_dt(p.get("start")),
        end=parse_dt(p.get("end")),
    )


# ---------------------------------------------------------------------------
# Resource extractors
# ---------------------------------------------------------------------------

def extract_patient(resource: dict, file_path: str = "", file_size: int = 0) -> PatientSummary:
    summary = PatientSummary()
    summary.patient_id = resource.get("id", "")
    summary.file_path = file_path
    summary.file_size_bytes = file_size

    # Name
    names = resource.get("name", [])
    if names:
        n = names[0]
        family = n.get("family", "")
        given = " ".join(n.get("given", []))
        summary.name = f"{given} {family}".strip()

    summary.gender = resource.get("gender", "")

    # Birth / death
    summary.birth_date = parse_date(resource.get("birthDate"))
    if resource.get("deceasedBoolean"):
        summary.deceased = True
    deceased_str = resource.get("deceasedDateTime")
    if deceased_str:
        summary.deceased = True
        summary.deceased_date = parse_date(deceased_str)

    # Age
    if summary.birth_date:
        ref = summary.deceased_date or date.today()
        summary.age_years = (ref - summary.birth_date).days / 365.25

    # Address
    addresses = resource.get("address", [])
    if addresses:
        addr = addresses[0]
        summary.city = addr.get("city", "")
        summary.state = addr.get("state", "")
        summary.country = addr.get("country", "")
        summary.postal_code = addr.get("postalCode", "")
        for ext in addr.get("extension", []):
            if "geolocation" in ext.get("url", ""):
                for sub in ext.get("extension", []):
                    if sub.get("url") == "latitude":
                        summary.lat = sub.get("valueDecimal")
                    elif sub.get("url") == "longitude":
                        summary.lon = sub.get("valueDecimal")

    # Telecom
    for tc in resource.get("telecom", []):
        if tc.get("system") == "phone":
            summary.phone = tc.get("value", "")

    # Marital status
    ms = resource.get("maritalStatus", {})
    ms_codings = ms.get("coding", [])
    if ms_codings:
        summary.marital_status = ms_codings[0].get("code", "")

    # Language
    comms = resource.get("communication", [])
    if comms:
        lang_cc = comms[0].get("language", {})
        lang_codings = lang_cc.get("coding", [])
        if lang_codings:
            summary.language = lang_codings[0].get("display", "")

    # Identifiers
    for ident in resource.get("identifier", []):
        type_codings = ident.get("type", {}).get("coding", [])
        type_code = type_codings[0].get("code", "") if type_codings else ""
        val = ident.get("value", "")
        if type_code == "MR":
            summary.mrn = val
        elif type_code == "SS":
            summary.ssn = val

    # Extensions — walk by URL, not position
    for ext in resource.get("extension", []):
        url = ext.get("url", "")

        if "us-core-race" in url:
            for sub in ext.get("extension", []):
                if sub.get("url") == "text":
                    summary.race = sub.get("valueString", "")

        elif "us-core-ethnicity" in url:
            for sub in ext.get("extension", []):
                if sub.get("url") == "text":
                    summary.ethnicity = sub.get("valueString", "")

        elif "us-core-birthsex" in url:
            summary.birth_sex = ext.get("valueCode", "")

        elif "patient-birthPlace" in url:
            addr = ext.get("valueAddress", {})
            parts = [addr.get("city", ""), addr.get("state", ""), addr.get("country", "")]
            summary.birth_place = ", ".join(p for p in parts if p)

        elif "patient-mothersMaidenName" in url:
            summary.mothers_maiden_name = ext.get("valueString", "")

        elif "disability-adjusted-life-years" in url:
            summary.daly = ext.get("valueDecimal")

        elif "quality-adjusted-life-years" in url:
            summary.qaly = ext.get("valueDecimal")

    return summary


def extract_encounter(resource: dict) -> EncounterRecord:
    enc = EncounterRecord()
    enc.encounter_id = resource.get("id", "")
    enc.status = resource.get("status", "")

    # Class code (AMB, IMP, EMER, etc.)
    cls = resource.get("class", {})
    enc.class_code = cls.get("code", "")

    # Encounter type
    types = resource.get("type", [])
    if types:
        codings = types[0].get("coding", [])
        if codings:
            enc.encounter_type = codings[0].get("display", "")
        if not enc.encounter_type:
            enc.encounter_type = types[0].get("text", "")

    # Reason
    reasons = resource.get("reasonCode", [])
    if reasons:
        codings = reasons[0].get("coding", [])
        if codings:
            enc.reason_display = codings[0].get("display", "")

    enc.period = get_period(resource)

    # Patient reference
    subject = resource.get("subject", {})
    enc.patient_id = strip_ref(subject.get("reference", ""))

    # Participant (practitioner)
    for participant in resource.get("participant", []):
        individual = participant.get("individual", {})
        display = individual.get("display", "")
        if display:
            enc.practitioner_name = display
            break

    # Service provider (organization)
    sp = resource.get("serviceProvider", {})
    enc.provider_org = sp.get("display", "")

    return enc


def extract_observation(resource: dict) -> ObservationRecord:
    obs = ObservationRecord()
    obs.obs_id = resource.get("id", "")
    obs.status = resource.get("status", "")

    # Patient + encounter references
    obs.patient_id = strip_ref(resource.get("subject", {}).get("reference", ""))
    obs.encounter_id = strip_ref(resource.get("encounter", {}).get("reference", "")) or None

    # Category
    categories = resource.get("category", [])
    if categories:
        cat_codings = categories[0].get("coding", [])
        if cat_codings:
            obs.category = cat_codings[0].get("code", "")

    # Code (LOINC)
    code_cc = resource.get("code", {})
    code_codings = code_cc.get("coding", [])
    if code_codings:
        obs.loinc_code = code_codings[0].get("code", "")
        obs.display = code_codings[0].get("display", "") or code_cc.get("text", "")
    else:
        obs.display = code_cc.get("text", "")

    # Effective time
    obs.effective_dt = parse_dt(resource.get("effectiveDateTime") or resource.get("effectivePeriod", {}).get("start"))

    # Value — handle all three cases
    if "valueQuantity" in resource:
        obs.value_type = "quantity"
        vq = resource["valueQuantity"]
        obs.value_quantity = vq.get("value")
        obs.value_unit = vq.get("unit") or vq.get("code", "")

    elif "valueCodeableConcept" in resource:
        obs.value_type = "codeable_concept"
        vcc = resource["valueCodeableConcept"]
        vcc_codings = vcc.get("coding", [])
        if vcc_codings:
            obs.value_concept_display = vcc_codings[0].get("display", "")
        if not obs.value_concept_display:
            obs.value_concept_display = vcc.get("text", "")

    elif "component" in resource:
        obs.value_type = "component"
        for comp in resource["component"]:
            c = ObservationComponent()
            comp_code = comp.get("code", {})
            comp_codings = comp_code.get("coding", [])
            if comp_codings:
                c.loinc_code = comp_codings[0].get("code", "")
                c.display = comp_codings[0].get("display", "")
            if "valueQuantity" in comp:
                vq = comp["valueQuantity"]
                c.value = vq.get("value")
                c.unit = vq.get("unit") or vq.get("code", "")
            elif "valueCodeableConcept" in comp:
                vcc = comp["valueCodeableConcept"]
                vcc_codings = vcc.get("coding", [])
                c.value_concept_display = vcc_codings[0].get("display", "") if vcc_codings else vcc.get("text", "")
            obs.components.append(c)

    else:
        obs.value_type = "none"

    return obs


def extract_condition(resource: dict) -> ConditionRecord:
    cond = ConditionRecord()
    cond.condition_id = resource.get("id", "")
    cond.patient_id = strip_ref(resource.get("subject", {}).get("reference", ""))
    cond.encounter_id = strip_ref(resource.get("encounter", {}).get("reference", "")) or None

    cond.clinical_status = get_status_code(resource, "clinicalStatus")
    cond.verification_status = get_status_code(resource, "verificationStatus")

    cond.code = get_codeable_concept(resource, "code")

    cond.onset_dt = parse_dt(resource.get("onsetDateTime") or resource.get("onsetPeriod", {}).get("start"))
    cond.abatement_dt = parse_dt(resource.get("abatementDateTime") or resource.get("abatementPeriod", {}).get("start"))
    cond.recorded_dt = parse_dt(resource.get("recordedDate"))

    cond.is_active = (cond.clinical_status == "active") and (cond.abatement_dt is None)

    return cond


def extract_medication(resource: dict) -> MedicationRecord:
    med = MedicationRecord()
    med.med_id = resource.get("id", "")
    med.patient_id = strip_ref(resource.get("subject", {}).get("reference", ""))
    med.encounter_id = strip_ref(resource.get("encounter", {}).get("reference", "")) or None
    med.status = resource.get("status", "")

    # Synthea uses medicationCodeableConcept; real EHR may use medicationReference
    if "medicationCodeableConcept" in resource:
        mcc = resource["medicationCodeableConcept"]
        codings = mcc.get("coding", [])
        if codings:
            med.rxnorm_code = codings[0].get("code", "")
            med.display = codings[0].get("display", "") or mcc.get("text", "")
        else:
            med.display = mcc.get("text", "")
    elif "medicationReference" in resource:
        # Real-world case — we don't resolve the reference here
        med.display = resource["medicationReference"].get("display", "")

    med.authored_on = parse_dt(resource.get("authoredOn"))

    requester = resource.get("requester", {})
    med.requester = requester.get("display", "")

    # Dosage
    dosages = resource.get("dosageInstruction", [])
    if dosages:
        med.as_needed = dosages[0].get("asNeededBoolean", False)
        med.dosage_text = dosages[0].get("text", "")

    # Reason
    reasons = resource.get("reasonCode", [])
    if reasons:
        codings = reasons[0].get("coding", [])
        if codings:
            med.reason_display = codings[0].get("display", "")

    return med


def extract_procedure(resource: dict) -> ProcedureRecord:
    proc = ProcedureRecord()
    proc.procedure_id = resource.get("id", "")
    proc.patient_id = strip_ref(resource.get("subject", {}).get("reference", ""))
    proc.encounter_id = strip_ref(resource.get("encounter", {}).get("reference", "")) or None
    proc.status = resource.get("status", "")
    proc.code = get_codeable_concept(resource, "code")

    if "performedPeriod" in resource:
        proc.performed_period = get_period(resource, "performedPeriod")
    elif "performedDateTime" in resource:
        dt = parse_dt(resource["performedDateTime"])
        proc.performed_period = Period(start=dt, end=dt)

    reasons = resource.get("reasonCode", [])
    if reasons:
        codings = reasons[0].get("coding", [])
        if codings:
            proc.reason_display = codings[0].get("display", "")

    return proc


def extract_diagnostic_report(resource: dict) -> DiagnosticReportRecord:
    report = DiagnosticReportRecord()
    report.report_id = resource.get("id", "")
    report.patient_id = strip_ref(resource.get("subject", {}).get("reference", ""))
    report.encounter_id = strip_ref(resource.get("encounter", {}).get("reference", "")) or None
    report.status = resource.get("status", "")

    # Category
    categories = resource.get("category", [])
    if categories:
        cat_codings = categories[0].get("coding", [])
        if cat_codings:
            report.category = cat_codings[0].get("code", "")

    report.code = get_codeable_concept(resource, "code")
    report.effective_dt = parse_dt(resource.get("effectiveDateTime") or resource.get("effectivePeriod", {}).get("start"))

    # Result references (observation UUIDs this report groups)
    for result in resource.get("result", []):
        ref = strip_ref(result.get("reference", ""))
        if ref:
            report.result_refs.append(ref)

    # Clinical note (presentedForm — present in real EHR exports, absent in Synthea)
    for form in resource.get("presentedForm", []):
        report.has_presented_form = True
        data = form.get("data", "")
        if data:
            try:
                report.presented_form_text = base64.b64decode(data).decode("utf-8", errors="replace")
            except Exception:
                report.presented_form_text = "[Could not decode clinical note]"
        break  # only take the first form

    return report


def extract_immunization(resource: dict) -> ImmunizationRecord:
    imm = ImmunizationRecord()
    imm.imm_id = resource.get("id", "")
    imm.patient_id = strip_ref(resource.get("patient", {}).get("reference", ""))
    imm.encounter_id = strip_ref(resource.get("encounter", {}).get("reference", "")) or None
    imm.status = resource.get("status", "")

    vcc = resource.get("vaccineCode", {})
    codings = vcc.get("coding", [])
    if codings:
        imm.cvx_code = codings[0].get("code", "")
        imm.display = codings[0].get("display", "") or vcc.get("text", "")
    else:
        imm.display = vcc.get("text", "")

    imm.occurrence_dt = parse_dt(resource.get("occurrenceDateTime"))

    return imm


def extract_allergy(resource: dict) -> AllergyRecord:
    allergy = AllergyRecord()
    allergy.allergy_id = resource.get("id", "")
    allergy.patient_id = strip_ref(resource.get("patient", {}).get("reference", ""))
    allergy.clinical_status = get_status_code(resource, "clinicalStatus")
    allergy.allergy_type = resource.get("type", "")
    allergy.categories = resource.get("category", [])
    allergy.criticality = resource.get("criticality", "")
    allergy.code = get_codeable_concept(resource, "code")
    allergy.onset_dt = parse_dt(resource.get("onsetDateTime"))
    allergy.recorded_date = parse_dt(resource.get("recordedDate"))
    return allergy


def extract_claim(resource: dict) -> ClaimRecord:
    claim = ClaimRecord()
    claim.claim_id = resource.get("id", "")
    claim.patient_id = strip_ref(resource.get("patient", {}).get("reference", ""))

    # Encounter reference lives inside item[].encounter[]
    items = resource.get("item", [])
    for item in items:
        for enc_ref in item.get("encounter", []):
            ref = strip_ref(enc_ref.get("reference", ""))
            if ref:
                claim.encounter_id = ref
                break
        if claim.encounter_id:
            break

    claim.billable_period = get_period(resource, "billablePeriod")

    total = resource.get("total", {})
    claim.total_billed = total.get("value")

    claim_type_codings = resource.get("type", {}).get("coding", [])
    if claim_type_codings:
        claim.claim_type = claim_type_codings[0].get("code", "")

    return claim


def extract_eob_insurer(resource: dict) -> str:
    """Extract the insurer name from an ExplanationOfBenefit's contained Coverage."""
    for contained in resource.get("contained", []):
        if contained.get("resourceType") == "Coverage":
            payor_refs = contained.get("payor", [])
            if payor_refs:
                return payor_refs[0].get("display", "")
    # Fallback: check insurer field directly
    return resource.get("insurer", {}).get("display", "")


def extract_eob_payment(resource: dict) -> float | None:
    """Extract the total payment amount from an EOB."""
    payment = resource.get("payment", {})
    amount = payment.get("amount", {})
    return amount.get("value")


def extract_imaging_study(resource: dict) -> ImagingStudyRecord:
    study = ImagingStudyRecord()
    study.study_id = resource.get("id", "")
    study.patient_id = strip_ref(resource.get("subject", {}).get("reference", ""))
    study.encounter_id = strip_ref(resource.get("encounter", {}).get("reference", "")) or None
    study.status = resource.get("status", "")
    study.started = parse_dt(resource.get("started"))
    study.description = resource.get("description", "")
    study.series_count = resource.get("numberOfSeries", 0)
    study.instance_count = resource.get("numberOfInstances", 0)

    # Modality from first series
    series = resource.get("series", [])
    if series:
        modality = series[0].get("modality", {})
        study.modality = modality.get("code", "")

    return study
