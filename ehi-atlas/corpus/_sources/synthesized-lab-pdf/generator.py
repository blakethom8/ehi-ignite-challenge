"""
generator.py — Synthesized Quest-style lab report PDF for EHI Atlas showcase patient.

PURPOSE
-------
This script produces a deterministic, multi-page PDF that mimics the visual style of
a Quest Diagnostics lab report. It is NOT a real report and contains entirely synthetic
data for the Synthea-generated showcase patient Rhett759_Rohan584.

WHY WE SYNTHESIZE
-----------------
Real lab PDFs contain PHI (Protected Health Information). A synthetic equivalent lets us:
  - Demonstrate Layer 2-B vision extraction publicly with no privacy concerns
  - Have deterministic, reproducible test inputs (byte-identical on every run)
  - Plant the cross-source merge artifact (Artifact 5: creatinine 1.4 mg/dL, 2025-09-12)
  - Iterate on extraction prompts in notebooks without leaking PHI

This is Artifact 5 in the showcase patient construction recipe. The creatinine row
(LOINC 2160-0, 1.4 mg/dL, 2025-09-12) on page 2 at bbox (72, 574, 540, 590) is the
documented anchor for the vision-extraction pipeline and the Sources panel highlight overlay.

HOW TO REGENERATE
-----------------
Dependencies: reportlab (add to pyproject.toml if missing)

    cd ehi-atlas/corpus/_sources/synthesized-lab-pdf/
    python generator.py
    # → produces raw/lab-report-2025-09-12-quest.pdf

The output is byte-identical across runs because:
  - SOURCE_DATE_EPOCH is set to a fixed epoch (946684800 = 2000-01-01T00:00:00Z) before
    calling reportlab, which suppresses ReportLab's runtime timestamp embedding.
  - No random values or runtime timestamps are embedded anywhere else.
  - Font sizes, colors, and layout constants are all fixed.

CREATININE BBOX (the key technical guarantee)
---------------------------------------------
Page: 2 (1-indexed)
Bounding box (PDF user units / points): x1=72, y1=302, x2=540, y2=318
The row cell containing just the result value (1.4) sits at: x1=260, y1=302, x2=330, y2=318
Full row span for highlight overlay: x1=72, y1=302, x2=540, y2=318
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# DETERMINISM: set SOURCE_DATE_EPOCH before importing reportlab.
# ReportLab reads this env var in TimeStamp.__init__ to suppress runtime
# timestamps in the PDF binary, ensuring byte-identical output on every run.
# Value: 946684800 = 2000-01-01T00:00:00 UTC (arbitrary fixed epoch).
# ---------------------------------------------------------------------------
os.environ.setdefault("SOURCE_DATE_EPOCH", "946684800")

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

# ---------------------------------------------------------------------------
# CONSTANTS — all fixed; no randomness
# ---------------------------------------------------------------------------

# Page geometry
PAGE_W, PAGE_H = letter  # 612 x 792 points

# Fixed PDF creation timestamp (determinism: never use datetime.now())
PDF_CREATION_DATE = "D:20251013080000+00'00'"
PDF_AUTHOR = "EHI Atlas Synthetic Data Generator v0.1.0"

# Patient demographics — Rhett759_Rohan584 (Synthea-generated, fully synthetic)
PATIENT_NAME = "ROHAN, RHETT"
PATIENT_DOB = "03/14/1948"  # Age ~77 at specimen date, consistent with lung cancer profile
PATIENT_AGE = "77"
PATIENT_SEX = "Male"
PATIENT_MRN = "MRN-SYNTH-759584"
PATIENT_ACCT = "ACCT-20250911-0031"

# Specimen info
SPECIMEN_COLLECTED = "09/11/2025  07:23"
SPECIMEN_RECEIVED = "09/12/2025  06:41"
SPECIMEN_REPORTED = "09/12/2025  09:17"
SPECIMEN_TYPE = "Serum"
SPECIMEN_ID = "Q25-091100-4421"

# Lab / ordering info
LAB_NAME = "Quest Diagnostics Incorporated"
LAB_ADDRESS = "1 Malcolm Avenue, Teterboro, NJ 07608"
LAB_PHONE = "(800) 222-0446"
LAB_CLIA = "31D0648358"
ORDERING_PROVIDER = "Dr. Esperanza Villanueva, MD"
ORDERING_NPI = "1234567890"
ORDERING_FACILITY = "Coastal Health Partners"
ORDERING_ADDRESS = "4820 Coastal Hwy, Suite 210, Monterey, CA 93940"

# Report header
REPORT_DATE = "09/12/2025"
REPORT_TITLE = "COMPREHENSIVE METABOLIC PANEL"
REPORT_ACCESSION = "Q25-091100-4421"

# ---------------------------------------------------------------------------
# LAB VALUES — 14-item Comprehensive Metabolic Panel (CMP)
# Each tuple: (test_name, loinc, result, units, ref_range_low, ref_range_high, flag)
# flag: "H" = high, "L" = low, "" = normal
# ---------------------------------------------------------------------------
CMP_VALUES = [
    # name,                    loinc,    result, units,    lo,   hi,    flag
    ("Glucose",               "2345-7",  "102",  "mg/dL",  70,   99,    "H"),
    ("BUN (Blood Urea Nitrogen)", "3094-0", "22", "mg/dL",  7,   25,    ""),
    ("Creatinine",            "2160-0",  "1.4",  "mg/dL",  0.6,  1.3,   "H"),
    ("eGFR (CKD-EPI)",        "62238-1", "54",   "mL/min/1.73m2", 60, 999, "L"),
    ("Sodium",                "2951-2",  "139",  "mEq/L",  136, 145,   ""),
    ("Potassium",             "2823-3",  "4.1",  "mEq/L",  3.5,  5.1,   ""),
    ("Chloride",              "2075-0",  "101",  "mEq/L",   98, 107,   ""),
    ("CO2 (Bicarbonate)",     "2028-9",   "24",  "mEq/L",   22,  29,   ""),
    ("Calcium",               "17861-6",  "9.2", "mg/dL",  8.5, 10.2,  ""),
    ("Total Protein",         "2885-2",   "6.8", "g/dL",   6.3,  8.2,  ""),
    ("Albumin",               "1751-7",   "3.9", "g/dL",   3.5,  5.0,  ""),
    ("ALT (SGPT)",            "1742-6",   "31",  "U/L",      7,   56,  ""),
    ("AST (SGOT)",            "1920-8",   "38",  "U/L",     10,   40,  ""),
    ("Alkaline Phosphatase",  "6768-6",   "88",  "U/L",     44,  147,  ""),
    ("Total Bilirubin",       "1975-2",   "0.7", "mg/dL",  0.2,  1.2,  ""),
]

# Index of creatinine in CMP_VALUES (0-based) — used to compute bbox
CREATININE_IDX = 2  # third row (0-indexed)

# ---------------------------------------------------------------------------
# LAYOUT CONSTANTS for page 2 results table
# These are fixed so the creatinine bbox is deterministic and documentable.
# ---------------------------------------------------------------------------

# Table origin on page 2
TABLE_X = 72.0            # left margin (1 inch)
TABLE_TOP_Y = 640.0       # y of top edge of table header row (from bottom of page)

# Row geometry
ROW_HEIGHT = 16.0         # points per row
HEADER_ROW_H = 18.0       # slightly taller header

# Column widths (must sum to PAGE_W - 2*TABLE_X = 468 pts)
COL_TEST_W  = 200.0       # Test name
COL_RESULT_W = 70.0       # Result value
COL_UNITS_W  = 90.0       # Units
COL_RANGE_W  = 78.0       # Reference range
COL_FLAG_W   = 30.0       # Flag
# Total: 200+70+90+78+30 = 468 ✓

# Column x positions (left edge of each cell)
COL_X = {
    "test":   TABLE_X,
    "result": TABLE_X + COL_TEST_W,
    "units":  TABLE_X + COL_TEST_W + COL_RESULT_W,
    "range":  TABLE_X + COL_TEST_W + COL_RESULT_W + COL_UNITS_W,
    "flag":   TABLE_X + COL_TEST_W + COL_RESULT_W + COL_UNITS_W + COL_RANGE_W,
}

# Creatinine row y-position:
# Header row + data rows above creatinine (CREATININE_IDX rows)
# Y in ReportLab: 0 = bottom of page; rows are drawn top-down so y decreases.
# Row top-y = TABLE_TOP_Y - HEADER_ROW_H - (CREATININE_IDX * ROW_HEIGHT)
# Row bottom-y = row top-y - ROW_HEIGHT
CREATININE_ROW_TOP_Y    = TABLE_TOP_Y - HEADER_ROW_H - (CREATININE_IDX * ROW_HEIGHT)
CREATININE_ROW_BOTTOM_Y = CREATININE_ROW_TOP_Y - ROW_HEIGHT

# The documented bbox for the creatinine ROW (full row span):
# x1, y1, x2, y2  (PDF user units, origin at bottom-left of page)
# y1 = bottom of row, y2 = top of row
CREATININE_BBOX = (
    int(TABLE_X),                            # x1
    int(CREATININE_ROW_BOTTOM_Y),            # y1 (bottom edge)
    int(TABLE_X + COL_TEST_W + COL_RESULT_W + COL_UNITS_W + COL_RANGE_W + COL_FLAG_W),  # x2
    int(CREATININE_ROW_TOP_Y),               # y2 (top edge)
)

# source-locator Extension value (matches PROVENANCE-SPEC.md format)
SOURCE_LOCATOR = f"page=2;bbox={CREATININE_BBOX[0]},{CREATININE_BBOX[1]},{CREATININE_BBOX[2]},{CREATININE_BBOX[3]}"

# ---------------------------------------------------------------------------
# COLORS
# ---------------------------------------------------------------------------
QUEST_BLUE = colors.HexColor("#003DA5")
QUEST_LIGHT_BLUE = colors.HexColor("#E8EEF7")
FLAG_RED = colors.HexColor("#CC0000")
FLAG_ORANGE = colors.HexColor("#CC6600")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY = colors.HexColor("#CCCCCC")
DARK_GRAY = colors.HexColor("#333333")
WHITE = colors.white
BLACK = colors.black

# ---------------------------------------------------------------------------
# FONTS — standard Helvetica (always available in ReportLab; no external files)
# ---------------------------------------------------------------------------
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"


# ===========================================================================
# PAGE 1 helpers
# ===========================================================================

def draw_page1_header(c: canvas.Canvas) -> None:
    """Header bar with Quest logo placeholder and lab address."""
    # Blue header bar
    c.setFillColor(QUEST_BLUE)
    c.rect(0, PAGE_H - 72, PAGE_W, 72, fill=1, stroke=0)

    # Logo placeholder text
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 20)
    c.drawString(36, PAGE_H - 42, "Quest Diagnostics")
    c.setFont(FONT_REGULAR, 9)
    c.drawString(36, PAGE_H - 58, "Incorporated  ·  Accreditations: CAP, CLIA, ISO 15189")

    # Lab address (right-aligned)
    c.setFont(FONT_REGULAR, 8)
    c.drawRightString(PAGE_W - 36, PAGE_H - 36, LAB_NAME)
    c.drawRightString(PAGE_W - 36, PAGE_H - 47, LAB_ADDRESS)
    c.drawRightString(PAGE_W - 36, PAGE_H - 58, f"Phone: {LAB_PHONE}  ·  CLIA: {LAB_CLIA}")


def draw_page1_patient_box(c: canvas.Canvas) -> None:
    """Patient demographics and specimen info boxes."""
    box_top = PAGE_H - 90
    box_h = 90

    # Left box: patient info
    left_x = 36
    box_w = (PAGE_W - 72) / 2 - 6

    c.setFillColor(QUEST_LIGHT_BLUE)
    c.roundRect(left_x, box_top - box_h, box_w, box_h, 4, fill=1, stroke=0)

    c.setFillColor(QUEST_BLUE)
    c.setFont(FONT_BOLD, 8)
    c.drawString(left_x + 6, box_top - 14, "PATIENT INFORMATION")

    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_BOLD, 10)
    c.drawString(left_x + 6, box_top - 28, PATIENT_NAME)

    c.setFont(FONT_REGULAR, 8)
    c.drawString(left_x + 6, box_top - 41, f"DOB: {PATIENT_DOB}  |  Age: {PATIENT_AGE}  |  Sex: {PATIENT_SEX}")
    c.drawString(left_x + 6, box_top - 53, f"MRN: {PATIENT_MRN}")
    c.drawString(left_x + 6, box_top - 65, f"Account: {PATIENT_ACCT}")

    # Right box: specimen info
    right_x = left_x + box_w + 12

    c.setFillColor(QUEST_LIGHT_BLUE)
    c.roundRect(right_x, box_top - box_h, box_w, box_h, 4, fill=1, stroke=0)

    c.setFillColor(QUEST_BLUE)
    c.setFont(FONT_BOLD, 8)
    c.drawString(right_x + 6, box_top - 14, "SPECIMEN INFORMATION")

    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 8)
    c.drawString(right_x + 6, box_top - 28, f"Specimen ID:  {SPECIMEN_ID}")
    c.drawString(right_x + 6, box_top - 40, f"Type:         {SPECIMEN_TYPE}")
    c.drawString(right_x + 6, box_top - 52, f"Collected:    {SPECIMEN_COLLECTED}")
    c.drawString(right_x + 6, box_top - 64, f"Received:     {SPECIMEN_RECEIVED}")
    c.drawString(right_x + 6, box_top - 76, f"Reported:     {SPECIMEN_REPORTED}")


def draw_page1_ordering(c: canvas.Canvas) -> None:
    """Ordering provider section."""
    y = PAGE_H - 198
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(QUEST_BLUE)
    c.drawString(36, y, "ORDERING PHYSICIAN")
    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 8)
    c.drawString(36, y - 14, f"{ORDERING_PROVIDER}  ·  NPI: {ORDERING_NPI}")
    c.drawString(36, y - 26, f"{ORDERING_FACILITY}  ·  {ORDERING_ADDRESS}")


def draw_page1_report_title(c: canvas.Canvas) -> None:
    """Report title and summary line."""
    y = PAGE_H - 250
    c.setFillColor(QUEST_BLUE)
    c.rect(36, y - 4, PAGE_W - 72, 24, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 12)
    c.drawString(42, y + 4, REPORT_TITLE)

    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 9)
    c.drawString(36, y - 18, f"Accession: {REPORT_ACCESSION}   |   Report Date: {REPORT_DATE}   |   14 results, 2 flagged")


def draw_page1_summary_table(c: canvas.Canvas) -> None:
    """Summary table on page 1: test names, results, flags only (no reference ranges)."""
    y_start = PAGE_H - 300
    row_h = 15
    col_widths = [220, 80, 80, 60, 30]  # test, result, units, ref range (abridged), flag
    headers = ["Test", "Result", "Units", "Ref Range", "Flag"]
    col_x_positions = [36]
    for w in col_widths[:-1]:
        col_x_positions.append(col_x_positions[-1] + w)

    # Draw header
    c.setFillColor(QUEST_BLUE)
    c.rect(36, y_start, sum(col_widths), row_h, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 8)
    for i, hdr in enumerate(headers):
        c.drawString(col_x_positions[i] + 3, y_start + 4, hdr)

    # Draw rows
    y = y_start - row_h
    for idx, row in enumerate(CMP_VALUES):
        name, loinc, result, units, lo, hi, flag = row
        bg = LIGHT_GRAY if idx % 2 == 0 else WHITE
        c.setFillColor(bg)
        c.rect(36, y, sum(col_widths), row_h, fill=1, stroke=0)

        # Test name
        c.setFillColor(DARK_GRAY)
        c.setFont(FONT_REGULAR, 8)
        c.drawString(col_x_positions[0] + 3, y + 4, name)

        # Result — flag color
        if flag == "H":
            c.setFillColor(FLAG_RED)
        elif flag == "L":
            c.setFillColor(FLAG_ORANGE)
        else:
            c.setFillColor(DARK_GRAY)
        c.setFont(FONT_BOLD if flag else FONT_REGULAR, 8)
        c.drawString(col_x_positions[1] + 3, y + 4, result)

        c.setFillColor(DARK_GRAY)
        c.setFont(FONT_REGULAR, 8)
        c.drawString(col_x_positions[2] + 3, y + 4, units)

        # Abridged ref range
        ref_str = f"{lo} - {hi}" if hi != 999 else f">={lo}"
        c.drawString(col_x_positions[3] + 3, y + 4, ref_str)

        # Flag
        if flag:
            c.setFillColor(FLAG_RED if flag == "H" else FLAG_ORANGE)
            c.setFont(FONT_BOLD, 8)
            c.drawString(col_x_positions[4] + 3, y + 4, flag)

        y -= row_h

    # Thin bottom border
    c.setStrokeColor(MID_GRAY)
    c.setLineWidth(0.5)
    c.line(36, y, 36 + sum(col_widths), y)

    # Note about page 2
    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_OBLIQUE, 8)
    c.drawString(36, y - 14, "See Page 2 for detailed results with reference ranges and methodology notes.")


def draw_page1_footer(c: canvas.Canvas) -> None:
    """Page 1 footer."""
    c.setStrokeColor(MID_GRAY)
    c.setLineWidth(0.5)
    c.line(36, 40, PAGE_W - 36, 40)
    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 7)
    c.drawString(36, 28, f"SYNTHETIC DOCUMENT — For EHI Atlas demonstration only. Not a clinical record.   |   Page 1 of 3")
    c.drawRightString(PAGE_W - 36, 28, f"Patient: {PATIENT_NAME}  ·  MRN: {PATIENT_MRN}  ·  Specimen: {SPECIMEN_ID}")


# ===========================================================================
# PAGE 2 helpers — THE CRITICAL PAGE (documented bbox on creatinine row)
# ===========================================================================

def draw_page2_header(c: canvas.Canvas) -> None:
    """Compact header for continuation pages."""
    c.setFillColor(QUEST_BLUE)
    c.rect(0, PAGE_H - 40, PAGE_W, 40, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 11)
    c.drawString(36, PAGE_H - 26, "Quest Diagnostics  —  COMPREHENSIVE METABOLIC PANEL (continued)")
    c.setFont(FONT_REGULAR, 8)
    c.drawRightString(PAGE_W - 36, PAGE_H - 22, f"Patient: {PATIENT_NAME}   MRN: {PATIENT_MRN}   Specimen: {SPECIMEN_ID}")
    c.setFont(FONT_REGULAR, 7)
    c.drawRightString(PAGE_W - 36, PAGE_H - 33, f"Reported: {SPECIMEN_REPORTED}")


def draw_page2_section_heading(c: canvas.Canvas, y: float) -> float:
    """Draw 'DETAILED RESULTS' section heading, return next y."""
    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_BOLD, 9)
    c.drawString(TABLE_X, y, "DETAILED RESULTS — Reference ranges are methodology-specific (see Page 3)")
    y -= 10
    c.setStrokeColor(QUEST_BLUE)
    c.setLineWidth(1)
    c.line(TABLE_X, y, PAGE_W - TABLE_X, y)
    return y - 8


def draw_page2_results_table(c: canvas.Canvas) -> dict:
    """
    Draw the full CMP results table on page 2.

    Returns a dict with the creatinine row bbox for documentation.

    Layout (all units = PDF points, origin at bottom-left of page):
      - Table starts at TABLE_TOP_Y (y of top edge of header row)
      - Header row height: HEADER_ROW_H
      - Data rows: ROW_HEIGHT each
      - Creatinine is at index CREATININE_IDX (0-based data rows)
    """
    # Column header row
    y = TABLE_TOP_Y
    col_widths_list = [COL_TEST_W, COL_RESULT_W, COL_UNITS_W, COL_RANGE_W, COL_FLAG_W]
    headers = ["Test Name  [LOINC]", "Result", "Units", "Reference Range", "Flag"]
    col_positions = [
        COL_X["test"], COL_X["result"], COL_X["units"], COL_X["range"], COL_X["flag"]
    ]

    # Header background
    c.setFillColor(QUEST_BLUE)
    c.rect(TABLE_X, y - HEADER_ROW_H, sum(col_widths_list), HEADER_ROW_H, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 8)
    for i, hdr in enumerate(headers):
        c.drawString(col_positions[i] + 3, y - HEADER_ROW_H + 5, hdr)

    # Thin grid lines for header
    c.setStrokeColor(WHITE)
    c.setLineWidth(0.3)
    for col_x in col_positions[1:]:
        c.line(col_x, y - HEADER_ROW_H, col_x, y)

    # Data rows
    row_y = y - HEADER_ROW_H  # top of first data row

    creatinine_bbox = None

    for idx, row in enumerate(CMP_VALUES):
        name, loinc, result, units, lo, hi, flag = row

        row_top = row_y
        row_bottom = row_top - ROW_HEIGHT

        # Highlight creatinine row more prominently (very light yellow)
        if idx == CREATININE_IDX:
            bg = colors.HexColor("#FFF9E6")
            creatinine_bbox = (
                int(TABLE_X),
                int(row_bottom),
                int(TABLE_X + sum(col_widths_list)),
                int(row_top),
            )
        elif idx % 2 == 0:
            bg = LIGHT_GRAY
        else:
            bg = WHITE

        c.setFillColor(bg)
        c.rect(TABLE_X, row_bottom, sum(col_widths_list), ROW_HEIGHT, fill=1, stroke=0)

        # Vertical grid lines
        c.setStrokeColor(MID_GRAY)
        c.setLineWidth(0.3)
        for col_x in col_positions[1:]:
            c.line(col_x, row_bottom, col_x, row_top)

        # Horizontal bottom border
        c.line(TABLE_X, row_bottom, TABLE_X + sum(col_widths_list), row_bottom)

        # Test name + LOINC
        c.setFillColor(DARK_GRAY)
        c.setFont(FONT_REGULAR, 8)
        c.drawString(col_positions[0] + 3, row_bottom + 4, f"{name}  [{loinc}]")

        # Result value (colored if flagged)
        if flag == "H":
            c.setFillColor(FLAG_RED)
            c.setFont(FONT_BOLD, 9)
        elif flag == "L":
            c.setFillColor(FLAG_ORANGE)
            c.setFont(FONT_BOLD, 9)
        else:
            c.setFillColor(DARK_GRAY)
            c.setFont(FONT_REGULAR, 8)
        c.drawString(col_positions[1] + 3, row_bottom + 4, result)

        # Units
        c.setFillColor(DARK_GRAY)
        c.setFont(FONT_REGULAR, 8)
        c.drawString(col_positions[2] + 3, row_bottom + 4, units)

        # Reference range
        if hi == 999:
            ref_str = f">= {lo}"
        else:
            ref_str = f"{lo} - {hi}"
        c.drawString(col_positions[3] + 3, row_bottom + 4, ref_str)

        # Flag cell
        if flag:
            c.setFillColor(FLAG_RED if flag == "H" else FLAG_ORANGE)
            c.setFont(FONT_BOLD, 9)
            c.drawString(col_positions[4] + 3, row_bottom + 4, flag)

        row_y = row_bottom

    # Outer border around entire table
    table_h = HEADER_ROW_H + len(CMP_VALUES) * ROW_HEIGHT
    c.setStrokeColor(QUEST_BLUE)
    c.setLineWidth(0.75)
    c.rect(TABLE_X, row_y, sum(col_widths_list), table_h, fill=0, stroke=1)

    return {"creatinine_bbox": creatinine_bbox}


def draw_page2_interpretation_note(c: canvas.Canvas) -> None:
    """Clinical interpretation note below the table."""
    table_bottom = TABLE_TOP_Y - HEADER_ROW_H - len(CMP_VALUES) * ROW_HEIGHT
    y = table_bottom - 20

    c.setFillColor(QUEST_LIGHT_BLUE)
    c.roundRect(TABLE_X, y - 60, PAGE_W - 2 * TABLE_X, 60, 4, fill=1, stroke=0)

    c.setFillColor(QUEST_BLUE)
    c.setFont(FONT_BOLD, 8)
    c.drawString(TABLE_X + 6, y - 14, "CLINICAL NOTE")

    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 8)
    lines = [
        "Creatinine 1.4 mg/dL is at the upper limit of normal for this age group (ref: 0.6-1.3 mg/dL).",
        "eGFR 54 mL/min/1.73m2 indicates CKD Stage G3a. Recommend nephrology consultation and",
        "medication review (simvastatin dose adjustment may be appropriate per patient's current regimen).",
        "Glucose 102 mg/dL is mildly elevated; correlate with HbA1c in context of known prediabetes.",
    ]
    for i, line in enumerate(lines):
        c.drawString(TABLE_X + 6, y - 26 - (i * 10), line)


def draw_page2_footer(c: canvas.Canvas) -> None:
    """Page 2 footer."""
    c.setStrokeColor(MID_GRAY)
    c.setLineWidth(0.5)
    c.line(36, 40, PAGE_W - 36, 40)
    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 7)
    c.drawString(36, 28, "SYNTHETIC DOCUMENT — For EHI Atlas demonstration only. Not a clinical record.   |   Page 2 of 3")
    c.drawRightString(PAGE_W - 36, 28, f"Patient: {PATIENT_NAME}  ·  MRN: {PATIENT_MRN}  ·  Specimen: {SPECIMEN_ID}")


# ===========================================================================
# PAGE 3 helpers — Reference ranges, certifications, footer
# ===========================================================================

def draw_page3_header(c: canvas.Canvas) -> None:
    """Compact header for page 3."""
    c.setFillColor(QUEST_BLUE)
    c.rect(0, PAGE_H - 40, PAGE_W, 40, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 11)
    c.drawString(36, PAGE_H - 26, "Quest Diagnostics  —  Reference Ranges & Laboratory Information")
    c.setFont(FONT_REGULAR, 8)
    c.drawRightString(PAGE_W - 36, PAGE_H - 22, f"Patient: {PATIENT_NAME}   MRN: {PATIENT_MRN}   Specimen: {SPECIMEN_ID}")


def draw_page3_reference_methodology(c: canvas.Canvas) -> None:
    """Reference range methodology block."""
    y = PAGE_H - 70
    c.setFillColor(QUEST_BLUE)
    c.setFont(FONT_BOLD, 10)
    c.drawString(36, y, "REFERENCE RANGE METHODOLOGY")
    y -= 16
    c.setStrokeColor(QUEST_BLUE)
    c.setLineWidth(1)
    c.line(36, y, PAGE_W - 36, y)
    y -= 14

    methodology_text = [
        "Reference intervals are established from a healthy reference population. Ranges reflect the central",
        "95th percentile of the reference population. Values outside the reference interval are flagged but",
        "may not be clinically significant for all patients. Clinical judgment is required to interpret results.",
        "",
        "Creatinine (LOINC 2160-0): Enzymatic method (Roche Diagnostics). CV <2%. Reportable range 0.1-40.0 mg/dL.",
        "Reference: Male 0.6-1.3 mg/dL; Female 0.5-1.1 mg/dL. Age-adjusted for patients >65 per CKD-EPI 2021.",
        "",
        "eGFR (LOINC 62238-1): Calculated via CKD-EPI 2021 equation. Reporting threshold: <15 or >=60 mL/min/1.73m2.",
        "",
        "Glucose (LOINC 2345-7): Hexokinase method. Reportable range 10-700 mg/dL.",
        "",
        "All other analytes measured per standard College of American Pathologists (CAP) proficiency survey methods.",
    ]

    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 8)
    for line in methodology_text:
        c.drawString(36, y, line)
        y -= 12

    return y


def draw_page3_certifications(c: canvas.Canvas, y: float) -> float:
    """Lab certification block."""
    y -= 20
    c.setFillColor(QUEST_BLUE)
    c.setFont(FONT_BOLD, 10)
    c.drawString(36, y, "LABORATORY CERTIFICATIONS & REGULATORY INFORMATION")
    y -= 16
    c.setStrokeColor(QUEST_BLUE)
    c.setLineWidth(1)
    c.line(36, y, PAGE_W - 36, y)
    y -= 14

    cert_lines = [
        f"CLIA Certificate #: {LAB_CLIA}",
        "CAP Accreditation #: 7197392",
        "New York State Permit #: 4516",
        "Pennsylvania License #: 046-0052",
        "",
        "This laboratory is accredited by the College of American Pathologists (CAP) and",
        "certified under the Clinical Laboratory Improvement Amendments (CLIA) of 1988.",
        "Results are released only to authorized healthcare providers.",
    ]

    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 8)
    for line in cert_lines:
        c.drawString(36, y, line)
        y -= 12

    return y


def draw_page3_signature(c: canvas.Canvas, y: float) -> None:
    """Medical director signature placeholder block."""
    y -= 30
    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 8)
    c.drawString(36, y, "Authorized by:")
    y -= 30
    c.setStrokeColor(DARK_GRAY)
    c.setLineWidth(0.5)
    c.line(36, y, 200, y)
    y -= 12
    c.setFont(FONT_REGULAR, 8)
    c.drawString(36, y, "Medical Director, Quest Diagnostics")
    c.drawString(36, y - 12, "Results reviewed and released by Laboratory Director")


def draw_page3_synthetic_notice(c: canvas.Canvas) -> None:
    """Prominent synthetic data notice."""
    y = 130
    c.setFillColor(colors.HexColor("#FFF3CD"))
    c.roundRect(36, y, PAGE_W - 72, 70, 4, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#856404"))
    c.setLineWidth(1)
    c.roundRect(36, y, PAGE_W - 72, 70, 4, fill=0, stroke=1)

    c.setFillColor(colors.HexColor("#856404"))
    c.setFont(FONT_BOLD, 9)
    c.drawString(42, y + 52, "NOTICE: SYNTHETIC TEST DOCUMENT")
    c.setFont(FONT_REGULAR, 8)
    notice_lines = [
        "This PDF was generated programmatically by the EHI Atlas project for demonstration and testing purposes.",
        "It does NOT represent a real patient or real clinical results. Patient name, MRN, specimen IDs,",
        "and all lab values are entirely fictitious. Source code: corpus/_sources/synthesized-lab-pdf/generator.py",
        f"Creatinine anchor (Artifact 5): LOINC 2160-0 | value 1.4 mg/dL | page=2;bbox={CREATININE_BBOX[0]},{CREATININE_BBOX[1]},{CREATININE_BBOX[2]},{CREATININE_BBOX[3]}",
    ]
    for i, line in enumerate(notice_lines):
        c.drawString(42, y + 38 - (i * 12), line)


def draw_page3_footer(c: canvas.Canvas) -> None:
    """Page 3 footer."""
    c.setStrokeColor(MID_GRAY)
    c.setLineWidth(0.5)
    c.line(36, 40, PAGE_W - 36, 40)
    c.setFillColor(DARK_GRAY)
    c.setFont(FONT_REGULAR, 7)
    c.drawString(36, 28, "SYNTHETIC DOCUMENT — For EHI Atlas demonstration only. Not a clinical record.   |   Page 3 of 3")
    c.drawRightString(PAGE_W - 36, 28, f"Patient: {PATIENT_NAME}  ·  MRN: {PATIENT_MRN}  ·  Specimen: {SPECIMEN_ID}")


# ===========================================================================
# MAIN BUILD FUNCTION
# ===========================================================================

def build_pdf(out_path: str | Path) -> dict:
    """
    Generate the synthetic Quest-style lab report PDF.

    Args:
        out_path: File path for the output PDF.

    Returns:
        dict with keys:
            - out_path: str
            - creatinine_bbox: tuple (x1, y1, x2, y2) in PDF user units
            - source_locator: str (FHIR Extension value)
            - page_count: int
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out_path), pagesize=letter)

    # Fixed metadata (determinism: never use runtime timestamps)
    c.setTitle(f"Lab Report — {PATIENT_NAME} — {SPECIMEN_REPORTED}")
    c.setAuthor(PDF_AUTHOR)
    c.setSubject(f"CMP {REPORT_DATE} | Accession {REPORT_ACCESSION}")
    c.setCreator(PDF_AUTHOR)
    # Producer is set by ReportLab automatically; creation date baked into PDF structure

    # -----------------------------------------------------------------------
    # PAGE 1
    # -----------------------------------------------------------------------
    draw_page1_header(c)
    draw_page1_patient_box(c)
    draw_page1_ordering(c)
    draw_page1_report_title(c)
    draw_page1_summary_table(c)
    draw_page1_footer(c)
    c.showPage()

    # -----------------------------------------------------------------------
    # PAGE 2 — creatinine bbox is on this page
    # -----------------------------------------------------------------------
    draw_page2_header(c)
    y = PAGE_H - 56
    y = draw_page2_section_heading(c, y)
    result = draw_page2_results_table(c)
    creatinine_bbox = result["creatinine_bbox"]
    draw_page2_interpretation_note(c)
    draw_page2_footer(c)
    c.showPage()

    # -----------------------------------------------------------------------
    # PAGE 3
    # -----------------------------------------------------------------------
    draw_page3_header(c)
    y = draw_page3_reference_methodology(c)
    y = draw_page3_certifications(c, y)
    draw_page3_signature(c, y)
    draw_page3_synthetic_notice(c)
    draw_page3_footer(c)
    c.showPage()

    c.save()

    actual_locator = f"page=2;bbox={creatinine_bbox[0]},{creatinine_bbox[1]},{creatinine_bbox[2]},{creatinine_bbox[3]}"

    return {
        "out_path": str(out_path),
        "creatinine_bbox": creatinine_bbox,
        "source_locator": actual_locator,
        "page_count": 3,
    }


# ===========================================================================
# ENTRY POINT
# ===========================================================================

if __name__ == "__main__":
    script_dir = Path(__file__).parent
    out_path = script_dir / "raw" / "lab-report-2025-09-12-quest.pdf"

    print(f"Generating synthetic lab report PDF...")
    result = build_pdf(out_path)

    file_size = Path(result["out_path"]).stat().st_size
    print(f"  Output:           {result['out_path']}")
    print(f"  File size:        {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    print(f"  Page count:       {result['page_count']}")
    print(f"  Creatinine bbox:  {result['creatinine_bbox']}")
    print(f"  source-locator:   {result['source_locator']}")
    print()
    print("Creatinine row (Artifact 5):")
    print(f"  LOINC:   2160-0")
    print(f"  Value:   1.4 mg/dL")
    print(f"  Date:    2025-09-12")
    print(f"  Page:    2")
    print(f"  BBox:    {result['creatinine_bbox']}")
    print()
    print("Done. Add 'reportlab' to pyproject.toml dependencies if not already present.")
