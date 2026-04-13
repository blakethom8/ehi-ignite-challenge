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

from derived import (  # type: ignore  # noqa: E402
    build_medication_episodes,
    default_derivations,
    medication_episode_derivation,
)
from enrich import (  # type: ignore  # noqa: E402
    default_enrichments,
    load_drug_classifier,
    medication_request_enrichment,
)
from fhirpath import evaluate  # type: ignore  # noqa: E402
from runner import run_view  # type: ignore  # noqa: E402
from sqlite_sink import materialize, materialize_all, open_db  # type: ignore  # noqa: E402
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


# ---------------------------------------------------------------------------
# Enrichment — drug_class on medication_request (P1.1)
# ---------------------------------------------------------------------------


def _medication_view() -> ViewDefinition:
    return ViewDefinition.from_json_file(ROOT / "views" / "medication_request.json")


def _med_resource(
    res_id: str,
    *,
    rxnorm_code: str | None = None,
    rxnorm_display: str | None = None,
    text: str | None = None,
    authored_on: str = "2023-01-01",
    status: str = "active",
    subject_ref: str = "urn:uuid:pt-x",
) -> dict:
    coding = []
    if rxnorm_code or rxnorm_display:
        coding.append(
            {
                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                "code": rxnorm_code,
                "display": rxnorm_display,
            }
        )
    return {
        "resourceType": "MedicationRequest",
        "id": res_id,
        "status": status,
        "intent": "order",
        "subject": {"reference": subject_ref},
        "authoredOn": authored_on,
        "medicationCodeableConcept": {
            "text": text,
            "coding": coding or None,
        },
    }


class TestDrugClassifier:
    def test_rxnorm_code_match_wins(self):
        classify = load_drug_classifier()
        # 11289 is warfarin in the shared mapping
        assert classify("11289", None) == "anticoagulants"

    def test_keyword_match_when_no_rxnorm(self):
        classify = load_drug_classifier()
        assert classify(None, "Warfarin sodium 5 MG") == "anticoagulants"

    def test_keyword_match_is_case_insensitive(self):
        classify = load_drug_classifier()
        assert classify(None, "APIXABAN 5 mg oral tablet") == "anticoagulants"

    def test_rxnorm_code_takes_precedence_over_unrelated_text(self):
        classify = load_drug_classifier()
        # Warfarin RxNorm + gibberish text still classifies as anticoag
        assert classify("11289", "zzz unrelated zzz") == "anticoagulants"

    def test_unknown_medication_returns_none(self):
        classify = load_drug_classifier()
        assert classify(None, "some random vitamin") is None

    def test_empty_inputs(self):
        classify = load_drug_classifier()
        assert classify(None, None) is None
        assert classify("", "") is None

    def test_known_classes_exposed(self):
        classify = load_drug_classifier()
        # Touch each class key we document in the run_sql preamble so
        # the preamble and the mapping file can't drift silently.
        assert classify(None, "clopidogrel 75 mg") == "antiplatelets"
        assert classify(None, "lisinopril 10 mg") == "ace_inhibitors"
        assert classify(None, "losartan 50 mg") == "arbs"
        assert classify(None, "ibuprofen 400 mg") == "nsaids"
        assert classify(None, "oxycodone 5 mg") == "opioids"


class TestMedicationEnrichment:
    def test_enrichment_adds_drug_class_column(self):
        enrichment = medication_request_enrichment()
        assert enrichment.view_name == "medication_request"
        names = [c.name for c in enrichment.columns]
        assert "drug_class" in names

    def test_apply_populates_drug_class(self):
        enrichment = medication_request_enrichment()
        row = {
            "id": "m1",
            "rxnorm_code": "11289",
            "medication_text": "warfarin 5 mg",
        }
        enrichment.apply(row)
        assert row["drug_class"] == "anticoagulants"

    def test_apply_sets_none_for_unknown(self):
        enrichment = medication_request_enrichment()
        row = {"id": "m2", "rxnorm_code": None, "medication_text": "random vitamin"}
        enrichment.apply(row)
        assert "drug_class" in row
        assert row["drug_class"] is None

    def test_default_registry_has_medication_request(self):
        reg = default_enrichments()
        assert "medication_request" in reg


