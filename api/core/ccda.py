"""C-CDA ingestion helpers for the harmonization layer.

This module is intentionally a narrow adapter boundary.  The fallback parser
extracts the patient anchor plus common Problems and Medications sections so
XML uploads can participate in harmonization now.  A full converter such as
Microsoft FHIR-Converter or cda2r4 can replace `convert_ccda_to_fhir_bundle`
without changing the harmonizer's source loading contract.
"""

from __future__ import annotations

import re
import json
import subprocess
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.settings import get_settings


HL7_V3_NS = "urn:hl7-org:v3"
SOURCE_TAG_SYSTEM = "https://ehi-atlas.example/fhir/source-kind"


@dataclass(frozen=True)
class CcdaIdentityCheck:
    status: str
    reason: str


def is_ccda_xml(path: Path) -> bool:
    if path.suffix.lower() != ".xml" or not path.exists():
        return False
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return False
    return _local_name(root.tag) == "ClinicalDocument"


def convert_ccda_to_fhir_bundle(path_str: str, source_id: str, *, mode: str = "auto") -> dict[str, Any]:
    """Convert one C-CDA XML file to a small FHIR R4 Bundle.

    Microsoft FHIR-Converter is preferred when configured.  The deterministic
    fallback is intentionally conservative and exists for local development and
    testability when the converter service/binary is not installed.
    """

    path = Path(path_str)
    root_template = _root_template_for_ccda(path)
    if mode == "fallback":
        bundle = _fallback_ccda_to_fhir_bundle(path, source_id)
        return _postprocess_converted_bundle(bundle, source_id, path)
    if mode not in {"auto", "microsoft"}:
        raise ValueError(f"Unsupported C-CDA conversion mode: {mode}")

    bundle = _try_microsoft_converter(path, root_template)
    if bundle is None and mode == "microsoft":
        raise RuntimeError("Microsoft FHIR Converter is not configured or did not return a FHIR Bundle.")
    if bundle is None:
        bundle = _fallback_ccda_to_fhir_bundle(path, source_id)
    return _postprocess_converted_bundle(bundle, source_id, path)


def _try_microsoft_converter(path: Path, root_template: str) -> dict[str, Any] | None:
    settings = get_settings()
    if settings.fhir_converter_url:
        return _convert_with_microsoft_api(path, root_template)
    if settings.fhir_converter_bin and settings.fhir_converter_template_dir:
        return _convert_with_microsoft_cli(path, root_template)
    return None


def is_converter_required() -> bool:
    return get_settings().fhir_converter_required


