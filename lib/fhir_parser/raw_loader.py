"""
Raw FHIR JSON loader.

Re-reads a FHIR bundle file and returns raw resource dicts partitioned by type.
This is intentionally separate from bundle_parser.py — it keeps raw JSON
available for display without doubling memory in the parsed PatientRecord.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_raw_resources(file_path: str | Path) -> dict[str, list[dict]]:
    """Load a FHIR bundle and return resources partitioned by resourceType.

    Args:
        file_path: Path to a FHIR R4 Bundle JSON file.

    Returns:
        Dict mapping resourceType strings to lists of raw resource dicts.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    buckets: dict[str, list[dict]] = {}
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "Unknown")
        buckets.setdefault(rtype, []).append(resource)

    return buckets


def summarize_raw_resource(resource_type: str, resource: dict) -> str:
    """Generate a one-line summary label for a raw FHIR resource.

    Used as expander titles when browsing raw JSON.
    """
    rid = resource.get("id", "")[:12]

    if resource_type == "Patient":
        names = resource.get("name", [{}])
        if names:
            given = " ".join(names[0].get("given", []))
            family = names[0].get("family", "")
            return f"{given} {family}".strip() or rid
        return rid

    if resource_type == "Encounter":
        class_code = resource.get("class", {}).get("code", "")
        enc_type = ""
        types = resource.get("type", [])
        if types:
            codings = types[0].get("coding", [])
            if codings:
                enc_type = codings[0].get("display", "")
        period = resource.get("period", {})
        start = (period.get("start", "") or "")[:10]
        parts = [start, enc_type, f"[{class_code}]" if class_code else ""]
        return " — ".join(p for p in parts if p) or rid

    if resource_type == "Condition":
        display = _get_code_display(resource)
        status = _get_nested_code(resource, "clinicalStatus")
        parts = [display, f"({status})" if status else ""]
        return " ".join(p for p in parts if p) or rid

    if resource_type == "MedicationRequest":
        med = resource.get("medicationCodeableConcept", {})
        display = ""
        if med:
            codings = med.get("coding", [])
            display = codings[0].get("display", "") if codings else med.get("text", "")
        status = resource.get("status", "")
        parts = [display, f"({status})" if status else ""]
        return " ".join(p for p in parts if p) or rid

    if resource_type == "Observation":
        display = _get_code_display(resource)
        value_str = _summarize_obs_value(resource)
        if display and value_str:
            return f"{display} = {value_str}"
        return display or rid

    if resource_type == "Procedure":
        display = _get_code_display(resource)
        period = resource.get("performedPeriod", {})
        dt = resource.get("performedDateTime", "")
        date_str = (period.get("start", "") or dt or "")[:10]
        parts = [display, f"({date_str})" if date_str else ""]
        return " ".join(p for p in parts if p) or rid

    if resource_type == "Immunization":
        vaccine = resource.get("vaccineCode", {})
        display = ""
        if vaccine:
            codings = vaccine.get("coding", [])
            display = codings[0].get("display", "") if codings else vaccine.get("text", "")
        dt = (resource.get("occurrenceDateTime", "") or "")[:10]
        parts = [display, f"({dt})" if dt else ""]
        return " ".join(p for p in parts if p) or rid

    if resource_type == "AllergyIntolerance":
        display = _get_code_display(resource)
        status = _get_nested_code(resource, "clinicalStatus")
        parts = [display, f"({status})" if status else ""]
        return " ".join(p for p in parts if p) or rid

    if resource_type == "DiagnosticReport":
        display = _get_code_display(resource)
        dt = (resource.get("effectiveDateTime", "") or "")[:10]
        parts = [display, f"({dt})" if dt else ""]
        return " ".join(p for p in parts if p) or rid

    if resource_type == "Claim":
        total = resource.get("total", {})
        amount = total.get("value", "") if total else ""
        period = resource.get("billablePeriod", {})
        start = (period.get("start", "") or "")[:10]
        parts = [f"${amount}" if amount else "", start]
        return " — ".join(p for p in parts if p) or rid

    if resource_type == "ExplanationOfBenefit":
        payment = resource.get("payment", {})
        amount = payment.get("amount", {}).get("value", "") if payment else ""
        return f"Payment: ${amount}" if amount else rid

    # Fallback for any other resource type
    display = _get_code_display(resource)
    return display or rid or resource_type


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_code_display(resource: dict) -> str:
    """Extract display text from a resource's primary code field."""
    code = resource.get("code", {})
    if not code:
        return ""
    codings = code.get("coding", [])
    if codings:
        return codings[0].get("display", "") or code.get("text", "")
    return code.get("text", "")


def _get_nested_code(resource: dict, field: str) -> str:
    """Extract the code value from a CodeableConcept status field."""
    cc = resource.get(field, {})
    if not cc:
        return ""
    codings = cc.get("coding", [])
    return codings[0].get("code", "") if codings else ""


def _summarize_obs_value(resource: dict) -> str:
    """Summarize an Observation's value as a short string."""
    vq = resource.get("valueQuantity")
    if vq:
        val = vq.get("value", "")
        unit = vq.get("unit", "")
        return f"{val} {unit}".strip()

    vc = resource.get("valueCodeableConcept")
    if vc:
        codings = vc.get("coding", [])
        if codings:
            return codings[0].get("display", "")
        return vc.get("text", "")

    vs = resource.get("valueString")
    if vs:
        return vs[:60]

    # Component observations (e.g., blood pressure)
    components = resource.get("component", [])
    if components:
        parts = []
        for comp in components[:3]:
            cdisplay = ""
            ccode = comp.get("code", {}).get("coding", [])
            if ccode:
                cdisplay = ccode[0].get("display", "")
            cvq = comp.get("valueQuantity", {})
            cval = cvq.get("value", "")
            cunit = cvq.get("unit", "")
            if cdisplay and cval:
                parts.append(f"{cdisplay}: {cval} {cunit}".strip())
        return " | ".join(parts)

    return ""
