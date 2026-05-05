"""Tests for the skill runtime: workspace + patient memory + CT.gov client + runner.

Covers the workspace contract enforced in `api.core.skills.workspace` and
the cross-run patient memory layer in `api.core.skills.patient_memory`,
plus the ClinicalTrials.gov v2 parser. The runner is exercised end-to-end
against a stub CT.gov transport so no live HTTP is made.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from api.core.skills import clinicaltrials_gov as ctgov
from api.core.skills.loader import SKILLS_ROOT, load_skill
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.runner import SkillRunner
from api.core.skills.workspace import (
    CASES_ROOT as WS_CASES_ROOT,
    Workspace,
    WorkspaceContractError,
    allocate_run_dir,
    list_runs,
    load_workspace,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_cases_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect CASES_ROOT for each test so files don't collide."""
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    monkeypatch.setenv("SKILLS_CASES_PATH", str(cases_root))
    # Patch the already-imported module-level constants too.
    import api.core.skills.workspace as workspace_module
    import api.core.skills.patient_memory as memory_module
    monkeypatch.setattr(workspace_module, "CASES_ROOT", cases_root)
    monkeypatch.setattr(memory_module, "CASES_ROOT", cases_root)
    return cases_root


@pytest.fixture()
def trial_skill():
    return load_skill(SKILLS_ROOT / "trial-matching")


def _fresh_workspace(skill, patient_id: str = "patient-001") -> Workspace:
    memory = PatientMemory(patient_id)
    run_dir = allocate_run_dir(patient_id, skill.name)
    return Workspace(
        skill=skill,
        patient_id=patient_id,
        patient_memory=memory,
        run_dir=run_dir,
        brief={"foo": "bar"},
    )


# ── Workspace primitives ────────────────────────────────────────────────────


