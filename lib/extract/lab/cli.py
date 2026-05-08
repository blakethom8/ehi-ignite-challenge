"""CLI for the PDF Lab. Subcommands:
    run     — run pipeline(s) on a PDF, capture full traces
    compare — diff two completed runs (LAB-T04)
    show    — print a single-run markdown summary (LAB-T06)
    list    — list recent runs (LAB-T06)
    report  — generate a paste-able markdown report (LAB-T06)

All subcommands are fully implemented.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from lib.extract.lab.bundle_shape import score_bundle_shape
from lib.extract.lab.recorder import DEFAULT_LAB_ROOT, RunRecorder
from lib.extract.pipelines import get as get_pipeline, list_pipelines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m lib.extract.lab",
        description="PDF Lab — agent-first CLI for running pipelines and capturing traces.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    _add_run_parser(subparsers)
    _add_compare_parser(subparsers)
    _add_show_parser(subparsers)
    _add_list_parser(subparsers)
    _add_report_parser(subparsers)

    args = parser.parse_args(argv)

    if args.cmd == "run":
        return _cmd_run(args)
    if args.cmd == "compare":
        return _cmd_compare(args)
    if args.cmd == "show":
        return _cmd_show(args)
    if args.cmd == "list":
        return _cmd_list(args)
    if args.cmd == "report":
        return _cmd_report(args)

    parser.error(f"unknown command: {args.cmd}")
    return 2  # unreachable after parser.error


def _add_run_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser(
        "run",
        help="Run pipeline(s) on a PDF, capture full traces",
        description="""\
Runs one or more pipelines against a single PDF. Each pipeline gets its
own run_id; traces / bundle / manifest land under data/pdf-lab/runs/.

Examples:
    python -m lib.extract.lab run --pipeline multipass-fhir --pdf path/to.pdf
    python -m lib.extract.lab run \\
        --pipeline multipass-fhir \\
        --pipeline multipass-fhir-bidi-scout \\
        --pdf path/to.pdf \\
        --ground-truth path/to/ground-truth.json
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--pipeline",
        action="append",
        required=False,
        default=None,
        metavar="NAME",
        help=(
            "Pipeline name (repeatable). "
            "Run `python -m lib.extract.lab run --list-pipelines` to see options."
        ),
    )
    p.add_argument(
        "--pdf",
        required=False,
        default=None,
        type=Path,
        help="Path to the input PDF.",
    )
    p.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Optional path to a ground-truth FHIR Bundle JSON (for future F1 scoring).",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_LAB_ROOT,
        help=f"Lab root directory (default: {DEFAULT_LAB_ROOT}).",
    )
    p.add_argument(
        "--list-pipelines",
        action="store_true",
        help="Print registered pipeline names and exit.",
    )


