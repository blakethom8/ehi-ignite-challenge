"""
ehi_atlas.terminology
~~~~~~~~~~~~~~~~~~~~~

Reference terminology loaders for Phase 1 (showcase-patient scope).

Phase 1 uses:
  - A static LOINC subset (~22 codes) for the showcase patient panels
  - A hand-curated SNOMED/ICD-10 crosswalk for showcase conditions and meds
  - A RxNorm REST client (no local snapshot)

Phase 2 will load the full UMLS Metathesaurus. See corpus/reference/VERSIONS.md.

Public interface:
  load_loinc_showcase()        -> dict (full JSON including "codes" list)
  load_handcrafted_crosswalk() -> dict (full JSON including "codes" list)
  lookup_cross(system, code)   -> dict | None (single crosswalk row or None)
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Absolute paths are derived relative to this file so they work regardless
# of the process working directory.
_REFERENCE_DIR = Path(__file__).parent.parent.parent / "corpus" / "reference"
_LOINC_SHOWCASE_PATH = _REFERENCE_DIR / "loinc" / "showcase-loinc.json"
_CROSSWALK_PATH = _REFERENCE_DIR / "handcrafted-crosswalk" / "showcase.json"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_loinc_showcase() -> dict:
    """
    Load the static LOINC showcase subset.

    Returns the parsed JSON document, which has the shape::

        {
          "version": "0.1.0",
          "codes": [
            {"code": "2160-0", "display": "...", "system": "...", ...},
            ...
          ]
        }

    The list is available at ``result["codes"]``.

    Raises:
        FileNotFoundError: if the LOINC showcase file is missing.
        json.JSONDecodeError: if the file is malformed.
    """
    if not _LOINC_SHOWCASE_PATH.exists():
        raise FileNotFoundError(
            f"LOINC showcase file not found: {_LOINC_SHOWCASE_PATH}. "
            "Run the corpus setup to regenerate."
        )
    data = json.loads(_LOINC_SHOWCASE_PATH.read_text())
    logger.debug("Loaded %d LOINC showcase codes", len(data.get("codes", [])))
    return data


@lru_cache(maxsize=1)
def load_handcrafted_crosswalk() -> dict:
    """
    Load the hand-curated SNOMED/ICD-10/RxNorm crosswalk for showcase codes.

    Returns the parsed JSON document, which has the shape::

        {
          "version": "0.1.0",
          "codes": [
            {
              "concept_label": "...",
              "umls_cui": "...",
              "snomed_ct": {"code": "...", "display": "..."},
              "icd_10_cm": {"code": "...", "display": "..."},
              "rxnorm": {"rxcui": "...", "display": "..."} | null,
              "notes": "..."
            },
            ...
          ]
        }

    Raises:
        FileNotFoundError: if the crosswalk file is missing.
        json.JSONDecodeError: if the file is malformed.
    """
    if not _CROSSWALK_PATH.exists():
        raise FileNotFoundError(
            f"Handcrafted crosswalk file not found: {_CROSSWALK_PATH}. "
            "Run the corpus setup to regenerate."
        )
    data = json.loads(_CROSSWALK_PATH.read_text())
    logger.debug(
        "Loaded %d handcrafted crosswalk entries", len(data.get("codes", []))
    )
    return data


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def lookup_cross(system: str, code: str) -> dict | None:
    """
    Search the handcrafted crosswalk for a code in the given code system.

    Args:
        system: Code system URI or short name. Recognised values:
                  - ``"http://snomed.info/sct"`` or ``"snomed"``
                  - ``"http://hl7.org/fhir/sid/icd-10-cm"`` or ``"icd-10-cm"`` or ``"icd10cm"``
                  - ``"http://www.nlm.nih.gov/research/umls/rxnorm"`` or ``"rxnorm"``
                  - ``"umls"`` (matches on umls_cui)
        code:   The code value to look up (e.g. ``"38341003"`` for SNOMED HTN).

    Returns:
        The first matching crosswalk entry dict, or ``None`` if not found.

    Example::

        >>> row = lookup_cross("http://snomed.info/sct", "38341003")
        >>> row["concept_label"]
        'Hypertensive disorder'
        >>> row["icd_10_cm"]["code"]
        'I10'
    """
    xwalk = load_handcrafted_crosswalk()
    entries = xwalk.get("codes", [])

    # Normalise system to a short token for comparison
    system_lower = system.lower()
    if "snomed" in system_lower:
        key = "snomed_ct"
    elif "icd-10" in system_lower or "icd10" in system_lower:
        key = "icd_10_cm"
    elif "rxnorm" in system_lower:
        key = "rxnorm"
    elif "umls" in system_lower:
        key = "umls_cui"
    else:
        logger.warning("lookup_cross: unrecognised system %r — returning None", system)
        return None

    for entry in entries:
        if key == "umls_cui":
            # umls_cui is a plain string on the entry, not a nested dict
            if entry.get("umls_cui") == code:
                return entry
        elif key == "rxnorm":
            # RxNorm entries use "rxcui" as the code key, not "code"
            nested = entry.get(key)
            if nested and nested.get("rxcui") == code:
                return entry
        else:
            nested = entry.get(key)
            if nested and nested.get("code") == code:
                return entry

    return None


def list_loinc_codes() -> list[str]:
    """Return a sorted list of LOINC code strings from the showcase subset."""
    data = load_loinc_showcase()
    return sorted(row["code"] for row in data.get("codes", []))


def list_crosswalk_concepts() -> list[str]:
    """Return a sorted list of concept labels from the handcrafted crosswalk."""
    data = load_handcrafted_crosswalk()
    return sorted(row["concept_label"] for row in data.get("codes", []))
