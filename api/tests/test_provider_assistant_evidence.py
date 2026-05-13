from __future__ import annotations

from datetime import datetime

import api.core.provider_assistant as provider_assistant


def _fact(text: str, resource_id: str, keywords: set[str]) -> provider_assistant._Fact:
    return provider_assistant._Fact(
        text=text,
        citation=provider_assistant.AssistantCitationPayload(
            source_type="MedicationRequest",
            resource_id=resource_id,
            label=text,
            detail=text,
            event_date=datetime(2026, 5, 1),
        ),
        keywords=keywords,
        tags={"medication"},
        priority=10,
    )


def test_provider_evidence_session_reuses_built_fact_corpus(monkeypatch) -> None:
    build_calls = 0

    def fake_build_facts(_patient_id: str):
        nonlocal build_calls
        build_calls += 1
        summary = {
            "patient_name": "Test Patient",
            "parse_warning_count": 0,
            "active_flags": [],
            "interactions": [],
            "active_high_risk_condition_count": 0,
        }
        return (
            [
                _fact("Apixaban active since Apr 2026", "med-apixaban", {"apixaban", "active"}),
                _fact("Creatinine 1.2 mg/dL", "lab-creatinine", {"creatinine", "lab"}),
            ],
            summary,
        )

    monkeypatch.setattr(provider_assistant, "_build_facts", fake_build_facts)

    session = provider_assistant.build_provider_evidence_session("patient-123")

    first = session.get_relevant_evidence("apixaban", history=[], max_facts=4, max_citations=4)
    second = session.get_relevant_evidence("apixaban", history=[], max_facts=4, max_citations=4)
    third = session.get_relevant_evidence("creatinine", history=[], max_facts=4, max_citations=4)

    assert build_calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert third.cache_hit is False
    assert first.payload["evidence_lines"][0] == "Apixaban active since Apr 2026"
    assert "Creatinine 1.2 mg/dL" in third.payload["evidence_lines"]
    assert second.payload == first.payload
