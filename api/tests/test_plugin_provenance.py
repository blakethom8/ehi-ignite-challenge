from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.plugins import provenance as prov
from api.trust.models import UserIdentity, VendorIdentity


@pytest.fixture
def tmp_db(tmp_path: Path):
    return tmp_path / "provenance.db"


def _write(tmp_db, **overrides):
    base = dict(
        run_id="r_test",
        plugin_id="trial-finder",
        plugin_version="2.4.1",
        vendor=VendorIdentity(
            id="helix-clinical", name="Helix Clinical", keyFingerprint="ed25519:abc"
        ),
        action="send-packet",
        approver=UserIdentity(id="u_42", name="Dr. Q", role="clinician"),
        redaction_preset="de-id-v3",
        artifact_id="outreach-packet-NCT-0421187",
        endpoint="https://sites.clinicaltrials.gov/contact",
        response_status=202,
        response_summary="Packet queued.",
        db_path=tmp_db,
    )
    base.update(overrides)
    return prov.write_record(**base)


def test_write_then_read_back(tmp_db):
    r = _write(tmp_db)
    rows = prov.list_records(plugin_id="trial-finder", db_path=tmp_db)
    assert len(rows) == 1
    assert rows[0].id == r.id


def test_signed_record_verifies(tmp_db):
    r = _write(tmp_db)
    prov.verify_record(r)


def test_tampered_record_fails_verify(tmp_db):
    r = _write(tmp_db)
    r.responseSummary = "Tampered."
    with pytest.raises(prov.ProvenanceError):
        prov.verify_record(r)


def test_multiple_records_filter_by_run(tmp_db):
    _write(tmp_db, run_id="r_a")
    _write(tmp_db, run_id="r_b")
    _write(tmp_db, run_id="r_b")
    assert len(prov.list_records(run_id="r_b", db_path=tmp_db)) == 2
    assert len(prov.list_records(run_id="r_a", db_path=tmp_db)) == 1


def test_listed_records_in_descending_time(tmp_db):
    t0 = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 5, 10, 13, 0, 0, tzinfo=timezone.utc)
    _write(tmp_db, run_id="r1", ts=t0)
    _write(tmp_db, run_id="r2", ts=t1)
    rows = prov.list_records(db_path=tmp_db)
    assert rows[0].runId == "r2"
    assert rows[1].runId == "r1"


def test_append_only_via_api(tmp_db):
    """The module exposes write/list/verify. There is no update or delete."""
    assert not hasattr(prov, "update_record")
    assert not hasattr(prov, "delete_record")


# ── H0.11 — approver_id index ──────────────────────────────────────────────


def test_approver_id_filter_returns_only_matching_user(tmp_db):
    """H0.11 regression: list_records(approver_id=...) returns only the
    records that user approved, using the indexed column."""
    alice = UserIdentity(id="u_alice", name="Alice", role="clinician")
    bob = UserIdentity(id="u_bob", name="Bob", role="attending")
    _write(tmp_db, run_id="r_a1", approver=alice)
    _write(tmp_db, run_id="r_a2", approver=alice)
    _write(tmp_db, run_id="r_b1", approver=bob)

    alice_rows = prov.list_records(approver_id="u_alice", db_path=tmp_db)
    assert {r.runId for r in alice_rows} == {"r_a1", "r_a2"}

    bob_rows = prov.list_records(approver_id="u_bob", db_path=tmp_db)
    assert [r.runId for r in bob_rows] == ["r_b1"]


def test_approver_id_filter_combined_with_time_window(tmp_db):
    alice = UserIdentity(id="u_alice", name="Alice", role="clinician")
    early = datetime(2026, 5, 10, 10, 0, 0, tzinfo=timezone.utc)
    mid = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    late = datetime(2026, 5, 10, 14, 0, 0, tzinfo=timezone.utc)
    _write(tmp_db, run_id="r_early", approver=alice, ts=early)
    _write(tmp_db, run_id="r_mid", approver=alice, ts=mid)
    _write(tmp_db, run_id="r_late", approver=alice, ts=late)

    rows = prov.list_records(
        approver_id="u_alice",
        since="2026-05-10T11:00:00Z",
        until="2026-05-10T13:00:00Z",
        db_path=tmp_db,
    )
    assert [r.runId for r in rows] == ["r_mid"]


def test_approver_id_index_uses_query_plan(tmp_db):
    """Sanity check that the index is actually consulted — EXPLAIN QUERY
    PLAN should mention the approver_id index, not a SCAN."""
    import sqlite3

    _write(tmp_db, run_id="r1")
    conn = sqlite3.connect(str(tmp_db))
    try:
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM provenance WHERE approver_id = ?",
            ("u_42",),
        ).fetchall()
    finally:
        conn.close()
    plan_text = " ".join(str(row) for row in plan)
    assert "idx_provenance_approver_id" in plan_text, (
        f"expected approver_id index to be used; got plan: {plan_text}"
    )


def test_existing_records_backfill_approver_id_on_open(tmp_db):
    """Pre-existing rows (written before H0.11) get approver_id backfilled
    on the next _conn() call. This avoids forcing a manual migration."""
    import json
    import sqlite3

    # Write a row "the old way" — directly into a DB without the column.
    conn = sqlite3.connect(str(tmp_db))
    try:
        conn.execute(
            """
            CREATE TABLE provenance (
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
        conn.execute(
            "INSERT INTO provenance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "prov_legacy",
                "r_legacy",
                "trial-finder",
                "2.4.1",
                json.dumps({"id": "v", "name": "v", "keyFingerprint": "fp"}),
                "send-packet",
                json.dumps({"id": "u_legacy", "name": "Legacy", "role": "clinician"}),
                "minimal",
                None,
                "https://example.com",
                200,
                "ok",
                "2026-05-10T12:00:00Z",
                "sig",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Open via prov._conn — backfill runs.
    rows = prov.list_records(approver_id="u_legacy", db_path=tmp_db)
    assert len(rows) == 1
    assert rows[0].id == "prov_legacy"
