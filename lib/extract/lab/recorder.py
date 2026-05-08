"""RunRecorder — captures full per-run artifacts for the PDF Lab CLI.

After a pipeline runs against a PDF, RunRecorder has persisted everything
needed to:
  - Replay the run (raw prompts + responses)
  - Audit costs and latency per pass
  - Compute bundle-shape metrics (LAB-T05)
  - Diff vs another run (LAB-T04)
  - Generate a markdown report (LAB-T06)

Storage is plain JSON / text files under data/pdf-lab/runs/<run-id>/.
No database. No locking (one recorder per run dir). Atomic enough for
single-process use; the CLI is the single producer.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Literal


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LAB_ROOT = REPO_ROOT / "data" / "pdf-lab"

# Only alphanumeric, dash, and underscore are permitted in pass names.
_PASS_NAME_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON to path atomically: write to .tmp, then rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


@dataclass
class TraceEntry:
    """One pass's trace artifacts. Serialized to traces/<pass_name>/."""
    pass_name: str
    prompt: str
    response: dict
    usage: dict
    extraction: dict | None = None


@dataclass
class RunManifest:
    """Metadata for a single run. Serialized to manifest.json.

    Latency notes:
      - latency_ms reports WALL-CLOCK time from started_at → finished_at.
        Computed deterministically in finish(); reflects actual elapsed
        time including parallel pass dispatch.
      - sum_pass_latency_ms is the sum of per-pass latencies. Always >=
        latency_ms when passes ran in parallel; ratio (sum / wall) is
        the parallelism factor.
    """
    run_id: str
    pipeline_name: str
    pdf_path: str
    pdf_sha256: str
    ground_truth_path: str | None
    started_at: str
    finished_at: str | None = None
    cost_usd: float = 0.0
    latency_ms: int = 0  # wall-clock; populated by finish()
    sum_pass_latency_ms: int = 0  # sum of per-pass; accumulated in log_pass()
    status: Literal["running", "succeeded", "failed"] = "running"
    error: str | None = None


