"""EHI Atlas Console — PDF Lab page.

Live vision-extraction playground. Upload (or pick from prior uploads / the
rhett759 fixture), inspect the rasterized pages and bbox layer, run the
configured VisionBackend, and see the validated ExtractionResult + the
deterministic FHIR Observation side-by-side.

Run from repo root:
    uv run streamlit run ehi-atlas/app/streamlit_app.py --server.port 8503
Or from inside ehi-atlas/:
    uv run streamlit run app/streamlit_app.py --server.port 8503

Then click into "PDF Lab" in the sidebar.
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

_APP_DIR = Path(__file__).parent.parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import pandas as pd
import pypdfium2 as pdfium
import streamlit as st

from components.badges import engine_badge_row
from components.header import render_header
from ehi_atlas.extract.cache import CacheKey, ExtractionCache, hash_file
from ehi_atlas.extract.layout import extract_layout, find_text_bbox
from ehi_atlas.extract.pdf import (
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    DEFAULT_PROMPT_VERSION,
    DEFAULT_SCHEMA_VERSION,
    extract_lab_pdf,
)
from ehi_atlas.extract.schemas import ExtractionResult
from ehi_atlas.extract.to_fhir import lab_result_to_observation
from ehi_atlas.extract.uploads import (
    UPLOADS_ROOT,
    UploadRecord,
    list_uploads,
    store_upload,
    store_upload_from_path,
)

# ---------------------------------------------------------------------------
# Page config + header
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas — PDF Lab",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header("PDF Lab — Live Vision Extraction")

st.markdown(
    """
