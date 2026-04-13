"""SQL-on-FHIR tool surface for the Claude Agent SDK.

Exposes a single ``run_sql`` helper that the agent can invoke against a
pre-materialized SQLite database built by the SQL-on-FHIR v2 prototype.

Design constraints (enforced here, not in the SDK):

* **SELECT-only.** A regex gate rejects any statement containing DDL/DML
  keywords (DROP, INSERT, UPDATE, DELETE, ATTACH, PRAGMA, CREATE, ALTER,
  REPLACE, TRUNCATE, VACUUM). The DB is also opened ``mode=ro``.
* **Row cap.** Every query is wrapped in ``LIMIT <limit>`` if the caller
  did not supply one. The final limit is hard-capped at ``MAX_ROWS``.
* **No multi-statement.** Semicolon-separated statements are rejected.

The module does **not** touch the agent SDK directly — it only returns
pure-Python primitives so it can be unit-tested without a Claude runtime.
Wiring into the ``@tool`` decorator happens in
``provider_assistant_agent_sdk.py``.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PATIENT_JOURNEY = _REPO_ROOT / "patient-journey"
_VIEWS_DIR = _PATIENT_JOURNEY / "core" / "sql_on_fhir" / "views"
DEFAULT_SOF_DB = _REPO_ROOT / "data" / "sof.db"

# Make `from core.sql_on_fhir...` importable the same way the rest of `api/`
# already reaches into the patient-journey package.
if str(_PATIENT_JOURNEY) not in sys.path:
    sys.path.insert(0, str(_PATIENT_JOURNEY))


# ---------------------------------------------------------------------------
# Limits + safety gate
# ---------------------------------------------------------------------------

MAX_ROWS = 500
DEFAULT_LIMIT = 50

# Keywords that must never appear as the first token of a statement or as a
# bare token anywhere in the query. We match whole words only so column
# aliases like ``dropped_count`` are still legal.
_FORBIDDEN = {
    "drop",
    "insert",
    "update",
    "delete",
    "attach",
    "detach",
    "pragma",
    "create",
    "alter",
    "replace",
    "truncate",
    "vacuum",
    "reindex",
    "analyze",
}

# Simple tokenizer: strip quoted strings and comments, then split on word
# boundaries. Quoted strings can legitimately contain the word "drop"
# (e.g. ``WHERE status = 'Drop'``), so we must ignore them.
_STRING_RE = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _strip_noise(query: str) -> str:
    q = _BLOCK_COMMENT_RE.sub(" ", query)
    q = _LINE_COMMENT_RE.sub(" ", q)
    q = _STRING_RE.sub(" ", q)
    return q


def is_safe_sql(query: str) -> tuple[bool, str]:
    """Return ``(ok, reason)``. ``reason`` is empty when ``ok`` is True."""
    if not query or not query.strip():
        return False, "empty query"

    stripped = _strip_noise(query).strip().rstrip(";")

    # No multi-statement
    if ";" in stripped:
        return False, "multi-statement queries are not allowed"

    tokens = [t.lower() for t in _WORD_RE.findall(stripped)]
    if not tokens:
        return False, "no SQL tokens found"

    first = tokens[0]
    if first not in {"select", "with"}:
        return False, f"only SELECT/WITH queries are allowed (got {first.upper()})"

    for tok in tokens:
        if tok in _FORBIDDEN:
            return False, f"forbidden keyword: {tok.upper()}"

    return True, ""


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------


@dataclass
class SqlRunResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    query: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "query": self.query,
            "error": self.error,
        }


def _apply_limit(query: str, limit: int) -> tuple[str, bool]:
    """Wrap the query in a LIMIT if the caller didn't add one.

    Returns ``(rewritten_query, did_inject)``. We only rewrite when the
    trailing tokens don't already look like ``LIMIT <n>`` (optionally with
    ``OFFSET <m>``). When we do rewrite, we ask for ``limit + 1`` rows so
    the caller can detect truncation — the ``+1`` row is sliced off before
    the result is returned.
    """
    q = query.strip().rstrip(";")
    stripped = _strip_noise(q).strip().rstrip(";").lower()
    tail_match = re.search(r"\blimit\s+\d+(\s+offset\s+\d+)?\s*$", stripped)
    if tail_match:
        return q, False
    return f"{q} LIMIT {limit + 1}", True


def run_sql(
    query: str,
    limit: int = DEFAULT_LIMIT,
    db_path: str | Path | None = None,
) -> SqlRunResult:
    """Execute a read-only SELECT against the SOF SQLite database.

    Returns a ``SqlRunResult``. On a gate failure or SQLite error the
    ``error`` field is populated and ``rows`` is empty — we never raise.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_SOF_DB

    try:
        capped = max(1, min(int(limit), MAX_ROWS))
    except (TypeError, ValueError):
        capped = DEFAULT_LIMIT

    ok, reason = is_safe_sql(query)
    if not ok:
        return SqlRunResult(
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            query=query,
            error=f"rejected: {reason}",
        )

    if not path.exists():
        return SqlRunResult(
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            query=query,
            error=f"database not found at {path}",
        )

    bounded, injected = _apply_limit(query, capped)

    try:
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            cursor = conn.execute(bounded)
            columns = [d[0] for d in cursor.description or []]
            # If we injected the limit, we asked for capped+1 rows so we can
            # detect truncation. Otherwise respect whatever the caller wrote
            # and only cap the in-memory payload.
            fetched = cursor.fetchmany(capped + 1)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return SqlRunResult(
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            query=bounded,
            error=f"sqlite error: {exc}",
        )

    truncated = len(fetched) > capped
    rows = [list(r) for r in fetched[:capped]]
    return SqlRunResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        query=bounded,
    )


