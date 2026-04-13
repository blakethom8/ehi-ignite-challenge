"""Materialize ViewDefinition rows into a SQLite database.

The table name defaults to the ViewDefinition's `name`. Column types are
mapped from FHIR-ish types to SQLite affinities:

    id, string, code, uri, canonical   → TEXT
    integer, positiveInt, unsignedInt  → INTEGER
    decimal                             → REAL
    boolean                             → INTEGER (0/1)
    dateTime, date, instant, time       → TEXT (ISO strings)
    everything else                     → TEXT
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

try:
    from .runner import _eval_select, _passes_where, run_view
    from .view_definition import Column, SelectClause, ViewDefinition
except ImportError:  # running as a loose script
    from runner import _eval_select, _passes_where, run_view  # type: ignore
    from view_definition import Column, SelectClause, ViewDefinition  # type: ignore


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


def _ensure_table(conn: sqlite3.Connection, view: ViewDefinition) -> list[Column]:
    cols = view.all_columns()
    # Deduplicate by name, preserving first occurrence
    seen: dict[str, Column] = {}
    for c in cols:
        if c.name not in seen:
            seen[c.name] = c
    ordered = list(seen.values())
    coldefs = ", ".join(f'"{c.name}" {_sql_type(c)}' for c in ordered)
    conn.execute(f'DROP TABLE IF EXISTS "{view.name}"')
    conn.execute(f'CREATE TABLE "{view.name}" ({coldefs})')
    return ordered


def materialize(
    view: ViewDefinition,
    resources: Iterable[dict],
    conn: sqlite3.Connection,
) -> int:
    """Run the view against `resources` and insert all rows into SQLite.
    Returns the number of rows inserted."""
    ordered = _ensure_table(conn, view)
    col_names = [c.name for c in ordered]
    placeholders = ", ".join("?" for _ in col_names)
    quoted = ", ".join(f'"{n}"' for n in col_names)
    sql = f'INSERT INTO "{view.name}" ({quoted}) VALUES ({placeholders})'

    count = 0
    batch: list[tuple] = []
    for row in run_view(view, resources):
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
) -> dict[str, int]:
    """Single-pass materialization: iterate `resources` once and dispatch to
    every matching ViewDefinition. Much faster than calling `materialize`
    per view when resources live on disk — lets us parse each bundle only
    once regardless of how many views are defined.
    """
    # Pre-build tables + per-view SQL + column lists
    prep: dict[str, dict] = {}
    for view in views:
        ordered = _ensure_table(conn, view)
        col_names = [c.name for c in ordered]
        quoted = ", ".join('"' + n + '"' for n in col_names)
        placeholders = ", ".join("?" for _ in col_names)
        sql = f'INSERT INTO "{view.name}" ({quoted}) VALUES ({placeholders})'
        prep[view.name] = {"view": view, "columns": ordered, "sql": sql, "batch": []}

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

            for row in combos:
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
    return counts
