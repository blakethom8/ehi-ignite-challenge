"""LLM observability primitives — tracing context managers and types.

Public surface intended for lib/ callers that want to emit spans without
reaching back into api/. The canonical implementation lives in
``lib.observability.tracing``; ``api.core.tracing`` re-exports the same
symbols plus any api-side wiring.
"""

from lib.observability.tracing import SpanKind, start_span

__all__ = ["SpanKind", "start_span"]
