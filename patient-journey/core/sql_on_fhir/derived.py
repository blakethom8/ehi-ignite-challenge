"""Derived tables for the SQL-on-FHIR warehouse.

A ``Derivation`` is a post-materialization pass that reads from one or
more already-populated view tables and writes a brand-new table whose
rows are *computed* rather than projected. The ViewDefinition runtime
is intentionally standards-pure — FHIRPath-lite cannot express "group
consecutive MedicationRequests for the same drug into a continuous
treatment episode" — so derivations are the escape hatch for clinical
logic that the warehouse still needs to expose to SQL consumers.

Today we ship exactly one derivation:

- ``medication_episode`` — built from ``medication_request`` by grouping
  rows per ``(patient_ref, normalized display)`` pair and collapsing
  each group into a single episode with start/end dates, latest
  status, and a ``drug_class`` carried forward from the enrichment
  pass so cohort queries like "patients with an active anticoagulant
  episode" stay a one-line ``GROUP BY``.

The registry mirrors the ``enrich`` module's sentinel pattern:
``None`` in the sink means "apply the default derivations", ``{}``
means "pure ViewDefinition build, no derived tables". Keeping the
default on means every warehouse — dev, prod, pitch snapshot — carries
the same clinically-smart surface.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

try:
    from .view_definition import Column
except ImportError:  # running as a loose script
    from view_definition import Column  # type: ignore


# ---------------------------------------------------------------------------
# Derivation protocol
# ---------------------------------------------------------------------------


DerivationBuilder = Callable[[sqlite3.Connection], int]


@dataclass
class Derivation:
    """A single derived table.

    Attributes:
        table_name: the SQLite table this derivation will create.
        depends_on: the source table names that must already exist
            before ``build`` is called. The sink uses this list to
            short-circuit derivations whose dependencies were opted
            out of the run — e.g. a pure build with ``views=[patient]``
            will skip ``medication_episode`` because
            ``medication_request`` isn't there.
        build: a callable that takes an open SQLite connection,
            (re)creates the target table, and returns the row count.
        columns: the schema, as a list of ``Column`` entries. Used by
            the LLM tool surface (``api/core/sof_tools``) to render
            this table in the agent's system prompt. Must match the
            DDL emitted by ``build``.
        description: human-readable description surfaced in the
            prompt alongside ``table_name``.
    """

    table_name: str
    depends_on: list[str]
    build: DerivationBuilder
    columns: list[Column] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# medication_episode
# ---------------------------------------------------------------------------


# Statuses that mean the prescription is still live today. Mirrors
# episode_detector.detect_medication_episodes so the warehouse and the
# safety panel never disagree about "is this patient still on X".
_ACTIVE_STATUSES = {"active", "on-hold"}


_MED_EPISODE_DDL = """
CREATE TABLE "medication_episode" (
    "episode_id"       TEXT PRIMARY KEY,
    "patient_ref"      TEXT,
    "display"          TEXT,
    "rxnorm_code"      TEXT,
    "drug_class"       TEXT,
    "latest_status"    TEXT,
    "is_active"        INTEGER,
    "start_date"       TEXT,
    "end_date"         TEXT,
    "request_count"    INTEGER,
    "duration_days"    REAL,
    "first_request_id" TEXT
)
"""


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 string loosely. Returns ``None`` on anything
    we can't handle — the SOF runtime already guarantees these are
    strings when present, but synthetic test fixtures sometimes pass
    bare dates without a timezone."""
    if not value:
        return None
    try:
        # Python 3.11+ parses 'Z' suffix natively.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _normalize_key(display: Optional[str]) -> str:
    """Episode grouping key. Mirrors episode_detector which uses
    ``display.strip().lower()``. Empty/NULL displays collapse into a
    single ``""`` bucket which we drop."""
    return (display or "").strip().lower()


