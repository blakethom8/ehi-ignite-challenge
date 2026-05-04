"""Tests for /api/harmonize endpoints.

The tests rely on the demo collection ``blake-real`` whose source files
live in the corpus drop. They're skipped when the source files aren't
available so the suite still passes on a fresh checkout without the
private data.
"""

from __future__ import annotations

import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
