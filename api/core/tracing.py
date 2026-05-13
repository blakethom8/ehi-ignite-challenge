"""
LLM Observability & Tracing — API-side re-export.

The canonical implementation lives in :mod:`lib.observability.tracing` so
that ``lib/`` callers can emit spans without reaching back into ``api/``
(see ``lib/README.md`` — ``lib/`` must not depend on ``api/``). This
module preserves the existing import surface for everything inside
``api/``: routers, middleware, and tests can keep importing ``SpanKind``,
``start_trace``, etc. from ``api.core.tracing``.

Module-level constants (``TRACING_ENABLED``, ``DB_PATH``, …) snapshot the
env-var-driven config at module import time. Tests that mutate
``os.environ`` and ``importlib.reload(api.core.tracing)`` continue to see
fresh values because the snapshot is re-evaluated on reload — and the
lib implementation re-reads env vars on every call regardless.
"""

from __future__ import annotations

from lib.observability.tracing import (
    WORKSPACE_CASPIAN,
    WORKSPACE_PLUGIN,
    WORKSPACE_SKILL,
    Span,
    SpanKind,
    Trace,
    get_current_span,
    get_current_trace,
    get_trace_detail,
    get_traces_summary,
    langfuse_enabled,
    langfuse_host,
    langfuse_public_key,
    langfuse_secret_key,
    query_traces,
    start_span,
    start_trace,
    traces_db_path,
    tracing_enabled,
    tracing_sample_rate,
)

# Back-compat snapshots — read once at module load so existing callers can
# do ``from api.core.tracing import TRACING_ENABLED``. Live config is still
# the env-var getters in lib.observability.tracing, which is what start_trace
# et al. consult on every call.
TRACING_ENABLED = tracing_enabled()
DB_PATH = traces_db_path()
TRACING_SAMPLE_RATE = tracing_sample_rate()
LANGFUSE_PUBLIC_KEY = langfuse_public_key()
LANGFUSE_SECRET_KEY = langfuse_secret_key()
LANGFUSE_HOST = langfuse_host()
LANGFUSE_ENABLED = langfuse_enabled()

__all__ = [
    "Span",
    "SpanKind",
    "Trace",
    "WORKSPACE_CASPIAN",
    "WORKSPACE_PLUGIN",
    "WORKSPACE_SKILL",
    "TRACING_ENABLED",
    "DB_PATH",
    "TRACING_SAMPLE_RATE",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "LANGFUSE_ENABLED",
    "get_current_span",
    "get_current_trace",
    "get_trace_detail",
    "get_traces_summary",
    "query_traces",
    "start_span",
    "start_trace",
]
