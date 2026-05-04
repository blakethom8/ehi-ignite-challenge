"""EHI Atlas CLI.

`ehi-atlas <command> [options]`

Commands stub here; sub-commands are implemented as the corresponding pipeline
stages come online. See BUILD-TRACKER.md for current implementation status.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="ehi-atlas",
    help="Patient-side EHI harmonization with FHIR-native provenance.",
    no_args_is_help=True,
)
console = Console()


# ---- Top-level subcommand groups ----------------------------------------

corpus_app = typer.Typer(help="Corpus assembly (Layer 1 inputs).")
ingest_app = typer.Typer(help="Layer 1: source → bronze.")
standardize_app = typer.Typer(help="Layer 2: bronze → silver (FHIR R4).")
extract_app = typer.Typer(help="Layer 2-B: vision extraction for unstructured sources.")
harmonize_app = typer.Typer(help="Layer 3: silver → gold (merged + Provenance).")

app.add_typer(corpus_app, name="corpus")
app.add_typer(ingest_app, name="ingest")
app.add_typer(standardize_app, name="standardize")
app.add_typer(extract_app, name="extract")
app.add_typer(harmonize_app, name="harmonize")


# ---- Corpus management --------------------------------------------------

@corpus_app.command("status")
def corpus_status() -> None:
    """Show what's present and missing in the corpus."""
    console.print("[yellow]corpus status: not yet implemented[/yellow]")
    console.print("Tracker task: 1.13")


@corpus_app.command("build")
def corpus_build() -> None:
    """Stage _sources/ to bronze/ for all configured sources."""
    console.print("[yellow]corpus build: not yet implemented[/yellow]")
    console.print("Tracker task: 1.12")


# ---- Ingest (Layer 1) ---------------------------------------------------

# Corpus root, resolved relative to this file's location (ehi_atlas/ → ehi-atlas/).
_ATLAS_ROOT = Path(__file__).resolve().parent.parent
_SOURCES_ROOT = _ATLAS_ROOT / "corpus" / "_sources"
_BRONZE_ROOT = _ATLAS_ROOT / "corpus" / "bronze"


@ingest_app.callback(invoke_without_command=True)
def ingest_main(
    source: str = typer.Option(None, "--source", help="Source name (e.g. synthea)"),
    patient: str = typer.Option(None, "--patient", help="Patient ID; default = all"),
    all_sources: bool = typer.Option(False, "--all", help="Run all registered adapters"),
) -> None:
    """Run a Layer 1 adapter end-to-end."""
    from ehi_atlas.adapters import REGISTRY

    if all_sources:
        sources_to_run = list(REGISTRY.keys())
    elif source:
        sources_to_run = [source]
    else:
        console.print("[yellow]Specify --source <name> or --all[/yellow]")
        console.print(f"Registered sources: {sorted(REGISTRY.keys())}")
        raise typer.Exit(1)

    for src_name in sources_to_run:
        adapter_cls = REGISTRY.get(src_name)
        if adapter_cls is None:
            console.print(f"[red]Unknown source: {src_name!r}. Not yet implemented.[/red]")
            console.print(f"Registered: {sorted(REGISTRY.keys())}")
            raise typer.Exit(1)

        source_root = _SOURCES_ROOT / src_name / "raw"
        bronze_root = _BRONZE_ROOT / src_name
        adapter = adapter_cls(source_root=source_root, bronze_root=bronze_root)

        patients_to_run = [patient] if patient else adapter.list_patients()
        if not patients_to_run:
            console.print(f"[yellow]No patients found for source {src_name!r}[/yellow]")
            continue

        for pid in patients_to_run:
            try:
                metadata = adapter.ingest(pid)
                bronze_dir = adapter.bronze_dir(pid)
                # Find the actual data file the adapter wrote (data.json | data.xml | data.pdf | etc.)
                data_files = sorted(bronze_dir.glob("data.*"))
                bronze_path = data_files[0] if data_files else bronze_dir
                console.print(
                    f"[green]✓[/green] {src_name}/{pid} → {bronze_path}  "
                    f"(sha256: {metadata.sha256[:16]}…)"
                )
            except Exception as exc:
                console.print(f"[red]✗ {src_name}/{pid}: {exc}[/red]")
                raise typer.Exit(1)


# ---- Standardize (Layer 2) ----------------------------------------------

_SILVER_ROOT = _ATLAS_ROOT / "corpus" / "silver"


