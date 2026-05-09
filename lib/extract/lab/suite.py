"""Experiment-suite support for the PDF Lab.

The Lab's `run` command is good for one-off work. Suites are for the next
phase: dozens of additive pipelines, repeated document sets, and stable review
artifacts that let us see whether extraction and harmonization are improving.
"""

from __future__ import annotations

import datetime
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lib.extract.lab.bundle_shape import score_bundle_shape
from lib.extract.lab.ground_truth import load_latest_ground_truth
from lib.extract.lab.recorder import DEFAULT_LAB_ROOT, REPO_ROOT, RunRecorder
from lib.extract.pipelines import get as get_pipeline


@dataclass(frozen=True)
class SuiteCase:
    label: str
    pdf: Path
    ground_truth: Path | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LabSuite:
    name: str
    description: str
    pipelines: list[str]
    cases: list[SuiteCase]
    skip_cache: bool = False


@dataclass(frozen=True)
class SuiteCellResult:
    pipeline: str
    case_label: str
    pdf: str
    ground_truth: str | None
    status: str
    run_id: str | None
    latency_s: float
    fact_count: int = 0
    resource_counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SuiteRunResult:
    suite_name: str
    suite_run_id: str
    root: Path
    cells: list[SuiteCellResult]

    @property
    def suite_dir(self) -> Path:
        return self.root / "suites" / self.suite_run_id


def load_suite(path: Path) -> LabSuite:
    """Load a YAML/JSON suite manifest."""

    raw = yaml.safe_load(path.read_text()) or {}
    base = path.parent

    def resolve(value: str | None) -> Path | None:
        if not value:
            return None
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
        if (base / candidate).exists():
            return (base / candidate).resolve()
        return (REPO_ROOT / candidate).resolve()

    cases: list[SuiteCase] = []
    for item in raw.get("cases", []):
        pdf = resolve(item.get("pdf"))
        if pdf is None:
            raise ValueError(f"suite case {item!r} is missing pdf")
        cases.append(
            SuiteCase(
                label=str(item.get("label") or pdf.stem),
                pdf=pdf,
                ground_truth=resolve(item.get("ground_truth")),
                tags=list(item.get("tags") or []),
            )
        )

    return LabSuite(
        name=str(raw.get("name") or path.stem),
        description=str(raw.get("description") or ""),
        pipelines=list(raw.get("pipelines") or []),
        cases=cases,
        skip_cache=bool(raw.get("settings", {}).get("skip_cache", False)),
    )


def validate_suite(suite: LabSuite) -> list[str]:
    """Return human-readable validation errors without running anything."""

    errors: list[str] = []
    if not suite.pipelines:
        errors.append("suite has no pipelines")
    if not suite.cases:
        errors.append("suite has no cases")

    for name in suite.pipelines:
        try:
            get_pipeline(name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"unknown pipeline {name!r}: {exc}")

    for case in suite.cases:
        if not case.pdf.exists():
            errors.append(f"case {case.label!r} PDF not found: {case.pdf}")
        if case.ground_truth is not None and not case.ground_truth.exists():
            errors.append(f"case {case.label!r} ground truth not found: {case.ground_truth}")

    return errors


def dry_run_plan(suite: LabSuite) -> list[dict[str, Any]]:
    """Return planned cells as plain dicts for CLI display/tests."""

    return [
        {
            "pipeline": pipeline,
            "case": case.label,
            "pdf": str(case.pdf),
            "ground_truth": str(case.ground_truth) if case.ground_truth else None,
            "tags": case.tags,
        }
        for pipeline in suite.pipelines
        for case in suite.cases
    ]


