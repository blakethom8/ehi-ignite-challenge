"""
Provider assistant mode selector.

Chooses deterministic or Anthropic Agent SDK runtime based on environment.
"""

from __future__ import annotations

import logging
import os

from api.core.provider_assistant import AssistantResult, answer_provider_question as answer_deterministic
from api.core.tracing import get_current_trace


LOGGER = logging.getLogger(__name__)


def _record_trace_metadata(result: AssistantResult) -> None:
    """Populate the current trace with response metadata."""
    trace = get_current_trace()
    if trace is None:
        return
    trace.engine = result.engine
    trace.confidence = result.confidence
    trace.answer_preview = result.answer[:500] if result.answer else ""
    trace.answer_length = len(result.answer) if result.answer else 0
    trace.citation_count = len(result.citations) if result.citations else 0
    trace.follow_up_count = len(result.follow_ups) if result.follow_ups else 0
    if "fallback" in (result.engine or ""):
        trace.status = "fallback"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _assistant_mode() -> str:
    return os.getenv("PROVIDER_ASSISTANT_MODE", "deterministic").strip().lower()


def answer_provider_question(
    *,
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None,
    stance: str,
) -> AssistantResult:
    """
    Unified provider-assistant entry point.

    Modes:
    - deterministic (default)
    - anthropic (alias: anthropic_agent, agent_sdk)
    """
    mode = _assistant_mode()
    fallback_enabled = _env_bool("PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC", True)

    if mode in {"anthropic", "anthropic_agent", "agent_sdk", "anthropic_sdk"}:
        try:
            from api.core.provider_assistant_agent_sdk import (
                AgentConfigurationError,
                AgentExecutionError,
                answer_provider_question_with_agent_sdk,
            )

            result = answer_provider_question_with_agent_sdk(
                patient_id=patient_id,
                question=question,
                history=history,
                stance=stance,
            )
            _record_trace_metadata(result)
            return result
        except (AgentConfigurationError, AgentExecutionError) as exc:
            if not fallback_enabled:
                raise
            LOGGER.warning(
                "Anthropic assistant mode failed (%s). Falling back to deterministic mode.",
                str(exc),
            )
            fallback = answer_deterministic(
                patient_id=patient_id,
                question=question,
                history=history,
                stance=stance,
            )
            fallback.engine = "deterministic-fallback"
            _record_trace_metadata(fallback)
            return fallback
        except Exception as exc:  # pragma: no cover - defensive fallback path
            if not fallback_enabled:
                raise RuntimeError(f"Anthropic assistant mode failed: {exc}") from exc
            LOGGER.exception(
                "Unexpected Anthropic assistant failure. Falling back to deterministic mode."
            )
            fallback = answer_deterministic(
                patient_id=patient_id,
                question=question,
                history=history,
                stance=stance,
            )
            fallback.engine = "deterministic-fallback"
            _record_trace_metadata(fallback)
            return fallback

    result = answer_deterministic(
        patient_id=patient_id,
        question=question,
        history=history,
        stance=stance,
    )
    _record_trace_metadata(result)
    return result
