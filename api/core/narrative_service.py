"""Per-patient narrative orchestration (T5 / T6).

Reads the curated ``data/narratives/<patient_id>/episodes.json``,
materializes a harmonized FHIR Bundle from the workspace collection
(or falls back to the raw Synthea bundle when no workspace exists),
generates one Composition per episode, and persists each via
:func:`lib.narratives.storage.write_current_narrative`.

This module is the orchestration layer the FastAPI publish hook (T6)
calls. It is also the CLI surface — ``python -m lib.narratives
<patient_id>`` reaches the same entry point.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from api.core.loader import load_patient, path_from_patient_id
from lib.narratives import (
    SonnetNarrativeGenerator,
    generate_episode_narrative,
    write_current_narrative,
)
from lib.narratives.storage import NARRATIVE_STORE_ROOT


REPO_ROOT = Path(__file__).resolve().parents[2]
PATIENT_CONTEXT_STORE_ROOT = Path(
    os.getenv("PATIENT_CONTEXT_STORE_PATH", REPO_ROOT / "data" / "patient-context")
)


_logger = logging.getLogger(__name__)


def regenerate_all_episodes(
    patient_id: str,
    *,
    collection_id: str | None = None,
    generator=None,
    voice_summarizer=None,
    adjudicator=None,
) -> list[Path]:
    """Regenerate every episode narrative for ``patient_id``.

    Also regenerates:
      - ``voice_summary.json`` (T8a) so the patient-voice card stays fresh.
      - ``caveats.json`` (T7) so the conflicts panel reflects the
        current merged record.

    Returns the list of paths written. Errors in voice summary or
    caveats are logged but never block narrative regen. Per-episode
    narrative failures are tolerated so one bad episode doesn't block
    the others.
    """
    # T8a: voice summary regen runs first so even if no episodes exist
    # we still refresh the patient-voice card.
    try:
        from lib.patient_voice import regenerate_voice_summary

        regenerate_voice_summary(patient_id, summarizer=voice_summarizer)
    except Exception as exc:  # noqa: BLE001 — best-effort
        _logger.warning("voice summary regen failed for %s: %s", patient_id, exc)

    # T7: conflict adjudicator. Run before narratives so the narrative
    # generator can cite caveats if it ever needs to (Phase 2 P4).
    try:
        _regenerate_caveats(patient_id, collection_id=collection_id, adjudicator=adjudicator)
    except Exception as exc:  # noqa: BLE001 — best-effort
        _logger.warning("caveats regen failed for %s: %s", patient_id, exc)

    episodes_path = NARRATIVE_STORE_ROOT / patient_id / "episodes.json"
    if not episodes_path.exists():
        _logger.warning("no episodes.json for patient %s; skipping regen", patient_id)
        return []
    try:
        bundle = json.loads(episodes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _logger.error("episodes.json for %s is unreadable: %s", patient_id, exc)
        return []
    episodes = [
        e["resource"]
        for e in bundle.get("entry") or []
        if isinstance(e, dict)
        and isinstance(e.get("resource"), dict)
        and e["resource"].get("resourceType") == "EpisodeOfCare"
    ]
    if not episodes:
        return []

    harmonized = _load_harmonized_bundle(patient_id, collection_id=collection_id)
    patient_voice = _load_patient_voice_bundle(patient_id)
    backend = generator or SonnetNarrativeGenerator()

    written: list[Path] = []
    for episode in episodes:
        try:
            composition = generate_episode_narrative(
                patient_id=patient_id,
                episode=episode,
                harmonized_record=harmonized,
                patient_voice_bundle=patient_voice,
                generator=backend,
            )
            path = write_current_narrative(
                patient_id=patient_id, composition=composition
            )
            written.append(path)
        except Exception as exc:  # noqa: BLE001 — per-episode tolerance
            _logger.exception(
                "narrative regen failed for %s/%s: %s",
                patient_id,
                episode.get("id"),
                exc,
            )
    return written


def _load_harmonized_bundle(
    patient_id: str, *, collection_id: str | None = None
) -> dict[str, Any]:
    """Return a FHIR Bundle (collection) of merged resources for the patient.

    Preference order:
    1. If ``collection_id`` is given, use the harmonize service merged
       resources for that workspace collection.
    2. Otherwise try the workspace collection
       ``workspace-<patient_id>``.
    3. Fall back to the raw Synthea bundle on disk (for demo runs
       outside the workspace flow). When the Synthea bundle exists,
       its native shape already satisfies the generator's cite-index
       requirements.
    """
    cid = collection_id or f"workspace-{patient_id}"
    try:
        from api.core import harmonize_service

        entries: list[dict[str, Any]] = []
        for merged in harmonize_service.merged_conditions(cid):
            for src in merged.sources:
                entries.append(
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": src.source_condition_ref.rsplit("/", 1)[-1]
                            if "/" in src.source_condition_ref
                            else src.source_condition_ref,
                            "code": {"text": src.display},
                            "clinicalStatus": {
                                "coding": [{"code": src.clinical_status or "active"}]
                            },
                            "onsetDateTime": src.onset_date.isoformat()
                            if src.onset_date
                            else None,
                        }
                    }
                )
        for merged in harmonize_service.merged_medications(cid):
            entries.append(
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": _merged_id(getattr(merged, "_merged_ref", None))
                        or merged.canonical_name.lower().replace(" ", "-"),
                        "medicationCodeableConcept": {"text": merged.canonical_name},
                        "status": merged.canonical_status or "unknown",
                    }
                }
            )
        for merged in harmonize_service.merged_observations(cid):
            entries.append(
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": _merged_id(getattr(merged, "_merged_ref", None))
                        or merged.canonical_name.lower().replace(" ", "-"),
                        "code": {"text": merged.canonical_name},
                    }
                }
            )
        if entries:
            return {"resourceType": "Bundle", "type": "collection", "entry": entries}
    except Exception as exc:  # noqa: BLE001 — workspace not present, fall through
        _logger.debug("harmonize_service unavailable for %s: %s", cid, exc)

    # Fallback: load the raw Synthea bundle.
    bundle_path = path_from_patient_id(patient_id)
    if bundle_path is None:
        return {"resourceType": "Bundle", "type": "collection", "entry": []}
    try:
        return json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"resourceType": "Bundle", "type": "collection", "entry": []}


def _load_patient_voice_bundle(patient_id: str) -> dict[str, Any] | None:
    """Return the most recent patient-voice FHIR Bundle, if any.

    Multiple sessions are stored as separate files; Phase 1 uses the
    union (newest-mtime first) to render the prompt's turn list and
    cite-index. A future refinement can scope to turns whose
    ``created_at`` falls in the episode window — defer to P2.
    """
    fhir_dir = PATIENT_CONTEXT_STORE_ROOT / patient_id / "fhir"
    if not fhir_dir.exists():
        return None
    bundles = sorted(fhir_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not bundles:
        return None
    merged_entries: list[dict[str, Any]] = []
    meta_source = None
    for path in bundles:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("resourceType") != "Bundle":
            continue
        if meta_source is None:
            meta_source = (payload.get("meta") or {}).get("source")
        merged_entries.extend(payload.get("entry") or [])
    if not merged_entries:
        return None
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"source": meta_source} if meta_source else {},
        "entry": merged_entries,
    }


def _merged_id(merged_ref: str | None) -> str | None:
    if not merged_ref:
        return None
    if "/" in merged_ref:
        return merged_ref.rsplit("/", 1)[-1]
    return merged_ref


def _regenerate_caveats(
    patient_id: str,
    *,
    collection_id: str | None,
    adjudicator,
) -> None:
    """Scan the harmonized record for conflicts; write caveats.json (T7).

    When the workspace collection exists, walks its merged medications
    / observations / allergies. Falls back to writing an empty bundle
    when there's nothing to scan (so the UI sees a stable file shape).
    """
    from lib.harmonize.adjudicator import adjudicate_merged_record, write_caveats

    merged_meds: list = []
    merged_obs: list = []
    merged_allergies: list = []
    cid = collection_id or f"workspace-{patient_id}"
    try:
        from api.core import harmonize_service

        if harmonize_service.get_collection(cid) is not None:
            merged_meds = list(harmonize_service.merged_medications(cid))
            merged_obs = list(harmonize_service.merged_observations(cid))
            merged_allergies = list(harmonize_service.merged_allergies(cid))
    except Exception as exc:  # noqa: BLE001
        _logger.debug("harmonize_service unavailable for caveats: %s", exc)

    caveats = adjudicate_merged_record(
        patient_id,
        merged_medications=merged_meds,
        merged_observations=merged_obs,
        merged_allergies=merged_allergies,
        adjudicator=adjudicator,
    )
    write_caveats(patient_id, caveats)