def test_start_writes_workspace_template_and_brief(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()

    md = ws.workspace_md_path.read_text("utf-8")
    assert "Trial Matching" in md
    brief = json.loads((ws.run_dir / "brief.json").read_text("utf-8"))
    assert brief["foo"] == "bar"
    assert brief["started_at"]
    assert ws.status == "running"


def test_cite_returns_sequential_ids_and_persists(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    cid_a = ws.cite(
        claim="Active diabetes diagnosis",
        source_kind="fhir_resource",
        source_ref="Condition/diabetes-1",
        evidence_tier="T1",
    )
    cid_b = ws.cite(
        claim="Trial NCT12345678 retrieved",
        source_kind="external_url",
        source_ref="https://clinicaltrials.gov/study/NCT12345678",
        evidence_tier="T2",
    )
    assert cid_a == "c_0001"
    assert cid_b == "c_0002"

    persisted = (ws.run_dir / "citations.jsonl").read_text("utf-8").splitlines()
    assert len(persisted) == 2
    rec_a = json.loads(persisted[0])
    assert rec_a["evidence_tier"] == "T1"


def test_cite_rejects_invalid_source_kind(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    with pytest.raises(WorkspaceContractError, match="invalid source_kind"):
        ws.cite(
            claim="x",
            source_kind="rumor",
            source_ref="foo",
            evidence_tier="T1",
        )


def test_cite_requires_source_ref_for_fhir_or_url(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    with pytest.raises(WorkspaceContractError, match="source_ref is required"):
        ws.cite(
            claim="x",
            source_kind="fhir_resource",
            source_ref=None,
            evidence_tier="T1",
        )


def test_cite_allows_agent_inference_without_source_ref(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    cid = ws.cite(
        claim="agent inferred fit signal",
        source_kind="agent_inference",
        source_ref=None,
        evidence_tier="T4",
    )
    assert cid.startswith("c_")


def test_cite_rejects_invalid_tier(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    with pytest.raises(WorkspaceContractError, match="evidence_tier"):
        ws.cite(
            claim="x",
            source_kind="agent_inference",
            source_ref=None,
            evidence_tier="T9",
        )


def test_write_with_unregistered_citation_rejected(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    with pytest.raises(WorkspaceContractError, match="unregistered citation"):
        ws.write(
            section="bad",
            content="A claim [cite:c_0099].",
        )


def test_write_with_registered_citation_succeeds(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    cid = ws.cite(
        claim="x",
        source_kind="fhir_resource",
        source_ref="Condition/x",
        evidence_tier="T1",
    )
    ws.write(
        section="findings",
        content=f"This is grounded in [cite:{cid}] reality.",
        citation_ids=[cid],
    )
    md = ws.workspace_md_path.read_text("utf-8")
    assert f"[cite:{cid}]" in md


# ── Escalations ─────────────────────────────────────────────────────────────


def test_escalate_with_declared_condition_succeeds(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    esc = ws.escalate(
        condition="no_anchor_condition",
        prompt="Confirm the patient has an anchor condition.",
    )
    assert esc.approval_id == "a_0001"
    assert ws.status == "escalated"

    persisted = (ws.run_dir / "approvals.jsonl").read_text("utf-8").strip().splitlines()
    assert len(persisted) == 1


def test_escalate_with_undeclared_condition_rejected(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    with pytest.raises(WorkspaceContractError, match="not in skill manifest"):
        ws.escalate(
            condition="random_condition",
            prompt="Do something.",
        )


def test_escalate_ad_hoc_prefix_allowed(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    esc = ws.escalate(
        condition="ad_hoc:network_unreachable",
        prompt="Network down — retry?",
    )
    assert esc.approval_id == "a_0001"
    assert ws.status == "escalated"


def test_resolve_escalation_returns_run_to_running(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    esc = ws.escalate(
        condition="no_anchor_condition", prompt="Confirm anchor."
    )
    ws.resolve_escalation(esc.approval_id, choice="confirmed", actor="clinician")
    assert ws.status == "running"
    assert all(e.resolved for e in ws._escalations)


def test_resolve_unknown_escalation_rejected(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    with pytest.raises(WorkspaceContractError, match="not found"):
        ws.resolve_escalation("a_9999", choice="ok")


def test_double_resolve_rejected(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    esc = ws.escalate(condition="no_anchor_condition", prompt="x")
    ws.resolve_escalation(esc.approval_id, choice="ok")
    with pytest.raises(WorkspaceContractError, match="already resolved"):
        ws.resolve_escalation(esc.approval_id, choice="again")


# ── Finalize / output schema ────────────────────────────────────────────────


def _valid_output(ws: Workspace) -> dict[str, Any]:
    return {
        "run_id": ws.run_id,
        "skill_version": ws.skill.manifest.version,
        "patient_id": ws.patient_id,
        "summary": {
            "trials_reviewed": 1,
            "trials_surviving": 1,
            "trials_excluded": 0,
            "confidence_note": "ok",
        },
        "trials": [
            {
                "nct_id": "NCT12345678",
                "title": "A test trial",
                "fit_score": 80,
                "evidence_tier": "T2",
                "supporting_facts": [
                    {
                        "claim": "active condition",
                        "source_kind": "fhir_resource",
                        "source_ref": "Condition/x",
                        "evidence_tier": "T1",
                    }
                ],
                "gaps": [],
                "excluded": False,
                "escalation_triggered": False,
            }
        ],
        "escalations": [],
    }


def test_finalize_writes_output_when_schema_passes(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    final = ws.finalize(_valid_output(ws))
    assert ws.status == "finished"
    assert (ws.run_dir / "output.json").is_file()
    assert final["trials"][0]["nct_id"] == "NCT12345678"


def test_finalize_rejects_invalid_output(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    bad = _valid_output(ws)
    bad["trials"][0]["nct_id"] = "BAD_FORMAT"  # violates pattern
    with pytest.raises(WorkspaceContractError, match="schema validation"):
        ws.finalize(bad)


# ── Save destinations + patient memory ─────────────────────────────────────


def test_save_run_edits_writes_clinician_edits(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    ws.finalize(_valid_output(ws))
    path = ws.save_run_edits("Looks good — added context.", actor="dr.maxgibber")

    assert path.is_file()
    text = path.read_text("utf-8")
    assert "Looks good" in text
    assert "dr.maxgibber" in text


def test_pin_to_patient_writes_pinned_md_with_citation(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill, patient_id="patient-pin-001")
    ws.start()
    cid = ws.cite(
        claim="active dx",
        source_kind="fhir_resource",
        source_ref="Condition/abc",
        evidence_tier="T1",
    )
    ws.finalize(_valid_output(ws))
    ws.pin_to_patient(
        [{"text": "Patient prefers trials in CA only.", "citation_id": cid}],
        actor="dr.maxgibber",
    )

    memory = PatientMemory("patient-pin-001")
    pinned = memory.pinned()
    assert "Patient prefers trials in CA only." in pinned
    assert "Condition/abc" in pinned
    notes = memory.notes()
    assert any(n["kind"] == "pin_to_patient" for n in notes)


def test_pin_with_unknown_citation_rejected(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill)
    ws.start()
    with pytest.raises(WorkspaceContractError, match="unknown citation"):
        ws.pin_to_patient([{"text": "fact", "citation_id": "c_0099"}])


def test_save_as_context_package(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill, patient_id="patient-ctx-001")
    ws.start()
    ws.save_as_context_package(
        "patient-trial-prefs",
        "## Patient preferences\n\n- Geography: West Coast only\n",
        actor="dr.maxgibber",
    )
    memory = PatientMemory("patient-ctx-001")
    pkgs = memory.context_packages()
    assert "patient-trial-prefs" in pkgs
    assert "West Coast" in pkgs["patient-trial-prefs"]


def test_session_context_includes_pinned_and_packages(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill, patient_id="patient-session-001")
    ws.start()
    cid = ws.cite(
        claim="x",
        source_kind="fhir_resource",
        source_ref="Condition/y",
        evidence_tier="T2",
    )
    ws.finalize(_valid_output(ws))
    ws.pin_to_patient([{"text": "Pin one", "citation_id": cid}])
    ws.save_as_context_package("trial-prefs", "Pkg content")

    memory = PatientMemory("patient-session-001")
    rendered = memory.session_context(["trial-prefs"])
    assert "pinned facts" in rendered
    assert "Pin one" in rendered
    assert "trial-prefs" in rendered
    assert "Pkg content" in rendered


# ── load_workspace replay ───────────────────────────────────────────────────


def test_load_workspace_round_trips_state(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill, patient_id="rep-001")
    ws.start()
    ws.cite(
        claim="x",
        source_kind="fhir_resource",
        source_ref="Condition/y",
        evidence_tier="T2",
    )
    ws.escalate(condition="no_anchor_condition", prompt="hmm")

    rehydrated = load_workspace(trial_skill, "rep-001", ws.run_id)
    assert rehydrated.status == "escalated"
    assert len(rehydrated.citations()) == 1
    assert len(rehydrated.pending_escalations()) == 1


def test_list_runs_finds_runs(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill, patient_id="list-001")
    ws.start()
    runs = list_runs("list-001")
    assert any(r["run_id"] == ws.run_id for r in runs)


# ── ClinicalTrials.gov client ──────────────────────────────────────────────


_SAMPLE_STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT01234567",
            "briefTitle": "Test Trial",
            "officialTitle": "An Official Test Trial",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "lastUpdateSubmitDate": "2026-01-15",
        },
        "designModule": {"phases": ["PHASE2"]},
        "conditionsModule": {"conditions": ["Diabetes Mellitus"]},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Acme Pharma"}},
        "eligibilityModule": {
            "minimumAge": "18 Years",
            "maximumAge": "75 Years",
            "sex": "ALL",
            "healthyVolunteers": False,
            "eligibilityCriteria": (
                "Inclusion Criteria:\n"
                "- Adults aged 18-75\n"
                "- Diagnosed with Type 2 Diabetes\n"
                "- HbA1c >= 7.0%\n\n"
                "Exclusion Criteria:\n"
                "- Pregnancy\n"
                "- Severe renal impairment\n"
            ),
        },
        "descriptionModule": {
            "briefSummary": "Brief summary text.",
            "detailedDescription": "Detailed description text.",
        },
        "contactsLocationsModule": {
            "centralContacts": [{"name": "Coord", "phone": "555-0100"}],
            "locations": [
                {"facility": "Site A", "city": "Boston", "state": "MA", "country": "USA"},
                {"facility": "Site B", "city": "San Francisco", "state": "CA", "country": "USA"},
            ],
        },
    }
}


class StubTransport:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, params))
        return self.payload

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_search_parses_studies() -> None:
    transport = StubTransport({"studies": [_SAMPLE_STUDY]})
    results = await ctgov.search(condition="diabetes", transport=transport)
    assert len(results) == 1
    assert results[0].nct_id == "NCT01234567"
    assert "Diabetes Mellitus" in results[0].conditions
    assert results[0].locations_count == 2


@pytest.mark.asyncio
async def test_get_record_parses_inclusion_exclusion() -> None:
    transport = StubTransport(_SAMPLE_STUDY)
    record = await ctgov.get_record("NCT01234567", transport=transport)
    assert "Adults aged 18-75" in record.inclusion_lines
    assert "Pregnancy" in record.exclusion_lines


def test_invalid_nct_id_rejected() -> None:
    with pytest.raises(ValueError):
        asyncio.run(ctgov.get_record("BAD12345"))


@pytest.mark.asyncio
async def test_search_filters_by_sex() -> None:
    male_only = json.loads(json.dumps(_SAMPLE_STUDY))
    male_only["protocolSection"]["eligibilityModule"]["sex"] = "MALE"
    transport = StubTransport({"studies": [male_only]})
    out = await ctgov.search(condition="x", sex="FEMALE", transport=transport)
    assert out == []


# ── Runner end-to-end with stub transport ──────────────────────────────────


class MultiResponseStubTransport:
    """Returns different payloads for /studies vs /studies/{nct_id}."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, params))
        if path == "/studies":
            return {"studies": [_SAMPLE_STUDY]}
        if path.startswith("/studies/"):
            return _SAMPLE_STUDY
        return {}

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_runner_end_to_end_produces_valid_output(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill, patient_id="e2e-001")
    transport = MultiResponseStubTransport()
    runner = SkillRunner(
        skill=trial_skill,
        workspace=ws,
        patient_memory=PatientMemory("e2e-001"),
        brief={
            "anchors": [
                {"display": "Diabetes Mellitus", "resource_id": "Condition/dm-1"}
            ],
            "page_size": 5,
            "_test_ctgov_transport": transport,
        },
    )
    result = await runner.run()
    assert result.status == "finished"
    assert result.output is not None
    assert result.output["trials"][0]["nct_id"] == "NCT01234567"
    md = ws.workspace_md_path.read_text("utf-8")
    assert "NCT01234567" in md
    assert "[cite:c_" in md  # citation chips embedded


@pytest.mark.asyncio
async def test_runner_escalates_on_no_anchors(trial_skill) -> None:
    ws = _fresh_workspace(trial_skill, patient_id="noanchor-001")
    runner = SkillRunner(
        skill=trial_skill,
        workspace=ws,
        patient_memory=PatientMemory("noanchor-001"),
        brief={"anchors": []},
    )
    result = await runner.run()
    assert result.status == "escalated"
    pending = ws.pending_escalations()
    assert pending and pending[0].condition == "no_anchor_condition"
