# EHI Atlas Console — reusable components
#
# Side effect: load credentials from the repo-root .env on first import so
# every page in the app picks up ANTHROPIC_API_KEY / GOOGLE_API_KEY from the
# same place the API server reads them from. Streamlit's multi-page model
# means a user can navigate directly to any page without first hitting
# streamlit_app.py, so we have to be defensive about where dotenv runs.
import os as _os
from pathlib import Path as _Path

try:
    from dotenv import load_dotenv as _load_dotenv

    # ehi-atlas/app/components/__init__.py → parents[3] = repo root
    _REPO_ROOT = _Path(__file__).resolve().parents[3]
    _ENV_FILE = _REPO_ROOT / ".env"
    if _ENV_FILE.exists():
        # override=True: parent processes (Claude Code launcher, shell rc, etc)
        # sometimes inject empty-string ANTHROPIC_API_KEY / GOOGLE_API_KEY,
        # and override=False would treat that as "already set" and skip the
        # real value in .env. The .env is canonical for this project.
        _load_dotenv(_ENV_FILE, override=True)
except ImportError:
    # python-dotenv not installed — caller must export env vars themselves
    pass

from .badges import engine_badge, engine_badge_row
from .header import render_header
from .pipeline_diagram import render_pipeline_diagram
from .corpus_loader import (
    load_manifest,
    load_gold_bundle,
    load_provenance,
    load_bronze_metadata,
    count_bronze_records,
    list_bronze_sources,
    CORPUS_ROOT,
    GOLD_PATIENT_DIR,
)

__all__ = [
    "engine_badge",
    "engine_badge_row",
    "render_header",
    "render_pipeline_diagram",
    "load_manifest",
    "load_gold_bundle",
    "load_provenance",
    "load_bronze_metadata",
    "count_bronze_records",
    "list_bronze_sources",
    "CORPUS_ROOT",
    "GOLD_PATIENT_DIR",
]
