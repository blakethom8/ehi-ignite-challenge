"""
Episode detector — detects medication start/stop/change events and
groups conditions into clinical episodes.

An "episode" here means a continuous period of treatment or a cluster
of related clinical events. This powers both the medication Gantt chart
and the condition tracker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from fhir_explorer.parser.models import (
    ConditionRecord,
    EncounterRecord,
    MedicationRecord,
    PatientRecord,
)


# ---------------------------------------------------------------------------
# Medication episodes
# ---------------------------------------------------------------------------

@dataclass
class MedicationEpisode:
    """A continuous period during which a medication was prescribed.

    Synthea data gives us one MedicationRequest per encounter where a drug
    was prescribed/continued. We group these into episodes by drug name
    to build the Gantt chart.
    """
    display: str
    rxnorm_code: str
    status: str                             # latest status
    requests: list[MedicationRecord] = field(default_factory=list)
    start_date: datetime | None = None
    end_date: datetime | None = None        # None = still active
    is_active: bool = False
    dosage_text: str = ""
    reason: str = ""

    @property
    def duration_days(self) -> float | None:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).total_seconds() / 86400
        return None


def detect_medication_episodes(
    medications: list[MedicationRecord],
) -> list[MedicationEpisode]:
    """Group MedicationRequest records into episodes by drug name.

    Synthea typically generates one MedicationRequest per encounter for
    ongoing medications. We group by normalized display name and track
    the earliest authored_on as start and latest as end.
    """
    # Group by normalized drug name (lowercase, stripped)
    groups: dict[str, list[MedicationRecord]] = {}
    for med in medications:
        key = med.display.strip().lower()
        if not key:
            continue
        groups.setdefault(key, []).append(med)

    episodes: list[MedicationEpisode] = []

    for _key, meds in groups.items():
        # Sort by authored date
        dated = [m for m in meds if m.authored_on]
        dated.sort(key=lambda m: m.authored_on)  # type: ignore[arg-type]

        if not dated:
            # No dates — still create an episode with what we have
            ref = meds[0]
            episodes.append(MedicationEpisode(
                display=ref.display,
                rxnorm_code=ref.rxnorm_code,
                status=ref.status,
                requests=meds,
                dosage_text=ref.dosage_text,
                reason=ref.reason_display,
            ))
            continue

        ref = dated[0]
        latest = dated[-1]

        # Determine if still active
        is_active = latest.status in ("active", "on-hold")

        episode = MedicationEpisode(
            display=ref.display,
            rxnorm_code=ref.rxnorm_code,
            status=latest.status,
            requests=list(meds),
            start_date=dated[0].authored_on,
            end_date=None if is_active else dated[-1].authored_on,
            is_active=is_active,
            dosage_text=latest.dosage_text or ref.dosage_text,
            reason=ref.reason_display or latest.reason_display,
        )
        episodes.append(episode)

    # Sort by start date (earliest first), then by name
    episodes.sort(key=lambda e: (e.start_date or datetime.min, e.display.lower()))
    return episodes


# ---------------------------------------------------------------------------
# Condition episodes
# ---------------------------------------------------------------------------

@dataclass
class ConditionEpisode:
    """A condition with its timeline and related encounters."""
    condition: ConditionRecord
    related_encounters: list[EncounterRecord] = field(default_factory=list)
    related_medications: list[MedicationRecord] = field(default_factory=list)


def detect_condition_episodes(record: PatientRecord) -> list[ConditionEpisode]:
    """Build condition episodes by linking conditions to their encounters
    and medications via encounter IDs."""
    # Build lookup: encounter_id -> encounter
    enc_index = record.encounter_index

    # Build lookup: encounter_id -> medications ordered in that encounter
    meds_by_enc: dict[str, list[MedicationRecord]] = {}
    for med in record.medications:
        if med.encounter_id:
            meds_by_enc.setdefault(med.encounter_id, []).append(med)

    episodes: list[ConditionEpisode] = []

    for cond in record.conditions:
        related_encs: list[EncounterRecord] = []
        related_meds: list[MedicationRecord] = []

        if cond.encounter_id:
            enc = enc_index.get(cond.encounter_id)
            if enc:
                related_encs.append(enc)
            related_meds.extend(meds_by_enc.get(cond.encounter_id, []))

        episodes.append(ConditionEpisode(
            condition=cond,
            related_encounters=related_encs,
            related_medications=related_meds,
        ))

    # Sort: active first, then by onset date descending
    episodes.sort(key=lambda e: (
        0 if e.condition.is_active else 1,
        -(e.condition.onset_dt or datetime.min).timestamp(),
    ))

    return episodes