def _convert_with_microsoft_api(path: Path, root_template: str) -> dict[str, Any] | None:
    settings = get_settings()
    base_url = (settings.fhir_converter_url or "").rstrip("/")
    api_version = settings.fhir_converter_api_version
    timeout = settings.fhir_converter_timeout_seconds
    url = f"{base_url}/convertToFhir?api-version={api_version}"
    payload = {
        "InputDataFormat": "Ccda",
        "RootTemplateName": root_template,
        "InputDataString": path.read_text(encoding="utf-8"),
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = settings.fhir_converter_bearer_token
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        if is_converter_required():
            raise
        return None
    bundle = raw.get("result") if isinstance(raw, dict) else None
    return bundle if _is_fhir_bundle(bundle) else None


def _convert_with_microsoft_cli(path: Path, root_template: str) -> dict[str, Any] | None:
    settings = get_settings()
    converter_bin = settings.fhir_converter_bin
    template_dir = settings.fhir_converter_template_dir
    if not converter_bin or not template_dir:
        return None
    timeout = settings.fhir_converter_timeout_seconds
    with tempfile.TemporaryDirectory(prefix="ccda-convert-") as tmp:
        out = Path(tmp) / "bundle.json"
        cmd = [
            converter_bin,
            "convert",
            "-n",
            str(path),
            "-d",
            template_dir,
            "-f",
            str(out),
            "-r",
            root_template,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0 or not out.exists():
                if is_converter_required():
                    raise RuntimeError(result.stderr or result.stdout or "FHIR converter failed")
                return None
            bundle = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            if is_converter_required():
                raise
            return None
    return bundle if _is_fhir_bundle(bundle) else None


def _fallback_ccda_to_fhir_bundle(path: Path, source_id: str) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    patient = _extract_patient(root, source_id, path)
    document_id = _safe_id(f"{source_id}-document")
    document = {
        "resourceType": "DocumentReference",
        "id": document_id,
        "status": "current",
        "type": {"text": _document_title(root) or "C-CDA document"},
        "subject": {"reference": f"Patient/{patient['id']}"},
        "content": [{"attachment": {"contentType": "text/xml", "title": path.name}}],
        "meta": _source_meta(source_id),
    }
    resources: list[dict[str, Any]] = [patient, document]
    resources.extend(_extract_problems(root, source_id, patient["id"], document_id))
    resources.extend(_extract_medications(root, source_id, patient["id"], document_id))
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": resource} for resource in resources],
    }


def _postprocess_converted_bundle(bundle: dict[str, Any], source_id: str, path: Path) -> dict[str, Any]:
    """Normalize converter output into the harmonizer's source contract."""

    entries = bundle.setdefault("entry", [])
    patient_id = None
    has_document_reference = False
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        _tag_resource_as_ccda(resource, source_id)
        if resource.get("resourceType") == "Patient" and patient_id is None:
            patient_id = str(resource.get("id") or _safe_id(f"{source_id}-patient"))
            resource["id"] = patient_id
        if resource.get("resourceType") == "DocumentReference":
            has_document_reference = True

    if not has_document_reference:
        document_id = _safe_id(f"{source_id}-document")
        document: dict[str, Any] = {
            "resourceType": "DocumentReference",
            "id": document_id,
            "status": "current",
            "type": {"text": _document_title(ET.parse(path).getroot()) or "C-CDA document"},
            "content": [{"attachment": {"contentType": "text/xml", "title": path.name}}],
            "meta": _source_meta(source_id),
        }
        if patient_id:
            document["subject"] = {"reference": f"Patient/{patient_id}"}
        entries.append({"resource": document})
    return bundle


def _tag_resource_as_ccda(resource: dict[str, Any], source_id: str) -> None:
    meta = resource.setdefault("meta", {})
    tags = meta.setdefault("tag", [])
    if not isinstance(tags, list):
        meta["tag"] = tags = []
    tag = {"system": SOURCE_TAG_SYSTEM, "code": "ccda", "display": f"C-CDA source {source_id}"}
    if tag not in tags:
        tags.append(tag)


def _is_fhir_bundle(value: Any) -> bool:
    return isinstance(value, dict) and value.get("resourceType") == "Bundle" and isinstance(value.get("entry"), list)


def _root_template_for_ccda(path: Path) -> str:
    override = get_settings().fhir_converter_root_template
    if override:
        return override
    try:
        title = _document_title(ET.parse(path).getroot()).lower()
    except ET.ParseError:
        return "CCD"
    if "discharge" in title:
        return "DischargeSummary"
    if "consult" in title:
        return "ConsultationNote"
    if "history" in title and "physical" in title:
        return "HistoryandPhysical"
    if "operative" in title:
        return "OperativeNote"
    if "procedure" in title:
        return "ProcedureNote"
    if "progress" in title:
        return "ProgressNote"
    if "referral" in title or "transition of care" in title:
        return "ReferralNote"
    if "transfer" in title:
        return "TransferSummary"
    return "CCD"


def patient_identity_from_resource(patient: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(patient, dict):
        return {}
    name = _patient_name_parts(patient)
    identity = {
        "given": name["given"],
        "family": name["family"],
        "birthDate": str(patient.get("birthDate") or ""),
        "gender": str(patient.get("gender") or ""),
    }
    return {key: value for key, value in identity.items() if value}


def compare_patient_identity(
    baseline_patient: dict[str, Any] | None,
    candidate_patient: dict[str, Any] | None,
) -> CcdaIdentityCheck:
    """Return whether a converted C-CDA patient can merge into the baseline."""

    if not baseline_patient or not candidate_patient:
        return CcdaIdentityCheck("unknown", "Patient identity was not available for comparison.")

    base = patient_identity_from_resource(baseline_patient)
    cand = patient_identity_from_resource(candidate_patient)

    if base.get("birthDate") and cand.get("birthDate") and base["birthDate"] != cand["birthDate"]:
        return CcdaIdentityCheck("mismatch", "C-CDA birth date differs from the workspace patient.")
    if base.get("gender") and cand.get("gender") and base["gender"].lower() != cand["gender"].lower():
        return CcdaIdentityCheck("mismatch", "C-CDA gender differs from the workspace patient.")

    base_family = _norm_name(base.get("family"))
    cand_family = _norm_name(cand.get("family"))
    if base_family and cand_family and base_family != cand_family:
        return CcdaIdentityCheck("mismatch", "C-CDA family name differs from the workspace patient.")

    base_given = _norm_name(base.get("given"))
    cand_given = _norm_name(cand.get("given"))
    if base_given and cand_given and base_given[0] != cand_given[0]:
        return CcdaIdentityCheck("mismatch", "C-CDA given name differs from the workspace patient.")

    if not any(base.get(k) and cand.get(k) for k in ("birthDate", "family", "given")):
        return CcdaIdentityCheck("unknown", "Patient identity overlap is insufficient for automatic merge.")
    return CcdaIdentityCheck("match", "C-CDA patient identity matches available workspace patient fields.")


def _extract_patient(root: ET.Element, source_id: str, path: Path) -> dict[str, Any]:
    patient_el = _first(root, "recordTarget", "patientRole", "patient")
    role_el = _first(root, "recordTarget", "patientRole")
    patient_id = _safe_id(f"{source_id}-patient")
    patient: dict[str, Any] = {
        "resourceType": "Patient",
        "id": patient_id,
        "meta": _source_meta(source_id),
        "identifier": [{"system": f"ccda://{path.name}", "value": source_id}],
    }
    if role_el is not None:
        id_el = _child(role_el, "id")
        if id_el is not None and id_el.attrib.get("extension"):
            patient["identifier"].append(
                {
                    "system": id_el.attrib.get("root") or f"ccda://{path.name}",
                    "value": id_el.attrib["extension"],
                }
            )
    if patient_el is None:
        return patient

    name_el = _child(patient_el, "name")
    if name_el is not None:
        given = [_text(child) for child in name_el if _local_name(child.tag) == "given"]
        family = next((_text(child) for child in name_el if _local_name(child.tag) == "family"), "")
        patient["name"] = [{"given": [value for value in given if value], "family": family}]
    gender_el = _child(patient_el, "administrativeGenderCode")
    gender_code = (gender_el.attrib.get("code") if gender_el is not None else "") or ""
    if gender_code.upper() == "M":
        patient["gender"] = "male"
    elif gender_code.upper() == "F":
        patient["gender"] = "female"
    birth_el = _child(patient_el, "birthTime")
    birth_date = _ccda_date(birth_el.attrib.get("value") if birth_el is not None else None)
    if birth_date:
        patient["birthDate"] = birth_date
    return patient


def _extract_problems(root: ET.Element, source_id: str, patient_id: str, document_id: str) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for section in _sections(root):
        title = (_text(_child(section, "title")) or "").lower()
        code = _child(section, "code")
        section_code = code.attrib.get("code") if code is not None else None
        if "problem" not in title and section_code != "11450-4":
            continue
        for obs in _iter_local(section, "observation"):
            if _is_problem_status_observation(obs):
                continue
            value = _child(obs, "value")
            if value is None:
                continue
            display, code_value, system = _coded_value(value)
            if not display:
                continue
            resources.append(
                {
                    "resourceType": "Condition",
                    "id": _safe_id(f"{source_id}-condition-{len(resources) + 1}"),
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "clinicalStatus": {"text": "active"},
                    "code": _codeable(display, code_value, system),
                    "onsetDateTime": _effective_date(obs),
                    "evidence": [{"detail": [{"reference": f"DocumentReference/{document_id}"}]}],
                    "meta": _source_meta(source_id),
                }
            )
    return resources


def _extract_medications(root: ET.Element, source_id: str, patient_id: str, document_id: str) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for section in _sections(root):
        title = (_text(_child(section, "title")) or "").lower()
        code = _child(section, "code")
        section_code = code.attrib.get("code") if code is not None else None
        if "medication" not in title and section_code != "10160-0":
            continue
        for sa in _iter_local(section, "substanceAdministration"):
            material_code = None
            for manufactured in _iter_local(sa, "manufacturedMaterial"):
                material_code = _child(manufactured, "code")
                break
            display, code_value, system = _coded_value(material_code)
            if not display and material_code is not None:
                display = _referenced_original_text(section, material_code)
            if not display:
                text_el = _child(sa, "text")
                display = _referenced_original_text(section, text_el) or _text(text_el)
            if not display:
                continue
            status_el = _child(sa, "statusCode")
            resources.append(
                {
                    "resourceType": "MedicationRequest",
                    "id": _safe_id(f"{source_id}-medication-{len(resources) + 1}"),
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "status": (status_el.attrib.get("code") if status_el is not None else None) or "unknown",
                    "intent": "order",
                    "medicationCodeableConcept": _codeable(display, code_value, system),
                    "authoredOn": _effective_date(sa),
                    "supportingInformation": [{"reference": f"DocumentReference/{document_id}"}],
                    "meta": _source_meta(source_id),
                }
            )
    return resources


def _is_problem_status_observation(obs: ET.Element) -> bool:
    code = _child(obs, "code")
    if code is None:
        return False
    code_value = code.attrib.get("code")
    display = (code.attrib.get("displayName") or "").lower()
    return code_value == "33999-4" or display == "status"


def _sections(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == "section"]


def _iter_local(element: ET.Element, local_name: str):
    for child in element.iter():
        if _local_name(child.tag) == local_name:
            yield child


def _first(root: ET.Element, *path: str) -> ET.Element | None:
    current = root
    for part in path:
        current = _child(current, part)
        if current is None:
            return None
    return current


def _child(element: ET.Element, local_name: str) -> ET.Element | None:
    for child in element:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(" ".join(element.itertext()).split())


def _ccda_date(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value)
    if len(value) >= 8 and value[:8].isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return value


def _effective_date(element: ET.Element) -> str | None:
    effective = _child(element, "effectiveTime")
    if effective is None:
        return None
    if effective.attrib.get("value"):
        return _ccda_date(effective.attrib["value"])
    for child in effective:
        if _local_name(child.tag) == "low" and child.attrib.get("value"):
            return _ccda_date(child.attrib["value"])
    return None


def _coded_value(element: ET.Element | None) -> tuple[str, str | None, str | None]:
    if element is None:
        return "", None, None
    display = element.attrib.get("displayName")
    if display == "????":
        display = None
    code = element.attrib.get("code")
    system = element.attrib.get("codeSystemName") or element.attrib.get("codeSystem")
    if not display:
        for child in element:
            if _local_name(child.tag) == "translation":
                display = child.attrib.get("displayName")
                code = code or child.attrib.get("code")
                system = system or child.attrib.get("codeSystemName") or child.attrib.get("codeSystem")
                break
    return (display or _text(element), code, system)


def _referenced_original_text(section: ET.Element, element: ET.Element | None) -> str:
    if element is None:
        return ""
    for original_text in _iter_local(element, "originalText"):
        reference = _child(original_text, "reference")
        value = reference.attrib.get("value") if reference is not None else None
        if value and value.startswith("#"):
            return _content_text_by_id(section, value[1:])
    reference = _child(element, "reference")
    value = reference.attrib.get("value") if reference is not None else None
    if value and value.startswith("#"):
        return _content_text_by_id(section, value[1:])
    return ""


def _content_text_by_id(section: ET.Element, content_id: str) -> str:
    for content in _iter_local(section, "content"):
        if content.attrib.get("ID") == content_id or content.attrib.get("id") == content_id:
            return _text(content)
    return ""


def _codeable(display: str, code: str | None, system: str | None) -> dict[str, Any]:
    codeable: dict[str, Any] = {"text": display}
    if code:
        coding: dict[str, str] = {"code": code, "display": display}
        if system:
            coding["system"] = system
        codeable["coding"] = [coding]
    return codeable


def _source_meta(source_id: str) -> dict[str, Any]:
    return {"tag": [{"system": SOURCE_TAG_SYSTEM, "code": "ccda", "display": f"C-CDA source {source_id}"}]}


def _document_title(root: ET.Element) -> str:
    return _text(_child(root, "title"))


def _patient_name_parts(patient: dict[str, Any]) -> dict[str, str]:
    names = patient.get("name")
    if not isinstance(names, list) or not names:
        return {"given": "", "family": ""}
    name = names[0] if isinstance(names[0], dict) else {}
    given = name.get("given")
    return {
        "given": " ".join(str(value) for value in given) if isinstance(given, list) else "",
        "family": str(name.get("family") or ""),
    }


def _norm_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-")
    return cleaned[:64] or "ccda-resource"
