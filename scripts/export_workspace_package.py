#!/usr/bin/env python3
"""Export a portable EHI Atlas evidence workspace package.

V1 is intentionally scripts-first and stdlib-only. It can package either:
- data/harmonize-demo/<collection> FHIR bundles (synthea-demo today)
- data/harmonization-runs/workspace-<collection>/latest.json plus aggregation uploads
- data/aggregation-uploads/<collection> extracted bundles/metadata

The output is a zip that can be inspected by humans, CLI tools, or external agents.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
import textwrap
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FHIR_TYPES = {
    "Observation",
    "Condition",
    "MedicationRequest",
    "MedicationStatement",
    "AllergyIntolerance",
    "Immunization",
    "Encounter",
    "Procedure",
    "DiagnosticReport",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return path.name



def ccda_date(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value)
    if len(value) >= 8 and value[:8].isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return value


def ccda_text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    text = " ".join(" ".join(el.itertext()).split())
    return text or None


def ccda_narrative_index(root: ET.Element) -> dict[str, str]:
    idx: dict[str, str] = {}
    for el in root.iter():
        key = el.attrib.get("ID") or el.attrib.get("id")
        if key:
            text = ccda_text(el)
            if text:
                idx[f"#{key}"] = text
    return idx


def ccda_ref_text(el: ET.Element | None, narrative: dict[str, str]) -> str | None:
    if el is None:
        return None
    for ref in el.iter():
        if ref.tag.endswith("reference") and ref.attrib.get("value") in narrative:
            return narrative[ref.attrib["value"]]
    return ccda_text(el)


def ccda_first_child(el: ET.Element, local_name: str) -> ET.Element | None:
    for child in el.iter():
        if child.tag.endswith(local_name):
            return child
    return None


def ccda_effective_date(el: ET.Element) -> str | None:
    effective = ccda_first_child(el, "effectiveTime")
    if effective is None:
        return None
    if effective.attrib.get("value"):
        return ccda_date(effective.attrib.get("value"))
    for child in effective:
        if child.tag.endswith("low") and child.attrib.get("value"):
            return ccda_date(child.attrib.get("value"))
    return None


def ccda_extract_resources(path: Path) -> list[dict[str, Any]]:
    """Lightweight C-CDA → FHIR-compatible facts for package demos.

    This is deliberately conservative: it extracts common Problems and
    Medications sections from public/sample C-CDA XML without claiming full CDA
    normalization. Full conversion can still use a dedicated FHIR converter.
    """
    root = ET.parse(path).getroot()
    narrative = ccda_narrative_index(root)
    resources: list[dict[str, Any]] = []
    patient_id = path.stem.replace(" ", "-")

    for section in root.iter():
        if not section.tag.endswith("section"):
            continue
        title_el = next((c for c in section if c.tag.endswith("title")), None)
        title = (ccda_text(title_el) or "").lower()
        code_el = next((c for c in section if c.tag.endswith("code")), None)
        section_code = code_el.attrib.get("code") if code_el is not None else None

        if "problem" in title or section_code == "11450-4":
            for obs in section.iter():
                if not obs.tag.endswith("observation"):
                    continue
                obs_code_el = next((c for c in obs if c.tag.endswith("code")), None)
                if obs_code_el is not None and obs_code_el.attrib.get("code") not in {None, "55607006"}:
                    continue
                value = next((c for c in obs if c.tag.endswith("value")), None)
                if value is None:
                    continue
                translations = [c for c in value if c.tag.endswith("translation")]
                display = value.attrib.get("displayName") or (translations[0].attrib.get("displayName") if translations else None)
                code = value.attrib.get("code") or (translations[0].attrib.get("code") if translations else None)
                system_name = value.attrib.get("codeSystemName") or (translations[0].attrib.get("codeSystemName") if translations else None)
                if not display:
                    display = ccda_ref_text(value, narrative)
                if not display:
                    continue
                resources.append({
                    "resourceType": "Condition",
                    "id": f"ccda-condition-{len(resources)+1}",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "clinicalStatus": {"text": "active"},
                    "code": {"text": display, "coding": ([{"code": code, "display": display, "system": system_name}] if code else [])},
                    "onsetDateTime": ccda_effective_date(obs),
                    "meta": {"source": f"ccda://{path.name}"},
                })

        if "medication" in title or section_code == "10160-0":
            for sa in section.iter():
                if not sa.tag.endswith("substanceAdministration"):
                    continue
                mat_code = None
                for el in sa.iter():
                    if el.tag.endswith("manufacturedMaterial"):
                        mat_code = next((c for c in el if c.tag.endswith("code")), None)
                        break
                display = None
                code = None
                system_name = None
                if mat_code is not None:
                    display = mat_code.attrib.get("displayName")
                    if display == "????":
                        display = None
                    code = mat_code.attrib.get("code")
                    system_name = mat_code.attrib.get("codeSystemName")
                    display = display or ccda_ref_text(mat_code, narrative)
                text_el = next((c for c in sa if c.tag.endswith("text")), None)
                display = display or ccda_ref_text(text_el, narrative)
                if not display:
                    continue
                status_el = next((c for c in sa if c.tag.endswith("statusCode")), None)
                resources.append({
                    "resourceType": "MedicationRequest",
                    "id": f"ccda-medication-{len(resources)+1}",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "status": (status_el.attrib.get("code") if status_el is not None else "unknown") or "unknown",
                    "intent": "order",
                    "medicationCodeableConcept": {"text": display, "coding": ([{"code": code, "display": display, "system": system_name}] if code else [])},
                    "authoredOn": ccda_effective_date(sa),
                    "meta": {"source": f"ccda://{path.name}"},
                })
    return resources


def bundle_entries(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for entry in bundle.get("entry", []) or []:
        res = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(res, dict):
            entries.append(res)
    return entries


def coding_display(codeable: dict[str, Any] | None) -> str | None:
    if not isinstance(codeable, dict):
        return None
    if codeable.get("text"):
        return str(codeable["text"])
    for coding in codeable.get("coding", []) or []:
        if coding.get("display"):
            return str(coding["display"])
        if coding.get("code"):
            return str(coding["code"])
    return None


def coding_code(codeable: dict[str, Any] | None) -> str | None:
    if not isinstance(codeable, dict):
        return None
    for coding in codeable.get("coding", []) or []:
        if coding.get("code"):
            return str(coding["code"])
    return None


def patient_display(patient: dict[str, Any] | None) -> str:
    if not patient:
        return "Synthetic Demo Patient"
    names = patient.get("name") or []
    if names:
        n = names[0]
        given = " ".join(n.get("given") or [])
        family = n.get("family") or ""
        full = " ".join(x for x in [given, family] if x).strip()
        if full:
            return full
    return patient.get("id") or "Synthetic Demo Patient"


def resource_date(res: dict[str, Any]) -> str | None:
    for key in [
        "effectiveDateTime",
        "effectiveInstant",
        "issued",
        "recordedDate",
        "onsetDateTime",
        "authoredOn",
        "date",
        "occurrenceDateTime",
        "performedDateTime",
    ]:
        if res.get(key):
            return str(res[key])
    period = res.get("effectivePeriod") or res.get("period")
    if isinstance(period, dict):
        return period.get("start") or period.get("end")
    return None


def resource_value(res: dict[str, Any]) -> str | None:
    q = res.get("valueQuantity")
    if isinstance(q, dict):
        val = q.get("value")
        unit = q.get("unit") or q.get("code") or ""
        return f"{val} {unit}".strip() if val is not None else None
    for key in ["valueString", "valueCodeableConcept", "valueBoolean", "valueInteger"]:
        if key in res:
            val = res[key]
            if key == "valueCodeableConcept":
                return coding_display(val)
            return str(val)
    return None


def resource_display(res: dict[str, Any]) -> str:
    rt = res.get("resourceType", "Resource")
    if rt == "Observation":
        return coding_display(res.get("code")) or res.get("id") or rt
    if rt == "Condition":
        return coding_display(res.get("code")) or res.get("id") or rt
    if rt in {"MedicationRequest", "MedicationStatement"}:
        return coding_display(res.get("medicationCodeableConcept")) or res.get("id") or rt
    if rt == "AllergyIntolerance":
        return coding_display(res.get("code")) or res.get("id") or rt
    if rt == "Immunization":
        return coding_display(res.get("vaccineCode")) or res.get("id") or rt
    if rt == "Encounter":
        return coding_display(res.get("type")) or res.get("class", {}).get("display") or res.get("id") or rt
    return coding_display(res.get("code")) or res.get("id") or rt


def fact_key(res: dict[str, Any]) -> str:
    rt = res.get("resourceType", "Resource")
    code = None
    if rt in {"MedicationRequest", "MedicationStatement"}:
        code = coding_code(res.get("medicationCodeableConcept")) or coding_display(res.get("medicationCodeableConcept"))
    elif rt == "Immunization":
        code = coding_code(res.get("vaccineCode")) or coding_display(res.get("vaccineCode"))
    else:
        code = coding_code(res.get("code")) or coding_display(res.get("code"))
    date = (resource_date(res) or "").split("T")[0]
    value = resource_value(res) or ""
    return "|".join([rt, str(code or resource_display(res)).lower(), date, value.lower()])


def safe_file_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def source_kind_for_path(path: Path) -> str:
    if path.suffix.lower() == ".xml":
        return "ccda-xml"
    if path.suffix.lower() == ".pdf":
        return "pdf-report"
    if path.suffix.lower() == ".json":
        return "fhir-bundle"
    return "source-file"


def _flatten_resources(resources_by_type: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for rows in resources_by_type.values():
        resources.extend(row for row in rows if isinstance(row, dict))
    return resources


def _original_for_source(kind: str, path: Path) -> Path | None:
    if kind == "ccda-xml":
        return path
    if kind == "extracted-pdf" and path.name.endswith(".extracted.json"):
        candidate = path.with_name(path.name.removesuffix(".extracted.json"))
        return candidate if candidate.exists() else None
    if path.suffix.lower() != ".json":
        return path
    return None


def discover_harmonize_sources(collection: str) -> list[dict[str, Any]] | None:
    """Prefer the API harmonize registry so exports match merged workspace state."""

    try:
        from api.core import harmonize_service
    except Exception:
        return None

    coll = harmonize_service.get_collection(collection)
    if coll is None:
        return None
    resources_by_source = harmonize_service.load_collection_resources(collection)
    sources: list[dict[str, Any]] = []
    for source in coll.sources:
        path = source.path
        sources.append(
            {
                "source_id": source.id,
                "label": source.label,
                "kind": source.kind,
                "path": path,
                "original_path": _original_for_source(source.kind, path),
                "document_reference": source.document_reference,
                "resources": _flatten_resources(resources_by_source.get(source.id, {})),
                "demo_source": "synthea" in collection.lower() or "harmonize-demo" in str(path),
            }
        )
    return sources


def discover_sources(collection: str) -> list[dict[str, Any]]:
    harmonize_sources = discover_harmonize_sources(collection)
    if harmonize_sources is not None:
        if not harmonize_sources:
            raise SystemExit(f"No packageable sources found for collection '{collection}'")
        return harmonize_sources

    sources: list[dict[str, Any]] = []

    demo_dir = REPO_ROOT / "data" / "harmonize-demo" / collection
    if demo_dir.exists():
        for path in sorted(list(demo_dir.glob("*.json")) + list(demo_dir.glob("*.xml"))):
            sources.append(
                {
                    "source_id": path.stem,
                    "label": path.name,
                    "kind": source_kind_for_path(path),
                    "path": path,
                    "original_path": path if path.suffix.lower() != ".json" else None,
                    "demo_source": True,
                }
            )

    uploads_dir = REPO_ROOT / "data" / "aggregation-uploads" / collection
    if uploads_dir.exists():
        for meta in sorted(uploads_dir.glob("*.metadata.json")):
            metadata = read_json(meta)
            file_id = metadata.get("file_id") or meta.name.split(".")[0]
            extracted = next(iter(uploads_dir.glob(f"{file_id}-*.extracted.json")), None)
            original = Path(metadata.get("storage_path", "")) if metadata.get("storage_path") else None
            if original and not original.exists():
                original = uploads_dir / original.name
            sources.append(
                {
                    "source_id": f"upload-{file_id}",
                    "label": metadata.get("file_name") or file_id,
                    "kind": metadata.get("data_type") or metadata.get("content_type") or "upload",
                    "path": extracted or original or meta,
                    "metadata_path": meta,
                    "original_path": original if original and original.exists() else None,
                    "metadata": metadata,
                    "demo_source": "synthetic" in json.dumps(metadata).lower() or "smoke" in collection,
                }
            )

    if not sources and not collection.startswith("workspace-"):
        sources.extend(discover_sources(f"workspace-{collection}"))

    if not sources:
        raise SystemExit(f"No packageable sources found for collection '{collection}'")
    return sources


def load_harmonization(collection: str) -> dict[str, Any] | None:
    candidates = [
        REPO_ROOT / "data" / "harmonization-runs" / collection / "latest.json",
        REPO_ROOT / "data" / "harmonization-runs" / f"workspace-{collection}" / "latest.json",
    ]
    for path in candidates:
        if path.exists():
            return read_json(path)
    return None


def source_bundle(source: dict[str, Any]) -> dict[str, Any] | None:
    path = source.get("path")
    if not isinstance(path, Path) or not path.exists() or path.suffix.lower() != ".json":
        return None
    try:
        data = read_json(path)
    except Exception:
        return None
    if data.get("resourceType") == "Bundle":
        return data
    return None


def build_evidence(collection: str, sources: list[dict[str, Any]], harmonization: dict[str, Any] | None) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    fhir_entries: list[dict[str, Any]] = []
    patient = None
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for source in sources:
        bundle = source_bundle(source)
        resources_for_source: list[dict[str, Any]] = []
        if isinstance(source.get("resources"), list):
            resources_for_source = [res for res in source["resources"] if isinstance(res, dict)]
        elif bundle:
            resources_for_source = bundle_entries(bundle)
        elif source.get("kind") == "ccda-xml" and isinstance(source.get("path"), Path):
            try:
                resources_for_source = ccda_extract_resources(source["path"])
            except Exception as exc:  # keep package export resilient; source remains inventoried
                resources_for_source = []
        if not resources_for_source:
            continue
        for res in resources_for_source:
            if res.get("resourceType") == "Patient" and patient is None:
                patient = res
            if res.get("resourceType") in FHIR_TYPES:
                grouped[fact_key(res)].append({"resource": res, "source": source})
                fhir_entries.append({"resource": res})

    for idx, (key, items) in enumerate(sorted(grouped.items()), start=1):
        first = items[0]["resource"]
        rt = first.get("resourceType", "Resource")
        fact_id = f"fact-{idx:04d}-{rt.lower()}"
        source_refs = []
        prov_refs = []
        for j, item in enumerate(items, start=1):
            res = item["resource"]
            src = item["source"]
            src_ref = f"{src['source_id']}:{rt}/{res.get('id', j)}"
            prov_id = f"prov-{idx:04d}-{j:02d}"
            source_refs.append(src_ref)
            prov_refs.append(prov_id)
            provenance.append(
                {
                    "provenance_id": prov_id,
                    "fact_id": fact_id,
                    "source_id": src["source_id"],
                    "source_label": src["label"],
                    "resource_ref": f"{rt}/{res.get('id', j)}",
                    "locator": src_ref,
                    "method": "fhir-bundle-import" if src["kind"] == "fhir-bundle" else "prepared-upload-import",
                    "confidence": "source-structured" if src["kind"] == "fhir-bundle" else "prepared-extraction",
                }
            )
        facts.append(
            {
                "fact_id": fact_id,
                "resource_type": rt,
                "display": resource_display(first),
                "date": resource_date(first),
                "value": resource_value(first),
                "status": first.get("status") or first.get("clinicalStatus", {}).get("text") or "accepted",
                "code": coding_code(first.get("code")) or coding_code(first.get("medicationCodeableConcept")) or coding_code(first.get("vaccineCode")),
                "source_refs": source_refs,
                "provenance_refs": prov_refs,
                "source_count": len({item["source"]["source_id"] for item in items}),
                "review_state": "auto_accepted" if len(items) == 1 else "cross_source_matched",
            }
        )

    # If a previous harmonization run exists, carry its candidate summaries too.
    candidate_record = harmonization.get("candidate_record") if harmonization else None
    if isinstance(candidate_record, dict):
        for kind, rows in candidate_record.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                fact_id = f"harmonized-{kind}-{len(facts)+1:04d}"
                source_refs = [s.get("source_observation_ref") or s.get("source_label") for s in row.get("sources", []) if isinstance(s, dict)]
                facts.append(
                    {
                        "fact_id": fact_id,
                        "resource_type": kind.rstrip("s").title(),
                        "display": row.get("canonical_name") or row.get("name") or row.get("merged_ref") or kind,
                        "date": (row.get("latest") or {}).get("effective_date"),
                        "value": f"{(row.get('latest') or {}).get('value')} {(row.get('latest') or {}).get('unit', '')}".strip(),
                        "status": "accepted",
                        "code": row.get("loinc_code") or row.get("rxnorm_code"),
                        "source_refs": source_refs,
                        "provenance_refs": [],
                        "source_count": row.get("source_count"),
                        "measurement_count": row.get("measurement_count"),
                        "review_state": "harmonized_candidate",
                    }
                )

    source_contributions = []
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        for ref in fact.get("source_refs", []) or []:
            source_id = str(ref).split(":", 1)[0]
            by_source[source_id].append(fact)
    for source in sources:
        rows = by_source.get(source["source_id"], [])
        counts = Counter(row["resource_type"] for row in rows)
        source_contributions.append(
            {
                "source_id": source["source_id"],
                "source_label": source["label"],
                "kind": source["kind"],
                "fact_count": len(rows),
                "resource_counts": dict(sorted(counts.items())),
                "unique_fact_ids": [row["fact_id"] for row in rows if row.get("source_count") in (None, 1)],
                "shared_fact_ids": [row["fact_id"] for row in rows if (row.get("source_count") or 0) > 1],
            }
        )

    conflicts = []
    if harmonization and harmonization.get("review_items"):
        conflicts = harmonization["review_items"]
    else:
        # Conservative V1: only flag exact same resource/date/display with different values.
        value_groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for fact in facts:
            value_groups[(fact["resource_type"], str(fact.get("display")), str(fact.get("date")))].add(str(fact.get("value")))
        for (rt, display, date), values in value_groups.items():
            clean = {v for v in values if v not in {"None", ""}}
            if len(clean) > 1:
                conflicts.append({"resource_type": rt, "display": display, "date": date, "values": sorted(clean), "review_reason": "same concept/date has multiple values"})

    counts = Counter(f["resource_type"] for f in facts)
    missing = []
    for rt, label in [("AllergyIntolerance", "allergy list"), ("MedicationRequest", "active medication list"), ("Condition", "problem list"), ("Observation", "recent labs/vitals")]:
        if counts.get(rt, 0) == 0:
            missing.append({"kind": rt, "message": f"No {label} facts found in packaged sources.", "severity": "informational"})

    return {
        "patient": patient,
        "patient_display": patient_display(patient),
        "facts": facts,
        "provenance": provenance,
        "source_contributions": source_contributions,
        "conflicts": conflicts,
        "missing_information": missing,
        "fhir_bundle": {"resourceType": "Bundle", "type": "collection", "entry": fhir_entries},
        "summary": {"fact_count": len(facts), "resource_counts": dict(sorted(counts.items())), "source_count": len(sources), "conflict_count": len(conflicts), "missing_information_count": len(missing)},
    }


def markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = ["| " + " | ".join(str(c).replace("\n", " ") for c in row) + " |" for row in rows[1:]]
    return "\n".join([header, sep] + body)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def package_cli_text() -> str:
    return r'''#!/usr/bin/env python3
"""Tiny CLI for an unpacked EHI Atlas workspace package."""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text())

def cmd_manifest(args):
    print(json.dumps(load('MANIFEST.json'), indent=2))

def cmd_sources(args):
    for s in load('sources/sources.json')['sources']:
        print(f"{s['source_id']}\t{s.get('kind','')}\t{s.get('label','')}")

def cmd_facts(args):
    facts = load('evidence/canonical-facts.json')['facts']
    q = (args.search or '').lower()
    typ = args.type
    for f in facts:
        if typ and f.get('resource_type') != typ: continue
        hay = json.dumps(f).lower()
        if q and q not in hay: continue
        print(f"{f['fact_id']}\t{f.get('resource_type','')}\t{f.get('date','')}\t{f.get('display','')}\t{f.get('value','')}")

def cmd_provenance(args):
    for p in load('evidence/provenance.json')['provenance']:
        if p.get('fact_id') == args.fact_id or p.get('provenance_id') == args.fact_id:
            print(json.dumps(p, indent=2))

def cmd_conflicts(args):
    print(json.dumps(load('evidence/conflicts.json'), indent=2))

def cmd_missing(args):
    print(json.dumps(load('evidence/missing-information.json'), indent=2))

def cmd_packet(args):
    name = args.name if args.name.endswith('.context.json') else f"{args.name}.context.json"
    print((ROOT / 'packets' / name).read_text())

def main():
    ap = argparse.ArgumentParser(description='Inspect an EHI Atlas workspace package')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('manifest').set_defaults(func=cmd_manifest)
    sub.add_parser('sources').set_defaults(func=cmd_sources)
    p = sub.add_parser('facts'); p.add_argument('--type'); p.add_argument('--search'); p.set_defaults(func=cmd_facts)
    p = sub.add_parser('provenance'); p.add_argument('fact_id'); p.set_defaults(func=cmd_provenance)
    sub.add_parser('conflicts').set_defaults(func=cmd_conflicts)
    sub.add_parser('missing').set_defaults(func=cmd_missing)
    p = sub.add_parser('packet'); p.add_argument('name'); p.set_defaults(func=cmd_packet)
    args = ap.parse_args(); args.func(args)
if __name__ == '__main__': main()
'''


def build_package(collection: str, out: Path, include_originals: bool) -> Path:
    sources = discover_sources(collection)
    harmonization = load_harmonization(collection)
    evidence = build_evidence(collection, sources, harmonization)
    package_id = f"ehi-atlas-workspace-{collection}-{datetime.now().strftime('%Y%m%d')}"
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="atlas-package-") as tmp:
        root = Path(tmp) / package_id
        root.mkdir()

        source_records = []
        for src in sources:
            path = src.get("path")
            record = {
                "source_id": src["source_id"],
                "label": src["label"],
                "kind": src["kind"],
                "demo_source": bool(src.get("demo_source")),
            }
            if isinstance(path, Path) and path.exists():
                record.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path), "packaged_path": f"sources/prepared/{path.name}" if path.suffix.lower() == ".json" else None})
                if path.suffix.lower() == ".json":
                    safe_file_copy(path, root / "sources" / "prepared" / path.name)
            if (include_originals or src.get("kind") == "ccda-xml") and isinstance(src.get("original_path"), Path):
                orig = src["original_path"]
                if orig.exists():
                    safe_file_copy(orig, root / "sources" / "original" / orig.name)
                    record["original_packaged_path"] = f"sources/original/{orig.name}"
            source_records.append(record)

        manifest_files = [
            "README.md",
            "MANIFEST.json",
            "PATIENT-SUMMARY.md",
            "AGENT-INSTRUCTIONS.md",
            "sources/sources.json",
            "evidence/canonical-facts.json",
            "evidence/provenance.json",
            "evidence/source-contributions.json",
            "evidence/conflicts.json",
            "evidence/missing-information.json",
            "fhir/harmonized-bundle.json",
            "packets/second-opinion.context.json",
            "exports/clinician-handoff.md",
            "exports/labs.csv",
            "cli/atlas_workspace.py",
        ]
        manifest = {
            "package_version": "atlas-workspace.v1",
            "workspace_id": collection,
            "created_at": now_iso(),
            "patient": {"display": evidence["patient_display"], "source": "synthetic/demo" if any(s.get("demo_source") for s in sources) else "workspace"},
            "source_count": len(sources),
            "canonical_fact_count": evidence["summary"]["fact_count"],
            "review_item_count": len(evidence["conflicts"]),
            "summary": evidence["summary"],
            "files": [{"path": p} for p in manifest_files],
            "privacy": {"contains_phi": not all(s.get("demo_source") for s in sources), "demo_data": all(s.get("demo_source") for s in sources), "sharing_warning": "Review before sharing outside your care team."},
        }

        (root / "README.md").write_text(textwrap.dedent(f"""
        # EHI Atlas Portable Workspace — {collection}

        This package is a patient-owned evidence workspace. It is designed to be inspected by humans and used by tools. It is not a replacement for clinical judgment.

        ## What is included

        - Source inventory and prepared source bundles
        - Canonical clinical facts
        - Provenance and source contribution maps
        - Conflicts and missing-information signals
        - Agent-ready context packets
        - Clinician/patient exports
        - A tiny CLI for local inspection

        ## Quick start

        ```bash
        python cli/atlas_workspace.py manifest
        python cli/atlas_workspace.py sources
        python cli/atlas_workspace.py facts --type Observation
        python cli/atlas_workspace.py missing
        python cli/atlas_workspace.py packet second-opinion
        ```

        ## Privacy

        Demo data: `{manifest['privacy']['demo_data']}`. Contains PHI flag: `{manifest['privacy']['contains_phi']}`.
        Review all contents before sharing.
        """).lstrip())

        (root / "AGENT-INSTRUCTIONS.md").write_text(textwrap.dedent("""
        # Instructions for agents using this package

        1. Read `MANIFEST.json` first.
        2. Prefer structured evidence in `evidence/` and `packets/` before inspecting raw/prepared source files.
        3. Cite `source_refs` or `provenance_refs` for important clinical claims.
        4. Use `evidence/missing-information.json` to disclose gaps.
        5. Use `evidence/conflicts.json` to disclose unresolved or ambiguous facts.
        6. Do not invent unsupported clinical facts.
        7. If raw files are included, use them to verify or investigate; do not discard the structured evidence layer.
        8. This is not medical advice. Recommend clinician review for medical decisions.
        """).lstrip())

        top_facts = sorted(evidence["facts"], key=lambda f: (str(f.get("date") or ""), f["resource_type"], f["display"]), reverse=True)[:12]
        rows = [["Type", "Date", "Fact", "Value", "Sources"]] + [[f["resource_type"], str(f.get("date") or ""), str(f.get("display") or ""), str(f.get("value") or ""), str(len(f.get("source_refs") or []))] for f in top_facts]
        (root / "PATIENT-SUMMARY.md").write_text(textwrap.dedent(f"""
        # Patient Summary

        **Patient:** {evidence['patient_display']}  
        **Workspace:** {collection}  
        **Sources:** {len(sources)}  
        **Canonical facts:** {evidence['summary']['fact_count']}  
        **Review items/conflicts:** {len(evidence['conflicts'])}

        ## Recent / representative facts

        {markdown_table(rows)}

        ## Missing information signals

        {chr(10).join('- ' + item['message'] for item in evidence['missing_information']) or '- No missing-information signals generated by V1.'}

        ## Notes

        This summary is generated from structured package evidence. It should be reviewed by a clinician before medical use.
        """).lstrip())

        write_json(root / "MANIFEST.json", manifest)
        write_json(root / "sources" / "sources.json", {"sources": source_records})
        write_json(root / "evidence" / "canonical-facts.json", {"facts": evidence["facts"]})
        write_json(root / "evidence" / "provenance.json", {"provenance": evidence["provenance"]})
        write_json(root / "evidence" / "source-contributions.json", {"source_contributions": evidence["source_contributions"]})
        write_json(root / "evidence" / "conflicts.json", {"conflicts": evidence["conflicts"]})
        write_json(root / "evidence" / "missing-information.json", {"missing_information": evidence["missing_information"]})
        write_json(root / "fhir" / "harmonized-bundle.json", evidence["fhir_bundle"])

        packet = {
            "packet_version": "atlas-context.v1",
            "purpose": "second-opinion",
            "audience": "clinician_or_agent",
            "workspace_id": collection,
            "instructions": [
                "Use only facts in this packet unless explicitly asked to inspect source files.",
                "Cite source_refs or provenance_refs for important claims.",
                "Mention relevant missing_information and conflicts.",
                "Do not provide unsupported medical advice.",
            ],
            "summary": evidence["summary"],
            "facts": evidence["facts"][:200],
            "provenance": evidence["provenance"][:200],
            "missing_information": evidence["missing_information"],
            "conflicts": evidence["conflicts"],
        }
        write_json(root / "packets" / "second-opinion.context.json", packet)

        handoff_rows = [["Type", "Date", "Fact", "Value", "Evidence"]] + [[f["resource_type"], str(f.get("date") or ""), str(f.get("display") or ""), str(f.get("value") or ""), ", ".join((f.get("provenance_refs") or f.get("source_refs") or [])[:3])] for f in top_facts]
        (root / "exports" / "clinician-handoff.md").parent.mkdir(parents=True, exist_ok=True)
        (root / "exports" / "clinician-handoff.md").write_text("# Clinician Handoff\n\n" + markdown_table(handoff_rows) + "\n\n## Gaps / review items\n\n" + ("\n".join(f"- {m['message']}" for m in evidence["missing_information"]) or "- None generated by V1.") + "\n")
        lab_rows = [f for f in evidence["facts"] if f["resource_type"] == "Observation"]
        write_csv(root / "exports" / "labs.csv", lab_rows, ["fact_id", "resource_type", "date", "display", "value", "code", "review_state"])

        cli_path = root / "cli" / "atlas_workspace.py"
        cli_path.parent.mkdir(parents=True, exist_ok=True)
        cli_path.write_text(package_cli_text())
        cli_path.chmod(0o755)

        if out.exists():
            out.unlink()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(root.parent))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Export a portable EHI Atlas workspace package")
    ap.add_argument("--collection", required=True, help="Collection/workspace id, e.g. synthea-demo or smoke-codex-upload-2026")
    ap.add_argument("--out", required=True, type=Path, help="Output zip path")
    ap.add_argument("--include-originals", action="store_true", help="Include original uploaded source files when available")
    args = ap.parse_args()
    out = build_package(args.collection, args.out, args.include_originals)
    print(out)


if __name__ == "__main__":
    main()
