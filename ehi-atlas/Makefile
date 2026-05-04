# EHI Atlas — Makefile
# Live targets only. The 5-layer pipeline targets (ingest/standardize/
# harmonize/pipeline) were archived in May 2026; see
# `archive/ehi-atlas-5layer/`.

.PHONY: help install console test test-fast clean lint format validate-gate

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

install:  ## Sync uv environment + dev deps
	uv sync --all-extras
	@echo "✓ environment ready"

console:  ## Launch the EHI Atlas Streamlit console (PDF Lab, PDF Compare, Pipeline Bakeoff)
	uv run streamlit run app/streamlit_app.py --server.port 8503

validate-gate:  ## Verify privacy gate: no personal raw data committed
	@bash scripts/validate-privacy-gate.sh

test:  ## Run the full test suite
	uv run pytest tests/ -v

test-fast:  ## Run tests, skipping integration markers
	uv run pytest tests/ -v -m "not integration"

clean:  ## Remove caches and ephemeral outputs (preserves _sources/ and bronze/)
	rm -rf ehi_atlas/extract/.cache .extraction-cache
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ cleaned"

lint:  ## Run ruff
	uv run ruff check ehi_atlas/ tests/

format:  ## Format with ruff
	uv run ruff format ehi_atlas/ tests/
