"""Deterministic clinical QA components used as the first evaluation fixture."""

from __future__ import annotations

from collections import Counter
from typing import Any

from lib.extract.lab.evaluations.models import (
    ClinicalAnswer,
    ClinicalContext,
    ClinicalQATestCase,
    EvaluationSuite,
    EvidenceCitation,
    QuestionGrade,
)


RENAL_TEST_ID = "renal-impairment-medication-surgery"
RENAL_CODES = {"2160-0", "33914-3", "62238-1", "3094-0"}
RENAL_NAME_TOKENS = ("creatinine", "egfr", "e-gfr", "gfr", "bun", "urea nitrogen")


DEFAULT_CLINICAL_QA_SUITE = EvaluationSuite(
    suite_id="clinical-qa-smoke-v1",
    name="Clinical QA smoke suite",
    description=(
        "A deterministic downstream usefulness check. It asks whether the "
        "extracted Bundle supports one safety-critical renal impairment answer."
    ),
    version="1.0.0",
    test_cases=[
        ClinicalQATestCase(
            test_id=RENAL_TEST_ID,
            title="Renal impairment relevant to medication dosing or surgery",
            clinical_question=(
                "Does this patient have renal impairment relevant to medication "
                "dosing or surgery? Answer only from extracted evidence and cite "
                "the supporting facts."
            ),
            expected_answer=(
                "If renal labs indicate impaired kidney function, answer yes and "
                "cite creatinine, eGFR, or BUN. If those facts are absent, abstain."
            ),
            grading_rubric=(
                "Credit answers that make the renal dosing/surgery implication clear, "
                "cite facts present in the Bundle, avoid unsupported diagnoses, and "
                "abstain when renal evidence is insufficient."
            ),
            required_evidence_types=["Observation"],
            ideal_citations=["Creatinine", "eGFR", "BUN"],
            expected_supporting_facts=["creatinine high", "eGFR low", "BUN high"],
            safety_critical=True,
            abstention_allowed=True,
        )
    ],
)


class FhirBundleContextBuilder:
    """Build a compact evidence index from the emitted FHIR Bundle."""

    name = "fhir-bundle-evidence-index-v1"

    def build_context(self, bundle: dict[str, Any]) -> ClinicalContext:
        resources = [
            entry.get("resource") or {}
            for entry in bundle.get("entry", []) or []
            if isinstance(entry, dict)
        ]
        resource_counts = Counter(str(resource.get("resourceType") or "Unknown") for resource in resources)
        observations = [resource for resource in resources if resource.get("resourceType") == "Observation"]
        evidence = [
            _resource_to_evidence(resource, index)
            for index, resource in enumerate(resources, start=1)
            if resource.get("resourceType")
            in {"Observation", "Condition", "MedicationRequest", "Encounter", "DiagnosticReport", "DocumentReference"}
        ]
        lab_like_count = sum(1 for observation in observations if _is_lab_like_observation(observation))
        return ClinicalContext(
            context_builder=self.name,
            bundle_stats={
                "total_entries": len(bundle.get("entry", []) or []),
                "resource_counts": dict(resource_counts),
                "observation_count": resource_counts.get("Observation", 0),
                "lab_like_observation_count": lab_like_count,
                "condition_count": resource_counts.get("Condition", 0),
                "medication_request_count": resource_counts.get("MedicationRequest", 0),
                "encounter_count": resource_counts.get("Encounter", 0),
                "diagnostic_report_count": resource_counts.get("DiagnosticReport", 0),
                "document_reference_count": resource_counts.get("DocumentReference", 0),
            },
            evidence=evidence,
            notes=[
                "Context is built only from the pipeline output Bundle.",
                "No source PDF or ground truth is consulted by this deterministic smoke suite.",
            ],
        )


