"""Cross-source Observation matcher.

Takes per-source FHIR Observation lists and produces ``MergedObservation``
records — one per canonical lab fact, with all source measurements
attached longitudinally.

Match strategy (in priority order):

1. **LOINC code match** — both sources share a LOINC code. Most reliable.
2. **Bridge lookup** — one or both sources only have a free-text label;
   ``lib.harmonize.loinc_bridge`` resolves names to LOINC. Falls back to
   the normalized name when the bridge doesn't know the lab.
3. **Normalized-name passthrough** — neither source has LOINC and the
   bridge can't resolve. The merged fact still happens (so two text-only
   sources merge), but ``loinc_code`` is ``None``.

No temporal bucketing in v1: every source measurement becomes a separate
``ObservationSource`` on the merged record. The UI surfaces them
chronologically. Conflict detection is per-day same-source-or-cross-source
disagreement (see ``MergedObservation.has_conflict``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .loinc_bridge import canonical_for_loinc, lookup_by_name, normalize_name
from .models import MergedObservation, ObservationSource, ProvenanceEdge
from .units import convert


# ---------------------------------------------------------------------------
# Source description
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceBundle:
    """One source's contribution: a label + the FHIR Observations it emitted.

    Wrapping the raw list lets the matcher attribute every output
    ObservationSource back to a human-readable source name without
    re-deriving it from each Observation's ``meta.source``.
    """

    label: str
    """Human-readable source name, e.g. ``"Cedars-Sinai"``."""

    observations: list[dict[str, Any]]
    """The raw FHIR Observation resources from this source."""

    document_reference: str | None = None
    """Optional FHIR DocumentReference id for the source document
    (used by Provenance when the source is a PDF)."""


# ---------------------------------------------------------------------------
# Per-Observation extraction
# ---------------------------------------------------------------------------


def _extract_loinc(obs: dict[str, Any]) -> str | None:
    """Pull a LOINC code from an Observation's ``code.coding`` array, if any."""
    for c in obs.get("code", {}).get("coding", []):
        sys_ = c.get("system", "")
        if sys_.endswith("loinc.org") or sys_ == "http://loinc.org":
            code = c.get("code")
            if code:
                return code
    return None


def _extract_name(obs: dict[str, Any]) -> str:
    """Pull the best available human name for the Observation."""
    code = obs.get("code", {})
    if text := code.get("text"):
        return text
    for c in code.get("coding", []):
        if d := c.get("display"):
            return d
    return ""


def _extract_value_and_unit(obs: dict[str, Any]) -> tuple[float | None, str | None]:
    val = obs.get("valueQuantity") or {}
    v = val.get("value")
    u = val.get("unit") or val.get("code")
    if v is not None:
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = None
    return v, u


def _extract_date(obs: dict[str, Any]) -> datetime | None:
    for key in ("effectiveDateTime", "effectiveInstant", "issued"):
        v = obs.get(key)
        if v:
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
    period = obs.get("effectivePeriod") or {}
    start = period.get("start")
    if start:
        try:
            return datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def _obs_ref(obs: dict[str, Any], source_label: str, idx: int) -> str:
    """Stable reference back to the source Observation."""
    if rid := obs.get("id"):
        return f"Observation/{rid}"
    # Fall back to source-label + index when the Observation lacks an id
    # (common for freshly-extracted PDF Observations that haven't been
    # persisted yet).
    slug = source_label.lower().replace(" ", "-")
    return f"Observation/{slug}-{idx}"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def merge_observations(
    sources: Iterable[SourceBundle],
) -> list[MergedObservation]:
    """Merge Observations across sources into canonical ``MergedObservation`` records.

    Args:
        sources: One ``SourceBundle`` per ingestion path. Sources without
            Observations are accepted (treated as no-ops).

    Returns:
        A list of merged facts, one per distinct canonical identity. Order
        is canonical-name alphabetical; the longitudinal source list
        within each merged fact is chronological (oldest first).
    """
    # Match key → in-progress merged record
    by_key: dict[str, MergedObservation] = {}
    now = datetime.now()

    for bundle in sources:
        for idx, obs in enumerate(bundle.observations):
            loinc = _extract_loinc(obs)
            name = _extract_name(obs)

            # Resolve canonical identity.
            if loinc:
                bridge = canonical_for_loinc(loinc)
                if bridge:
                    canonical_name, canonical_unit = bridge
                else:
                    canonical_name, canonical_unit = name or loinc, None
                key = f"loinc:{loinc}"
                activity = "loinc-match"
            else:
                bridged = lookup_by_name(name)
                if bridged:
                    loinc, canonical_name, canonical_unit = bridged
                    key = f"loinc:{loinc}"
                    activity = "name-match"
                else:
                    norm = normalize_name(name)
                    if not norm:
                        continue
                    canonical_name, canonical_unit = name, None
                    key = f"name:{norm}"
                    activity = "passthrough"

            # Get source value, normalize unit if we have a canonical.
            raw_value, raw_unit = _extract_value_and_unit(obs)
            value, applied_unit = convert(
                raw_value, raw_unit, canonical_unit, loinc=loinc
            )
            # Track whether unit conversion happened — bumps the Provenance
            # activity from a plain match to "unit-normalize" for the edge.
            unit_converted = (
                raw_value is not None
                and raw_unit is not None
                and canonical_unit is not None
                and applied_unit == canonical_unit
                and raw_unit.lower().replace(" ", "") != canonical_unit.lower().replace(" ", "")
            )
            edge_activity = "unit-normalize" if unit_converted else activity

            ref = _obs_ref(obs, bundle.label, idx)
            source = ObservationSource(
                source_label=bundle.label,
                source_observation_ref=ref,
                value=value,
                unit=applied_unit,
                raw_value=raw_value,
                raw_unit=raw_unit,
                effective_date=_extract_date(obs),
                document_reference=bundle.document_reference,
            )

            merged = by_key.get(key)
            if merged is None:
                # New canonical fact.
                target_ref = (
                    f"Observation/merged-loinc-{loinc}"
                    if loinc
                    else f"Observation/merged-{normalize_name(canonical_name).replace(' ', '-')}"
                )
                merged = MergedObservation(
                    canonical_name=canonical_name,
                    loinc_code=loinc,
                    canonical_unit=canonical_unit,
                )
                # Stamp the merged ref onto a hidden attribute for provenance later
                merged._merged_ref = target_ref  # type: ignore[attr-defined]
                by_key[key] = merged

            merged.sources.append(source)
            merged.provenance.append(
                ProvenanceEdge(
                    target_ref=getattr(merged, "_merged_ref"),
                    source_ref=ref,
                    source_label=bundle.label,
                    activity=edge_activity,
                    recorded=now,
                )
            )

    # Chronological order within each merged record (oldest first), then
    # alphabetical across records for stable iteration. Naive and tz-aware
    # datetimes can co-exist across sources; key on UTC-normalized epoch.
    def _sort_key(s: ObservationSource) -> float:
        d = s.effective_date
        if d is None:
            return float("-inf")
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()

    for m in by_key.values():
        m.sources.sort(key=_sort_key)
    return sorted(by_key.values(), key=lambda m: m.canonical_name.lower())
