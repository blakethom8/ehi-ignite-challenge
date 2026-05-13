# C-CDA Harmonization

Status: implementation slice, 2026-05-09

## Goal

C-CDA is a source input, not a package-only artifact. Uploaded C-CDA XML should enter the same harmonization spine as FHIR pulls and extracted PDFs:

1. Source Intake stores the original XML.
2. Harmonize discovers the XML as a `ccda-xml` source.
3. The source is converted to FHIR-shaped resources.
4. Patient identity is compared against the workspace baseline.
5. Matching sources contribute facts to merge/review/export.
6. Mismatched sources are retained in the source manifest but excluded from canonical facts.

## Converter Boundary

The adapter lives in `api/core/ccda.py`.

Preferred converter:

- Microsoft FHIR-Converter API/container
- Microsoft FHIR-Converter local CLI

Fallback converter:

- deterministic local parser for Patient, DocumentReference, Problems, and Medications

The fallback exists so development and tests still work without a running converter. It is not a full C-CDA implementation.

## Runtime Configuration

Hosted/container API mode:

```bash
export FHIR_CONVERTER_URL="http://localhost:18080"
export FHIR_CONVERTER_API_VERSION="2024-05-01-preview"
# optional
export FHIR_CONVERTER_BEARER_TOKEN="..."
export FHIR_CONVERTER_TIMEOUT_SECONDS="30"
```

On Hetzner, the production API uses `http://fhir-converter:8080` on the private Docker network. Local development can use the same long-running converter through an SSH tunnel to the localhost-only host binding:

```bash
ssh -L 18080:127.0.0.1:18080 hetzner2
```

Local CLI mode:

```bash
export FHIR_CONVERTER_BIN="/path/to/Microsoft.Health.Fhir.Liquid.Converter.Tool"
export FHIR_CONVERTER_TEMPLATE_DIR="/path/to/FHIR-Converter/data/Templates/Ccda"
export FHIR_CONVERTER_TIMEOUT_SECONDS="30"
```

Optional hard-fail mode:

```bash
export FHIR_CONVERTER_REQUIRED=true
```

By default, converter failures fall back to the local parser. With `FHIR_CONVERTER_REQUIRED=true`, converter failures raise instead.

## Data Contract

`convert_ccda_to_fhir_bundle(path, source_id)` returns a FHIR Bundle. The harmonizer flattens that bundle into the existing `{resourceType: [resources]}` contract used by FHIR and PDF sources.

Every converted resource receives a source tag:

```json
{
  "system": "https://ehi-atlas.example/fhir/source-kind",
  "code": "ccda"
}
```

If the converter output lacks a `DocumentReference`, the adapter adds one pointing back to the original XML.

## Identity Gate

For patient workspaces with a non-C-CDA baseline Patient, C-CDA resources are excluded if the converted C-CDA Patient conflicts on:

- birth date
- gender
- family name
- first initial of given name

Excluded sources appear in `/api/harmonize/{collection_id}/sources` as:

```json
{
  "kind": "ccda-xml",
  "status": "identity_mismatch"
}
```

This prevents a public/sample C-CDA from being merged into a different patient's package.

## Export Rule

Workspace export consumes the harmonize collection registry and loaded resources. It no longer accepts package-only extra C-CDA sources. If a C-CDA should appear in an export, it must first be a harmonized source.

## References

- Deployment posture: `docs/architecture/deployment/FHIR-CONVERTER-DEPLOYMENT.md`
- Microsoft FHIR-Converter: https://github.com/microsoft/FHIR-Converter
- Microsoft converter API docs: https://raw.githubusercontent.com/microsoft/FHIR-Converter/main/docs/how-to-guides/use-convert-web-apis.md
- HL7 C-CDA on FHIR IG: https://hl7.org/fhir/us/ccda/
