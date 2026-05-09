"""Swappable interfaces for clinical QA evaluation components."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from lib.extract.lab.evaluations.models import (
    ClinicalAnswer,
    ClinicalContext,
    ClinicalQATestCase,
    QuestionGrade,
)


@runtime_checkable
class ContextBuilder(Protocol):
    """Build a model-ready clinical context from a pipeline Bundle."""

    name: str

    def build_context(self, bundle: dict[str, Any]) -> ClinicalContext:
        ...


@runtime_checkable
class ClinicalQuestionRunner(Protocol):
    """Answer one clinical question from a built clinical context."""

    name: str
    prompt_template_id: str
    answer_model: str

    def build_prompt(
        self,
        *,
        test_case: ClinicalQATestCase,
        context: ClinicalContext,
    ) -> str:
        ...

    def answer_question(
        self,
        *,
        test_case: ClinicalQATestCase,
        context: ClinicalContext,
        prompt: str,
    ) -> ClinicalAnswer:
        ...


@runtime_checkable
class AnswerGrader(Protocol):
    """Grade a clinical answer against a test case and available evidence."""

    name: str

    def grade_answer(
        self,
        *,
        test_case: ClinicalQATestCase,
        context: ClinicalContext,
        answer: ClinicalAnswer,
    ) -> QuestionGrade:
        ...
