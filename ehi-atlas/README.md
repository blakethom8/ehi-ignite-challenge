# EHI Atlas

**Patient-side EHI harmonization with FHIR-native provenance.**

Self-contained Python package that ingests heterogeneous patient health data — SMART-on-FHIR pulls, Epic EHI Export TSV, CMS claims, C-CDA documents, PDFs — and produces one canonical FHIR R4 record with full Provenance lineage. The clinician-facing app at `../api/` and `../app/` consumes our gold-tier output via the existing FHIR loader; nothing else is shared.

## Quickstart

```bash
cd ehi-atlas
uv sync --all-extras

# Set up the corpus from open sources (Synthea, Josh's repos, BB sandbox)
make corpus

# Run the end-to-end pipeline on the showcase patient
make pipeline

# Run the test suite
make test
```

## Where the docs live

This repo holds **operating docs** (how to run the harmonizer, how to add a new source, the FHIR Extension URLs we mint). Strategic and architectural docs live in the project workspace:

- **Architecture:** [`../architecture/DATA-AGGREGATION-LAYER.md`](../architecture/DATA-AGGREGATION-LAYER.md) — the 5-layer pipeline, FHIR-native Provenance, scripts vs LLMs principle, worked examples
- **Strategy:** [`../research/strategic-options.md`](../research/strategic-options.md) — embed/partner/parallel decision, rubric analysis
- **Prior art:** [`../research/harmonization-prior-art.md`](../research/harmonization-prior-art.md) — survey of 25 systems, 12 citations, reviewer pushbacks
- **Mandel dossier:** [`../research/josh-mandel/`](../research/josh-mandel/) — full grounding on the prior art we embed

## Operating docs (in `docs/`)

- [`docs/INTEGRATION.md`](docs/INTEGRATION.md) — how the existing app consumes `corpus/gold/`
- [`docs/ADAPTER-CONTRACT.md`](docs/ADAPTER-CONTRACT.md) — rules for adding a new source adapter
- [`docs/CROSSWALK-WORKFLOW.md`](docs/CROSSWALK-WORKFLOW.md) — build-time LLM bootstrap procedure for vendor-specific code mappings
- [`docs/PROVENANCE-SPEC.md`](docs/PROVENANCE-SPEC.md) — the FHIR Extension URLs we mint, frozen
- [`docs/mapping-decisions.md`](docs/mapping-decisions.md) — per-source mapping log

## Build state

- **Active tracker:** [`BUILD-TRACKER.md`](BUILD-TRACKER.md)
- **Orchestration meta-doc:** [`BUILD-ORCHESTRATION.md`](BUILD-ORCHESTRATION.md)

## The hard boundary

```
┌─ Existing app (../api/, ../app/) ──────────┐
│   imports nothing from ehi_atlas/          │
│   reads only corpus/gold/                  │
└────────────────────┬───────────────────────┘
                     │ FHIR Bundles + Provenance JSON
                     │
┌────────────────────▼───────────────────────┐
│ EHI Atlas (this directory)                 │
│   imports nothing from ../api/ or ../app/  │
│   self-contained Python package            │
└────────────────────────────────────────────┘
```

If you ever feel tempted to `from ehi_atlas import ...` in the existing app, that's a smell. The interface is pure data on disk.

## License

MIT — see [`LICENSE`](LICENSE).

## Attribution

EHI Atlas embeds open-source components from Josh Mandel's stack with attribution:

- [`request-my-ehi`](https://github.com/jmandel/request-my-ehi) (Apache-2.0)
- [`health-skillz`](https://github.com/jmandel/health-skillz) (MIT, claimed)
- [`health-record-mcp`](https://github.com/jmandel/health-record-mcp) (MIT)
- [`my-health-data-ehi-wip`](https://github.com/jmandel/my-health-data-ehi-wip) (MIT, claimed)
- [`sample_ccdas`](https://github.com/jmandel/sample_ccdas) (CC BY 4.0)

See [`../research/josh-mandel/README.md`](../research/josh-mandel/README.md) for the full attribution dossier.
