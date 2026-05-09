"""Pipeline Lab leaderboard API.

Reads PDF Lab artifacts from disk and exposes a dashboard-friendly summary of
registered pipelines, recent runs, architecture lanes, and observed metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from lib.extract.lab.evaluations import (
    DEFAULT_EVAL_ROOT,
    EvaluationResult,
    list_evaluation_summaries,
    run_evaluation_for_pipeline_run,
)
from lib.extract.lab.recorder import REPO_ROOT
from lib.extract.pipelines import list_pipelines

router = APIRouter(prefix="/pipeline-lab", tags=["pipeline-lab"])


class PipelineRunSummary(BaseModel):
    run_id: str
    pipeline_name: str
    architecture: str | None = None
    lab_root: str
    status: str
    pdf_path: str
    pdf_label: str
    pdf_sha256: str | None = None
    artifact_dir: str
    source_pdf_artifact: str | None = None
    bundle_artifact: str | None = None
    eval_artifact: str | None = None
    bundle_shape_artifact: str | None = None
    ground_truth_artifact: str | None = None
    ground_truth_path: str | None = None
    has_ground_truth: bool = False
    trace_count: int = 0
    artifact_urls: dict[str, str] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0
    total_entries: int = 0
    weighted_f1: float | None = None
    loinc_resolution_rate: float | None = None
    patient_link_rate: float | None = None
    encounter_link_rate: float | None = None
    resource_counts: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


class PipelineLeaderboardRow(BaseModel):
    name: str
    architecture: str
    description: str
    primary_backends: list[str]
    estimated_cost_per_pdf_usd: float | None = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float | None = None
    last_run_at: str | None = None
    last_status: str | None = None
    last_run_id: str | None = None
    avg_latency_ms: int | None = None
    avg_cost_usd: float | None = None
    avg_entries: float | None = None
    best_weighted_f1: float | None = None
    latest_weighted_f1: float | None = None
    best_clinical_qa_score: float | None = None
    latest_clinical_qa_score: float | None = None
    latest_eval_run_id: str | None = None
    latest_loinc_resolution_rate: float | None = None
    latest_patient_link_rate: float | None = None
    latest_encounter_link_rate: float | None = None
    tested_pdf_count: int = 0
    recent_runs: list[PipelineRunSummary] = Field(default_factory=list)


class PipelineSuiteSummary(BaseModel):
    suite_run_id: str
    suite_name: str
    root: str
    cell_count: int
    succeeded: int
    failed: int
    created_at: str | None = None
    report_path: str | None = None


class PipelineQuestionEvaluationSummary(BaseModel):
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


class PipelineEvaluationSummary(BaseModel):
    eval_run_id: str
    suite_id: str
    suite_name: str
    suite_version: str
    status: str
    created_at: str
    finished_at: str | None = None
    pipeline_run_id: str
    pipeline_name: str
    lab_root: str
    pdf_label: str
    artifact_dir: str
    artifact_urls: dict[str, str] = Field(default_factory=dict)
    question_count: int
    safety_critical_count: int
    overall_score: float | None = None
    mean_correctness: float | None = None
    mean_evidence_citation_quality: float | None = None
    mean_hallucination_avoidance: float | None = None
    mean_abstention_quality: float | None = None
    unsupported_claim_rate: float | None = None
    abstention_rate: float | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0
    bundle_stats: dict[str, Any] = Field(default_factory=dict)
    question_results: list[PipelineQuestionEvaluationSummary] = Field(default_factory=list)


class PipelineQuestionEvaluationDetail(BaseModel):
    question_id: str
    title: str
    clinical_question: str
    expected_answer: str | None = None
    grading_rubric: str | None = None
    required_evidence_types: list[str] = Field(default_factory=list)
    ideal_citations: list[str] = Field(default_factory=list)
    expected_supporting_facts: list[str] = Field(default_factory=list)
    safety_critical: bool = False
    abstention_allowed: bool = True
    answer: str | None = None
    abstained: bool = False
    citations: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    answer_model: str | None = None
    prompt_template_id: str | None = None
    harness_name: str | None = None
    response_format_version: str | None = None
    answer_latency_ms: int = 0
    tool_call_count: int = 0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = 0.0
    score: float | None = None
    correctness: float | None = None
    completeness: float | None = None
    evidence_citation_quality: float | None = None
    cited_fact_support: float | None = None
    hallucination_avoidance: float | None = None
    abstention_quality: float | None = None
    clinical_usefulness: float | None = None
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_required_evidence_types: list[str] = Field(default_factory=list)
    grader: str | None = None
    grader_rationale: str | None = None
    cited_evidence: list[dict[str, Any]] = Field(default_factory=list)
    available_evidence_count: int = 0
    artifact_urls: dict[str, str] = Field(default_factory=dict)


class PipelineEvaluationDetail(BaseModel):
    summary: PipelineEvaluationSummary
    context_builder: str | None = None
    question_runner: str | None = None
    answer_grader: str | None = None
    bundle_stats: dict[str, Any] = Field(default_factory=dict)
    prompt_contract: dict[str, Any] = Field(default_factory=dict)
    run_instructions: dict[str, Any] = Field(default_factory=dict)
    questions: list[PipelineQuestionEvaluationDetail] = Field(default_factory=list)


class PipelineTestCriterion(BaseModel):
    key: str
    label: str
    target: str
    measurement: str
    why_it_matters: str


class PipelineTestPdfSummary(BaseModel):
    pdf_sha256: str | None = None
    pdf_label: str
    original_path: str
    run_count: int
    pipeline_count: int
    pipelines: list[str]
    latest_run_at: str | None = None
    has_ground_truth: bool = False
    ground_truth_path: str | None = None


class GoldStandardSummary(BaseModel):
    pipeline_name: str = "multipass-fhir-gold"
    label: str = "Gold standard"
    definition: str
    measurement: str
    current_run_count: int = 0
    latest_run_at: str | None = None
    artifact_policy: str


class GroundTruthPdfSummary(BaseModel):
    pdf_sha_prefix: str
    pdf_sha256: str
    pdf_label: str
    pdf_path: str
    latest_version: int
    created_at: str | None = None
    reviewer: str | None = None
    source_run_id: str | None = None
    resource_counts: dict[str, int] = Field(default_factory=dict)
    total_entries: int = 0
    ground_truth_path: str


class GroundTruthSummary(BaseModel):
    definition: str
    what_it_is_not: str
    storage_policy: str
    comparison_policy: str
    creation_workflow: list[str]
    pdf_count: int
    versions: list[GroundTruthPdfSummary]


class PipelineLabLeaderboardResponse(BaseModel):
    generated_at: str
    lab_roots: list[str]
    pipelines: list[PipelineLeaderboardRow]
    recent_runs: list[PipelineRunSummary]
    evaluations: list[PipelineEvaluationSummary]
    suites: list[PipelineSuiteSummary]
    test_criteria: list[PipelineTestCriterion]
    test_pdfs: list[PipelineTestPdfSummary]
    gold_standard: GoldStandardSummary
    ground_truth: GroundTruthSummary
    totals: dict[str, int | float]


@dataclass(frozen=True)
class _RunArtifact:
    summary: PipelineRunSummary
    sort_key: str


@router.get("/leaderboard", response_model=PipelineLabLeaderboardResponse)
def get_pipeline_lab_leaderboard() -> PipelineLabLeaderboardResponse:
    lab_roots = [
        REPO_ROOT / "data" / "pdf-lab",
        REPO_ROOT / "data" / "local-model-lab",
    ]
    metadata = {meta.name: meta for meta in list_pipelines()}
    runs = _read_runs(lab_roots, metadata)
    evaluations = _read_evaluation_summaries()
    evaluations_by_pipeline: dict[str, list[PipelineEvaluationSummary]] = defaultdict(list)
    for evaluation in evaluations:
        evaluations_by_pipeline[evaluation.pipeline_name].append(evaluation)
    runs_by_pipeline: dict[str, list[PipelineRunSummary]] = defaultdict(list)
    for artifact in runs:
        runs_by_pipeline[artifact.summary.pipeline_name].append(artifact.summary)

    rows: list[PipelineLeaderboardRow] = []
    all_pipeline_names = sorted(set(metadata) | set(runs_by_pipeline))
    for name in all_pipeline_names:
        meta = metadata.get(name)
        pipeline_runs = sorted(
            runs_by_pipeline.get(name, []),
            key=lambda run: run.finished_at or run.started_at or "",
            reverse=True,
        )
        pipeline_evaluations = sorted(
            evaluations_by_pipeline.get(name, []),
            key=lambda item: item.finished_at or item.created_at,
            reverse=True,
        )
        rows.append(_leaderboard_row(name, meta, pipeline_runs, pipeline_evaluations))

    recent_runs = [artifact.summary for artifact in sorted(runs, key=lambda item: item.sort_key, reverse=True)[:40]]
    suites = _read_suites(lab_roots)
    test_pdfs = _summarize_test_pdfs([artifact.summary for artifact in runs])
    gold_runs = runs_by_pipeline.get("multipass-fhir-gold", [])
    ground_truth = _read_ground_truth(REPO_ROOT / "data" / "pdf-lab")

    success_count = sum(1 for run in runs if run.summary.status == "succeeded")
    return PipelineLabLeaderboardResponse(
        generated_at=_now_iso(),
        lab_roots=[str(root.relative_to(REPO_ROOT)) for root in lab_roots],
        pipelines=sorted(
            rows,
            key=lambda row: (
                row.name != "multipass-fhir-gold",
                row.last_run_at is None,
                -(row.best_weighted_f1 or -1),
                row.name,
            ),
        ),
        recent_runs=recent_runs,
        evaluations=evaluations[:20],
        suites=suites,
        test_criteria=_test_criteria(),
        test_pdfs=test_pdfs,
        gold_standard=GoldStandardSummary(
            definition=(
                "The reference extraction lane used to create or validate ground truth. "
                "It uses the most expensive/high-reasoning architecture, self-consistency, "
                "and reviewer checks where available; its output is still reviewed before "
                "being treated as verified truth."
            ),
            measurement=(
                "Gold-standard runs are not ranked as normal competitors. Other pipelines "
                "are scored against reviewed ground-truth bundles with weighted F1, then "
                "checked for structural quality with bundle-shape metrics."
            ),
            current_run_count=len(gold_runs),
            latest_run_at=(gold_runs[0].finished_at or gold_runs[0].started_at) if gold_runs else None,
            artifact_policy=(
                "Every run is cached under data/pdf-lab or data/local-model-lab with the "
                "source PDF, output bundle, manifest, metrics, and pass traces when logged."
            ),
        ),
        ground_truth=ground_truth,
        totals={
            "registered_pipelines": len(metadata),
            "pipelines_with_runs": len(runs_by_pipeline),
            "run_count": len(runs),
            "success_count": success_count,
            "failure_count": len(runs) - success_count,
            "eval_run_count": len(evaluations),
            "suite_count": len(suites),
        },
    )


@router.get("/evaluations", response_model=list[PipelineEvaluationSummary])
def get_pipeline_lab_evaluations() -> list[PipelineEvaluationSummary]:
    return _read_evaluation_summaries()


@router.get("/evaluations/{eval_run_id}", response_model=PipelineEvaluationDetail)
def get_pipeline_lab_evaluation(eval_run_id: str) -> PipelineEvaluationDetail:
    detail = _read_evaluation_detail(eval_run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return detail


@router.post("/evaluations/run", response_model=PipelineEvaluationSummary)
def run_pipeline_lab_evaluation(
    run_id: str = Query(...),
    root: str = Query(default="data/pdf-lab"),
) -> PipelineEvaluationSummary:
    root_path = _safe_lab_root(root)
    run_dir = root_path / "runs" / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    try:
        result = run_evaluation_for_pipeline_run(run_dir=run_dir, lab_root=root_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _api_evaluation_summary(result)


@router.get("/evaluations/{eval_run_id}/artifacts/{artifact_name}")
def get_evaluation_artifact(
    eval_run_id: str,
    artifact_name: str,
    question_id: str | None = Query(default=None),
) -> FileResponse:
    allowed = {
        "manifest": "manifest.json",
        "suite": "suite.json",
        "pipeline_run_ref": "pipeline_run_ref.json",
        "context": "context.json",
        "summary": "summary.json",
    }
    if artifact_name in {"prompt", "answer", "grade", "evidence"}:
        if not question_id:
            raise HTTPException(status_code=400, detail="question_id is required for question artifacts")
        filename = "prompt.txt" if artifact_name == "prompt" else f"{artifact_name}.json"
        path = DEFAULT_EVAL_ROOT / "runs" / eval_run_id / "questions" / question_id / filename
    else:
        filename = allowed.get(artifact_name)
        if filename is None:
            raise HTTPException(status_code=404, detail="Unknown artifact")
        path = DEFAULT_EVAL_ROOT / "runs" / eval_run_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)


@router.get("/runs/{run_id}/artifacts/{artifact_name}")
def get_run_artifact(
    run_id: str,
    artifact_name: str,
    root: str = Query(default="data/pdf-lab"),
) -> FileResponse:
    allowed = {
        "manifest": "manifest.json",
        "bundle": "bundle.json",
        "eval": "eval.json",
        "bundle_shape": "bundle_shape.json",
        "source_pdf": "source.pdf",
        "ground_truth": "ground-truth.json",
    }
    filename = allowed.get(artifact_name)
    if filename is None:
        raise HTTPException(status_code=404, detail="Unknown artifact")
    root_path = _safe_lab_root(root)
    path = root_path / "runs" / run_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)


def _leaderboard_row(
    name: str,
    meta: Any,
    runs: list[PipelineRunSummary],
    evaluations: list[PipelineEvaluationSummary],
) -> PipelineLeaderboardRow:
    success_runs = [run for run in runs if run.status == "succeeded"]
    f1_values = [run.weighted_f1 for run in success_runs if run.weighted_f1 is not None]
    latest = runs[0] if runs else None
    latest_success = success_runs[0] if success_runs else None
    latest_evaluation = evaluations[0] if evaluations else None
    clinical_scores = [
        evaluation.overall_score
        for evaluation in evaluations
        if evaluation.status == "succeeded" and evaluation.overall_score is not None
    ]
    avg_latency = _avg_int([run.latency_ms for run in success_runs if run.latency_ms])
    avg_cost = _avg_float([run.cost_usd for run in success_runs])
    avg_entries = _avg_float([float(run.total_entries) for run in success_runs])

    return PipelineLeaderboardRow(
        name=name,
        architecture=getattr(meta, "architecture", "unknown") if meta else "unknown",
        description=getattr(meta, "description", "") if meta else "",
        primary_backends=list(getattr(meta, "primary_backends", []) or []) if meta else [],
        estimated_cost_per_pdf_usd=getattr(meta, "estimated_cost_per_pdf_usd", None) if meta else None,
        run_count=len(runs),
        success_count=len(success_runs),
        failure_count=len(runs) - len(success_runs),
        success_rate=(len(success_runs) / len(runs)) if runs else None,
        last_run_at=(latest.finished_at or latest.started_at) if latest else None,
        last_status=latest.status if latest else None,
        last_run_id=latest.run_id if latest else None,
        avg_latency_ms=avg_latency,
        avg_cost_usd=avg_cost,
        avg_entries=avg_entries,
        best_weighted_f1=max(f1_values) if f1_values else None,
        latest_weighted_f1=latest_success.weighted_f1 if latest_success else None,
        best_clinical_qa_score=max(clinical_scores) if clinical_scores else None,
        latest_clinical_qa_score=latest_evaluation.overall_score if latest_evaluation else None,
        latest_eval_run_id=latest_evaluation.eval_run_id if latest_evaluation else None,
        latest_loinc_resolution_rate=latest_success.loinc_resolution_rate if latest_success else None,
        latest_patient_link_rate=latest_success.patient_link_rate if latest_success else None,
        latest_encounter_link_rate=latest_success.encounter_link_rate if latest_success else None,
        tested_pdf_count=len({run.pdf_path for run in runs}),
        recent_runs=runs[:5],
    )


def _read_evaluation_summaries() -> list[PipelineEvaluationSummary]:
    return [_api_evaluation_summary(summary) for summary in list_evaluation_summaries()]


def _api_evaluation_summary(summary: EvaluationResult) -> PipelineEvaluationSummary:
    return PipelineEvaluationSummary(
        eval_run_id=summary.eval_run_id,
        suite_id=summary.suite_id,
        suite_name=summary.suite_name,
        suite_version=summary.suite_version,
        status=summary.status,
        created_at=summary.created_at,
        finished_at=summary.finished_at,
        pipeline_run_id=summary.pipeline_run.run_id,
        pipeline_name=summary.pipeline_run.pipeline_name,
        lab_root=summary.pipeline_run.lab_root,
        pdf_label=summary.pipeline_run.pdf_label,
        artifact_dir=str((DEFAULT_EVAL_ROOT / "runs" / summary.eval_run_id).relative_to(REPO_ROOT)),
        artifact_urls=_evaluation_artifact_urls(summary),
        question_count=summary.question_count,
        safety_critical_count=summary.safety_critical_count,
        overall_score=summary.overall_score,
        mean_correctness=summary.mean_correctness,
        mean_evidence_citation_quality=summary.mean_evidence_citation_quality,
        mean_hallucination_avoidance=summary.mean_hallucination_avoidance,
        mean_abstention_quality=summary.mean_abstention_quality,
        unsupported_claim_rate=summary.unsupported_claim_rate,
        abstention_rate=summary.abstention_rate,
        latency_ms=summary.latency_ms,
        cost_usd=summary.cost_usd,
        bundle_stats=summary.bundle_stats,
        question_results=[
            PipelineQuestionEvaluationSummary(**question.model_dump(mode="json"))
            for question in summary.question_results
        ],
    )


def _read_evaluation_detail(eval_run_id: str) -> PipelineEvaluationDetail | None:
    eval_dir = DEFAULT_EVAL_ROOT / "runs" / eval_run_id
    summary_data = _read_json(eval_dir / "summary.json")
    if not isinstance(summary_data, dict) or not summary_data:
        return None
    summary = _api_evaluation_summary(EvaluationResult.model_validate(summary_data))
    manifest = _read_json(eval_dir / "manifest.json")
    suite = _read_json(eval_dir / "suite.json")
    context = _read_json(eval_dir / "context.json")
    test_cases = {
        str(item.get("test_id")): item
        for item in suite.get("test_cases", [])
        if isinstance(item, dict) and item.get("test_id")
    }

    questions: list[PipelineQuestionEvaluationDetail] = []
    for question_summary in summary.question_results:
        question_id = question_summary.question_id
        question_dir = eval_dir / "questions" / question_id
        test_case = test_cases.get(question_id, {})
        answer = _read_json(question_dir / "answer.json")
        grade = _read_json(question_dir / "grade.json")
        evidence = _read_json(question_dir / "evidence.json")
        questions.append(
            PipelineQuestionEvaluationDetail(
                question_id=question_id,
                title=str(test_case.get("title") or question_summary.title),
                clinical_question=str(test_case.get("clinical_question") or ""),
                expected_answer=test_case.get("expected_answer"),
                grading_rubric=test_case.get("grading_rubric"),
                required_evidence_types=list(test_case.get("required_evidence_types") or []),
                ideal_citations=list(test_case.get("ideal_citations") or []),
                expected_supporting_facts=list(test_case.get("expected_supporting_facts") or []),
                safety_critical=bool(test_case.get("safety_critical") or question_summary.safety_critical),
                abstention_allowed=bool(test_case.get("abstention_allowed", True)),
                answer=answer.get("answer") if isinstance(answer, dict) else None,
                abstained=bool(answer.get("abstained") if isinstance(answer, dict) else question_summary.abstained),
                citations=list(answer.get("citations") or []) if isinstance(answer, dict) else [],
                claims=list(answer.get("claims") or []) if isinstance(answer, dict) else [],
                answer_model=answer.get("answer_model") if isinstance(answer, dict) else question_summary.answer_model,
                prompt_template_id=answer.get("prompt_template_id") if isinstance(answer, dict) else None,
                harness_name=answer.get("harness_name") if isinstance(answer, dict) else None,
                response_format_version=answer.get("response_format_version") if isinstance(answer, dict) else None,
                answer_latency_ms=int(answer.get("latency_ms") or question_summary.answer_latency_ms)
                if isinstance(answer, dict)
                else question_summary.answer_latency_ms,
                tool_call_count=int(answer.get("tool_call_count") or question_summary.tool_call_count)
                if isinstance(answer, dict)
                else question_summary.tool_call_count,
                tool_calls=list(answer.get("tool_calls") or []) if isinstance(answer, dict) else [],
                cost_usd=float(answer.get("cost_usd") or 0.0) if isinstance(answer, dict) else 0.0,
                score=_float_or_none(grade.get("score")) if isinstance(grade, dict) else question_summary.score,
                correctness=_float_or_none(grade.get("correctness")) if isinstance(grade, dict) else question_summary.correctness,
                completeness=_float_or_none(grade.get("completeness")) if isinstance(grade, dict) else None,
                evidence_citation_quality=_float_or_none(grade.get("evidence_citation_quality"))
                if isinstance(grade, dict)
                else question_summary.evidence_citation_quality,
                cited_fact_support=_float_or_none(grade.get("cited_fact_support")) if isinstance(grade, dict) else None,
                hallucination_avoidance=_float_or_none(grade.get("hallucination_avoidance"))
                if isinstance(grade, dict)
                else question_summary.hallucination_avoidance,
                abstention_quality=_float_or_none(grade.get("abstention_quality")) if isinstance(grade, dict) else question_summary.abstention_quality,
                clinical_usefulness=_float_or_none(grade.get("clinical_usefulness")) if isinstance(grade, dict) else question_summary.clinical_usefulness,
                unsupported_claims=list(grade.get("unsupported_claims") or []) if isinstance(grade, dict) else [],
                missing_required_evidence_types=list(grade.get("missing_required_evidence_types") or [])
                if isinstance(grade, dict)
                else question_summary.missing_required_evidence_types,
                grader=grade.get("grader") if isinstance(grade, dict) else None,
                grader_rationale=grade.get("rationale") if isinstance(grade, dict) else None,
                cited_evidence=list(evidence.get("cited_evidence") or []) if isinstance(evidence, dict) else [],
                available_evidence_count=int(evidence.get("available_evidence_count") or 0) if isinstance(evidence, dict) else 0,
                artifact_urls=_question_artifact_urls(eval_run_id, question_id),
            )
        )

    return PipelineEvaluationDetail(
        summary=summary,
        context_builder=manifest.get("context_builder") if isinstance(manifest, dict) else None,
        question_runner=manifest.get("question_runner") if isinstance(manifest, dict) else None,
        answer_grader=manifest.get("answer_grader") if isinstance(manifest, dict) else None,
        bundle_stats=context.get("bundle_stats", {}) if isinstance(context, dict) else {},
        prompt_contract=_prompt_contract(),
        run_instructions=_run_instructions(summary),
        questions=questions,
    )


def _question_artifact_urls(eval_run_id: str, question_id: str) -> dict[str, str]:
    base = f"/api/pipeline-lab/evaluations/{quote(eval_run_id)}/artifacts"
    qid = quote(question_id)
    return {
        "prompt": f"{base}/prompt?question_id={qid}",
        "answer": f"{base}/answer?question_id={qid}",
        "grade": f"{base}/grade?question_id={qid}",
        "evidence": f"{base}/evidence?question_id={qid}",
    }


def _prompt_contract() -> dict[str, Any]:
    return {
        "answer_format": "clinical-qa-answer-v1",
        "required_fields": [
            "answer",
            "abstained",
            "citations",
            "claims",
            "tool_call_count",
            "tool_calls",
            "latency_ms",
            "cost_usd",
        ],
        "tool_call_schema": {
            "name": "string",
            "input_summary": "string",
            "latency_ms": "number",
            "result_summary": "string",
        },
        "grading_model_target": "Opus or another high-accuracy grader can score correctness, evidence support, abstention, and unsupported claims from this normalized answer shape.",
    }


def _run_instructions(summary: PipelineEvaluationSummary) -> dict[str, Any]:
    return {
        "api": f"POST /api/pipeline-lab/evaluations/run?root={summary.lab_root}&run_id={summary.pipeline_run_id}",
        "cli_equivalent": (
            "python -m lib.extract.lab.evaluations.run "
            f"--root {summary.lab_root} --run-id {summary.pipeline_run_id}"
        ),
        "current_artifact_dir": summary.artifact_dir,
    }


def _read_runs(
    lab_roots: list[Path],
    metadata: dict[str, Any],
) -> list[_RunArtifact]:
    out: list[_RunArtifact] = []
    for root in lab_roots:
        runs_dir = root / "runs"
        if not runs_dir.exists():
            continue
        for manifest_path in runs_dir.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                continue
            run_dir = manifest_path.parent
            pipeline_name = str(manifest.get("pipeline_name") or "unknown")
            shape = _read_json(run_dir / "bundle_shape.json")
            eval_result = _read_json(run_dir / "eval.json")
            bundle = _read_json(run_dir / "bundle.json")
            total_entries = int(shape.get("total_entries") or _bundle_entry_count(bundle))
            weighted_f1 = eval_result.get("weighted_f1")
            pdf_path = str(manifest.get("pdf_path") or "")
            finished_at = manifest.get("finished_at")
            started_at = manifest.get("started_at")
            meta = metadata.get(pipeline_name)
            summary = PipelineRunSummary(
                run_id=str(manifest.get("run_id") or run_dir.name),
                pipeline_name=pipeline_name,
                architecture=getattr(meta, "architecture", None) if meta else None,
                lab_root=str(root.relative_to(REPO_ROOT)),
                status=str(manifest.get("status") or "unknown"),
                pdf_path=pdf_path,
                pdf_label=Path(pdf_path).name if pdf_path else "unknown",
                pdf_sha256=manifest.get("pdf_sha256"),
                artifact_dir=_rel(run_dir),
                source_pdf_artifact=_rel(run_dir / "source.pdf") if (run_dir / "source.pdf").exists() else None,
                bundle_artifact=_rel(run_dir / "bundle.json") if (run_dir / "bundle.json").exists() else None,
                eval_artifact=_rel(run_dir / "eval.json") if (run_dir / "eval.json").exists() else None,
                bundle_shape_artifact=_rel(run_dir / "bundle_shape.json") if (run_dir / "bundle_shape.json").exists() else None,
                ground_truth_artifact=_rel(run_dir / "ground-truth.json") if (run_dir / "ground-truth.json").exists() else None,
                ground_truth_path=manifest.get("ground_truth_path"),
                has_ground_truth=bool(manifest.get("ground_truth_path") or (run_dir / "ground-truth.json").exists()),
                trace_count=_trace_count(run_dir),
                artifact_urls=_artifact_urls(root, run_dir.name),
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=int(manifest.get("latency_ms") or 0),
                cost_usd=float(manifest.get("cost_usd") or 0.0),
                total_entries=total_entries,
                weighted_f1=float(weighted_f1) if isinstance(weighted_f1, (int, float)) else None,
                loinc_resolution_rate=_float_or_none(shape.get("loinc_resolution_rate")),
                patient_link_rate=_float_or_none(shape.get("patient_link_rate")),
                encounter_link_rate=_float_or_none(shape.get("encounter_link_rate")),
                resource_counts=_resource_counts(bundle),
                error=manifest.get("error"),
            )
            out.append(_RunArtifact(summary=summary, sort_key=finished_at or started_at or ""))
    return out


def _summarize_test_pdfs(runs: list[PipelineRunSummary]) -> list[PipelineTestPdfSummary]:
    by_pdf: dict[str, list[PipelineRunSummary]] = defaultdict(list)
    for run in runs:
        key = run.pdf_sha256 or run.pdf_path or run.pdf_label
        by_pdf[key].append(run)

    summaries: list[PipelineTestPdfSummary] = []
    for _, pdf_runs in by_pdf.items():
        latest = sorted(pdf_runs, key=lambda run: run.finished_at or run.started_at or "", reverse=True)[0]
        pipelines = sorted({run.pipeline_name for run in pdf_runs})
        ground_truth_path = next((run.ground_truth_path or run.ground_truth_artifact for run in pdf_runs if run.has_ground_truth), None)
        summaries.append(
            PipelineTestPdfSummary(
                pdf_sha256=latest.pdf_sha256,
                pdf_label=latest.pdf_label,
                original_path=latest.pdf_path,
                run_count=len(pdf_runs),
                pipeline_count=len(pipelines),
                pipelines=pipelines,
                latest_run_at=latest.finished_at or latest.started_at,
                has_ground_truth=any(run.has_ground_truth for run in pdf_runs),
                ground_truth_path=ground_truth_path,
            )
        )
    return sorted(summaries, key=lambda item: item.latest_run_at or "", reverse=True)


def _read_suites(lab_roots: list[Path]) -> list[PipelineSuiteSummary]:
    suites: list[PipelineSuiteSummary] = []
    for root in lab_roots:
        suites_dir = root / "suites"
        if not suites_dir.exists():
            continue
        for cells_path in suites_dir.glob("*/cells.json"):
            suite_dir = cells_path.parent
            cells = _read_json(cells_path)
            if not isinstance(cells, list):
                cells = []
            suite_data = _read_json(suite_dir / "suite.json")
            statuses = [str(cell.get("status") or "") for cell in cells if isinstance(cell, dict)]
            suites.append(
                PipelineSuiteSummary(
                    suite_run_id=suite_dir.name,
                    suite_name=str(suite_data.get("name") or suite_dir.name),
                    root=str(root.relative_to(REPO_ROOT)),
                    cell_count=len(cells),
                    succeeded=statuses.count("succeeded"),
                    failed=statuses.count("failed"),
                    created_at=_suite_created_at(suite_dir.name),
                    report_path=str((suite_dir / "report.md").relative_to(REPO_ROOT))
                    if (suite_dir / "report.md").exists()
                    else None,
                )
            )
    return sorted(suites, key=lambda suite: suite.created_at or "", reverse=True)


def _read_ground_truth(lab_root: Path) -> GroundTruthSummary:
    versions: list[GroundTruthPdfSummary] = []
    gt_root = lab_root / "ground-truth"
    if gt_root.exists():
        for meta_path in gt_root.glob("*/*.meta.json"):
            meta = _read_json(meta_path)
            if not isinstance(meta, dict):
                continue
            latest_version = int(meta.get("latest_version") or 0)
            version_path = meta_path.parent / f"v{latest_version}.json"
            version_data = _read_json(version_path)
            if not isinstance(version_data, dict):
                version_data = {}
            bundle = version_data.get("bundle") if isinstance(version_data.get("bundle"), dict) else {}
            pdf_path = str(meta.get("pdf_path") or version_data.get("pdf_path") or "")
            versions.append(
                GroundTruthPdfSummary(
                    pdf_sha_prefix=str(meta.get("pdf_sha_prefix") or meta_path.parent.name),
                    pdf_sha256=str(meta.get("pdf_sha256") or version_data.get("pdf_sha256") or ""),
                    pdf_label=Path(pdf_path).name if pdf_path else "unknown",
                    pdf_path=pdf_path,
                    latest_version=latest_version,
                    created_at=version_data.get("created_at")
                    or (meta.get("versions_created") or [None])[-1],
                    reviewer=version_data.get("reviewer"),
                    source_run_id=version_data.get("source_run_id"),
                    resource_counts=_resource_counts(bundle),
                    total_entries=_bundle_entry_count(bundle),
                    ground_truth_path=_rel(version_path),
                )
            )

    return GroundTruthSummary(
        definition=(
            "Ground truth is the reviewed reference FHIR Bundle for one exact source PDF. "
            "It is keyed by the PDF SHA256, versioned immutably, and used as the target "
            "when computing fact-agreement metrics such as weighted F1."
        ),
        what_it_is_not=(
            "It is not simply the output of the gold-standard pipeline. The gold pipeline "
            "can propose candidate facts, but those facts only become ground truth after "
            "review, acceptance/rejection, and versioned save."
        ),
        storage_policy=(
            "Stored under data/pdf-lab/ground-truth/<pdf-sha-prefix>/vN.json with a "
            "sidecar meta file. Each version preserves the verified Bundle, reviewer "
            "decisions, reviewer identity when provided, source run id, notes, and timestamp."
        ),
        comparison_policy=(
            "A run is compared to ground truth only when the run PDF SHA has a matching "
            "ground-truth version or when a suite explicitly supplies a ground-truth file. "
            "Otherwise structural metrics still show, but F1 should be read as unavailable."
        ),
        creation_workflow=[
            "Run a candidate extraction, often the gold-standard pipeline.",
            "Review each emitted FHIR resource against the source PDF.",
            "Accept, reject, or edit each fact.",
            "Save the reviewed result as a new immutable ground-truth version.",
            "Use that version for future pipeline comparisons against the same PDF SHA.",
        ],
        pdf_count=len(versions),
        versions=sorted(versions, key=lambda item: item.created_at or "", reverse=True),
    )


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _bundle_entry_count(bundle: Any) -> int:
    if not isinstance(bundle, dict):
        return 0
    entries = bundle.get("entry")
    return len(entries) if isinstance(entries, list) else 0


def _resource_counts(bundle: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(bundle, dict):
        return counts
    for entry in bundle.get("entry", []):
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource") or {}
        if not isinstance(resource, dict):
            continue
        resource_type = str(resource.get("resourceType") or "Unknown")
        counts[resource_type] = counts.get(resource_type, 0) + 1
    return counts


def _test_criteria() -> list[PipelineTestCriterion]:
    return [
        PipelineTestCriterion(
            key="weighted_f1",
            label="Weighted F1 vs verified ground truth",
            target="Primary ranked score when a reviewed ground-truth bundle exists",
            measurement=(
                "Extracted facts are normalized by resource type and matched against the "
                "truth bundle. F1 is computed per resource type, then weighted by truth "
                "fact count so high-volume facts like labs influence the headline score."
            ),
            why_it_matters="Measures clinical fact agreement, not just whether a Bundle was emitted.",
        ),
        PipelineTestCriterion(
            key="downstream_answer_quality",
            label="Downstream answer quality",
            target="Primary clinical-task score once question-answer eval sets are available",
            measurement=(
                "A fixed question set is answered from each pipeline's output. Responses "
                "are graded for correctness, evidence citation, abstention on missing data, "
                "and whether the answer changes the clinical handoff appropriately."
            ),
            why_it_matters=(
                "This is the outcome metric. Extraction scores explain why a pipeline did "
                "well or poorly, but the product succeeds only if the model can answer the "
                "clinical question from the produced record."
            ),
        ),
        PipelineTestCriterion(
            key="loinc_resolution_rate",
            label="LOINC resolution rate",
            target="Observation coding completeness",
            measurement="Fraction of Observations that include at least one LOINC coding entry.",
            why_it_matters="Lab facts are much more useful downstream when they can be queried by canonical code.",
        ),
        PipelineTestCriterion(
            key="patient_link_rate",
            label="Patient linkage rate",
            target="Single-patient record integrity",
            measurement=(
                "Fraction of subject/patient/beneficiary references that resolve to the "
                "actual Patient.id in the emitted Bundle."
            ),
            why_it_matters="Prevents orphaned facts and cross-patient contamination in harmonization.",
        ),
        PipelineTestCriterion(
            key="encounter_link_rate",
            label="Encounter linkage rate",
            target="Timeline reconstruction quality",
            measurement="Fraction of encounter-scopable resources that carry an encounter reference.",
            why_it_matters="Allows extracted facts to land in the right clinical visit or document context.",
        ),
        PipelineTestCriterion(
            key="latency_ms",
            label="Wall-clock latency",
            target="Pipeline speed",
            measurement="Elapsed time from run start to finish, including parallel LLM/tool calls.",
            why_it_matters="Separates interactive candidates from slower offline enrichment lanes.",
        ),
        PipelineTestCriterion(
            key="cost_usd",
            label="Estimated model/tool cost",
            target="Cost per PDF",
            measurement="Sum of logged pass usage cost when available, otherwise pipeline estimate.",
            why_it_matters="Lets us compare quality improvements against marginal extraction cost.",
        ),
        PipelineTestCriterion(
            key="artifact_completeness",
            label="Artifact completeness",
            target="Reviewability and reproducibility",
            measurement="Presence of source PDF, manifest, output Bundle, shape metrics, eval metrics, and traces.",
            why_it_matters="A pipeline result only helps iteration if we can inspect and reproduce it later.",
        ),
    ]


def _trace_count(run_dir: Path) -> int:
    traces_dir = run_dir / "traces"
    if not traces_dir.exists():
        return 0
    return sum(1 for child in traces_dir.iterdir() if child.is_dir())


def _artifact_urls(root: Path, run_id: str) -> dict[str, str]:
    root_rel = quote(str(root.relative_to(REPO_ROOT)))
    base = f"/api/pipeline-lab/runs/{quote(run_id)}/artifacts"
    urls: dict[str, str] = {}
    for key in ("manifest", "bundle", "eval", "bundle_shape", "source_pdf", "ground_truth"):
        urls[key] = f"{base}/{key}?root={root_rel}"
    return urls


def _evaluation_artifact_urls(summary: EvaluationResult) -> dict[str, str]:
    base = f"/api/pipeline-lab/evaluations/{quote(summary.eval_run_id)}/artifacts"
    urls = {
        "manifest": f"{base}/manifest",
        "suite": f"{base}/suite",
        "pipeline_run_ref": f"{base}/pipeline_run_ref",
        "context": f"{base}/context",
        "summary": f"{base}/summary",
    }
    for question in summary.question_results:
        qid = quote(question.question_id)
        urls[f"question:{question.question_id}:prompt"] = f"{base}/prompt?question_id={qid}"
        urls[f"question:{question.question_id}:answer"] = f"{base}/answer?question_id={qid}"
        urls[f"question:{question.question_id}:grade"] = f"{base}/grade?question_id={qid}"
        urls[f"question:{question.question_id}:evidence"] = f"{base}/evidence?question_id={qid}"
    return urls


def _safe_lab_root(root: str) -> Path:
    root_path = (REPO_ROOT / root).resolve()
    allowed = {
        (REPO_ROOT / "data" / "pdf-lab").resolve(),
        (REPO_ROOT / "data" / "local-model-lab").resolve(),
    }
    if root_path not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported lab root")
    return root_path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _float_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _avg_int(values: list[int]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def _avg_float(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _suite_created_at(suite_run_id: str) -> str | None:
    prefix = suite_run_id.split("_", 1)[0]
    return prefix + "Z" if "T" in prefix else None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
