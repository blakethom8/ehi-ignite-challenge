"""Tests for /api/harmonize endpoints.

The blake-real tests rely on demo collection source files living in the
corpus drop; they skip gracefully when the source files aren't available
so the suite still passes on a fresh checkout without the private data.

The upload-derived collection tests use a tempdir override so they run
on any checkout without external state.
"""

from __future__ import annotations

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

        self._old_root = harmonize_service.UPLOADS_ROOT
        harmonize_service.UPLOADS_ROOT = self._tmp
        # Bust caches so discovery reads from the new root.
        harmonize_service._cached_load.cache_clear()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        from api.core import harmonize_service

        harmonize_service.UPLOADS_ROOT = self._old_root
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

    def test_extract_endpoint_rejects_static_collection(self) -> None:
        # blake-real is static; extraction must 400
        r = self.client.post("/api/harmonize/blake-real/extract")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