@standardize_app.callback(invoke_without_command=True)
def standardize_main(
    source: str = typer.Option(None, "--source", help="Source name (e.g. synthea)"),
    patient: str = typer.Option(None, "--patient", help="Patient ID; default = all"),
    all_sources: bool = typer.Option(False, "--all", help="Run all registered standardizers"),
    strict: bool = typer.Option(False, "--strict", help="Fail on unknown profiles instead of warning"),
) -> None:
    """Run Layer 2 standardization (bronze → silver)."""
    from ehi_atlas.standardize import REGISTRY as STD_REGISTRY

    if all_sources:
        sources_to_run = list(STD_REGISTRY.keys())
    elif source:
        sources_to_run = [source]
    else:
        console.print("[yellow]Specify --source <name> or --all[/yellow]")
        console.print(f"Registered standardizers: {sorted(STD_REGISTRY.keys())}")
        raise typer.Exit(1)

    exit_code = 0

    for src_name in sources_to_run:
        standardizer_cls = STD_REGISTRY.get(src_name)
        if standardizer_cls is None:
            console.print(f"[red]Unknown source: {src_name!r}. Not yet implemented.[/red]")
            console.print(f"Registered: {sorted(STD_REGISTRY.keys())}")
            raise typer.Exit(1)

        bronze_root = _BRONZE_ROOT / src_name
        silver_root = _SILVER_ROOT / src_name
        standardizer = standardizer_cls(bronze_root=bronze_root, silver_root=silver_root)

        # Derive the list of patients from the bronze directory if not specified
        if patient:
            patients_to_run = [patient]
        else:
            # Walk bronze/<source>/ subdirectories as patient IDs
            if bronze_root.exists():
                patients_to_run = sorted(
                    p.name for p in bronze_root.iterdir()
                    if p.is_dir() and (p / "data.json").exists()
                )
            else:
                patients_to_run = []

        if not patients_to_run:
            console.print(f"[yellow]No patients found for source {src_name!r} under {bronze_root}[/yellow]")
            continue

        for pid in patients_to_run:
            try:
                result = standardizer.standardize(pid, strict=strict)
                console.print(
                    f"[green]✓[/green] {src_name}/{pid} → {result.silver_path}  "
                    f"(sha256: {result.sha256[:16]}…)"
                )
                for w in result.validation_warnings:
                    console.print(f"  [yellow]{w}[/yellow]")
            except Exception as exc:
                console.print(f"[red]✗ {src_name}/{pid}: {exc}[/red]")
                exit_code = 1

    if exit_code:
        raise typer.Exit(exit_code)


# ---- Extract (Layer 2-B) ------------------------------------------------

@extract_app.callback(invoke_without_command=True)
def extract_main(ctx: typer.Context) -> None:
    """Run Layer 2-B vision extraction (unstructured → silver).

    Use `ehi-atlas extract run` to invoke real extraction.
    """
    if ctx.invoked_subcommand is None:
        console.print(
            "[yellow]Specify a subcommand. "
            "Use 'ehi-atlas extract run --help' for options.[/yellow]"
        )


@extract_app.command("run")
def extract_run(
    source: str = typer.Option("lab-pdf", "--source", help="Bronze source name (e.g. lab-pdf)"),
    patient: str = typer.Option("rhett759", "--patient", help="Patient ID under the source"),
    skip_cache: bool = typer.Option(False, "--no-cache", help="Force a real API call and overwrite cache"),
) -> None:
    """Run vision extraction on a bronze PDF, write silver extraction JSON.

    Reads ``corpus/bronze/<source>/<patient>/data.pdf``, runs the Claude vision
    wrapper, prints the ExtractionResult, and writes:

    \\b
    - ``corpus/silver/<source>/<patient>/extraction.json`` — the validated output
    - Cache entry under ``ehi_atlas/extract/.cache/<hash>.json``

    Requires ``ANTHROPIC_API_KEY`` to be set unless the result is already cached.
    Pass ``--no-cache`` once to force a real API call and populate the cache;
    subsequent runs will hit the cache and make no network requests.
    """
    import json
    from ehi_atlas.extract.pdf import extract_lab_pdf

    bronze_path = _ATLAS_ROOT / "corpus" / "bronze" / source / patient / "data.pdf"
    if not bronze_path.exists():
        console.print(f"[red]Bronze PDF not found: {bronze_path}[/red]")
        console.print(
            f"Run 'ehi-atlas ingest --source {source} --patient {patient}' first."
        )
        raise typer.Exit(1)

    silver_dir = _ATLAS_ROOT / "corpus" / "silver" / source / patient
    silver_dir.mkdir(parents=True, exist_ok=True)
    silver_path = silver_dir / "extraction.json"

    console.print(f"[bold]Extracting[/bold] {bronze_path} ...")
    console.print(f"  skip_cache={skip_cache}")

    try:
        result = extract_lab_pdf(bronze_path, skip_cache=skip_cache)
    except Exception as exc:
        # Surface actionable messages for common failure modes
        err_str = str(exc)
        if "api_key" in err_str.lower() or "authentication" in err_str.lower():
            console.print(
                "[red]API key error: set ANTHROPIC_API_KEY and retry.[/red]"
            )
        elif "tool" in err_str.lower():
            console.print(f"[red]Model did not emit tool call: {exc}[/red]")
        else:
            console.print(f"[red]Extraction failed: {exc}[/red]")
        raise typer.Exit(1)

    silver_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )

    console.print(f"[green]✓[/green] Extraction complete.")
    console.print(f"  Silver: {silver_path}")
    console.print(f"  Confidence: {result.extraction_confidence}")
    console.print(f"  Model: {result.extraction_model}")
    console.print(f"  Document type: {result.document.document_type}")

    # Pretty-print result summary
    doc = result.document
    if hasattr(doc, "results"):
        console.print(f"  Lab results extracted: {len(doc.results)}")
        for r in doc.results[:5]:  # first 5 rows
            flag = f" [{r.flag}]" if r.flag else ""
            console.print(
                f"    {r.test_name}: {r.value_quantity} {r.unit or ''}{flag}"
            )
        if len(doc.results) > 5:
            console.print(f"    ... and {len(doc.results) - 5} more")


