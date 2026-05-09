"""Local MedGemma/Ollama PDF → FHIR extraction pipeline.

This is intentionally a net-new local-model pipeline rather than a patch on the
existing cloud-vision stack. It gives us a clean place to benchmark MedGemma 4B
running through Ollama against the existing Claude/Gemini PDF pipelines.

Current scope
-------------
- Input: PDF path.
- Preprocess: rasterize pages to PNG images locally.
- Model: call Ollama's local HTTP API with ``medgemma:4b`` and page images.
- Output: FHIR R4 Bundle containing candidate Observation resources.

Why labs first?
---------------
Lab PDFs are the cleanest first MedGemma benchmark: tabular, bounded, easy to
score, and directly relevant to the EHI harmonization story. Conditions,
medications, allergies, and notes can become additional focused passes after we
measure the local model on observations.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pypdfium2 as pdfium
from pydantic import BaseModel, Field, ValidationError

from lib.extract.pipelines.base import PipelineMetadata, register

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "medgemma:4b"
DEFAULT_DPI = 144
PROMPT_VERSION = "medgemma-ollama-lab-v0.1.0"
FHIR_EXT_BASE = "https://ehi-atlas.example/fhir/StructureDefinition"


class MedGemmaLabObservation(BaseModel):
    """One lab/vital observation extracted from a PDF page."""

    test_name: str = Field(description="Printed test/analyte name, e.g. Creatinine")
    value: str | None = Field(default=None, description="Printed result value as text")
    unit: str | None = Field(default=None, description="Printed unit, if present")
    reference_range: str | None = Field(default=None, description="Printed reference range")
    flag: str | None = Field(default=None, description="Printed abnormal flag: H, L, A, N, etc.")
    effective_date: str | None = Field(default=None, description="YYYY-MM-DD if visible or inferable from document context")
    loinc_code: str | None = Field(default=None, description="LOINC only if explicitly printed or very high confidence")
    source_text: str | None = Field(default=None, description="Short exact source phrase/row text")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    page: int | None = Field(default=None, description="1-indexed source page")


class MedGemmaPageExtraction(BaseModel):
    """Structured JSON expected from one MedGemma page call."""

    document_type: str | None = None
    patient_name: str | None = None
    patient_dob: str | None = None
    facility_name: str | None = None
    report_date: str | None = None
    observations: list[MedGemmaLabObservation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class OllamaResponseStats:
    total_duration_s: float | None = None
    load_duration_s: float | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration_s: float | None = None
    eval_count: int | None = None
    eval_duration_s: float | None = None

    @property
    def tokens_per_second(self) -> float | None:
        if not self.eval_count or not self.eval_duration_s or self.eval_duration_s <= 0:
            return None
        return self.eval_count / self.eval_duration_s


@dataclass(frozen=True)
class PageResult:
    page: int
    extraction: MedGemmaPageExtraction
    raw_response: str
    stats: OllamaResponseStats


class OllamaMedGemmaClient:
    """Small Ollama HTTP client for local vision extraction."""

    def __init__(
        self,
        *,
        host: str = DEFAULT_OLLAMA_HOST,
        model: str = DEFAULT_MODEL,
        timeout_s: int = 180,
        temperature: float = 0.0,
        num_ctx: int = 8192,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.num_ctx = num_ctx

    def extract_page(self, *, image_b64: str, page: int) -> PageResult:
        prompt = _page_prompt(page)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:  # pragma: no cover - depends on local daemon
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}. Start it with `ollama serve`."
            ) from exc

        text = str(data.get("response") or "")
        parsed = _parse_page_response(text, page=page)
        return PageResult(
            page=page,
            extraction=parsed,
            raw_response=text,
            stats=_stats_from_ollama(data),
        )


def _stats_from_ollama(data: dict[str, Any]) -> OllamaResponseStats:
    # Ollama durations are nanoseconds.
    def ns_to_s(value: Any) -> float | None:
        if isinstance(value, (int, float)) and value > 0:
            return float(value) / 1_000_000_000
        return None

    return OllamaResponseStats(
        total_duration_s=ns_to_s(data.get("total_duration")),
        load_duration_s=ns_to_s(data.get("load_duration")),
        prompt_eval_count=data.get("prompt_eval_count"),
        prompt_eval_duration_s=ns_to_s(data.get("prompt_eval_duration")),
        eval_count=data.get("eval_count"),
        eval_duration_s=ns_to_s(data.get("eval_duration")),
    )


def _page_prompt(page: int) -> str:
    return f"""