**Drop a PDF, watch the pipeline run end-to-end.** The Lab rasterizes each page,
extracts text + bboxes via pdfplumber, calls the configured `VisionBackend` for
structured extraction, and shows you the validated `ExtractionResult` + the
deterministic FHIR Observation it converts to. Live by default — every run hits
the model unless you flip the cache toggle.
"""
)

# ---------------------------------------------------------------------------
# Sidebar — backend + cache controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Engine")
    engine_badge_row(
        [
            ("script", "rasterize + bbox layer"),
            ("llm", f"{DEFAULT_BACKEND}/{DEFAULT_MODEL}"),
            ("script", "FHIR conversion"),
        ]
    )
    st.divider()

    st.markdown("### Backend")
    st.code(f"{DEFAULT_BACKEND} / {DEFAULT_MODEL}", language="text")
    st.caption(
        "Set `EHI_VISION_BACKEND` env var to swap (Gemma 4 backends ship in a "
        "follow-up commit)."
    )

    st.markdown("### Run mode")
    skip_cache = st.toggle(
        "Live every run (skip cache)",
        value=True,
        help=(
            "When on, every Run Extraction click hits the model. "
            "Turn off after review to replay from cache."
        ),
    )

    st.divider()
    st.page_link("streamlit_app.py", label="← Overview", icon="🏠")

# ---------------------------------------------------------------------------
# Source picker — three modes: upload / prior upload / fixture
# ---------------------------------------------------------------------------

# Default fixture path
_FIXTURE_PDF = (
    Path(__file__).resolve().parents[2]
    / "corpus"
    / "_sources"
    / "synthesized-lab-pdf"
    / "raw"
    / "lab-report-2025-09-12-quest.pdf"
)


def _source_options() -> dict[str, dict]:
    """Build the source picker dropdown choices.

    Returns a dict keyed by display label. Each value carries:
      - kind: 'upload' | 'fixture'
      - record: UploadRecord (uploads only)
      - path: Path
    """
    options: dict[str, dict] = {}
    if _FIXTURE_PDF.exists():
        options["Fixture — rhett759 (synthesized Quest lab, 3 pages)"] = {
            "kind": "fixture",
            "path": _FIXTURE_PDF,
        }
    for record in reversed(list_uploads()):  # newest first
        size_kb = record.size_bytes / 1024
        label = (
            f"Upload — {record.label}  ({record.hash_prefix}, {size_kb:.0f} KB)"
        )
        options[label] = {
            "kind": "upload",
            "record": record,
            "path": record.pdf_path,
        }
    return options


st.subheader("1 · Pick a PDF")

up_col, src_col = st.columns([1, 1], gap="large")

with up_col:
    st.markdown("**Upload a new PDF**")
    uploaded = st.file_uploader(
        "Drop a PDF here. It's saved under "
        "`corpus/_sources/uploads/<hash-prefix>/data.pdf` and gitignored.",
        type=["pdf"],
        accept_multiple_files=False,
        label_visibility="visible",
    )
    if uploaded is not None:
        record = store_upload(
            uploaded.getvalue(),
            original_filename=uploaded.name,
            label=uploaded.name,
        )
        st.success(
            f"Saved as `{record.hash_prefix}` "
            f"({record.size_bytes:,} bytes). Selected below."
        )
        st.session_state["selected_source_label"] = (
            f"Upload — {record.label}  "
            f"({record.hash_prefix}, {record.size_bytes / 1024:.0f} KB)"
        )

with src_col:
    st.markdown("**Or pick an existing source**")
    options = _source_options()
    if not options:
        st.warning(
            "No PDFs available. Upload one (left) or place a file at "
            f"`{_FIXTURE_PDF.relative_to(_FIXTURE_PDF.parents[3])}`."
        )
        st.stop()

    selected_label = st.selectbox(
        "Source",
        list(options.keys()),
        index=0,
        key="selected_source_label",
        label_visibility="collapsed",
    )

selected = options.get(selected_label) or next(iter(options.values()))
pdf_path: Path = selected["path"]

st.markdown("")
meta_cols = st.columns(4)
meta_cols[0].metric("File", pdf_path.name, label_visibility="visible")
meta_cols[1].metric("Size", f"{pdf_path.stat().st_size:,} B")
meta_cols[2].metric("SHA-256", hash_file(pdf_path)[:12])
meta_cols[3].metric("Source", selected["kind"])

# ---------------------------------------------------------------------------
# Cached compute helpers (Streamlit re-runs the script on every interaction)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Rasterizing PDF pages…")
def _rasterize_in_memory(pdf_bytes: bytes, dpi: int = 150) -> list[tuple[bytes, tuple[int, int]]]:
    """Render each PDF page to PNG bytes. Returns list of (png_bytes, (w,h))."""
    doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    scale = dpi / 72.0
    out: list[tuple[bytes, tuple[int, int]]] = []
    for page in doc:
        pil = page.render(scale=scale).to_pil()
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        out.append((buf.getvalue(), pil.size))
    return out


@st.cache_data(show_spinner="Extracting text + bbox layer…")
def _layout_for(pdf_path_str: str) -> dict:
    """Return DocumentLayout serialised as a plain dict (for st.cache_data)."""
    layout = extract_layout(Path(pdf_path_str))
    return layout.model_dump()


# ---------------------------------------------------------------------------
# Extraction button + result panels
# ---------------------------------------------------------------------------

st.divider()
st.subheader("2 · Run extraction")

run_col, status_col = st.columns([1, 3])
with run_col:
    run_clicked = st.button("▶ Run extraction", type="primary", use_container_width=True)

# Cache-check status
cache = ExtractionCache()
key = CacheKey(
    file_sha256=hash_file(pdf_path),
    prompt_version=DEFAULT_PROMPT_VERSION,
    schema_version=DEFAULT_SCHEMA_VERSION,
    model_name=f"{DEFAULT_BACKEND}/{DEFAULT_MODEL}",
)
with status_col:
    if cache.has(key):
        st.info(
            f"Cache hit available · key digest `{key.digest()[:12]}…`. "
            f"With **Live every run** {'on' if skip_cache else 'off'}, "
            f"extraction will {'**skip** the cache' if skip_cache else '**use** the cache'}."
        )
    else:
        st.info(
            f"No cache entry · key digest `{key.digest()[:12]}…`. "
            "First run will hit the model."
        )

# State key per-PDF so toggling sources doesn't clobber prior results
_RESULT_KEY = f"extraction_result__{key.digest()}"
_ERROR_KEY = f"extraction_error__{key.digest()}"
_ELAPSED_KEY = f"extraction_elapsed__{key.digest()}"

if run_clicked:
    with st.spinner("Calling vision backend…"):
        try:
            t0 = time.time()
            extraction = extract_lab_pdf(pdf_path, skip_cache=skip_cache)
            st.session_state[_RESULT_KEY] = extraction
            st.session_state[_ERROR_KEY] = None
            st.session_state[_ELAPSED_KEY] = time.time() - t0
        except Exception as exc:  # noqa: BLE001 — surface any error to the UI
            st.session_state[_RESULT_KEY] = None
            st.session_state[_ERROR_KEY] = exc
            st.session_state[_ELAPSED_KEY] = None

extraction = st.session_state.get(_RESULT_KEY)
extraction_error = st.session_state.get(_ERROR_KEY)
extraction_elapsed = st.session_state.get(_ELAPSED_KEY)

if extraction_error is not None:
    st.error(
        f"Extraction failed: **{type(extraction_error).__name__}** — {extraction_error}"
    )
    st.caption(
        "Common causes: `ANTHROPIC_API_KEY` not set in `ehi-atlas/.env`, "
        "network blocked, schema rejected by the model."
    )
elif extraction is not None:
    confidence_pct = extraction.extraction_confidence * 100
    elapsed_str = f"{extraction_elapsed:.2f}s" if extraction_elapsed else "—"
    summary_cols = st.columns(4)
    summary_cols[0].metric("Status", "✓ extracted")
    summary_cols[1].metric("Latency", elapsed_str)
    summary_cols[2].metric("Confidence", f"{confidence_pct:.0f}%")
    summary_cols[3].metric("Model", extraction.extraction_model)

# ---------------------------------------------------------------------------
# Four-panel display (always shown; populated when data is available)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("3 · Inspect")

# Pre-compute rasterization + layout (cached by st.cache_data on bytes/path)
pdf_bytes = pdf_path.read_bytes()
pages = _rasterize_in_memory(pdf_bytes)
layout_dict = _layout_for(str(pdf_path))
n_pages = len(pages)

selected_page = st.number_input(
    "Page",
    min_value=1,
    max_value=n_pages,
    value=min(2, n_pages),
    step=1,
    help="Which page to focus the inspection panels on.",
)

tab_pages, tab_layout, tab_extract, tab_fhir = st.tabs(
    ["📄 Pages", "🔤 Text + bbox", "🤖 ExtractionResult", "🧬 FHIR Observation"]
)

# --- Panel 1: rasterized pages strip + focus page ----------------------------

with tab_pages:
    st.markdown(
        f"Rasterized at 150 DPI via pypdfium2. **Page {selected_page} of {n_pages}** in focus."
    )
    main_col, strip_col = st.columns([3, 1], gap="small")
    with main_col:
        png_bytes, (w, h) = pages[selected_page - 1]
        st.image(png_bytes, caption=f"Page {selected_page} ({w}×{h} px)", use_column_width=True)
    with strip_col:
        for i, (b, _) in enumerate(pages, start=1):
            st.image(b, caption=f"p.{i}", use_column_width=True)

# --- Panel 2: text + bbox table ----------------------------------------------

with tab_layout:
    page_layout = layout_dict["pages"][selected_page - 1]
    spans = page_layout["spans"]
    st.markdown(
        f"Page {selected_page}: **{len(spans)} spans** · "
        f"{page_layout['width']:.0f} × {page_layout['height']:.0f} pt "
        f"(bottom-left origin)"
    )
    if spans:
        df = pd.DataFrame(
            [
                {
                    "text": s["text"],
                    "x1": round(s["x1"], 1),
                    "y1": round(s["y1"], 1),
                    "x2": round(s["x2"], 1),
                    "y2": round(s["y2"], 1),
                    "font": s.get("font_name") or "—",
                    "size": round(s["font_size"], 1) if s.get("font_size") else None,
                }
                for s in spans
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True, height=420)
    else:
        st.warning("No text spans extracted from this page (scanned image?).")

    # Anchor lookup helper
    st.divider()
    st.markdown("**Find a phrase**")
    anchor = st.text_input(
        "Locate the bbox of any text on this page (case-insensitive substring).",
        value="Creatinine" if pdf_path.name == _FIXTURE_PDF.name else "",
        placeholder="e.g. Creatinine",
    )
    if anchor:
        from ehi_atlas.extract.layout import DocumentLayout

        full_layout = DocumentLayout.model_validate(layout_dict)
        result = find_text_bbox(full_layout, anchor, page=selected_page)
        if result is None:
            st.warning(f"'{anchor}' not found on page {selected_page}.")
        else:
            bbox = result.to_schemas_bbox()
            st.success(f"Found: `{bbox.to_locator_string()}`")

# --- Panel 3: validated ExtractionResult -------------------------------------

with tab_extract:
    if extraction is None:
        st.info(
            "Click **Run extraction** to populate this panel with the model's "
            "validated `ExtractionResult`."
        )
    else:
        doc = extraction.document
        st.markdown(f"**Document type:** `{doc.document_type}`")
        st.markdown(
            f"**Extraction model:** `{extraction.extraction_model}` · "
            f"**prompt:** `{extraction.extraction_prompt_version}` · "
            f"**confidence:** {extraction.extraction_confidence:.2f}"
        )
        if doc.document_type == "lab-report":
            st.markdown(
                f"**Lab:** {doc.lab_name or '—'} · "
                f"**Document date:** {doc.document_date or '—'} · "
                f"**Patient on report:** {doc.patient_name_seen or '—'}"
            )
            if doc.results:
                rows = [
                    {
                        "test_name": r.test_name,
                        "loinc": r.loinc_code or "—",
                        "value": r.value_quantity if r.value_quantity is not None else r.value_string,
                        "unit": r.unit or "—",
                        "ref_low": r.reference_range_low,
                        "ref_high": r.reference_range_high,
                        "flag": r.flag or "—",
                        "page": r.bbox.page,
                        "bbox": r.bbox.to_locator_string(),
                    }
                    for r in doc.results
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("No lab results in the extraction.")
        else:
            st.markdown("**Clinical-note extraction:**")
            if doc.extracted_conditions:
                st.markdown(f"- {len(doc.extracted_conditions)} condition(s)")
            if doc.extracted_symptoms:
                st.markdown(f"- {len(doc.extracted_symptoms)} symptom(s)")

        with st.expander("Raw validated JSON", expanded=False):
            st.json(extraction.model_dump())

# --- Panel 4: FHIR Observation conversion ------------------------------------

with tab_fhir:
    if extraction is None:
        st.info(
            "FHIR conversion runs after a successful extraction. Click "
            "**Run extraction** above first."
        )
    else:
        doc = extraction.document
        if doc.document_type != "lab-report":
            st.info(
                "FHIR conversion in this Lab is wired for lab-report results today. "
                "Conditions / symptoms route through `harmonize/` later in the pipeline."
            )
        elif not doc.results:
            st.info("No lab results in the extraction — nothing to convert.")
        else:
            patient_id = (
                "rhett759" if pdf_path.name == _FIXTURE_PDF.name else "unknown"
            )
            for i, result in enumerate(doc.results):
                with st.expander(
                    f"Observation {i + 1}: {result.test_name} = "
                    f"{result.value_quantity} {result.unit or ''}",
                    expanded=(i == 0),
                ):
                    obs = lab_result_to_observation(
                        result=result,
                        patient_id=patient_id,
                        source_attachment_id=pdf_path.stem,
                        model=extraction.extraction_model,
                        prompt_version=extraction.extraction_prompt_version,
                        confidence=extraction.extraction_confidence,
                    )
                    meta_exts = obs.get("meta", {}).get("extension", [])
                    locator = next(
                        (
                            e.get("valueString")
                            for e in meta_exts
                            if "source-locator" in e.get("url", "")
                        ),
                        None,
                    )
                    sub_cols = st.columns(3)
                    sub_cols[0].metric("resourceType", obs.get("resourceType", "—"))
                    sub_cols[1].metric("valueQuantity", str(obs.get("valueQuantity", "—")))
                    sub_cols[2].metric("source-locator", locator or "—")
                    st.caption(
                        f"meta.extension count: {len(meta_exts)} · "
                        f"types: {[e['url'].split('/')[-1] for e in meta_exts]}"
                    )
                    st.json(obs)

# ---------------------------------------------------------------------------
# Footer — what to read next
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Notebook walkthrough: "
    "[`notebooks/03_layer2b_vision_extraction.ipynb`](../notebooks/03_layer2b_vision_extraction.ipynb)"
    " · "
    "Backend abstraction: `ehi_atlas/extract/pdf.py` (`VisionBackend` Protocol)"
    " · "
    "Uploads dropbox: `corpus/_sources/uploads/` (gitignored)"
)
