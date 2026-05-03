"""HTTP client for the Node `cursor-sidecar` service (Cursor `@cursor/sdk` runtime)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)


@dataclass
class CursorSidecarInvokeResult:
    """Normalized successful response from POST /invoke."""

    answer: str
    confidence: str
    citations: list[dict[str, Any]]
    follow_ups: list[str]
    engine: str
    model_used: str
    run_id: str | None
    duration_ms: int | None


class CursorSidecarHttpError(RuntimeError):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = code


class CursorSidecarClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        raw = (base_url or os.getenv("CURSOR_SIDECAR_URL") or "http://127.0.0.1:3040").rstrip("/")
        self._base = raw
        self._timeout = timeout_s if timeout_s is not None else float(os.getenv("CURSOR_SIDECAR_TIMEOUT_S", "120"))

    def health(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{self._base}/health")
                return r.status_code == 200
        except httpx.RequestError:
            return False

    def invoke(self, payload: dict[str, Any]) -> CursorSidecarInvokeResult:
        with httpx.Client(timeout=self._timeout) as client:
            r = client.post(f"{self._base}/invoke", json=payload)
            if r.status_code >= 400:
                try:
                    err = r.json()
                    msg = err.get("message", r.text)
                    code = err.get("code", "execution")
                except json.JSONDecodeError:
                    msg = r.text or r.reason_phrase
                    code = "execution"
                LOGGER.warning("cursor-sidecar invoke failed: %s %s", r.status_code, msg)
                raise CursorSidecarHttpError(status_code=r.status_code, code=str(code), message=str(msg))

            data = r.json()
            return CursorSidecarInvokeResult(
                answer=str(data.get("answer", "")),
                confidence=str(data.get("confidence", "medium")),
                citations=list(data.get("citations") or []),
                follow_ups=list(data.get("follow_ups") or []),
                engine=str(data.get("engine", "cursor-sdk-sidecar")),
                model_used=str(data.get("model_used", "")),
                run_id=data.get("run_id"),
                duration_ms=data.get("duration_ms"),
            )