# ---------------------------------------------------------------------------
# Schema discovery for the system prompt
# ---------------------------------------------------------------------------


def _load_view_definitions() -> list[Any]:
    from core.sql_on_fhir.view_definition import ViewDefinition  # type: ignore

    views: list[Any] = []
    if not _VIEWS_DIR.exists():
        return views
    for path in sorted(_VIEWS_DIR.glob("*.json")):
        views.append(ViewDefinition.from_json_file(path))
    return views


def get_schemas_for_prompt() -> str:
    """Render a compact schema summary for every bundled ViewDefinition.

    Output format (plain text, no markdown fences):

        -- <table>: <description>
        CREATE TABLE <table> (
          <col> <TYPE>,
          ...
        );

    Types use the same mapping as ``sqlite_sink._sql_type`` so the prompt
    matches what the agent will actually see when it queries.

    The renderer also picks up any enrichment columns registered in
    ``enrich.default_enrichments`` — e.g. ``drug_class`` on
    ``medication_request`` — so the agent's system prompt always
    matches the column list the warehouse was actually built with.
    """
    try:
        from core.sql_on_fhir.sqlite_sink import _sql_type  # type: ignore
    except ImportError:  # pragma: no cover — module always present in-tree
        def _sql_type(col):  # type: ignore
            return "TEXT"

    try:
        from core.sql_on_fhir.enrich import default_enrichments  # type: ignore
        enrichments = default_enrichments()
    except Exception:  # pragma: no cover — enrich module is in-tree
        enrichments = {}

    views = _load_view_definitions()
    if not views:
        return "-- (no ViewDefinitions found)"

    chunks: list[str] = []
    for view in views:
        seen: dict[str, Any] = {}
        for col in view.all_columns():
            if col.name not in seen:
                seen[col.name] = col
        enrichment = enrichments.get(view.name)
        enrichment_names: set[str] = set()
        if enrichment:
            for extra in enrichment.columns:
                if extra.name not in seen:
                    seen[extra.name] = extra
                    enrichment_names.add(extra.name)
        lines = [f"-- {view.name}: {view.description or view.resource}"]
        lines.append(f"CREATE TABLE {view.name} (")
        col_lines = []
        for c in seen.values():
            suffix = "  -- enriched" if c.name in enrichment_names else ""
            col_lines.append(f"  {c.name} {_sql_type(c)}{suffix}")
        lines.append(",\n".join(col_lines))
        lines.append(");")
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


# ---------------------------------------------------------------------------
# MCP tool description
# ---------------------------------------------------------------------------


_TOOL_PREAMBLE = """\
Run a read-only SELECT against the SQL-on-FHIR SQLite warehouse.

Use this for cohort-level or cross-patient questions: drug-class distributions,
condition prevalence, observation trends, encounter volume, anything you'd
normally answer with a GROUP BY. Do NOT use this for single-patient chart
lookups — use get_patient_snapshot / query_chart_evidence for that.

Rules:
- SELECT or WITH only. DROP/INSERT/UPDATE/DELETE/ATTACH/PRAGMA are rejected.
- One statement per call (no semicolons).
- Results are capped at 500 rows; use `limit` to request fewer.
- Synthea patient references are stored as `urn:uuid:<id>`. To join back to
  `patient.id`, use `WHERE x.patient_ref = 'urn:uuid:' || p.id`.
- Columns marked `-- enriched` below are derived at ingest time (not in the
  raw FHIR). `medication_request.drug_class` is populated from the shared
  drug-class mapping and takes one of: 'anticoagulants', 'antiplatelets',
  'ace_inhibitors', 'arbs', 'jak_inhibitors', 'immunosuppressants', 'nsaids',
  'opioids', 'anticonvulsants', 'psych_medications', 'stimulants',
  'diabetes_medications' — or NULL if nothing matched. Use
  `GROUP BY drug_class` for risk-class distributions.

Schemas:

"""


def build_tool_description() -> str:
    return _TOOL_PREAMBLE + get_schemas_for_prompt()


def tool_result_payload(result: SqlRunResult) -> dict[str, Any]:
    """Format a ``SqlRunResult`` for the Claude Agent SDK tool envelope."""
    body = result.to_dict()
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(body, default=str),
            }
        ],
        "is_error": result.error is not None,
    }
