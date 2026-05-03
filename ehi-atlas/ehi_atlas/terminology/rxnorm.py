"""
RxNorm REST API client (no auth required).

Uses urllib.request from the standard library — no additional dependencies.
Provides a file-based cache at corpus/reference/rxnorm/.cache/<query-hash>.json
so repeated lookups don't hit the API.

API reference: https://rxnav.nlm.nih.gov/RxNormAPIs.html
"""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Base URL for all RxNorm REST calls
_BASE_URL = "https://rxnav.nlm.nih.gov/REST"

# Cache lives next to the snapshot data
_CACHE_DIR = Path(__file__).parent.parent.parent / "corpus" / "reference" / "rxnorm" / ".cache"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cache_key(segment: str) -> str:
    """Stable hex digest for a URL segment string."""
    return hashlib.sha256(segment.encode()).hexdigest()


def _get_cached(key: str) -> Any | None:
    """Return parsed JSON from cache, or None if not present."""
    path = _CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            path.unlink(missing_ok=True)
    return None


def _put_cached(key: str, data: Any) -> None:
    """Write data to cache as JSON."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(data, indent=2))


def _get_json(url: str, *, timeout: int = 10) -> Any | None:
    """
    HTTP GET returning parsed JSON, or None on error.

    Always requests JSON format by appending ?format=json if not already present.
    """
    if "format=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}format=json"

    cache_key = _cache_key(url)
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.debug("Cache hit: %s", url)
        return cached

    logger.debug("Fetching: %s", url)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw)
        _put_cached(cache_key, data)
        return data
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("RxNorm request failed for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lookup_rxcui(name: str) -> str | None:
    """
    Return the best-match RxCUI for a drug name, or None if not found.

    Uses /approximateTerm — returns a ranked list of candidates; we take the
    first one whose rxcui is non-empty.

    Args:
        name: Drug name string (e.g. "simvastatin", "fluticasone/salmeterol").

    Returns:
        RxCUI string (e.g. "36567") or None.

    Example:
        >>> lookup_rxcui("simvastatin")
        '36567'
    """
    encoded = urllib.parse.quote(name)
    url = f"{_BASE_URL}/approximateTerm?term={encoded}&maxEntries=5"
    data = _get_json(url)
    if data is None:
        return None

    candidates = (
        data.get("approximateGroup", {})
        .get("candidate", [])
    )
    for candidate in candidates:
        rxcui = candidate.get("rxcui", "").strip()
        if rxcui:
            return rxcui
    return None


def get_ingredients(rxcui: str) -> list[dict]:
    """
    Return ingredient-level concepts for a given RxCUI.

    Useful for ingredient-level deduplication: a branded drug (e.g. Zocor)
    and a generic (simvastatin) both resolve to RXCUI 36567 at the ingredient
    level.

    Args:
        rxcui: RxCUI string.

    Returns:
        List of dicts, each with keys: rxcui, name, tty (term type).

    Example:
        >>> get_ingredients("36567")
        [{'rxcui': '36567', 'name': 'Simvastatin', 'tty': 'IN'}]
    """
    url = f"{_BASE_URL}/rxcui/{rxcui}/related?tty=IN"
    data = _get_json(url)
    if data is None:
        return []

    concepts = (
        data.get("relatedGroup", {})
        .get("conceptGroup", [])
    )
    ingredients: list[dict] = []
    for group in concepts:
        for prop in group.get("conceptProperties", []):
            ingredients.append(
                {
                    "rxcui": prop.get("rxcui", ""),
                    "name": prop.get("name", ""),
                    "tty": prop.get("tty", ""),
                }
            )
    return ingredients


def get_rxcui_properties(rxcui: str) -> dict | None:
    """
    Return the properties for a given RxCUI (name, tty, language, etc.).

    Args:
        rxcui: RxCUI string.

    Returns:
        Dict with rxcui properties, or None if not found.
    """
    url = f"{_BASE_URL}/rxcui/{rxcui}/properties"
    data = _get_json(url)
    if data is None:
        return None
    return data.get("properties")
