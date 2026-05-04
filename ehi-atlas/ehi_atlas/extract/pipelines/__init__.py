"""Pipeline registry for PDF → FHIR extraction architectures.

See ``docs/architecture/PDF-PROCESSOR.md`` for the architectural decision
record and ``ehi_atlas/extract/pipelines/README.md`` for the contributor
guide on how to implement a new pipeline.

Public API
----------
- :class:`ExtractionPipeline` — Protocol every pipeline implements
- :class:`PipelineMetadata` — declarative description of a pipeline
- :func:`register` — decorator that adds a pipeline class to the registry
- :func:`get` — look up a pipeline class by name
- :func:`list_pipelines` — enumerate registered pipelines

The registry is a plain in-memory dict — pipelines register themselves
at import time via the ``@register`` decorator. Importing a pipeline
module is enough to make it discoverable. To wire a new pipeline into
the bake-off harness, just import its module here (or via dynamic
discovery if we add it later).
"""

from __future__ import annotations

from .base import (
    ExtractionPipeline,
    PipelineMetadata,
    PipelineRegistry,
    get,
    list_pipelines,
    register,
)

__all__ = [
    "ExtractionPipeline",
    "PipelineMetadata",
    "PipelineRegistry",
    "get",
    "list_pipelines",
    "register",
]

# Import each shipped pipeline so its @register decorator runs.
# Adding a new pipeline = creating a new module here + adding an import below.
# (Dynamic discovery via entry_points is a Phase-2 polish item.)

from . import single_pass_vision  # noqa: F401  (K.2 — baseline)

# Pipelines will be registered as they land in K.4 / K.5:
# from . import multipass_fhir      # noqa: F401  (K.4)
# from . import ocr_then_extract    # noqa: F401  (K.5)
