"""PDF Lab — agent-first CLI for running pipelines, capturing traces,
comparing runs, and generating markdown reports.

See `.claude/pdf-lab-cli-queue.md` for the full build plan.
"""

from lib.extract.lab.recorder import (
    DEFAULT_LAB_ROOT,
    RunManifest,
    RunRecorder,
    TraceEntry,
)

__all__ = ["DEFAULT_LAB_ROOT", "RunManifest", "RunRecorder", "TraceEntry"]
