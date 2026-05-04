"""Name → LOINC bridge.

The harmonization layer's central trick: when one source uses LOINC codes
(Cedars FHIR, Quest LIS) and another uses free-text labels (Function
Health PDFs, Apple Health, scanned reports), we need to bridge them onto
a common identity so the matcher can join them.

Approach for v1: a hand-curated dict for the ~50 most common labs across
Blake's actual sources (Cedars + Function Health). This covers >95% of
the lab volume in the demo without external service calls. The bridge is
extensible — when a name doesn't resolve, we fall back to the normalized
text label as the match key (so two sources that both lack LOINC but use
the same name still merge).

Future: an LLM-bootstrapped expanded bridge cached as a JSON crosswalk,
mirroring the pattern in ``lib/sql_on_fhir/`` enrichments. Out of scope
for v1.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Hand-curated name → LOINC table
# ---------------------------------------------------------------------------
#
# Keys are normalized lowercase names (strip punctuation, collapse spaces).
# Values are (loinc_code, canonical_display_name, canonical_unit).
#
# Sourced from LOINC's common-lab subset, cross-checked against the labs
# Blake's Cedars + Function Health sources actually emit. When a single
# name maps to multiple LOINC codes (e.g. method-specific variants), we
# pick the one most commonly emitted by US clinical labs.
# ---------------------------------------------------------------------------

_BRIDGE: dict[str, tuple[str, str, str | None]] = {
    # --- Lipid panel ---
    "cholesterol": ("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma", "mg/dL"),
    "cholesterol total": ("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma", "mg/dL"),
    "total cholesterol": ("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma", "mg/dL"),
    "hdl": ("2085-9", "HDL Cholesterol [Mass/volume] in Serum or Plasma", "mg/dL"),
    "hdl cholesterol": ("2085-9", "HDL Cholesterol [Mass/volume] in Serum or Plasma", "mg/dL"),
    "ldl": ("13457-7", "LDL Cholesterol [Mass/volume] in Serum or Plasma calculated", "mg/dL"),
    "ldl calculated": ("13457-7", "LDL Cholesterol [Mass/volume] in Serum or Plasma calculated", "mg/dL"),
    "ldl cholesterol": ("13457-7", "LDL Cholesterol [Mass/volume] in Serum or Plasma calculated", "mg/dL"),
    "triglycerides": ("2571-8", "Triglyceride [Mass/volume] in Serum or Plasma", "mg/dL"),
    "non hdl cholesterol": ("43396-1", "Cholesterol non HDL [Mass/volume] in Serum or Plasma", "mg/dL"),
    "non-hdl cholesterol": ("43396-1", "Cholesterol non HDL [Mass/volume] in Serum or Plasma", "mg/dL"),
    "cholesterol hdl ratio": ("9830-1", "Cholesterol/Cholesterol.in HDL [Mass Ratio]", None),
    "chol hdlc ratio": ("9830-1", "Cholesterol/Cholesterol.in HDL [Mass Ratio]", None),
    "apolipoprotein b": ("1884-6", "Apolipoprotein B [Mass/volume] in Serum or Plasma", "mg/dL"),
    "apob": ("1884-6", "Apolipoprotein B [Mass/volume] in Serum or Plasma", "mg/dL"),
    # --- Metabolic panel (BMP/CMP) ---
    "glucose": ("2345-7", "Glucose [Mass/volume] in Serum or Plasma", "mg/dL"),
    "sodium": ("2951-2", "Sodium [Moles/volume] in Serum or Plasma", "mmol/L"),
    "potassium": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma", "mmol/L"),
    "chloride": ("2075-0", "Chloride [Moles/volume] in Serum or Plasma", "mmol/L"),
    "carbon dioxide": ("2028-9", "Carbon dioxide, total [Moles/volume] in Serum or Plasma", "mmol/L"),
    "co2": ("2028-9", "Carbon dioxide, total [Moles/volume] in Serum or Plasma", "mmol/L"),
    "calcium": ("17861-6", "Calcium [Mass/volume] in Serum or Plasma", "mg/dL"),
    "creatinine": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma", "mg/dL"),
    "bun": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma", "mg/dL"),
    "urea nitrogen": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma", "mg/dL"),
    "urea nitrogen bun": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma", "mg/dL"),
    "egfr": ("62238-1", "Glomerular filtration rate/1.73 sq M.predicted [Volume Rate/Area] in Serum, Plasma or Blood by Creatinine-based formula (CKD-EPI)", "mL/min/1.73m2"),
    "bun creatinine ratio": ("3097-3", "Urea nitrogen/Creatinine [Mass Ratio] in Serum or Plasma", None),
    # --- Liver panel ---
    "protein total": ("2885-2", "Protein [Mass/volume] in Serum or Plasma", "g/dL"),
    "total protein": ("2885-2", "Protein [Mass/volume] in Serum or Plasma", "g/dL"),
    "albumin": ("1751-7", "Albumin [Mass/volume] in Serum or Plasma", "g/dL"),
    "globulin": ("2336-6", "Globulin [Mass/volume] in Serum by calculation", "g/dL"),
    "albumin globulin ratio": ("1759-0", "Albumin/Globulin [Mass Ratio] in Serum or Plasma", None),
    "bilirubin total": ("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma", "mg/dL"),
    "alkaline phosphatase": ("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma", "U/L"),
    "ast": ("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "U/L"),
    "alt": ("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "U/L"),
    # --- CBC ---
    "white blood cell count": ("6690-2", "Leukocytes [#/volume] in Blood by Automated count", "10*3/uL"),
    "wbc": ("6690-2", "Leukocytes [#/volume] in Blood by Automated count", "10*3/uL"),
    "red blood cell count": ("789-8", "Erythrocytes [#/volume] in Blood by Automated count", "10*6/uL"),
    "rbc": ("789-8", "Erythrocytes [#/volume] in Blood by Automated count", "10*6/uL"),
    "hemoglobin": ("718-7", "Hemoglobin [Mass/volume] in Blood", "g/dL"),
    "hematocrit": ("4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count", "%"),
    "mcv": ("787-2", "MCV [Entitic volume] by Automated count", "fL"),
    "mch": ("785-6", "MCH [Entitic mass] by Automated count", "pg"),
    "mchc": ("786-4", "MCHC [Mass/volume] by Automated count", "g/dL"),
    "rdw": ("788-0", "Erythrocyte distribution width [Ratio] by Automated count", "%"),
    "platelet count": ("777-3", "Platelets [#/volume] in Blood by Automated count", "10*3/uL"),
    "mpv": ("32623-1", "Platelet mean volume [Entitic volume] in Blood by Automated count", "fL"),
    # --- Endocrine ---
    "tsh": ("3016-3", "Thyrotropin [Units/volume] in Serum or Plasma", "mIU/L"),
    "hemoglobin a1c": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "hba1c": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "a1c": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "insulin": ("20448-7", "Insulin [Units/volume] in Serum or Plasma", "uIU/mL"),
    # --- Inflammation ---
    "hs crp": ("30522-7", "C reactive protein [Mass/volume] in Serum or Plasma by High sensitivity method", "mg/L"),
    "high sensitivity c reactive protein": ("30522-7", "C reactive protein [Mass/volume] in Serum or Plasma by High sensitivity method", "mg/L"),
}

# Reverse lookup: LOINC → canonical display + unit
_LOINC_TO_CANONICAL: dict[str, tuple[str, str | None]] = {}
for _name, (_code, _display, _unit) in _BRIDGE.items():
    if _code not in _LOINC_TO_CANONICAL:
        _LOINC_TO_CANONICAL[_code] = (_display, _unit)


def normalize_name(raw: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Keeps the matcher tolerant to punctuation drift across sources
    (``"BUN/Creatinine Ratio"`` → ``"bun creatinine ratio"``).
    """
    s = raw.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def lookup_by_name(raw_name: str) -> tuple[str, str, str | None] | None:
    """Resolve a free-text lab name to ``(loinc_code, canonical_display, canonical_unit)``.

    Returns ``None`` when the bridge doesn't recognize the name. Callers
    fall back to the normalized name as the match key in that case.
    """
    if not raw_name:
        return None
    return _BRIDGE.get(normalize_name(raw_name))


def canonical_for_loinc(loinc: str) -> tuple[str, str | None] | None:
    """Get ``(canonical_display, canonical_unit)`` for a known LOINC code.

    Returns ``None`` for LOINC codes outside our hand-curated subset.
    """
    return _LOINC_TO_CANONICAL.get(loinc)
