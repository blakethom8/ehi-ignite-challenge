"""Downstream clinical QA evaluation harness for PDF-to-FHIR lab runs."""

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
    ClinicalQATestCase,
    EvaluationManifest,
    EvaluationResult,
    EvaluationSuite,
    EvidenceCitation,
    PipelineRunRef,
    QuestionEvaluationResult,
    QuestionGrade,
)
from lib.extract.lab.evaluations.runner import run_evaluation_for_pipeline_run
from lib.extract.lab.evaluations.store import (
    DEFAULT_EVAL_ROOT,
    list_evaluation_summaries,
    load_evaluation_summary,
)

__all__ = [
    "AnswerGrader",
    "ClinicalAnswer",
    "ClinicalContext",
    "ClinicalQATestCase",
    "ClinicalQuestionRunner",
    "ContextBuilder",
    "DEFAULT_CLINICAL_QA_SUITE",
    "DEFAULT_EVAL_ROOT",
    "DeterministicAnswerGrader",
    "DeterministicClinicalQuestionRunner",
    "EvaluationManifest",
    "EvaluationResult",
    "EvaluationSuite",
    "EvidenceCitation",
    "FhirBundleContextBuilder",
    "PipelineRunRef",
    "QuestionEvaluationResult",
    "QuestionGrade",
    "list_evaluation_summaries",
    "load_evaluation_summary",
    "run_evaluation_for_pipeline_run",
]
