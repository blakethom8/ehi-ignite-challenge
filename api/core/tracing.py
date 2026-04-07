"""
LLM Observability & Tracing — Core Module.

Provides structured tracing for Provider Assistant LLM calls.
Stores traces locally in SQLite and optionally exports to Langfuse.

Enable with TRACING_ENABLED=true environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generator

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TRACING_ENABLED = os.getenv("TRACING_ENABLED", "false").lower() in ("true", "1", "yes")
DB_PATH = Path(os.getenv("TRACES_DB_PATH", "data/traces.db"))

# Langfuse (optional)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class SpanKind(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"


@dataclass
class Span:
    """A single operation within a trace (LLM call, tool invocation, or retrieval)."""

    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    kind: SpanKind = SpanKind.LLM
    name: str = ""
    input_data: str | None = None
    output_data: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    total_cost_usd: float | None = None
    num_turns: int | None = None
    duration_ms: float = 0.0
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Internal timing
    _start_time: float = field(default=0.0, repr=False)


@dataclass
class Trace:
    """Top-level trace for a single assistant chat request."""

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    patient_id: str = ""
    question: str = ""
    stance: str = "opinionated"
    engine: str | None = None
    status: str = "ok"  # "ok" | "error" | "fallback"
    confidence: str | None = None
    answer_preview: str = ""  # First 500 chars of the answer
    answer_length: int = 0
    citation_count: int = 0
    follow_up_count: int = 0
    duration_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    spans: list[Span] = field(default_factory=list)
    # Internal timing
    _start_time: float = field(default=0.0, repr=False)


# ---------------------------------------------------------------------------
# Context Variables — thread/async-safe trace propagation
# ---------------------------------------------------------------------------

_current_trace: ContextVar[Trace | None] = ContextVar("_current_trace", default=None)
_current_span: ContextVar[Span | None] = ContextVar("_current_span", default=None)


def get_current_trace() -> Trace | None:
    """Get the active trace from the current context (if tracing is enabled)."""
    if not TRACING_ENABLED:
        return None
    return _current_trace.get(None)


def get_current_span() -> Span | None:
    """Get the active span from the current context."""
    if not TRACING_ENABLED:
        return None
    return _current_span.get(None)


# ---------------------------------------------------------------------------
# Context Managers
# ---------------------------------------------------------------------------


@contextmanager
def start_trace(
    patient_id: str,
    question: str,
    stance: str = "opinionated",
) -> Generator[Trace | None, None, None]:
    """Open a new trace. On exit, flush to storage."""
    if not TRACING_ENABLED:
        yield None
        return

    trace = Trace(
        patient_id=patient_id,
        question=question[:2000],  # Cap stored question length
        stance=stance,
        _start_time=time.monotonic(),
    )
    token = _current_trace.set(trace)

    try:
        yield trace
    except Exception as exc:
        trace.status = "error"
        # Record error on any active span too
        current_span = _current_span.get(None)
        if current_span and not current_span.error:
            current_span.error = str(exc)[:1000]
        raise
    finally:
        trace.duration_ms = (time.monotonic() - trace._start_time) * 1000
        # Finalize any open span durations
        for span in trace.spans:
            if span.duration_ms == 0.0 and span._start_time > 0:
                span.duration_ms = (time.monotonic() - span._start_time) * 1000
        _flush_trace(trace)
        _current_trace.reset(token)


@contextmanager
def start_span(
    kind: SpanKind,
    name: str,
    input_data: Any = None,
) -> Generator[Span | None, None, None]:
    """Open a span within the current trace."""
    trace = _current_trace.get(None)
    if trace is None:
        yield None
        return

    input_json = None
    if input_data is not None:
        try:
            input_json = json.dumps(input_data, default=str)[:50_000]  # Cap at 50KB
        except (TypeError, ValueError):
            input_json = str(input_data)[:50_000]

    span = Span(
        trace_id=trace.trace_id,
        kind=kind,
        name=name,
        input_data=input_json,
        _start_time=time.monotonic(),
    )
    trace.spans.append(span)
    token = _current_span.set(span)

    try:
        yield span
    except Exception as exc:
        span.error = str(exc)[:1000]
        raise
    finally:
        span.duration_ms = (time.monotonic() - span._start_time) * 1000
        _current_span.reset(token)


# ---------------------------------------------------------------------------
# SQLite Storage
# ---------------------------------------------------------------------------

_db_lock = threading.Lock()
_db_initialized = False


def _ensure_db() -> None:
    """Create tables and indexes if they don't exist."""
    global _db_initialized
    if _db_initialized:
        return

    with _db_lock:
        if _db_initialized:
            return

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id       TEXT PRIMARY KEY,
                    patient_id     TEXT NOT NULL,
                    question       TEXT NOT NULL,
                    stance         TEXT NOT NULL,
                    engine         TEXT,
                    status         TEXT NOT NULL DEFAULT 'ok',
                    confidence     TEXT,
                    answer_preview TEXT,
                    answer_length  INTEGER DEFAULT 0,
                    citation_count INTEGER DEFAULT 0,
                    follow_up_count INTEGER DEFAULT 0,
                    duration_ms    REAL DEFAULT 0,
                    created_at     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS spans (
                    span_id          TEXT PRIMARY KEY,
                    trace_id         TEXT NOT NULL,
                    kind             TEXT NOT NULL,
                    name             TEXT NOT NULL,
                    input_data       TEXT,
                    output_data      TEXT,
                    input_tokens     INTEGER,
                    output_tokens    INTEGER,
                    cache_read_tokens INTEGER,
                    total_cost_usd   REAL,
                    num_turns        INTEGER,
                    duration_ms      REAL DEFAULT 0,
                    error            TEXT,
                    started_at       TEXT NOT NULL,
                    FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
                );

                CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at);
                CREATE INDEX IF NOT EXISTS idx_traces_patient_id ON traces(patient_id);
                CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
            """)
        finally:
            conn.close()

        _db_initialized = True


def _flush_trace(trace: Trace) -> None:
    """Write trace and its spans to SQLite. Optionally export to Langfuse."""
    try:
        _ensure_db()
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """INSERT OR REPLACE INTO traces
                   (trace_id, patient_id, question, stance, engine, status,
                    confidence, answer_preview, answer_length, citation_count,
                    follow_up_count, duration_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace.trace_id,
                    trace.patient_id,
                    trace.question,
                    trace.stance,
                    trace.engine,
                    trace.status,
                    trace.confidence,
                    trace.answer_preview[:500] if trace.answer_preview else None,
                    trace.answer_length,
                    trace.citation_count,
                    trace.follow_up_count,
                    trace.duration_ms,
                    trace.created_at.isoformat(),
                ),
            )

            for span in trace.spans:
                conn.execute(
                    """INSERT OR REPLACE INTO spans
                       (span_id, trace_id, kind, name, input_data, output_data,
                        input_tokens, output_tokens, cache_read_tokens,
                        total_cost_usd, num_turns, duration_ms, error, started_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        span.span_id,
                        span.trace_id,
                        span.kind.value,
                        span.name,
                        span.input_data,
                        span.output_data,
                        span.input_tokens,
                        span.output_tokens,
                        span.cache_read_tokens,
                        span.total_cost_usd,
                        span.num_turns,
                        span.duration_ms,
                        span.error,
                        span.started_at.isoformat(),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

        LOGGER.debug(
            "Trace %s flushed: %s, %d spans, %.0fms",
            trace.trace_id[:8],
            trace.status,
            len(trace.spans),
            trace.duration_ms,
        )

    except Exception:
        LOGGER.exception("Failed to flush trace %s", trace.trace_id[:8])

    # Langfuse export (non-blocking)
    if LANGFUSE_ENABLED:
        thread = threading.Thread(
            target=_export_to_langfuse, args=(trace,), daemon=True
        )
        thread.start()


# ---------------------------------------------------------------------------
# Langfuse Export
# ---------------------------------------------------------------------------

_langfuse_client = None
_langfuse_init_lock = threading.Lock()


def _get_langfuse():
    """Lazy-initialize Langfuse client."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    with _langfuse_init_lock:
        if _langfuse_client is not None:
            return _langfuse_client
        try:
            from langfuse import Langfuse  # noqa: F811

            _langfuse_client = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
            )
            LOGGER.info("Langfuse client initialized (host=%s)", LANGFUSE_HOST)
        except ImportError:
            LOGGER.warning("langfuse package not installed; Langfuse export disabled")
            return None
        except Exception:
            LOGGER.exception("Failed to initialize Langfuse client")
            return None

    return _langfuse_client


