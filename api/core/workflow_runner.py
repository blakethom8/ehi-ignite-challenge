"""
Caspian workflow runner — execute a prepared workflow packet against a patient
chart and return a structured artifact for the workbench.

A workflow packet (data/workflows/<id>.json) declares:
  - instructions: the prompt body the agent reads
  - output_schema: a freeform JSON sketch the agent fills in

The runner assembles the same clinical context the chat path uses, asks Claude
to fill in the artifact schema, and returns a validated WorkflowArtifact plus
the deterministic citations the rest of Caspian already knows how to render
(inspector chips, FHIR resource lookups, etc.).

Single-turn, ~3-5s. Designed to slot into the existing tracing pipeline so the
Inspector → Trace tab shows the workflow run with the same fidelity as a chat.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path: str | Path) -> dict:  # type: ignore[misc]
        return {}

from api.core.context_builder import build_clinical_context
from api.core.provider_assistant import _collect_citations, _rank_relevant_facts
from api.core.tracing import SpanKind, start_span
from api.core import caspian_workspace
from api.core.auth import SessionPrincipal
from api.models import (
    ProviderAssistantCitation,
    WorkflowArtifact,
    WorkflowBanner,
    WorkflowFactCell,
    WorkflowNarrativeSection,
    WorkflowTableSection,
)

LOGGER = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOWS_DIR = _REPO_ROOT / "data" / "workflows"
_ENV_PATH = _REPO_ROOT / ".env"


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowRunError(RuntimeError):
    pass


def _resolve_api_key() -> str:
    env_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if env_key and "YOUR_KEY_HERE" not in env_key:
        return env_key
    if _ENV_PATH.exists():
        file_key = (dotenv_values(_ENV_PATH).get("ANTHROPIC_API_KEY") or "").strip()
        if file_key and "YOUR_KEY_HERE" not in file_key:
            return file_key
    return env_key


def load_packet(workflow_id: str) -> dict[str, Any]:
    """Load a workflow packet from disk. Raises WorkflowNotFoundError on miss."""
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "", workflow_id)
    if safe_id != workflow_id:
        raise WorkflowNotFoundError(f"invalid workflow id: {workflow_id!r}")
    path = _WORKFLOWS_DIR / f"{workflow_id}.json"
    if not path.exists():
        raise WorkflowNotFoundError(f"workflow not found: {workflow_id}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


_SYSTEM_PREAMBLE = """You are Caspian, a clinical chart assistant. The clinician has run a prepared review workflow over a single patient's chart.

Your job is to fill in the workflow's structured artifact based ONLY on the patient chart context provided below. Do not invent values. If a needed datum is missing from the chart, declare the absence (use "—" in table cells, mention it in the narrative, and surface it as an open question rather than fabricating).

OUTPUT FORMAT:
Return a single JSON object — no prose before or after, no markdown fence, no commentary. The object MUST conform to the schema described in the workflow packet and the rules below.

Schema rules:
- `banner.status` must be one of the literal options listed in the packet (e.g. "clear", "review", "hold").
- `banner.label` is a 2-4 word category tag in UPPER CASE with a middle dot, e.g. "REVIEW · ANTICOAGULATION".
- `banner.headline` is one sentence ≤ 120 chars stating the disposition.
- `banner.action_label` is a 1-3 word button label (e.g. "Approve hold", "Acknowledge").
- `fact_rail` is an array of exactly 5 cells with `label` and `value`. Use "—" for unknown values.
- `sections` is an array; each element has `kind`: "table" or "narrative".
  - For `kind: "table"`: include `title`, `columns` (array of header strings), and `rows` (array of rows, each row an array of strings with the same length as `columns`).
  - For `kind: "narrative"`: include `title` and `body` (markdown-safe plain text).
  - If a table has no rows from the chart, include the section anyway with `rows: []` and `empty_note` set to a one-line explanation.
- `chat_narration` is ≤ 2 sentences naming the workflow result and top concern.

