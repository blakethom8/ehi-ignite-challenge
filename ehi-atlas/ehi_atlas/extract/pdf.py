"""Vision-LLM PDF extraction wrapper.

Takes a PDF + Pydantic output schema, returns the validated extraction with
caching and Provenance metadata. Combines schemas (4.1), layout (4.2), and
cache (4.4) into the runtime extraction pipeline.

Determinism: same PDF + same prompt version + same schema version + same model
=> same cached output, no LLM call.

Backend abstraction
-------------------
Extraction is delegated to a pluggable :class:`VisionBackend`. The ``anthropic``
backend (Claude) is the only implementation today; the seam is in place for
adding a Gemma 4 backend (Google AI Studio / Ollama) without touching this
module's caller-facing API.

Backend selection precedence:
  1. ``backend=...`` kwarg (explicit override)
  2. ``api_client=...`` kwarg (back-compat: builds an AnthropicBackend with
     the supplied Anthropic SDK client — used by the test suite to inject mocks)
  3. ``EHI_VISION_BACKEND`` env var (e.g. ``"anthropic"``)
  4. Default: ``"anthropic"``

How callers invoke it
---------------------
The main entry point is :func:`extract_from_pdf`. For lab-report PDFs the
convenience wrapper :func:`extract_lab_pdf` is preferred::

    from pathlib import Path
    from ehi_atlas.extract.pdf import extract_lab_pdf

    result = extract_lab_pdf(Path("corpus/bronze/lab-pdf/rhett759/data.pdf"))
    print(result.document.results[0].test_name)   # "Creatinine"

Deterministic-replay guarantee
-------------------------------
Results are cached under ``ehi_atlas/extract/.cache/<sha256-digest>.json``.
The cache key covers four inputs: PDF bytes SHA-256, prompt version, schema
version, and a model identifier of the form ``"<backend>/<model>"``. Changing
the backend, the model, the prompt, or the schema all invalidate cache.

Tests do NOT make real API calls
---------------------------------
``tests/extract/test_pdf.py`` injects a mock Anthropic client via the
``api_client`` kwarg. No ``ANTHROPIC_API_KEY`` is required to run the suite.

Prompt and schema versioning policy
-------------------------------------
- ``DEFAULT_PROMPT_VERSION`` is frozen at **v0.1.0** for the Phase 1 showcase.
- ``DEFAULT_SCHEMA_VERSION`` is frozen at **extraction-result-v0.1.0**.
- Bump either when the corresponding artifact's content changes.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Protocol, Type, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

from ehi_atlas.extract.cache import CacheKey, ExtractionCache, hash_file
from ehi_atlas.extract.schemas import ExtractionResult

T = TypeVar("T", bound=BaseModel)

DEFAULT_BACKEND = "anthropic"
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_PROMPT_VERSION = "v0.1.0"
DEFAULT_SCHEMA_VERSION = "extraction-result-v0.1.0"


# ---------------------------------------------------------------------------
# System prompt — frozen at PROMPT_VERSION v0.1.0
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a medical document extraction assistant. Given a PDF
document, extract its clinical content into the structured schema provided.

Rules:
- For lab reports: extract every result row visible in the detailed-results
  table. Each result has a test name, a value, units, a reference range, and
  an optional flag (H/L/HH/LL/A/N).
- LOINC codes: only emit a LOINC code if you are confident it matches the test
  on the row. If unsure, emit null — never fabricate. The harmonizer will
  resolve unknown codes via terminology lookup.
- Bounding boxes: every extracted item carries a bbox indicating where on the
  PDF it was found. Use the page number (1-indexed) and the bbox coordinates
  in PDF user units, bottom-left origin convention.
- For clinical notes: extract structured Conditions and Symptoms — do not
  paraphrase. Each must include the source_text (the exact phrase from the note
  that justified the extraction).
- Confidence: emit an extraction_confidence between 0 and 1. Use ≤0.85 for any
  field you are uncertain about; the harmonizer will flag low-confidence facts
  for review."""


# ---------------------------------------------------------------------------
# Backend abstraction
# ---------------------------------------------------------------------------


