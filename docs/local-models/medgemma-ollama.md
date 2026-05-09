# MedGemma 4B via Ollama — Local PDF Extraction Lab

Status: integrated benchmark path.

## Why this exists

This is a local extraction path for the EHI Ignite PDF work. It is additive:
we are not replacing existing pipelines. The goal is an iterative workspace
where multiple parser variants can run side-by-side, be measured, and feed the
same harmonization layer so PDF parsing and record reconciliation improve
together. The local MedGemma/Gemma work now has two integration levels:

1. `medgemma-ollama` — isolated lab/vitals benchmark pipeline.
2. `gemma-ollama` — shared `VisionBackend` for the main processor, usable by `multipass-fhir` pass overrides.

## Local model storage

Ollama stores model weights outside the repo:

```text
~/.ollama/models/
```

Current local model:

```bash
ollama list
ollama show medgemma:4b
```

The EHI repo should not store model weights. It only stores integration code, prompts, benchmark scripts, and non-PHI fixtures.

## Pipeline location

```text
lib/extract/pipelines/medgemma_ollama.py
```

Registered pipeline name:

```text
medgemma-ollama
```

Shared backend name:

```text
gemma-ollama
```

Main multipass bake-off variant:

```text
multipass-fhir-ollama-tabular
```

Lab pipeline architecture:

```text
PDF → page PNGs → Ollama MedGemma vision call/page → strict JSON → FHIR Observation Bundle
```

Main processor architecture:

```text
PDF → multipass-fhir
  Claude: document context, narrative, identity-heavy passes
  Ollama: medications, immunizations, lab observations, vital signs
  → FHIR Bundle → existing harmonization layer
```

The shared backend uses Ollama's `/api/generate` endpoint with the Pydantic schema passed through the `format` field for structured JSON output. It rasterizes PDF pages locally, chunks long PDFs, and validates returned JSON through the existing Pydantic schemas.

## First benchmark scope

Labs/vitals only. This is deliberate:

- bounded extraction target
- easy to score against known lab PDFs
- directly useful for cross-source harmonization
- avoids asking a 4B local model to solve the whole clinical-document problem on day one

## How to start Ollama

Temporary foreground-style server:

```bash
OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" ollama serve
```

Installed model:

```bash
ollama pull medgemma:4b
```

## App/UI note

Ollama itself is primarily a daemon + CLI + HTTP API, not a full frontend product. For a UI, use one of:

- **Ollama Desktop / native app** if installed separately
- **Open WebUI** for a ChatGPT-style local web UI
- **LM Studio** as an alternate local-model app with UI
- Our own EHI frontend, calling the local backend once wired

For this project, the important surface is the HTTP API at:

```text
http://127.0.0.1:11434
```

## Next implementation steps

1. Run `multipass-fhir-ollama-tabular` alongside the existing pipelines on the same Cedars and Function Health PDFs.
2. Capture F1 / latency / resource counts / harmonization impact in `docs/architecture/PIPELINE-LOG.md`.
3. Add caching for the standalone `medgemma-ollama` lab pipeline if it remains useful after the multipass bake-off.
4. If 4B is weak, test page cropping / OCR-assisted prompts before jumping to larger local models.
5. Add OCR/text-first variants after measuring Docling / Marker / MinerU / Mistral-style raw text quality against our actual PDFs.

## Running the local tabular variant

```bash
OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" ollama serve
ollama pull medgemma:4b
```

Set a different local model tag if needed:

```bash
export EHI_OLLAMA_VISION_MODEL="gemma4:e4b"
```

The registered pipeline name for the bake-off harness is:

```text
multipass-fhir-ollama-tabular
```
