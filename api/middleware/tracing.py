"""
Tracing middleware — opens a trace for each assistant chat request.

Intercepts POST /api/assistant/chat, extracts patient_id / question / stance
from the request body, and manages the trace lifecycle via context vars.
"""

from __future__ import annotations

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from api.core.tracing import TRACING_ENABLED, start_trace

LOGGER = logging.getLogger(__name__)

_TRACED_PATH = "/api/assistant/chat"


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware that wraps assistant chat requests in a trace."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Only trace the assistant chat endpoint
        if not TRACING_ENABLED or request.url.path != _TRACED_PATH or request.method != "POST":
            return await call_next(request)

        # Parse request body to extract trace metadata
        patient_id = ""
        question = ""
        stance = "opinionated"
        try:
            body_bytes = await request.body()
            body = json.loads(body_bytes)
            patient_id = body.get("patient_id", "")
            question = body.get("question", "")
            stance = body.get("stance", "opinionated")
        except Exception:
            LOGGER.debug("Could not parse request body for tracing")

        with start_trace(patient_id=patient_id, question=question, stance=stance) as trace:
            response = await call_next(request)

            if trace is not None:
                # Capture HTTP-level status
                if response.status_code >= 500:
                    trace.status = "error"
                elif response.status_code >= 400:
                    trace.status = "error"

            return response
