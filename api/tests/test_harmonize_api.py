"""Tests for /api/harmonize endpoints.

The blake-real tests rely on demo collection source files living in the
corpus drop; they skip gracefully when the source files aren't available
so the suite still passes on a fresh checkout without the private data.

The upload-derived collection tests use a tempdir override so they run
on any checkout without external state.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.core.harmonize_service import _BLAKE_DIR
from api.main import app


_DEMO_AVAILABLE = (_BLAKE_DIR / "cedars-healthskillz-download" / "health-records.json").exists()


@unittest.skipUnless(_DEMO_AVAILABLE, "blake-real source files not present in this checkout")
class HarmonizeAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_collections_lists_blake_real(self) -> None:
        r = self.client.get("/api/harmonize/collections")
        self.assertEqual(r.status_code, 200)
        ids = {c["id"] for c in r.json()["collections"]}
        self.assertIn("blake-real", ids)

    def test_synthea_demo_collection_self_bootstraps(self) -> None:
        """Synthea demo collection appears whenever the public Synthea data
        shipped with the repo is available — does not need Blake's data."""
        r = self.client.get("/api/harmonize/collections")
        ids = {c["id"] for c in r.json()["collections"]}
        self.assertIn("synthea-demo", ids)
        sources = self.client.get("/api/harmonize/synthea-demo/sources").json()
        self.assertEqual(len(sources["sources"]), 2)
        labels = {s["label"] for s in sources["sources"]}
        self.assertEqual(labels, {"EHR snapshot · 2018", "EHR snapshot · 2024"})

    def test_synthea_demo_has_cross_source_conditions(self) -> None:
        """Chronic conditions carry across the temporal split → cross-source merges."""
        r = self.client.get("/api/harmonize/synthea-demo/conditions")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreater(body["total"], 5)
        self.assertGreater(body["cross_source"], 0)

    def test_sources_for_blake_real_returns_five(self) -> None:
        r = self.client.get("/api/harmonize/blake-real/sources")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["collection_id"], "blake-real")
        # Cedars FHIR + Cedars PDF + 3 Function Health PDFs = 5 sources
        self.assertEqual(len(body["sources"]), 5)
        kinds = {s["kind"] for s in body["sources"]}
        self.assertEqual(kinds, {"fhir-pull", "extracted-pdf"})

    def test_sources_for_unknown_collection_404s(self) -> None:
        r = self.client.get("/api/harmonize/does-not-exist/sources")
        self.assertEqual(r.status_code, 404)

    def test_observations_returns_cross_source_merges(self) -> None:
        r = self.client.get("/api/harmonize/blake-real/observations")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreater(body["total"], 0)
        self.assertGreater(body["cross_source"], 10)
        # Spot-check shape
        first = body["merged"][0]
        self.assertIn("canonical_name", first)
        self.assertIn("loinc_code", first)
        self.assertIn("sources", first)

    def test_observations_cross_source_only_filter(self) -> None:
        full = self.client.get("/api/harmonize/blake-real/observations").json()
        cross = self.client.get(
            "/api/harmonize/blake-real/observations?cross_source_only=true"
        ).json()
        self.assertEqual(len(cross["merged"]), full["cross_source"])
        self.assertLess(len(cross["merged"]), len(full["merged"]))

    def test_conditions_returns_merges(self) -> None:
        r = self.client.get("/api/harmonize/blake-real/conditions")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreater(body["total"], 10)
        self.assertGreaterEqual(body["cross_source"], 1)
        # Spot-check coding fields
        for m in body["merged"]:
            if m["snomed"]:
                self.assertTrue(m["snomed"].isdigit() or "-" in m["snomed"])
                break
        else:
            self.fail("Expected at least one merged Condition with a SNOMED code")

    def test_medications_returns_cross_source_merges(self) -> None:
        r = self.client.get("/api/harmonize/blake-real/medications")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Cedars FHIR has 7 MedicationRequests; the PDF extraction adds 6 — most
        # should cross-source-merge via RxNorm + drug-name bridge.
        self.assertGreater(body["total"], 5)
        self.assertGreaterEqual(body["cross_source"], 5)
        # Spot-check shape
        first = body["merged"][0]
        self.assertIn("canonical_name", first)
        self.assertIn("rxnorm_codes", first)
        self.assertIn("is_active", first)

    def test_allergies_endpoint(self) -> None:
        r = self.client.get("/api/harmonize/blake-real/allergies")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Cedars FHIR + Cedars PDF each have one "No Known Allergies" record;
        # they merge via name-bridge.
        self.assertGreaterEqual(body["total"], 1)

    def test_immunizations_endpoint(self) -> None:
        r = self.client.get("/api/harmonize/blake-real/immunizations")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Cedars FHIR has 10 Immunizations; PDF has 8; cross-source merges should
        # cover the same-day pairs across both sources.
        self.assertGreater(body["total"], 5)
        self.assertGreaterEqual(body["cross_source"], 5)
        # Spot-check shape: occurrence_date is required for the chronological view.
        self.assertTrue(any(m.get("occurrence_date") for m in body["merged"]))

    def test_contributions_for_cedars_fhir_document_reference(self) -> None:
        # The blake-real registry attaches this DocumentReference to the
        # Cedars-Sinai FHIR pull, which is the heaviest source in the bundle.
        r = self.client.get(
            "/api/harmonize/blake-real/contributions/DocumentReference/cedars-healthskillz-2025-11-07"
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["label"], "Cedars-Sinai (FHIR)")
        self.assertEqual(body["kind"], "fhir-pull")
        # Cedars FHIR contributes to most resource types.
        totals = body["totals"]
        self.assertGreater(totals["observations"], 50)
        self.assertGreater(totals["conditions"], 5)
        self.assertGreaterEqual(totals["medications"], 7)
        self.assertGreaterEqual(totals["allergies"], 1)
        self.assertGreaterEqual(totals["immunizations"], 5)
        self.assertGreater(totals["all"], 60)

    def test_contributions_for_unknown_document_returns_zero_facts(self) -> None:
        r = self.client.get(
            "/api/harmonize/blake-real/contributions/DocumentReference/does-not-exist"
        )
        self.assertEqual(r.status_code, 200)
        totals = r.json()["totals"]
        self.assertEqual(totals["all"], 0)

    def test_source_diff_returns_per_source_unique_vs_shared(self) -> None:
        r = self.client.get("/api/harmonize/blake-real/source-diff")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Five registered sources in blake-real.
        self.assertEqual(len(body["sources"]), 5)
        # Cedars (FHIR) should have substantial unique contributions
        # (older immunizations, vitals not in summary PDF, etc.).
        cedars_fhir = next(
            s for s in body["sources"] if s["label"] == "Cedars-Sinai (FHIR)"
        )
        self.assertGreater(cedars_fhir["totals"]["unique"]["all"], 20)
        self.assertGreater(cedars_fhir["totals"]["shared"]["all"], 0)

    def test_source_diff_unique_facts_listed(self) -> None:
        body = self.client.get("/api/harmonize/blake-real/source-diff").json()
        cedars_pdf = next(
            s for s in body["sources"] if s["label"] == "Cedars-Sinai (PDF)"
        )
        # Unique-fact lists should match the totals.
        u = cedars_pdf["totals"]["unique"]
        self.assertEqual(len(cedars_pdf["unique_facts"]["observations"]), u["observations"])
        self.assertEqual(len(cedars_pdf["unique_facts"]["conditions"]), u["conditions"])

    def test_source_diff_unknown_collection_404s(self) -> None:
        r = self.client.get("/api/harmonize/does-not-exist/source-diff")
        self.assertEqual(r.status_code, 404)

    def test_provenance_for_known_merged_obs_ref(self) -> None:
        # First find any cross-source merged observation
        obs = self.client.get(
            "/api/harmonize/blake-real/observations?cross_source_only=true"
        ).json()["merged"]
        self.assertGreater(len(obs), 0)
        merged_ref = obs[0]["merged_ref"]

        r = self.client.get(
            f"/api/harmonize/blake-real/provenance/{merged_ref}"
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["merged_ref"], merged_ref)
        prov = body["provenance"]
        self.assertEqual(prov["resourceType"], "Provenance")
        self.assertGreaterEqual(len(prov["entity"]), 2)

    def test_provenance_unknown_ref_404s(self) -> None:
        r = self.client.get(
            "/api/harmonize/blake-real/provenance/Observation/merged-loinc-9999999-9"
        )
        self.assertEqual(r.status_code, 404)


