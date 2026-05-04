"""Provenance graph emission for Layer 3 harmonization.

Every gold-tier resource gets at least one Provenance resource recording
how it was produced from silver-tier source records. The Provenance graph
is written as line-delimited JSON to corpus/gold/<patient>/provenance.ndjson
(lazy-loadable). Per docs/INTEGRATION.md, this is the file the existing app
walks when a clinician clicks "where did this fact come from?"

This module also exposes the Extension URLs we mint for our custom provenance
tracking, ensuring Layer-3 sub-tasks reference them by constant rather than
string literal.

Typical Layer-3 harmonize sub-task usage::

    from ehi_atlas.harmonize.provenance import (
        ProvenanceWriter, merge_provenance, attach_quality_score, attach_merge_rationale
    )

    with ProvenanceWriter(gold_root, patient_id="rhett759") as pw:
        # Merge two Hypertension Conditions across sources
        merged_condition = build_merged_condition(...)
        attach_quality_score(merged_condition, 0.94)
        attach_merge_rationale(merged_condition, "UMLS CUI C0020538 hit on both sources")

        pw.add(merge_provenance(
            target=f"Condition/{merged_condition['id']}",
            sources=[
                "Condition/synthea-cond-htn-001",
                "Condition/epic-ehi-PROBLEM_LIST-row-42",
            ],
            rationale="UMLS CUI hit on Hypertensive disorder (C0020538)",
        ))
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ehi_atlas import __version__

# ---------------------------------------------------------------------------
# Extension namespace — FROZEN.  Per docs/PROVENANCE-SPEC.md.
# ---------------------------------------------------------------------------

EXT_BASE = "https://ehi-atlas.example/fhir/StructureDefinition"

EXT_QUALITY_SCORE = f"{EXT_BASE}/quality-score"
EXT_CONFLICT_PAIR = f"{EXT_BASE}/conflict-pair"
EXT_EXTRACTION_MODEL = f"{EXT_BASE}/extraction-model"
EXT_EXTRACTION_CONFIDENCE = f"{EXT_BASE}/extraction-confidence"
EXT_EXTRACTION_PROMPT_VER = f"{EXT_BASE}/extraction-prompt-version"
EXT_SOURCE_ATTACHMENT = f"{EXT_BASE}/source-attachment"
EXT_SOURCE_LOCATOR = f"{EXT_BASE}/source-locator"
EXT_MERGE_RATIONALE = f"{EXT_BASE}/merge-rationale"
EXT_UMLS_CUI = f"{EXT_BASE}/umls-cui"

# Tag systems (used by adapters / standardizers / harmonizers)
SYS_BASE = "https://ehi-atlas.example/fhir/CodeSystem"
SYS_SOURCE_TAG = f"{SYS_BASE}/source-tag"
SYS_LIFECYCLE = f"{SYS_BASE}/lifecycle"
SYS_LLM_MODEL = f"{SYS_BASE}/llm-model"

# Activity codes — v3-DataOperation system
ACTIVITY_SYS = "http://terminology.hl7.org/CodeSystem/v3-DataOperation"
ActivityCode = Literal["MERGE", "DERIVE", "EXTRACT", "TRANSFORM"]

# ---------------------------------------------------------------------------
# Deterministic default timestamp for Phase 1 reproducibility.
# Production runs would use real timestamps; for the showcase patient demo
# we want byte-identical re-runs.  Layer-3 sub-tasks that want a live
# timestamp can still pass recorded=datetime.now(timezone.utc).isoformat().
# ---------------------------------------------------------------------------
DEFAULT_RECORDED = "2026-04-29T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    """A reference to a silver-tier resource that contributed to a gold resource."""

    reference: str  # e.g. "Condition/cedars-abc123"
    role: str = "source"  # FHIR Provenance.entity.role: "source" | "derivation" | etc.
    display: str | None = None


def _coerce_source(s: str | SourceRef) -> SourceRef:
    """Accept a bare reference string or a SourceRef; always return SourceRef."""
    if isinstance(s, SourceRef):
        return s
    return SourceRef(reference=s)


@dataclass
class ProvenanceRecord:
    """A single Provenance resource describing one harmonize decision.

    Attributes:
        target_reference: FHIR relative reference to the gold-tier resource
            this Provenance is about, e.g. ``"Condition/harmonized-htn-blake"``.
        activity: One of MERGE | DERIVE | EXTRACT | TRANSFORM.
        sources: Silver-tier records that contributed.  Use :class:`SourceRef`
            for role/display control or bare strings for "source" role.
        recorded: ISO-8601 timestamp.  Defaults to ``DEFAULT_RECORDED`` for
            deterministic Phase 1 re-runs.
        rationale: Human-readable explanation of the merge/derive decision.
        agent_display: Override the agent display string; default is the
            package version string ``"ehi-atlas v0.1.0"``.
    """

    target_reference: str
    activity: ActivityCode
    sources: list[SourceRef]
    recorded: str | None = None
    rationale: str | None = None
    agent_display: str | None = None

    def to_fhir(self) -> dict:
        """Emit the FHIR R4 Provenance resource as a plain dict.

        Structural validity is the caller's concern (BundleValidator is the
        downstream gatekeeper); this method emits a spec-compliant shape.
        """
        recorded = self.recorded or DEFAULT_RECORDED
        agent = self.agent_display or f"ehi-atlas v{__version__}"
        prov: dict = {
            "resourceType": "Provenance",
            "target": [{"reference": self.target_reference}],
            "recorded": recorded,
            "activity": {
                "coding": [{"system": ACTIVITY_SYS, "code": self.activity}]
            },
            "agent": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": (
                                    "http://terminology.hl7.org/CodeSystem/"
                                    "provenance-participant-type"
                                ),
                                "code": "performer",
                            }
                        ]
                    },
                    "who": {"display": agent},
                }
            ],
            "entity": [
                {
                    "role": s.role,
                    "what": (
                        {"reference": s.reference, "display": s.display}
                        if s.display
                        else {"reference": s.reference}
                    ),
                }
                for s in self.sources
            ],
        }
        return prov


# ---------------------------------------------------------------------------
# High-level builder functions
# ---------------------------------------------------------------------------


def merge_provenance(
    *,
    target: str,
    sources: list[str | SourceRef],
    rationale: str | None = None,
    recorded: str | None = None,
) -> ProvenanceRecord:
    """Build a MERGE Provenance — N silver records → one gold record.

    Args:
        target: Reference to the gold resource, e.g. ``"Condition/harmonized-htn-blake"``.
        sources: Silver records that were merged.  Accept bare strings or :class:`SourceRef`.
        rationale: Optional one-line explanation (e.g. "UMLS CUI C0020538 match").
        recorded: ISO-8601 timestamp; defaults to ``DEFAULT_RECORDED``.
    """
    return ProvenanceRecord(
        target_reference=target,
        activity="MERGE",
        sources=[_coerce_source(s) for s in sources],
        rationale=rationale,
        recorded=recorded,
    )


def derive_provenance(
    *,
    target: str,
    source: str | SourceRef,
    rationale: str | None = None,
    recorded: str | None = None,
) -> ProvenanceRecord:
    """Build a DERIVE Provenance — one silver record → one gold record via transformation.

    Args:
        target: Reference to the derived gold resource.
        source: The single silver resource this was derived from.
        rationale: Optional explanation.
        recorded: ISO-8601 timestamp; defaults to ``DEFAULT_RECORDED``.
    """
    return ProvenanceRecord(
        target_reference=target,
        activity="DERIVE",
        sources=[_coerce_source(source)],
        rationale=rationale,
        recorded=recorded,
    )


def extract_provenance(
    *,
    target: str,
    source_attachment: str,  # "Binary/<id>"
    rationale: str | None = None,
    recorded: str | None = None,
) -> ProvenanceRecord:
    """Build an EXTRACT Provenance — unstructured source (PDF, note) → gold resource.

    The canonical extractor is ``ehi_atlas.extract.pdf.extract_from_pdf`` (task 4.3).
    The ``source_attachment`` should be the reference to the ``Binary`` resource the
    extraction came from.

    Args:
        target: Reference to the extracted gold resource.
        source_attachment: ``"Binary/<id>"`` reference to the source document.
        rationale: Optional explanation.
        recorded: ISO-8601 timestamp; defaults to ``DEFAULT_RECORDED``.
    """
    return ProvenanceRecord(
        target_reference=target,
        activity="EXTRACT",
        sources=[SourceRef(reference=source_attachment, role="source")],
        rationale=rationale,
        recorded=recorded,
    )


def transform_provenance(
    *,
    target: str,
    source: str | SourceRef,
    rationale: str | None = None,
    recorded: str | None = None,
) -> ProvenanceRecord:
    """Build a TRANSFORM Provenance — format conversion (CCDA→FHIR, TSV→FHIR).

    Args:
        target: Reference to the transformed gold resource.
        source: The silver resource this was transformed from.
        rationale: Optional explanation.
        recorded: ISO-8601 timestamp; defaults to ``DEFAULT_RECORDED``.
    """
    return ProvenanceRecord(
        target_reference=target,
        activity="TRANSFORM",
        sources=[_coerce_source(source)],
        rationale=rationale,
        recorded=recorded,
    )


# ---------------------------------------------------------------------------
# Resource-meta helpers
# ---------------------------------------------------------------------------


def _ensure_meta(resource: dict) -> dict:
    """Ensure ``resource["meta"]`` exists and return it."""
    if "meta" not in resource:
        resource["meta"] = {}
    return resource["meta"]


def _ensure_meta_extensions(resource: dict) -> list:
    """Ensure ``resource["meta"]["extension"]`` exists and return it."""
    meta = _ensure_meta(resource)
    if "extension" not in meta:
        meta["extension"] = []
    return meta["extension"]


def _ensure_resource_extensions(resource: dict) -> list:
    """Ensure ``resource["extension"]`` (top-level) exists and return it."""
    if "extension" not in resource:
        resource["extension"] = []
    return resource["extension"]


def attach_quality_score(resource: dict, score: float) -> dict:
    """Add the ``.../quality-score`` extension to ``resource.meta``.

    Idempotent — if the URL is already present, the value is updated in place.
    Returns the modified dict.

    Args:
        resource: A mutable FHIR resource dict.
        score: Quality score in [0, 1].
    """
    exts = _ensure_meta_extensions(resource)
    for ext in exts:
        if ext.get("url") == EXT_QUALITY_SCORE:
            ext["valueDecimal"] = score
            return resource
    exts.append({"url": EXT_QUALITY_SCORE, "valueDecimal": score})
    return resource


def attach_conflict_pair(resource: dict, other_reference: str) -> dict:
    """Add the ``.../conflict-pair`` extension to the resource (top level, not meta).

    Per spec, conflict-pair is on the resource itself — not in meta — because it
    references another resource in the same gold bundle.

    Args:
        resource: A mutable FHIR resource dict.
        other_reference: The reference string of the conflicting resource,
            e.g. ``"MedicationRequest/epic-atorvastatin-row42"``.
    """
    exts = _ensure_resource_extensions(resource)
    for ext in exts:
        if ext.get("url") == EXT_CONFLICT_PAIR:
            ext["valueReference"] = {"reference": other_reference}
            return resource
    exts.append(
        {"url": EXT_CONFLICT_PAIR, "valueReference": {"reference": other_reference}}
    )
    return resource


def attach_merge_rationale(resource: dict, rationale: str) -> dict:
    """Add the ``.../merge-rationale`` extension to the resource (top level).

    One-line explanation of why this merge happened. Per spec this goes on the
    resource itself so the Sources panel can surface it without loading Provenance.

    Args:
        resource: A mutable FHIR resource dict.
        rationale: Human-readable merge rationale.
    """
    exts = _ensure_resource_extensions(resource)
    for ext in exts:
        if ext.get("url") == EXT_MERGE_RATIONALE:
            ext["valueString"] = rationale
            return resource
    exts.append({"url": EXT_MERGE_RATIONALE, "valueString": rationale})
    return resource


def attach_umls_cui(coding: dict, cui: str) -> dict:
    """Add the ``.../umls-cui`` extension to a single ``CodeableConcept.coding[i]`` dict.

    This goes on an individual coding entry (not on the resource or meta), per spec.

    Args:
        coding: A ``{"system": ..., "code": ..., "display": ...}`` dict.
        cui: The UMLS Concept Unique Identifier, e.g. ``"C0020538"``.
    """
    if "extension" not in coding:
        coding["extension"] = []
    for ext in coding["extension"]:
        if ext.get("url") == EXT_UMLS_CUI:
            ext["valueString"] = cui
            return coding
    coding["extension"].append({"url": EXT_UMLS_CUI, "valueString": cui})
    return coding


def attach_extraction_provenance(
    resource: dict,
    *,
    model: str,
    confidence: float,
    prompt_version: str,
    source_attachment: str,
    source_locator: str | None = None,
) -> dict:
    """Add the five extraction-related extensions to ``resource.meta``.

    This is the helper that Layer 2-B's ``to_fhir.py`` should ideally call.
    Currently ``ehi_atlas/extract/to_fhir.py`` builds these inline; that is a
    known tech-debt item flagged for a follow-up refactor — do NOT touch
    ``to_fhir.py`` as part of this task.

    Extensions added (per PROVENANCE-SPEC.md):
    - ``.../extraction-model`` → valueCoding with SYS_LLM_MODEL system
    - ``.../extraction-confidence`` → valueDecimal
    - ``.../extraction-prompt-version`` → valueString
    - ``.../source-attachment`` → valueReference
    - ``.../source-locator`` → valueString (if provided)

    Args:
        resource: A mutable FHIR resource dict.
        model: Model name / code (e.g. ``"claude-opus-4-7"``).
        confidence: Extraction confidence in [0, 1].
        prompt_version: Frozen prompt version string (e.g. ``"v0.1.0"``).
        source_attachment: ``"Binary/<id>"`` reference to the source document.
        source_locator: Optional ``"page=N;bbox=x1,y1,x2,y2"`` string.
    """
    exts = _ensure_meta_extensions(resource)

    def _upsert(url: str, value_key: str, value: object) -> None:
        for ext in exts:
            if ext.get("url") == url:
                ext[value_key] = value
                return
        exts.append({"url": url, value_key: value})

    _upsert(
        EXT_EXTRACTION_MODEL,
        "valueCoding",
        {"system": SYS_LLM_MODEL, "code": model},
    )
    _upsert(EXT_EXTRACTION_CONFIDENCE, "valueDecimal", confidence)
    _upsert(EXT_EXTRACTION_PROMPT_VER, "valueString", prompt_version)
    _upsert(
        EXT_SOURCE_ATTACHMENT,
        "valueReference",
        {"reference": source_attachment},
    )
    if source_locator is not None:
        _upsert(EXT_SOURCE_LOCATOR, "valueString", source_locator)

    return resource


# ---------------------------------------------------------------------------
# ProvenanceWriter
# ---------------------------------------------------------------------------


class ProvenanceWriter:
    """Accumulates Provenance records for a patient and writes ``provenance.ndjson``.

    Records are sorted by ``(recorded, target_reference)`` before writing so that
    byte-identical re-runs are guaranteed given the same inputs and
    :data:`DEFAULT_RECORDED` timestamps.

    Usage::

        with ProvenanceWriter(gold_root, patient_id="rhett759") as writer:
            writer.add(merge_provenance(target=..., sources=...))
            writer.add(extract_provenance(...))
        # writer.flush() called automatically on __exit__

    The output file is at ``gold_root / "patients" / patient_id / "provenance.ndjson"``.
    """

    def __init__(self, gold_root: Path, patient_id: str) -> None:
        self._gold_root = Path(gold_root)
        self._patient_id = patient_id
        self._records: list[ProvenanceRecord] = []

    @property
    def output_path(self) -> Path:
        """Absolute path to the ``provenance.ndjson`` file."""
        return self._gold_root / "patients" / self._patient_id / "provenance.ndjson"

    def add(self, record: ProvenanceRecord) -> None:
        """Accumulate a single :class:`ProvenanceRecord`."""
        self._records.append(record)

    def add_many(self, records: list[ProvenanceRecord]) -> None:
        """Accumulate multiple :class:`ProvenanceRecord` objects at once."""
        self._records.extend(records)

    def flush(self) -> Path:
        """Sort records and write ``provenance.ndjson``; returns the output path.

        Sort key is ``(recorded ASC, target_reference ASC)`` for deterministic
        byte-identical output.  Creates the parent directory if needed.
        """
        out = self.output_path
        out.parent.mkdir(parents=True, exist_ok=True)

        # Materialise FHIR dicts and sort for determinism
        fhir_records = [r.to_fhir() for r in self._records]
        fhir_records.sort(
            key=lambda d: (
                d.get("recorded", DEFAULT_RECORDED),
                d.get("target", [{}])[0].get("reference", ""),
            )
        )

        with out.open("w", encoding="utf-8") as fh:
            for rec in fhir_records:
                fh.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False))
                fh.write("\n")

        return out

    def __enter__(self) -> "ProvenanceWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        if exc_type is None:
            self.flush()
