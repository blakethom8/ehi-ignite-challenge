"""PDF Lab — agent-first CLI for running pipelines, capturing traces,
comparing runs, and generating markdown reports.

See `.claude/pdf-lab-cli-queue.md` for the full build plan.
"""

from lib.extract.lab.bundle_shape import BundleShapeReport, score_bundle_shape
from lib.extract.lab.compare import (
    FactSample,
    RunComparison,
    compare_runs,
)
from lib.extract.lab.recorder import (
    DEFAULT_LAB_ROOT,
    RunManifest,
    RunRecorder,
    TraceEntry,
)

__all__ = [
    "BundleShapeReport",
    "DEFAULT_LAB_ROOT",
    "FactSample",
    "RunComparison",
    "RunManifest",
    "RunRecorder",
    "TraceEntry",
    "compare_runs",
    "score_bundle_shape",
]
