# EHI Atlas — Makefile
# Standard tasks for building, testing, and running the harmonizer.

.PHONY: help install corpus ingest standardize harmonize pipeline test test-fast clean validate-gate

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

install:  ## Sync uv environment + dev deps
	uv sync --all-extras
	@echo "✓ environment ready"

# ---- Corpus assembly (Stage 1) ----

corpus:  ## Build the bronze tier from _sources/
	uv run ehi-atlas corpus build

corpus-status:  ## Show what's present and missing in the corpus
	uv run ehi-atlas corpus status

validate-gate:  ## Verify privacy gate: no personal raw data committed
	@bash scripts/validate-privacy-gate.sh

# ---- Pipeline stages ----

ingest:  ## Layer 1: source → bronze (per-source adapters)
	uv run ehi-atlas ingest --all

standardize:  ## Layer 2: bronze → silver (FHIR R4 Bundles)
	uv run ehi-atlas standardize --all

extract:  ## Layer 2-B: vision extraction for unstructured sources
	uv run ehi-atlas extract --all

harmonize:  ## Layer 3: silver → gold (cross-source merged FHIR + Provenance)
	uv run ehi-atlas harmonize --patient showcase

pipeline:  ## End-to-end: ingest → standardize → extract → harmonize
	uv run ehi-atlas pipeline --patient showcase

# ---- Testing ----

test:  ## Run the full test suite
	uv run pytest tests/ -v

test-fast:  ## Run only fast tests (skip integration)
	uv run pytest tests/ -v -m "not integration"

test-showcase:  ## Run the 5-artifact integration test on the showcase patient
	uv run pytest tests/harmonize/test_showcase_patient.py -v

# ---- Maintenance ----

clean:  ## Remove caches and tier outputs (preserves _sources/)
	rm -rf corpus/bronze corpus/silver corpus/gold
	rm -rf ehi_atlas/extract/.cache .extraction-cache
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ cleaned"

lint:  ## Run ruff
	uv run ruff check ehi_atlas/ tests/

format:  ## Format with ruff
	uv run ruff format ehi_atlas/ tests/
