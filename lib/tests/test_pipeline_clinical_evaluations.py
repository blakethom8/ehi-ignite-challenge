from __future__ import annotations

import json
from pathlib import Path

from lib.extract.lab.evaluations import (
    DeterministicAnswerGrader,
    DeterministicClinicalQuestionRunner,
    FhirBundleContextBuilder,
    run_evaluation_for_pipeline_run,
)
from lib.extract.lab.evaluations.deterministic import DEFAULT_CLINICAL_QA_SUITE


def test_deterministic_renal_smoke_eval_scores_supported_answer(tmp_path: Path) -> None:
    run_dir = _write_run(
        tmp_path,
        bundle={
            "resourceType": "Bundle",
            "type": "document",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "creatinine",
                        "status": "final",
                        "code": {
                            "text": "Creatinine",
                            "coding": [{"system": "http://loinc.org", "code": "2160-0"}],
                        },
                        "valueQuantity": {"value": 1.8, "unit": "mg/dL"},
                        "interpretation": [{"coding": [{"code": "H"}]}],
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "egfr",
                        "status": "final",
                        "code": {
                            "text": "eGFR",
                            "coding": [{"system": "http://loinc.org", "code": "33914-3"}],
                        },
                        "valueQuantity": {"value": 42, "unit": "mL/min/1.73m2"},
                        "interpretation": [{"coding": [{"code": "L"}]}],
                    }
                },
            ],
        },
    )

    result = run_evaluation_for_pipeline_run(
        run_dir=run_dir,
        lab_root=tmp_path / "lab",
        eval_root=tmp_path / "evals",
    )

    assert result.status == "succeeded"
    assert result.overall_score == 1.0
    assert result.question_results[0].abstained is False
    assert result.question_results[0].citation_count == 2
    assert result.bundle_stats["lab_like_observation_count"] == 2
    assert (tmp_path / "evals" / "runs" / result.eval_run_id / "questions").exists()


def test_deterministic_renal_smoke_eval_rewards_abstention_when_evidence_missing() -> None:
    context = FhirBundleContextBuilder().build_context(
        {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "sodium",
                        "code": {
                            "text": "Sodium",
                            "coding": [{"system": "http://loinc.org", "code": "2951-2"}],
                        },
                        "valueQuantity": {"value": 137, "unit": "mmol/L"},
                    }
                }
            ],
        }
    )
    test_case = DEFAULT_CLINICAL_QA_SUITE.test_cases[0]
    runner = DeterministicClinicalQuestionRunner()
    prompt = runner.build_prompt(test_case=test_case, context=context)
    answer = runner.answer_question(test_case=test_case, context=context, prompt=prompt)
    grade = DeterministicAnswerGrader().grade_answer(
        test_case=test_case,
        context=context,
        answer=answer,
    )

    assert answer.abstained is True
    assert answer.citations == []
    assert grade.correctness == 1.0
    assert grade.abstention_quality == 1.0
    assert grade.unsupported_claims == []


def _write_run(tmp_path: Path, *, bundle: dict) -> Path:
    run_dir = tmp_path / "lab" / "runs" / "test-run"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "test-run",
                "pipeline_name": "fixture-pipeline",
                "pdf_path": "/tmp/source.pdf",
                "pdf_sha256": "abc123",
                "started_at": "2026-05-09T00:00:00Z",
                "finished_at": "2026-05-09T00:00:01Z",
                "status": "succeeded",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    return run_dir
