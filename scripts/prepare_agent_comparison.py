#!/usr/bin/env python3
"""Prepare raw-files vs workspace-package comparison prompts.

This does not call Claude/Codex. It creates a reproducible evaluation folder with
standard prompts, arm instructions, and file manifests so the same task set can
be run across agents.
"""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

PROMPTS: list[dict[str, str]] = [
    {
        "id": "patient-summary",
        "title": "Patient summary",
        "prompt": "You are helping a patient understand their medical record. Produce a concise, plain-language summary of the five most important things in this record. Include what changed recently, what information appears missing, and what the patient should ask their doctor. Cite sources for important claims when source information is available.",
    },
    {
        "id": "clinician-handoff",
        "title": "Clinician handoff",
        "prompt": "Create a one-page clinician handoff for a specialist reviewing this patient. Include active medications, allergies, key conditions, recent abnormal labs, missing information, and source citations. Do not invent facts. If evidence is unclear, say so.",
    },
    {
        "id": "source-contribution",
        "title": "Source contribution",
        "prompt": "Explain what each source contributed to the patient record. Identify facts that appear in more than one source, facts unique to a source, and any conflicts or duplicates that require review.",
    },
    {
        "id": "chart-ready-labs",
        "title": "Chart-ready labs",
        "prompt": "Create a chart-ready table of kidney, liver, metabolic, and hematology labs over time. Include test name, date, value, unit, reference range, abnormal flag, and source. State which labs are missing or not comparable.",
    },
    {
        "id": "agent-audit",
        "title": "Agent audit",
        "prompt": "Audit your own answer. List every important claim, the source or evidence you used, and any claim that lacks adequate support.",
    },
]

ARMS = {
    "raw": "Use only the raw/source files in this arm. Do not inspect the prepared Atlas workspace package.",
    "package": "Use the EHI Atlas workspace package. Read MANIFEST.json and AGENT-INSTRUCTIONS.md first. Prefer structured evidence, provenance, source contributions, conflicts, and missing-information files.",
    "package-plus-raw": "Use the EHI Atlas workspace package first, then inspect raw/source files only when needed to verify or investigate gaps. Cite structured evidence whenever possible.",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def discover_raw_sources(collection: str) -> list[Path]:
    paths: list[Path] = []
    demo_dir = REPO_ROOT / "data" / "harmonize-demo" / collection
    if demo_dir.exists():
        paths.extend(sorted(demo_dir.glob("*.json")))
    uploads_dir = REPO_ROOT / "data" / "aggregation-uploads" / collection
    if uploads_dir.exists():
        for p in sorted(uploads_dir.iterdir()):
            if p.suffix.lower() in {".pdf", ".json", ".xml", ".csv"} and not p.name.endswith(".metadata.json") and not p.name.endswith(".extracted.json"):
                paths.append(p)
    if not paths and not collection.startswith("workspace-"):
        return discover_raw_sources(f"workspace-{collection}")
    return paths


def file_manifest(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for p in paths:
        rows.append({"path": str(p), "name": p.name, "size_bytes": p.stat().st_size})
    return rows


def copy_inputs(paths: list[Path], dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    rels = []
    for p in paths:
        target = dest / p.name
        shutil.copy2(p, target)
        rels.append(str(target.relative_to(dest.parent.parent)))
    return rels


def write_prompt_files(out_dir: Path) -> None:
    prompts_dir = out_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for item in PROMPTS:
        (prompts_dir / f"{item['id']}.md").write_text(f"# {item['title']}\n\n{item['prompt']}\n")
    (prompts_dir / "all-prompts.json").write_text(json.dumps(PROMPTS, indent=2) + "\n")


def prepare(collection: str, package: Path, out_dir: Path, copy: bool) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_sources = discover_raw_sources(collection)
    if not raw_sources:
        raise SystemExit(f"No raw sources found for {collection}")
    if not package.exists():
        raise SystemExit(f"Package not found: {package}")

    write_prompt_files(out_dir)
    package_rel = None
    raw_rels = [str(p) for p in raw_sources]
    if copy:
        raw_rels = copy_inputs(raw_sources, out_dir / "arms" / "raw" / "inputs")
        (out_dir / "arms" / "package" / "inputs").mkdir(parents=True, exist_ok=True)
        pkg_target = out_dir / "arms" / "package" / "inputs" / package.name
        shutil.copy2(package, pkg_target)
        package_rel = str(pkg_target.relative_to(out_dir))
        (out_dir / "arms" / "package-plus-raw" / "inputs").mkdir(parents=True, exist_ok=True)
        shutil.copy2(package, out_dir / "arms" / "package-plus-raw" / "inputs" / package.name)
        for p in raw_sources:
            shutil.copy2(p, out_dir / "arms" / "package-plus-raw" / "inputs" / p.name)
    else:
        package_rel = str(package)

    for arm, instruction in ARMS.items():
        arm_dir = out_dir / "arms" / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        (arm_dir / "INSTRUCTIONS.md").write_text(f"# {arm}\n\n{instruction}\n\nRun each prompt in `../../prompts/` and save outputs in this folder.\n")

    manifest = {
        "comparison_version": "atlas-agent-comparison.v1",
        "created_at": now_iso(),
        "collection": collection,
        "package": package_rel,
        "raw_sources": file_manifest(raw_sources),
        "arms": ARMS,
        "prompts": PROMPTS,
        "scoring_dimensions": [
            "correctness",
            "completeness",
            "traceability",
            "interpretability",
            "cross_source_reasoning",
            "missing_info_handling",
            "chart_readiness",
            "reusability",
            "auditability",
        ],
    }
    (out_dir / "comparison-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out_dir / "README.md").write_text(
        "# Agent Comparison Run\n\n"
        "Compare raw files vs the EHI Atlas workspace package. Use the same prompts for each arm and score outputs with the dimensions in `comparison-manifest.json`.\n\n"
        "Arms: raw, package, package-plus-raw.\n"
    )
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare raw-files vs workspace-package comparison prompts")
    ap.add_argument("--collection", required=True)
    ap.add_argument("--package", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--copy-inputs", action="store_true")
    args = ap.parse_args()
    out = prepare(args.collection, args.package, args.out, args.copy_inputs)
    print(out)


if __name__ == "__main__":
    main()