def build_medication_episodes(conn: sqlite3.Connection) -> int:
    """Populate ``medication_episode`` from ``medication_request``.

    One row per ``(patient_ref, normalized display)`` pair. The target
    table is dropped and recreated so repeated calls are idempotent —
    matches the rebuild-from-scratch behavior of the view-table DDL.

    Returns the number of episode rows inserted.
    """
    # Fresh table every time so a stale schema never lingers after a
    # column rename upstream.
    conn.execute('DROP TABLE IF EXISTS "medication_episode"')
    conn.execute(_MED_EPISODE_DDL)

    # The enriched ``drug_class`` column exists on medication_request
    # by default (see enrich.medication_request_enrichment). If a
    # caller opted out of enrichment the column is still present
    # (CREATE TABLE always writes it) and every row will just be NULL,
    # which the COALESCE below handles gracefully.
    source_cols = [
        "id",
        "patient_ref",
        "authored_on",
        "medication_text",
        "rxnorm_code",
        "rxnorm_display",
        "status",
    ]
    # drug_class may not exist if an older schema is being queried;
    # probe it once so we degrade gracefully rather than raising.
    has_drug_class = _column_exists(conn, "medication_request", "drug_class")
    if has_drug_class:
        source_cols.append("drug_class")

    select_sql = (
        'SELECT '
        + ", ".join(f'"{c}"' for c in source_cols)
        + ' FROM "medication_request" '
        'ORDER BY "patient_ref", "authored_on"'
    )

    rows = conn.execute(select_sql).fetchall()

    # Group by (patient_ref, normalized_display).
    groups: dict[tuple[str, str], list[dict]] = {}
    for raw in rows:
        row = dict(zip(source_cols, raw))
        display = row.get("medication_text") or row.get("rxnorm_display")
        key = _normalize_key(display)
        if not key:
            # Skip rows with no usable display — they can't be grouped
            # into an episode meaningfully.
            continue
        groups.setdefault((row["patient_ref"], key), []).append(row)

    inserts: list[tuple] = []
    for (patient_ref, key), reqs in groups.items():
        # Sort within the group so "first" and "latest" are stable.
        dated = [r for r in reqs if r.get("authored_on")]
        dated.sort(key=lambda r: r["authored_on"])
        # When nothing has an authored date, fall back to the raw
        # order (already sorted by the SELECT).
        ordered = dated if dated else reqs

        first = ordered[0]
        latest = ordered[-1]

        latest_status = latest.get("status") or ""
        is_active = 1 if latest_status in _ACTIVE_STATUSES else 0

        start_date = first.get("authored_on") if dated else None
        end_date = None if is_active else (latest.get("authored_on") if dated else None)

        duration_days: Optional[float] = None
        if start_date and end_date:
            start_dt = _parse_iso(start_date)
            end_dt = _parse_iso(end_date)
            if start_dt and end_dt:
                duration_days = (end_dt - start_dt).total_seconds() / 86400.0

        # Representative display = the first non-empty medication_text
        # or rxnorm_display we encounter in the sorted run. Matches how
        # episode_detector picks ``ref.display`` (the first dated
        # record).
        display = (
            first.get("medication_text")
            or first.get("rxnorm_display")
            or latest.get("medication_text")
            or latest.get("rxnorm_display")
            or key
        )
        # First non-null RxNorm code wins — prescribers sometimes
        # recode a drug mid-treatment; surfacing the earliest coding
        # keeps the episode linked to its original ordering.
        rxnorm_code = next(
            (r.get("rxnorm_code") for r in ordered if r.get("rxnorm_code")),
            None,
        )
        drug_class = None
        if has_drug_class:
            drug_class = next(
                (r.get("drug_class") for r in ordered if r.get("drug_class")),
                None,
            )

        episode_id = f"{patient_ref}::{key}"
        inserts.append(
            (
                episode_id,
                patient_ref,
                display,
                rxnorm_code,
                drug_class,
                latest_status,
                is_active,
                start_date,
                end_date,
                len(reqs),
                duration_days,
                first.get("id"),
            )
        )

    if inserts:
        conn.executemany(
            'INSERT INTO "medication_episode" VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            inserts,
        )
    conn.commit()
    return len(inserts)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(r[1] == column for r in rows)


def _medication_episode_columns() -> list[Column]:
    """Column schema for ``medication_episode``. Must match
    ``_MED_EPISODE_DDL`` above — the renderer in ``sof_tools`` uses
    these entries verbatim in the agent's system prompt.
    """
    return [
        Column(name="episode_id", path="<derived>", type="string",
               description="Stable PK: patient_ref :: normalized display."),
        Column(name="patient_ref", path="<derived>", type="string"),
        Column(name="display", path="<derived>", type="string",
               description="Representative drug display (earliest-seen)."),
        Column(name="rxnorm_code", path="<derived>", type="code"),
        Column(name="drug_class", path="<derived>", type="string",
               description="First non-null drug_class carried from medication_request."),
        Column(name="latest_status", path="<derived>", type="code"),
        Column(name="is_active", path="<derived>", type="boolean",
               description="1 if latest_status in (active, on-hold)."),
        Column(name="start_date", path="<derived>", type="dateTime"),
        Column(name="end_date", path="<derived>", type="dateTime",
               description="NULL when the episode is still active."),
        Column(name="request_count", path="<derived>", type="integer",
               description="Number of medication_request rows rolled up."),
        Column(name="duration_days", path="<derived>", type="decimal",
               description="(end_date - start_date) in days, NULL when active."),
        Column(name="first_request_id", path="<derived>", type="id"),
    ]


def medication_episode_derivation() -> Derivation:
    """The default ``medication_episode`` derivation entry."""
    return Derivation(
        table_name="medication_episode",
        depends_on=["medication_request"],
        build=build_medication_episodes,
        columns=_medication_episode_columns(),
        description=(
            "One row per (patient, drug) continuous treatment episode. "
            "Built by grouping medication_request rows on normalized display."
        ),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def default_derivations() -> dict[str, Derivation]:
    """Return the default table_name → Derivation registry.

    Callers that want a pure (ViewDefinition-only) build can pass
    ``derivations={}`` to ``materialize_all`` instead.
    """
    return {
        "medication_episode": medication_episode_derivation(),
    }
