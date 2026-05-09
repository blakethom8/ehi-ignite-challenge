"""Typed artifacts for downstream clinical QA evaluation.

These models describe the evaluation layer around PDF-to-FHIR pipeline runs.
They intentionally do not know how extraction works; they only reference a
saved run and evaluate whether its Bundle supports clinical question answering.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ScoringWeights(BaseModel):
    correctness: float = 0.3
    completeness: float = 0.2
    evidence_citation_quality: float = 0.2
    hallucination_avoidance: float = 0.15
    abstention_quality: float = 0.1
    clinical_usefulness: float = 0.05


class ClinicalQATestCase(BaseModel):
    test_id: str
    title: str
    clinical_question: str
    expected_answer: str | None = None
    grading_rubric: str | None = None
    required_evidence_types: list[str] = Field(default_factory=list)
    ideal_citations: list[str] = Field(default_factory=list)
    expected_supporting_facts: list[str] = Field(default_factory=list)
    safety_critical: bool = False
    abstention_allowed: bool = True
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)


class EvaluationSuite(BaseModel):
    suite_id: str
    name: str
    description: str
    version: str
    test_cases: list[ClinicalQATestCase]


class PipelineRunRef(BaseModel):
    run_id: str
    lab_root: str
    artifact_dir: str
    pipeline_name: str
    pdf_path: str
    pdf_label: str
    pdf_sha256: str | None = None
    manifest_path: str
    bundle_path: str
    bundle_shape_path: str | None = None
    eval_path: str | None = None
    ground_truth_path: str | None = None


class EvidenceCitation(BaseModel):
    citation_id: str
    resource_type: str
    resource_id: str | None = None
    display: str
    code: str | None = None
    code_system: str | None = None
    value: str | None = None
    unit: str | None = None
    interpretation: str | None = None
    effective_date: str | None = None
    source_locator: str | None = None
    exists_in_bundle: bool = True
    raw: dict[str, Any] | None = None


class ClinicalContext(BaseModel):
    context_builder: str
    built_at: str = Field(default_factory=utc_now_iso)
    bundle_stats: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceCitation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ClinicalAnswer(BaseModel):
    question_id: str
    answer_model: str
    prompt_template_id: str
    harness_name: str | None = None
    response_format_version: str = "clinical-qa-answer-v1"
    answered_at: str = Field(default_factory=utc_now_iso)
    answer: str
    abstained: bool
    citations: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    tool_call_count: int = 0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int = 0
    cost_usd: float = 0.0


class QuestionGrade(BaseModel):
    question_id: str
    grader: str
    graded_at: str = Field(default_factory=utc_now_iso)
    score: float
    correctness: float
    completeness: float
    evidence_citation_quality: float
    cited_fact_support: float
    hallucination_avoidance: float
    abstention_quality: float
    clinical_usefulness: float
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_required_evidence_types: list[str] = Field(default_factory=list)
    rationale: str


class QuestionEvaluationResult(BaseModel):
    question_id: str
    title: str
    safety_critical: bool
    abstained: bool
    score: float
    correctness: float
    evidence_citation_quality: float
    hallucination_avoidance: float
    abstention_quality: float
    clinical_usefulness: float
    citation_count: int
    unsupported_claim_count: int
    answer_model: str | None = None
    answer_latency_ms: int = 0
    tool_call_count: int = 0
    missing_required_evidence_types: list[str] = Field(default_factory=list)


class EvaluationManifest(BaseModel):
    eval_run_id: str
    suite_id: str
    suite_name: str
    suite_version: str
    created_at: str = Field(default_factory=utc_now_iso)
    finished_at: str | None = None
    status: Literal["running", "succeeded", "failed"] = "running"
    pipeline_run: PipelineRunRef
    context_builder: str
    question_runner: str
    answer_grader: str
    question_count: int
    latency_ms: int = 0
    cost_usd: float = 0.0
    error: str | None = None


class EvaluationResult(BaseModel):
    eval_run_id: str
    suite_id: str
    suite_name: str
    suite_version: str
    created_at: str
    finished_at: str | None
    status: str
    pipeline_run: PipelineRunRef
    question_count: int
    safety_critical_count: int
    overall_score: float | None
    mean_correctness: float | None
    mean_evidence_citation_quality: float | None
    mean_hallucination_avoidance: float | None
    mean_abstention_quality: float | None
    unsupported_claim_rate: float | None
    abstention_rate: float | None
    latency_ms: int = 0
    cost_usd: float = 0.0
    bundle_stats: dict[str, Any] = Field(default_factory=dict)
    question_results: list[QuestionEvaluationResult] = Field(default_factory=list)
