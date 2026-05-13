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
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.core.harmonize_service import _BLAKE_DIR
from api.main import app


_DEMO_AVAILABLE = (_BLAKE_DIR / "cedars-healthskillz-download" / "health-records.json").exists()


class HarmonizeDemoAccessTests(unittest.TestCase):
    def test_demo_session_can_open_patient_workspace_collection(self) -> None:
        client = TestClient(app)
        start = client.post("/api/auth/demo", json={"patient_id": "demo-aggregate-icu"})
        self.assertEqual(start.status_code, 200)

        workspace = client.get("/api/harmonize/workspaces/demo-aggregate-icu")
        self.assertEqual(workspace.status_code, 200)
        body = workspace.json()
        self.assertEqual(body["id"], "workspace-demo-aggregate-icu")
        self.assertGreaterEqual(body["source_count"], 1)

    def test_demo_session_can_read_workspace_published_state(self) -> None:
        client = TestClient(app)
        start = client.post("/api/auth/demo", json={"patient_id": "demo-aggregate-icu"})
        self.assertEqual(start.status_code, 200)

        published = client.get("/api/harmonize/workspace-demo-aggregate-icu/published")
        self.assertEqual(published.status_code, 200)
        body = published.json()
        self.assertEqual(body["collection_id"], "workspace-demo-aggregate-icu")