class RunRecorder:
    """Captures per-run artifacts to disk under
    {root}/runs/{run_id}/. Use RunRecorder.start() to construct;
    log_pass() during extraction; finish() at the end."""

    def __init__(self, manifest: RunManifest, root: Path) -> None:
        self._manifest = manifest
        self._root = root
        self._run_dir = root / "runs" / manifest.run_id

    @classmethod
    def start(
        cls,
        *,
        pipeline_name: str,
        pdf_path: Path,
        ground_truth_path: Path | None = None,
        root: Path | None = None,
    ) -> "RunRecorder":
        """Create a new run directory + initial manifest.json. Returns
        the recorder ready to receive log_pass calls."""
        effective_root = root if root is not None else DEFAULT_LAB_ROOT

        # 1. Compute SHA256 of the PDF
        pdf_bytes = pdf_path.read_bytes()
        sha = hashlib.sha256(pdf_bytes).hexdigest()[:6]

        # 2. Build run_id: {utc_iso}_{sha_prefix}_{pipeline_name}
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        run_id = f"{ts}_{sha}_{pipeline_name}"

        # 3. Create the run directory under {root}/runs/{run_id}/
        run_dir = effective_root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # 4. Copy the PDF to source.pdf
        shutil.copy2(pdf_path, run_dir / "source.pdf")

        # 5. Copy ground_truth_path to ground-truth.json if provided
        gt_path_str: str | None = None
        if ground_truth_path is not None:
            shutil.copy2(ground_truth_path, run_dir / "ground-truth.json")
            gt_path_str = str(ground_truth_path.resolve())

        # 6. Create traces/ subdirectory
        (run_dir / "traces").mkdir(exist_ok=True)

        # 7. Write manifest.json with status="running", started_at=utc-iso
        manifest = RunManifest(
            run_id=run_id,
            pipeline_name=pipeline_name,
            pdf_path=str(pdf_path.resolve()),
            pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            ground_truth_path=gt_path_str,
            started_at=datetime.datetime.utcnow().isoformat() + "Z",
            finished_at=None,
            cost_usd=0.0,
            latency_ms=0,
            status="running",
            error=None,
        )
        _atomic_write_json(run_dir / "manifest.json", asdict(manifest))

        # 8. Return RunRecorder(manifest, root)
        return cls(manifest, effective_root)

    def log_pass(
        self,
        *,
        pass_name: str,
        prompt: str,
        response: dict,
        usage: dict,
        extraction: dict | None = None,
    ) -> None:
        """Persist this pass's artifacts under traces/<pass_name>/. Update
        running cost / latency totals on manifest.json (rewritten atomically
        — write to .tmp, rename)."""
        # 1. Validate pass_name (alphanumeric + dash + underscore only)
        if not _PASS_NAME_RE.match(pass_name):
            raise ValueError(
                f"pass_name {pass_name!r} contains invalid characters. "
                "Only alphanumeric, dash (-), and underscore (_) are allowed."
            )

        # 2. mkdir traces/<pass_name>/
        trace_dir = self._run_dir / "traces" / pass_name
        trace_dir.mkdir(parents=True, exist_ok=True)

        # 3. Write prompt.txt, response.json, usage.json, extraction.json
        (trace_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        _atomic_write_json(trace_dir / "response.json", response)
        _atomic_write_json(trace_dir / "usage.json", usage)
        if extraction is not None:
            _atomic_write_json(trace_dir / "extraction.json", extraction)

        # 4. Update manifest.cost_usd += usage.get('cost_usd', 0)
        self._manifest.cost_usd += float(usage.get("cost_usd", 0))

        # 5. Accumulate per-pass latency separately. The headline `latency_ms`
        # is wall-clock (set in finish()); per-pass sum lives in
        # sum_pass_latency_ms so callers can compute the parallelism factor.
        self._manifest.sum_pass_latency_ms += int(usage.get("latency_ms", 0))

        # 6. Atomic rewrite of manifest.json
        _atomic_write_json(self._run_dir / "manifest.json", asdict(self._manifest))

    def finish(
        self,
        *,
        bundle: dict,
        eval_result: dict | None = None,
        bundle_shape: dict | None = None,
        status: Literal["succeeded", "failed"] = "succeeded",
        error: str | None = None,
    ) -> None:
        """Write bundle.json + eval.json (if provided) + bundle_shape.json
        (if provided), finalize manifest.json with finished_at, status,
        error. Append a single line to {root}/runs.jsonl with the final
        manifest."""
        # Guard against double-finish
        if self._manifest.status != "running":
            raise RuntimeError(
                f"finish() called on run {self._manifest.run_id!r} that is "
                f"already in status {self._manifest.status!r}. "
                "Each run may only be finished once."
            )

        # Write bundle.json
        _atomic_write_json(self._run_dir / "bundle.json", bundle)

        # Write eval.json if provided
        if eval_result is not None:
            _atomic_write_json(self._run_dir / "eval.json", eval_result)

        # Write bundle_shape.json if provided
        if bundle_shape is not None:
            _atomic_write_json(self._run_dir / "bundle_shape.json", bundle_shape)

        # Finalize manifest. latency_ms is wall-clock from started_at →
        # finished_at; sum_pass_latency_ms (already accumulated) stays
        # on the dataclass as the per-pass total for parallelism analysis.
        finished_at = datetime.datetime.utcnow()
        self._manifest.finished_at = finished_at.isoformat() + "Z"
        self._manifest.status = status
        self._manifest.error = error
        try:
            started_at = datetime.datetime.fromisoformat(
                self._manifest.started_at.replace("Z", "")
            )
            wall_clock_ms = int((finished_at - started_at).total_seconds() * 1000)
            self._manifest.latency_ms = max(wall_clock_ms, 0)
        except (ValueError, AttributeError):
            # Fallback: keep latency_ms at whatever it was
            pass
        _atomic_write_json(self._run_dir / "manifest.json", asdict(self._manifest))

        # Append a single line to {root}/runs.jsonl
        runs_jsonl = self._root / "runs.jsonl"
        with runs_jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(self._manifest), default=str) + "\n")

    @property
    def run_id(self) -> str:
        return self._manifest.run_id

    @property
    def root(self) -> Path:
        return self._run_dir

    @property
    def manifest(self) -> RunManifest:
        return self._manifest
