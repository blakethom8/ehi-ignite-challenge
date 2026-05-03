# Glossary — Josh Mandel Stack Deep Dive

Append-only. Each session adds new terms. Sorted alphabetically within each session block.

## Session 00 (2026-05-01)

- **Anthropic Skill** — packaging convention for Claude-runnable capability bundles. A directory containing `SKILL.md` (with YAML frontmatter: `name`, `description`, optional `argument-hint`, `allowed-tools`) plus optional `scripts/`, `references/`, `data/`. Loaded by Claude Code or web Claude as a unit. Both `request-my-ehi` and `health-skillz` ship this format.
- **Brand directory / brand tags** — Josh's portable JSON registry of FHIR endpoints (`static/brands/*.json` in `health-record-mcp`; `src/client/lib/brands/` in `health-skillz`). Filterable via URL params like `?brandTags=epic^prod` (AND on `^`, OR on `,`). Drives the patient-portal picker UI.
- **C-CDA (Consolidated CDA)** — XML-based clinical document standard, predecessor to FHIR. Josh's `sample_ccdas` corpus (747 docs, 2018-frozen) is the de-facto open fixture set.
- **`ClientFullEHR`** — Josh's snapshot type representing a fully fetched per-patient FHIR record set, used as the in-memory shape and as input to the `flattened-SQLite` materializer in `health-record-mcp`.
- **EHI Export** — the bulk patient-data export mandated by the ONC Cures Act. Real Epic EHI is delivered as hundreds of TSV files plus a manifest, *not* as FHIR. `my-health-data-ehi-wip` is the only open ingest pipeline.
- **MCP (Model Context Protocol)** — Anthropic's spec for exposing tools/resources to LLM clients over stdio, SSE, or HTTP. `health-record-mcp` was Josh's first wrapper; `health-skillz` replaces transport-bound MCP with bundled-skill scripts.
- **PKCE (Proof Key for Code Exchange, RFC 7636)** — OAuth 2.0 extension that hardens the authorization-code flow for public clients. Used by both Josh's SMART clients.
- **SMART on FHIR / SMART App Launch** — OAuth 2.0 + OIDC profile for FHIR clients accessing patient portals. Public-client variant uses PKCE; confidential variant uses asymmetric client assertion (`client-assertion.ts` in `health-skillz`).
- **TEFCA / Carequality / Commonwell** — US national health-information-exchange networks (mentioned in the prior dossier but not directly implemented in Josh's stack — he focuses on direct SMART pulls + Epic EHI Export).

## Session D01 (2026-05-01)

- **`ClientFullEHR`** — formal type signature: `{ fhir: Record<string, any[]>, attachments: ClientProcessedAttachment[] }`. The canonical in-memory shape for one patient's complete record set in Josh's stack. Defined in `health-record-mcp/clientTypes.ts:23`. Reused (with the same shape) in `health-skillz`. Single most load-bearing data shape in the stack.
- **`ClientProcessedAttachment`** — the per-attachment record on `ClientFullEHR.attachments`. Fields: `resourceType`, `resourceId`, `path` (dotted JSONPath into the parent resource), `contentType`, `json` (original attachment node as JSON string), `contentBase64`, `contentPlaintext`. The plaintext field is best-effort — null when extraction fails.
- **Initial-fetch query plan** — the 29 patient-scoped FHIR searches Josh's fetcher runs to consider a patient "fully fetched." Defined in `health-record-mcp/src/fhirSearchQueries.ts`. Includes 7 `Observation`-by-category queries plus one query each for ~22 other resource types. Triggers a BFS reference-discovery loop, so actual fetches typically reach hundreds.
- **`_C_NAME` columns (Epic EHI)** — denormalized lookup-table joins. Epic stores categorical values as integer codes in `_C` columns; the EHI Export serializes both code and human label as adjacent columns (`X_C` + `X_C_NAME`). Inflates column counts but makes exports self-contained.
- **Wiggum** — Josh's LLM-runner submodule in `ehi-export-analysis/wiggum/`. Generated the per-vendor `analyses/{slug}.md` files programmatically over CHPL data + vendor docs. Treat outputs as narrative summaries, not authoritative truth.
- **CHPL (Certified Health IT Product List)** — ONC's authoritative US registry of certified EHR products. The upstream source-of-truth for `vendors.json`'s editorial layer. Browseable at chpl.healthit.gov.
- **Variant cluster (redaction)** — in `health-skillz/redaction.ts`, multiple instances of the same value (e.g. `"Lisinopril"` across many `MedicationRequest.medicationCodeableConcept.text`) get one profile entry that's applied to all instances. Lets the user redact a class of facts in one click rather than per-resource.
- **`$meta` envelope (Josh's post-merge JSON)** — the `json/<table>.json` files in `my-health-data-ehi-wip` carry their own schema(s) under `$meta.schemas`. Self-describing artifacts — an LLM consumer doesn't need a sidecar schema fetch.

## Acronym index

| Acronym | Expansion |
|---|---|
| ABN | Advance Beneficiary Notice (Medicare-mandated patient notice that a service may not be covered) |
| AES-GCM | Advanced Encryption Standard, Galois/Counter Mode |
| C-CDA | Consolidated Clinical Document Architecture |
| CDM | Common Data Model (e.g. OMOP, PCORnet, Sentinel) |
| CHPL | Certified Health IT Product List (ONC) |
| CSN | Contact Serial Number (Epic per-encounter unique ID) |
| HNO | (Epic internal) Hospital Note record type |
| ECDH | Elliptic-Curve Diffie–Hellman |
| EHI | Electronic Health Information |
| FHIR | Fast Healthcare Interoperability Resources |
| MCP | Model Context Protocol |
| ONC | Office of the National Coordinator for Health IT |
| PHI | Protected Health Information |
| PKCE | Proof Key for Code Exchange |
| ROI | Release of Information (the form patients sign to authorize record release) |
| SMART | Substitutable Medical Apps & Reusable Technologies (FHIR-on-OAuth profile) |
| SSE | Server-Sent Events |
| TSV | Tab-Separated Values |
| USCDI | United States Core Data for Interoperability |
