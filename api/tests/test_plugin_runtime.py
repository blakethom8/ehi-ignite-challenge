"""End-to-end run lifecycle tests for all three example plugins."""

from pathlib import Path

import pytest

from api.plugins import provenance as prov_log
from api.plugins import runtime as rt
from api.plugins.connectors import UndeclaredConnector
from api.plugins.tools import ApprovalRequired, PermissionDenied
from api.trust.models import UserIdentity


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "DEFAULT_DB_PATH", tmp_path / "runs.db")
    monkeypatch.setattr(prov_log, "DEFAULT_DB_PATH", tmp_path / "provenance.db")
    rt.reset_in_memory_state()
    yield
    rt.reset_in_memory_state()


@pytest.fixture
def clinician() -> UserIdentity:
    return UserIdentity(id="u_clinician_42", name="Dr. Q", role="clinician")


@pytest.fixture
def attending() -> UserIdentity:
    return UserIdentity(id="u_attending_7", name="Dr. Atal", role="attending")


# ============================================================
# Trial Finder — full happy path
# ============================================================


def test_trial_finder_end_to_end(clinician):
    run = rt.start_run(
        plugin_id="trial-finder",
        patient_id="8.4127.881",
        workflow_id="shortlist",
        title="Trial shortlist — Hollister",
        user=clinician,
    )
    assert run.state == "awaiting-consent"

    rt.grant_consent(run.id, approver=clinician)
    run = rt.get_run(run.id)
    assert run.state == "running"

    # Non-outbound tool calls: search + score
    search = rt.call_tool(
        run_id=run.id,
        tool_id="trial.search",
        payload={"connector": "clinicaltrials-gov"},
    )
    assert any(s["nctId"] == "NCT-0421187" for s in search["studies"])

    score = rt.call_tool(
        run_id=run.id, tool_id="trial.score_fit", payload={"nctId": "NCT-0421187"}
    )
    assert score["fit"] > 0.9

    draft = rt.call_tool(
        run_id=run.id, tool_id="packet.draft", payload={"nctId": "NCT-0421187"}
    )
    assert draft["artifactId"]

    # Outbound: request approval, then approve
    appr = rt.request_outbound_approval(
        run_id=run.id,
        tool_id="packet.send",
        tool_payload={
            "channel": "site-packet",
            "site": "MSKCC",
            "artifactId": draft["artifactId"],
        },
        action="send-packet",
        description="Route packet to MSKCC for NCT-0421187",
        payload_preview=draft["preview"],
        destination="MSKCC",
    )
    assert rt.get_run(run.id).state == "waiting"

    result = rt.approve_outbound(approval_id=appr.approvalId, approver=clinician)
    assert result["result"]["status"] == 202
    assert rt.get_run(run.id).state == "running"

    # Provenance written.
    rows = prov_log.list_records(plugin_id="trial-finder")
    assert len(rows) == 1
    prov_log.verify_record(rows[0])
    assert rows[0].action == "send-packet"


def test_run_canvas_tracks_tool_results_and_approved_outbound(clinician):
    run = rt.start_run(
        plugin_id="trial-finder",
        patient_id="8.4127.881",
        workflow_id="packet",
        title="Canvas contract",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)

    draft = rt.call_tool(
        run_id=run.id, tool_id="packet.draft", payload={"nctId": "NCT-0421187"}
    )
    run = rt.get_run(run.id)
    assert run.canvas["packet.draft"] == draft

    approval = rt.request_outbound_approval(
        run_id=run.id,
        tool_id="packet.send",
        tool_payload={
            "channel": "site-packet",
            "site": "MSKCC",
            "artifactId": draft["artifactId"],
        },
        action="send-packet",
        description="Send packet",
        payload_preview=draft["preview"],
        destination="MSKCC",
    )
    outcome = rt.approve_outbound(approval_id=approval.approvalId, approver=clinician)
    run = rt.get_run(run.id)
    assert run.canvas["packet.send"] == outcome["result"]


# ============================================================
# Medication Access — outbound to a different channel
# ============================================================


def test_med_access_pa_submission(clinician):
    run = rt.start_run(
        plugin_id="med-access",
        patient_id="8.4127.881",
        workflow_id="file-pa",
        title="Apixaban PA — Hollister",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)

    barriers = rt.call_tool(
        run_id=run.id, tool_id="med.identify_barriers", payload={}
    )
    assert any("apixaban" in b["drug"].lower() for b in barriers["barriers"])

    compose = rt.call_tool(
        run_id=run.id, tool_id="pa.compose", payload={"drug": "apixaban"}
    )
    assert "apixaban" in compose["preview"].lower()

    appr = rt.request_outbound_approval(
        run_id=run.id,
        tool_id="pa.submit",
        tool_payload={"channel": "pa-submission", "drug": "apixaban"},
        action="submit-application",
        description="Submit apixaban PA to Aetna",
        payload_preview=compose["preview"],
        destination="Aetna Open Access PPO",
    )
    result = rt.approve_outbound(approval_id=appr.approvalId, approver=clinician)
    assert result["result"]["submissionId"].startswith("PA-")

    # Provenance has both endpoint and submissionId summary.
    rows = prov_log.list_records(plugin_id="med-access")
    assert rows[0].endpoint.endswith("/edi/pa/submit")


