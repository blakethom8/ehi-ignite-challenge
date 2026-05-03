"""Unit tests for api.core.sof_tools.

These tests build a fresh SQLite database in a tmpdir using the SQL-on-FHIR
v2 prototype (``materialize_all``) over a couple of hand-rolled FHIR
resources. That keeps the test fast (< 200 ms) and lets us exercise the
read-only gate + run_sql happy path without depending on Synthea bundles.
"""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VIEWS_DIR = REPO_ROOT / "lib" / "sql_on_fhir" / "views"

from api.core import sof_tools
from api.core.sof_tools import (
    MAX_ROWS,
    build_tool_description,
    get_schemas_for_prompt,
    is_safe_sql,
    run_sql,
    tool_result_payload,
)


def _load_sample_views() -> list:
    from lib.sql_on_fhir.view_definition import ViewDefinition

    return [
        ViewDefinition.from_json_file(p)
        for p in sorted(VIEWS_DIR.glob("*.json"))
    ]


def _sample_resources() -> list[dict]:
    return [
        {
            "resourceType": "Patient",
            "id": "pt-1",
            "gender": "male",
            "birthDate": "1970-05-01",
            "name": [{"family": "Gibber", "given": ["Max"]}],
        },
        {
            "resourceType": "Patient",
            "id": "pt-2",
            "gender": "female",
            "birthDate": "1982-11-03",
            "name": [{"family": "Smith", "given": ["Alex"]}],
        },
        {
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
        },
        {
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
        },
    ]


def _build_db(path: Path) -> None:
    from lib.sql_on_fhir.sqlite_sink import materialize_all, open_db  # type: ignore

    views = _load_sample_views()
    conn = open_db(path)
    try:
        materialize_all(views, _sample_resources(), conn)
    finally:
        conn.close()


class TestIsSafeSql(unittest.TestCase):
    def test_select_allowed(self) -> None:
        ok, _ = is_safe_sql("SELECT * FROM patient")
        self.assertTrue(ok)

    def test_cte_allowed(self) -> None:
        ok, _ = is_safe_sql("WITH x AS (SELECT id FROM patient) SELECT * FROM x")
        self.assertTrue(ok)

    def test_drop_rejected(self) -> None:
        ok, reason = is_safe_sql("DROP TABLE patient")
        self.assertFalse(ok)
        self.assertIn("DROP", reason)

    def test_insert_rejected(self) -> None:
        ok, _ = is_safe_sql("INSERT INTO patient VALUES (1)")
        self.assertFalse(ok)

    def test_update_rejected(self) -> None:
        ok, _ = is_safe_sql("UPDATE patient SET gender='x'")
        self.assertFalse(ok)

    def test_delete_rejected(self) -> None:
        ok, _ = is_safe_sql("DELETE FROM patient")
        self.assertFalse(ok)

    def test_multi_statement_rejected(self) -> None:
        ok, reason = is_safe_sql("SELECT 1; SELECT 2")
        self.assertFalse(ok)
        self.assertIn("multi-statement", reason)

    def test_drop_in_string_literal_allowed(self) -> None:
        # 'Drop' inside a quoted literal should not trip the gate.
        ok, _ = is_safe_sql("SELECT * FROM patient WHERE gender = 'drop'")
        self.assertTrue(ok)

    def test_trailing_semicolon_allowed(self) -> None:
        ok, _ = is_safe_sql("SELECT 1;")
        self.assertTrue(ok)

    def test_empty_rejected(self) -> None:
        ok, _ = is_safe_sql("")
        self.assertFalse(ok)

    def test_pragma_rejected(self) -> None:
        ok, _ = is_safe_sql("PRAGMA table_info(patient)")
        self.assertFalse(ok)


class TestRunSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = Path(__file__).resolve().parent / "_tmp_sof"
        cls.tmpdir.mkdir(exist_ok=True)
        cls.db_path = cls.tmpdir / "test_sof.db"
        if cls.db_path.exists():
            cls.db_path.unlink()
        _build_db(cls.db_path)

    @classmethod
    def tearDownClass(cls) -> None:
        for p in cls.tmpdir.glob("*"):
            p.unlink()
        cls.tmpdir.rmdir()

    def test_select_patient_rows(self) -> None:
        result = run_sql("SELECT id, gender FROM patient ORDER BY id", db_path=self.db_path)
        self.assertIsNone(result.error)
        self.assertEqual(result.columns, ["id", "gender"])
        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.rows[0][0], "pt-1")

    def test_join_condition_to_patient(self) -> None:
        query = (
            "SELECT p.id, c.code_display "
            "FROM patient p JOIN condition c "
            "ON c.patient_ref = 'urn:uuid:' || p.id"
        )
        result = run_sql(query, db_path=self.db_path)
        self.assertIsNone(result.error)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0][1], "Atrial fibrillation")

    def test_limit_is_applied_when_absent(self) -> None:
        # With 2 patients and limit=1, we inject LIMIT 2 (limit+1 probe) and
        # slice to 1 row, marking the result truncated.
        result = run_sql("SELECT * FROM patient", limit=1, db_path=self.db_path)
        self.assertIsNone(result.error)
        self.assertEqual(result.row_count, 1)
        self.assertTrue(result.truncated)
        self.assertIn("LIMIT 2", result.query.upper())

    def test_caller_limit_preserved(self) -> None:
        result = run_sql("SELECT * FROM patient LIMIT 2", db_path=self.db_path)
        self.assertIsNone(result.error)
        # Ensure we didn't tack on a second LIMIT clause
        self.assertEqual(result.query.upper().count("LIMIT"), 1)

    def test_max_rows_cap(self) -> None:
        # Request more than MAX_ROWS → injected LIMIT uses the cap (+1 probe row).
        result = run_sql("SELECT * FROM patient", limit=MAX_ROWS + 10_000, db_path=self.db_path)
        self.assertIsNone(result.error)
        self.assertIn(f"LIMIT {MAX_ROWS + 1}", result.query)
        self.assertLessEqual(result.row_count, MAX_ROWS)

    def test_drop_rejected_without_touching_db(self) -> None:
        result = run_sql("DROP TABLE patient", db_path=self.db_path)
        self.assertIsNotNone(result.error)
        self.assertIn("rejected", result.error or "")
        # DB should still be usable
        again = run_sql("SELECT COUNT(*) FROM patient", db_path=self.db_path)
        self.assertIsNone(again.error)
        self.assertEqual(again.rows[0][0], 2)

    def test_missing_db_returns_error(self) -> None:
        result = run_sql("SELECT 1", db_path=self.tmpdir / "nope.db")
        self.assertIsNotNone(result.error)
        self.assertIn("not found", result.error or "")

    def test_sqlite_error_propagated(self) -> None:
        result = run_sql("SELECT * FROM nonexistent_table", db_path=self.db_path)
        self.assertIsNotNone(result.error)
        self.assertIn("sqlite error", result.error or "")

    def test_tool_result_payload_shape(self) -> None:
        result = run_sql("SELECT id FROM patient LIMIT 1", db_path=self.db_path)
        payload = tool_result_payload(result)
        self.assertIn("content", payload)
        self.assertEqual(payload["content"][0]["type"], "text")
        self.assertFalse(payload["is_error"])


class TestSchemas(unittest.TestCase):
    def test_schemas_cover_all_five_views(self) -> None:
        schema = get_schemas_for_prompt()
        for table in ("patient", "condition", "medication_request", "observation", "encounter"):
            self.assertIn(f"CREATE TABLE {table}", schema)

    def test_tool_description_embeds_schemas(self) -> None:
        desc = build_tool_description()
        self.assertIn("SELECT", desc)
        self.assertIn("CREATE TABLE patient", desc)
        self.assertIn("urn:uuid:", desc)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
