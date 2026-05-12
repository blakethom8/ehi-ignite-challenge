"""Guest PDF pipeline — multipass dispatch, page caps, MANIFEST stanza.

These tests cover the failure modes that allowed a 25-page Cedars summary
to produce an empty workspace export: the wrong default pipeline, the
20-page hard cap, and the PDF→facts→export adapter gap. The vision backend
is monkeypatched so tests don't incur Anthropic API costs.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from api.core import guest_harmonization
from api.main import app
from lib.extract.pipelines import base as pipeline_base
from scripts import export_workspace_package


def _fake_bundle() -> dict[str, Any]:
    """A FHIR Bundle that mimics what a real multipass run would produce
    for the Cedars-Sinai summary: Patient + Encounter + Condition + meds
    + immunizations + observations. Keeps the test deterministic without a
    real PDF or a live Claude call.
    """
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-from-pdf",
                    "name": [{"given": ["Sample"], "family": "Cedars"}],
                    "gender": "female",
                    "birthDate": "1975-03-21",
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "enc-1",
                    "status": "finished",
                    "class": {"display": "AMB"},
                    "type": [{"text": "Office Visit"}],
                    "period": {"start": "2026-04-22"},
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "cond-1",
                    "code": {"text": "Allergic rhinitis"},
                    "clinicalStatus": {"text": "active"},
                    "recordedDate": "2025-07-01",
                }
            },
            {
                "resource": {
                    "resourceType": "MedicationStatement",
                    "id": "med-1",
                    "status": "active",
                    "medicationCodeableConcept": {"text": "Cetirizine 10 MG"},
                    "effectiveDateTime": "2025-07-01",
                }
            },
            {
                "resource": {
                    "resourceType": "MedicationStatement",
                    "id": "med-2",
                    "status": "active",
                    "medicationCodeableConcept": {"text": "Fluticasone propionate nasal spray"},
                }
            },
            {
                "resource": {
                    "resourceType": "Immunization",
                    "id": "imm-1",
                    "status": "completed",
                    "vaccineCode": {"text": "Influenza"},
                    "occurrenceDateTime": "2025-10-15",
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-1",
                    "status": "final",
                    "code": {"text": "Hemoglobin"},
                    "valueQuantity": {"value": 13.4, "unit": "g/dL"},
                    "effectiveDateTime": "2025-11-07",
                }
            },
        ],
    }


@dataclass
class _StubPage:
    text: str = "stub page text"
    tables: tuple = ()


class _StubPipeline:
    """Drop-in replacement for the registered multipass-fhir class.

    Records constructor args + the path passed to ``extract()`` so tests
    can assert on dispatch behavior. Always returns ``_fake_bundle()``.
    """

    metadata = pipeline_base.PipelineMetadata(
        name="multipass-fhir",
        description="stub",
        architecture="multipass-vision",
        primary_backends=["anthropic"],
    )

    last_init: dict[str, Any] = {}
    last_extract: dict[str, Any] = {}
    raise_on_extract: Exception | None = None

    def __init__(self, *, patient_id: str = "unknown", **_kwargs: Any) -> None:
        _StubPipeline.last_init = {"patient_id": patient_id}

    def extract(self, pdf_path: Path, **_kwargs: Any) -> dict[str, Any]:
        _StubPipeline.last_extract = {"path": Path(pdf_path)}
        if _StubPipeline.raise_on_extract is not None:
            raise _StubPipeline.raise_on_extract
        return _fake_bundle()


class _FallbackStubPipeline:
    """Registers as ``pdfplumber-lab-text`` for fallback-path tests."""

    metadata = pipeline_base.PipelineMetadata(
        name="pdfplumber-lab-text",
        description="stub fallback",
        architecture="ocr-text",
        primary_backends=["pdfplumber"],
    )

    last_init: dict[str, Any] = {}

    def __init__(self, *, patient_id: str = "unknown", **_kwargs: Any) -> None:
        _FallbackStubPipeline.last_init = {"patient_id": patient_id}

    def extract(self, pdf_path: Path, **_kwargs: Any) -> dict[str, Any]:
        return {"resourceType": "Bundle", "type": "collection", "entry": []}


class GuestPDFPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="guest-pdf-pipeline-test-"))
        self._old_root = guest_harmonization.GUEST_ROOT
        self._old_secret_path = guest_harmonization.GUEST_SECRET_PATH
        guest_harmonization.GUEST_ROOT = self._tmp / "runs"
        guest_harmonization.GUEST_SECRET_PATH = self._tmp / "guest.key"
        self.client = TestClient(app)

        self._page_count = 3
        from lib.extract.pipelines import text_first as _text_first

        self._old_extract_pages = _text_first.extract_pdf_text_pages

        def _fake_pages(_path: Path) -> list[_StubPage]:
            return [_StubPage() for _ in range(self._page_count)]

        _text_first.extract_pdf_text_pages = _fake_pages  # type: ignore[assignment]
        self._text_first_module = _text_first

        # Register the stubs under the same names as the real pipelines so
        # `get_pipeline(name)` routes to them. We restore the real classes
        # in tearDown.
        registry = pipeline_base._REGISTRY
        self._registry = registry
        self._old_pipelines = dict(registry._pipelines)
        registry._pipelines["multipass-fhir"] = _StubPipeline
        registry._pipelines["pdfplumber-lab-text"] = _FallbackStubPipeline

        _StubPipeline.last_init = {}
        _StubPipeline.last_extract = {}
        _StubPipeline.raise_on_extract = None
        _FallbackStubPipeline.last_init = {}

        import os as _os

        self._old_api_key = _os.environ.get("ANTHROPIC_API_KEY")
        _os.environ["ANTHROPIC_API_KEY"] = "test-key"

        # Make sure each test sees a clean daily budget — the budget sidecar
        # lives under GUEST_ROOT which is already per-test, so nothing more
        # is needed; the file just doesn't exist yet.

    def tearDown(self) -> None:
        guest_harmonization.GUEST_ROOT = self._old_root
        guest_harmonization.GUEST_SECRET_PATH = self._old_secret_path
        self._text_first_module.extract_pdf_text_pages = self._old_extract_pages  # type: ignore[assignment]
        self._registry._pipelines = self._old_pipelines

        import os as _os

        if self._old_api_key is None:
            _os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            _os.environ["ANTHROPIC_API_KEY"] = self._old_api_key

        shutil.rmtree(self._tmp, ignore_errors=True)

    def _create_run(self) -> str:
        response = self.client.post("/api/guest-harmonization/runs")
        self.assertEqual(response.status_code, 201)
        return response.json()["run_id"]

    def _upload_fake_pdf(self, run_id: str, *, name: str = "cedars.pdf") -> dict[str, Any]:
        response = self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": (name, b"%PDF-1.4 stub", "application/pdf")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_pdf_dispatch_runs_multipass_and_persists_bundle(self) -> None:
        run_id = self._create_run()
        self._upload_fake_pdf(run_id)
        self._page_count = 7

        processed = self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        self.assertEqual(processed.status_code, 200, processed.text)
        guest_harmonization.wait_for_processing(run_id)

        output = self.client.get(f"/api/guest-harmonization/runs/{run_id}/output").json()
        methods = {prov["method"] for prov in output["provenance"]}
        self.assertIn("guest_pdf_multipass_v1", methods)
        # The per-run harmonized record allows a narrow resource set;
        # Encounter is only present in the workspace export (see the
        # export test for that assertion).
        resource_types = {fact["resource_type"] for fact in output["facts"]}
        self.assertIn("Condition", resource_types)
        self.assertIn("MedicationStatement", resource_types)
        self.assertIn("Observation", resource_types)
        self.assertIn("Immunization", resource_types)

        # Per-source bundle is persisted for the workspace exporter.
        manifest = guest_harmonization.get_run(run_id)
        uploaded_id = manifest["uploaded_files"][0]["file_id"]
        bundle_path = guest_harmonization._per_source_bundle_path(run_id, uploaded_id)
        self.assertTrue(bundle_path.exists(), "expected per-source FHIR bundle on disk")

        # Pipeline bookkeeping made it onto the manifest.
        self.assertEqual(manifest["pdf_pipelines_used"], ["multipass-fhir"])
        self.assertEqual(manifest["pdf_pages_processed"], 7)

    def test_export_workspace_includes_pdf_extracted_facts(self) -> None:
        run_id = self._create_run()
        self._upload_fake_pdf(run_id)
        self._page_count = 25  # The Cedars summary the bug reproduced on.

        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        guest_harmonization.wait_for_processing(run_id)
        response = self.client.get(
            f"/api/guest-harmonization/runs/{run_id}/export-workspace"
        )
        self.assertEqual(response.status_code, 200, response.text)
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        with zf:
            roots = {name.split("/", 1)[0] for name in zf.namelist() if "/" in name}
            (root,) = roots

            manifest = json.loads(zf.read(f"{root}/MANIFEST.json"))
            self.assertGreater(manifest["canonical_fact_count"], 0)
            self.assertIn("extraction", manifest)
            self.assertEqual(manifest["extraction"]["tier"], "guest")
            self.assertEqual(manifest["extraction"]["pdf_pipeline"], "multipass-fhir")
            self.assertEqual(manifest["extraction"]["pdf_pages_processed"], 25)

            facts = json.loads(zf.read(f"{root}/evidence/canonical-facts.json"))["facts"]
            resource_types = {f["resource_type"] for f in facts}
            for required in ("Encounter", "Condition", "MedicationStatement", "Immunization", "Observation"):
                self.assertIn(required, resource_types, f"missing {required} in workspace export")

            patient_summary = zf.read(f"{root}/PATIENT-SUMMARY.md").decode()
            # Real name from the fake Patient resource — not the misleading
            # 'Synthetic Demo Patient' fallback that the bug exposed.
            self.assertIn("Sample Cedars", patient_summary)
            self.assertNotIn("Synthetic Demo Patient", patient_summary)

    def test_per_pdf_page_cap_rejects_oversized_input(self) -> None:
        run_id = self._create_run()
        self._upload_fake_pdf(run_id)
        self._page_count = guest_harmonization.GUEST_MAX_PAGES_PER_PDF + 1

        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        guest_harmonization.wait_for_processing(run_id)
        output = self.client.get(
            f"/api/guest-harmonization/runs/{run_id}/output"
        ).json()
        codes = {issue["code"] for issue in output["quality_issues"]}
        self.assertIn("pdf_page_limit_per_file_exceeded", codes)
        # No facts should have come through.
        self.assertEqual(output["facts"], [])

    def test_25_page_pdf_fits_under_default_run_cap(self) -> None:
        # The 25-page Cedars summary used to trip the old 20-page hard cap.
        # Confirm the default 60-page run cap accepts it cleanly.
        run_id = self._create_run()
        self._upload_fake_pdf(run_id)
        self._page_count = 25

        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        guest_harmonization.wait_for_processing(run_id)
        output = self.client.get(
            f"/api/guest-harmonization/runs/{run_id}/output"
        ).json()
        codes = {issue["code"] for issue in output["quality_issues"]}
        self.assertNotIn("pdf_page_limit_exceeded", codes)
        self.assertNotIn("pdf_page_limit_per_file_exceeded", codes)

    def test_missing_anthropic_key_falls_back_to_lab_pipeline(self) -> None:
        import os as _os

        _os.environ.pop("ANTHROPIC_API_KEY", None)
        run_id = self._create_run()
        self._upload_fake_pdf(run_id)

        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        guest_harmonization.wait_for_processing(run_id)
        output = self.client.get(
            f"/api/guest-harmonization/runs/{run_id}/output"
        ).json()
        codes = {issue["code"] for issue in output["quality_issues"]}
        self.assertIn("pipeline_unconfigured", codes)

        manifest = guest_harmonization.get_run(run_id)
        self.assertIn(
            "pdfplumber-lab-text",
            manifest.get("pdf_pipelines_used") or [],
            "expected fallback pipeline to run when ANTHROPIC_API_KEY is missing",
        )

    def test_daily_budget_exhausted_triggers_circuit_break(self) -> None:
        # Pre-fill the daily counter past the configured budget.
        old_budget = guest_harmonization.GUEST_GLOBAL_DAILY_PAGE_BUDGET
        guest_harmonization.GUEST_GLOBAL_DAILY_PAGE_BUDGET = 1
        try:
            guest_harmonization._record_daily_page_use(10)
            run_id = self._create_run()
            self._upload_fake_pdf(run_id)
            self._page_count = 3

            self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
            guest_harmonization.wait_for_processing(run_id)
            output = self.client.get(
                f"/api/guest-harmonization/runs/{run_id}/output"
            ).json()
            codes = {issue["code"] for issue in output["quality_issues"]}
            self.assertIn("daily_budget_exhausted", codes)

            manifest = guest_harmonization.get_run(run_id)
            self.assertIn(
                "pdfplumber-lab-text",
                manifest.get("pdf_pipelines_used") or [],
            )
        finally:
            guest_harmonization.GUEST_GLOBAL_DAILY_PAGE_BUDGET = old_budget


class GuestProgressEventTests(unittest.TestCase):
    """Progress block + events list — the dynamic feedback frontend renders.

    Mirrors the authenticated ExtractJob shape so the same React components
    (PdfPageProgressMap, PdfExtractionEventTimeline) work on both surfaces.
    """

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="guest-progress-test-"))
        self._old_root = guest_harmonization.GUEST_ROOT
        self._old_secret_path = guest_harmonization.GUEST_SECRET_PATH
        guest_harmonization.GUEST_ROOT = self._tmp / "runs"
        guest_harmonization.GUEST_SECRET_PATH = self._tmp / "guest.key"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        guest_harmonization.GUEST_ROOT = self._old_root
        guest_harmonization.GUEST_SECRET_PATH = self._old_secret_path
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _bundle(self) -> dict[str, Any]:
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "p1",
                        "name": [{"given": ["Progress"], "family": "Test"}],
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "o1",
                        "code": {"text": "Test"},
                        "valueQuantity": {"value": 1, "unit": "x"},
                        "effectiveDateTime": "2025-01-01",
                        "status": "final",
                    }
                },
            ],
        }

    def test_initial_response_is_processing_with_seeded_progress(self) -> None:
        run = self.client.post("/api/guest-harmonization/runs").json()
        run_id = run["run_id"]
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("bundle.json", json.dumps(self._bundle()), "application/json")},
        )

        kickoff = self.client.post(f"/api/guest-harmonization/runs/{run_id}/process").json()
        self.assertEqual(kickoff["status"], "processing")
        self.assertIsNotNone(kickoff["progress"])
        # Seeded progress carries the total file count so the UI can render
        # a progress bar before the daemon writes its first event.
        self.assertEqual(kickoff["progress"]["total_files"], 1)

        guest_harmonization.wait_for_processing(run_id)

    def test_progress_events_are_appended_per_file(self) -> None:
        run_id = self.client.post("/api/guest-harmonization/runs").json()["run_id"]
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("a.json", json.dumps(self._bundle()), "application/json")},
        )
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("b.json", json.dumps(self._bundle()), "application/json")},
        )
        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        guest_harmonization.wait_for_processing(run_id)

        final = self.client.get(f"/api/guest-harmonization/runs/{run_id}").json()
        progress = final["progress"]
        self.assertEqual(progress["status"], "complete")
        self.assertEqual(progress["processed_files"], 2)
        self.assertEqual(progress["total_files"], 2)

        event_types = [e["event_type"] for e in progress["events"]]
        self.assertEqual(event_types[0], "job_started")
        self.assertEqual(event_types[-1], "job_completed")
        self.assertEqual(event_types.count("file_started"), 2)
        self.assertEqual(event_types.count("file_completed"), 2)
        # Each file event carries a source label so the UI can show "Working
        # on a.json" / "Finished b.json" without joining tables.
        labels = {e["source_label"] for e in progress["events"] if e["source_label"]}
        self.assertEqual(labels, {"a.json", "b.json"})

    def test_failed_processing_records_failure_event(self) -> None:
        run_id = self.client.post("/api/guest-harmonization/runs").json()["run_id"]
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("bundle.json", json.dumps(self._bundle()), "application/json")},
        )

        original_process_run = guest_harmonization.process_run

        def _boom(_run_id: str) -> dict[str, Any]:
            raise RuntimeError("simulated worker crash")

        guest_harmonization.process_run = _boom  # type: ignore[assignment]
        try:
            self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
            guest_harmonization.wait_for_processing(run_id)
        finally:
            guest_harmonization.process_run = original_process_run  # type: ignore[assignment]

        final = self.client.get(f"/api/guest-harmonization/runs/{run_id}").json()
        self.assertEqual(final["status"], "failed")
        self.assertEqual(final["progress"]["status"], "failed")
        last_event = final["progress"]["events"][-1]
        self.assertEqual(last_event["event_type"], "job_failed")
        self.assertIn("simulated worker crash", last_event["message"])


class PatientDisplayFallbackTests(unittest.TestCase):
    def test_unknown_patient_when_no_resource(self) -> None:
        self.assertEqual(export_workspace_package.patient_display(None), "Unknown patient")
        self.assertEqual(export_workspace_package.patient_display({}), "Unknown patient")

    def test_uses_human_name_when_available(self) -> None:
        result = export_workspace_package.patient_display(
            {"name": [{"given": ["Blake"], "family": "Thomson"}]}
        )
        self.assertEqual(result, "Blake Thomson")


if __name__ == "__main__":
    unittest.main()
