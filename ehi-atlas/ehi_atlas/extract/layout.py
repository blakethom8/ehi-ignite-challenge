"""
ehi_atlas.extract.layout
~~~~~~~~~~~~~~~~~~~~~~~~

PDF layout-extraction module: rasterize pages and extract text + bounding boxes.

This module produces the ``pages/`` artifacts that live alongside each PDF in the
bronze tier::

    bronze/<source>/<patient>/
    ├── data.pdf
    └── pages/
        ├── 001.png          ← rasterized page image (vision LLM input)
        ├── 001.text.json    ← per-token text + bbox (ground-truth strings + layout)
        ├── 002.png
        ├── 002.text.json
        └── ...

These two artifacts are consumed together by task 4.3 (Claude vision wrapper): the
PNG gives the LLM a visual representation while the text JSON provides ground-truth
strings and layout anchors that improve extraction reliability.

Coordinate convention
---------------------
All bounding boxes in this module use **bottom-left origin** (PDF user units,
points at 72 pt/inch), matching the reportlab convention used when the synthesized
lab PDF was generated, and matching the documented bbox format::

    page=2;bbox=72,574,540,590

Fields ``x1, y1, x2, y2`` where:
- ``x1`` = left edge
- ``y1`` = bottom edge  (smaller y = lower on the page)
- ``x2`` = right edge
- ``y2`` = top edge     (larger y = higher on the page)

pdfplumber uses a **top-left origin** internally (its ``top`` attribute is the
distance from the top of the page). The conversion is::

    y1_bl = page_height - char_bottom   # pdfplumber "bottom" → BL "y1"
    y2_bl = page_height - char_top      # pdfplumber "top"    → BL "y2"

Rasterization fallback chain
-----------------------------
1. ``pdf2image.convert_from_path`` — uses poppler (system dep). Fast and accurate.
2. ``pypdfium2`` — pure-Python wheel with bundled binaries. No system deps. Always
   available. Falls back to this automatically if poppler is missing.
3. If both fail, raises ``RuntimeError`` with install instructions.

Install poppler on macOS: ``brew install poppler``
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class TextSpan(BaseModel):
    """A single text span (word/character cluster) with its bounding box.

    Bounding box is in PDF user units (points), bottom-left origin convention.
    """

    text: str
    page: int  # 1-indexed
    # Bbox in PDF user units (points), bottom-left origin
    x1: float
    y1: float  # bottom edge
    x2: float
    y2: float  # top edge
    font_name: str | None = None
    font_size: float | None = None


class PageLayout(BaseModel):
    """Complete layout extraction for one page."""

    page: int  # 1-indexed
    width: float  # in points
    height: float  # in points
    spans: list[TextSpan]


class DocumentLayout(BaseModel):
    """Complete layout extraction for a multi-page document."""

    page_count: int
    pages: list[PageLayout]


# ---------------------------------------------------------------------------
# Rasterization
# ---------------------------------------------------------------------------


def rasterize_pdf(
    pdf_path: Path,
    output_dir: Path,
    *,
    dpi: int = 200,
    image_format: Literal["png", "jpeg"] = "png",
) -> list[Path]:
    """Rasterize each page of the PDF to an image file.

    Returns the list of output paths in page order.
    Output files are named ``<output_dir>/{NNN}.{ext}`` with NNN zero-padded to
    three digits (001, 002, …).

    Fallback chain:
    1. ``pdf2image`` (requires poppler system binary — ``brew install poppler``).
    2. ``pypdfium2`` (pure-Python wheel with bundled binaries; always available).
    3. Raises ``RuntimeError`` if both fail.

    Parameters
    ----------
    pdf_path:
        Path to the source PDF.
    output_dir:
        Directory where image files will be written. Created if absent.
    dpi:
        Render resolution in dots per inch. 200 DPI is a good balance between
        quality and file size for lab reports.
    image_format:
        Output image format. "png" for lossless (default); "jpeg" for smaller files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = image_format.lower()
    pil_format = "PNG" if ext == "png" else "JPEG"

    images = _rasterize_with_fallback(pdf_path, dpi=dpi)

    output_paths: list[Path] = []
    for idx, img in enumerate(images):
        page_num = idx + 1
        out_path = output_dir / f"{page_num:03d}.{ext}"
        img.save(str(out_path), format=pil_format)
        output_paths.append(out_path)

    return output_paths


