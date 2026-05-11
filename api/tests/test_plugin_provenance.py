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
