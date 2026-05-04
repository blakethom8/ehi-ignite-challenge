"""ExtractionPipeline contract — the Protocol every PDF→FHIR pipeline implements.

A pipeline is a black box: PDF in, FHIR Bundle out. Internal architecture
(single-pass vision, multi-pass vision, OCR-first, hybrid, anything else)
is opaque to the framework and to the eval harness. The contract is
intentionally minimal so external contributors can implement against a
stable interface.

Read :doc:`docs/architecture/PDF-PROCESSOR.md` decisions 5 and 6 for the
*why*. Read ``pipelines/README.md`` for *how to add one*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Type, runtime_checkable

# ---------------------------------------------------------------------------
# Pipeline metadata + Protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineMetadata:
    """Declarative description of a pipeline.

    Used by the bake-off harness for UI labels, by the eval harness for
    cost-attribution, and by external contributors for documentation.
    """

    name: str
    """Stable identifier. Lowercase, hyphenated. Used in cache keys, in
    Streamlit picker labels, and in markdown reports.
    Examples: ``"single-pass-vision"``, ``"multipass-fhir-claude"``."""

    description: str
    """One-line human-readable summary of what the pipeline does."""

    architecture: str
    """Short tag indicating the architecture family. Used to group
    pipelines in bake-off output. Suggested values:
    ``"single-pass-vision"``, ``"multipass-vision"``, ``"ocr-text"``,
    ``"hybrid"``."""

    primary_backends: list[str] = field(default_factory=list)
    """Backend identifiers this pipeline relies on (e.g. ``["anthropic"]``,
    ``["anthropic", "gemma-google-ai-studio"]``, ``["mineru-local",
    "anthropic"]``). Lets the bake-off page warn when a required backend
    is missing credentials."""

    estimated_cost_per_pdf_usd: float | None = None
    """Rough cost estimate for one extraction run, in USD. Optional —
    used in bake-off output for budget visibility. ``None`` means the
    pipeline hasn't been profiled yet."""


@runtime_checkable
class ExtractionPipeline(Protocol):
    """The contract every pipeline implements.

    Implementation requirements
    ---------------------------
    - ``metadata`` — class attribute or property. A :class:`PipelineMetadata`
      describing the pipeline.
    - ``extract(pdf_path: Path) -> dict`` — runs the pipeline. Returns a
      FHIR Bundle (R4 / US Core profiled) as a plain dict. Implementations
      should:
        * be idempotent for the same input PDF + same configuration
        * raise a descriptive exception on failure (not return ``None`` or ``{}``)
        * not mutate ``pdf_path`` or any sibling files
        * write any cache entries under their own subdirectory

    The framework does not impose:
    - Async vs sync (pick what fits the architecture)
    - Single LLM call vs many (multi-pass is welcome)
    - Where to cache (we recommend ``ehi_atlas/extract/.cache/<pipeline-name>/``)

    The framework does require:
    - The output Bundle validates against US Core profiles (validation
      happens at the bake-off boundary; pipelines that emit invalid
      Bundles fail before reaching the eval).
    - Each emitted resource carries ``meta.source`` and a
      ``meta.extension`` ``source-locator`` entry pointing back to the
      source PDF + (where applicable) bbox. Required for Provenance.
    """

    metadata: PipelineMetadata

    def extract(self, pdf_path: Path) -> dict[str, Any]:
        """Run the pipeline on ``pdf_path``, return a FHIR Bundle dict."""
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class PipelineRegistry:
    """In-memory store of registered pipeline classes.

    Pipelines register themselves at import time via the
    :func:`register` decorator. The registry is a singleton; the global
    ``_REGISTRY`` instance is what the module-level :func:`register`,
    :func:`get`, and :func:`list_pipelines` operate on.
    """

    def __init__(self) -> None:
        self._pipelines: dict[str, Type[ExtractionPipeline]] = {}

    def register(self, pipeline_cls: Type[ExtractionPipeline]) -> Type[ExtractionPipeline]:
        """Add a pipeline class to the registry. Idempotent on the same class."""
        meta = getattr(pipeline_cls, "metadata", None)
        if meta is None:
            raise ValueError(
                f"{pipeline_cls.__name__} cannot be registered: missing "
                f"`metadata` class attribute (must be a PipelineMetadata)."
            )
        if not isinstance(meta, PipelineMetadata):
            raise TypeError(
                f"{pipeline_cls.__name__}.metadata must be a PipelineMetadata, "
                f"got {type(meta).__name__}."
            )
        existing = self._pipelines.get(meta.name)
        if existing is not None and existing is not pipeline_cls:
            raise ValueError(
                f"Pipeline name conflict: {meta.name!r} is already registered "
                f"by {existing.__name__}; cannot also register {pipeline_cls.__name__}."
            )
        self._pipelines[meta.name] = pipeline_cls
        return pipeline_cls

    def get(self, name: str) -> Type[ExtractionPipeline]:
        """Return the pipeline class registered under ``name``.

        Raises :class:`KeyError` with the list of known names if not found.
        """
        try:
            return self._pipelines[name]
        except KeyError:
            known = ", ".join(sorted(self._pipelines.keys())) or "(none)"
            raise KeyError(
                f"No pipeline registered under {name!r}. Known: {known}"
            ) from None

    def list_pipelines(self) -> list[PipelineMetadata]:
        """Return metadata for every registered pipeline, sorted by name."""
        return [
            cls.metadata
            for _, cls in sorted(self._pipelines.items(), key=lambda kv: kv[0])
        ]


# Module-level singleton + thin function wrappers so callers can write
# ``from ehi_atlas.extract.pipelines import register, get, list_pipelines``.
_REGISTRY = PipelineRegistry()


def register(pipeline_cls: Type[ExtractionPipeline]) -> Type[ExtractionPipeline]:
    """Decorator: register a pipeline class with the global registry.

    Usage::

        from ehi_atlas.extract.pipelines import (
            ExtractionPipeline,
            PipelineMetadata,
            register,
        )

        @register
        class MyPipeline:
            metadata = PipelineMetadata(
                name="my-pipeline",
                description="Single-line description.",
                architecture="multipass-vision",
                primary_backends=["anthropic"],
            )

            def extract(self, pdf_path):
                ...
                return bundle_dict
    """
    return _REGISTRY.register(pipeline_cls)


def get(name: str) -> Type[ExtractionPipeline]:
    """Look up a pipeline class by its ``metadata.name``."""
    return _REGISTRY.get(name)


def list_pipelines() -> list[PipelineMetadata]:
    """Return :class:`PipelineMetadata` for every registered pipeline."""
    return _REGISTRY.list_pipelines()