def _rasterize_with_fallback(pdf_path: Path, *, dpi: int):
    """Return a list of PIL images, one per page. Tries pdf2image then pypdfium2."""
    # Attempt 1: pdf2image (poppler)
    try:
        from pdf2image import convert_from_path
        from pdf2image.exceptions import PDFInfoNotInstalledError

        try:
            return convert_from_path(str(pdf_path), dpi=dpi)
        except PDFInfoNotInstalledError:
            pass  # fall through to pypdfium2
        except Exception as exc:
            # Catch other poppler-related errors by message
            msg = str(exc).lower()
            if "poppler" in msg or "pdfinfo" in msg or "pdftoppm" in msg:
                pass  # fall through to pypdfium2
            else:
                raise
    except ImportError:
        pass  # pdf2image not installed — fall through

    # Attempt 2: pypdfium2 (bundled binaries, always available)
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(pdf_path))
        scale = dpi / 72.0  # PDF user units are 72 pt/inch
        images = []
        for page in doc:
            bitmap = page.render(scale=scale)
            images.append(bitmap.to_pil())
        return images
    except Exception as exc:
        raise RuntimeError(
            f"Both pdf2image and pypdfium2 failed to rasterize {pdf_path}.\n"
            "To use pdf2image (faster): brew install poppler (macOS) or "
            "apt-get install poppler-utils (Ubuntu).\n"
            f"pypdfium2 error: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Text + bbox extraction
# ---------------------------------------------------------------------------


def extract_layout(pdf_path: Path) -> DocumentLayout:
    """Extract text + bounding boxes from every page of the PDF.

    Uses pdfplumber for text-extractable PDFs. Coordinates are converted from
    pdfplumber's top-left origin to bottom-left origin (PDF convention).

    Raises ``ValueError`` if any page has zero extractable text, which signals
    a scanned-image PDF. OCR fallback (e.g. tesseract) is a Phase 2 task.

    Parameters
    ----------
    pdf_path:
        Path to the PDF to extract layout from.
    """
    import pdfplumber

    pages: list[PageLayout] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        total_pages = len(pdf.pages)

        for idx, plumber_page in enumerate(pdf.pages):
            page_num = idx + 1
            page_width = float(plumber_page.width)
            page_height = float(plumber_page.height)

            # extract_words groups adjacent chars into word tokens.
            # extra_attrs pulls font metadata from the underlying char objects.
            words = plumber_page.extract_words(
                extra_attrs=["fontname", "size"],
                keep_blank_chars=False,
                use_text_flow=False,
            )

            if not words:
                raise ValueError(
                    f"Page {page_num} of {pdf_path} has zero extractable text. "
                    "This is likely a scanned-image PDF. "
                    "OCR fallback (tesseract) is Phase 2 work — "
                    "not implemented in this module."
                )

            spans: list[TextSpan] = []
            for word in words:
                # pdfplumber 'top' = distance from top of page (top-left origin)
                # Convert to bottom-left: y1_bl = height - bottom, y2_bl = height - top
                y1_bl = page_height - float(word["bottom"])
                y2_bl = page_height - float(word["top"])

                spans.append(
                    TextSpan(
                        text=word["text"],
                        page=page_num,
                        x1=float(word["x0"]),
                        y1=y1_bl,
                        x2=float(word["x1"]),
                        y2=y2_bl,
                        font_name=word.get("fontname"),
                        font_size=float(word["size"]) if word.get("size") else None,
                    )
                )

            pages.append(
                PageLayout(
                    page=page_num,
                    width=page_width,
                    height=page_height,
                    spans=spans,
                )
            )

    return DocumentLayout(page_count=total_pages, pages=pages)


# ---------------------------------------------------------------------------
# Write layout JSON artifacts
# ---------------------------------------------------------------------------


def write_layout_json(layout: DocumentLayout, output_dir: Path) -> list[Path]:
    """Write per-page layout JSON files alongside the rasterized images.

    For each page, writes ``<output_dir>/{NNN}.text.json`` containing the
    ``PageLayout`` serialized as JSON. Returns list of output paths.

    Parameters
    ----------
    layout:
        The ``DocumentLayout`` returned by :func:`extract_layout`.
    output_dir:
        Directory where JSON files will be written. Created if absent.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []

    for page_layout in layout.pages:
        out_path = output_dir / f"{page_layout.page:03d}.text.json"
        out_path.write_text(
            page_layout.model_dump_json(indent=2),
            encoding="utf-8",
        )
        output_paths.append(out_path)

    return output_paths


# ---------------------------------------------------------------------------
# End-to-end convenience
# ---------------------------------------------------------------------------


def prepare_pdf_for_extraction(
    pdf_path: Path,
    output_dir: Path,
    *,
    dpi: int = 200,
) -> dict:
    """End-to-end: rasterize + extract layout + write artifacts.

    Writes PNG images and ``*.text.json`` files to ``output_dir`` and returns
    a manifest dict::

        {
            "page_count": int,
            "image_paths": [Path, ...],
            "layout_paths": [Path, ...],
            "dpi": int,
        }

    Parameters
    ----------
    pdf_path:
        Path to the source PDF.
    output_dir:
        Directory where all output artifacts are written (created if absent).
    dpi:
        Render resolution for rasterization. Default 200.
    """
    image_paths = rasterize_pdf(pdf_path, output_dir, dpi=dpi)
    layout = extract_layout(pdf_path)
    layout_paths = write_layout_json(layout, output_dir)

    return {
        "page_count": layout.page_count,
        "image_paths": image_paths,
        "layout_paths": layout_paths,
        "dpi": dpi,
    }


# ---------------------------------------------------------------------------
# Bbox detection helper
# ---------------------------------------------------------------------------


def find_text_bbox(
    layout: DocumentLayout,
    text: str,
    *,
    page: int | None = None,
) -> "BBoxResult | None":
    """Find the bounding box of the text row containing a given substring.

    Finds the **first** span whose text contains ``text`` as a substring
    (exact substring match; case-sensitive), then returns the enclosing bbox
    of **all spans on the same row** (same y-band, within ±2 points).

    This returns the full row extent rather than just the matching word, which
    is the behaviour needed to match the documented PDF row bboxes.

    When ``page`` is ``None``, pages are searched in order and the first match
    across the whole document is returned. When ``page`` is given, only that
    page is searched.

    Useful for verifying the synthesized lab PDF: calling::

        find_text_bbox(layout, "Creatinine", page=2)

    should return a bbox close to (72, 574, 540, 590)
    (within ±5 points on each coordinate — the left margin and the "H" flag
    at the far right of the row anchor the x1/x2 bounds).

    Parameters
    ----------
    layout:
        The ``DocumentLayout`` to search.
    text:
        Substring to search for within span text.
    page:
        If given, restrict the search to this 1-indexed page number.

    Returns
    -------
    ``BBoxResult`` with ``page``, ``x1``, ``y1``, ``x2``, ``y2`` in bottom-left
    PDF user units enclosing the full row, or ``None`` if no match found.
    """
    _ROW_TOLERANCE = 2.0  # points; spans within this y-band are considered same row

    for page_layout in layout.pages:
        if page is not None and page_layout.page != page:
            continue
        for span in page_layout.spans:
            if text in span.text:
                # Found the anchor span. Collect all spans on the same row
                # (same y-band: y1 within ±ROW_TOLERANCE of the anchor).
                row_y_center = (span.y1 + span.y2) / 2.0
                row_spans = [
                    s
                    for s in page_layout.spans
                    if abs((s.y1 + s.y2) / 2.0 - row_y_center) <= _ROW_TOLERANCE
                ]
                x1 = min(s.x1 for s in row_spans)
                y1 = min(s.y1 for s in row_spans)
                x2 = max(s.x2 for s in row_spans)
                y2 = max(s.y2 for s in row_spans)
                return BBoxResult(
                    page=page_layout.page,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )

    return None


class BBoxResult:
    """Simple result container for :func:`find_text_bbox`.

    Uses ``BBox`` from ``extract.schemas`` when available. This class is
    intentionally minimal so layout.py can be used before schemas.py lands.
    """

    def __init__(self, *, page: int, x1: float, y1: float, x2: float, y2: float):
        self.page = page
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def to_schemas_bbox(self):
        """Convert to :class:`ehi_atlas.extract.schemas.BBox` if available."""
        try:
            from ehi_atlas.extract.schemas import BBox

            return BBox(page=self.page, x1=self.x1, y1=self.y1, x2=self.x2, y2=self.y2)
        except ImportError:
            return self

    def __repr__(self) -> str:
        return (
            f"BBoxResult(page={self.page}, "
            f"x1={self.x1:.1f}, y1={self.y1:.1f}, "
            f"x2={self.x2:.1f}, y2={self.y2:.1f})"
        )