class DeterministicClinicalQuestionRunner:
    """Rule-based answerer used to validate the evaluation harness."""

    name = "deterministic-clinical-question-runner-v1"
    prompt_template_id = "clinical-qa-deterministic-v1"
    answer_model = "deterministic-rules"

    def build_prompt(
        self,
        *,
        test_case: ClinicalQATestCase,
        context: ClinicalContext,
    ) -> str:
        evidence_lines = [
            f"- [{item.citation_id}] {item.resource_type}: {item.display} "
            f"{item.value or ''} {item.unit or ''} {item.interpretation or ''}".strip()
            for item in context.evidence
        ]
        return "\n".join(
            [
                f"Question: {test_case.clinical_question}",
                "",
                "Available extracted evidence:",
                *evidence_lines,
                "",
                "Instruction: answer only from this extracted evidence and cite citation ids.",
            ]
        )

    def answer_question(
        self,
        *,
        test_case: ClinicalQATestCase,
        context: ClinicalContext,
        prompt: str,
    ) -> ClinicalAnswer:
        if test_case.test_id != RENAL_TEST_ID:
            return ClinicalAnswer(
                question_id=test_case.test_id,
                answer_model=self.answer_model,
                prompt_template_id=self.prompt_template_id,
                harness_name=self.name,
                answer="This deterministic runner only supports the renal impairment smoke test.",
                abstained=True,
                claims=[],
            )

        renal_evidence = _renal_impairment_evidence(context)
        if not renal_evidence:
            return ClinicalAnswer(
                question_id=test_case.test_id,
                answer_model=self.answer_model,
                prompt_template_id=self.prompt_template_id,
                harness_name=self.name,
                answer=(
                    "Insufficient extracted evidence to determine renal impairment. "
                    "The Bundle does not contain creatinine, eGFR, or BUN evidence "
                    "that can support a safe medication-dosing or surgical-risk answer."
                ),
                abstained=True,
                citations=[],
                claims=["renal evidence insufficient"],
            )

        fact_text = "; ".join(_format_evidence_fact(item) for item in renal_evidence[:3])
        return ClinicalAnswer(
            question_id=test_case.test_id,
            answer_model=self.answer_model,
            prompt_template_id=self.prompt_template_id,
            harness_name=self.name,
            answer=(
                "Yes. Extracted evidence suggests renal impairment relevant to medication "
                f"dosing or perioperative planning: {fact_text}. This should trigger renal-dose "
                "review and surgical clearance attention."
            ),
            abstained=False,
            citations=[item.citation_id for item in renal_evidence[:3]],
            claims=[
                "renal impairment present",
                "renal-dose review indicated",
                "perioperative planning should account for renal function",
            ],
        )


class DeterministicAnswerGrader:
    """Rule-based grader for the smoke suite.

    This is intentionally conservative: it can judge support, citation hygiene,
    and abstention behavior from the Bundle. It is not a replacement for a
    reviewer-grounded or LLM rubric grader.
    """

    name = "deterministic-clinical-answer-grader-v1"

    def grade_answer(
        self,
        *,
        test_case: ClinicalQATestCase,
        context: ClinicalContext,
        answer: ClinicalAnswer,
    ) -> QuestionGrade:
        if test_case.test_id != RENAL_TEST_ID:
            return _grade_with_values(
                test_case=test_case,
                answer=answer,
                correctness=0.0,
                completeness=0.0,
                evidence_citation_quality=0.0,
                cited_fact_support=0.0,
                hallucination_avoidance=1.0,
                abstention_quality=1.0 if answer.abstained else 0.0,
                clinical_usefulness=0.0,
                unsupported_claims=[],
                missing_required_evidence_types=test_case.required_evidence_types,
                rationale="Unsupported deterministic question id.",
            )

        renal_evidence = _renal_impairment_evidence(context)
        cited_ids = set(answer.citations)
        evidence_ids = {item.citation_id for item in context.evidence}
        cited_existing = cited_ids & evidence_ids
        cited_renal = {item.citation_id for item in renal_evidence} & cited_ids
        unsupported_claims: list[str] = []
        if cited_ids - evidence_ids:
            unsupported_claims.extend(f"citation_not_found:{item}" for item in sorted(cited_ids - evidence_ids))
        if answer.abstained and renal_evidence:
            unsupported_claims.append("abstained_despite_extracted_renal_evidence")
        if not answer.abstained and not renal_evidence:
            unsupported_claims.append("answered_yes_without_extracted_renal_evidence")

        if renal_evidence:
            correctness = 1.0 if not answer.abstained else 0.0
            completeness = min(len(cited_renal) / min(len(renal_evidence), 3), 1.0)
            evidence_citation_quality = min(len(cited_existing) / max(len(cited_ids), 1), 1.0) if cited_ids else 0.0
            cited_fact_support = 1.0 if cited_renal else 0.0
            abstention_quality = 1.0 if not answer.abstained else 0.0
            usefulness_terms = ("dosing", "surgery", "perioperative", "clearance")
            clinical_usefulness = 1.0 if any(term in answer.answer.lower() for term in usefulness_terms) else 0.5
            rationale = "Renal evidence was present; the answer should identify risk and cite extracted facts."
        else:
            correctness = 1.0 if answer.abstained else 0.0
            completeness = 1.0 if answer.abstained else 0.0
            evidence_citation_quality = 1.0 if not cited_ids else 0.0
            cited_fact_support = 1.0 if not cited_ids else 0.0
            abstention_quality = 1.0 if answer.abstained else 0.0
            clinical_usefulness = 0.8 if "insufficient" in answer.answer.lower() else 0.4
            rationale = "No renal evidence was present; a useful answer should abstain and name the missing evidence."

        hallucination_avoidance = 1.0 if not unsupported_claims else 0.0
        missing_required = []
        if renal_evidence and not any(item.resource_type == "Observation" for item in renal_evidence):
            missing_required.append("Observation")
        if not renal_evidence and not answer.abstained:
            missing_required.extend(test_case.required_evidence_types)

        return _grade_with_values(
            test_case=test_case,
            answer=answer,
            correctness=correctness,
            completeness=completeness,
            evidence_citation_quality=evidence_citation_quality,
            cited_fact_support=cited_fact_support,
            hallucination_avoidance=hallucination_avoidance,
            abstention_quality=abstention_quality,
            clinical_usefulness=clinical_usefulness,
            unsupported_claims=unsupported_claims,
            missing_required_evidence_types=missing_required,
            rationale=rationale,
        )