Citations:
- Where a finding ties to a specific medication, lab, condition, or encounter, include the resource type and identifier inline in the cell as text like `MedicationRequest:abc-123` or `Observation:def-456`. The frontend will resolve these into clickable chips.
"""


def _format_packet_for_prompt(packet: dict[str, Any]) -> str:
    title = packet.get("title", "Workflow review")
    workflow_type = packet.get("type", "Workflow")
    instructions = (packet.get("instructions") or "").strip()
    output_schema = packet.get("output_schema") or {}
    schema_text = json.dumps(output_schema, indent=2)
    return (
        f"## Workflow: {title}\n"
        f"Type: {workflow_type}\n\n"
        f"### Instructions\n{instructions}\n\n"
        f"### Output schema (sketch — return JSON matching this shape)\n"
        f"```\n{schema_text}\n```"
    )


def _extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of the model's response.

    Tolerates an accidental code fence or leading prose, since strict JSON-only
    output isn't always honored even with explicit instructions.
    """
    stripped = text.strip()
    # Strip ```json … ``` fences.
    if stripped.startswith("```"):
        fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", stripped, re.DOTALL)
        if fence_match:
            stripped = fence_match.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        first = stripped.find("{")
        last = stripped.rfind("}")
        if first == -1 or last == -1 or last <= first:
            raise WorkflowRunError("Model did not return a JSON object")
        try:
            return json.loads(stripped[first : last + 1])
        except json.JSONDecodeError as exc:
            raise WorkflowRunError(f"Could not parse workflow JSON: {exc}") from exc


def _coerce_artifact(
    raw: dict[str, Any],
    *,
    workflow_id: str,
    packet: dict[str, Any],
    generated_at: datetime,
) -> WorkflowArtifact:
    banner_raw = raw.get("banner") or {}
    fact_rail_raw = raw.get("fact_rail") or []
    sections_raw = raw.get("sections") or []

    sections: list[WorkflowTableSection | WorkflowNarrativeSection] = []
    for section in sections_raw:
        if not isinstance(section, dict):
            continue
        kind = section.get("kind")
        if kind == "table":
            cols = [str(c) for c in (section.get("columns") or [])]
            row_count = len(cols) or 1
            rows: list[list[str]] = []
            for row in section.get("rows") or []:
                if not isinstance(row, list):
                    continue
                normalized = [
                    "—" if cell is None else str(cell)
                    for cell in row
                ]
                # pad / truncate so every row matches column count
                if len(normalized) < row_count:
                    normalized = normalized + ["—"] * (row_count - len(normalized))
                else:
                    normalized = normalized[:row_count]
                rows.append(normalized)
            sections.append(
                WorkflowTableSection(
                    title=str(section.get("title") or "Untitled"),
                    columns=cols or ["Item"],
                    rows=rows,
                    empty_note=(section.get("empty_note") or None),
                )
            )
        elif kind == "narrative":
            body = str(section.get("body") or "").strip() or "—"
            sections.append(
                WorkflowNarrativeSection(
                    title=str(section.get("title") or "Untitled"),
                    body=body,
                )
            )

    fact_rail: list[WorkflowFactCell] = []
    for cell in fact_rail_raw[:8]:
        if not isinstance(cell, dict):
            continue
        label = str(cell.get("label") or "").strip()
        value = str(cell.get("value") or "—").strip() or "—"
        if not label:
            continue
        tone_raw = cell.get("tone")
        tone = tone_raw if tone_raw in {"default", "tier", "caution"} else "default"
        fact_rail.append(WorkflowFactCell(label=label[:40], value=value[:80], tone=tone))

    banner = WorkflowBanner(
        status=banner_raw.get("status") or _default_status(workflow_id),
        label=str(banner_raw.get("label") or packet.get("type") or "Review")[:80],
        headline=str(banner_raw.get("headline") or "Workflow complete.")[:240],
        action_label=(str(banner_raw.get("action_label"))[:40] if banner_raw.get("action_label") else None),
    )

    narration = str(raw.get("chat_narration") or "").strip()
    if not narration:
        narration = f"{packet.get('title', 'Workflow')} complete."
    narration = narration[:400]

    artifact_id = f"workflow:{workflow_id}:{generated_at.strftime('%Y%m%dT%H%M%S')}:{uuid.uuid4().hex[:6]}"

    return WorkflowArtifact(
        workflow_id=workflow_id,
        workflow_title=str(packet.get("title") or workflow_id),
        workflow_type=str(packet.get("type") or "Workflow"),
        artifact_id=artifact_id,
        generated_at=generated_at,
        banner=banner,
        fact_rail=fact_rail,
        sections=sections,
        chat_narration=narration,
    )