def _export_to_langfuse(trace: Trace) -> None:
    """Export a trace and its spans to Langfuse."""
    client = _get_langfuse()
    if client is None:
        return

    try:
        lf_trace = client.trace(
            id=trace.trace_id,
            name="provider_assistant_chat",
            input={"question": trace.question, "stance": trace.stance},
            output={"answer_preview": trace.answer_preview},
            metadata={
                "patient_id": trace.patient_id,
                "engine": trace.engine,
                "status": trace.status,
                "confidence": trace.confidence,
                "citation_count": trace.citation_count,
                "follow_up_count": trace.follow_up_count,
            },
        )

        for span in trace.spans:
            if span.kind == SpanKind.LLM:
                lf_trace.generation(
                    id=span.span_id,
                    name=span.name,
                    input=span.input_data,
                    output=span.output_data,
                    model=os.getenv("PROVIDER_ASSISTANT_MODEL", "claude-sonnet-4-5"),
                    usage={
                        "input": span.input_tokens,
                        "output": span.output_tokens,
                        "total": (span.input_tokens or 0) + (span.output_tokens or 0),
                    }
                    if span.input_tokens
                    else None,
                    metadata={
                        "num_turns": span.num_turns,
                        "total_cost_usd": span.total_cost_usd,
                        "cache_read_tokens": span.cache_read_tokens,
                    },
                )
            else:
                lf_trace.span(
                    id=span.span_id,
                    name=span.name,
                    input=span.input_data,
                    output=span.output_data,
                    metadata={
                        "kind": span.kind.value,
                        "error": span.error,
                    },
                )

        client.flush()
        LOGGER.debug("Trace %s exported to Langfuse", trace.trace_id[:8])

    except Exception:
        LOGGER.exception("Langfuse export failed for trace %s", trace.trace_id[:8])


