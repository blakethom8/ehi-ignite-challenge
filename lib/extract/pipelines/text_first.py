"""Text-first PDF extraction pipelines.

These are additive workspace variants. They do not replace the vision
pipelines; they give the lab a way to compare "PDF -> raw text -> FHIR" lanes
against vision-direct lanes using the same Bundle output contract.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from lib.extract.pdf import AnthropicBackend, DEFAULT_MODEL
from lib.extract.pipelines.base import PipelineMetadata, register
from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    LabObservationEntry,
    LabObservationExtraction,
    MultiPassFHIRPipeline,
    _PASS_0_PROMPT,
    _PASSES,
)


@dataclass(frozen=True)
class TextPage:
    page: int
    text: str


def extract_pdf_text_pages(pdf_path: Path) -> list[TextPage]:
    """Extract page-level text with pdfplumber.

    This is intentionally thin: OCR/scanned-PDF support belongs in separate
    Marker/Docling/MinerU/Mistral variants. This baseline measures what we can
    get from the embedded text layer alone.
    """

    import pdfplumber

    pages: list[TextPage] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            pages.append(TextPage(page=idx, text=text))
    return pages


def _pages_to_prompt_text(pages: list[TextPage], *, max_chars: int = 120_000) -> str:
    chunks: list[str] = []
    total = 0
    for page in pages:
        block = f"\n\n--- PAGE {page.page} ---\n{page.text.strip()}"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                chunks.append(block[:remaining] + "\n[TRUNCATED]")
            break
        chunks.append(block)
        total += len(block)
    return "".join(chunks).strip()


_DATE_RE = re.compile(r"\b(?P<m>\d{1,2})[/-](?P<d>\d{1,2})[/-](?P<y>\d{2,4})\b")
_RANGE_RE = re.compile(
    r"(?P<low>[<>]?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(?P<high>\d+(?:\.\d+)?)"
)
_RESULT_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 /(),.'%+#-]{2,80}?)\s+"
    r"(?P<value>[<>]?\d+(?:\.\d+)?|negative|positive|detected|not detected|"
    r"nonreactive|reactive|normal|abnormal)\b"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
_FLAG_RE = re.compile(r"\b(HH|LL|H|L|A|N)\b")
_UNIT_RE = re.compile(r"\b(mg/dL|g/dL|ng/mL|pg/mL|mIU/L|uIU/mL|IU/L|U/L|mmol/L|mmol/mol|%|K/uL|10\^3/uL|x10E3/uL|cells/uL)\b", re.IGNORECASE)


def _normalize_date(raw: str) -> str | None:
    match = _DATE_RE.search(raw)
    if not match:
        return None
    month = int(match.group("m"))
    day = int(match.group("d"))
    year_raw = match.group("y")
    year = int(year_raw)
    if year < 100:
        year += 2000 if year < 70 else 1900
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_range(text: str) -> tuple[float | None, float | None]:
    match = _RANGE_RE.search(text)
    if not match:
        return None, None
    try:
        low = float(match.group("low").lstrip("<>"))
        high = float(match.group("high"))
    except ValueError:
        return None, None
    return low, high


def _line_to_lab_observation(line: str, *, page: int, effective_date: str | None) -> LabObservationEntry | None:
    cleaned = " ".join(line.replace("\t", " ").split())
    if not cleaned or len(cleaned) < 6:
        return None
    if cleaned.lower().startswith(
        (
            "page ",
            "reference range",
            "result ",
            "test name",
            "collected ",
            "reported ",
            "received ",
            "date ",
            "dob ",
        )
    ):
        return None
    lowered = cleaned.lower()
    if any(token in lowered for token in (" void", "voided", "released in error", "do not use", "preliminary")):
        return None
    if lowered.startswith(("the ", "use the ", "important ")):
        return None

    match = _RESULT_RE.match(cleaned)
    if not match:
        return None

    name = match.group("name").strip(" :-")
    value = match.group("value").strip()
    tail = match.group("tail") or ""
    if len(name.split()) > 8 or len(name) < 3:
        return None

    unit_match = _UNIT_RE.search(tail)
    flag_match = _FLAG_RE.search(tail)
    low, high = _parse_range(tail)

    value_quantity: float | None = None
    value_string: str | None = None
    try:
        value_quantity = float(value.lstrip("<>"))
    except ValueError:
        value_string = value

    flag = flag_match.group(1).upper() if flag_match else None
    if flag not in {"H", "L", "N", "HH", "LL", "A", None}:
        flag = None

    return LabObservationEntry(
        test_name=name,
        value_quantity=value_quantity,
        value_string=value_string,
        unit=unit_match.group(1) if unit_match else None,
        reference_range_low=low,
        reference_range_high=high,
        flag=flag,  # type: ignore[arg-type]
        effective_date=effective_date,
        page=page,
    )


def extract_lab_observations_from_text_pages(pages: list[TextPage]) -> LabObservationExtraction:
    """Deterministic text-layer lab extractor.

    This is deliberately simple. It gives the workspace a cheap baseline and
    helps identify whether failures are due to raw-text quality or LLM/FHIR
    mapping quality.
    """

    observations: list[LabObservationEntry] = []
    seen: set[tuple[int, str, str | float | None]] = set()
    document_date = None
    skip_voided_block = False
    for page in pages:
        if document_date is None:
            document_date = _normalize_date(page.text)
        for line in page.text.splitlines():
            line_lower = line.lower()
            if "voided preliminary values" in line_lower:
                skip_voided_block = True
                continue
            if skip_voided_block and line_lower.startswith("electronically signed"):
                skip_voided_block = False
                continue
            if skip_voided_block:
                continue
            obs = _line_to_lab_observation(line, page=page.page, effective_date=document_date)
            if obs is None:
                continue
            key = (obs.page or 0, obs.test_name.lower(), obs.value_quantity if obs.value_quantity is not None else obs.value_string)
            if key in seen:
                continue
            seen.add(key)
            observations.append(obs)
    return LabObservationExtraction(observations=observations)


@register
class PdfPlumberLabTextPipeline(MultiPassFHIRPipeline):
    """No-LLM text-layer lab baseline.

    PDF -> pdfplumber text -> deterministic lab-row regex -> FHIR Observation
    Bundle. Useful for fast local comparison and for separating raw text
    extraction failures from model extraction failures.
    """

    metadata = PipelineMetadata(
        name="pdfplumber-lab-text",
        description=(
            "No-LLM baseline. Extracts embedded PDF text with pdfplumber, "
            "parses likely lab rows deterministically, and emits FHIR Observations."
        ),
        architecture="ocr-text",
        primary_backends=["pdfplumber"],
        estimated_cost_per_pdf_usd=0.0,
    )

    def __init__(self, *, patient_id: str = "unknown") -> None:
        super().__init__(
            patient_id=patient_id,
            backend_name="pdfplumber-text",
            model="deterministic-lab-regex",
            max_workers=1,
        )

    def extract(
        self,
        pdf_path: Path,
        *,
        skip_cache: bool = False,
        recorder: Any | None = None,
    ) -> dict[str, Any]:
        del skip_cache
        pages = extract_pdf_text_pages(pdf_path)
        lab_extraction = extract_lab_observations_from_text_pages(pages)
        doc_context = DocumentContext(
            document_type="lab-report",
            patient_name=None,
            patient_dob=None,
            encounter_date=lab_extraction.observations[0].effective_date if lab_extraction.observations else None,
            ordering_provider=None,
            facility_name=None,
        )
        layout = self._safe_extract_layout(pdf_path)
        bundle = self._merge_to_bundle(
            doc_context=doc_context,
            per_pass={"lab_observations": lab_extraction},
            pdf_path=pdf_path,
            layout=layout,
        )
        _set_bundle_pipeline_name(bundle, self.metadata.name)
        if recorder is not None:
            recorder.log_pass(
                pass_name="pdfplumber_text_labs",
                prompt="deterministic pdfplumber text lab-row extraction",
                response=lab_extraction.model_dump(),
                usage={"input_tokens": 0, "output_tokens": 0, "latency_ms": 0, "cost_usd": 0.0, "estimated": True},
                extraction=lab_extraction.model_dump(),
            )
            recorder.finish(bundle=bundle)
        return bundle


@register
class PdfPlumberTextFHIRPipeline(MultiPassFHIRPipeline):
    """Text-first LLM variant over the existing multipass FHIR schemas.

    PDF -> pdfplumber page text -> Anthropic text-only structured calls per
    resource pass -> normal multipass FHIR merger. This tests whether raw text
    plus focused schemas can compete with vision-direct extraction on
    digitally-born PDFs.
    """

    metadata = PipelineMetadata(
        name="pdfplumber-text-fhir",
        description=(
            "Text-first multipass variant. Uses pdfplumber page text instead "
            "of page images, then runs the same resource-specific FHIR schemas."
        ),
        architecture="ocr-text",
        primary_backends=["pdfplumber", "anthropic"],
        estimated_cost_per_pdf_usd=0.18,
    )

    def __init__(
        self,
        *,
        patient_id: str = "unknown",
        model: str | None = None,
        max_workers: int = 6,
    ) -> None:
        super().__init__(
            patient_id=patient_id,
            backend_name="pdfplumber-text",
            model=model or os.environ.get("EHI_TEXT_EXTRACT_MODEL") or DEFAULT_MODEL,
            max_workers=max_workers,
        )
        self._text_backend = AnthropicBackend(model=self._model or DEFAULT_MODEL)

    def extract(
        self,
        pdf_path: Path,
        *,
        skip_cache: bool = False,
        recorder: Any | None = None,
    ) -> dict[str, Any]:
        # No cache yet: this is an experimental workspace lane. The Lab recorder
        # captures enough trace data to compare runs while we decide whether the
        # variant is worth hardening.
        del skip_cache
        pages = extract_pdf_text_pages(pdf_path)
        document_text = _pages_to_prompt_text(pages)
        if not document_text:
            raise RuntimeError("pdfplumber-text-fhir found no embedded text; use a real OCR variant for scanned PDFs.")

        doc_context = self._call_text_schema(
            system_prompt=_PASS_0_PROMPT,
            user_prompt=_text_user_prompt(document_text),
            schema=DocumentContext,
        )
        context_suffix = (
            f"\n\n--- DOCUMENT CONTEXT ---\n"
            f"document_type: {doc_context.document_type}\n"
            f"patient_name: {doc_context.patient_name}\n"
            f"patient_dob: {doc_context.patient_dob}\n"
            f"encounter_date: {doc_context.encounter_date}\n"
            f"ordering_provider: {doc_context.ordering_provider}\n"
            f"facility_name: {doc_context.facility_name}\n"
            f"--- end context ---"
        )

        per_pass_outputs: dict[str, BaseModel] = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(
                    self._call_text_schema,
                    system_prompt=p.system_prompt + context_suffix,
                    user_prompt=_text_user_prompt(document_text),
                    schema=p.schema,
                ): p
                for p in _PASSES
            }
            for future in as_completed(futures):
                p = futures[future]
                try:
                    per_pass_outputs[p.name] = future.result()
                except Exception as exc:
                    per_pass_outputs[p.name] = p.schema()
                    print(f"[pdfplumber-text-fhir] pass {p.name!r} failed: {type(exc).__name__}: {exc}")

        layout = self._safe_extract_layout(pdf_path)
        bundle = self._merge_to_bundle(
            doc_context=doc_context,
            per_pass=per_pass_outputs,
            pdf_path=pdf_path,
            layout=layout,
        )
        _set_bundle_pipeline_name(bundle, self.metadata.name)
        if recorder is not None:
            recorder.finish(bundle=bundle)
        return bundle

    def _call_text_schema(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        return self._text_backend.call_with_schema(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            max_tokens=8192,
        )


def _text_user_prompt(document_text: str) -> str:
    return (
        "Extract from this text transcription of a medical PDF. Page markers "
        "are included as '--- PAGE N ---'. Preserve page numbers on extracted "
        "facts when the source text supports them.\n\n"
        f"{document_text}"
    )


def _set_bundle_pipeline_name(bundle: dict[str, Any], pipeline_name: str) -> None:
    for ext in bundle.get("meta", {}).get("extension", []):
        if ext.get("url") == "https://ehi-atlas.example/fhir/StructureDefinition/extraction-pipeline":
            ext["valueString"] = pipeline_name
