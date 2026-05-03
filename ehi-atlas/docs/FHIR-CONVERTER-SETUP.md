# FHIR-Converter Setup

> Layer 2 CCDA → FHIR R4 conversion requires Microsoft FHIR-Converter.
> Layer 1 (the adapter) ships without it — the probe is informational.

---

## Why Microsoft FHIR-Converter?

Per **Decision D1** in [`docs/mapping-decisions.md`](mapping-decisions.md):

> Wrap the Microsoft FHIR-Converter CLI as a subprocess. Do not port Liquid
> templates inline.

Microsoft's converter ships battle-tested Liquid templates that implement the
published CCDA → FHIR mapping IG. The alternatives (LinuxForHealth, older
pure-Python libraries) have patchier coverage, smaller communities, and require
ongoing maintenance of the template logic.

The subprocess interface is intentionally thin: one Python file
(`ehi_atlas/standardize/ccda_to_fhir.py`, a Stage 2 deliverable) wraps the
CLI call. Replacing the converter later is a single-file change.

---

## Install paths

### Recommended — npm global install (requires Node.js 18+)

```bash
# Verify Node.js version (must be >= 18)
node --version

# Install the converter globally
npm install -g @microsoft/fhir-converter

# Confirm it is on PATH
fhir-converter --version
```

The `fhir-converter` binary will be available on your PATH after this step.
The EHI Atlas adapter calls it as `fhir-converter --version` first, then falls
back to the `npx` form if the global binary is not found.

### Alternative — clone and build from source

For environments where global npm installs are restricted:

```bash
git clone https://github.com/microsoft/FHIR-Converter.git
cd FHIR-Converter
npm ci
npm run build
# The built CLI lives at node_modules/.bin/fhir-converter or similar.
# Add it to PATH, or set FHIR_CONVERTER_BIN in your environment for the
# Layer 2 standardize function to pick up.
```

See the upstream repo for build prerequisites and release notes:
<https://github.com/microsoft/FHIR-Converter>

---

## How the adapter probes for it

`ehi_atlas/adapters/ccda.py` contains `_probe_fhir_converter()`, a cached
subprocess probe that runs at validate() time:

1. Try `fhir-converter --version` (standalone global CLI)
2. Try `npx @microsoft/fhir-converter --version` (via npx, no install required)
3. If both fail, return `(False, "<install instructions>")`

The result is cached with `@lru_cache` for the lifetime of the process so
repeated `validate()` calls don't fork a subprocess on every invocation.

### Interpreting the validate() output

When FHIR-Converter is **not installed**, `validate()` returns a list
containing one string prefixed with `"warning:"`:

```
warning: FHIR-Converter unavailable (Layer 2 conversion will fail). ...
```

The `"warning:"` prefix follows the same convention as `BundleValidator` (see
`docs/ADAPTER-CONTRACT.md`): warnings are non-fatal and do not block the Layer 1
pipeline. The Layer 2 standardize function will hard-fail if the tool is absent.

When FHIR-Converter **is installed**, the warning is absent and `validate()`
returns `[]` for a structurally valid CCDA document.

---

## Phase 1 fallback

If FHIR-Converter is not installed at submission time:

- The CCDA **Layer 1 adapter** (bronze copy) ships and works fully — no Node.js
  dependency at Layer 1.
- The CCDA **Layer 2 standardize** step (CCDA → FHIR R4 conversion) becomes a
  Phase 2 deliverable.
- The 5-source showcase demo can run on the other four sources
  (Synthea, Synthea-payer, Epic EHI projection, Lab PDF) without the Cerner
  CCDA FHIR bundle.
- The bronze `corpus/bronze/ccda/rhett759/data.xml` record still exists and is
  hashed — Layer 3 harmonization can include it once Layer 2 is unblocked.

This ensures Phase 1 is not blocked by the Node.js toolchain dependency.