You are extracting structured clinical data from page {page} of a medical PDF.
Return ONLY valid JSON. No markdown. No prose.

Task: extract visible lab results / vital signs from this page image.

Rules:
- Extract only values visibly supported by the page.
- Do not invent missing values.
- Use null when unknown.
- LOINC: only include if printed or extremely high confidence.
- Keep source_text short: exact row/phrase that supports the observation.
- confidence should reflect extraction confidence, not medical truth.

JSON shape:
{{
  "document_type": "lab-report | patient-summary | unknown | ...",
  "patient_name": string|null,
  "patient_dob": "YYYY-MM-DD"|null,
  "facility_name": string|null,
  "report_date": "YYYY-MM-DD"|null,
  "observations": [
    {{
      "test_name": string,
      "value": string|null,
      "unit": string|null,
      "reference_range": string|null,
      "flag": string|null,
      "effective_date": "YYYY-MM-DD"|null,
      "loinc_code": string|null,
      "source_text": string|null,
      "confidence": number,
      "page": {page}
    }}
  ],
  "notes": [string]
}}
""".strip()


def _parse_page_response(text: str, *, page: int) -> MedGemmaPageExtraction:
    obj = _extract_json_object(text)
    if obj is None:
        raise ValueError(f"MedGemma response for page {page} did not contain a JSON object: {text[:500]!r}")
    try:
        parsed = MedGemmaPageExtraction.model_validate(obj)
    except ValidationError as exc:
        raise ValueError(f"MedGemma JSON for page {page} failed schema validation: {exc}") from exc
    for observation in parsed.observations:
        if observation.page is None:
            observation.page = page
    return parsed


def _extract_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = candidate.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i, char in enumerate(candidate[start:], start=start):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(candidate[start : i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def pdf_pages_to_png_base64(pdf_path: Path, *, dpi: int = DEFAULT_DPI, max_pages: int | None = None) -> list[str]:
    """Rasterize PDF pages to base64 PNG strings for Ollama vision calls."""

    doc = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72
    pages: list[str] = []
    limit = len(doc) if max_pages is None else min(len(doc), max_pages)
    for idx in range(limit):
        page = doc[idx]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        pages.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    return pages


@register
class MedGemmaOllamaPipeline:
    """Net-new local MedGemma/Ollama lab-observation pipeline."""

    metadata = PipelineMetadata(
        name="medgemma-ollama",
        description=(
            "Local MedGemma 4B via Ollama. Rasterizes PDF pages, extracts lab/vital "
            "observations as strict JSON, and emits candidate FHIR Observations."
        ),
        architecture="local-vision",
        primary_backends=["ollama"],
        estimated_cost_per_pdf_usd=0.0,
    )

    def __init__(
        self,
        *,
        patient_id: str = "unknown",
        model: str | None = None,
        host: str | None = None,
        dpi: int = DEFAULT_DPI,
        max_pages: int | None = None,
        client: OllamaMedGemmaClient | None = None,
    ) -> None:
        self.patient_id = patient_id
        self.model = model or os.getenv("EHI_MEDGEMMA_MODEL", DEFAULT_MODEL)
        self.host = host or os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
        self.dpi = dpi
        self.max_pages = max_pages
        self.client = client or OllamaMedGemmaClient(host=self.host, model=self.model)

    def extract(
        self,
        pdf_path: Path,
        *,
        skip_cache: bool = False,
        recorder: Any | None = None,
    ) -> dict[str, Any]:
        # skip_cache is accepted for protocol compatibility. This first local
        # pipeline version intentionally does not cache yet; benchmark runs
        # should measure live local inference.
        del skip_cache
        started = time.perf_counter()
        try:
            images = pdf_pages_to_png_base64(pdf_path, dpi=self.dpi, max_pages=self.max_pages)
            page_results = [
                self.client.extract_page(image_b64=image_b64, page=i)
                for i, image_b64 in enumerate(images, start=1)
            ]
            elapsed_s = time.perf_counter() - started
            bundle = _page_results_to_bundle(
                page_results,
                patient_id=self.patient_id,
                pdf_path=pdf_path,
                model=self.model,
                elapsed_s=elapsed_s,
                dpi=self.dpi,
            )
            if recorder is not None:
                extraction = {
                    "pages": [
                        {
                            "page": result.page,
                            "extraction": result.extraction.model_dump(),
                            "stats": {
                                "eval_count": result.stats.eval_count,
                                "eval_duration_s": result.stats.eval_duration_s,
                                "tokens_per_second": result.stats.tokens_per_second,
                            },
                        }
                        for result in page_results
                    ]
                }
                recorder.log_pass(
                    pass_name="medgemma_ollama_pages",
                    prompt=_page_prompt(1),
                    response=extraction,
                    usage={
                        "input_tokens": 0,
                        "output_tokens": sum(result.stats.eval_count or 0 for result in page_results),
                        "latency_ms": int(elapsed_s * 1000),
                        "cost_usd": 0.0,
                        "estimated": False,
                    },
                    extraction=extraction,
                )
                recorder.finish(bundle=bundle)
            return bundle
        except Exception as exc:
            if recorder is not None:
                recorder.finish(bundle={}, status="failed", error=str(exc))
            raise


def _page_results_to_bundle(
    page_results: Iterable[PageResult],
    *,
    patient_id: str,
    pdf_path: Path,
    model: str,
    elapsed_s: float,
    dpi: int,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    stats: list[dict[str, Any]] = []
    for page_result in page_results:
        stats.append(
            {
                "page": page_result.page,
                "eval_count": page_result.stats.eval_count,
                "eval_duration_s": page_result.stats.eval_duration_s,
                "tokens_per_second": page_result.stats.tokens_per_second,
            }
        )
        for idx, observation in enumerate(page_result.extraction.observations, start=1):
            entries.append(
                {
                    "resource": _observation_to_fhir(
                        observation,
                        patient_id=patient_id,
                        source_attachment_id=pdf_path.stem,
                        model=model,
                        ordinal=len(entries) + idx,
                    )
                }
            )

    return {
        "resourceType": "Bundle",
        "type": "document",
        "entry": entries,
        "meta": {
            "source": f"file://{pdf_path.name}",
            "extension": [
                {"url": f"{FHIR_EXT_BASE}/extraction-pipeline", "valueString": MedGemmaOllamaPipeline.metadata.name},
                {"url": f"{FHIR_EXT_BASE}/extraction-model", "valueString": f"ollama/{model}"},
                {"url": f"{FHIR_EXT_BASE}/extraction-prompt-version", "valueString": PROMPT_VERSION},
                {"url": f"{FHIR_EXT_BASE}/local-inference", "valueBoolean": True},
                {"url": f"{FHIR_EXT_BASE}/raster-dpi", "valueInteger": dpi},
                {"url": f"{FHIR_EXT_BASE}/elapsed-seconds", "valueDecimal": round(elapsed_s, 3)},
                {"url": f"{FHIR_EXT_BASE}/ollama-page-stats", "valueString": json.dumps(stats)},
            ],
        },
    }


def _observation_to_fhir(
    obs: MedGemmaLabObservation,
    *,
    patient_id: str,
    source_attachment_id: str,
    model: str,
    ordinal: int,
) -> dict[str, Any]:
    resource_id = _stable_id(source_attachment_id, obs, ordinal)
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": {"text": obs.test_name},
        "meta": {
            "source": f"extracted://{source_attachment_id}",
            "extension": [
                {"url": f"{FHIR_EXT_BASE}/extraction-pipeline", "valueString": MedGemmaOllamaPipeline.metadata.name},
                {"url": f"{FHIR_EXT_BASE}/extraction-model", "valueString": f"ollama/{model}"},
                {"url": f"{FHIR_EXT_BASE}/extraction-confidence", "valueDecimal": obs.confidence},
                {"url": f"{FHIR_EXT_BASE}/source-locator", "valueString": f"page={obs.page or ''};text={obs.source_text or obs.test_name}"},
            ],
        },
    }
    if obs.loinc_code:
        resource["code"]["coding"] = [
            {
                "system": "http://loinc.org",
                "code": obs.loinc_code,
                "display": obs.test_name,
            }
        ]
    if obs.effective_date:
        resource["effectiveDateTime"] = obs.effective_date
    if obs.value is not None:
        numeric_value = _to_float(obs.value)
        if numeric_value is not None:
            resource["valueQuantity"] = {"value": numeric_value}
            if obs.unit:
                resource["valueQuantity"]["unit"] = obs.unit
        else:
            resource["valueString"] = obs.value
    if obs.reference_range:
        resource["referenceRange"] = [{"text": obs.reference_range}]
    if obs.flag:
        resource["interpretation"] = [{"text": obs.flag}]
    return resource


def _to_float(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _stable_id(source_attachment_id: str, obs: MedGemmaLabObservation, ordinal: int) -> str:
    raw = f"{source_attachment_id}|{obs.page}|{obs.test_name}|{obs.value}|{ordinal}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")[:56]
    return f"medgemma-{slug or ordinal}"
