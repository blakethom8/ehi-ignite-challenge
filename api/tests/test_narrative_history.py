"""Narrative history — endpoint + bundle inclusion."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from api.core import narrative_history as narrative_history_module
from api.main import app
from lib.narratives import storage as narrative_storage


def _composition(comp_id: str, generated_at: datetime, replaces: str | None = None) -> dict:
    payload: dict = {
        "resourceType": "Composition",
        "id": comp_id,
        "status": "final",
        "type": {"text": "Episode narrative"},
        "date": generated_at.isoformat(),
        "subject": {"reference": "Patient/p1"},
        "extension": [
            {
                "url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/episode-ref",
                "valueReference": {"reference": "EpisodeOfCare/episode-cardiometabolic"},
            }
        ],
        "section": [],
    }
    if replaces:
        payload["relatesTo"] = [
            {"code": "replaces", "targetReference": {"reference": f"Composition/{replaces}"}}
        ]
    return payload


class NarrativeHistoryEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="nh-test-"))
        self._old_root = narrative_storage.NARRATIVE_STORE_ROOT
        narrative_storage.NARRATIVE_STORE_ROOT = self._tmp / "narratives"
        self.client = TestClient(app)
        # Authenticate so the new endpoints (require_access_session) pass.
        login = self.client.post(
            "/api/auth/login",
            json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
        )
        assert login.status_code == 200, login.text

    def tearDown(self) -> None:
        narrative_storage.NARRATIVE_STORE_ROOT = self._old_root
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_three_versions(self) -> list[str]:
        """Write three narratives, returns their composition ids oldest-first."""
        base = datetime(2026, 5, 1, tzinfo=UTC)
        ids: list[str] = []
        prev: str | None = None
        for i in range(3):
            generated = base + timedelta(days=i)
            comp_id = f"narrative-cardiometabolic-v{i+1}"
            payload = _composition(comp_id, generated, replaces=prev)
            narrative_storage.write_current_narrative("p1", payload)
            ids.append(comp_id)
            prev = comp_id
        return ids

    def test_list_history_returns_archived_versions_newest_first(self) -> None:
        ids = self._write_three_versions()
        # The current is v3; archived prior are v2 and v1.
        response = self.client.get(
            "/api/patient-context/p1/narratives/cardiometabolic/history"
        )
        self.assertEqual(response.status_code, 200, response.text)
        versions = response.json()["versions"]
        # Two archived (v1 and v2), newest-first means v2 then v1.
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["composition_id"], ids[1])
        self.assertEqual(versions[1]["composition_id"], ids[0])
        # v2 should record that it replaces v1.
        self.assertEqual(versions[0]["replaces_id"], ids[0])

    def test_load_archived_returns_the_full_composition(self) -> None:
        self._write_three_versions()
        listing = self.client.get(
            "/api/patient-context/p1/narratives/cardiometabolic/history"
        ).json()
        timestamp = listing["versions"][0]["timestamp"]
        response = self.client.get(
            f"/api/patient-context/p1/narratives/cardiometabolic/history/{timestamp}"
        )
        self.assertEqual(response.status_code, 200, response.text)
        archived = response.json()
        self.assertEqual(archived["resourceType"], "Composition")
        self.assertEqual(archived.get("status"), "superseded")

    def test_unknown_timestamp_404s(self) -> None:
        self._write_three_versions()
        response = self.client.get(
            "/api/patient-context/p1/narratives/cardiometabolic/history/no-such-version"
        )
        self.assertEqual(response.status_code, 404)


class NarrativeHistoryModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="nh-mod-test-"))
        self._old_root = narrative_storage.NARRATIVE_STORE_ROOT
        narrative_storage.NARRATIVE_STORE_ROOT = self._tmp / "narratives"

    def tearDown(self) -> None:
        narrative_storage.NARRATIVE_STORE_ROOT = self._old_root
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_load_history_compositions_oldest_first(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        prev: str | None = None
        ids: list[str] = []
        for i in range(3):
            comp_id = f"narrative-cardiometabolic-v{i+1}"
            narrative_storage.write_current_narrative(
                "patient-x", _composition(comp_id, base + timedelta(days=i), replaces=prev)
            )
            ids.append(comp_id)
            prev = comp_id

        compositions = narrative_history_module.load_history_compositions(
            "patient-x", "cardiometabolic"
        )
        # v1 and v2 are archived; v3 is current. Helper returns oldest-first.
        self.assertEqual(len(compositions), 2)
        self.assertEqual(compositions[0]["composition"]["id"], ids[0])
        self.assertEqual(compositions[1]["composition"]["id"], ids[1])


if __name__ == "__main__":
    unittest.main()