class VisionBackend(Protocol):
    """Pluggable vision-extraction backend.

    Implementations must expose ``name`` and ``model`` attributes (used to
    build the cache key) and a single :meth:`extract` method that performs
    the actual model call.
    """

    name: str   # e.g. "anthropic", "gemma-google-ai-studio", "gemma-ollama"
    model: str  # e.g. "claude-opus-4-7", "gemma-4-4b-it"

    def extract(
        self,
        *,
        pdf_bytes: bytes,
        system_prompt: str,
        schema_json: dict[str, Any],
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Run extraction; return the structured tool-call input as a dict."""
        ...


class AnthropicBackend:
    """Claude vision-extraction backend.

    Uses the Anthropic Messages API with the ``emit_extraction`` tool to force
    structured output. The same response shape that worked before the backend
    refactor is preserved exactly.
    """

    name = "anthropic"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        client: Anthropic | None = None,
    ) -> None:
        self.model = model
        self._client = client

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            self._client = Anthropic()
        return self._client

    def extract(
        self,
        *,
        pdf_bytes: bytes,
        system_prompt: str,
        schema_json: dict[str, Any],
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=[
                {
                    "name": "emit_extraction",
                    "description": (
                        "Emit the validated extraction in the provided schema."
                    ),
                    "input_schema": schema_json,
                }
            ],
            tool_choice={"type": "tool", "name": "emit_extraction"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract this document into the schema. "
                                "Return only the structured tool call."
                            ),
                        },
                    ],
                }
            ],
        )

        tool_call = None
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                tool_call = block
                break

        if tool_call is None:
            content_types = [getattr(b, "type", None) for b in message.content]
            raise RuntimeError(
                f"Model did not emit the expected tool call 'emit_extraction'. "
                f"stop_reason={message.stop_reason!r}, "
                f"content block types={content_types}. "
                f"This usually means the model hit a content filter or the schema "
                f"was rejected. Try lowering max_tokens or simplifying the schema."
            )

        return tool_call.input  # already a dict from the SDK


def get_backend(
    name: str | None = None,
    *,
    model: str | None = None,
    client: Any = None,
) -> VisionBackend:
    """Resolve a :class:`VisionBackend` by name.

    Args:
        name: Backend identifier. Falls back to ``EHI_VISION_BACKEND`` env var,
            then to ``DEFAULT_BACKEND``.
        model: Model name override (passed to the backend).
        client: Backend-specific SDK client (e.g. ``Anthropic`` instance).
    """
    name = name or os.environ.get("EHI_VISION_BACKEND") or DEFAULT_BACKEND
    if name == "anthropic":
        return AnthropicBackend(
            model=model or DEFAULT_MODEL,
            client=client,
        )
    raise ValueError(
        f"Unknown vision backend: {name!r}. Known: 'anthropic'. "
        f"Phase 1 ships only the Anthropic backend; Gemma 4 (Google AI Studio "
        f"and Ollama) backends will be added in a follow-up commit."
    )


# ---------------------------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------------------------


def extract_from_pdf(
    pdf_path: Path,
    output_schema: Type[T] = ExtractionResult,  # type: ignore[assignment]
    *,
    backend: VisionBackend | None = None,
    model: str | None = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    cache: ExtractionCache | None = None,
    api_client: Anthropic | None = None,
    skip_cache: bool = False,
) -> T:
    """Extract structured content from a PDF using a vision-capable LLM.

    Args:
        pdf_path: Path to the PDF file.
        output_schema: The Pydantic output schema (default ``ExtractionResult``).
        backend: Explicit :class:`VisionBackend` override. If omitted, one is
            built from ``model`` / ``api_client`` / ``EHI_VISION_BACKEND``.
        model: Model name override (used only when ``backend`` is None).
        prompt_version: Bump to invalidate cached results.
        schema_version: Bump when ``output_schema``'s structure changes.
        cache: ``ExtractionCache`` instance (defaults to one in
            ``ehi_atlas/extract/.cache/``).
        api_client: Back-compat shortcut: a pre-built ``Anthropic`` client.
            Used by the test suite to inject mocks. When supplied (and
            ``backend`` is None), an ``AnthropicBackend`` is built around it.
        skip_cache: If ``True``, force a real API call and overwrite any
            existing cache entry.

    Returns:
        The validated Pydantic instance of type ``output_schema``.

    Raises:
        RuntimeError: If the model responds without emitting the required tool
            call (e.g. returns a text block instead of ``tool_use``).
    """
    cache = cache or ExtractionCache()

    if backend is None:
        backend = get_backend(model=model, client=api_client)

    file_hash = hash_file(pdf_path)
    cache_model_id = f"{backend.name}/{backend.model}"
    key = CacheKey(
        file_sha256=file_hash,
        prompt_version=prompt_version,
        schema_version=schema_version,
        model_name=cache_model_id,
    )

    if not skip_cache:
        cached = cache.get(key)
        if cached is not None:
            return output_schema.model_validate(cached)

    raw = backend.extract(
        pdf_bytes=pdf_path.read_bytes(),
        system_prompt=SYSTEM_PROMPT,
        schema_json=output_schema.model_json_schema(),
    )

    raw = _coerce_stringified_subobjects(raw)

    cache.put(key, raw)
    return output_schema.model_validate(raw)


# ---------------------------------------------------------------------------
# Response repair
# ---------------------------------------------------------------------------


def _coerce_stringified_subobjects(raw: dict[str, Any]) -> dict[str, Any]:
    """Repair a known Claude tool-call quirk.

    When the output schema uses a Pydantic discriminated union (e.g. our
    ``ExtractionResult.document``), Claude occasionally emits the chosen
    branch as a **stringified JSON** rather than a nested object — i.e.
    ``{"document": "{\\"document_type\\": \\"lab-report\\", ...}"}`` instead
    of ``{"document": {"document_type": "lab-report", ...}}``.

    This helper walks the top-level keys and parses any string value that
    looks like a JSON object/array. The transformation is intentionally
    shallow: deeply-nested stringified JSON is much rarer and we'd rather
    surface the validation error than silently coerce structure we don't
    understand.

    Returns a (possibly new) dict with stringified sub-objects parsed.
    """
    if not isinstance(raw, dict):
        return raw

    repaired: dict[str, Any] = {}
    for k, v in raw.items():
        if (
            isinstance(v, str)
            and len(v) > 1
            and v.lstrip().startswith(("{", "["))
        ):
            try:
                repaired[k] = json.loads(v)
                continue
            except (json.JSONDecodeError, ValueError):
                pass
        repaired[k] = v
    return repaired


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def extract_lab_pdf(pdf_path: Path, **kwargs) -> ExtractionResult:
    """Convenience wrapper for the lab-report extraction path.

    Equivalent to ``extract_from_pdf(pdf_path, ExtractionResult, **kwargs)``
    but typed to return ``ExtractionResult`` directly.
    """
    return extract_from_pdf(pdf_path, ExtractionResult, **kwargs)