def _add_compare_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser(
        "compare",
        help="Diff two completed runs",
        description="""\
Reads two completed runs from data/pdf-lab/runs/ and prints a
structured diff: resource counts, fact agreement, cost / latency
delta, bundle-shape delta.

Examples:
    python -m lib.extract.lab compare --run-a <id> --run-b <id>
    python -m lib.extract.lab compare --run-a <id> --run-b <id> --format json
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--run-a", required=True, help="Baseline run id")
    p.add_argument("--run-b", required=True, help="Comparison run id")
    p.add_argument("--root", type=Path, default=DEFAULT_LAB_ROOT, help=f"Lab root (default: {DEFAULT_LAB_ROOT})")
    p.add_argument("--format", choices=["text", "json"], default="text", help="Output format")


def _cmd_compare(args: argparse.Namespace) -> int:
    from lib.extract.lab.compare import compare_runs
    try:
        comparison = compare_runs(args.run_a, args.run_b, root=args.root)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(asdict(comparison), indent=2, default=str))
    else:
        # Markdown / human-readable summary
        print("# Run comparison")
        print(f"  A: {comparison.run_a_id} ({comparison.pipeline_a})")
        print(f"  B: {comparison.run_b_id} ({comparison.pipeline_b})")
        print()
        print("## Cost / latency")
        print(f"  cost delta:    {comparison.cost_delta_usd:+.4f} USD (B - A)")
        print(f"  latency delta: {comparison.latency_delta_ms:+d} ms (B - A)")
        print()
        print("## Resource counts")
        all_types = sorted(set(comparison.resource_counts_a) | set(comparison.resource_counts_b))
        for rt in all_types:
            a = comparison.resource_counts_a.get(rt, 0)
            b = comparison.resource_counts_b.get(rt, 0)
            delta = b - a
            print(f"  {rt:<25} A={a:<4} B={b:<4} Δ={delta:+d}")
        print()
        print("## Fact agreement (only in A / only in B / overlap)")
        for rt in sorted(comparison.fact_overlap):
            ov = comparison.fact_overlap[rt]
            a_only = len(comparison.fact_only_in_a.get(rt, []))
            b_only = len(comparison.fact_only_in_b.get(rt, []))
            print(f"  {rt:<25} overlap={ov} only_in_a={a_only} only_in_b={b_only}")
    return 0


def _add_show_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("show", help="Print a single-run markdown summary")
    p.add_argument("--run", required=True, help="Run id")
    p.add_argument("--root", type=Path, default=DEFAULT_LAB_ROOT)


def _cmd_show(args: argparse.Namespace) -> int:
    from lib.extract.lab.report import render_run_summary
    try:
        print(render_run_summary(args.run, root=args.root))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _add_list_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("list", help="List recent runs")
    p.add_argument("--pipeline", default=None, help="Filter by pipeline name")
    p.add_argument("--last", type=int, default=20, help="Show only the last N runs (default 20)")
    p.add_argument("--root", type=Path, default=DEFAULT_LAB_ROOT)


def _cmd_list(args: argparse.Namespace) -> int:
    from lib.extract.lab.report import read_runs_index, render_runs_list
    runs = read_runs_index(root=args.root)
    runs = runs[: args.last]
    print(render_runs_list(runs, pipeline_filter=args.pipeline))
    return 0


def _add_report_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("report", help="Generate a markdown report for a run or comparison")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", help="Run id (single-run summary)")
    g.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"), help="Compare two run ids")
    p.add_argument("--root", type=Path, default=DEFAULT_LAB_ROOT)


def _cmd_report(args: argparse.Namespace) -> int:
    from lib.extract.lab.report import render_run_summary, render_comparison
    from lib.extract.lab.compare import compare_runs
    if args.run:
        try:
            print(render_run_summary(args.run, root=args.root))
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    else:
        run_a, run_b = args.compare
        try:
            comparison = compare_runs(run_a, run_b, root=args.root)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(render_comparison(comparison))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    if args.list_pipelines:
        for meta in list_pipelines():
            cost_str = f"~${meta.estimated_cost_per_pdf_usd}/pdf" if meta.estimated_cost_per_pdf_usd is not None else "cost unknown"
            print(f"  {meta.name:<32} {meta.architecture:<36} {cost_str}")
        return 0

    # --pdf is required when not --list-pipelines
    if not args.pdf:
        print("error: --pdf is required", file=sys.stderr)
        return 2

    pdf_path: Path = args.pdf
    if not pdf_path.exists():
        print(f"error: PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    if args.ground_truth and not args.ground_truth.exists():
        print(f"error: ground-truth not found: {args.ground_truth}", file=sys.stderr)
        return 2

    # --pipeline is required when not --list-pipelines
    if not args.pipeline:
        print("error: --pipeline is required", file=sys.stderr)
        return 2

    pipeline_names: list[str] = list(dict.fromkeys(args.pipeline))  # de-dupe, preserve order
    completed: list[tuple[str, str]] = []   # (pipeline_name, run_id)
    failures: list[tuple[str, str]] = []    # (pipeline_name, error)

    for name in pipeline_names:
        try:
            pipeline_cls = get_pipeline(name)
        except (KeyError, ValueError) as exc:
            print(f"error: unknown pipeline {name!r}: {exc}", file=sys.stderr)
            return 2

        pipeline = pipeline_cls()

        print(f"Running pipeline {name!r} on {pdf_path}...")
        recorder = RunRecorder.start(
            pipeline_name=name,
            pdf_path=pdf_path,
            ground_truth_path=args.ground_truth,
            root=args.root,
        )
        try:
            bundle = pipeline.extract(pdf_path, recorder=recorder)  # type: ignore[call-arg]
        except Exception as exc:  # noqa: BLE001
            print(f"  x FAILED: {exc}", file=sys.stderr)
            failures.append((name, str(exc)))
            # recorder.finish() is called inside extract() on failure (LAB-T02 contract)
            continue

        # Compute bundle shape and write bundle_shape.json
        shape = score_bundle_shape(bundle if isinstance(bundle, dict) else {})
        shape_path = recorder.root / "bundle_shape.json"
        shape_path.write_text(json.dumps(asdict(shape), indent=2))

        manifest = recorder.manifest
        bundle_entries = len(bundle.get("entry", [])) if isinstance(bundle, dict) else 0
        print(f"  run-id: {recorder.run_id}")
        print(f"  artifacts: {recorder.root}")
        print(f"  cost: ${manifest.cost_usd:.4f}")
        print(f"  latency: {manifest.latency_ms / 1000:.1f}s")
        print(f"  bundle: {bundle_entries} entries")
        print(f"  patient_count: {shape.patient_count}")
        print(f"  encounter_link_rate: {shape.encounter_link_rate:.0%}")
        print(f"  patient_link_rate: {shape.patient_link_rate:.0%}")
        print(f"  loinc_resolution_rate: {shape.loinc_resolution_rate:.0%}")
        completed.append((name, recorder.run_id))

    print()
    print(f"Done. {len(completed)} run(s) completed, {len(failures)} failed.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