# ---- Harmonize (Layer 3) ------------------------------------------------

@harmonize_app.callback(invoke_without_command=True)
def harmonize_main(
    patient: str = typer.Option("rhett759", "--patient", help="Patient ID"),
) -> None:
    """Run Layer-3 harmonize on a patient."""
    from ehi_atlas.harmonize.orchestrator import harmonize_patient

    silver_root = _ATLAS_ROOT / "corpus" / "silver"
    bronze_root = _ATLAS_ROOT / "corpus" / "bronze"
    gold_root = _ATLAS_ROOT / "corpus" / "gold"

    try:
        result = harmonize_patient(silver_root, bronze_root, gold_root, patient)
    except Exception as exc:
        console.print(f"[red]✗ harmonize failed: {exc}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {patient} → {result.bundle_path}")
    console.print(f"  sources: {result.source_count}")
    console.print(f"  merged: {result.merged_counts}")
    console.print(f"  conflicts: {result.conflict_count}")
    console.print(f"  sha256: {result.bundle_sha256[:16]}…")


# ---- Pipeline (end-to-end) ----------------------------------------------

@app.command("pipeline")
def pipeline(
    patient: str = typer.Option("showcase", "--patient"),
) -> None:
    """End-to-end pipeline: ingest → standardize → extract → harmonize."""
    console.print(f"[yellow]pipeline --patient={patient}: not yet implemented[/yellow]")
    console.print("This will run all stages in order once they're online.")


# ---- Validate (Layer 2 silver-gate) -------------------------------------

@app.command("validate")
def validate(
    bundle: Path = typer.Option(..., "--bundle", help="Path to a silver FHIR R4 Bundle JSON file."),
    strict: bool = typer.Option(False, "--strict", help="Treat unknown profiles as errors (not warnings)."),
) -> None:
    """Validate a silver-tier FHIR R4 Bundle against EHI Atlas profile and provenance rules.

    Exits 0 if the bundle passes all checks; exits 1 if any errors are found.
    Warnings (e.g. unknown profiles in non-strict mode) are printed but do not
    cause a non-zero exit.
    """
    import json
    from ehi_atlas.standardize.validators import BundleValidator

    if not bundle.exists():
        console.print(f"[red]File not found: {bundle}[/red]")
        raise typer.Exit(1)

    try:
        with bundle.open() as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        console.print(f"[red]JSON parse error: {exc}[/red]")
        raise typer.Exit(1)

    validator = BundleValidator(strict=strict)
    messages = validator.validate(data)

    errors = [m for m in messages if not m.startswith("warning:")]
    warnings = [m for m in messages if m.startswith("warning:")]

    for w in warnings:
        console.print(f"[yellow]{w}[/yellow]")
    for e in errors:
        console.print(f"[red]{e}[/red]")

    if errors:
        console.print(f"[red]✗ {len(errors)} error(s) — bundle is invalid.[/red]")
        raise typer.Exit(1)
    elif warnings:
        console.print(f"[green]✓ bundle valid[/green] (with {len(warnings)} warning(s))")
    else:
        console.print("[green]✓ bundle valid[/green]")


@app.command("integrate")
def integrate() -> None:
    """Set up the symlink so the existing app finds gold-tier output."""
    console.print("[yellow]integrate: not yet implemented[/yellow]")
    console.print("Will create ../data/ehi-atlas-output → ./corpus/gold/ symlink.")


@app.command("version")
def version() -> None:
    """Print the harmonizer version."""
    from ehi_atlas import __version__
    console.print(f"ehi-atlas {__version__}")


if __name__ == "__main__":
    app()
