import json
from pathlib import Path
from typing import Any

import pytest

from lib.extract.lab.cli import main
from lib.extract.lab.recorder import RunRecorder
from lib.extract.lab.suite import dry_run_plan, load_suite, run_suite, validate_suite
from lib.extract.pipelines.multipass_fhir import MultiPassFHIRPipeline


def _stub_extract(self: Any, pdf_path: Path, *, recorder: RunRecorder | None = None, **kwargs: Any) -> dict:
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"text": "Creatinine"},
                    "valueQuantity": {"value": 1.2, "unit": "mg/dL"},
                }
            }
        ],
    }
    if recorder is not None:
        recorder.log_pass(
            pass_name="stub",
            prompt="stub",
            response={},
            usage={"input_tokens": 1, "output_tokens": 1, "latency_ms": 10, "cost_usd": 0.0},
            extraction={},
        )
        recorder.finish(bundle=bundle)
    return bundle


@pytest.fixture()
def fake_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return pdf


@pytest.fixture()
def suite_file(tmp_path: Path, fake_pdf: Path) -> Path:
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        f"""
name: test-suite
pipelines:
  - multipass-fhir
cases:
  - label: fake
    pdf: {fake_pdf}
    tags: [unit]
""".strip()
    )
    return suite


def test_load_suite_and_dry_run(suite_file: Path, fake_pdf: Path) -> None:
    suite = load_suite(suite_file)

    assert validate_suite(suite) == []
    assert suite.name == "test-suite"
    assert suite.pipelines == ["multipass-fhir"]
    assert suite.cases[0].pdf == fake_pdf
    assert dry_run_plan(suite)[0]["case"] == "fake"


def test_cli_suite_dry_run(suite_file: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = main(["suite", "--config", str(suite_file), "--dry-run"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "test-suite" in captured.out
    assert "multipass-fhir" in captured.out


def test_run_suite_writes_suite_artifacts(
    suite_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MultiPassFHIRPipeline, "extract", _stub_extract)
    suite = load_suite(suite_file)

    result = run_suite(suite, root=tmp_path / "pdf-lab")

    assert len(result.cells) == 1
    assert result.cells[0].status == "succeeded"
    assert result.cells[0].fact_count == 1
    assert (result.suite_dir / "suite.json").exists()
    cells = json.loads((result.suite_dir / "cells.json").read_text())
    assert cells[0]["pipeline"] == "multipass-fhir"
    assert (result.suite_dir / "report.md").exists()
