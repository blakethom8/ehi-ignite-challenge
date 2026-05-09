"""Evaluation runner that writes durable clinical QA artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import time
from pathlib import Path
from typing import Any

from lib.extract.lab.evaluations.deterministic import (
    DEFAULT_CLINICAL_QA_SUITE,
    DeterministicAnswerGrader,
    DeterministicClinicalQuestionRunner,
    FhirBundleContextBuilder,
)
from lib.extract.lab.evaluations.interfaces import (
    AnswerGrader,
    ClinicalQuestionRunner,
    ContextBuilder,
)
from lib.extract.lab.evaluations.models import (
    ClinicalAnswer,
    ClinicalContext,
    EvaluationManifest,
    EvaluationResult,
    EvaluationSuite,
    PipelineRunRef,
    QuestionEvaluationResult,
    QuestionGrade,
    utc_now_iso,
)
from lib.extract.lab.evaluations.store import (
    DEFAULT_EVAL_ROOT,
    atomic_write_json,
    load_json,
    relative_to_repo,
    write_text,
)


def run_evaluation_for_pipeline_run(
    *,
    run_dir: Path,
    lab_root: Path,
    suite: EvaluationSuite | None = None,
    context_builder: ContextBuilder | None = None,
    question_runner: ClinicalQuestionRunner | None = None,
    answer_grader: AnswerGrader | None = None,
    eval_root: Path | None = None,
) -> EvaluationResult:
    """Run a clinical QA suite against a saved pipeline run directory.

    The default implementation is fully deterministic and has no model or
    network dependency. LLM-backed implementations can be passed via the
    interfaces above without changing artifact layout.
    """
    effective_suite = suite or DEFAULT_CLINICAL_QA_SUITE
    effective_context_builder = context_builder or FhirBundleContextBuilder()
    effective_question_runner = question_runner or DeterministicClinicalQuestionRunner()
    effective_answer_grader = answer_grader or DeterministicAnswerGrader()
    effective_eval_root = eval_root or DEFAULT_EVAL_ROOT

    manifest_data = load_json(run_dir / "manifest.json")
    bundle = load_json(run_dir / "bundle.json")
    if not isinstance(manifest_data, dict) or not manifest_data:
        raise FileNotFoundError(f"Missing manifest.json for pipeline run: {run_dir}")
    if not isinstance(bundle, dict) or not bundle:
        raise FileNotFoundError(f"Missing bundle.json for pipeline run: {run_dir}")

    pipeline_ref = _pipeline_run_ref(
        run_dir=run_dir,
        lab_root=lab_root,
        manifest=manifest_data,
    )
    eval_run_id = _make_eval_run_id(
        pipeline_run_id=pipeline_ref.run_id,
        suite_id=effective_suite.suite_id,
    )
    eval_dir = effective_eval_root / "runs" / eval_run_id
    start = time.perf_counter()

    manifest = EvaluationManifest(
        eval_run_id=eval_run_id,
        suite_id=effective_suite.suite_id,
        suite_name=effective_suite.name,
        suite_version=effective_suite.version,
        pipeline_run=pipeline_ref,
        context_builder=effective_context_builder.name,
        question_runner=effective_question_runner.name,
        answer_grader=effective_answer_grader.name,
        question_count=len(effective_suite.test_cases),
    )
    atomic_write_json(eval_dir / "manifest.json", manifest.model_dump(mode="json"))
    atomic_write_json(eval_dir / "suite.json", effective_suite.model_dump(mode="json"))
    atomic_write_json(eval_dir / "pipeline_run_ref.json", pipeline_ref.model_dump(mode="json"))

    try:
        context = effective_context_builder.build_context(bundle)
        atomic_write_json(eval_dir / "context.json", context.model_dump(mode="json"))

        question_results: list[QuestionEvaluationResult] = []
        answers: list[ClinicalAnswer] = []
        grades: list[QuestionGrade] = []
        for test_case in effective_suite.test_cases:
            prompt = effective_question_runner.build_prompt(test_case=test_case, context=context)
            answer = effective_question_runner.answer_question(
                test_case=test_case,
                context=context,
                prompt=prompt,
            )
            grade = effective_answer_grader.grade_answer(
                test_case=test_case,
                context=context,
                answer=answer,
            )
            answers.append(answer)
            grades.append(grade)
            question_results.append(_question_summary(test_case.title, test_case.safety_critical, answer, grade))

            question_dir = eval_dir / "questions" / test_case.test_id
            write_text(question_dir / "prompt.txt", prompt)
            atomic_write_json(question_dir / "answer.json", answer.model_dump(mode="json"))
            atomic_write_json(question_dir / "grade.json", grade.model_dump(mode="json"))
            cited = [item for item in context.evidence if item.citation_id in set(answer.citations)]
            atomic_write_json(
                question_dir / "evidence.json",
                {
                    "question_id": test_case.test_id,
                    "cited_evidence": [item.model_dump(mode="json") for item in cited],
                    "available_evidence_count": len(context.evidence),
                },
            )

        latency_ms = round((time.perf_counter() - start) * 1000)
        manifest.finished_at = utc_now_iso()
        manifest.status = "succeeded"
        manifest.latency_ms = latency_ms
        manifest.cost_usd = round(sum(answer.cost_usd for answer in answers), 6)
        result = _evaluation_summary(
            manifest=manifest,
            context=context,
            grades=grades,
            question_results=question_results,
        )
        atomic_write_json(eval_dir / "summary.json", result.model_dump(mode="json"))
        atomic_write_json(eval_dir / "manifest.json", manifest.model_dump(mode="json"))
        _append_jsonl(effective_eval_root / "runs.jsonl", result.model_dump(mode="json"))
        return result
    except Exception as exc:
        manifest.finished_at = utc_now_iso()
        manifest.status = "failed"
        manifest.error = str(exc)
        manifest.latency_ms = round((time.perf_counter() - start) * 1000)
        atomic_write_json(eval_dir / "manifest.json", manifest.model_dump(mode="json"))
        raise


def _pipeline_run_ref(*, run_dir: Path, lab_root: Path, manifest: dict[str, Any]) -> PipelineRunRef:
    root = lab_root.resolve()
    pdf_path = str(manifest.get("pdf_path") or "")
    ground_truth = manifest.get("ground_truth_path")
    return PipelineRunRef(
        run_id=str(manifest.get("run_id") or run_dir.name),
        lab_root=relative_to_repo(root),
        artifact_dir=relative_to_repo(run_dir),
        pipeline_name=str(manifest.get("pipeline_name") or "unknown"),
        pdf_path=pdf_path,
        pdf_label=Path(pdf_path).name if pdf_path else "unknown",
        pdf_sha256=manifest.get("pdf_sha256"),
        manifest_path=relative_to_repo(run_dir / "manifest.json"),
        bundle_path=relative_to_repo(run_dir / "bundle.json"),
        bundle_shape_path=relative_to_repo(run_dir / "bundle_shape.json")
        if (run_dir / "bundle_shape.json").exists()
        else None,
        eval_path=relative_to_repo(run_dir / "eval.json") if (run_dir / "eval.json").exists() else None,
        ground_truth_path=str(ground_truth) if ground_truth else None,
    )


def _make_eval_run_id(*, pipeline_run_id: str, suite_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    safe_run = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in pipeline_run_id)[-64:]
    safe_suite = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in suite_id)
    return f"{timestamp}_{safe_suite}_{safe_run}"


def _question_summary(
    title: str,
    safety_critical: bool,
    answer: ClinicalAnswer,
    grade: QuestionGrade,
) -> QuestionEvaluationResult:
    return QuestionEvaluationResult(
        question_id=grade.question_id,
        title=title,
        safety_critical=safety_critical,
        abstained=answer.abstained,
        score=grade.score,
        correctness=grade.correctness,
        evidence_citation_quality=grade.evidence_citation_quality,
        hallucination_avoidance=grade.hallucination_avoidance,
        abstention_quality=grade.abstention_quality,
        clinical_usefulness=grade.clinical_usefulness,
        citation_count=len(answer.citations),
        unsupported_claim_count=len(grade.unsupported_claims),
        answer_model=answer.answer_model,
        answer_latency_ms=answer.latency_ms,
        tool_call_count=answer.tool_call_count,
        missing_required_evidence_types=grade.missing_required_evidence_types,
    )


def _evaluation_summary(
    *,
    manifest: EvaluationManifest,
    context: ClinicalContext,
    grades: list[QuestionGrade],
    question_results: list[QuestionEvaluationResult],
) -> EvaluationResult:
    question_count = len(question_results)
    unsupported_claim_count = sum(result.unsupported_claim_count for result in question_results)
    total_claim_slots = max(question_count, 1)
    return EvaluationResult(
        eval_run_id=manifest.eval_run_id,
        suite_id=manifest.suite_id,
        suite_name=manifest.suite_name,
        suite_version=manifest.suite_version,
        created_at=manifest.created_at,
        finished_at=manifest.finished_at,
        status=manifest.status,
        pipeline_run=manifest.pipeline_run,
        question_count=question_count,
        safety_critical_count=sum(1 for item in question_results if item.safety_critical),
        overall_score=_mean([grade.score for grade in grades]),
        mean_correctness=_mean([grade.correctness for grade in grades]),
        mean_evidence_citation_quality=_mean([grade.evidence_citation_quality for grade in grades]),
        mean_hallucination_avoidance=_mean([grade.hallucination_avoidance for grade in grades]),
        mean_abstention_quality=_mean([grade.abstention_quality for grade in grades]),
        unsupported_claim_rate=round(unsupported_claim_count / total_claim_slots, 4),
        abstention_rate=round(sum(1 for item in question_results if item.abstained) / question_count, 4)
        if question_count
        else None,
        latency_ms=manifest.latency_ms,
        cost_usd=manifest.cost_usd,
        bundle_stats=context.bundle_stats,
        question_results=question_results,
    )


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, default=str) + "\n")
