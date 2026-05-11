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
          signature TEXT NOT NULL
        )
        """
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
                   responseStatus, responseSummary, ts, signature)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                ),
            )
    return record


def list_records(
    *,
    plugin_id: str | None = None,
    run_id: str | None = None,
    db_path: Path | None = None,
) -> list[ProvenanceRecord]:
    with _lock:
        with _conn(db_path) as conn:
            q = "SELECT * FROM provenance"
            params: list = []
            wheres: list[str] = []
            if plugin_id:
                wheres.append("pluginId = ?")
                params.append(plugin_id)
            if run_id:
                wheres.append("runId = ?")
                params.append(run_id)
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
