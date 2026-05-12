"""Bundle enrichment coverage — drug classes, packets, terminology, derived."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.core import guest_harmonization
from api.main import app


def _zip_root(payload: bytes) -> tuple[zipfile.ZipFile, str]:
    zf = zipfile.ZipFile(io.BytesIO(payload))
    roots = {name.split("/", 1)[0] for name in zf.namelist() if "/" in name}
    assert len(roots) == 1, f"expected single zip root, got {roots}"
    return zf, roots.pop()


def _authenticated_client() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
    )
    assert response.status_code == 200, response.text
    return client


class AuthEnrichmentTests(unittest.TestCase):
    """Authenticated synthea export ships the new enrichments."""

    def test_export_includes_enrichments_and_four_packets(self) -> None:
        client = _authenticated_client()
        response = client.get("/api/harmonize/synthea-demo/export-workspace")
        self.assertEqual(response.status_code, 200, response.text)

        zf, root = _zip_root(response.content)
        with zf:
            names = set(zf.namelist())
            for required in [
                f"{root}/evidence/drug-classes.json",
                f"{root}/evidence/medication-episodes.json",
                f"{root}/evidence/observations-latest.json",
                f"{root}/packets/second-opinion.context.json",
                f"{root}/packets/patient-summary.context.json",
                f"{root}/packets/clinician-handoff.context.json",
                f"{root}/packets/preop-review.context.json",
            ]:
                self.assertIn(required, names, f"missing {required}")

            preop = json.loads(zf.read(f"{root}/packets/preop-review.context.json"))
            self.assertEqual(preop["packet_version"], "atlas-context.v1")
            self.assertEqual(preop["purpose"], "preop-review")
            self.assertIn("medication_episodes", preop)
            self.assertIn("active_medication_count", preop["summary"])

            episodes = json.loads(zf.read(f"{root}/evidence/medication-episodes.json"))
            self.assertIn("medication_episodes", episodes)

            observations_latest = json.loads(zf.read(f"{root}/evidence/observations-latest.json"))
            self.assertIn("observations_latest", observations_latest)

            # If any LOINC codes were used, the slice should be present.
            facts = json.loads(zf.read(f"{root}/evidence/canonical-facts.json"))["facts"]
            loinc_codes = {str(f.get("code")) for f in facts if f.get("resource_type") == "Observation" and f.get("code")}
            if loinc_codes:
                self.assertIn(f"{root}/terminology/loinc-used.json", names)
                slice_payload = json.loads(zf.read(f"{root}/terminology/loinc-used.json"))
                self.assertEqual(slice_payload["system"], "http://loinc.org")

            # Manifest must list every file we wrote.
            manifest = json.loads(zf.read(f"{root}/MANIFEST.json"))
            manifest_paths = {entry["path"] for entry in manifest["files"] if isinstance(entry, dict)}
            for required in [
                "evidence/drug-classes.json",
                "evidence/medication-episodes.json",
                "evidence/observations-latest.json",
                "packets/patient-summary.context.json",
                "packets/clinician-handoff.context.json",
                "packets/preop-review.context.json",
            ]:
                self.assertIn(required, manifest_paths)


class GuestEnrichmentTests(unittest.TestCase):
    """Guest export ships the same enrichments via the same packager."""

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="guest-enrich-test-"))
        self._old_root = guest_harmonization.GUEST_ROOT
        self._old_secret_path = guest_harmonization.GUEST_SECRET_PATH
        guest_harmonization.GUEST_ROOT = self._tmp / "runs"
        guest_harmonization.GUEST_SECRET_PATH = self._tmp / "guest.key"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        guest_harmonization.GUEST_ROOT = self._old_root
        guest_harmonization.GUEST_SECRET_PATH = self._old_secret_path
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _run_with_anticoagulant_bundle(self) -> str:
        run = self.client.post("/api/guest-harmonization/runs")
        run_id = run.json()["run_id"]
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "p1", "name": [{"given": ["E"], "family": "T"}]}},
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": "warfarin-1",
                        "status": "active",
                        "intent": "order",
                        "medicationCodeableConcept": {"text": "Warfarin 5 MG"},
                        "authoredOn": "2025-08-01",
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "hba1c-1",
                        "code": {
                            "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}],
                            "text": "A1C",
                        },
                        "valueQuantity": {"value": 6.4, "unit": "%"},
                        "effectiveDateTime": "2025-09-12",
                        "status": "final",
                    }
                },
            ],
        }
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("bundle.json", json.dumps(bundle), "application/json")},
        )
        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        return run_id

    def test_guest_export_includes_enrichments_and_drug_class(self) -> None:
        run_id = self._run_with_anticoagulant_bundle()
        response = self.client.get(f"/api/guest-harmonization/runs/{run_id}/export-workspace")
        self.assertEqual(response.status_code, 200, response.text)

        zf, root = _zip_root(response.content)
        with zf:
            names = set(zf.namelist())
            for required in [
                f"{root}/evidence/drug-classes.json",
                f"{root}/evidence/medication-episodes.json",
                f"{root}/evidence/observations-latest.json",
                f"{root}/packets/patient-summary.context.json",
                f"{root}/packets/preop-review.context.json",
            ]:
                self.assertIn(required, names, f"missing {required}")

            drug_classes = json.loads(zf.read(f"{root}/evidence/drug-classes.json"))["drug_classes"]
            # Warfarin should classify as anticoagulant (severity: critical).
            self.assertTrue(any(entry.get("severity_max") == "critical" for entry in drug_classes.values()))

            episodes = json.loads(zf.read(f"{root}/evidence/medication-episodes.json"))["medication_episodes"]
            self.assertEqual(len(episodes), 1)
            self.assertTrue(episodes[0]["is_active"])
            self.assertEqual(episodes[0]["drug_class"], "anticoagulants")

            preop = json.loads(zf.read(f"{root}/packets/preop-review.context.json"))
            self.assertGreaterEqual(preop["summary"]["active_medication_count"], 1)

            obs_latest = json.loads(zf.read(f"{root}/evidence/observations-latest.json"))["observations_latest"]
            self.assertTrue(any(r.get("loinc_code") == "4548-4" for r in obs_latest))

            self.assertIn(f"{root}/terminology/loinc-used.json", names)
            loinc_slice = json.loads(zf.read(f"{root}/terminology/loinc-used.json"))
            self.assertEqual(loinc_slice["system"], "http://loinc.org")


if __name__ == "__main__":
    unittest.main()
