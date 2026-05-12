"""
Caspian chat tools — write_file / read_file / list_files.

These are passed to the Anthropic Messages API on every chat turn (see
provider_assistant_context.answer_with_context). They mirror the HTTP
endpoints in api/routers/caspian_files.py but run in-process so the chat
loop can dispatch them between rounds.

Each tool is defined as:
  - a spec dict (Anthropic tool-use schema)
  - an executor function that takes the parsed input + the session principal
    + the resolved patient id, and returns a JSON-serializable dict

The dispatcher in provider_assistant_context wraps each call in a tracing
span so the run shows up in the Inspector's Trace tab.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from api.core import caspian_workspace
from api.core.auth import SessionPrincipal
from api.core.caspian_workspace import (
    WorkspaceForbiddenError,
    WorkspaceNotFoundError,
    WorkspacePathError,
)

LOGGER = logging.getLogger(__name__)


WRITE_FILE_TOOL: dict[str, Any] = {
    "name": "write_file",
    "description": (
        "Create or overwrite a file in the user's working directory for this "
        "patient. Writes are allowed under `notes/`, under `workflow-runs/`, "
        "or as the bare file `user-instructions.md`. The `system-context/` "
        "folder is read-only — writes there will return an error and the user "
        "will see the failure. Path is relative to the workspace root. The "
        "full content you supply will overwrite any existing file at that "
        "path. Prefer descriptive filenames with the `.md` extension for "
        "human-readable reports."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Relative path. Example: 'notes/clopidogrel-report.md'."
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "Full file content. Will overwrite any existing file at "
                    "that path. Keep under 200,000 characters."
                ),
            },
        },
        "required": ["path", "content"],
    },
}


READ_FILE_TOOL: dict[str, Any] = {
    "name": "read_file",
    "description": (
        "Read a single file from the user's working directory for this "
        "patient. You can read files under `notes/`, `workflow-runs/`, "
        "`user-instructions.md`, and the read-only `system-context/` folder "
        "(useful for citing the live patient chart context or the workflow "
        "packets that drive structured reviews)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Relative workspace path, e.g. 'notes/intake-checklist.md' "
                    "or 'system-context/patient-chart-context.md'."
                ),
            },
        },
        "required": ["path"],
    },
}


LIST_FILES_TOOL: dict[str, Any] = {
    "name": "list_files",
    "description": (
        "List every file currently in the user's working directory for this "
        "patient. Returns a flat list of relative paths with whether each is "
        "editable. Use this before write_file to avoid clobbering an existing "
        "file, or to check what artifacts are already available."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def caspian_chat_tools_for(session: SessionPrincipal | None) -> list[dict[str, Any]]:
    """Return the tool spec list the agent should be offered for this session.

    - authenticated: read + write + list
    - demo:          read + list only (workspace is read-only sample data)
    - guest / anonymous / unknown: no tools (Caspian is not available)
    """
    if session is None:
        return []
    if session.is_authenticated:
        return [LIST_FILES_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL]
    if session.is_demo:
        return [LIST_FILES_TOOL, READ_FILE_TOOL]
    return []


# Deprecated: kept as a back-compat alias for older callers that read tools at
# import time. Prefer ``caspian_chat_tools_for(session)`` so we can gate the
# write tool per mode. Remove once no callers reference this constant.
CASPIAN_CHAT_TOOLS: list[dict[str, Any]] = [
    LIST_FILES_TOOL,
    READ_FILE_TOOL,
    WRITE_FILE_TOOL,
]


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def _flatten_tree_for_listing(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in nodes:
        kind = node.get("type")
        if kind == "file":
            out.append(
                {
                    "path": node.get("id"),
                    "editable": bool(node.get("editable")),
                }
            )
        elif kind == "folder":
            out.extend(_flatten_tree_for_listing(node.get("children") or []))
    return out


def execute_write_file(
    session: SessionPrincipal,
    resolved_patient_id: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    path = args.get("path", "")
    content = args.get("content", "")
    if not isinstance(path, str) or not isinstance(content, str):
        return {"error": "path and content must both be strings"}
    try:
        result = caspian_workspace.write_workspace_file(
            session, resolved_patient_id, path, content
        )
    except WorkspaceForbiddenError as exc:
        return {"error": f"forbidden: {exc}"}
    except WorkspacePathError as exc:
        return {"error": f"invalid path: {exc}"}
    return {
        "path": result.path,
        "bytes": result.bytes,
        "mtime": result.mtime.isoformat(),
    }


def execute_read_file(
    session: SessionPrincipal,
    resolved_patient_id: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    path = args.get("path", "")
    if not isinstance(path, str):
        return {"error": "path must be a string"}
    try:
        result = caspian_workspace.read_workspace_file(
            session, resolved_patient_id, path
        )
    except WorkspacePathError as exc:
        return {"error": f"invalid path: {exc}"}
    except WorkspaceNotFoundError as exc:
        return {"error": f"not found: {exc}"}
    return {
        "path": result.path,
        "content": result.content,
        "editable": result.editable,
        "kind": result.kind,
    }


def execute_list_files(
    session: SessionPrincipal,
    resolved_patient_id: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    data = caspian_workspace.list_workspace(session, resolved_patient_id)
    return {
        "workspace_key": data["workspace_key"],
        "files": _flatten_tree_for_listing(data["tree"]),
    }


EXECUTORS = {
    "write_file": execute_write_file,
    "read_file": execute_read_file,
    "list_files": execute_list_files,
}


def execute_tool(
    name: str,
    args: dict[str, Any],
    session: SessionPrincipal,
    resolved_patient_id: str,
) -> tuple[dict[str, Any], bool]:
    """Dispatch a tool call. Returns (payload, is_error)."""
    # Mode-aware gate for the write tool. The tool spec list itself is filtered
    # per-session by ``caspian_chat_tools_for``, but if the model somehow tries
    # to call ``write_file`` anyway (cached schema, prompt-injection, etc.) we
    # surface a clean error rather than 500 from the workspace layer.
    if name == "write_file" and not session.is_authenticated:
        return (
            {
                "error": "write_file is not available in this session. "
                "Sample workspaces are read-only."
            },
            True,
        )
    executor = EXECUTORS.get(name)
    if executor is None:
        return ({"error": f"unknown tool: {name}"}, True)
    try:
        result = executor(session, resolved_patient_id, args)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("Tool %s failed", name)
        return ({"error": f"tool {name} crashed: {exc}"}, True)
    is_error = bool(result.get("error"))
    return (result, is_error)


def tool_result_payload(payload: dict[str, Any], is_error: bool) -> dict[str, Any]:
    """Shape a payload into Anthropic's tool_result content block format."""
    return {
        "type": "tool_result",
        "content": [{"type": "text", "text": json.dumps(payload, default=str)}],
        "is_error": is_error,
    }
