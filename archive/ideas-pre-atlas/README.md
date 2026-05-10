# `archive/ideas-pre-atlas/`

Product spec docs that fed the original (pre-Atlas) product shape. Preserved as historical record; do not extend. The strategic intent in each is mostly intact, but the IA, naming, and module boundaries are superseded by the Atlas Agentic Workspaces redesign.

| File | What it described | Where the intent landed |
|---|---|---|
| `PATIENT-JOURNEY-APP.md` | Standalone clinician-facing journey app — medications, safety panel, timeline | Folded into **Caspian** as the longitudinal-synthesis workflow + the FHIR Charts journey view (`/fhir-charts/journey`) |
| `FORMAT-AGNOSTIC-INGESTION.md` | Multi-format ingestion service spec (PDF, C-CDA, HL7, CSV) | Implemented as `lib/extract/` (PDF → FHIR pipeline) and the Patient Record / Source Intake routes |
| `DATA-AGGREGATOR-WIREFRAMES.md` | Wireframes for the standalone "Data Aggregator" module with its own left nav | Folded into **Patient Record** as sub-routes (`/patient-record/sources`, `/patient-record/harmonize`, `/patient-record/publish`, etc.) |

Authoritative current sources:
- `.claude/handoff/atlas/README.md` — Atlas product spec
- `design/agentic-shell-spec/` — agentic shell vision
- `docs/architecture/AGENTIC-HARNESS.md` — runtime contract for Caspian vs. Plugins
- `app/src/components/atlas/README.md` — current shared-component inventory
