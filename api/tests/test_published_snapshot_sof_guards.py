from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import api.routers.patients as patients_router
import api.core.provider_assistant_agent_sdk as agent_sdk
import sqlite3


def test_active_published_care_journey_skips_global_sof(monkeypatch) -> None:
    record = SimpleNamespace(
        medications=[],
        conditions=[],
        procedures=[],
        diagnostic_reports=[],
        encounters=[
            SimpleNamespace(
                encounter_id="published-encounter",
                class_code="PUB",
                encounter_type="Published encounter",
                reason_display="Published-only source event",
                period=SimpleNamespace(start=datetime(2026, 2, 3), end=None),
                linked_conditions=[],
            )
        ],
        encounter_index={},
    )
    stats = SimpleNamespace(name="Published Patient")

    monkeypatch.setattr(patients_router, "load_patient", lambda _patient_id: (record, stats))
    monkeypatch.setattr(patients_router, "load_active_published_run", lambda _patient_id: {"run_id": "active"})
    monkeypatch.setattr(patients_router, "_patient_fhir_uuid", lambda _patient_id: "global-sof-patient")
    monkeypatch.setattr(patients_router, "_sof_db_path", lambda: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(patients_router, "_authorized_patient_id", lambda _request, patient_id: patient_id)

    def fail_connect(*_args, **_kwargs):
        raise AssertionError("global SOF should not be queried for active published snapshots")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)

    response = patients_router.get_care_journey("synthea-id-with-active-snapshot", SimpleNamespace())

    assert [item.type_text for item in response.encounters] == ["Published encounter"]


def test_active_published_agent_sql_tool_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(agent_sdk, "load_active_published_run", lambda _patient_id: {"run_id": "active"})

    def fail_sql(*_args, **_kwargs):
        raise AssertionError("global SOF should not be queried for active published snapshots")

    monkeypatch.setattr(agent_sdk, "_sof_run_sql", fail_sql)

    result = agent_sdk._run_sql_for_patient_scope(
        "synthea-id-with-active-snapshot",
        "SELECT COUNT(*) FROM patient",
        10,
    )

    assert result.error is not None
    assert "active published chart snapshot" in result.error
    assert result.row_count == 0
