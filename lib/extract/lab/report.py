"""Markdown report generators for the PDF Lab.

The PRIMARY artifact for the agent-loop: Claude generates a report,
pastes the markdown into a conversation with the user. Output is
designed to be readable in a terminal AND copy-paste-able into chat.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.extract.lab.recorder import DEFAULT_LAB_ROOT
from lib.extract.lab.compare import RunComparison


def render_run_summary(run_id: str, *, root: Path | None = None) -> str:
    """Single-run markdown summary. Read manifest + bundle + bundle_shape;
    render as readable markdown."""
    root = root or DEFAULT_LAB_ROOT
    run_dir = root / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"run not found: {run_id} ({run_dir})")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    bundle = _read_optional_json(run_dir / "bundle.json", {"entry": []})
    bundle_shape = _read_optional_json(run_dir / "bundle_shape.json", {})

    lines: list[str] = []
    lines.append(f"# Run: `{run_id}`")
    lines.append("")
    lines.append(f"- **Pipeline:** {manifest.get('pipeline_name', '?')}")
    lines.append(f"- **Status:** {manifest.get('status', '?')}")
    lines.append(f"- **PDF:** `{manifest.get('pdf_path', '?')}`")
    lines.append(f"- **Started:** {manifest.get('started_at', '?')}")
    lines.append(f"- **Finished:** {manifest.get('finished_at', '?')}")
    lines.append(f"- **Cost:** ${manifest.get('cost_usd', 0):.4f}")
    lines.append(f"- **Latency:** {manifest.get('latency_ms', 0) / 1000:.1f}s")
    if manifest.get("error"):
        lines.append(f"- **Error:** {manifest['error']}")
    lines.append("")

    # Resource counts
    counts: dict[str, int] = {}
    for entry in bundle.get("entry", []):
        rt = entry.get("resource", {}).get("resourceType", "?")
        counts[rt] = counts.get(rt, 0) + 1
    if counts:
        lines.append("## Resource counts")
        lines.append("")
        lines.append("| Type | Count |")
        lines.append("|---|---:|")
        for rt in sorted(counts):
            lines.append(f"| {rt} | {counts[rt]} |")
        lines.append(f"| **Total** | **{sum(counts.values())}** |")
        lines.append("")

    # Bundle shape highlights
    if bundle_shape:
        lines.append("## Bundle shape")
        lines.append("")
        for k in (
            "patient_count",
            "encounter_count",
            "encounter_link_rate",
            "patient_link_rate",
            "practitioner_npi_rate",
            "loinc_resolution_rate",
            "interpretation_rate",
            "clinical_category_rate",
            "note_encounter_link_rate",
        ):
            if k in bundle_shape:
                v = bundle_shape[k]
                if isinstance(v, float):
                    lines.append(f"- **{k}**: {v:.0%}" if 0 <= v <= 1 else f"- **{k}**: {v:.4f}")
                else:
                    lines.append(f"- **{k}**: {v}")
        if bundle_shape.get("multiple_patients_warning"):
            lines.append("- WARNING: **multiple_patients_warning** — bundle has more than 1 Patient resource")
        if bundle_shape.get("duplicate_practitioner_npis"):
            lines.append(f"- WARNING: **duplicate practitioner NPIs**: {bundle_shape['duplicate_practitioner_npis']}")
        if bundle_shape.get("orphaned_subject_references"):
            n = len(bundle_shape["orphaned_subject_references"])
            lines.append(f"- WARNING: **{n} orphaned subject references**")
        if bundle_shape.get("orphaned_encounter_references"):
            n = len(bundle_shape["orphaned_encounter_references"])
            lines.append(f"- WARNING: **{n} orphaned encounter references**")
        lines.append("")

    # Per-pass cost / latency breakdown (if traces dir exists)
    traces_dir = run_dir / "traces"
    if traces_dir.exists():
        lines.append("## Per-pass breakdown")
        lines.append("")
        lines.append("| Pass | Tokens (in/out) | Latency | Cost |")
        lines.append("|---|---|---:|---:|")
        for pass_dir in sorted(traces_dir.iterdir()):
            if not pass_dir.is_dir():
                continue
            usage_path = pass_dir / "usage.json"
            if not usage_path.exists():
                continue
            usage = json.loads(usage_path.read_text())
            tin = usage.get("input_tokens", "?")
            tout = usage.get("output_tokens", "?")
            lat = usage.get("latency_ms", 0)
            cost = usage.get("cost_usd", 0)
            lines.append(f"| {pass_dir.name} | {tin}/{tout} | {lat / 1000:.1f}s | ${cost:.4f} |")
        lines.append("")

    return "\n".join(lines)


def render_runs_list(runs: list[dict], *, pipeline_filter: str | None = None) -> str:
    """Markdown table of recent runs. `runs` is a list of manifest dicts
    (one per line of runs.jsonl)."""
    if pipeline_filter:
        runs = [r for r in runs if r.get("pipeline_name") == pipeline_filter]
    if not runs:
        return "_No runs found._"

    lines: list[str] = []
    lines.append("# Recent runs")
    lines.append("")
    lines.append("| run_id | pipeline | status | cost | latency |")
    lines.append("|---|---|---|---:|---:|")
    for r in runs:
        rid = r.get("run_id", "?")
        pipeline = r.get("pipeline_name", "?")
        status = r.get("status", "?")
        cost = r.get("cost_usd", 0)
        latency = r.get("latency_ms", 0)
        lines.append(f"| `{rid}` | {pipeline} | {status} | ${cost:.4f} | {latency / 1000:.1f}s |")
    return "\n".join(lines)


def render_comparison(comparison: RunComparison) -> str:
    """Render RunComparison as a paste-able markdown report."""
    c = comparison
    lines: list[str] = []
    lines.append(f"# Comparison: `{c.run_a_id}` (A) vs `{c.run_b_id}` (B)")
    lines.append("")
    lines.append(f"- **Pipeline A:** {c.pipeline_a}")
    lines.append(f"- **Pipeline B:** {c.pipeline_b}")
    lines.append(f"- **Cost delta (B - A):** {c.cost_delta_usd:+.4f} USD")
    lines.append(f"- **Latency delta (B - A):** {c.latency_delta_ms:+d} ms")
    lines.append("")

    # Resource counts
    lines.append("## Resource counts")
    lines.append("")
    lines.append("| Type | A | B | Delta |")
    lines.append("|---|---:|---:|---:|")
    all_types = sorted(set(c.resource_counts_a) | set(c.resource_counts_b))
    for rt in all_types:
        a = c.resource_counts_a.get(rt, 0)
        b = c.resource_counts_b.get(rt, 0)
        delta = b - a
        delta_str = f"{delta:+d}" if delta != 0 else "—"
        lines.append(f"| {rt} | {a} | {b} | {delta_str} |")
    lines.append("")

    # Fact agreement
    lines.append("## Fact agreement")
    lines.append("")
    lines.append("| Type | overlap | only_in_a | only_in_b |")
    lines.append("|---|---:|---:|---:|")
    fact_types = sorted(set(c.fact_overlap) | set(c.fact_only_in_a) | set(c.fact_only_in_b))
    for rt in fact_types:
        overlap = c.fact_overlap.get(rt, 0)
        a_only = len(c.fact_only_in_a.get(rt, []))
        b_only = len(c.fact_only_in_b.get(rt, []))
        lines.append(f"| {rt} | {overlap} | {a_only} | {b_only} |")
    lines.append("")

    # Sample disagreements
    if any(c.fact_only_in_a.values()) or any(c.fact_only_in_b.values()):
        lines.append("## Disagreement samples")
        lines.append("")
        for rt, samples in c.fact_only_in_a.items():
            if not samples:
                continue
            lines.append(f"### Only in A — {rt} ({len(samples)} sampled)")
            for s in samples:
                code = f" ({s.code})" if s.code else ""
                value = f" = {s.value}" if s.value else ""
                lines.append(f"- `{s.display}`{code}{value}")
            lines.append("")
        for rt, samples in c.fact_only_in_b.items():
            if not samples:
                continue
            lines.append(f"### Only in B — {rt} ({len(samples)} sampled)")
            for s in samples:
                code = f" ({s.code})" if s.code else ""
                value = f" = {s.value}" if s.value else ""
                lines.append(f"- `{s.display}`{code}{value}")
            lines.append("")

    # Bundle shape delta
    if c.bundle_shape_a or c.bundle_shape_b:
        lines.append("## Bundle shape delta")
        lines.append("")
        lines.append("| Metric | A | B |")
        lines.append("|---|---:|---:|")
        all_keys = sorted(set(c.bundle_shape_a) | set(c.bundle_shape_b))
        for k in all_keys:
            if k in ("duplicate_practitioner_npis", "orphaned_subject_references", "orphaned_encounter_references"):
                continue  # list fields rendered separately
            a_val = c.bundle_shape_a.get(k)
            b_val = c.bundle_shape_b.get(k)
            lines.append(f"| {k} | {a_val} | {b_val} |")
        lines.append("")

    return "\n".join(lines)


def _read_optional_json(path: Path, default: object) -> object:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return default
    return default


def read_runs_index(root: Path | None = None) -> list[dict]:
    """Read runs.jsonl into a list of manifest dicts. Newest first."""
    root = root or DEFAULT_LAB_ROOT
    index_path = root / "runs.jsonl"
    if not index_path.exists():
        return []
    rows: list[dict] = []
    for line in index_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    # Sort newest-first by started_at (ISO-sortable strings)
    rows.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return rows
