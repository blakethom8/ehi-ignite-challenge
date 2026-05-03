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
import io
import json
import os
import urllib.error
import urllib.request
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

# Google AI Studio defaults — Gemma 4 31B is the flagship and the only Gemma 4
# variant on the hosted API that supports vision + responseSchema reliably.
DEFAULT_GOOGLE_MODEL = "gemma-4-31b-it"
GOOGLE_GEMMA_RASTER_DPI = 150


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


class GoogleAIStudioBackend:
    """Gemma 4 vision-extraction backend via Google AI Studio's hosted API.

    Three things differ from :class:`AnthropicBackend` and are encapsulated here:

    1. **Image input.** Gemini's API takes images per page, not whole PDFs.
       We rasterize via pypdfium2 (already a project dep) at 150 DPI and
       attach each page as ``inline_data``.
    2. **Structured output.** Gemma 4 is a "thinking" model; without a schema
       constraint it spends thousands of reasoning tokens before emitting
       prose. ``responseSchema`` (Gemini's structured-output mechanism)
       suppresses thinking entirely and yields valid JSON in ~500 tokens.
    3. **Schema dialect.** ``responseSchema`` is OpenAPI-3-subset, not full
       JSON Schema — it rejects ``$defs``, ``$ref``, and ``discriminator``.
       We translate the input schema via :func:`_pydantic_schema_to_gemini`
       before sending; the validation step downstream still uses the full
       Pydantic schema, so any schema drift surfaces there.

    Requires ``GOOGLE_API_KEY`` in the environment (or via ``api_key=`` arg).
    """

    name = "gemma-google-ai-studio"

    def __init__(
        self,
        model: str = DEFAULT_GOOGLE_MODEL,
        api_key: str | None = None,
        dpi: int = GOOGLE_GEMMA_RASTER_DPI,
    ) -> None:
        self.model = model
        self.dpi = dpi
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        key = self._api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise RuntimeError(
                "GoogleAIStudioBackend requires GOOGLE_API_KEY. Add it to "
                ".env (one-time) and dotenv-source before running, or pass "
                "api_key=... explicitly."
            )
        return key

    def extract(
        self,
        *,
        pdf_bytes: bytes,
        system_prompt: str,
        schema_json: dict[str, Any],
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        page_images = self._rasterize(pdf_bytes)

        gemini_schema = _pydantic_schema_to_gemini(schema_json)

        # Gemma uses Gemini's content-parts API. System prompt is concatenated
        # into the user message because Gemma doesn't honor systemInstruction.
        parts: list[dict[str, Any]] = [
            {
                "text": (
                    f"{system_prompt}\n\n"
                    "Extract this document into the structured schema. "
                    "Pages follow as separate images."
                )
            }
        ]
        for img_bytes in page_images:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.standard_b64encode(img_bytes).decode("utf-8"),
                    }
                }
            )

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "responseSchema": gemini_schema,
            },
        }

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_text = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Google AI Studio HTTP {e.code}: {err_text[:500]}"
            ) from e

        candidates = body.get("candidates", [])
        if not candidates:
            raise RuntimeError(
                f"Google AI Studio returned no candidates. "
                f"promptFeedback={body.get('promptFeedback')!r}"
            )

        text_parts = candidates[0].get("content", {}).get("parts", [])
        if not text_parts:
            raise RuntimeError(
                f"Google AI Studio response had no text parts. "
                f"finish_reason={candidates[0].get('finishReason')!r}"
            )

        text = text_parts[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Google AI Studio returned non-JSON text despite "
                f"responseMimeType=application/json. First 300 chars: "
                f"{text[:300]!r}"
            ) from e

    def _rasterize(self, pdf_bytes: bytes) -> list[bytes]:
        """Render each PDF page to PNG bytes via pypdfium2."""
        import pypdfium2 as pdfium  # lazy import — only Google backend needs it

        doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
        scale = self.dpi / 72.0
        out: list[bytes] = []
        for page in doc:
            pil = page.render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            out.append(buf.getvalue())
        return out


# ---------------------------------------------------------------------------
# Schema dialect translation: Pydantic JSON Schema → Gemini responseSchema
# ---------------------------------------------------------------------------


