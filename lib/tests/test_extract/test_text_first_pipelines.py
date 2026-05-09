from pathlib import Path

from lib.extract.pipelines import get, list_pipelines
from lib.extract.pipelines.text_first import (
    PdfPlumberLabTextPipeline,
    TextPage,
    extract_lab_observations_from_text_pages,
)


def test_text_first_pipelines_registered() -> None:
    names = {meta.name for meta in list_pipelines()}

    assert "pdfplumber-lab-text" in names
    assert "pdfplumber-text-fhir" in names
    assert get("pdfplumber-lab-text") is PdfPlumberLabTextPipeline


def test_extract_lab_observations_from_text_pages() -> None:
    extraction = extract_lab_observations_from_text_pages(
        [
            TextPage(
                page=1,
                text=(
                    "Collected 09/12/2025\n"
                    "Creatinine 1.4 mg/dL 0.70-1.30 H\n"
                    "Glucose 91 mg/dL 70-99 N\n"
                    "Reference Range not a result\n"
                ),
            )
        ]
    )

    assert len(extraction.observations) == 2
    creatinine = extraction.observations[0]
    assert creatinine.test_name == "Creatinine"
    assert creatinine.value_quantity == 1.4
    assert creatinine.unit == "mg/dL"
    assert creatinine.reference_range_low == 0.70
    assert creatinine.reference_range_high == 1.30
    assert creatinine.flag == "H"
    assert creatinine.effective_date == "2025-09-12"
    assert creatinine.page == 1


def test_pdfplumber_lab_text_pipeline_bundle(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "lab.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        "lib.extract.pipelines.text_first.extract_pdf_text_pages",
        lambda _path: [
            TextPage(
                page=1,
                text="Collected 09/12/2025\nCreatinine 1.4 mg/dL 0.70-1.30 H",
            )
        ],
    )
    monkeypatch.setattr(PdfPlumberLabTextPipeline, "_safe_extract_layout", lambda self, _path: None)

    bundle = PdfPlumberLabTextPipeline(patient_id="test-patient").extract(pdf_path)

    assert bundle["resourceType"] == "Bundle"
    assert bundle["meta"]["extension"][0]["valueString"] == "pdfplumber-lab-text"
    resources = [entry["resource"] for entry in bundle["entry"]]
    assert [resource["resourceType"] for resource in resources] == ["Observation"]
    obs = resources[0]
    assert obs["subject"]["reference"] == "Patient/test-patient"
    assert obs["code"]["text"] == "Creatinine"
    assert obs["valueQuantity"]["value"] == 1.4