class UploadCollectionDiscoveryTests(unittest.TestCase):
    """Verify the registry surfaces upload-session directories as collections."""

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="harmonize-test-"))
        # Patch the UPLOADS_ROOT module global so discovery scans our tempdir.
        from api.core import harmonize_service
        from api.core import harmonization_runs
        from api.core import published_charts

        self._old_root = harmonize_service.UPLOADS_ROOT
        self._old_profile_root = harmonize_service.PROFILE_ROOT
        self._old_profile_registry_path = harmonize_service.PROFILE_REGISTRY_PATH
        self._old_runs_root = harmonization_runs.RUNS_ROOT
        self._old_published_root = published_charts.PUBLISHED_ROOT
        harmonize_service.UPLOADS_ROOT = self._tmp
        harmonize_service.PROFILE_ROOT = self._tmp / "profiles"
        harmonize_service.PROFILE_REGISTRY_PATH = harmonize_service.PROFILE_ROOT / "profiles.json"
        harmonization_runs.RUNS_ROOT = self._tmp / "runs"
        published_charts.PUBLISHED_ROOT = self._tmp / "published"
        # Bust caches so discovery reads from the new root.
        harmonize_service._cached_load.cache_clear()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        from api.core import harmonize_service
        from api.core import harmonization_runs
        from api.core import published_charts

        harmonize_service.UPLOADS_ROOT = self._old_root
        harmonize_service.PROFILE_ROOT = self._old_profile_root
        harmonize_service.PROFILE_REGISTRY_PATH = self._old_profile_registry_path
        harmonization_runs.RUNS_ROOT = self._old_runs_root
        published_charts.PUBLISHED_ROOT = self._old_published_root
        harmonize_service._cached_load.cache_clear()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _stage_session(self, session_id: str) -> Path:
        """Create one upload session with a FHIR JSON + a PDF (no extraction yet)."""
        sess = self._tmp / session_id
        sess.mkdir(parents=True, exist_ok=True)
        # Minimal FHIR-shaped JSON
        (sess / "labs.json").write_text(
            json.dumps(
                {
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "code": {
                                    "coding": [
                                        {"system": "http://loinc.org", "code": "4548-4"}
                                    ],
                                    "text": "A1C",
                                },
                                "valueQuantity": {"value": 5.2, "unit": "%"},
                                "effectiveDateTime": "2025-11-29",
                            }
                        }
                    ],
                }
            )
        )
        # Empty stub PDF (won't be extracted in this test; just shape coverage)
        (sess / "report.pdf").write_bytes(b"%PDF-1.4 stub")
        return sess

    def _stage_clinical_session(self, session_id: str) -> Path:
        """Create a source with clinical-document resources beyond core facts."""
        sess = self._tmp / session_id
        sess.mkdir(parents=True, exist_ok=True)
        note_text = "Assessment: chronic kidney disease risk discussed. Follow up with PCP."
        (sess / "clinical.json").write_text(
            json.dumps(
                {
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "enc-1",
                                "status": "finished",
                                "class": {"code": "AMB"},
                                "type": [{"text": "Office visit"}],
                                "period": {"start": "2026-02-03", "end": "2026-02-03"},
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "creatinine-1",
                                "status": "final",
                                "code": {
                                    "coding": [
                                        {
                                            "system": "http://loinc.org",
                                            "code": "2160-0",
                                            "display": "Creatinine [Mass/volume] in Serum or Plasma",
                                        }
                                    ],
                                    "text": "Creatinine",
                                },
                                "valueQuantity": {"value": 1.8, "unit": "mg/dL"},
                                "effectiveDateTime": "2026-02-03",
                                "encounter": {"reference": "Encounter/enc-1"},
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Procedure",
                                "id": "proc-1",
                                "status": "completed",
                                "code": {"text": "Renal ultrasound"},
                                "performedDateTime": "2026-02-03",
                                "encounter": {"reference": "Encounter/enc-1"},
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "DiagnosticReport",
                                "id": "report-1",
                                "status": "final",
                                "category": [{"text": "Laboratory"}],
                                "code": {"text": "Renal function panel"},
                                "effectiveDateTime": "2026-02-03",
                                "encounter": {"reference": "Encounter/enc-1"},
                                "result": [{"reference": "Observation/creatinine-1"}],
                                "presentedForm": [
                                    {
                                        "contentType": "text/plain",
                                        "data": base64.b64encode(note_text.encode("utf-8")).decode("ascii"),
                                    }
                                ],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Condition",
                                "id": "condition-note-1",
                                "clinicalStatus": {"text": "active"},
                                "code": {"text": "Kidney function concern"},
                                "onsetDateTime": "2026-02-03",
                                "note": [{"text": note_text}],
                            }
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return sess

    def _sample_patient_id(self) -> str:
        from api.core.loader import list_patient_files, patient_id_from_path

        files = list_patient_files()
        if not files:
            self.skipTest("Synthea sample patient files not present")
        return patient_id_from_path(files[0])

    def test_discovery_lists_upload_collection(self) -> None:
        self._stage_session("alice-2026")
        r = self.client.get("/api/harmonize/collections")
        self.assertEqual(r.status_code, 200)
        ids = {c["id"] for c in r.json()["collections"]}
        self.assertIn("upload-alice-2026", ids)

    def test_upload_collection_sources_count_pdfs_and_jsons(self) -> None:
        self._stage_session("bob-001")
        r = self.client.get("/api/harmonize/upload-bob-001/sources")
        self.assertEqual(r.status_code, 200)
        srcs = r.json()["sources"]
        kinds = {s["kind"] for s in srcs}
        self.assertEqual(kinds, {"fhir-pull", "extracted-pdf"})
        # PDF source unavailable until extraction is run; FHIR source available.
        by_kind = {s["kind"]: s for s in srcs}
        self.assertTrue(by_kind["fhir-pull"]["available"])
        self.assertFalse(by_kind["extracted-pdf"]["available"])

    def test_upload_collection_observations_include_fhir_source(self) -> None:
        self._stage_session("carol-x")
        r = self.client.get("/api/harmonize/upload-carol-x/observations")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # The single FHIR-shaped JSON has one Observation (A1C).
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["merged"][0]["loinc_code"], "4548-4")

    def test_patient_workspace_uses_synthea_bundle_as_baseline_source(self) -> None:
        patient_id = self._sample_patient_id()
        r = self.client.get(f"/api/harmonize/workspaces/{patient_id}")
        self.assertEqual(r.status_code, 200)
        workspace = r.json()
        self.assertEqual(workspace["id"], f"workspace-{patient_id}")
        self.assertEqual(workspace["source_count"], 1)

        sources = self.client.get(f"/api/harmonize/{workspace['id']}/sources").json()["sources"]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], "synthea-fhir")
        self.assertEqual(sources[0]["kind"], "fhir-pull")
        self.assertEqual(sources[0]["status"], "structured")

    def test_patient_workspace_attaches_upload_sources(self) -> None:
        patient_id = self._sample_patient_id()
        self._stage_session(patient_id)
        r = self.client.get(f"/api/harmonize/workspaces/{patient_id}")
        self.assertEqual(r.status_code, 200)
        workspace = r.json()
        self.assertEqual(workspace["source_count"], 3)

        sources = self.client.get(f"/api/harmonize/{workspace['id']}/sources").json()["sources"]
        labels = {source["label"] for source in sources}
        self.assertIn("Synthea FHIR patient bundle", labels)
        self.assertIn("labs.json", labels)
        self.assertIn("report.pdf", labels)

    def test_empty_upload_profile_is_empty_harmonize_workspace(self) -> None:
        from api.core import harmonize_service

        profile_id = "workspace-empty-harmonize-test"
        harmonize_service.PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        harmonize_service.PROFILE_REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "profiles": [
                        {
                            "id": profile_id,
                            "display_name": "Empty Harmonize Test",
                            "created_at": "2026-05-05T00:00:00Z",
                            "updated_at": "2026-05-05T00:00:00Z",
                            "notes": "",
                            "storage_mode": "server-local-workspace",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        workspace = self.client.get(f"/api/harmonize/workspaces/{profile_id}")
        self.assertEqual(workspace.status_code, 200)
        body = workspace.json()
        self.assertEqual(body["id"], f"workspace-{profile_id}")
        self.assertEqual(body["name"], "Empty Harmonize Test — patient workspace")
        self.assertEqual(body["source_count"], 0)

        sources = self.client.get(f"/api/harmonize/{body['id']}/sources")
        self.assertEqual(sources.status_code, 200)
        self.assertEqual(sources.json()["sources"], [])

        observations = self.client.get(f"/api/harmonize/{body['id']}/observations")
        self.assertEqual(observations.status_code, 200)
        self.assertEqual(observations.json()["total"], 0)

    def test_harmonization_run_persists_candidate_summary(self) -> None:
        self._stage_session("run-test")

        latest_before = self.client.get("/api/harmonize/upload-run-test/runs/latest")
        self.assertEqual(latest_before.status_code, 200)
        self.assertIsNone(latest_before.json()["latest_run"])

        created = self.client.post("/api/harmonize/upload-run-test/runs")
        self.assertEqual(created.status_code, 201)
        run = created.json()
        self.assertEqual(run["collection_id"], "upload-run-test")
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["rule_version"], "scripted-harmonize-v1")
        self.assertEqual(run["summary"]["source_count"], 2)
        self.assertEqual(run["summary"]["prepared_source_count"], 1)
        self.assertEqual(run["summary"]["needs_preparation_count"], 1)
        self.assertEqual(run["summary"]["candidate_counts"]["observations"], 1)
        self.assertGreaterEqual(run["summary"]["review_item_count"], 1)
        self.assertTrue(any(item["category"] == "source" for item in run["review_items"]))

        latest_after = self.client.get("/api/harmonize/upload-run-test/runs/latest")
        self.assertEqual(latest_after.status_code, 200)
        self.assertEqual(latest_after.json()["latest_run"]["run_id"], run["run_id"])

        fetched = self.client.get(f"/api/harmonize/upload-run-test/runs/{run['run_id']}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["run_id"], run["run_id"])

    def test_publish_rejects_run_with_review_items(self) -> None:
        self._stage_session("blocked-publish")
        run = self.client.post("/api/harmonize/upload-blocked-publish/runs").json()

        published = self.client.post(
            f"/api/harmonize/upload-blocked-publish/runs/{run['run_id']}/publish"
        )
        self.assertEqual(published.status_code, 400)
        self.assertIn("Resolve review items", published.json()["detail"])

    def test_resolving_review_item_unblocks_publish(self) -> None:
        self._stage_session("resolve-review")
        run = self.client.post("/api/harmonize/upload-resolve-review/runs").json()
        self.assertGreaterEqual(run["summary"]["review_item_count"], 1)
        item_id = run["review_items"][0]["id"]

        resolved = self.client.post(
            f"/api/harmonize/upload-resolve-review/runs/{run['run_id']}/review-items/resolve",
            json={
                "item_id": item_id,
                "decision": "dismissed",
                "notes": "Reviewed source blocker for test publish.",
            },
        )
        self.assertEqual(resolved.status_code, 200)
        resolved_run = resolved.json()
        self.assertEqual(resolved_run["summary"]["review_item_count"], 0)
        self.assertTrue(resolved_run["summary"]["publishable"])
        self.assertTrue(resolved_run["review_items"][0]["resolved"])
        self.assertEqual(resolved_run["review_items"][0]["decision"], "dismissed")

        latest = self.client.get("/api/harmonize/upload-resolve-review/runs/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["latest_run"]["summary"]["review_item_count"], 0)

        published = self.client.post(
            f"/api/harmonize/upload-resolve-review/runs/{run['run_id']}/publish"
        )
        self.assertEqual(published.status_code, 201)

    def test_publish_clean_run_and_unpublish(self) -> None:
        sess = self._stage_session("clean-publish")
        (sess / "report.pdf").unlink()

        run = self.client.post("/api/harmonize/upload-clean-publish/runs").json()
        self.assertEqual(run["summary"]["review_item_count"], 0)

        state = self.client.post(
            f"/api/harmonize/upload-clean-publish/runs/{run['run_id']}/publish"
        )
        self.assertEqual(state.status_code, 201)
        body = state.json()
        self.assertIsNotNone(body["active_snapshot"])
        self.assertEqual(body["active_snapshot"]["run_id"], run["run_id"])
        self.assertEqual(len(body["snapshots"]), 1)

        snapshot_id = body["active_snapshot"]["snapshot_id"]
        activated = self.client.post(
            f"/api/harmonize/upload-clean-publish/published/{snapshot_id}/activate"
        )
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["active_snapshot"]["snapshot_id"], snapshot_id)

        unpublished = self.client.delete("/api/harmonize/upload-clean-publish/published/active")
        self.assertEqual(unpublished.status_code, 200)
        self.assertIsNone(unpublished.json()["active_snapshot"])
        self.assertEqual(len(unpublished.json()["snapshots"]), 1)

    def test_published_workspace_feeds_patient_read_endpoints(self) -> None:
        sess = self._stage_session("workspace-downstream")
        (sess / "report.pdf").unlink()

        run = self.client.post("/api/harmonize/workspace-workspace-downstream/runs").json()
        state = self.client.post(
            f"/api/harmonize/workspace-workspace-downstream/runs/{run['run_id']}/publish"
        )
        self.assertEqual(state.status_code, 201)

        overview = self.client.get("/api/patients/workspace-downstream/overview")
        self.assertEqual(overview.status_code, 200)
        body = overview.json()
        self.assertEqual(body["id"], "workspace-downstream")
        self.assertEqual(body["unique_loinc_count"], 1)
        self.assertGreaterEqual(body["total_resources"], 2)

        timeline = self.client.get("/api/patients/workspace-downstream/timeline")
        self.assertEqual(timeline.status_code, 200)
        self.assertGreaterEqual(len(timeline.json()["encounters"]), 1)

        care_journey = self.client.get("/api/patients/workspace-downstream/care-journey")
        self.assertEqual(care_journey.status_code, 200)
        self.assertGreaterEqual(len(care_journey.json()["encounters"]), 1)

        raw_fhir = self.client.get("/api/patients/workspace-downstream/fhir")
        self.assertEqual(raw_fhir.status_code, 200)
        bundle = raw_fhir.json()
        self.assertEqual(bundle["resourceType"], "Bundle")
        resource_types = {entry["resource"]["resourceType"] for entry in bundle["entry"]}
        self.assertIn("Patient", resource_types)
        self.assertIn("Observation", resource_types)

    def test_published_workspace_preserves_clinical_artifacts(self) -> None:
        self._stage_clinical_session("workspace-clinical-artifacts")

        run = self.client.post("/api/harmonize/workspace-workspace-clinical-artifacts/runs").json()
        self.assertEqual(run["summary"]["candidate_counts"]["observations"], 1)
        self.assertEqual(run["summary"]["candidate_counts"]["procedures"], 1)
        self.assertEqual(run["summary"]["candidate_counts"]["diagnostic_reports"], 1)
        self.assertEqual(run["summary"]["candidate_counts"]["clinical_documents"], 1)
        self.assertGreaterEqual(run["summary"]["candidate_counts"]["clinical_notes"], 2)

        state = self.client.post(
            f"/api/harmonize/workspace-workspace-clinical-artifacts/runs/{run['run_id']}/publish"
        )
        self.assertEqual(state.status_code, 201)

        procedures = self.client.get("/api/patients/workspace-clinical-artifacts/procedures")
        self.assertEqual(procedures.status_code, 200)
        self.assertEqual(procedures.json()["total_count"], 1)
        self.assertEqual(procedures.json()["procedures"][0]["display"], "Renal ultrasound")

        care_journey = self.client.get("/api/patients/workspace-clinical-artifacts/care-journey")
        self.assertEqual(care_journey.status_code, 200)
        self.assertEqual(len(care_journey.json()["diagnostic_reports"]), 1)

        raw_fhir = self.client.get("/api/patients/workspace-clinical-artifacts/fhir")
        self.assertEqual(raw_fhir.status_code, 200)
        resource_types = {entry["resource"]["resourceType"] for entry in raw_fhir.json()["entry"]}
        self.assertIn("Procedure", resource_types)
        self.assertIn("DiagnosticReport", resource_types)

    def test_provider_assistant_uses_published_workspace_snapshot(self) -> None:
        sess = self._stage_session("workspace-assistant")
        (sess / "report.pdf").unlink()

        run = self.client.post("/api/harmonize/workspace-workspace-assistant/runs").json()
        state = self.client.post(
            f"/api/harmonize/workspace-workspace-assistant/runs/{run['run_id']}/publish"
        )
        self.assertEqual(state.status_code, 201)

        response = self.client.post(
            "/api/assistant/chat",
            json={
                "patient_id": "workspace-assistant",
                "question": "What A1C result is in this chart?",
                "history": [],
                "context_packages": [],
                "stance": "opinionated",
                "mode": "deterministic",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["patient_id"], "workspace-assistant")
        self.assertNotIn("Patient not found", body["answer"])

    def test_extract_endpoint_rejects_static_collection(self) -> None:
        # blake-real is static; extraction must 400
        r = self.client.post("/api/harmonize/blake-real/extract")
        self.assertEqual(r.status_code, 400)

    def test_extract_starts_async_job_with_no_pdfs(self) -> None:
        """When upload directory contains only FHIR JSON (no PDFs), the job
        completes immediately with empty results."""
        self._stage_session("zen-extract")
        # Remove the PDF stub so the extract has nothing to do (the test
        # fixture's empty-bytes PDF would otherwise fail extraction).
        (self._tmp / "zen-extract" / "report.pdf").unlink()
        r = self.client.post("/api/harmonize/upload-zen-extract/extract")
        self.assertEqual(r.status_code, 202)
        body = r.json()
        self.assertIn(body["status"], ("pending", "running", "complete"))
        job_id = body["job_id"]
        self.assertGreaterEqual(body["progress_percent"], 5)
        self.assertLessEqual(body["progress_percent"], 100)
        latest = self.client.get("/api/harmonize/upload-zen-extract/extract-job")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["job_id"], job_id)

        # Poll until complete (the no-PDFs case finishes in milliseconds).
        import time
        deadline = time.time() + 10
        while time.time() < deadline:
            poll = self.client.get(f"/api/harmonize/extract-jobs/{job_id}").json()
            if poll["status"] in ("complete", "failed"):
                break
            time.sleep(0.05)
        self.assertEqual(poll["status"], "complete")
        self.assertEqual(poll["progress_percent"], 100)
        self.assertEqual(poll["results"], [])

    def test_extract_job_unknown_id_404s(self) -> None:
        r = self.client.get("/api/harmonize/extract-jobs/does-not-exist")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
