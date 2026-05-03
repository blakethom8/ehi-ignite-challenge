"""Materialize ViewDefinition rows into a SQLite database.

The table name defaults to the ViewDefinition's `name`. Column types are
mapped from FHIR-ish types to SQLite affinities:

    id, string, code, uri, canonical   → TEXT
    integer, positiveInt, unsignedInt  → INTEGER
    decimal                             → REAL
    boolean                             → INTEGER (0/1)
    dateTime, date, instant, time       → TEXT (ISO strings)
    everything else                     → TEXT

Optional enrichments (see ``enrich.py``) let callers splice derived
columns onto a view at ingest time — for example, mapping each
``medication_request`` row to a ``drug_class`` key before it hits the
SQLite sink. The enrichment registry is applied by default so the
warehouse always carries the clinically-smart columns; callers that
want a pure ViewDefinition build can pass ``enrichments={}``.

Optional **derivations** (see ``derived.py``) run a second pass after
every ViewDefinition has been materialized. Derivations read from one
or more already-populated view tables and build brand-new tables
whose rows are *computed* — e.g. ``medication_episode`` groups
``medication_request`` rows into continuous treatment episodes. Like
enrichments, derivations ship default-on; pass ``derivations={}`` to
opt out.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Sequence

try:
    from .derived import Derivation, default_derivations
    from .enrich import Enrichment, default_enrichments
    from .runner import _eval_select, _passes_where, run_view
    from .view_definition import Column, SelectClause, ViewDefinition
except ImportError:  # running as a loose script
    from derived import Derivation, default_derivations  # type: ignore
    from enrich import Enrichment, default_enrichments  # type: ignore
    from runner import _eval_select, _passes_where, run_view  # type: ignore
    from view_definition import Column, SelectClause, ViewDefinition  # type: ignore


def _resolve_enrichments(
    enrichments: Optional[dict[str, Enrichment]],
) -> dict[str, Enrichment]:
    """Sentinel-aware resolver.

    ``None`` means "use the default registry"; ``{}`` means "no
    enrichment at all". Keeps the default-on behavior while letting
    tests opt out cleanly.
    """
    if enrichments is None:
        return default_enrichments()
    return enrichments


def _resolve_derivations(
    derivations: Optional[dict[str, Derivation]],
) -> dict[str, Derivation]:
    """Sentinel-aware resolver for derived tables.

    Mirrors ``_resolve_enrichments``: ``None`` → default registry,
    ``{}`` → opt out of every derived table. Kept separate from the
    enrichment resolver so the two hooks can evolve independently.
    """
    if derivations is None:
        return default_derivations()
    return derivations


_TYPE_MAP = {
    "integer": "INTEGER",
    "positiveInt": "INTEGER",
    "unsignedInt": "INTEGER",
    "decimal": "REAL",
    "boolean": "INTEGER",
}


def _sql_type(col: Column) -> str:
    if col.collection:
        return "TEXT"  # we JSON-encode collection columns
    return _TYPE_MAP.get(col.type, "TEXT")


def _ensure_table(
    conn: sqlite3.Connection,
    view: ViewDefinition,
    enrichment: Optional[Enrichment] = None,
) -> list[Column]:
    cols = view.all_columns()
    # Deduplicate by name, preserving first occurrence
    seen: dict[str, Column] = {}
    for c in cols:
        if c.name not in seen:
            seen[c.name] = c
    # Append enrichment columns after the view's own columns. Skip any
    # whose name already collides with a declared column — the view
    # always wins.
    if enrichment:
        for extra in enrichment.columns:
            if extra.name not in seen:
                seen[extra.name] = extra
    ordered = list(seen.values())
    coldefs = ", ".join(f'"{c.name}" {_sql_type(c)}' for c in ordered)
    conn.execute(f'DROP TABLE IF EXISTS "{view.name}"')
    conn.execute(f'CREATE TABLE "{view.name}" ({coldefs})')
    return ordered


def materialize(
    view: ViewDefinition,
    resources: Iterable[dict],
    conn: sqlite3.Connection,
    enrichments: Optional[dict[str, Enrichment]] = None,
) -> int:
    """Run the view against `resources` and insert all rows into SQLite.
    Returns the number of rows inserted."""
    resolved = _resolve_enrichments(enrichments)
    enrichment = resolved.get(view.name)
    ordered = _ensure_table(conn, view, enrichment)
    col_names = [c.name for c in ordered]
    placeholders = ", ".join("?" for _ in col_names)
    quoted = ", ".join(f'"{n}"' for n in col_names)
    sql = f'INSERT INTO "{view.name}" ({quoted}) VALUES ({placeholders})'

    count = 0
    batch: list[tuple] = []
    for row in run_view(view, resources):
        if enrichment:
            enrichment.apply(row)
        values = []
        for c in ordered:
            v = row.get(c.name)
            if isinstance(v, (list, dict)):
                v = json.dumps(v)
            values.append(v)
        batch.append(tuple(values))
        count += 1
        if len(batch) >= 500:
            conn.executemany(sql, batch)
            batch.clear()
    if batch:
        conn.executemany(sql, batch)
    conn.commit()
    return count


def open_db(path: str | Path) -> sqlite3.Connection:
    """Open (or create) a SQLite database with sensible defaults."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def materialize_all(
    views: Sequence[ViewDefinition],
    resources: Iterable[dict],
    conn: sqlite3.Connection,
    enrichments: Optional[dict[str, Enrichment]] = None,
    derivations: Optional[dict[str, Derivation]] = None,
) -> dict[str, int]:
    """Single-pass materialization: iterate `resources` once and dispatch to
    every matching ViewDefinition. Much faster than calling `materialize`
    per view when resources live on disk — lets us parse each bundle only
    once regardless of how many views are defined.

    If ``enrichments`` is ``None`` the default registry (drug_class on
    ``medication_request``) is applied; pass ``{}`` to get a pure
    ViewDefinition build with zero derived columns.

    After every view has been populated, any matching ``derivations``
    run a second pass — each derivation reads from one or more of the
    just-built tables and produces a new derived table (e.g.
    ``medication_episode``). Derivations whose declared dependencies
    are missing from ``views`` are silently skipped so a partial build
    ("just patient + condition") doesn't explode. ``derivations=None``
    means the default registry; ``{}`` opts out of every derivation.
    """
    resolved = _resolve_enrichments(enrichments)
    resolved_deriv = _resolve_derivations(derivations)

    # Pre-build tables + per-view SQL + column lists
    prep: dict[str, dict] = {}
    for view in views:
        enrichment = resolved.get(view.name)
        ordered = _ensure_table(conn, view, enrichment)
        col_names = [c.name for c in ordered]
        quoted = ", ".join('"' + n + '"' for n in col_names)
        placeholders = ", ".join("?" for _ in col_names)
        sql = f'INSERT INTO "{view.name}" ({quoted}) VALUES ({placeholders})'
        prep[view.name] = {
            "view": view,
            "columns": ordered,
            "sql": sql,
            "batch": [],
            "enrichment": enrichment,
        }

    # Group views by resource type for O(1) dispatch
    by_type: dict[str, list[str]] = {}
    for view in views:
        by_type.setdefault(view.resource, []).append(view.name)

    counts = {v.name: 0 for v in views}
    BATCH = 500

    for resource in resources:
        if not isinstance(resource, dict):
            continue
        rtype = resource.get("resourceType")
        matching = by_type.get(rtype)
        if not matching:
            continue
        for view_name in matching:
            entry = prep[view_name]
            view: ViewDefinition = entry["view"]
            if not _passes_where(resource, view.where):
                continue

            # Reuse the runner's per-resource evaluation logic
            rowsets: list[list[dict]] = []
            for clause in view.selects:
                rowsets.append(_eval_select(clause, resource))
            if not rowsets or any(not rs for rs in rowsets):
                continue

            combos: list[dict] = [{}]
            for rows in rowsets:
                new_combos: list[dict] = []
                for combo in combos:
                    for r in rows:
                        merged = dict(combo)
                        merged.update(r)
                        new_combos.append(merged)
                combos = new_combos

            enrichment: Optional[Enrichment] = entry["enrichment"]
            for row in combos:
                if enrichment:
                    enrichment.apply(row)
                values = []
                for c in entry["columns"]:
                    v = row.get(c.name)
                    if isinstance(v, (list, dict)):
                        v = json.dumps(v)
                    values.append(v)
                entry["batch"].append(tuple(values))
                counts[view_name] += 1
                if len(entry["batch"]) >= BATCH:
                    conn.executemany(entry["sql"], entry["batch"])
                    entry["batch"].clear()

    # Flush remaining batches
    for entry in prep.values():
        if entry["batch"]:
            conn.executemany(entry["sql"], entry["batch"])
            entry["batch"].clear()
    conn.commit()

    # Derivation pass — runs after every view is flushed so builders
    # can SELECT from the just-populated tables. Skip any derivation
    # whose source tables weren't part of this run (partial build).
    view_names = {v.name for v in views}
    for name, derivation in resolved_deriv.items():
        if any(dep not in view_names for dep in derivation.depends_on):
            continue
        counts[name] = derivation.build(conn)

    return counts
