"""compare_runs() — structured diff between two completed runs.

Reads run artifacts from two run directories and computes a
RunComparison capturing what changed: resource counts, fact
agreement, cost / latency delta, bundle-shape delta (if available).
"""

from __future__ import annotations

import json
import re
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
    fuzzy_match_count: dict[str, int] = field(default_factory=dict)  # per-resource-type Stage 2 match count


# ---------------------------------------------------------------------------
# Fuzzy-match helpers (PERF-T01)
# ---------------------------------------------------------------------------

_DISPLAY_STOPWORDS = frozenset({
    # Common English filler
    "the", "a", "an", "of", "in", "on", "at", "with", "and", "or", "to", "as", "is", "are",
    # Medical narrative adjectives that don't change identity
    "active", "known", "current", "no", "yes", "right", "left",
})


def _normalize_display_tokens(display: str | None) -> frozenset[str]:
    """Aggressive token-set normalization for display-text fuzzy matching.

    Lowercases, strips punctuation, collapses whitespace, tokenizes on
    spaces, drops stopwords. Returns a frozenset of remaining tokens.

    Note: drops "no" — risk of losing negation in narrative text. Acceptable
    for this eval-match use case where we're comparing same-meaning labels
    (e.g., "No Known Allergies" vs "No known active allergies"); both
    normalize to {allergies} which is what we want to match.
    """
    if not display:
        return frozenset()
    text = display.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [t for t in text.split() if t not in _DISPLAY_STOPWORDS and len(t) > 1]
    return frozenset(tokens)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class FactMatchResult:
    """Result of matching two fact lists with code-first + fuzzy-fallback."""
    overlap: int
    only_in_a: list[FactSample]
    only_in_b: list[FactSample]
    fuzzy_matches: int  # how many of the overlap came from Stage 2 fuzzy


def match_fact_lists(
    facts_a: dict[tuple, FactSample],
    facts_b: dict[tuple, FactSample],
    *,
    fuzzy_threshold: float = 0.5,
) -> FactMatchResult:
    """Two-stage match: code-first, then fuzzy display-token Jaccard.

    Stage 1: exact code match. Facts with matching (lowercase) code are
    paired; any tuple-key (display, code) where both sides share the same
    non-empty code counts as a match regardless of display variance.

    Stage 2: for unmatched facts, try Jaccard token-overlap on
    aggressively-normalized display. Threshold parameterized; default 0.5.
    Only code-less facts are eligible for Stage 2 — code-bearing facts that
    didn't match in Stage 1 have different authoritative identities and must
    not be fuzzy-matched on display text alone.

    A fact is matched at most once (no double-counting). The function
    returns counts plus sample lists of unmatched facts on each side
    (for later display in compare/eval reports).
    """
    # Build code → sample lookup
    by_code_a: dict[str, FactSample] = {}
    no_code_a: list[FactSample] = []
    for (disp_norm, code_norm), sample in facts_a.items():
        if code_norm:
            by_code_a[code_norm] = sample
        else:
            no_code_a.append(sample)
    by_code_b: dict[str, FactSample] = {}
    no_code_b: list[FactSample] = []
    for (disp_norm, code_norm), sample in facts_b.items():
        if code_norm:
            by_code_b[code_norm] = sample
        else:
            no_code_b.append(sample)

    # Stage 1: code matches
    common_codes = set(by_code_a) & set(by_code_b)
    matched_a_ids: set[int] = set()
    matched_b_ids: set[int] = set()
    overlap = 0
    for code in common_codes:
        matched_a_ids.add(id(by_code_a[code]))
        matched_b_ids.add(id(by_code_b[code]))
        overlap += 1

    # Unmatched residue — only code-less facts are eligible for Stage 2.
    # Code-bearing facts that didn't match in Stage 1 have different authoritative
    # identities and should NOT be fuzzy-matched on display text alone.
    residue_a_coded = [
        s for s in by_code_a.values()
        if id(s) not in matched_a_ids
    ]
    residue_b_coded = [
        s for s in by_code_b.values()
        if id(s) not in matched_b_ids
    ]
    residue_a = list(no_code_a)
    residue_b = list(no_code_b)

    # Stage 2: fuzzy match via Jaccard — code-less facts only
    fuzzy_matches = 0
    for sa in list(residue_a):
        tokens_a = _normalize_display_tokens(sa.display)
        if not tokens_a:
            continue
        best_score = 0.0
        best_b = None
        for sb in residue_b:
            score = _jaccard(tokens_a, _normalize_display_tokens(sb.display))
            if score > best_score:
                best_score = score
                best_b = sb
        if best_b is not None and best_score >= fuzzy_threshold:
            residue_a.remove(sa)
            residue_b.remove(best_b)
            overlap += 1
            fuzzy_matches += 1

    return FactMatchResult(
        overlap=overlap,
        only_in_a=residue_a_coded + residue_a,
        only_in_b=residue_b_coded + residue_b,
        fuzzy_matches=fuzzy_matches,
    )


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

    overlap, only_a, only_b, fuzzy_counts = _fact_diff(bundle_a, bundle_b, fact_sample_cap)

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
        fuzzy_match_count=fuzzy_counts,
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
) -> tuple[dict[str, int], dict[str, list[FactSample]], dict[str, list[FactSample]], dict[str, int]]:
    """Per-resource-type fact agreement using two-stage code-first + fuzzy matching.

    A "fact" is keyed by (normalized_display, code) where the code is from
    the most authoritative coding system per resource type (LOINC for
    Observations, SNOMED/ICD-10 for Conditions, RxNorm for Medications,
    CVX for Immunizations, etc.).

    Stage 1: exact code match — facts sharing the same non-empty code match
    regardless of display variance.
    Stage 2: Jaccard token-overlap on aggressively-normalized display text
    for facts unmatched after Stage 1.

    Returns (overlap_counts, only_in_a_samples, only_in_b_samples, fuzzy_counts).
    """
    facts_a = _extract_fact_keys(bundle_a)
    facts_b = _extract_fact_keys(bundle_b)

    overlap: dict[str, int] = {}
    only_a: dict[str, list[FactSample]] = {}
    only_b: dict[str, list[FactSample]] = {}
    fuzzy_counts: dict[str, int] = {}

    all_types = set(facts_a) | set(facts_b)
    for rt in sorted(all_types):
        keys_a = facts_a.get(rt, {})
        keys_b = facts_b.get(rt, {})
        result = match_fact_lists(keys_a, keys_b)
        overlap[rt] = result.overlap
        if result.only_in_a:
            only_a[rt] = result.only_in_a[:sample_cap]
        if result.only_in_b:
            only_b[rt] = result.only_in_b[:sample_cap]
        if result.fuzzy_matches:
            fuzzy_counts[rt] = result.fuzzy_matches
    return overlap, only_a, only_b, fuzzy_counts


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