def _default_status(workflow_id: str) -> str:
    if workflow_id == "medication_safety_v1":
        return "review"
    if workflow_id == "longitudinal_synthesis_v1":
        return "stable"
    return "review"


def _citations_for_followup(
    *,
    patient_id: str,
    workflow_id: str,
    narration: str,
) -> list[ProviderAssistantCitation]:
    """Pull the same evidence chips the chat path would surface for a related question.

    This piggybacks on the existing rank_relevant_facts + _collect_citations
    pipeline so the inspector resolves citations identically to the chat surface.
    The workflow-specific intent keywords drive the ranking toward the right
    bucket of facts.
    """
    intent_query = {
        "preop_review_v1": "pre-op clearance bleeding anticoagulant labs",
        "medication_safety_v1": "drug interactions allergy renal dosing duplicate",
        "longitudinal_synthesis_v1": "trajectory longitudinal conditions encounters",
    }.get(workflow_id, narration)
    _intent, ranked, _summary = _rank_relevant_facts(
        patient_id=patient_id,
        question=intent_query,
        history=None,
        max_items=12,
    )
    citation_payloads = _collect_citations(ranked, max_items=8)
    return [
        ProviderAssistantCitation(
            source_type=c.source_type,
            resource_id=c.resource_id,
            label=c.label,
            detail=c.detail,
            event_date=c.event_date,
        )
        for c in citation_payloads
    ]


def _artifact_to_markdown(artifact: WorkflowArtifact) -> str:
    """Serialize a WorkflowArtifact to human-readable markdown for the files pane."""
    lines: list[str] = []
    lines.append(f"# {artifact.workflow_title}")
    lines.append("")
    lines.append(
        f"**Workflow:** `{artifact.workflow_id}` ({artifact.workflow_type})  "
    )
    lines.append(
        f"**Generated:** {artifact.generated_at.strftime('%Y-%m-%d %H:%M UTC')}  "
    )
    lines.append(f"**Status:** `{artifact.banner.status}` — {artifact.banner.label}")
    lines.append("")
    lines.append(f"> {artifact.banner.headline}")
    lines.append("")
    if artifact.fact_rail:
        lines.append("## At a glance")
        lines.append("")
        lines.append("| " + " | ".join(c.label for c in artifact.fact_rail) + " |")
        lines.append("|" + "|".join(["---"] * len(artifact.fact_rail)) + "|")
        lines.append("| " + " | ".join(c.value for c in artifact.fact_rail) + " |")
        lines.append("")
    for section in artifact.sections:
        if section.kind == "table":
            lines.append(f"## {section.title}")
            lines.append("")
            if not section.rows:
                lines.append(section.empty_note or "_no matching items in the chart._")
                lines.append("")
                continue
            lines.append("| " + " | ".join(section.columns) + " |")
            lines.append("|" + "|".join(["---"] * len(section.columns)) + "|")
            for row in section.rows:
                cells = [c.replace("|", "\\|") for c in row]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
        else:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.body)
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"_{artifact.chat_narration}_")
    return "\n".join(lines).rstrip() + "\n"


