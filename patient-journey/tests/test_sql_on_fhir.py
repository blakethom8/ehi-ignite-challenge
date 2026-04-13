"""Tests for the SQL-on-FHIR prototype.

We cover three layers:
1. FHIRPath-lite — the minimal expression evaluator
2. The ViewDefinition runner — against both synthetic fixtures and the
   canonical examples from the SQL-on-FHIR v2 test suite
3. SQLite materialization — round-trip into a real in-memory database
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "core" / "sql_on_fhir"
sys.path.insert(0, str(ROOT))

from fhirpath import evaluate  # type: ignore  # noqa: E402
from runner import run_view  # type: ignore  # noqa: E402
from sqlite_sink import materialize, open_db  # type: ignore  # noqa: E402
from view_definition import ViewDefinition  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# FHIRPath-lite
# ---------------------------------------------------------------------------


class TestFHIRPath:
    def test_field_access(self):
        assert evaluate("id", {"id": "abc"}) == ["abc"]

    def test_missing_field(self):
        assert evaluate("id", {}) == []

    def test_nested_field(self):
        data = {"name": {"family": "Smith"}}
        assert evaluate("name.family", data) == ["Smith"]

    def test_collection_field(self):
        data = {"name": [{"family": "A"}, {"family": "B"}]}
        assert evaluate("name.family", data) == ["A", "B"]

    def test_first(self):
        data = {"name": [{"family": "A"}, {"family": "B"}]}
        assert evaluate("name.first().family", data) == ["A"]

    def test_exists_true(self):
        assert evaluate("active.exists()", {"active": True}) == [True]

    def test_exists_false(self):
        assert evaluate("active.exists()", {}) == [False]

    def test_equality(self):
        assert evaluate("active = true", {"active": True}) == [True]
        assert evaluate("active = true", {"active": False}) == [False]

    def test_and_or_not(self):
        data = {"a": True, "b": False}
        assert evaluate("a and b", data) == [False]
        assert evaluate("a or b", data) == [True]
        assert evaluate("not b", data) == [True]

    def test_where_filter(self):
        data = {
            "name": [
                {"use": "official", "family": "Smith"},
                {"use": "nickname", "family": "Smitty"},
            ]
        }
        result = evaluate("name.where(use = 'official').family", data)
        assert result == ["Smith"]

    def test_string_literal(self):
        assert evaluate("'hello'", {}) == ["hello"]

    def test_get_reference_key(self):
        data = {"subject": {"reference": "Patient/abc"}}
        assert evaluate("subject.getReferenceKey()", data) == ["Patient/abc"]

    def test_count(self):
        data = {"name": [{"family": "A"}, {"family": "B"}, {"family": "C"}]}
        assert evaluate("name.count()", data) == [3]


# ---------------------------------------------------------------------------
# ViewDefinition runner — synthetic resources
# ---------------------------------------------------------------------------


def _view(data: dict) -> ViewDefinition:
    return ViewDefinition.from_dict(data)


class TestRunner:
    def test_simple_columns(self):
        view = _view(
            {
                "resource": "Patient",
                "select": [
                    {
                        "column": [
                            {"name": "id", "path": "id", "type": "id"},
                            {"name": "gender", "path": "gender", "type": "code"},
                        ]
                    }
                ],
            }
        )
        patient = {"resourceType": "Patient", "id": "p1", "gender": "male"}
        rows = list(run_view(view, [patient]))
        assert rows == [{"id": "p1", "gender": "male"}]

    def test_where_clause_excludes_resource(self):
        view = _view(
            {
                "resource": "Patient",
                "select": [{"column": [{"name": "id", "path": "id", "type": "id"}]}],
                "where": [{"path": "active = true"}],
            }
        )
        inactive = {"resourceType": "Patient", "id": "p1", "active": False}
        active = {"resourceType": "Patient", "id": "p2", "active": True}
        rows = list(run_view(view, [inactive, active]))
        assert rows == [{"id": "p2"}]

    def test_resource_type_mismatch_skipped(self):
        view = _view(
            {
                "resource": "Patient",
                "select": [{"column": [{"name": "id", "path": "id", "type": "id"}]}],
            }
        )
        obs = {"resourceType": "Observation", "id": "o1"}
        assert list(run_view(view, [obs])) == []

    def test_for_each_unnests(self):
        """From the spec's foreach.json fixture."""
        view = _view(
            {
                "resource": "Patient",
                "select": [
                    {
                        "column": [{"name": "id", "path": "id", "type": "id"}],
                        "select": [
                            {
                                "forEach": "name",
                                "column": [
                                    {"name": "family", "path": "family", "type": "string"}
                                ],
                            }
                        ],
                    }
                ],
            }
        )
        patient = {
            "resourceType": "Patient",
            "id": "pt1",
            "name": [{"family": "A"}, {"family": "B"}],
        }
        rows = list(run_view(view, [patient]))
        assert rows == [{"id": "pt1", "family": "A"}, {"id": "pt1", "family": "B"}]

    def test_for_each_or_null_keeps_empty(self):
        view = _view(
            {
                "resource": "Patient",
                "select": [
                    {
                        "column": [{"name": "id", "path": "id", "type": "id"}],
                        "select": [
                            {
                                "forEachOrNull": "name",
                                "column": [
                                    {"name": "family", "path": "family", "type": "string"}
                                ],
                            }
                        ],
                    }
                ],
            }
        )
        patient = {"resourceType": "Patient", "id": "pt1"}  # no names
        rows = list(run_view(view, [patient]))
        assert rows == [{"id": "pt1", "family": None}]

    def test_for_each_skipped_on_empty(self):
        view = _view(
            {
                "resource": "Patient",
                "select": [
                    {
                        "column": [{"name": "id", "path": "id", "type": "id"}],
                        "select": [
                            {
                                "forEach": "name",
                                "column": [
                                    {"name": "family", "path": "family", "type": "string"}
                                ],
                            }
                        ],
                    }
                ],
            }
        )
        patient = {"resourceType": "Patient", "id": "pt1"}  # no names
        assert list(run_view(view, [patient])) == []

    def test_union_all(self):
        view = _view(
            {
                "resource": "Patient",
                "select": [
                    {
                        "column": [{"name": "id", "path": "id", "type": "id"}],
                        "unionAll": [
                            {
                                "forEach": "name.where(use = 'official')",
                                "column": [
                                    {"name": "label", "path": "family", "type": "string"}
                                ],
                            },
                            {
                                "forEach": "name.where(use = 'nickname')",
                                "column": [
                                    {"name": "label", "path": "family", "type": "string"}
                                ],
                            },
                        ],
                    }
                ],
            }
        )
        patient = {
            "resourceType": "Patient",
            "id": "pt1",
            "name": [
                {"use": "official", "family": "Smith"},
                {"use": "nickname", "family": "Smitty"},
            ],
        }
        rows = list(run_view(view, [patient]))
        assert rows == [{"id": "pt1", "label": "Smith"}, {"id": "pt1", "label": "Smitty"}]


