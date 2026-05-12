"""Append-only signed provenance log.

Every successful outbound action writes one row. Rows are signed by
the Atlas key and stored in ``data/provenance.db`` (SQLite). The API
surface intentionally omits update + delete — provenance is the
auditable record of crossing the consented external boundary.

v2 = WORM storage on S3 + object-lock.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from api.trust.keys import REPO_ROOT, atlas_keypair
from api.trust.models import (
    OutboundActionKind,
    ProvenanceRecord,
    RedactionPreset,
    UserIdentity,
    VendorIdentity,
)
from api.trust.signatures import SignatureError, sign_object, verify_object


DEFAULT_DB_PATH = REPO_ROOT / "data" / "provenance.db"
_lock = threading.Lock()


class ProvenanceError(Exception):
    pass


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS provenance (
          id TEXT PRIMARY KEY,
          runId TEXT NOT NULL,
          pluginId TEXT NOT NULL,
          pluginVersion TEXT NOT NULL,
          vendor TEXT NOT NULL,
          action TEXT NOT NULL,
          approver TEXT NOT NULL,
          redactionPreset TEXT NOT NULL,
          artifactId TEXT,
          endpoint TEXT NOT NULL,
          responseStatus INTEGER NOT NULL,
          responseSummary TEXT NOT NULL,
          ts TEXT NOT NULL,
          signature TEXT NOT NULL,
          approver_id TEXT NOT NULL DEFAULT ''
        )
        """
    )
    # Forward-compat for DBs created before approver_id existed (H0.11).
    # NOT part of the signed payload — denormalized index column only.
    try:
        conn.execute(
            "ALTER TABLE provenance ADD COLUMN approver_id TEXT NOT NULL DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_provenance_approver_id "
        "ON provenance(approver_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_provenance_ts ON provenance(ts)"
    )
    # Backfill any pre-existing rows whose approver_id is empty (rows
    # written before the column existed). Reads the JSON `approver` blob
    # and pulls the id. Idempotent and cheap on small DBs.
    rows = conn.execute(
        "SELECT id, approver FROM provenance WHERE approver_id = ''"
    ).fetchall()
    for row_id, approver_json in rows:
        try:
            approver_id = (json.loads(approver_json) or {}).get("id", "")
        except (TypeError, ValueError, json.JSONDecodeError):
            approver_id = ""
        if approver_id:
            conn.execute(
                "UPDATE provenance SET approver_id = ? WHERE id = ?",
                (approver_id, row_id),
            )
    return conn


def _row_to_record(row: sqlite3.Row | tuple) -> ProvenanceRecord:
    keys = [
        "id",
        "runId",
        "pluginId",
        "pluginVersion",
        "vendor",
        "action",
        "approver",
        "redactionPreset",
        "artifactId",
        "endpoint",
        "responseStatus",
        "responseSummary",
        "ts",
        "signature",
    ]
    d = dict(zip(keys, row))
    d["vendor"] = json.loads(d["vendor"])
    d["approver"] = json.loads(d["approver"])
    return ProvenanceRecord.model_validate(d)


def write_record(
    *,
    run_id: str,
    plugin_id: str,
    plugin_version: str,
    vendor: VendorIdentity,
    action: OutboundActionKind,
    approver: UserIdentity,
    redaction_preset: RedactionPreset,
    artifact_id: str | None,
    endpoint: str,
    response_status: int,
    response_summary: str,
    db_path: Path | None = None,
    ts: datetime | None = None,
) -> ProvenanceRecord:
    record_id = "prov_" + uuid.uuid4().hex[:12]
    when = (ts or datetime.now(timezone.utc)).replace(microsecond=0)
    payload = {
        "id": record_id,
        "runId": run_id,
        "pluginId": plugin_id,
        "pluginVersion": plugin_version,
        "vendor": vendor.model_dump(),
        "action": action,
        "approver": approver.model_dump(),
        "redactionPreset": redaction_preset,
        "artifactId": artifact_id,
        "endpoint": endpoint,
        "responseStatus": response_status,
        "responseSummary": response_summary[:200],
        "ts": when.isoformat().replace("+00:00", "Z"),
    }
    sk, _ = atlas_keypair()
    payload["signature"] = sign_object(sk, payload, exclude_field=None)

    record = ProvenanceRecord.model_validate(payload)

    with _lock:
        with _conn(db_path) as conn:
            conn.execute(
                """
                INSERT INTO provenance
                  (id, runId, pluginId, pluginVersion, vendor, action,
                   approver, redactionPreset, artifactId, endpoint,
                   responseStatus, responseSummary, ts, signature, approver_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.id,
                    record.runId,
                    record.pluginId,
                    record.pluginVersion,
                    json.dumps(payload["vendor"], sort_keys=True),
                    record.action,
                    json.dumps(payload["approver"], sort_keys=True),
                    record.redactionPreset,
                    record.artifactId,
                    record.endpoint,
                    record.responseStatus,
                    record.responseSummary,
                    payload["ts"],
                    record.signature,
                    approver.id,
                ),
            )
    return record


def list_records(
    *,
    plugin_id: str | None = None,
    run_id: str | None = None,
    approver_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    db_path: Path | None = None,
) -> list[ProvenanceRecord]:
    """Query the provenance log. ``approver_id`` filters at SQL via the
    indexed column added in H0.11 — replaces the previous full-scan +
    Python-filter the audit endpoint had to do."""
    with _lock:
        with _conn(db_path) as conn:
            # SELECT only the original columns (approver_id is a denormalized
            # index, not part of the record shape returned to callers).
            q = (
                "SELECT id, runId, pluginId, pluginVersion, vendor, action, "
                "approver, redactionPreset, artifactId, endpoint, "
                "responseStatus, responseSummary, ts, signature "
                "FROM provenance"
            )
            params: list = []
            wheres: list[str] = []
            if plugin_id:
                wheres.append("pluginId = ?")
                params.append(plugin_id)
            if run_id:
                wheres.append("runId = ?")
                params.append(run_id)
            if approver_id:
                wheres.append("approver_id = ?")
                params.append(approver_id)
            if since:
                wheres.append("ts >= ?")
                params.append(since)
            if until:
                wheres.append("ts <= ?")
                params.append(until)
            if wheres:
                q += " WHERE " + " AND ".join(wheres)
            q += " ORDER BY ts DESC"
            rows = conn.execute(q, params).fetchall()
    return [_row_to_record(r) for r in rows]


def verify_record(record: ProvenanceRecord) -> None:
    _, pk = atlas_keypair()
    raw = record.model_dump(mode="json")
    sig = raw.pop("signature")
    try:
        verify_object(pk, raw, sig, exclude_field=None)
    except SignatureError as e:
        raise ProvenanceError(f"provenance signature invalid: {e}") from e


def verify_all(records: Iterable[ProvenanceRecord]) -> None:
    for r in records:
        verify_record(r)