def _pydantic_schema_to_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Translate a Pydantic-emitted JSON Schema to Gemini's responseSchema dialect.

    Gemini's responseSchema is the OpenAPI 3 subset and rejects:
      - ``$defs`` / ``$ref`` (everything must be inlined)
      - ``discriminator`` / ``oneOf`` / ``anyOf`` with discriminator
        (no tagged unions; we collapse to the FIRST branch)
      - ``const`` (Pydantic emits this for ``Literal[...]`` fields; we
        translate to ``{type: string, enum: [<const>]}``)
      - JSON-Schema-only annotations: ``title``, ``examples``, ``default``,
        ``additionalProperties``

    For nullable fields (Pydantic emits ``"anyOf": [{"type": ...}, {"type": "null"}]``)
    we collapse to the non-null branch — Gemini doesn't have a clean
    "nullable" surface and the field can be absent in optional cases.

    Discriminated-union collapse picks the FIRST branch. For our use case
    (always lab-report) that's correct. If you add union variants later,
    pass the concrete branch's schema directly or extend this helper to
    thread a discriminator hint.

    The full Pydantic schema is still used for validation downstream, so
    schema drift between what Gemini sees and what we accept surfaces there.
    """
    defs: dict[str, Any] = schema.get("$defs", {})

    _UNSUPPORTED = {
        "$defs",
        "title",
        "examples",
        "default",
        "additionalProperties",
        "discriminator",
    }

    def _strip(node: Any) -> Any:
        if isinstance(node, dict):
            # Resolve $ref before doing anything else — it usually IS the node
            if "$ref" in node:
                ref = node["$ref"]
                if ref.startswith("#/$defs/"):
                    target = defs.get(ref.removeprefix("#/$defs/"))
                    if target is not None:
                        return _strip(target)
                node = {k: v for k, v in node.items() if k != "$ref"}

            # const (Pydantic emits for Literal[...]) → enum
            if "const" in node:
                const_value = node["const"]
                converted = {
                    "type": "string" if isinstance(const_value, str) else node.get("type", "string"),
                    "enum": [const_value],
                }
                # Carry through description if present
                if "description" in node:
                    converted["description"] = node["description"]
                return converted

            # Discriminated union: oneOf/anyOf + discriminator → first branch
            if ("oneOf" in node or "anyOf" in node) and "discriminator" in node:
                branches = node.get("oneOf") or node.get("anyOf") or []
                first = branches[0] if branches else {}
                return _strip(first)

            # anyOf used for nullable / Optional fields:
            # "anyOf": [{type: string}, {type: "null"}] → just the non-null branch
            if "anyOf" in node and not branches_are_concrete_alternatives(node["anyOf"]):
                non_null = [b for b in node["anyOf"] if b.get("type") != "null"]
                if len(non_null) == 1:
                    merged = {k: v for k, v in node.items() if k != "anyOf"}
                    merged.update(_strip(non_null[0]))
                    return merged

            # Plain oneOf/anyOf without discriminator: collapse to first
            for key in ("oneOf", "anyOf"):
                if key in node:
                    branches = node[key]
                    if branches:
                        return _strip(branches[0])

            cleaned = {
                k: _strip(v)
                for k, v in node.items()
                if k not in _UNSUPPORTED
            }

            # enum fixups for Gemini: must declare type=string and reject null
            if "enum" in cleaned:
                cleaned["enum"] = [v for v in cleaned["enum"] if v is not None]
                if not cleaned.get("type"):
                    cleaned["type"] = "string"

            return cleaned

        if isinstance(node, list):
            return [_strip(item) for item in node]

        return node

    return _strip(schema)


def branches_are_concrete_alternatives(branches: list[dict]) -> bool:
    """Return True if an anyOf list represents real alternatives (not just nullability).

    Pydantic emits ``"anyOf": [{type: T}, {type: "null"}]`` for ``Optional[T]``.
    That's a nullability marker, not a real union. Real alternative anyOfs
    (e.g. ``Union[A, B]`` without discriminator) should be treated differently.
    """
    if len(branches) <= 1:
        return False
    non_null = [b for b in branches if b.get("type") != "null"]
    return len(non_null) > 1


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
    if name == "gemma-google-ai-studio":
        return GoogleAIStudioBackend(
            model=model or DEFAULT_GOOGLE_MODEL,
            api_key=client if isinstance(client, str) else None,
        )
    raise ValueError(
        f"Unknown vision backend: {name!r}. "
        f"Known: 'anthropic', 'gemma-google-ai-studio'. "
        f"Local Ollama backend (gemma-ollama) is a future addition."
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
            # Apply coercions on read too — pre-fix cache entries pick up
            # the latest repair logic without requiring a re-extraction.
            cached = _coerce_stringified_subobjects(cached)
            cached = _unwrap_extraction_envelope(cached)
            return output_schema.model_validate(cached)

    raw = backend.extract(
        pdf_bytes=pdf_path.read_bytes(),
        system_prompt=SYSTEM_PROMPT,
        schema_json=output_schema.model_json_schema(),
    )

    raw = _coerce_stringified_subobjects(raw)
    raw = _unwrap_extraction_envelope(raw)

    # Trust the orchestrator over the model for these fields. Some models
    # (notably Gemma 4 via Google AI Studio) hallucinate the extraction_model
    # name into the output; we know which backend ran, so override.
    if isinstance(raw, dict):
        raw.setdefault("extraction_prompt_version", prompt_version)
        raw["extraction_model"] = cache_model_id

    cache.put(key, raw)
    return output_schema.model_validate(raw)


# ---------------------------------------------------------------------------
# Response repair
# ---------------------------------------------------------------------------


def _unwrap_extraction_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    """Repair an "extra envelope" Claude tool-call quirk.

    Some PDFs (observed first on a 15-page colon-cancer medical record) cause
    Claude to wrap its tool-call output in an extra ``{"extraction": {...}}``
    layer instead of returning the schema's top-level fields directly. The
    inner content is correct — every nested field is present and well-formed
    — but Pydantic's validator can't see ``document`` because it's one level
    deeper than the schema declares.

    If the dict has an ``"extraction"`` key whose value is itself a dict that
    *looks like* the real payload (i.e. contains ``"document"``), lift that
    inner dict's keys up to the top level. Sibling keys (e.g. orchestrator-
    injected ``extraction_model``) are preserved.
    """
    if not isinstance(raw, dict):
        return raw
    inner = raw.get("extraction")
    if not (isinstance(inner, dict) and "document" in inner):
        return raw
    others = {k: v for k, v in raw.items() if k != "extraction"}
    return {**inner, **others}


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