class TestMaterializeWithEnrichment:
    def test_drug_class_populated_end_to_end(self, tmp_path):
        view = _medication_view()
        resources = [
            _med_resource(
                "m1",
                rxnorm_code="855332",
                rxnorm_display="warfarin sodium 5 MG Oral Tablet",
                text="warfarin 5 mg",
            ),
            _med_resource(
                "m2",
                rxnorm_code="99999",
                rxnorm_display="clopidogrel 75 MG Oral Tablet",
                text="clopidogrel 75 mg",
            ),
            _med_resource(
                "m3",
                rxnorm_code="0",
                rxnorm_display="Vitamin D 1000 IU",
                text="Vitamin D 1000 IU",
            ),
        ]
        conn = sqlite3.connect(":memory:")
        n = materialize(view, resources, conn)
        assert n == 3
        rows = conn.execute(
            "SELECT id, drug_class FROM medication_request ORDER BY id"
        ).fetchall()
        assert rows == [
            ("m1", "anticoagulants"),
            ("m2", "antiplatelets"),
            ("m3", None),
        ]

    def test_group_by_drug_class_smoke(self, tmp_path):
        view = _medication_view()
        resources = [
            _med_resource(
                f"a{i}",
                rxnorm_code=None,
                rxnorm_display=None,
                text="warfarin 5 mg",
            )
            for i in range(4)
        ] + [
            _med_resource(
                f"b{i}",
                rxnorm_code=None,
                rxnorm_display=None,
                text="aspirin 81 mg",
            )
            for i in range(2)
        ]
        conn = sqlite3.connect(":memory:")
        materialize(view, resources, conn)
        groups = dict(
            conn.execute(
                "SELECT drug_class, COUNT(*) FROM medication_request "
                "GROUP BY drug_class ORDER BY drug_class"
            ).fetchall()
        )
        assert groups["anticoagulants"] == 4
        assert groups["antiplatelets"] == 2

    def test_empty_enrichments_opts_out(self, tmp_path):
        view = _medication_view()
        resources = [
            _med_resource("m1", text="warfarin 5 mg"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize(view, resources, conn, enrichments={})
        # Column must not exist when enrichment is opted out
        cols = [
            r[1]
            for r in conn.execute("PRAGMA table_info(medication_request)").fetchall()
        ]
        assert "drug_class" not in cols

    def test_materialize_all_applies_enrichment(self, tmp_path):
        view = _medication_view()
        resources = [
            _med_resource("m1", text="warfarin 5 mg"),
            _med_resource("m2", text="ibuprofen 400 mg"),
        ]
        conn = sqlite3.connect(":memory:")
        counts = materialize_all([view], resources, conn)
        assert counts["medication_request"] == 2
        rows = conn.execute(
            "SELECT id, drug_class FROM medication_request ORDER BY id"
        ).fetchall()
        assert rows == [("m1", "anticoagulants"), ("m2", "nsaids")]


# ---------------------------------------------------------------------------
# Derived tables — medication_episode (P1.2)
# ---------------------------------------------------------------------------


class TestMedicationEpisodeDerivation:
    def test_default_registry_has_medication_episode(self):
        reg = default_derivations()
        assert "medication_episode" in reg
        derivation = reg["medication_episode"]
        assert derivation.depends_on == ["medication_request"]
        # Column schema must match the DDL in derived.py
        col_names = [c.name for c in derivation.columns]
        for expected in (
            "episode_id",
            "patient_ref",
            "display",
            "rxnorm_code",
            "drug_class",
            "latest_status",
            "is_active",
            "start_date",
            "end_date",
            "request_count",
            "duration_days",
            "first_request_id",
        ):
            assert expected in col_names

    def test_groups_by_display_into_single_episode(self):
        view = _medication_view()
        resources = [
            _med_resource("m1", text="warfarin 5 mg", authored_on="2022-01-15"),
            _med_resource("m2", text="warfarin 5 mg", authored_on="2022-06-20"),
            _med_resource("m3", text="warfarin 5 mg", authored_on="2022-12-01"),
        ]
        conn = sqlite3.connect(":memory:")
        counts = materialize_all([view], resources, conn)
        assert counts["medication_request"] == 3
        assert counts["medication_episode"] == 1
        row = conn.execute(
            "SELECT patient_ref, display, request_count, start_date, end_date, "
            "is_active, drug_class FROM medication_episode"
        ).fetchone()
        # Patient is only ever prescribed warfarin (status=active default),
        # so the episode is live today → end_date is NULL.
        assert row[0] == "urn:uuid:pt-x"
        assert row[1] == "warfarin 5 mg"
        assert row[2] == 3
        assert row[3] == "2022-01-15"
        assert row[4] is None
        assert row[5] == 1
        assert row[6] == "anticoagulants"

    def test_inactive_episode_has_end_date_and_duration(self):
        view = _medication_view()
        resources = [
            _med_resource(
                "m1", text="lisinopril 10 mg",
                authored_on="2020-01-01", status="completed",
            ),
            _med_resource(
                "m2", text="lisinopril 10 mg",
                authored_on="2020-07-10", status="stopped",
            ),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        row = conn.execute(
            "SELECT is_active, start_date, end_date, latest_status, duration_days "
            "FROM medication_episode"
        ).fetchone()
        assert row[0] == 0
        assert row[1] == "2020-01-01"
        assert row[2] == "2020-07-10"
        assert row[3] == "stopped"
        # Jan 1 → Jul 10 = 191 days exactly
        assert row[4] == pytest.approx(191.0, abs=0.001)

    def test_case_insensitive_grouping(self):
        view = _medication_view()
        resources = [
            _med_resource("m1", text="Aspirin 81 MG"),
            _med_resource("m2", text="aspirin 81 mg"),
            _med_resource("m3", text="ASPIRIN 81 MG "),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        rows = conn.execute(
            "SELECT request_count FROM medication_episode"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 3

    def test_episodes_separated_per_patient(self):
        view = _medication_view()
        resources = [
            _med_resource(
                "m1", text="metformin 500 mg",
                subject_ref="urn:uuid:pt-a",
            ),
            _med_resource(
                "m2", text="metformin 500 mg",
                subject_ref="urn:uuid:pt-b",
            ),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        rows = conn.execute(
            "SELECT patient_ref FROM medication_episode ORDER BY patient_ref"
        ).fetchall()
        assert [r[0] for r in rows] == ["urn:uuid:pt-a", "urn:uuid:pt-b"]

    def test_different_drugs_different_episodes(self):
        view = _medication_view()
        resources = [
            _med_resource("m1", text="warfarin 5 mg"),
            _med_resource("m2", text="ibuprofen 400 mg"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        rows = conn.execute(
            "SELECT display, drug_class FROM medication_episode ORDER BY display"
        ).fetchall()
        assert rows == [
            ("ibuprofen 400 mg", "nsaids"),
            ("warfarin 5 mg", "anticoagulants"),
        ]

    def test_empty_derivations_opts_out(self):
        view = _medication_view()
        resources = [_med_resource("m1", text="warfarin 5 mg")]
        conn = sqlite3.connect(":memory:")
        counts = materialize_all([view], resources, conn, derivations={})
        assert "medication_episode" not in counts
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "medication_episode" not in tables

    def test_dependency_missing_skips_derivation(self):
        # Partial build: only the patient view, no medication_request.
        patient_view = ViewDefinition.from_json_file(
            ROOT / "views" / "patient.json"
        )
        resources = [
            {
                "resourceType": "Patient",
                "id": "p1",
                "gender": "female",
                "birthDate": "1970-01-01",
            }
        ]
        conn = sqlite3.connect(":memory:")
        counts = materialize_all([patient_view], resources, conn)
        # medication_episode should not be built when its source table isn't
        # part of the run — we must not raise, just silently skip.
        assert "medication_episode" not in counts
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "medication_episode" not in tables

    def test_build_medication_episodes_is_idempotent(self):
        view = _medication_view()
        resources = [
            _med_resource("m1", text="warfarin 5 mg", authored_on="2022-01-01"),
            _med_resource("m2", text="warfarin 5 mg", authored_on="2022-06-01"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        first = conn.execute("SELECT COUNT(*) FROM medication_episode").fetchone()[0]
        # Calling build again should drop+recreate without duplicating rows.
        build_medication_episodes(conn)
        build_medication_episodes(conn)
        second = conn.execute("SELECT COUNT(*) FROM medication_episode").fetchone()[0]
        assert first == second == 1

    def test_rows_without_display_are_skipped(self):
        view = _medication_view()
        resources = [
            _med_resource("m1", text=None),  # no display at all
            _med_resource("m2", text="warfarin 5 mg"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        rows = conn.execute(
            "SELECT display FROM medication_episode"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "warfarin 5 mg"

    def test_medication_episode_derivation_helper(self):
        derivation = medication_episode_derivation()
        assert derivation.table_name == "medication_episode"
        assert "medication_request" in derivation.depends_on
        assert callable(derivation.build)
        assert len(derivation.columns) == 12
