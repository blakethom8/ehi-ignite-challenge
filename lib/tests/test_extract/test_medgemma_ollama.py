from pathlib import Path

from lib.extract.pipelines.medgemma_ollama import (
    MedGemmaOllamaPipeline,
    MedGemmaPageExtraction,
    MedGemmaLabObservation,
    OllamaResponseStats,
    PageResult,
    _extract_json_object,
)


class FakeClient:
    def extract_page(self, *, image_b64: str, page: int) -> PageResult:
        extraction = MedGemmaPageExtraction(
            document_type="lab-report",
            observations=[
                MedGemmaLabObservation(
                    test_name="Creatinine",
                    value="1.4",
                    unit="mg/dL",
                    reference_range="0.70-1.30",
                    flag="H",
                    effective_date="2025-09-12",
                    source_text="Creatinine 1.4 mg/dL H",
                    confidence=0.91,
                    page=page,
                )
            ],
        )
        return PageResult(page=page, extraction=extraction, raw_response="{}", stats=OllamaResponseStats(eval_count=10, eval_duration_s=0.5))


def test_extract_json_object_strips_markdown():
    assert _extract_json_object('```json\n{"observations": []}\n```') == {"observations": []}


def test_fake_client_bundle_shape(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(
        "lib.extract.pipelines.medgemma_ollama.pdf_pages_to_png_base64",
        lambda *args, **kwargs: ["fake-image"],
    )
    bundle = MedGemmaOllamaPipeline(client=FakeClient(), patient_id="test-patient").extract(pdf_path)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["entry"][0]["resource"]["resourceType"] == "Observation"
    assert bundle["entry"][0]["resource"]["subject"]["reference"] == "Patient/test-patient"
    assert bundle["entry"][0]["resource"]["valueQuantity"]["value"] == 1.4
