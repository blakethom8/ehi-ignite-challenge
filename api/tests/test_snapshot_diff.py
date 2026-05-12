"""Snapshot diff endpoint + helpers."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.core import published_charts
from api.main import app


def _authenticated_client() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
    )
    assert response.status_code == 200, response.text
    return client


def _candidate_record(observations: list[dict]) -> dict:
    return {
        "observations": observations,
        "conditions": [],
        "medications": [],
        "allergies": [],
        "immunizations": [],
    }


def _observation(merged_ref: str, name: str, value: float, unit: str = "mg/dL") -> dict:
    return {
        "merged_ref": merged_ref,
        "canonical_name": name,
        "latest": {"value": value, "unit": unit},
    }


class SnapshotDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="snapshot-diff-test-"))
        self._old_published_root = published_charts.PUBLISHED_ROOT
        published_charts.PUBLISHED_ROOT = self._tmp / "published"
        self._collection = "diff-test-collection"

        # Build two synthetic run JSONs.
        runs_dir = self._tmp / "runs" / self._collection
        runs_dir.mkdir(parents=True, exist_ok=True)
        self._run_a = "run-a"
        self._run_b = "run-b"
        (runs_dir / f"{self._run_a}.json").write_text(
            json.dumps(
                {
                    "run_id": self._run_a,
                    "candidate_record": _candidate_record(
                        [
                            _observation("Observation/lipid-1", "HDL Cholesterol", 56),
                            _observation("Observation/a1c-1", "Hemoglobin A1c", 6.2, "%"),
                        ]
                    ),
                    "summary": {
                        "total_candidate_facts": 2,
                        "source_count": 1,
                        "review_item_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        (runs_dir / f"{self._run_b}.json").write_text(
            json.dumps(
                {
                    "run_id": self._run_b,
                    "candidate_record": _candidate_record(
                        [
                            _observation("Observation/lipid-1", "HDL Cholesterol", 60),
                            _observation("Observation/creatinine-1", "Creatinine", 1.1),
                        ]
                    ),
                    "summary": {
                        "total_candidate_facts": 2,
                        "source_count": 1,
                        "review_item_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )

        # Patch harmonization_runs.get_run to read from our tmp dir.
        from api.core import harmonization_runs

        self._old_get_run = harmonization_runs.get_run

        def fake_get_run(coll_id: str, run_id: str):
            path = self._tmp / "runs" / coll_id / f"{run_id}.json"
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))

        harmonization_runs.get_run = fake_get_run  # type: ignore[assignment]
        self._harmonization_runs = harmonization_runs

        # Seed two snapshots into the published state for the collection.
        state_path = published_charts._state_path(self._collection)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "collection_id": self._collection,
                    "active_snapshot_id": "snap-b",
                    "snapshots": [
                        {
                            "snapshot_id": "snap-a",
                            "run_id": self._run_a,
                            "published_at": "2026-05-01T12:00:00Z",
                            "summary": {"total_candidate_facts": 2, "source_count": 1, "review_item_count": 0},
                            "change_summary": {"previous_snapshot_id": None, "headline": "Initial."},
                            "review_decision_summary": {
                                "event_count": 0,
                                "resolved_item_count": 0,
                                "open_item_count": 0,
                                "latest_event_at": None,
                                "decisions": {},
                            },
                            "candidate_fact_count": 2,
                            "source_count": 1,
                            "rule_version": "v1",
                        },
                        {
                            "snapshot_id": "snap-b",
                            "run_id": self._run_b,
                            "published_at": "2026-05-02T12:00:00Z",
                            "summary": {"total_candidate_facts": 2, "source_count": 1, "review_item_count": 0},
                            "change_summary": {"previous_snapshot_id": "snap-a", "headline": "Updated."},
                            "review_decision_summary": {
                                "event_count": 0,
                                "resolved_item_count": 0,
                                "open_item_count": 0,
                                "latest_event_at": None,
                                "decisions": {},
                            },
                            "candidate_fact_count": 2,
                            "source_count": 1,
                            "rule_version": "v1",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._harmonization_runs.get_run = self._old_get_run  # type: ignore[assignment]
        published_charts.PUBLISHED_ROOT = self._old_published_root
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_compute_diff_classifies_added_removed_changed(self) -> None:
        diff = published_charts.compute_snapshot_diff(self._collection, "snap-a", "snap-b")
        obs = diff["categories"]["observations"]
        added_refs = {entry["merged_ref"] for entry in obs["added"]}
        removed_refs = {entry["merged_ref"] for entry in obs["removed"]}
        changed_refs = {entry["merged_ref"] for entry in obs["changed"]}
        self.assertEqual(added_refs, {"Observation/creatinine-1"})
        self.assertEqual(removed_refs, {"Observation/a1c-1"})
        self.assertEqual(changed_refs, {"Observation/lipid-1"})

        changed = obs["changed"][0]
        self.assertEqual(changed["before"], "56 mg/dL")
        self.assertEqual(changed["after"], "60 mg/dL")

        self.assertEqual(diff["totals"], {"added": 1, "removed": 1, "changed": 1})

    def test_previous_snapshot_id_returns_chronological_predecessor(self) -> None:
        prev = published_charts.previous_snapshot_id(self._collection, "snap-b")
        self.assertEqual(prev, "snap-a")
        first = published_charts.previous_snapshot_id(self._collection, "snap-a")
        self.assertIsNone(first)

    def test_endpoint_uses_previous_snapshot_when_against_omitted(self) -> None:
        client = _authenticated_client()
        # Patch harmonize_service.get_collection so the test collection is recognized.
        from api.core import harmonize_service

        with patch.object(
            harmonize_service,
            "get_collection",
            lambda cid: object() if cid == self._collection else None,
        ):
            response = client.get(
                f"/api/harmonize/{self._collection}/snapshots/snap-b/diff"
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["snapshot_a"]["snapshot_id"], "snap-a")
            self.assertEqual(body["snapshot_b"]["snapshot_id"], "snap-b")

    def test_endpoint_404s_for_earliest_snapshot(self) -> None:
        client = _authenticated_client()
        from api.core import harmonize_service

        with patch.object(
            harmonize_service,
            "get_collection",
            lambda cid: object() if cid == self._collection else None,
        ):
            response = client.get(
                f"/api/harmonize/{self._collection}/snapshots/snap-a/diff"
            )
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