# ---------------------------------------------------------------------------
# Query Helpers (for the traces API)
# ---------------------------------------------------------------------------


def query_traces(
    *,
    patient_id: str | None = None,
    engine: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query traces from SQLite with optional filters."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conditions = []
        params: list[Any] = []
        if patient_id:
            conditions.append("patient_id = ?")
            params.append(patient_id)
        if engine:
            conditions.append("engine = ?")
            params.append(engine)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM traces {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_trace_detail(trace_id: str) -> dict[str, Any] | None:
    """Get a single trace with all its spans."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        trace_row = conn.execute(
            "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        if trace_row is None:
            return None

        span_rows = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY started_at", (trace_id,)
        ).fetchall()

        result = dict(trace_row)
        result["spans"] = [dict(row) for row in span_rows]
        return result
    finally:
        conn.close()


def get_traces_summary() -> dict[str, Any]:
    """Aggregate statistics across all traces."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        # Overall stats
        row = conn.execute("""
            SELECT
                COUNT(*) as total_traces,
                AVG(duration_ms) as avg_duration_ms,
                SUM(answer_length) as total_answer_chars,
                AVG(citation_count) as avg_citations,
                AVG(follow_up_count) as avg_follow_ups
            FROM traces
        """).fetchone()
        overall = dict(row) if row else {}

        # Token/cost stats from spans
        token_row = conn.execute("""
            SELECT
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cache_read_tokens) as total_cache_read_tokens,
                SUM(total_cost_usd) as total_cost_usd,
                AVG(total_cost_usd) as avg_cost_usd
            FROM spans
            WHERE kind = 'llm'
        """).fetchone()
        token_stats = dict(token_row) if token_row else {}

        # Breakdowns
        engine_rows = conn.execute(
            "SELECT engine, COUNT(*) as count FROM traces GROUP BY engine"
        ).fetchall()
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM traces GROUP BY status"
        ).fetchall()
        confidence_rows = conn.execute(
            "SELECT confidence, COUNT(*) as count FROM traces GROUP BY confidence"
        ).fetchall()

        return {
            **overall,
            **token_stats,
            "by_engine": {r["engine"]: r["count"] for r in engine_rows},
            "by_status": {r["status"]: r["count"] for r in status_rows},
            "by_confidence": {r["confidence"]: r["count"] for r in confidence_rows},
        }
    finally:
        conn.close()
