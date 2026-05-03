# EHI Atlas Console — reusable components
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
