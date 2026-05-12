"""
Virtual `system-context/` files for the Caspian workspace.

These files are rendered live on every read. They reflect *what is actually
in the code right now* — the base system prompt template, the workflow
packets on disk, and the patient chart context as the chat path renders it.

Nothing here is written to disk. The user cannot edit these files; the
workspace's editable surface is `user-instructions.md` + `notes/` + the
workflow-runs/ directory (see caspian_workspace.py).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


_SYSTEM_PROMPT_HEADER = """# Caspian system prompt (read-only)

This is the base system-prompt template Caspian sends to Claude on every chat
turn. The `{context}` slot is filled in with the live patient chart context
(`system-context/patient-chart-context.md` shows what gets injected today).
`{stance}` is the per-request stance ("opinionated" by default). The
`{context_packages}` slot is filled in when the clinician attaches a workflow
packet to the chat turn.

Anything you write in `user-instructions.md` is appended below this template
as a USER OVERRIDES section before the request goes to Claude.

---

"""


def render_caspian_system_prompt() -> str:
    """Return the base _SYSTEM_TEMPLATE so the user can see what's driving the agent."""
    # Imported lazily so this module doesn't pull in anthropic/dotenv at import time.
    from api.core.provider_assistant_context import _SYSTEM_TEMPLATE

    return _SYSTEM_PROMPT_HEADER + _SYSTEM_TEMPLATE


def render_patient_chart_context(resolved_patient_id: str) -> str:
    """Render the exact markdown the chat path passes to Claude for this patient."""
    from api.core.context_builder import build_clinical_context

    try:
        clinical_ctx = build_clinical_context(resolved_patient_id)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("Failed to build clinical context for %s", resolved_patient_id)
        return (
            "# Patient chart context\n\n"
            "_Could not build the chart context for this patient._\n\n"
            f"`{exc.__class__.__name__}`: {exc}\n"
        )

    body = clinical_ctx.to_prompt()
    header = (
        "# Patient chart context (live)\n\n"
        "This is the structured context Caspian feeds into Claude on every chat\n"
        "turn for this patient. It is regenerated from the underlying FHIR data\n"
        "every time you open this file.\n\n"
        f"- fact count: {clinical_ctx.fact_count}\n"
        f"- token estimate: {clinical_ctx.total_tokens_estimate}\n"
        "\n---\n\n"
    )
    return header + body


_WORKFLOWS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "workflows"
)


def _render_packet_markdown(workflow_id: str, packet: dict) -> str:
    title = packet.get("title", workflow_id)
    workflow_type = packet.get("type", "Workflow")
    summary = (packet.get("summary") or "").strip()
    instructions = (packet.get("instructions") or "").strip()
    output_schema = packet.get("output_schema") or {}

    parts: list[str] = [
        f"# {title}",
        "",
        f"**Workflow id:** `{workflow_id}`  ",
        f"**Type:** {workflow_type}",
        "",
        "## Summary",
        summary or "_no summary_",
        "",
        "## Instructions",
        instructions or "_no instructions_",
        "",
        "## Expected output schema",
        "",
        "```json",
        json.dumps(output_schema, indent=2),
        "```",
        "",
        (
            "These files are read-only. They reflect the on-disk packet under "
            "`data/workflows/`. To change a workflow's behavior, edit the JSON file "
            "in the repo (a future iteration will let you author packets in the UI)."
        ),
    ]
    return "\n".join(parts)


def render_workflow_packet(workflow_id: str) -> str:
    packet_path = _WORKFLOWS_DIR / f"{workflow_id}.json"
    if not packet_path.exists():
        return f"# Workflow `{workflow_id}` not found.\n"
    try:
        with packet_path.open("r", encoding="utf-8") as fh:
            packet = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return (
            f"# Workflow `{workflow_id}`\n\n"
            f"_Failed to load packet: {exc}_\n"
        )
    return _render_packet_markdown(workflow_id, packet)


# ---------------------------------------------------------------------------
# Resolver — turns a virtual `system-context/...` path into content
# ---------------------------------------------------------------------------


def render_virtual_file(rel_path: str, resolved_patient_id: str) -> str:
    """Render the file at `rel_path` (already validated by caspian_workspace)."""
    if rel_path == "system-context/caspian-system-prompt.md":
        return render_caspian_system_prompt()
    if rel_path == "system-context/patient-chart-context.md":
        return render_patient_chart_context(resolved_patient_id)
    if rel_path.startswith("system-context/workflows/"):
        leaf = rel_path.rsplit("/", 1)[1]
        if not leaf.endswith(".md"):
            return f"# Unknown workflow file: {leaf}\n"
        workflow_id = leaf[:-3]  # strip .md
        return render_workflow_packet(workflow_id)
    return f"# Unknown system-context file: {rel_path}\n"