def _resource_to_evidence(resource: dict[str, Any], index: int) -> EvidenceCitation:
    resource_type = str(resource.get("resourceType") or "Unknown")
    coding = _first_coding(resource.get("code") or {})
    display = (
        (resource.get("code") or {}).get("text")
        or coding.get("display")
        or resource.get("description")
        or resource.get("status")
        or resource_type
    )
    quantity = resource.get("valueQuantity") or {}
    value = quantity.get("value")
    unit = quantity.get("unit") or quantity.get("code")
    resource_id = resource.get("id")
    citation_id = f"{resource_type}/{resource_id}" if resource_id else f"{resource_type}/generated-{index}"
    return EvidenceCitation(
        citation_id=citation_id,
        resource_type=resource_type,
        resource_id=resource_id,
        display=str(display),
        code=coding.get("code"),
        code_system=coding.get("system"),
        value=str(value) if value is not None else None,
        unit=str(unit) if unit is not None else None,
        interpretation=_interpretation_code(resource),
        effective_date=resource.get("effectiveDateTime") or resource.get("issued"),
        source_locator=_source_locator(resource),
        raw=resource,
    )


def _first_coding(codeable: dict[str, Any]) -> dict[str, Any]:
    codings = codeable.get("coding") or []
    if codings and isinstance(codings[0], dict):
        return codings[0]
    return {}


def _interpretation_code(resource: dict[str, Any]) -> str | None:
    interpretations = resource.get("interpretation") or []
    if not interpretations:
        return None
    first = interpretations[0] or {}
    coding = _first_coding(first)
    return coding.get("code") or first.get("text")


def _source_locator(resource: dict[str, Any]) -> str | None:
    for extension in (resource.get("meta") or {}).get("extension") or []:
        url = str(extension.get("url") or "")
        if url.endswith("source-locator"):
            return extension.get("valueString")
    return None


def _is_lab_like_observation(resource: dict[str, Any]) -> bool:
    for category in resource.get("category") or []:
        for coding in category.get("coding") or []:
            if str(coding.get("code") or "").lower() == "laboratory":
                return True
    for coding in (resource.get("code") or {}).get("coding") or []:
        if "loinc" in str(coding.get("system") or "").lower():
            return True
    return False


def _renal_impairment_evidence(context: ClinicalContext) -> list[EvidenceCitation]:
    return [
        item
        for item in context.evidence
        if item.resource_type == "Observation" and _is_renal_impairment_fact(item)
    ]


def _is_renal_impairment_fact(item: EvidenceCitation) -> bool:
    text = f"{item.display} {item.code or ''}".lower()
    if item.code not in RENAL_CODES and not any(token in text for token in RENAL_NAME_TOKENS):
        return False
    value = _float_or_none(item.value)
    interp = (item.interpretation or "").upper()
    if item.code in {"33914-3", "62238-1"} or "egfr" in text or "gfr" in text:
        return value is not None and value < 60
    if item.code in {"2160-0", "3094-0"} or "creatinine" in text or "bun" in text:
        return interp in {"H", "HH", "HIGH"} or (value is not None and value > 1.3 and "creatinine" in text)
    return interp in {"H", "HH", "L", "LL", "HIGH", "LOW"}


def _format_evidence_fact(item: EvidenceCitation) -> str:
    value = f"{item.value} {item.unit}".strip() if item.value else "present"
    interp = f", {item.interpretation}" if item.interpretation else ""
    return f"{item.display} {value}{interp} [{item.citation_id}]"


def _grade_with_values(
    *,
    test_case: ClinicalQATestCase,
    answer: ClinicalAnswer,
    correctness: float,
    completeness: float,
    evidence_citation_quality: float,
    cited_fact_support: float,
    hallucination_avoidance: float,
    abstention_quality: float,
    clinical_usefulness: float,
    unsupported_claims: list[str],
    missing_required_evidence_types: list[str],
    rationale: str,
) -> QuestionGrade:
    weights = test_case.scoring_weights
    score = (
        correctness * weights.correctness
        + completeness * weights.completeness
        + evidence_citation_quality * weights.evidence_citation_quality
        + hallucination_avoidance * weights.hallucination_avoidance
        + abstention_quality * weights.abstention_quality
        + clinical_usefulness * weights.clinical_usefulness
    )
    return QuestionGrade(
        question_id=test_case.test_id,
        grader="deterministic-clinical-answer-grader-v1",
        score=round(score, 4),
        correctness=round(correctness, 4),
        completeness=round(completeness, 4),
        evidence_citation_quality=round(evidence_citation_quality, 4),
        cited_fact_support=round(cited_fact_support, 4),
        hallucination_avoidance=round(hallucination_avoidance, 4),
        abstention_quality=round(abstention_quality, 4),
        clinical_usefulness=round(clinical_usefulness, 4),
        unsupported_claims=unsupported_claims,
        missing_required_evidence_types=missing_required_evidence_types,
        rationale=rationale,
    )


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
