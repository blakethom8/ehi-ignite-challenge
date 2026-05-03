"""Cursor sidecar path: FastAPI orchestrates chart evidence; Node runs `@cursor/sdk`."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from api.core.cursor_sidecar_client import CursorSidecarClient, CursorSidecarHttpError
from api.core.provider_assistant import AssistantCitationPayload, AssistantResult, get_relevant_provider_evidence
from api.core.tracing import SpanKind, start_span


class CursorSidecarConfigurationError(RuntimeError):
    """Sidecar URL, allowlist, or environment misconfigured."""


class CursorSidecarExecutionError(RuntimeError):
    """Sidecar returned an error response or unparseable payload."""


def _parse_allowlist() -> set[str] | None:
    raw = (os.getenv("CURSOR_SIDECAR_MODEL_ALLOWLIST") or "").strip()
    if not raw:
        return None
    return {p.strip() for p in raw.split(",") if p.strip()}


def _resolve_cursor_model(requested: str | None) -> str:
    default = (os.getenv("CURSOR_SIDECAR_MODEL") or "composer-2").strip() or "composer-2"
    candidate = (requested or default).strip() or default
    allow = _parse_allowlist()
    if allow is not None and candidate not in allow:
        raise CursorSidecarConfigurationError(
            f"cursor model not allowed: {candidate}; allowlist: {sorted(allow)}",
        )
    return candidate


def _citation_from_baseline_item(item: dict[str, Any]) -> AssistantCitationPayload | None:
    source_type = str(item.get("source_type", "")).strip()
    resource_id = str(item.get("resource_id", "")).strip()
    if not source_type or not resource_id:
        return None
    event_date: datetime | None = None
    raw_ed = item.get("event_date")
    if isinstance(raw_ed, str) and raw_ed.strip():
        try:
            event_date = datetime.fromisoformat(raw_ed)
        except ValueError:
            event_date = None
    return AssistantCitationPayload(
        source_type=source_type,
        resource_id=resource_id,
        label=str(item.get("label", "")).strip() or resource_id,
        detail=str(item.get("detail", "")).strip() or "No detail provided.",
        event_date=event_date,
    )


def _filter_citations_to_baseline(
    parsed_raw: list[dict[str, Any]],
    baseline_keys: dict[tuple[str, str], AssistantCitationPayload],
) -> list[AssistantCitationPayload]:
    citations: list[AssistantCitationPayload] = []
    for item in parsed_raw:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("source_type", "")).strip(),
            str(item.get("resource_id", "")).strip(),
        )
        citation = baseline_keys.get(key)
        if citation and all(
            (existing.source_type, existing.resource_id) != key for existing in citations
        ):
            citations.append(citation)
    if not citations:
        citations = list(baseline_keys.values())[:6]
    return citations


def answer_with_cursor_sidecar(
    *,
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None,
    stance: str,
    cursor_model: str | None = None,
) -> AssistantResult:
    base_url = (os.getenv("CURSOR_SIDECAR_URL") or "").strip()
    if not base_url:
        raise CursorSidecarConfigurationError(
            "CURSOR_SIDECAR_URL is not set (e.g. http://127.0.0.1:3040 for local sidecar).",
        )

    model_resolved = _resolve_cursor_model(cursor_model)

    with start_span(
        SpanKind.RETRIEVAL,
        "cursor_baseline_evidence",
        input_data={"patient_id": patient_id, "question": question},
    ) as ev_span:
        baseline = get_relevant_provider_evidence(
            patient_id=patient_id,
            query=question,
            history=history,
            max_facts=8,
            max_citations=8,
        )
        if ev_span:
            ev_span.output_data = json.dumps(
                {"intent": baseline.get("intent"), "citation_count": len(baseline.get("citations", []))},
                default=str,
            )

    baseline_keys: dict[tuple[str, str], AssistantCitationPayload] = {}
    for item in baseline.get("citations", []):
        if not isinstance(item, dict):
            continue
        c = _citation_from_baseline_item(item)
        if c is not None:
            baseline_keys[(c.source_type, c.resource_id)] = c

    payload: dict[str, Any] = {
        "patient_id": patient_id,
        "question": question,
        "stance": stance,
        "history": history or [],
        "baseline_evidence": baseline,
        "model": model_resolved,
    }

    client = CursorSidecarClient(base_url=base_url)
    if not client.health():
        raise CursorSidecarConfigurationError(
            f"cursor-sidecar not reachable at {base_url} (GET /health failed).",
        )

    with start_span(
        SpanKind.LLM,
        "cursor_sidecar_invoke",
        input_data={"model": model_resolved, "patient_id": patient_id, "stance": stance},
    ) as llm_span:
        try:
            out = client.invoke(payload)
        except CursorSidecarHttpError as exc:
            if llm_span:
                llm_span.error = str(exc)
            if exc.status_code in (400, 503) or exc.error_code == "config":
                raise CursorSidecarConfigurationError(str(exc)) from exc
            raise CursorSidecarExecutionError(str(exc)) from exc

        if llm_span:
            llm_span.output_data = json.dumps(
                {"model_used": out.model_used, "run_id": out.run_id, "duration_ms": out.duration_ms},
                default=str,
            )
            llm_span.num_turns = 1

    citations = _filter_citations_to_baseline(out.citations, baseline_keys)
    raw_fu = baseline.get("follow_ups", [])
    fallback_fu: list[str] = []
    if isinstance(raw_fu, list):
        fallback_fu = [str(x).strip() for x in raw_fu if str(x).strip()][:3]

    return AssistantResult(
        answer=out.answer,
        confidence=out.confidence if out.confidence in {"high", "medium", "low"} else "medium",
        citations=citations,
        follow_ups=(out.follow_ups or [])[:3] or fallback_fu,
        engine=out.engine,
        model_used=out.model_used or model_resolved,
        mode_used="cursor",
    )
