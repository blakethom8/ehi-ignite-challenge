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


def _client_overrides_enabled() -> bool:
    default = os.getenv("ENVIRONMENT", "development").strip().lower() not in {"prod", "production"}
    return _env_bool("PROVIDER_ASSISTANT_ALLOW_CLIENT_OVERRIDES", default)


def _max_response_tokens() -> int:
    raw = os.getenv("PROVIDER_ASSISTANT_MAX_RESPONSE_TOKENS", "2000")
    try:
        value = int(raw)
    except ValueError:
        return 2000
    return min(max(value, 128), 4000)


def _assistant_mode() -> str:
    return os.getenv("PROVIDER_ASSISTANT_MODE", "deterministic").strip().lower()


def answer_provider_question(
    *,
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None,
    stance: str,
    model_override: str | None = None,
    mode_override: str | None = None,
    max_tokens_override: int | None = None,
) -> AssistantResult:
    """
    Unified provider-assistant entry point.

    Modes:
    - deterministic (default) — rule-based keyword matching, no LLM
    - context (recommended) — clean context + single Claude call (~3-5s)
    - anthropic (alias: agent_sdk) — multi-turn agent loop (~15-30s)
    """
    if not _client_overrides_enabled():
        model_override = None
        mode_override = None
        max_tokens_override = None
    elif max_tokens_override is not None:
        max_tokens_override = min(max_tokens_override, _max_response_tokens())

    mode = (mode_override or "").strip().lower() or _assistant_mode()
    fallback_enabled = _env_bool("PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC", True)

    # Context mode: single-turn Claude call with pre-built clinical context
    if mode in {"context", "context_single_turn", "single_turn"}:
        try:
            from api.core.provider_assistant_context import answer_with_context

            result = answer_with_context(
                patient_id=patient_id,
                question=question,
                history=history,
                stance=stance,
                model_override=model_override,
                max_tokens_override=max_tokens_override,
            )
            _record_trace_metadata(result)
            return result
        except Exception as exc:
            if not fallback_enabled:
                raise RuntimeError(f"Context mode failed: {exc}") from exc
            LOGGER.warning("Context mode failed (%s). Falling back to deterministic.", str(exc))
            fallback = answer_deterministic(
                patient_id=patient_id,
                question=question,
                history=history,
                stance=stance,
            )
            fallback.engine = "deterministic-fallback"
            _record_trace_metadata(fallback)
            return fallback

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
