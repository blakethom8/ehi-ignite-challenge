"""Tests for the SQL-on-FHIR prototype.

We cover three layers:
1. FHIRPath-lite — the minimal expression evaluator
2. The ViewDefinition runner — against both synthetic fixtures and the
   canonical examples from the SQL-on-FHIR v2 test suite
3. SQLite materialization — round-trip into a real in-memory database
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "sql_on_fhir"

from lib.sql_on_fhir.derived import (
    build_medication_episodes,
    build_observation_latest,
    default_derivations,
    medication_episode_derivation,
    observation_latest_derivation,
)
from lib.sql_on_fhir.enrich import (
    default_enrichments,
    load_drug_classifier,
    medication_request_enrichment,
)
from lib.sql_on_fhir.fhirpath import evaluate
from lib.sql_on_fhir.runner import run_view
from lib.sql_on_fhir.sqlite_sink import materialize, materialize_all, open_db
from lib.sql_on_fhir.view_definition import ViewDefinition


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
        views_dir = Path(__file__).resolve().parents[1] / "sql_on_fhir" / "views"
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


# ---------------------------------------------------------------------------
# Filtered subset view — condition_active (P1.3)
# ---------------------------------------------------------------------------


def _condition_resource(
    res_id: str,
    *,
    clinical_status: str | None = "active",
    display: str = "Test condition",
    snomed_code: str = "44054006",
    patient_ref: str = "urn:uuid:pt-x",
) -> dict:
    resource: dict = {
        "resourceType": "Condition",
        "id": res_id,
        "subject": {"reference": patient_ref},
        "code": {
            "text": display,
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": snomed_code,
                    "display": display,
                }
            ],
        },
    }
    if clinical_status is not None:
        resource["clinicalStatus"] = {
            "coding": [
                {
                    "system": (
                        "http://terminology.hl7.org/CodeSystem/condition-clinical"
                    ),
                    "code": clinical_status,
                }
            ]
        }
    return resource


class TestConditionActiveView:
    def test_active_condition_passes_filter(self):
        view = ViewDefinition.from_json_file(
            ROOT / "views" / "condition_active.json"
        )
        resources = [_condition_resource("c1", clinical_status="active")]
        rows = list(run_view(view, resources))
        assert len(rows) == 1
        assert rows[0]["clinical_status"] == "active"

    def test_resolved_condition_excluded(self):
        view = ViewDefinition.from_json_file(
            ROOT / "views" / "condition_active.json"
        )
        resources = [_condition_resource("c1", clinical_status="resolved")]
        rows = list(run_view(view, resources))
        assert rows == []

    def test_recurrence_and_relapse_pass_filter(self):
        view = ViewDefinition.from_json_file(
            ROOT / "views" / "condition_active.json"
        )
        resources = [
            _condition_resource("c1", clinical_status="recurrence"),
            _condition_resource("c2", clinical_status="relapse"),
        ]
        rows = list(run_view(view, resources))
        assert len(rows) == 2
        statuses = sorted(r["clinical_status"] for r in rows)
        assert statuses == ["recurrence", "relapse"]

    def test_missing_clinical_status_excluded(self):
        # Defensive: a Condition without clinicalStatus falls out of the
        # active subset rather than leaking into the problem list.
        view = ViewDefinition.from_json_file(
            ROOT / "views" / "condition_active.json"
        )
        resources = [_condition_resource("c1", clinical_status=None)]
        rows = list(run_view(view, resources))
        assert rows == []

    def test_subset_is_subset_of_condition(self):
        # Materialize both condition and condition_active against the same
        # mixed input and verify the filtered table is a strict subset of
        # the full table — same id space, fewer or equal rows.
        base_view = ViewDefinition.from_json_file(ROOT / "views" / "condition.json")
        active_view = ViewDefinition.from_json_file(
            ROOT / "views" / "condition_active.json"
        )
        resources = [
            _condition_resource("c1", clinical_status="active"),
            _condition_resource("c2", clinical_status="resolved"),
            _condition_resource("c3", clinical_status="recurrence"),
            _condition_resource("c4", clinical_status="inactive"),
            _condition_resource("c5", clinical_status="relapse"),
            _condition_resource("c6", clinical_status=None),
        ]
        conn = sqlite3.connect(":memory:")
        counts = materialize_all([base_view, active_view], resources, conn)
        assert counts["condition"] == 6
        assert counts["condition_active"] == 3

        base_ids = {
            r[0]
            for r in conn.execute('SELECT id FROM "condition"').fetchall()
        }
        active_ids = {
            r[0]
            for r in conn.execute('SELECT id FROM "condition_active"').fetchall()
        }
        assert active_ids.issubset(base_ids)
        assert active_ids == {"c1", "c3", "c5"}

    def test_column_shape_matches_condition_view(self):
        # The JSON contract: condition_active carries the same columns as
        # condition so any query that groups or joins on condition can be
        # pointed at condition_active without a rewrite.
        base = ViewDefinition.from_json_file(ROOT / "views" / "condition.json")
        active = ViewDefinition.from_json_file(
            ROOT / "views" / "condition_active.json"
        )
        base_cols = [c.name for c in base.all_columns()]
        active_cols = [c.name for c in active.all_columns()]
        assert base_cols == active_cols


# ---------------------------------------------------------------------------
# observation_latest (SQLite VIEW) — P1.4
# ---------------------------------------------------------------------------


def _obs_resource(
    res_id: str,
    *,
    loinc_code: str,
    value: float,
    effective_date: str,
    patient_ref: str = "urn:uuid:pt-x",
    display: str | None = None,
) -> dict:
    return {
        "resourceType": "Observation",
        "id": res_id,
        "status": "final",
        "subject": {"reference": patient_ref},
        "effectiveDateTime": effective_date,
        "code": {
            "text": display or loinc_code,
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": loinc_code,
                    "display": display or loinc_code,
                }
            ],
        },
        "valueQuantity": {"value": value, "unit": "x"},
    }


def _observation_view() -> ViewDefinition:
    return ViewDefinition.from_json_file(ROOT / "views" / "observation.json")


class TestObservationLatestView:
    def test_default_registry_has_observation_latest(self):
        reg = default_derivations()
        assert "observation_latest" in reg
        derivation = reg["observation_latest"]
        assert derivation.depends_on == ["observation"]
        assert derivation.kind == "view"

    def test_most_recent_row_per_loinc_wins(self):
        view = _observation_view()
        resources = [
            _obs_resource(
                "o1", loinc_code="4548-4", value=5.5, effective_date="2020-01-01"
            ),
            _obs_resource(
                "o2", loinc_code="4548-4", value=6.8, effective_date="2022-06-01"
            ),
            _obs_resource(
                "o3", loinc_code="4548-4", value=7.1, effective_date="2024-03-15"
            ),
        ]
        conn = sqlite3.connect(":memory:")
        counts = materialize_all([view], resources, conn)
        assert counts["observation"] == 3
        assert counts["observation_latest"] == 1
        row = conn.execute(
            "SELECT value_quantity, effective_date FROM observation_latest"
        ).fetchone()
        assert row[0] == 7.1
        assert row[1] == "2024-03-15"

    def test_one_row_per_patient_loinc_pair(self):
        view = _observation_view()
        resources = [
            _obs_resource("a1", loinc_code="4548-4", value=6.0,
                          effective_date="2023-01-01", patient_ref="urn:uuid:p1"),
            _obs_resource("a2", loinc_code="4548-4", value=7.0,
                          effective_date="2024-01-01", patient_ref="urn:uuid:p1"),
            _obs_resource("b1", loinc_code="4548-4", value=5.5,
                          effective_date="2023-06-01", patient_ref="urn:uuid:p2"),
            _obs_resource("c1", loinc_code="2160-0", value=0.9,
                          effective_date="2024-02-01", patient_ref="urn:uuid:p1"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        rows = conn.execute(
            "SELECT patient_ref, loinc_code, value_quantity "
            "FROM observation_latest "
            "ORDER BY patient_ref, loinc_code"
        ).fetchall()
        # Three groups: (p1, 4548-4), (p1, 2160-0), (p2, 4548-4)
        assert len(rows) == 3
        # p1's A1c is the 2024 reading, not 2023
        assert ("urn:uuid:p1", "4548-4", 7.0) in rows
        assert ("urn:uuid:p1", "2160-0", 0.9) in rows
        assert ("urn:uuid:p2", "4548-4", 5.5) in rows

    def test_row_count_le_observation(self):
        view = _observation_view()
        resources = [
            _obs_resource(
                f"o{i}", loinc_code="4548-4", value=float(i),
                effective_date=f"202{i}-01-01",
            )
            for i in range(5)
        ]
        conn = sqlite3.connect(":memory:")
        counts = materialize_all([view], resources, conn)
        # All five observations share the same (patient, loinc) pair,
        # so observation_latest should collapse to 1.
        obs_count = conn.execute(
            "SELECT COUNT(*) FROM observation"
        ).fetchone()[0]
        latest_count = conn.execute(
            "SELECT COUNT(*) FROM observation_latest"
        ).fetchone()[0]
        assert latest_count <= obs_count
        assert latest_count == 1
        assert counts["observation_latest"] == latest_count

    def test_tiebreaker_prefers_higher_id(self):
        view = _observation_view()
        # Two rows with identical effective_date — the higher id must win.
        resources = [
            _obs_resource("aaa", loinc_code="4548-4", value=5.0,
                          effective_date="2024-01-01"),
            _obs_resource("zzz", loinc_code="4548-4", value=9.9,
                          effective_date="2024-01-01"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        row = conn.execute(
            "SELECT id, value_quantity FROM observation_latest"
        ).fetchone()
        assert row[0] == "zzz"
        assert row[1] == 9.9

    def test_observation_latest_is_live_sqlite_view(self):
        # The view must reflect mutations to the underlying table
        # without a rebuild. This is what sets it apart from
        # medication_episode (which is a materialized table).
        view = _observation_view()
        resources = [
            _obs_resource("o1", loinc_code="4548-4", value=5.0,
                          effective_date="2020-01-01"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        row = conn.execute(
            "SELECT value_quantity FROM observation_latest"
        ).fetchone()
        assert row[0] == 5.0

        # Manually insert a newer observation (simulating a subsequent
        # ingest run) — the view should surface it without us calling
        # build_observation_latest again.
        conn.execute(
            'INSERT INTO "observation" '
            "(id, patient_ref, loinc_code, effective_date, value_quantity) "
            "VALUES (?, ?, ?, ?, ?)",
            ("o2", "urn:uuid:pt-x", "4548-4", "2024-06-01", 9.9),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, value_quantity FROM observation_latest"
        ).fetchone()
        assert row[0] == "o2"
        assert row[1] == 9.9

    def test_empty_derivations_opts_out(self):
        view = _observation_view()
        resources = [
            _obs_resource("o1", loinc_code="4548-4", value=5.0,
                          effective_date="2024-01-01"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn, derivations={})
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            ).fetchall()
        ]
        assert "observation_latest" not in tables

    def test_view_dropped_and_recreated_is_idempotent(self):
        view = _observation_view()
        resources = [
            _obs_resource("o1", loinc_code="4548-4", value=5.0,
                          effective_date="2020-01-01"),
            _obs_resource("o2", loinc_code="4548-4", value=7.0,
                          effective_date="2022-01-01"),
        ]
        conn = sqlite3.connect(":memory:")
        materialize_all([view], resources, conn)
        build_observation_latest(conn)
        build_observation_latest(conn)
        rows = conn.execute(
            "SELECT COUNT(*) FROM observation_latest"
        ).fetchone()
        assert rows[0] == 1

    def test_null_loinc_excluded(self):
        view = _observation_view()
        # Observation with no coding at all — loinc_code will be NULL.
        bad = {
            "resourceType": "Observation",
            "id": "bad",
            "status": "final",
            "subject": {"reference": "urn:uuid:pt-x"},
            "effectiveDateTime": "2024-01-01",
            "code": {"text": "no coding"},
            "valueQuantity": {"value": 1.0, "unit": "x"},
        }
        good = _obs_resource(
            "good", loinc_code="4548-4", value=5.5, effective_date="2024-01-01"
        )
        conn = sqlite3.connect(":memory:")
        materialize_all([view], [bad, good], conn)
        rows = conn.execute(
            "SELECT id FROM observation_latest"
        ).fetchall()
        assert [r[0] for r in rows] == ["good"]

    def test_observation_latest_derivation_helper(self):
        derivation = observation_latest_derivation()
        assert derivation.table_name == "observation_latest"
        assert derivation.kind == "view"
        assert "observation" in derivation.depends_on
        assert callable(derivation.build)
        col_names = [c.name for c in derivation.columns]
        for expected in (
            "id",
            "patient_ref",
            "loinc_code",
            "effective_date",
            "value_quantity",
        ):
            assert expected in col_names
