"""Tracing middleware — wraps audited surfaces in a per-request trace.

Audited surfaces (each emits one trace per request):
- POST /api/assistant/chat            → workspace_kind = "caspian"
- POST /api/skills/{name}/runs[/...]  → workspace_kind = "skill"
- POST /api/plugins/runs/{run_id}/tool/{tool_id}  → workspace_kind = "plugin"

Every trace carries (user_id, session_id, workspace_kind) extracted from
the session cookie so the per-user audit query (H0.6) can join across
all three surfaces.
"""

from __future__ import annotations

import json
import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from api.core.tracing import (
    TRACING_ENABLED,
    WORKSPACE_CASPIAN,
    WORKSPACE_PLUGIN,
    WORKSPACE_SKILL,
    start_trace,
)

LOGGER = logging.getLogger(__name__)

_CASPIAN_PATH = "/api/assistant/chat"
_CASPIAN_WORKFLOW_PATH = "/api/caspian/workflows/run"
_SKILL_PATH_PREFIX = "/api/skills/"
_PLUGIN_TOOL_RE = re.compile(r"^/api/plugins/runs/[^/]+/tool/[^/]+/?$")


def _classify(method: str, path: str) -> str | None:
    """Return the workspace_kind for an audited path, or None to skip."""
    if method != "POST":
        return None
    if path == _CASPIAN_PATH or path == _CASPIAN_WORKFLOW_PATH:
        return WORKSPACE_CASPIAN
    if path.startswith(_SKILL_PATH_PREFIX):
        return WORKSPACE_SKILL
    if _PLUGIN_TOOL_RE.match(path):
        return WORKSPACE_PLUGIN
    return None


def _session_identity(request: Request) -> tuple[str, str]:
    """Extract (user_id, session_id) from the request session cookie.

    Failures are silent — tracing is best-effort and must not block the
    request path. Demo sessions have no user_id; we record the empty
    string in that case so the audit query can still group by session.
    """
    try:
        # Lazy import: avoids the auth module's eager DB init at import time
        # for tests that monkey-patch SESSION_SECRET_PATH.
        from api.core.auth import current_session

        principal = current_session(request)
    except Exception:
        return "", ""
    if principal is None:
        return "", ""
    return principal.user_id or "", principal.session_id


class TracingMiddleware(BaseHTTPMiddleware):
    """Open a trace for every audited surface and tag it with the session."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not TRACING_ENABLED:
            return await call_next(request)

        kind = _classify(request.method, request.url.path)
        if kind is None:
            return await call_next(request)

        user_id, session_id = _session_identity(request)

        # Body parsing only for the legacy assistant chat path — Caspian
        # carries patient_id/question/stance in the body, while skill and
        # plugin routes carry the relevant ids in the URL. Reading the body
        # for non-chat paths risks consuming the request stream.
        patient_id = ""
        question = f"{request.method} {request.url.path}"
        stance = "opinionated"
        if kind == WORKSPACE_CASPIAN:
            try:
                body_bytes = await request.body()
                body = json.loads(body_bytes)
                patient_id = body.get("patient_id", "")
                workflow_id = body.get("workflow_id")
                if workflow_id:
                    # Workflow runs have no `question` field — name the trace
                    # after the workflow so the Inspector shows what fired.
                    question = f"workflow:{workflow_id}"
                else:
                    question = body.get("question", "") or question
                stance = body.get("stance", "opinionated")
            except Exception:
                LOGGER.debug("Could not parse chat request body for tracing")

        with start_trace(
            patient_id=patient_id,
            question=question,
            stance=stance,
            user_id=user_id,
            session_id=session_id,
            workspace_kind=kind,
        ) as trace:
            response = await call_next(request)
            if trace is not None and response.status_code >= 400:
                trace.status = "error"
            return response
