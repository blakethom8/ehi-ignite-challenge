"""Tests for api.core.sof_materialize.

These tests never touch the real ``data/sof.db``. We point every call at
an isolated tmpdir that contains:
  * a fake FHIR-bundle directory (one bundle with 2 patients + a couple
    of linked condition/medication resources)
  * a tmp DB path
The real ViewDefinitions under ``patient-journey/core/sql_on_fhir/views``
are reused — we're testing the materialize pipeline, not the views.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import unittest
from pathlib import Path

from api.core import sof_materialize
from api.core.sof_materialize import (
    MaterializeReport,
    materialize_from_env,
    materialize_if_stale,
)


def _mini_bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "pt-1",
                    "gender": "male",
                    "birthDate": "1970-05-01",
                    "name": [{"family": "Gibber", "given": ["Max"]}],
                }
            },
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "pt-2",
                    "gender": "female",
                    "birthDate": "1985-02-12",
                    "name": [{"family": "Smith", "given": ["Alex"]}],
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "c-1",
                    "subject": {"reference": "urn:uuid:pt-1"},
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "code": {
                        "text": "Atrial fibrillation",
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "49436004",
                                "display": "Atrial fibrillation",
                            }
                        ],
                    },
                    "onsetDateTime": "2020-03-10",
                }
            },
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": "m-1",
                    "subject": {"reference": "urn:uuid:pt-1"},
                    "status": "active",
                    "intent": "order",
                    "authoredOn": "2022-01-05",
                    "medicationCodeableConcept": {
                        "text": "warfarin 5 mg",
                        "coding": [
                            {
                                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                "code": "855332",
                                "display": "warfarin sodium 5 MG Oral Tablet",
                            }
                        ],
                    },
                }
            },
        ],
    }


class TestMaterializeIfStale(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = Path(__file__).resolve().parent / "_tmp_sof_mat"
        if cls.tmpdir.exists():
            shutil.rmtree(cls.tmpdir)
        cls.tmpdir.mkdir()
        cls.fhir_dir = cls.tmpdir / "fhir"
        cls.fhir_dir.mkdir()
        bundle_path = cls.fhir_dir / "patient_bundle.json"
        bundle_path.write_text(json.dumps(_mini_bundle()))
        cls.db_path = cls.tmpdir / "sof.db"

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _reset_db(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        tmp = self.db_path.with_suffix(self.db_path.suffix + ".tmp")
        if tmp.exists():
            tmp.unlink()

    def test_builds_when_missing(self) -> None:
        self._reset_db()
        report = materialize_if_stale(
            db_path=self.db_path, fhir_dir=self.fhir_dir, patient_limit=10
        )
        self.assertTrue(report.built)
        self.assertTrue(self.db_path.exists())
        self.assertGreater(report.row_counts.get("patient", 0), 0)
        self.assertGreater(report.row_counts.get("condition", 0), 0)
        self.assertGreater(report.row_counts.get("medication_request", 0), 0)
        self.assertEqual(report.reason, "db does not exist")

    def test_idempotent_second_call(self) -> None:
        self._reset_db()
        materialize_if_stale(
            db_path=self.db_path, fhir_dir=self.fhir_dir, patient_limit=10
        )
        first_mtime = self.db_path.stat().st_mtime

        # Pause so the mtime resolution on any sane filesystem would bump
        # if we actually wrote to the file.
        time.sleep(0.05)
        report = materialize_if_stale(
            db_path=self.db_path, fhir_dir=self.fhir_dir, patient_limit=10
        )
        self.assertFalse(report.built)
        self.assertEqual(report.reason, "db is fresh")
        self.assertEqual(self.db_path.stat().st_mtime, first_mtime)

    def test_rebuild_when_fhir_dir_touched(self) -> None:
        self._reset_db()
        materialize_if_stale(
            db_path=self.db_path, fhir_dir=self.fhir_dir, patient_limit=10
        )
        old_mtime = self.db_path.stat().st_mtime

        # Bump the fhir dir mtime forward so it appears newer than the db.
        future = old_mtime + 10
        os.utime(self.fhir_dir, (future, future))
        report = materialize_if_stale(
            db_path=self.db_path, fhir_dir=self.fhir_dir, patient_limit=10
        )
        self.assertTrue(report.built)
        self.assertEqual(report.reason, "fhir dir newer than db")

    def test_db_has_expected_tables(self) -> None:
        self._reset_db()
        materialize_if_stale(
            db_path=self.db_path, fhir_dir=self.fhir_dir, patient_limit=10
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        for expected in (
            "patient",
            "condition",
            "medication_request",
            "observation",
            "encounter",
        ):
            self.assertIn(expected, tables)

    def test_missing_fhir_dir_raises(self) -> None:
        self._reset_db()
        bogus = self.tmpdir / "nope"
        with self.assertRaises(FileNotFoundError):
            materialize_if_stale(
                db_path=self.db_path, fhir_dir=bogus, patient_limit=5
            )


class TestMaterializeFromEnv(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = Path(__file__).resolve().parent / "_tmp_sof_env"
        if cls.tmpdir.exists():
            shutil.rmtree(cls.tmpdir)
        cls.tmpdir.mkdir()
        cls.fhir_dir = cls.tmpdir / "fhir"
        cls.fhir_dir.mkdir()
        (cls.fhir_dir / "bundle.json").write_text(json.dumps(_mini_bundle()))
        cls.db_path = cls.tmpdir / "sof.db"

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self) -> None:
        self._saved = {
            k: os.environ.get(k)
            for k in (
                "SOF_AUTO_MATERIALIZE",
                "SOF_DB_PATH",
                "SOF_FHIR_DIR",
                "SOF_PATIENT_LIMIT",
            )
        }

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_auto_materialize_disabled_returns_none(self) -> None:
        os.environ["SOF_AUTO_MATERIALIZE"] = "0"
        os.environ["SOF_DB_PATH"] = str(self.db_path)
        os.environ["SOF_FHIR_DIR"] = str(self.fhir_dir)
        self.assertIsNone(materialize_from_env())
        self.assertFalse(self.db_path.exists())

    def test_env_driven_build(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        os.environ["SOF_AUTO_MATERIALIZE"] = "1"
        os.environ["SOF_DB_PATH"] = str(self.db_path)
        os.environ["SOF_FHIR_DIR"] = str(self.fhir_dir)
        os.environ["SOF_PATIENT_LIMIT"] = "5"
        report = materialize_from_env()
        self.assertIsInstance(report, MaterializeReport)
        assert report is not None  # for type-checker
        self.assertTrue(report.built)
        self.assertTrue(self.db_path.exists())
        self.assertEqual(report.patient_limit, 5)

    def test_env_swallows_errors(self) -> None:
        # Force a stale check by pointing at a brand-new DB path.
        broken_db = self.tmpdir / "broken.db"
        if broken_db.exists():
            broken_db.unlink()
        os.environ["SOF_AUTO_MATERIALIZE"] = "1"
        os.environ["SOF_DB_PATH"] = str(broken_db)
        os.environ["SOF_FHIR_DIR"] = str(self.tmpdir / "does-not-exist")
        self.assertIsNone(materialize_from_env())
        self.assertFalse(broken_db.exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
