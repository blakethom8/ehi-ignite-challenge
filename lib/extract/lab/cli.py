"""CLI for the PDF Lab. Subcommands:
    run     — run pipeline(s) on a PDF, capture full traces
    compare — diff two completed runs (LAB-T04, stub today)
    show    — print summary of one run (LAB-T06, stub today)
    list    — list recent runs (LAB-T06, stub today)
    report  — generate markdown report (LAB-T06, stub today)

Today this module ships only `run`. The other subcommands are stubbed
with a clear "lands in LAB-Tnn" message.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.extract.lab.recorder import DEFAULT_LAB_ROOT, RunRecorder
from lib.extract.pipelines import get as get_pipeline, list_pipelines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m lib.extract.lab",
        description="PDF Lab — agent-first CLI for running pipelines and capturing traces.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    _add_run_parser(subparsers)
    _add_stub_parsers(subparsers)

    args = parser.parse_args(argv)

    if args.cmd == "run":
        return _cmd_run(args)
    if args.cmd in ("compare", "show", "list", "report"):
        return _cmd_stub(args.cmd)

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


def _add_stub_parsers(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register placeholder subcommands so the help message lists them."""
    for cmd, deferred_to in [
        ("compare", "LAB-T04"),
        ("show", "LAB-T06"),
        ("list", "LAB-T06"),
        ("report", "LAB-T06"),
    ]:
        sp = sub.add_parser(cmd, help=f"(stub — lands in {deferred_to})")
        sp.set_defaults(deferred_to=deferred_to)


def _cmd_stub(cmd: str) -> int:
    deferred = {
        "compare": "LAB-T04",
        "show": "LAB-T06",
        "list": "LAB-T06",
        "report": "LAB-T06",
    }[cmd]
    print(f"`{cmd}` is not yet implemented. It lands in {deferred}.", file=sys.stderr)
    return 2


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

        manifest = recorder.manifest
        bundle_entries = len(bundle.get("entry", [])) if isinstance(bundle, dict) else 0
        print(f"  run-id: {recorder.run_id}")
        print(f"  artifacts: {recorder.root}")
        print(f"  cost: ${manifest.cost_usd:.4f}")
        print(f"  latency: {manifest.latency_ms / 1000:.1f}s")
        print(f"  bundle: {bundle_entries} entries")
        completed.append((name, recorder.run_id))

    print()
    print(f"Done. {len(completed)} run(s) completed, {len(failures)} failed.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
