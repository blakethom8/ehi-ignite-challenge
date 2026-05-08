"""compare_runs() — structured diff between two completed runs.

Reads run artifacts from two run directories and computes a
RunComparison capturing what changed: resource counts, fact
agreement, cost / latency delta, bundle-shape delta (if available).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from lib.extract.lab.recorder import DEFAULT_LAB_ROOT


@dataclass(frozen=True)
class FactSample:
    """A short representation of one fact for the only-in-A / only-in-B lists."""
    resource_type: str
    display: str
    code: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class RunComparison:
    run_a_id: str
    run_b_id: str
    pipeline_a: str
    pipeline_b: str
    cost_delta_usd: float
    latency_delta_ms: int
    resource_counts_a: dict[str, int]
    resource_counts_b: dict[str, int]
    counts_delta: dict[str, int]               # b - a per resource type
    fact_overlap: dict[str, int]               # per resource type: count of facts both extracted
    fact_only_in_a: dict[str, list[FactSample]]
    fact_only_in_b: dict[str, list[FactSample]]
    bundle_shape_a: dict                       # populated from bundle_shape.json (LAB-T05); empty if absent
    bundle_shape_b: dict


def compare_runs(
    run_a_id: str,
    run_b_id: str,
    *,
    root: Path | None = None,
    fact_sample_cap: int = 10,
) -> RunComparison:
    """Diff two completed runs from `<root>/runs/<run-id>/`."""
    root = root or DEFAULT_LAB_ROOT
    a_dir = root / "runs" / run_a_id
    b_dir = root / "runs" / run_b_id

    if not a_dir.exists():
        raise FileNotFoundError(f"run not found: {run_a_id} ({a_dir})")
    if not b_dir.exists():
        raise FileNotFoundError(f"run not found: {run_b_id} ({b_dir})")

    manifest_a = json.loads((a_dir / "manifest.json").read_text())
    manifest_b = json.loads((b_dir / "manifest.json").read_text())
    bundle_a = json.loads((a_dir / "bundle.json").read_text()) if (a_dir / "bundle.json").exists() else {"entry": []}
    bundle_b = json.loads((b_dir / "bundle.json").read_text()) if (b_dir / "bundle.json").exists() else {"entry": []}

    counts_a = _count_by_type(bundle_a)
    counts_b = _count_by_type(bundle_b)
    all_types = sorted(set(counts_a) | set(counts_b))
    counts_delta = {t: counts_b.get(t, 0) - counts_a.get(t, 0) for t in all_types}

    overlap, only_a, only_b = _fact_diff(bundle_a, bundle_b, fact_sample_cap)

    bundle_shape_a = _read_optional_json(a_dir / "bundle_shape.json", default={})
    bundle_shape_b = _read_optional_json(b_dir / "bundle_shape.json", default={})

    return RunComparison(
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        pipeline_a=manifest_a.get("pipeline_name", "?"),
        pipeline_b=manifest_b.get("pipeline_name", "?"),
        cost_delta_usd=manifest_b.get("cost_usd", 0) - manifest_a.get("cost_usd", 0),
        latency_delta_ms=manifest_b.get("latency_ms", 0) - manifest_a.get("latency_ms", 0),
        resource_counts_a=counts_a,
        resource_counts_b=counts_b,
        counts_delta=counts_delta,
        fact_overlap=overlap,
        fact_only_in_a=only_a,
        fact_only_in_b=only_b,
        bundle_shape_a=bundle_shape_a,
        bundle_shape_b=bundle_shape_b,
    )


def _count_by_type(bundle: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in bundle.get("entry", []):
        rt = entry.get("resource", {}).get("resourceType", "Unknown")
        counts[rt] = counts.get(rt, 0) + 1
    return counts


def _fact_diff(
    bundle_a: dict,
    bundle_b: dict,
    sample_cap: int,
) -> tuple[dict[str, int], dict[str, list[FactSample]], dict[str, list[FactSample]]]:
    """Per-resource-type fact agreement.

    A "fact" is keyed by (resourceType, normalized_display, code) where the
    code is from the most authoritative coding system per resource type
    (LOINC for Observations, SNOMED/ICD-10 for Conditions, RxNorm for
    Medications, CVX for Immunizations, etc.).

    Returns (overlap_counts, only_in_a_samples, only_in_b_samples).
    """
    facts_a = _extract_fact_keys(bundle_a)
    facts_b = _extract_fact_keys(bundle_b)

    overlap: dict[str, int] = {}
    only_a: dict[str, list[FactSample]] = {}
    only_b: dict[str, list[FactSample]] = {}

    all_types = set(facts_a) | set(facts_b)
    for rt in sorted(all_types):
        keys_a = facts_a.get(rt, {})
        keys_b = facts_b.get(rt, {})
        common = set(keys_a) & set(keys_b)
        a_only = set(keys_a) - set(keys_b)
        b_only = set(keys_b) - set(keys_a)
        overlap[rt] = len(common)
        if a_only:
            only_a[rt] = [keys_a[k] for k in list(a_only)[:sample_cap]]
        if b_only:
            only_b[rt] = [keys_b[k] for k in list(b_only)[:sample_cap]]
    return overlap, only_a, only_b


def _extract_fact_keys(bundle: dict) -> dict[str, dict[tuple, FactSample]]:
    """For each resource, build a (display, code) key mapping to a FactSample.
    Returns: {resource_type: {key: FactSample}}."""
    by_type: dict[str, dict[tuple, FactSample]] = {}
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rt = resource.get("resourceType")
        if not rt:
            continue
        display, code = _display_and_code(rt, resource)
        if not display:
            continue
        key = (display.lower().strip(), (code or "").lower())
        sample = FactSample(
            resource_type=rt,
            display=display,
            code=code,
            value=_value_summary(resource),
        )
        by_type.setdefault(rt, {})[key] = sample
    return by_type


def _display_and_code(rt: str, resource: dict) -> tuple[str | None, str | None]:
    """Pick the most informative display + code per resource type."""
    if rt == "Observation":
        code = resource.get("code", {})
        text = code.get("text")
        codings = code.get("coding") or []
        for c in codings:
            if "loinc" in (c.get("system", "") or "").lower():
                return text or c.get("display"), c.get("code")
        if codings:
            return text or codings[0].get("display"), codings[0].get("code")
        return text, None
    if rt == "Condition":
        code = resource.get("code", {})
        text = code.get("text")
        codings = code.get("coding") or []
        # Prefer SNOMED, then ICD-10
        for sys in ("snomed.info/sct", "icd-10", "icd10"):
            for c in codings:
                if sys in (c.get("system", "") or "").lower():
                    return text or c.get("display"), c.get("code")
        if codings:
            return text or codings[0].get("display"), codings[0].get("code")
        return text, None
    if rt == "MedicationRequest":
        med = resource.get("medicationCodeableConcept", {})
        text = med.get("text")
        codings = med.get("coding") or []
        for c in codings:
            if "rxnorm" in (c.get("system", "") or "").lower():
                return text or c.get("display"), c.get("code")
        if codings:
            return text or codings[0].get("display"), codings[0].get("code")
        return text, None
    if rt == "Immunization":
        vc = resource.get("vaccineCode", {})
        text = vc.get("text")
        codings = vc.get("coding") or []
        for c in codings:
            if "cvx" in (c.get("system", "") or "").lower():
                return text or c.get("display"), c.get("code")
        if codings:
            return text or codings[0].get("display"), codings[0].get("code")
        return text, None
    if rt == "AllergyIntolerance":
        code = resource.get("code", {})
        text = code.get("text")
        codings = code.get("coding") or []
        if codings:
            return text or codings[0].get("display"), codings[0].get("code")
        return text, None
    if rt == "Patient":
        names = resource.get("name") or []
        if names:
            n = names[0]
            given = " ".join(n.get("given") or [])
            family = n.get("family") or ""
            return f"{given} {family}".strip() or n.get("text"), resource.get("id")
        return resource.get("id"), None
    if rt == "Encounter":
        type_list = resource.get("type") or []
        text = type_list[0].get("text") if type_list else None
        return text or resource.get("id"), resource.get("id")
    if rt == "Practitioner":
        names = resource.get("name") or []
        if names:
            n = names[0]
            given = " ".join(n.get("given") or [])
            family = n.get("family") or ""
            display = f"{given} {family}".strip() or n.get("text")
        else:
            display = resource.get("id")
        identifiers = resource.get("identifier") or []
        npi = next((i.get("value") for i in identifiers if "npi" in (i.get("system", "") or "").lower()), None)
        return display, npi
    if rt == "Organization":
        return resource.get("name"), resource.get("id")
    if rt == "DocumentReference":
        type_obj = resource.get("type") or {}
        codings = type_obj.get("coding") or []
        text = type_obj.get("text") or (codings[0].get("display") if codings else None)
        code = codings[0].get("code") if codings else None
        return text, code
    if rt == "Composition":
        return resource.get("title") or resource.get("id"), None
    # Default fallback
    return resource.get("id"), None


def _value_summary(resource: dict) -> str | None:
    """Short value summary for a fact sample. Used in markdown reports."""
    if "valueQuantity" in resource:
        vq = resource["valueQuantity"]
        return f"{vq.get('value')} {vq.get('unit', '')}".strip()
    if "valueString" in resource:
        return str(resource["valueString"])[:60]
    if "valueCodeableConcept" in resource:
        return resource["valueCodeableConcept"].get("text")
    return None


def _read_optional_json(path: Path, *, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return default
    return default