def run_suite(
    suite: LabSuite,
    *,
    root: Path | None = None,
    skip_cache: bool | None = None,
) -> SuiteRunResult:
    """Run every pipeline × case cell and persist a suite summary."""

    errors = validate_suite(suite)
    if errors:
        raise ValueError("; ".join(errors))

    lab_root = root or DEFAULT_LAB_ROOT
    effective_skip_cache = suite.skip_cache if skip_cache is None else skip_cache
    suite_run_id = _suite_run_id(suite.name)
    suite_dir = lab_root / "suites" / suite_run_id
    suite_dir.mkdir(parents=True, exist_ok=True)

    cells: list[SuiteCellResult] = []
    for pipeline_name in suite.pipelines:
        pipeline_cls = get_pipeline(pipeline_name)
        pipeline = pipeline_cls()
        for case in suite.cases:
            started = time.perf_counter()
            recorder = RunRecorder.start(
                pipeline_name=pipeline_name,
                pdf_path=case.pdf,
                ground_truth_path=case.ground_truth,
                root=lab_root,
            )
            try:
                try:
                    bundle = pipeline.extract(case.pdf, recorder=recorder, skip_cache=effective_skip_cache)  # type: ignore[call-arg]
                except TypeError:
                    bundle = pipeline.extract(case.pdf, recorder=recorder)  # type: ignore[call-arg]
                _write_shape_and_eval(
                    bundle=bundle if isinstance(bundle, dict) else {},
                    recorder=recorder,
                    ground_truth_path=case.ground_truth,
                )
                elapsed = time.perf_counter() - started
                cells.append(
                    SuiteCellResult(
                        pipeline=pipeline_name,
                        case_label=case.label,
                        pdf=str(case.pdf),
                        ground_truth=str(case.ground_truth) if case.ground_truth else None,
                        status="succeeded",
                        run_id=recorder.run_id,
                        latency_s=elapsed,
                        fact_count=len((bundle if isinstance(bundle, dict) else {}).get("entry", [])),
                        resource_counts=_resource_counts(bundle if isinstance(bundle, dict) else {}),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                try:
                    if recorder.manifest.status == "running":
                        recorder.finish(bundle={}, status="failed", error=str(exc))
                except Exception:
                    pass
                elapsed = time.perf_counter() - started
                cells.append(
                    SuiteCellResult(
                        pipeline=pipeline_name,
                        case_label=case.label,
                        pdf=str(case.pdf),
                        ground_truth=str(case.ground_truth) if case.ground_truth else None,
                        status="failed",
                        run_id=recorder.run_id,
                        latency_s=elapsed,
                        error=str(exc),
                    )
                )

    result = SuiteRunResult(
        suite_name=suite.name,
        suite_run_id=suite_run_id,
        root=lab_root,
        cells=cells,
    )
    _write_suite_artifacts(result, suite)
    return result


def render_suite_markdown(result: SuiteRunResult) -> str:
    lines = [
        f"# Suite Run: {result.suite_name}",
        "",
        f"- **Run ID:** `{result.suite_run_id}`",
        f"- **Cells:** {len(result.cells)}",
        "",
        "| pipeline | case | status | facts | latency | run |",
        "|---|---|---|---:|---:|---|",
    ]
    for cell in result.cells:
        run = f"`{cell.run_id}`" if cell.run_id else ""
        lines.append(
            f"| `{cell.pipeline}` | {cell.case_label} | {cell.status} | "
            f"{cell.fact_count} | {cell.latency_s:.1f}s | {run} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_shape_and_eval(
    *,
    bundle: dict,
    recorder: RunRecorder,
    ground_truth_path: Path | None,
) -> None:
    shape = score_bundle_shape(bundle)
    (recorder.root / "bundle_shape.json").write_text(json.dumps(asdict(shape), indent=2))

    gt: tuple[str, dict] | None = None
    if ground_truth_path is not None:
        gt = ("manual", json.loads(ground_truth_path.read_text()))
    else:
        auto_gt = load_latest_ground_truth(recorder.manifest.pdf_sha256, lab_root=recorder.root.parents[1])
        if auto_gt is not None:
            gt = (f"auto:v{auto_gt.version}", auto_gt.bundle)

    if gt is not None:
        from lib.extract.lab.eval_against_gt import score_against_ground_truth

        source, gt_bundle = gt
        eval_result = score_against_ground_truth(
            extracted=bundle,
            ground_truth=gt_bundle,
            pipeline_name=recorder.manifest.pipeline_name,
            ground_truth_label=source,
        )
        (recorder.root / "eval.json").write_text(json.dumps(asdict(eval_result), indent=2, default=str))


def _write_suite_artifacts(result: SuiteRunResult, suite: LabSuite) -> None:
    suite_dir = result.suite_dir
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "suite.json").write_text(json.dumps(asdict(suite), indent=2, default=str))
    (suite_dir / "cells.json").write_text(json.dumps([asdict(c) for c in result.cells], indent=2, default=str))
    (suite_dir / "report.md").write_text(render_suite_markdown(result))


def _resource_counts(bundle: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in bundle.get("entry", []):
        rt = entry.get("resource", {}).get("resourceType", "Unknown")
        counts[rt] = counts.get(rt, 0) + 1
    return counts


def _suite_run_id(name: str) -> str:
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower() or "suite"
    return f"{ts}_{slug}"
