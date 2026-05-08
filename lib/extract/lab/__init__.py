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
from lib.extract.lab.eval_against_gt import (
    GroundTruthEvalResult,
    ResourceTypeScore,
    score_against_ground_truth,
)
from lib.extract.lab.ground_truth import (
    GroundTruthVersion,
    GroundTruthMeta,
    save_ground_truth,
    load_latest_ground_truth,
    load_ground_truth_version,
    list_ground_truth_versions,
    has_ground_truth,
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
    "GroundTruthEvalResult",
    "GroundTruthMeta",
    "GroundTruthVersion",
    "ResourceTypeScore",
    "RunComparison",
    "RunManifest",
    "RunRecorder",
    "TraceEntry",
    "compare_runs",
    "has_ground_truth",
    "list_ground_truth_versions",
    "load_ground_truth_version",
    "load_latest_ground_truth",
    "save_ground_truth",
    "score_against_ground_truth",
    "score_bundle_shape",
]
