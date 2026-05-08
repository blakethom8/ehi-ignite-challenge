"""Score an extracted FHIR Bundle against a verified ground-truth Bundle.

Lighter-weight than lib/extract/eval.py — just per-resource-type F1 +
fact-agreement counts. Used by the lab CLI's auto-eval (EVAL-T01)."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field

from lib.extract.lab.compare import _extract_fact_keys


@dataclass(frozen=True)
class ResourceTypeScore:
    resource_type: str
    truth_count: int
    extracted_count: int
    overlap: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class GroundTruthEvalResult:
    weighted_f1: float
    per_resource: dict[str, ResourceTypeScore]
    truth_only: dict[str, list[dict]]   # samples
    extracted_only: dict[str, list[dict]]  # samples
    total_truth: int
    total_extracted: int
    total_overlap: int


def score_against_ground_truth(
    extracted: dict,
    ground_truth: dict,
    *,
    fact_sample_cap: int = 10,
) -> GroundTruthEvalResult:
    """Score an extracted Bundle against a ground-truth Bundle. Per-fact
    matching uses the same authoritative-coding logic as compare.py
    (LOINC for Observations, SNOMED for Conditions, NPI for Practitioners,
    etc., with normalized display fallback)."""
    truth_facts = _extract_fact_keys(ground_truth)
    extr_facts = _extract_fact_keys(extracted)

    all_types = sorted(set(truth_facts) | set(extr_facts))

    per_resource: dict[str, ResourceTypeScore] = {}
    truth_only: dict[str, list[dict]] = {}
    extracted_only: dict[str, list[dict]] = {}
    total_truth = 0
    total_extracted = 0
    total_overlap = 0
    weighted_f1_sum = 0.0
    weighted_f1_denom = 0

    for rt in all_types:
        t_keys = truth_facts.get(rt, {})
        e_keys = extr_facts.get(rt, {})
        common = set(t_keys) & set(e_keys)
        truth_count = len(t_keys)
        extracted_count = len(e_keys)
        overlap = len(common)

        precision = overlap / extracted_count if extracted_count else 0.0
        recall = overlap / truth_count if truth_count else 0.0
        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        per_resource[rt] = ResourceTypeScore(
            resource_type=rt,
            truth_count=truth_count,
            extracted_count=extracted_count,
            overlap=overlap,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
        )

        only_in_truth = list(set(t_keys) - common)[:fact_sample_cap]
        only_in_extr = list(set(e_keys) - common)[:fact_sample_cap]
        if only_in_truth:
            truth_only[rt] = [
                {"display": t_keys[k].display, "code": t_keys[k].code}
                for k in only_in_truth
            ]
        if only_in_extr:
            extracted_only[rt] = [
                {"display": e_keys[k].display, "code": e_keys[k].code}
                for k in only_in_extr
            ]

        total_truth += truth_count
        total_extracted += extracted_count
        total_overlap += overlap
        weighted_f1_sum += f1 * truth_count
        weighted_f1_denom += truth_count

    weighted_f1 = (
        weighted_f1_sum / weighted_f1_denom if weighted_f1_denom else 0.0
    )

    return GroundTruthEvalResult(
        weighted_f1=round(weighted_f1, 4),
        per_resource=per_resource,
        truth_only=truth_only,
        extracted_only=extracted_only,
        total_truth=total_truth,
        total_extracted=total_extracted,
        total_overlap=total_overlap,
    )
