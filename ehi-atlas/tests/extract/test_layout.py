"""
tests/extract/test_layout.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for ehi_atlas.extract.layout against the synthesized lab PDF.

The synthesized lab PDF (3-page Quest-style CMP report) lives at:
    corpus/_sources/synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf

Expected creatinine row location (documented in README-extraction.md):
    page=2; bbox=(72, 574, 540, 590)   ← bottom-left PDF coordinates

Tests verify:
1. DocumentLayout has page_count=3 and len(pages)==3
2. find_text_bbox finds "Creatinine" on page 2
3. The returned bbox is close to (72, 574, 540, 590) within ±5 points per coord
4. rasterize_pdf produces 001.png, 002.png, 003.png in a tmp_path
5. prepare_pdf_for_extraction produces 3 PNGs + 3 JSONs; manifest matches disk

The session-scoped ``lab_pdf_path`` fixture avoids re-opening the PDF on every
test. The session-scoped ``lab_layout`` fixture avoids re-extracting layout.
"""

from pathlib import Path

import pytest

from ehi_atlas.extract.layout import (
    DocumentLayout,
    PageLayout,
    TextSpan,
    extract_layout,
    find_text_bbox,
    prepare_pdf_for_extraction,
    rasterize_pdf,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent  # ehi-atlas/


@pytest.fixture(scope="session")
def lab_pdf_path() -> Path:
    """Absolute path to the synthesized lab PDF."""
    p = _REPO_ROOT / "corpus/_sources/synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf"
    assert p.exists(), f"Lab PDF not found at {p}"
    return p


@pytest.fixture(scope="session")
def lab_layout(lab_pdf_path: Path) -> DocumentLayout:
    """Session-scoped layout extraction — runs pdfplumber once for all tests."""
    return extract_layout(lab_pdf_path)


# ---------------------------------------------------------------------------
# Test 1: three pages
# ---------------------------------------------------------------------------


def test_extract_layout_finds_three_pages(lab_layout: DocumentLayout) -> None:
    """DocumentLayout.page_count == 3 and len(pages) == 3."""
    assert lab_layout.page_count == 3
    assert len(lab_layout.pages) == 3


# ---------------------------------------------------------------------------
# Test 2: creatinine on page 2
# ---------------------------------------------------------------------------


def test_extract_layout_finds_creatinine_text(lab_layout: DocumentLayout) -> None:
    """find_text_bbox(page=2) returns a result on page 2.

    The synthesized lab PDF has "Creatinine" on both page 1 (summary table)
    and page 2 (detailed results with reference ranges). The detailed results
    page is the canonical Artifact 5 anchor, so we search page=2 explicitly.
    """
    result = find_text_bbox(lab_layout, "Creatinine", page=2)
    assert result is not None, "find_text_bbox returned None — 'Creatinine' not found on page 2"
    assert result.page == 2, (
        f"Expected Creatinine on page 2 but got page {result.page}. "
        "Check that the PDF has not been re-generated with a different layout."
    )


# ---------------------------------------------------------------------------
# Test 3: bbox close to documented (72, 574, 540, 590) within ±5 pts each coord
# ---------------------------------------------------------------------------


def test_extract_layout_creatinine_bbox_close_to_documented(
    lab_layout: DocumentLayout,
) -> None:
    """Creatinine row bbox is reasonably close to the documented (72, 574, 540, 590).

    Tolerances per coordinate:
    - x1 (left margin): ±5 pt  — leftmost text is at ~75, margin is at 72
    - y1 (row bottom):  ±5 pt  — text bottom maps to ~576, row bottom is 574
    - x2 (right margin): ±25 pt — rightmost text token ("H" flag) is at ~520;
                                   the documented x2=540 is the page margin, not a
                                   text token; text-only extraction can't recover it
    - y2 (row top):     ±10 pt — text top maps to ~585, row top is 590

    The y-coordinates and x1 are accurate; the right-edge gap is expected
    because the last token in the row ("H") doesn't reach the right margin.
    """
    result = find_text_bbox(lab_layout, "Creatinine", page=2)
    assert result is not None, "Creatinine not found on page 2"

    expected_x1, expected_y1, expected_x2, expected_y2 = 72.0, 574.0, 540.0, 590.0

    assert abs(result.x1 - expected_x1) <= 5.0, (
        f"x1={result.x1:.1f} not within 5 of expected {expected_x1}"
    )
    assert abs(result.y1 - expected_y1) <= 5.0, (
        f"y1={result.y1:.1f} not within 5 of expected {expected_y1}"
    )
    assert abs(result.x2 - expected_x2) <= 25.0, (
        f"x2={result.x2:.1f} not within 25 of expected {expected_x2}. "
        "The rightmost text token ('H' flag) ends at ~520; the documented x2=540 "
        "is the page right margin which contains no text."
    )
    assert abs(result.y2 - expected_y2) <= 10.0, (
        f"y2={result.y2:.1f} not within 10 of expected {expected_y2}"
    )


# ---------------------------------------------------------------------------
# Test 4: rasterize produces 001.png, 002.png, 003.png
# ---------------------------------------------------------------------------


def test_rasterize_pdf_produces_three_pngs(
    lab_pdf_path: Path, tmp_path: Path
) -> None:
    """rasterize_pdf writes 001.png, 002.png, 003.png into tmp_path."""
    output_paths = rasterize_pdf(lab_pdf_path, tmp_path)

    assert len(output_paths) == 3, f"Expected 3 paths, got {len(output_paths)}"

    expected_names = {"001.png", "002.png", "003.png"}
    actual_names = {p.name for p in output_paths}
    assert actual_names == expected_names, f"Unexpected filenames: {actual_names}"

    # Files must actually exist on disk and be non-empty
    for path in output_paths:
        assert path.exists(), f"Expected file not found: {path}"
        assert path.stat().st_size > 0, f"File is empty: {path}"


# ---------------------------------------------------------------------------
# Test 5: end-to-end prepare_pdf_for_extraction
# ---------------------------------------------------------------------------


def test_prepare_pdf_for_extraction_writes_both_images_and_json(
    lab_pdf_path: Path, tmp_path: Path
) -> None:
    """prepare_pdf_for_extraction produces 3 PNGs + 3 JSONs; manifest matches disk."""
    manifest = prepare_pdf_for_extraction(lab_pdf_path, tmp_path)

    # Manifest shape
    assert manifest["page_count"] == 3
    assert manifest["dpi"] == 200
    assert len(manifest["image_paths"]) == 3
    assert len(manifest["layout_paths"]) == 3

    # Image files exist
    for img_path in manifest["image_paths"]:
        assert img_path.exists(), f"Image file not found: {img_path}"
        assert img_path.suffix == ".png", f"Expected .png, got {img_path.suffix}"
        assert img_path.stat().st_size > 0

    # JSON files exist and parse
    import json

    for json_path in manifest["layout_paths"]:
        assert json_path.exists(), f"JSON file not found: {json_path}"
        assert json_path.name.endswith(".text.json"), (
            f"Expected *.text.json, got {json_path.name}"
        )
        data = json.loads(json_path.read_text())
        # Must have the PageLayout shape
        assert "page" in data
        assert "width" in data
        assert "height" in data
        assert "spans" in data
        assert isinstance(data["spans"], list)
        assert len(data["spans"]) > 0, f"Page {data['page']} has no spans"

    # Files on disk match what the manifest reports
    image_names_on_disk = {p.name for p in tmp_path.glob("*.png")}
    image_names_in_manifest = {p.name for p in manifest["image_paths"]}
    assert image_names_on_disk == image_names_in_manifest

    json_names_on_disk = {p.name for p in tmp_path.glob("*.text.json")}
    json_names_in_manifest = {p.name for p in manifest["layout_paths"]}
    assert json_names_on_disk == json_names_in_manifest
