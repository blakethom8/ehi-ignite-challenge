from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import api.core.context_builder as context_builder
from api.core.context_builder import _build_record_lab_context


def test_record_lab_context_recognizes_common_uploaded_lab_loincs() -> None:
    record = SimpleNamespace(
        observations=[
            SimpleNamespace(
                loinc_code="2951-2",
                display="Sodium [Moles/volume] in Serum or Plasma",
                value_quantity=139,
                value_unit="mmol/L",
                effective_dt=datetime(2025, 11, 19),
                status="final",
            ),
            SimpleNamespace(
                loinc_code="2345-7",
                display="Glucose [Mass/volume] in Serum or Plasma",
                value_quantity=115,
                value_unit="mg/dL",
                effective_dt=datetime(2025, 11, 19),
                status="final",
            ),
            SimpleNamespace(
                loinc_code="62238-1",
                display="Glomerular filtration rate/1.73 sq M.predicted",
                value_quantity=42,
                value_unit="mL/min/{1.73_m2}",
                effective_dt=datetime(2026, 2, 3),
                status="final",
            ),
        ]
    )

    lines = _build_record_lab_context(record)

    assert any("Sodium" in line and "139 mmol/L" in line for line in lines)
    assert any("Glucose" in line and "115 mg/dL" in line for line in lines)
    assert any("eGFR" in line and "42 mL/min/{1.73_m2}" in line for line in lines)


def test_record_lab_context_keeps_recent_non_allowlisted_labs() -> None:
    record = SimpleNamespace(
        observations=[
            SimpleNamespace(
                loinc_code="2160-0",
                display="Creatinine",
                value_quantity=1.03,
                value_unit="mg/dL",
                effective_dt=datetime(2025, 11, 19),
                status="final",
            ),
            SimpleNamespace(
                loinc_code="9999-9",
                display="Custom lab captured from source",
                value_quantity=7.5,
                value_unit="units",
                effective_dt=datetime(2026, 1, 2),
                status="final",
            ),
        ]
    )

    lines = _build_record_lab_context(record)

    assert any("Creatinine" in line for line in lines)
    assert any("Custom lab captured from source" in line for line in lines)


def test_active_published_context_skips_global_sof(monkeypatch) -> None:
    record = SimpleNamespace(
        summary=SimpleNamespace(
            name="Published Patient",
            birth_date=None,
            gender="female",
            city="Los Angeles",
            state="CA",
        ),
        medications=[],
        conditions=[],
        observations=[
            SimpleNamespace(
                loinc_code="2160-0",
                display="Published creatinine",
                value_quantity=1.8,
                value_unit="mg/dL",
                effective_dt=datetime(2026, 2, 3),
                status="final",
            )
        ],
        diagnostic_reports=[],
        procedures=[],
        allergies=[],
        encounters=[
            SimpleNamespace(
                period=SimpleNamespace(start=datetime(2026, 2, 3)),
                class_code="PUB",
                encounter_type="Published encounter",
                reason_display="Published-only source event",
                practitioner_name="Published clinician",
                provider_org="Published clinic",
                linked_observations=[],
                linked_conditions=[],
                linked_medications=[],
                linked_procedures=[],
                linked_diagnostic_reports=[],
                linked_immunizations=[],
            )
        ],
    )
    stats = SimpleNamespace(name="Published Patient")

    monkeypatch.setattr(context_builder, "load_patient", lambda _patient_id: (record, stats))
    monkeypatch.setattr(context_builder, "load_active_published_run", lambda _patient_id: {"run_id": "active"})
    monkeypatch.setattr(context_builder, "path_from_patient_id", lambda _patient_id: None)
    monkeypatch.setattr(context_builder, "_patient_uuid_from_id", lambda _patient_id: "global-sof-patient")
    monkeypatch.setattr(context_builder, "DEFAULT_SOF_DB", SimpleNamespace(exists=lambda: True))

    def fail_connect(*_args, **_kwargs):
        raise AssertionError("global SOF should not be queried for active published snapshots")

    monkeypatch.setattr(context_builder.sqlite3, "connect", fail_connect)

    context = context_builder.build_clinical_context("synthea-id-with-active-snapshot")
    prompt = context.to_prompt()

    assert "Published creatinine" in prompt or "Creatinine" in prompt
    assert "Published encounter" in prompt