# ---------------------------------------------------------------------------
# SQLite sink
# ---------------------------------------------------------------------------


class TestSqliteSink:
    def test_materialize_patient_view(self, tmp_path):
        view = _view(
            {
                "name": "patient",
                "resource": "Patient",
                "select": [
                    {
                        "column": [
                            {"name": "id", "path": "id", "type": "id"},
                            {"name": "gender", "path": "gender", "type": "code"},
                            {"name": "birth_date", "path": "birthDate", "type": "date"},
                        ]
                    }
                ],
            }
        )
        resources = [
            {"resourceType": "Patient", "id": "p1", "gender": "male", "birthDate": "1980-01-01"},
            {"resourceType": "Patient", "id": "p2", "gender": "female", "birthDate": "1990-06-15"},
        ]
        conn = sqlite3.connect(":memory:")
        n = materialize(view, resources, conn)
        assert n == 2
        rows = conn.execute("SELECT id, gender, birth_date FROM patient ORDER BY id").fetchall()
        assert rows == [("p1", "male", "1980-01-01"), ("p2", "female", "1990-06-15")]

    def test_open_db_creates_file(self, tmp_path):
        db = tmp_path / "test.db"
        conn = open_db(db)
        conn.execute("CREATE TABLE t (a INTEGER)")
        conn.commit()
        conn.close()
        assert db.exists()


# ---------------------------------------------------------------------------
# Against bundled sample ViewDefinitions — end-to-end smoke
# ---------------------------------------------------------------------------


class TestBundledViews:
    def test_load_all_views(self):
        views_dir = ROOT / "views"
        paths = sorted(views_dir.glob("*.json"))
        assert len(paths) >= 5
        for path in paths:
            view = ViewDefinition.from_json_file(path)
            assert view.name
            assert view.resource
            assert view.selects

    def test_patient_view_on_synthea(self):
        bundle_dir = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "synthea-samples"
            / "synthea-r4-individual"
            / "fhir"
        )
        if not bundle_dir.exists():
            pytest.skip("Synthea data not available")

        sample_bundle = next(bundle_dir.glob("*.json"), None)
        if sample_bundle is None:
            pytest.skip("No bundles found")

        import json as _json

        with open(sample_bundle) as f:
            bundle = _json.load(f)
        resources = [e["resource"] for e in bundle.get("entry", []) if e.get("resource")]

        view = ViewDefinition.from_json_file(ROOT / "views" / "patient.json")
        rows = list(run_view(view, resources))
        assert len(rows) >= 1
        patient_row = rows[0]
        assert patient_row["id"]
        assert patient_row["gender"] in ("male", "female", "other", "unknown")