@unittest.skipUnless(_DEMO_AVAILABLE, "blake-real source files not present in this checkout")
class HarmonizeAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        login = self.client.post(
            "/api/auth/login",
            json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
        )
        if login.status_code != 200:
            raise RuntimeError(f"Failed to bootstrap authenticated test client: {login.text}")

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
        login = self.client.post(
            "/api/auth/login",
            json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
        )
        if login.status_code != 200:
            raise RuntimeError(f"Failed to bootstrap authenticated test client: {login.text}")

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
                                "resourceType": "Patient",
                                "id": "patient-1",
                                "name": [{"given": ["Workspace"], "family": "Downstream"}],
                                "gender": "female",
                                "birthDate": "1984-03-02",
                                "address": [{"city": "Los Angeles", "state": "CA"}],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "a1c-primary",
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

    def _stage_ccda_session(
        self,
        session_id: str,
        *,
        given: str = "Ccdatest",
        family: str = "Patient",
        birth_date: str = "19840302",
        gender: str = "F",
        condition: str = "Test-only C-CDA condition",
        medication: str = "Test-only C-CDA medication",
    ) -> Path:
        sess = self._tmp / session_id
        sess.mkdir(parents=True, exist_ok=True)
        (sess / "summary.xml").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <id root="1.2.3" extension="{session_id}"/>
      <patient>
        <name><given>{given}</given><family>{family}</family></name>
        <administrativeGenderCode code="{gender}"/>
        <birthTime value="{birth_date}"/>
      </patient>
    </patientRole>
  </recordTarget>
  <title>Continuity of Care Document</title>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="11450-4"/>
          <title>Problems</title>
          <entry>
            <act>
              <entryRelationship>
                <observation>
                  <effectiveTime><low value="20240101"/></effectiveTime>
                  <value code="999001" displayName="{condition}" codeSystemName="SNOMED CT"/>
                </observation>
              </entryRelationship>
            </act>
          </entry>
        </section>
      </component>
      <component>
        <section>
          <code code="10160-0"/>
          <title>Medications</title>
          <entry>
            <substanceAdministration>
              <effectiveTime><low value="20240203"/></effectiveTime>
              <statusCode code="active"/>
              <consumable>
                <manufacturedProduct>
                  <manufacturedMaterial>
                    <code code="999002" displayName="{medication}" codeSystemName="RxNorm"/>
                  </manufacturedMaterial>
                </manufacturedProduct>
              </consumable>
            </substanceAdministration>
          </entry>
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>
""",
            encoding="utf-8",
        )
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
                                "resourceType": "Organization",
                                "id": "org-1",
                                "name": "Cedars-Sinai Nephrology",
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Practitioner",
                                "id": "prac-1",
                                "name": [
                                    {
                                        "prefix": ["Dr."],
                                        "given": ["Riley"],
                                        "family": "Renal",
                                    }
                                ],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Location",
                                "id": "loc-1",
                                "name": "Cedars-Sinai Outpatient Clinic",
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "enc-1",
                                "status": "finished",
                                "class": {"code": "AMB"},
                                "type": [{"text": "Office visit"}],
                                "period": {"start": "2026-02-03", "end": "2026-02-03"},
                                "serviceProvider": {"reference": "Organization/org-1"},
                                "participant": [
                                    {"individual": {"reference": "Practitioner/prac-1"}}
                                ],
                                "location": [
                                    {"location": {"reference": "Location/loc-1"}}
                                ],
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
                                "performer": [{"reference": "Organization/org-1"}],
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

    def test_upload_collection_includes_ccda_xml_as_structured_source(self) -> None:
        self._stage_ccda_session("ccda-source")
        r = self.client.get("/api/harmonize/upload-ccda-source/sources")
        self.assertEqual(r.status_code, 200)
        srcs = r.json()["sources"]
        self.assertEqual(len(srcs), 1)
        self.assertEqual(srcs[0]["kind"], "ccda-xml")
        self.assertEqual(srcs[0]["status"], "structured")
        self.assertGreaterEqual(srcs[0]["resource_counts"].get("Condition", 0), 1)

        conditions = self.client.get("/api/harmonize/upload-ccda-source/conditions")
        self.assertEqual(conditions.status_code, 200)
        self.assertIn("Test-only C-CDA condition", json.dumps(conditions.json()))

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

    def test_patient_workspace_excludes_mismatched_ccda_facts(self) -> None:
        patient_id = self._sample_patient_id()
        self._stage_ccda_session(
            patient_id,
            given="Victoria",
            family="Wade",
            birth_date="19750501",
            gender="F",
            condition="Test Mismatch Disorder",
            medication="Test Mismatch Medication",
        )

        workspace = self.client.get(f"/api/harmonize/workspaces/{patient_id}").json()
        sources = self.client.get(f"/api/harmonize/{workspace['id']}/sources").json()["sources"]
        ccda_source = next(source for source in sources if source["kind"] == "ccda-xml")
        self.assertEqual(ccda_source["status"], "identity_mismatch")
        self.assertEqual(ccda_source["total_resources"], 0)

        conditions = self.client.get(f"/api/harmonize/{workspace['id']}/conditions")
        self.assertEqual(conditions.status_code, 200)
        self.assertNotIn("Test Mismatch Disorder", json.dumps(conditions.json()))

        exported = self.client.get(f"/api/harmonize/{workspace['id']}/export-workspace")
        self.assertEqual(exported.status_code, 200)
        with zipfile.ZipFile(BytesIO(exported.content)) as zf:
            root = next(name.split("/", 1)[0] for name in zf.namelist() if "/" in name)
            facts = json.loads(zf.read(f"{root}/evidence/canonical-facts.json"))["facts"]
        self.assertNotIn("Test Mismatch Disorder", json.dumps(facts))

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
        self.assertIsNone(resolved_run["review_items"][0]["selected_source_ref"])

        latest = self.client.get("/api/harmonize/upload-resolve-review/runs/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["latest_run"]["summary"]["review_item_count"], 0)

        published = self.client.post(
            f"/api/harmonize/upload-resolve-review/runs/{run['run_id']}/publish"
        )
        self.assertEqual(published.status_code, 201)

    def test_review_decisions_append_audit_events_and_publish_summary(self) -> None:
        self._stage_session("review-audit")
        run = self.client.post("/api/harmonize/upload-review-audit/runs").json()
        item_id = run["review_items"][0]["id"]
        self.assertEqual(run["review_events"], [])
        self.assertEqual(run["review_decision_summary"]["event_count"], 0)

        deferred = self.client.post(
            f"/api/harmonize/upload-review-audit/runs/{run['run_id']}/review-items/resolve",
            json={
                "item_id": item_id,
                "decision": "deferred",
                "notes": "Needs source owner confirmation.",
            },
        )
        self.assertEqual(deferred.status_code, 200)
        deferred_run = deferred.json()
        self.assertEqual(deferred_run["summary"]["review_item_count"], 1)
        self.assertEqual(deferred_run["review_decision_summary"]["event_count"], 1)
        self.assertEqual(deferred_run["review_decision_summary"]["decisions"]["deferred"], 1)
        self.assertFalse(deferred_run["review_events"][0]["previous_resolved"])
        self.assertEqual(deferred_run["review_events"][0]["decision"], "deferred")

        dismissed = self.client.post(
            f"/api/harmonize/upload-review-audit/runs/{run['run_id']}/review-items/resolve",
            json={
                "item_id": item_id,
                "decision": "dismissed",
                "notes": "Reviewed and accepted source gap for this run.",
            },
        )
        self.assertEqual(dismissed.status_code, 200)
        dismissed_run = dismissed.json()
        self.assertEqual(dismissed_run["summary"]["review_item_count"], 0)
        self.assertTrue(dismissed_run["summary"]["publishable"])
        self.assertEqual(len(dismissed_run["review_events"]), 2)
        self.assertEqual(dismissed_run["review_decision_summary"]["event_count"], 2)
        self.assertEqual(dismissed_run["review_decision_summary"]["resolved_item_count"], 1)
        self.assertEqual(dismissed_run["review_decision_summary"]["open_item_count"], 0)
        self.assertEqual(dismissed_run["review_decision_summary"]["decisions"]["deferred"], 1)
        self.assertEqual(dismissed_run["review_decision_summary"]["decisions"]["dismissed"], 1)
        self.assertEqual(dismissed_run["review_events"][1]["previous_decision"], "deferred")
        self.assertFalse(dismissed_run["review_events"][1]["previous_resolved"])

        published = self.client.post(
            f"/api/harmonize/upload-review-audit/runs/{run['run_id']}/publish"
        )
        self.assertEqual(published.status_code, 201)
        active = published.json()["active_snapshot"]
        self.assertEqual(active["review_decision_summary"]["event_count"], 2)
        self.assertEqual(active["review_decision_summary"]["decisions"]["dismissed"], 1)

    def test_deferring_review_item_keeps_publish_blocked(self) -> None:
        self._stage_session("defer-review")
        run = self.client.post("/api/harmonize/upload-defer-review/runs").json()
        self.assertGreaterEqual(run["summary"]["review_item_count"], 1)
        item_id = run["review_items"][0]["id"]

        deferred = self.client.post(
            f"/api/harmonize/upload-defer-review/runs/{run['run_id']}/review-items/resolve",
            json={
                "item_id": item_id,
                "decision": "deferred",
                "notes": "Need a human reviewer before publishing.",
            },
        )
        self.assertEqual(deferred.status_code, 200)
        deferred_run = deferred.json()
        self.assertEqual(deferred_run["summary"]["review_item_count"], 1)
        self.assertFalse(deferred_run["summary"]["publishable"])
        self.assertFalse(deferred_run["review_items"][0]["resolved"])
        self.assertEqual(deferred_run["review_items"][0]["decision"], "deferred")
        self.assertIsNone(deferred_run["review_items"][0]["resolved_at"])

        published = self.client.post(
            f"/api/harmonize/upload-defer-review/runs/{run['run_id']}/publish"
        )
        self.assertEqual(published.status_code, 400)

    def test_keep_separate_review_item_unblocks_publish(self) -> None:
        self._stage_session("keep-separate-review")
        run = self.client.post("/api/harmonize/upload-keep-separate-review/runs").json()
        self.assertGreaterEqual(run["summary"]["review_item_count"], 1)
        item_id = run["review_items"][0]["id"]

        resolved = self.client.post(
            f"/api/harmonize/upload-keep-separate-review/runs/{run['run_id']}/review-items/resolve",
            json={
                "item_id": item_id,
                "decision": "kept_separate",
                "notes": "Keep the conflicting source-backed values separate.",
            },
        )
        self.assertEqual(resolved.status_code, 200)
        resolved_run = resolved.json()
        self.assertEqual(resolved_run["summary"]["review_item_count"], 0)
        self.assertTrue(resolved_run["summary"]["publishable"])
        self.assertTrue(resolved_run["review_items"][0]["resolved"])
        self.assertEqual(resolved_run["review_items"][0]["decision"], "kept_separate")

    def test_alternate_preference_is_persisted_on_review_item(self) -> None:
        from api.core import harmonization_runs

        sess = self._stage_session("alternate-review")
        (sess / "report.pdf").unlink()
        (sess / "labs-alt.json").write_text(
            json.dumps(
                {
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "a1c-alternate",
                                "code": {
                                    "coding": [
                                        {"system": "http://loinc.org", "code": "4548-4"}
                                    ],
                                    "text": "A1C",
                                },
                                "valueQuantity": {"value": 6.1, "unit": "%"},
                                "effectiveDateTime": "2025-11-29",
                            }
                        }
                    ],
                }
            )
        )
        run = self.client.post("/api/harmonize/upload-alternate-review/runs").json()
        self.assertGreaterEqual(run["summary"]["review_item_count"], 1)
        review_item = next(item for item in run["review_items"] if item["category"] == "fact")
        item_id = review_item["id"]

        persisted_before = harmonization_runs.get_run("upload-alternate-review", run["run_id"])
        self.assertIsNotNone(persisted_before)
        observation = next(
            obs
            for obs in persisted_before["candidate_record"]["observations"]
            if obs["merged_ref"] == review_item["merged_ref"]
        )
        latest = observation["latest"]
        alternate = next(
            source
            for source in observation["sources"]
            if not (
                source["value"] == latest["value"]
                and source["source_label"] == latest["source_label"]
                and source["effective_date"] == latest["effective_date"]
            )
        )
        selected_ref = alternate["source_observation_ref"]

        resolved = self.client.post(
            f"/api/harmonize/upload-alternate-review/runs/{run['run_id']}/review-items/resolve",
            json={
                "item_id": item_id,
                "decision": "overridden",
                "notes": "Prefer the alternate source value.",
                "selected_source_ref": selected_ref,
            },
        )
        self.assertEqual(resolved.status_code, 200)
        resolved_item = resolved.json()["review_items"][0]
        self.assertTrue(resolved_item["resolved"])
        self.assertEqual(resolved_item["decision"], "overridden")
        self.assertEqual(resolved_item["selected_source_ref"], selected_ref)

        persisted_after = harmonization_runs.get_run("upload-alternate-review", run["run_id"])
        self.assertIsNotNone(persisted_after)
        resolved_observation = next(
            obs
            for obs in persisted_after["candidate_record"]["observations"]
            if obs["merged_ref"] == review_item["merged_ref"]
        )
        self.assertEqual(resolved_observation["latest"]["value"], alternate["value"])
        self.assertEqual(resolved_observation["latest"]["unit"], alternate["unit"])
        self.assertEqual(resolved_observation["latest"]["source_label"], alternate["source_label"])
        selection = resolved_observation["canonical_selection"]
        self.assertTrue(selection["applied"])
        self.assertEqual(selection["decision"], "overridden")
        self.assertEqual(selection["selected_source_ref"], selected_ref)
        self.assertEqual(selection["selected_latest"]["value"], alternate["value"])

        provenance = self.client.get(
            f"/api/harmonize/upload-alternate-review/provenance/{review_item['merged_ref']}"
        )
        self.assertEqual(provenance.status_code, 200)
        provenance_body = provenance.json()
        self.assertEqual(
            provenance_body["canonical_selection"]["selected_source_ref"],
            selected_ref,
        )
        self.assertEqual(
            provenance_body["canonical_selection"]["selected_latest"]["value"],
            alternate["value"],
        )

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
        self.assertIsNotNone(body["active_snapshot"]["activated_at"])
        self.assertEqual(body["active_snapshot"]["change_summary"]["previous_snapshot_id"], None)

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

    def test_publish_snapshot_change_summary_and_rollback_metadata(self) -> None:
        sess = self._stage_session("compare-publish")
        (sess / "report.pdf").unlink()

        first_run = self.client.post("/api/harmonize/upload-compare-publish/runs").json()
        first_state = self.client.post(
            f"/api/harmonize/upload-compare-publish/runs/{first_run['run_id']}/publish"
        ).json()
        first_snapshot_id = first_state["active_snapshot"]["snapshot_id"]

        (sess / "renal.json").write_text(
            json.dumps(
                {
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "creatinine-compare",
                                "status": "final",
                                "code": {"coding": [{"system": "http://loinc.org", "code": "2160-0", "display": "Creatinine"}]},
                                "effectiveDateTime": "2024-03-02T10:00:00Z",
                                "valueQuantity": {"value": 1.2, "unit": "mg/dL"},
                            }
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        second_run = self.client.post("/api/harmonize/upload-compare-publish/runs").json()
        second_state = self.client.post(
            f"/api/harmonize/upload-compare-publish/runs/{second_run['run_id']}/publish"
        ).json()
        active = second_state["active_snapshot"]
        self.assertEqual(active["change_summary"]["previous_snapshot_id"], first_snapshot_id)
        self.assertGreater(active["change_summary"]["fact_delta"], 0)
        self.assertGreater(active["change_summary"]["source_delta"], 0)
        self.assertIn("candidate facts", active["change_summary"]["headline"])

        rollback = self.client.post(
            f"/api/harmonize/upload-compare-publish/published/{first_snapshot_id}/activate"
        ).json()
        self.assertEqual(rollback["active_snapshot"]["snapshot_id"], first_snapshot_id)
        self.assertEqual(
            rollback["active_snapshot"]["activated_from_snapshot_id"],
            active["snapshot_id"],
        )
        self.assertIsNotNone(rollback["active_snapshot"]["activated_at"])

    def test_published_workspace_feeds_patient_read_endpoints(self) -> None:
        sess = self._stage_session("workspace-downstream")
        (sess / "report.pdf").unlink()

        run = self.client.post("/api/harmonize/workspace-workspace-downstream/runs").json()
        from api.core import harmonization_runs

        persisted_run = harmonization_runs.latest_run("workspace-workspace-downstream") or {}
        artifacts = persisted_run["candidate_record"]["clinical_artifacts"]
        self.assertEqual(artifacts["patients"][0]["resource"]["birthDate"], "1984-03-02")
        self.assertEqual(artifacts["patients"][0]["resource"]["gender"], "female")

        state = self.client.post(
            f"/api/harmonize/workspace-workspace-downstream/runs/{run['run_id']}/publish"
        )
        self.assertEqual(state.status_code, 201)
        # Published snapshots should remain usable even when the original source
        # file is no longer available in the upload staging area.
        (sess / "labs.json").unlink()
        from api.core import harmonize_service

        harmonize_service._cached_load.cache_clear()

        overview = self.client.get("/api/patients/workspace-downstream/overview")
        self.assertEqual(overview.status_code, 200)
        body = overview.json()
        self.assertEqual(body["id"], "workspace-downstream")
        self.assertEqual(body["name"], "Workspace Downstream")
        self.assertEqual(body["birth_date"], "1984-03-02")
        self.assertEqual(body["gender"], "female")
        self.assertEqual(body["unique_loinc_count"], 1)
        self.assertGreaterEqual(body["total_resources"], 2)
        provider_names = {item["name"] for item in body["care_team"]}
        self.assertNotIn("Unknown provider", provider_names)
        self.assertTrue(any("records" in name.lower() for name in provider_names))
        self.assertTrue(
            any(item["specialty"] == "Laboratory / diagnostics" for item in body["care_team"])
        )
        site_names = {item["name"] for item in body["sites_of_service"]}
        self.assertIn("Labs", site_names)
        self.assertTrue(
            any(
                item["specialty"] == "Laboratory / diagnostics"
                for item in body["sites_of_service"]
            )
        )

        timeline = self.client.get("/api/patients/workspace-downstream/timeline")
        self.assertEqual(timeline.status_code, 200)
        timeline_body = timeline.json()
        self.assertGreaterEqual(len(timeline_body["encounters"]), 1)
        encounter_types = {enc["encounter_type"] for enc in timeline_body["encounters"]}
        self.assertIn("Diagnostic source event", encounter_types)

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

        timeline = self.client.get("/api/patients/workspace-clinical-artifacts/timeline")
        self.assertEqual(timeline.status_code, 200)
        office_visit = next(
            enc
            for enc in timeline.json()["encounters"]
            if enc["encounter_type"] == "Office visit"
        )
        self.assertEqual(office_visit["provider_org"], "Cedars-Sinai Nephrology")
        self.assertEqual(office_visit["practitioner_name"], "Dr. Riley Renal")
        self.assertEqual(office_visit["specialty"], "Nephrology")
        self.assertEqual(office_visit["source_category"], "Office / outpatient visit")
        self.assertEqual(office_visit["linked_observation_count"], 1)
        self.assertEqual(office_visit["linked_procedure_count"], 1)
        self.assertGreaterEqual(office_visit["linked_clinical_note_count"], 1)

        encounter_detail = self.client.get(
            f"/api/patients/workspace-clinical-artifacts/encounters/{office_visit['encounter_id']}"
        )
        self.assertEqual(encounter_detail.status_code, 200)
        detail = encounter_detail.json()
        self.assertEqual(detail["provider_org"], "Cedars-Sinai Nephrology")
        self.assertEqual(detail["practitioner_name"], "Dr. Riley Renal")
        self.assertEqual(detail["specialty"], "Nephrology")
        self.assertEqual(len(detail["observations"]), 1)
        self.assertEqual(detail["procedures"][0]["display"], "Renal ultrasound")
        self.assertTrue(
            any("chronic kidney disease risk discussed" in note["text"] for note in detail["clinical_notes"])
        )

        care_journey = self.client.get("/api/patients/workspace-clinical-artifacts/care-journey")
        self.assertEqual(care_journey.status_code, 200)
        diagnostic_reports = care_journey.json()["diagnostic_reports"]
        self.assertEqual(len(diagnostic_reports), 1)
        self.assertTrue(diagnostic_reports[0]["has_presented_form"])
        self.assertIn("chronic kidney disease risk discussed", diagnostic_reports[0]["note_preview"])
        self.assertGreaterEqual(len(care_journey.json()["clinical_notes"]), 2)

        clinical_notes = self.client.get("/api/patients/workspace-clinical-artifacts/clinical-notes")
        self.assertEqual(clinical_notes.status_code, 200)
        notes_body = clinical_notes.json()
        self.assertGreaterEqual(notes_body["total_count"], 2)
        self.assertTrue(
            any(note["linked_encounter_id"] == office_visit["encounter_id"] for note in notes_body["notes"])
        )
        self.assertTrue(
            any("chronic kidney disease risk discussed" in note["text"] for note in notes_body["notes"])
        )

        raw_fhir = self.client.get("/api/patients/workspace-clinical-artifacts/fhir")
        self.assertEqual(raw_fhir.status_code, 200)
        resource_types = {entry["resource"]["resourceType"] for entry in raw_fhir.json()["entry"]}
        self.assertIn("Procedure", resource_types)
        self.assertIn("DiagnosticReport", resource_types)

        contributions = self.client.get(
            "/api/harmonize/workspace-workspace-clinical-artifacts/"
            "contributions/DocumentReference/upload-clinical"
        )
        self.assertEqual(contributions.status_code, 200)
        contribution_body = contributions.json()
        self.assertGreaterEqual(contribution_body["totals"]["clinical_notes"], 2)
        self.assertEqual(contribution_body["totals"]["encounters"], 1)
        self.assertEqual(contribution_body["totals"]["procedures"], 1)
        self.assertEqual(contribution_body["totals"]["diagnostic_reports"], 1)
        self.assertTrue(contribution_body["clinical_notes"][0]["text"])
        self.assertTrue(
            any(note.get("encounter_id") == "enc-1" for note in contribution_body["clinical_notes"])
        )
        self.assertEqual(contribution_body["encounters"][0]["provider"], "Dr. Riley Renal")
        self.assertEqual(contribution_body["encounters"][0]["site"], "Cedars-Sinai Nephrology")
        self.assertEqual(contribution_body["procedures"][0]["display"], "Renal ultrasound")
        self.assertEqual(contribution_body["diagnostic_reports"][0]["display"], "Renal function panel")
        self.assertIn(
            "chronic kidney disease risk discussed",
            contribution_body["diagnostic_reports"][0]["note_preview"],
        )

        from api.core.context_builder import build_clinical_context

        clinical_context = build_clinical_context("workspace-clinical-artifacts")
        prompt = clinical_context.to_prompt()
        self.assertIn("CLINICAL NOTES AND DOCUMENT CONTEXT", prompt)
        self.assertIn("chronic kidney disease risk discussed", prompt)
        self.assertIn("Encounter/enc-1", prompt)

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
        self.assertNotIn("no chart", body["answer"].lower())
        self.assertTrue(
            any("A1C" in citation["label"] or "5.2" in citation["detail"] for citation in body["citations"]),
            body["citations"],
        )

    def test_published_workspace_numeric_string_observations_remain_labs(self) -> None:
        from api.core.loader import _record_from_published_run

        run = {
            "collection_id": "workspace-string-labs",
            "collection_name": "String Labs",
            "candidate_record": {
                "observations": [
                    {
                        "merged_ref": "obs-a1c",
                        "canonical_name": "Hemoglobin A1c",
                        "loinc_code": "4548-4",
                        "canonical_unit": "%",
                        "latest": {"value": "5.2", "unit": "%", "effective_date": "2025-11-29"},
                        "sources": [
                            {
                                "source_label": "cedars-sinai.json",
                                "source_observation_ref": "Observation/a1c",
                                "value": "5.2",
                                "unit": "%",
                                "effective_date": "2025-11-29",
                            }
                        ],
                    }
                ]
            },
        }

        record, _stats = _record_from_published_run("workspace-string-labs", run)

        self.assertEqual(len(record.observations), 1)
        self.assertEqual(record.observations[0].value_quantity, 5.2)
        self.assertEqual(record.observations[0].value_type, "quantity")

    def test_extract_endpoint_rejects_static_collection(self) -> None:
        # synthea-demo is a committed static collection; extraction must 400
        # even on fresh checkouts that do not have Blake's private demo files.
        r = self.client.post("/api/harmonize/synthea-demo/extract")
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
        self.assertGreaterEqual(len(poll["events"]), 2)
        event_types = [event["event_type"] for event in poll["events"]]
        self.assertIn("job_queued", event_types)
        self.assertIn("job_completed", event_types)
        self.assertEqual(poll["progress_mode"], "lifecycle")

    def test_extract_job_reports_file_page_checkpoint_events(self) -> None:
        self._stage_session("pdf-events")

        class FakePipeline:
            def extract(self, _pdf_path: Path) -> dict:
                return {
                    "resourceType": "Bundle",
                    "type": "document",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "pdf-a1c",
                                "code": {"text": "A1C"},
                            }
                        }
                    ],
                }

        def fake_get_pipeline(name: str):
            self.assertEqual(name, "multipass-fhir")
            return FakePipeline

        def fake_page_count(path: Path) -> int | None:
            return 3 if path.name == "report.pdf" else None

        with (
            patch("lib.extract.pipelines.get", side_effect=fake_get_pipeline),
            patch("api.core.harmonize_service._pdf_page_count", side_effect=fake_page_count),
        ):
            r = self.client.post("/api/harmonize/upload-pdf-events/extract")
            self.assertEqual(r.status_code, 202)
            job_id = r.json()["job_id"]

            import time
            deadline = time.time() + 10
            while time.time() < deadline:
                poll = self.client.get(f"/api/harmonize/extract-jobs/{job_id}").json()
                if poll["status"] in ("complete", "failed"):
                    break
                time.sleep(0.05)

        self.assertEqual(poll["status"], "complete")
        self.assertEqual(poll["total_pages"], 3)
        self.assertEqual(poll["processed_pages"], 3)
        self.assertEqual(poll["progress_mode"], "reported")
        event_types = [event["event_type"] for event in poll["events"]]
        self.assertIn("file_queued", event_types)
        self.assertIn("file_started", event_types)
        self.assertIn("file_completed", event_types)
        completed_event = next(event for event in poll["events"] if event["event_type"] == "file_completed")
        self.assertEqual(completed_event["page_start"], 1)
        self.assertEqual(completed_event["page_end"], 3)
        self.assertEqual(completed_event["progress_basis"], "reported")

    def test_extract_job_unknown_id_404s(self) -> None:
        r = self.client.get("/api/harmonize/extract-jobs/does-not-exist")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