# ============================================================
# Second Opinion — attending approval
# ============================================================


def test_second_opinion_attending_approval(clinician, attending):
    run = rt.start_run(
        plugin_id="second-opinion",
        patient_id="8.4127.881",
        workflow_id="compose-packet",
        title="Endocrinology referral — Hollister",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)

    compose = rt.call_tool(
        run_id=run.id,
        tool_id="referral.compose_packet",
        payload={"specialty": "endocrinology"},
    )
    assert "Referral packet" in compose["preview"]

    appr = rt.request_outbound_approval(
        run_id=run.id,
        tool_id="referral.route",
        tool_payload={"channel": "consulting-network", "specialty": "endocrinology"},
        action="send-packet",
        description="Route endo referral via ConferMD (attending approval)",
        payload_preview=compose["preview"],
        destination="ConferMD endocrinology network",
        approver_role="attending",
    )
    assert appr.approverRole == "attending"

    result = rt.approve_outbound(approval_id=appr.approvalId, approver=attending)
    assert result["result"]["referenceId"].startswith("CMR-")


# ============================================================
# Revocation invalidates pending approvals
# ============================================================


def test_revocation_survives_restart(clinician):
    """H0.1 regression: revoking consent must persist across an API restart.

    Without rehydration, ``_revoked_ids`` resets to an empty set on boot
    and a previously-revoked run silently regains tool access. The fix:
    ``revoked_at`` column on ``runs`` + ``reload_revoked_runs()`` at startup.
    """
    run = rt.start_run(
        plugin_id="trial-finder",
        patient_id="8.4127.881",
        workflow_id="shortlist",
        title="Restart-survival",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)
    rt.revoke_consent(run.id, approver=clinician)
    assert run.id in rt._revoked_ids

    # Simulate a process restart: drop the cached set.
    rt._revoked_ids.clear()
    assert run.id not in rt._revoked_ids

    # Startup hook re-hydrates from runs.db.
    loaded = rt.reload_revoked_runs()
    assert loaded >= 1
    assert run.id in rt._revoked_ids

    # Tool calls on the revoked run still fail after restart.
    from api.plugins.consent import ConsentError

    with pytest.raises(ConsentError):
        rt.call_tool(
            run_id=run.id,
            tool_id="trial.search",
            payload={"connector": "clinicaltrials-gov"},
        )


def test_revoke_consent_voids_pending_approvals(clinician):
    run = rt.start_run(
        plugin_id="trial-finder",
        patient_id="8.4127.881",
        workflow_id="packet",
        title="Outreach",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)
    draft = rt.call_tool(
        run_id=run.id, tool_id="packet.draft", payload={"nctId": "NCT-0421187"}
    )
    appr = rt.request_outbound_approval(
        run_id=run.id,
        tool_id="packet.send",
        tool_payload={"channel": "site-packet", "site": "MSKCC"},
        action="send-packet",
        description="Send packet",
        payload_preview=draft["preview"],
        destination="MSKCC",
    )
    rt.revoke_consent(run.id, approver=clinician)

    approvals = rt.list_approvals(run.id)
    assert {a["status"] for a in approvals} == {"voided"}
    assert rt.get_run(run.id).state == "revoked"


# ============================================================
# Refusals
# ============================================================


def test_refuse_outbound_without_approval(clinician):
    run = rt.start_run(
        plugin_id="trial-finder",
        patient_id="8.4127.881",
        workflow_id="packet",
        title="Outreach",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)
    # Trying to call an outbound tool directly via call_tool must fail.
    with pytest.raises(ApprovalRequired):
        rt.call_tool(
            run_id=run.id,
            tool_id="packet.send",
            payload={"channel": "site-packet"},
        )


def test_undeclared_connector_in_call_tool(clinician):
    run = rt.start_run(
        plugin_id="trial-finder",
        patient_id="8.4127.881",
        workflow_id="shortlist",
        title="Shortlist",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)
    with pytest.raises(UndeclaredConnector):
        rt.call_tool(
            run_id=run.id,
            tool_id="trial.search",
            payload={"connector": "surescripts-formulary"},
        )


def test_events_emitted_for_run_lifecycle(clinician):
    run = rt.start_run(
        plugin_id="trial-finder",
        patient_id="8.4127.881",
        workflow_id="shortlist",
        title="Shortlist",
        user=clinician,
    )
    rt.grant_consent(run.id, approver=clinician)
    rt.call_tool(
        run_id=run.id, tool_id="trial.search", payload={"connector": "clinicaltrials-gov"}
    )
    events = rt.list_events(run.id)
    kinds = [e["kind"] for e in events]
    assert "run.started" in kinds
    assert "run.consent-granted" in kinds
    assert "tool.result" in kinds
