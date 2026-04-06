"""
Provider assistant mode selector.

Chooses deterministic or Anthropic Agent SDK runtime based on environment.
"""

from __future__ import annotations

import logging
import os

from api.core.provider_assistant import AssistantResult, answer_provider_question as answer_deterministic


LOGGER = logging.getLogger(__name__)


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
        from api.core.provider_assistant_agent_sdk import (
            AgentConfigurationError,
            AgentExecutionError,
            answer_provider_question_with_agent_sdk,
        )

        try:
            return answer_provider_question_with_agent_sdk(
                patient_id=patient_id,
                question=question,
                history=history,
                stance=stance,
            )
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
            return fallback

    return answer_deterministic(
        patient_id=patient_id,
        question=question,
        history=history,
        stance=stance,
    )