def _persist_artifact_to_workspace(
    session: SessionPrincipal,
    resolved_patient_id: str,
    artifact: WorkflowArtifact,
) -> str | None:
    """Write the artifact's markdown form to the patient workspace.

    Returns the relative path on success, None if persistence failed (we never
    fail the workflow run because the file write hiccupped — the artifact is
    still useful even if the file copy fails)."""
    try:
        short_id = artifact.artifact_id.rsplit(":", 1)[-1]
        filename = caspian_workspace.workflow_run_filename(
            artifact.workflow_id, artifact.generated_at, short_id
        )
        rel_path = f"workflow-runs/{filename}"
        markdown = _artifact_to_markdown(artifact)
        caspian_workspace.write_workspace_file(
            session, resolved_patient_id, rel_path, markdown
        )
        return rel_path
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Failed to persist workflow artifact: %s", exc)
        return None


def run_workflow(
    *,
    patient_id: str,
    workflow_id: str,
    model_override: str | None = None,
    session: SessionPrincipal | None = None,
) -> tuple[WorkflowArtifact, list[ProviderAssistantCitation]]:
    """Execute a workflow packet against a patient chart.

    Raises:
        WorkflowNotFoundError: if the packet does not exist.
        ValueError: if the patient cannot be loaded (propagates from context_builder).
        WorkflowRunError: if the LLM call fails or returns unparseable output.
    """
    packet = load_packet(workflow_id)
    api_key = _resolve_api_key()
    if not api_key:
        raise WorkflowRunError(
            "ANTHROPIC_API_KEY not set. Set it in .env or the environment to run workflows."
        )

    with start_span(
        SpanKind.RETRIEVAL,
        "build_clinical_context",
        input_data={"patient_id": patient_id, "workflow_id": workflow_id},
    ) as ctx_span:
        clinical_ctx = build_clinical_context(patient_id)
        context_prompt = clinical_ctx.to_prompt()
        if ctx_span:
            ctx_span.output_data = json.dumps({
                "fact_count": clinical_ctx.fact_count,
                "token_estimate": clinical_ctx.total_tokens_estimate,
            })

    packet_block = _format_packet_for_prompt(packet)
    system_prompt = (
        f"{_SYSTEM_PREAMBLE}\n\n"
        f"PATIENT CHART CONTEXT:\n{context_prompt}\n\n"
        f"{packet_block}"
    )
    user_message = (
        f"Run the '{packet.get('title', workflow_id)}' workflow against this patient. "
        f"Return only the JSON artifact."
    )

    model = model_override or os.getenv("PROVIDER_ASSISTANT_MODEL", "claude-sonnet-4-5")
    max_tokens = 3000

    generated_at = datetime.now(timezone.utc)

    with start_span(
        SpanKind.LLM,
        "workflow_run",
        input_data={
            "model": model,
            "workflow_id": workflow_id,
            "system_prompt": system_prompt,
        },
    ) as llm_span:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        start_time = time.time()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as exc:
            raise WorkflowRunError(f"Anthropic API error: {exc}") from exc
        duration_ms = (time.time() - start_time) * 1000
        text_block = response.content[0].text if response.content else ""
        if llm_span:
            llm_span.input_tokens = response.usage.input_tokens
            llm_span.output_tokens = response.usage.output_tokens
            llm_span.duration_ms = duration_ms
            llm_span.output_data = json.dumps({
                "result_length": len(text_block),
                "stop_reason": response.stop_reason,
                "model": response.model,
            })
            input_cost = response.usage.input_tokens * 3.0 / 1_000_000
            output_cost = response.usage.output_tokens * 15.0 / 1_000_000
            llm_span.total_cost_usd = input_cost + output_cost

    raw_artifact = _extract_json(text_block)
    artifact = _coerce_artifact(
        raw_artifact,
        workflow_id=workflow_id,
        packet=packet,
        generated_at=generated_at,
    )

    citations = _citations_for_followup(
        patient_id=patient_id,
        workflow_id=workflow_id,
        narration=artifact.chat_narration,
    )

    if session is not None:
        artifact.file_path = _persist_artifact_to_workspace(session, patient_id, artifact)

    return artifact, citations
