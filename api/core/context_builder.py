"""
Context Builder — transforms raw FHIR patient data into token-efficient,
clinician-ready context for LLM consumption.

Implements Layers 0, 1, 3, 4 of the 5-layer context engineering pipeline
described in patient-journey/CONTEXT-ENGINEERING.md:

  Layer 0: Hard filters (remove billing noise, routine vitals, old resolved conditions)
  Layer 1: Episode compression (deduplicate meds, compress encounters)
  Layer 3: Format optimization (structured markdown, temporal markers)
  Layer 4: Review posture selection (general chart review by default;
           specialized context packages can narrow the workflow)

Layer 2 (LLM batch enrichment) is deferred to Phase 2.

Design principles:
  1. Lead with what kills (safety-critical info first)
  2. Time is the first dimension (every item has temporal context)
  3. Compress, don't discard (episodes not individual records)
  4. Declare absences (explicitly state what's NOT present)
  5. Rules for structure, LLM for meaning
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from api.core.loader import load_active_published_run, load_patient, path_from_patient_id
from api.core.sof_tools import DEFAULT_SOF_DB
from lib.clinical.drug_classifier import DrugClassifier

_DRUG_CLASSIFIER = DrugClassifier(
    mapping_path=_REPO_ROOT / "lib" / "clinical" / "drug_classes.json"
)
_MISSING = object()

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PatientVoiceContext:
    """Brief first-person summary of patient-reported facts (T8a)."""
    summary: str
    citations: list[str] = field(default_factory=list)


@dataclass
class EpisodeBrief:
    """One-line summary of an EpisodeOfCare narrative (T8b)."""
    episode_id: str
    type: str
    period_start: str
    period_end: str | None
    one_liner: str


@dataclass
class HarmonizationCaveat:
    """Structured LLM-adjudicated conflict (T7) for UI surfacing."""
    fact_path: str
    verdict: str
    confidence: str
    rationale: str
    dissenting_sources: list[str] = field(default_factory=list)


@dataclass
class ClinicalContext:
    """The assembled clinical context ready for LLM consumption."""
    patient_summary: str          # one-line patient summary
    safety_flags: list[str]       # safety-critical items (always first)
    interactions: list[str]       # drug-drug interactions
    active_medications: list[str] # current meds with drug class + reason
    active_conditions: list[str]  # current problem list
    key_labs: list[str]           # latest clinically important lab values
    clinical_notes: list[str]     # narrative note/document context
    recent_encounters: list[str]  # last N encounters with diagnosis
    procedures_summary: list[str] # recent/significant procedures
    historical_meds: list[str]    # compressed stopped medication episodes
    resolved_conditions: list[str]  # compressed resolved conditions
    absences: list[str]           # explicitly declared absences

    # T8a/T8b/T7 — LLM-augmented context fields. All read from disk in
    # `build_clinical_context`; never (re-)computed on the request path.
    patient_voice: PatientVoiceContext | None = None
    episode_briefs: list[EpisodeBrief] = field(default_factory=list)
    caveats: list[HarmonizationCaveat] = field(default_factory=list)

    # Metadata
    total_tokens_estimate: int = 0
    fact_count: int = 0

    def to_prompt(self) -> str:
        """Render as a structured markdown string for the LLM system prompt."""
        sections: list[str] = []

        sections.append(f"# Patient: {self.patient_summary}\n")

        # T8c: lead with the patient's own words so the clinician (and
        # the LLM) reasons about the patient as a person, not just a
        # set of structured rows. The plan §6 demo arc relies on this
        # being the first sentence of Caspian's system prompt.
        if self.patient_voice and self.patient_voice.summary:
            sections.append(f"In the patient's own words: {self.patient_voice.summary}\n")

        if self.episode_briefs:
            sections.append("## CARE EPISODES")
            for brief in self.episode_briefs:
                period = brief.period_start
                if brief.period_end:
                    period = f"{brief.period_start} → {brief.period_end}"
                sections.append(f"- **{brief.type}** ({period}): {brief.one_liner}")
            sections.append("")

        if self.caveats:
            sections.append("## OPEN CONFLICTS (LLM-adjudicated; clinician review pending)")
            for c in self.caveats:
                sections.append(
                    f"- `{c.fact_path}` → verdict: **{c.verdict}** "
                    f"({c.confidence} confidence). {c.rationale}"
                )
            sections.append("")

        if self.safety_flags:
            sections.append("## SAFETY FLAGS (Action Required)")
            sections.extend(self.safety_flags)
            sections.append("")

        if self.interactions:
            sections.append("## DRUG INTERACTIONS")
            sections.extend(self.interactions)
            sections.append("")

        if self.active_medications:
            sections.append("## ACTIVE MEDICATIONS")
            sections.extend(self.active_medications)
            sections.append("")

        if self.active_conditions:
            sections.append("## ACTIVE CONDITIONS (Problem List)")
            sections.extend(self.active_conditions)
            sections.append("")

        if self.key_labs:
            sections.append("## KEY LAB VALUES (Latest)")
            sections.extend(self.key_labs)
            sections.append("")

        if self.clinical_notes:
            sections.append("## CLINICAL NOTES AND DOCUMENT CONTEXT")
            sections.extend(self.clinical_notes)
            sections.append("")

        if self.recent_encounters:
            sections.append("## RECENT ENCOUNTERS")
            sections.extend(self.recent_encounters)
            sections.append("")

        if self.procedures_summary:
            sections.append("## PROCEDURES")
            sections.extend(self.procedures_summary)
            sections.append("")

        if self.historical_meds:
            sections.append("## HISTORICAL MEDICATIONS (Stopped)")
            sections.extend(self.historical_meds)
            sections.append("")

        if self.resolved_conditions:
            sections.append("## RESOLVED CONDITIONS")
            sections.extend(self.resolved_conditions)
            sections.append("")

        if self.absences:
            sections.append("## NOTABLE ABSENCES")
            sections.extend(self.absences)
            sections.append("")

        result = "\n".join(sections)
        # Rough token estimate (~4 chars per token)
        self.total_tokens_estimate = len(result) // 4
        self.fact_count = (
            len(self.safety_flags) + len(self.interactions) +
            len(self.active_medications) + len(self.active_conditions) +
            len(self.key_labs) + len(self.clinical_notes) + len(self.recent_encounters) +
            len(self.procedures_summary) + len(self.historical_meds) +
            len(self.resolved_conditions) + len(self.absences)
        )
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_date(dt_str: str | None) -> str:
    if not dt_str:
        return "unknown"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return dt_str[:10] if dt_str else "unknown"


def _duration_str(start_str: str | None, end_str: str | None = None) -> str:
    """Compute human-readable duration from ISO date strings."""
    if not start_str:
        return ""
    try:
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str) if end_str else datetime.now(timezone.utc)
        days = (end - start).days
        if days < 30:
            return f"{days}d"
        if days < 365:
            return f"{days // 30}mo"
        years = days / 365.25
        return f"{years:.1f}yr"
    except (ValueError, TypeError):
        return ""


def _patient_uuid_from_id(patient_id: str) -> str | None:
    """Extract FHIR patient UUID from API patient_id (filename stem)."""
    import json
    path = path_from_patient_id(patient_id)
    if not path:
        return None
    with open(path) as f:
        bundle = json.load(f)
    return _patient_uuid_from_bundle(bundle)


def _patient_uuid_from_bundle(bundle: dict[str, Any] | None) -> str | None:
    if not isinstance(bundle, dict):
        return None
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            full_url = entry.get("fullUrl", "")
            if full_url.startswith("urn:uuid:"):
                return full_url.removeprefix("urn:uuid:")
    return None


def _load_bundle_json(path: Path | None) -> dict[str, Any] | None:
    import json

    if path is None:
        return None
    try:
        with open(path) as f:
            bundle = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return bundle if isinstance(bundle, dict) else None


def _medication_reason_index_from_bundle(bundle: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(bundle, dict):
        return {}

    ref_index = {
        entry.get("fullUrl", ""): entry["resource"]
        for entry in bundle.get("entry", [])
        if isinstance(entry, dict) and isinstance(entry.get("resource"), dict)
    }
    reasons: dict[str, str] = {}
    for entry in bundle.get("entry", []):
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource", {})
        if not isinstance(resource, dict) or resource.get("resourceType") != "MedicationRequest":
            continue
        drug_text = str(resource.get("medicationCodeableConcept", {}).get("text", "")).strip().lower()
        if not drug_text:
            continue
        for ref in resource.get("reasonReference", []):
            if not isinstance(ref, dict):
                continue
            display = str(ref.get("display", "")).strip()
            if not display:
                target = ref_index.get(str(ref.get("reference", "")), {})
                if isinstance(target, dict):
                    display = str(target.get("code", {}).get("text", "")).strip()
            if display:
                reasons[drug_text] = display
                break
    return reasons


# ---------------------------------------------------------------------------
# Key lab codes (LOINC) that matter for high-speed clinical review
# ---------------------------------------------------------------------------

KEY_LAB_LOINCS = {
    "4548-4":  "HbA1c",
    "2160-0":  "Creatinine",
    "3094-0":  "BUN",
    "6299-2":  "BUN",
    "2951-2":  "Sodium",
    "2947-0":  "Sodium",
    "2823-3":  "Potassium",
    "6298-4":  "Potassium",
    "2093-3":  "Cholesterol",
    "2571-8":  "Triglycerides",
    "718-7":   "Hemoglobin",
    "20570-8": "Hematocrit",
    "4544-3":  "Hematocrit",
    "777-3":   "Platelets",
    "6690-2":  "WBC",
    "5902-2":  "PT (Prothrombin Time)",
    "34714-6": "INR",
    "6301-6":  "INR",
    "62238-1": "eGFR",
    "33914-3": "eGFR",
    "2345-7":  "Glucose",
    "2339-0":  "Glucose",
    "3173-2":  "PTT",
    "10839-9": "Troponin",
    "42637-9": "BNP",
    "33762-6": "proBNP",
    "1742-6":  "ALT",
    "1920-8":  "AST",
    "1975-2":  "Bilirubin",
    "2085-9":  "HDL",
    "2089-1":  "LDL",
    "30313-1": "Hemoglobin A1c",  # alternate code
}


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    return dt.strftime("%b %d, %Y")


def _value_text(value: float | None, unit: str = "") -> str:
    if value is None:
        return "value not recorded"
    try:
        rendered = f"{float(value):.1f}" if float(value) != int(float(value)) else str(int(float(value)))
    except (ValueError, TypeError):
        rendered = str(value)
    return f"{rendered} {unit}".strip()


def _compact_text(value: Any, max_chars: int = 700) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _is_active_med_status(status: str) -> bool:
    return status.lower() in {"active", "on-hold", "intended", "draft"}


def _build_record_medication_context(record, classifier: Any) -> tuple[list[str], list[str]]:
    active_meds: list[str] = []
    historical_meds: list[str] = []
    med_class_map = {
        classified.medication.med_id: classified.matched_classes
        for classified in classifier.classify_all(record.medications)
    }
    meds_sorted = sorted(record.medications, key=lambda med: med.authored_on or datetime.min, reverse=True)

    for med in meds_sorted[:80]:
        status = med.status or "unknown"
        classes = med_class_map.get(med.med_id, [])
        class_text = f" [{', '.join(classes)}]" if classes else ""
        reason_text = f" — for {med.reason_display}" if med.reason_display else ""
        line = f"- **{med.display or 'Unknown medication'}**{class_text}{reason_text} | {status} | {_fmt_dt(med.authored_on)}"
        if _is_active_med_status(status):
            active_meds.append(line)
        else:
            historical_meds.append(line.replace("**", ""))

    return active_meds[:25], historical_meds[:25]


def _build_record_condition_context(record) -> tuple[list[str], list[str]]:
    active_conditions: list[str] = []
    resolved_conditions: list[str] = []
    conditions_sorted = sorted(
        record.conditions,
        key=lambda condition: condition.onset_dt or condition.recorded_dt or datetime.min,
        reverse=True,
    )

    for condition in conditions_sorted[:80]:
        label = condition.code.label()
        status = condition.clinical_status or ("active" if condition.is_active else "unknown")
        onset = condition.onset_dt or condition.recorded_dt
        line = f"- **{label}** | {status} | {_fmt_dt(onset)}"
        if condition.is_active or status in {"active", "recurrence", "relapse"}:
            active_conditions.append(line)
        else:
            resolved_conditions.append(line.replace("**", ""))

    return active_conditions[:30], resolved_conditions[:25]


def _build_record_lab_context(record) -> list[str]:
    quantity_observations = [
        obs for obs in record.observations
        if obs.value_quantity is not None and (obs.loinc_code or obs.display)
    ]
    latest_by_key = {}
    for obs in quantity_observations:
        key = obs.loinc_code or obs.display
        current = latest_by_key.get(key)
        if current is None or (obs.effective_dt or datetime.min) > (current.effective_dt or datetime.min):
            latest_by_key[key] = obs

    key_labs = [
        latest_by_key[loinc]
        for loinc in KEY_LAB_LOINCS
        if loinc in latest_by_key
    ]
    recent_labs = sorted(
        latest_by_key.values(),
        key=lambda obs: obs.effective_dt or datetime.min,
        reverse=True,
    )
    selected_keys = {obs.loinc_code or obs.display for obs in key_labs}
    for obs in recent_labs:
        key = obs.loinc_code or obs.display
        if key not in selected_keys:
            key_labs.append(obs)
            selected_keys.add(key)
        if len(key_labs) >= 16:
            break

    lines: list[str] = []
    for obs in key_labs[:16]:
        lab_name = KEY_LAB_LOINCS.get(obs.loinc_code, obs.display or obs.loinc_code or "Observation")
        status_text = f", {obs.status}" if obs.status else ""
        lines.append(f"- **{lab_name}**: {_value_text(obs.value_quantity, obs.value_unit)} ({_fmt_dt(obs.effective_dt)}{status_text})")
    return lines


def _build_published_clinical_note_context(
    patient_id: str,
    limit: int = 8,
    *,
    published_run: dict[str, Any] | None | object = _MISSING,
) -> list[str]:
    """Surface note/document artifacts from the active published workspace.

    The shared PatientRecord facade intentionally focuses on normalized FHIR
    facts. Published harmonization runs also carry narrative artifacts that are
    important for chart-grounded Q&A, so the assistant context reads them from
    the durable run artifact when a workspace has been published.
    """
    run = load_active_published_run(patient_id) if published_run is _MISSING else published_run
    if not run:
        return []
    candidate = run.get("candidate_record")
    if not isinstance(candidate, dict):
        return []
    artifacts = candidate.get("clinical_artifacts")
    if not isinstance(artifacts, dict):
        return []
    raw_notes = [note for note in artifacts.get("clinical_notes") or [] if isinstance(note, dict)]
    raw_notes.sort(key=lambda note: str(note.get("date") or ""), reverse=True)

    seen: set[str] = set()
    lines: list[str] = []
    for note in raw_notes:
        text = _compact_text(note.get("text"))
        if not text or text in seen:
            continue
        seen.add(text)
        source = str(note.get("source_label") or note.get("source_id") or "source document")
        resource_type = str(note.get("resource_type") or "Clinical note")
        date = _fmt_date(str(note.get("date") or "")) if note.get("date") else "date unknown"
        resource_id = str(note.get("resource_id") or "").strip()
        encounter_id = str(note.get("encounter_id") or "").strip()
        ref = f" | {resource_type}/{resource_id}" if resource_id else f" | {resource_type}"
        if encounter_id:
            ref += f" | Encounter/{encounter_id}"
        lines.append(f"- **{resource_type} note** from {source} ({date}){ref}: {text}")
        if len(lines) >= limit:
            break
    return lines


def _build_record_clinical_note_context(record, limit: int = 6) -> list[str]:
    lines: list[str] = []
    for report in sorted(record.diagnostic_reports, key=lambda r: r.effective_dt or datetime.min, reverse=True):
        text = _compact_text(report.presented_form_text)
        if not text:
            continue
        label = report.code.label() or "Diagnostic report"
        lines.append(f"- **DiagnosticReport note** {label} ({_fmt_dt(report.effective_dt)} | {report.status or 'status unknown'}): {text}")
        if len(lines) >= limit:
            break
    return lines


def _linked_resource_summary(encounter) -> str:
    linked = {
        "obs": len(encounter.linked_observations),
        "conditions": len(encounter.linked_conditions),
        "meds": len(encounter.linked_medications),
        "procedures": len(encounter.linked_procedures),
        "reports": len(encounter.linked_diagnostic_reports),
        "immunizations": len(encounter.linked_immunizations),
    }
    parts = [f"{count} {label}" for label, count in linked.items() if count]
    return "; ".join(parts)


def _build_record_encounter_context(record) -> list[str]:
    encounters = sorted(record.encounters, key=lambda enc: enc.period.start or datetime.min, reverse=True)
    lines: list[str] = []
    for encounter in encounters[:12]:
        class_text = encounter.class_code or "UNK"
        type_text = encounter.encounter_type or "Encounter"
        reason = f" — {encounter.reason_display}" if encounter.reason_display else ""
        provider = encounter.practitioner_name or encounter.provider_org or "provider/source unknown"
        linked = _linked_resource_summary(encounter)
        linked_text = f" | linked: {linked}" if linked else ""
        lines.append(f"- {_fmt_dt(encounter.period.start)} | {class_text} | {type_text}{reason} | {provider}{linked_text}")
    return lines


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_clinical_context(patient_id: str) -> ClinicalContext:
    """
    Build a clean, structured clinical context for a patient.

    Pulls from both the FHIR bundle (via load_patient) and the SOF warehouse
    (for deduplicated medication episodes and latest labs).
    """
    # Load patient record
    result = load_patient(patient_id)
    if result is None:
        raise ValueError(f"Patient not found: {patient_id}")
    record, stats = result

    active_published_run = load_active_published_run(patient_id)

    # Get patient demographics. Uploaded/published workspace records do not have
    # a backing Synthea file path, so prefer the parsed record summary.
    path = path_from_patient_id(patient_id)
    source_bundle = _load_bundle_json(path)
    medication_reasons = _medication_reason_index_from_bundle(source_bundle)
    name = stats.name or record.summary.name or patient_id

    # Resolve FHIR UUID for SOF queries. When an active published snapshot
    # exists, the selected chart scope is the published facade, not global SOF.
    fhir_uuid = None if active_published_run is not None else _patient_uuid_from_bundle(source_bundle)
    patient_ref = f"urn:uuid:{fhir_uuid}" if fhir_uuid else None
    sof_conn: sqlite3.Connection | None = None
    if patient_ref and DEFAULT_SOF_DB.exists():
        sof_conn = sqlite3.connect(f"file:{DEFAULT_SOF_DB}?mode=ro", uri=True)
        sof_conn.row_factory = sqlite3.Row

    # --- Patient summary line ---
    demographics: list[str] = [name]
    if record.summary.birth_date:
        demographics.append(f"DOB {record.summary.birth_date.isoformat()}")
    if record.summary.gender:
        demographics.append(record.summary.gender)
    if record.summary.city or record.summary.state:
        demographics.append(", ".join(part for part in [record.summary.city, record.summary.state] if part))
    patient_summary = " · ".join(demographics)

    # --- Safety flags from drug classifier ---
    raw_flags = _DRUG_CLASSIFIER.generate_safety_flags(record.medications)

    safety_flags: list[str] = []
    interactions_list: list[str] = []

    for flag in raw_flags:
        if flag.status == "NONE":
            continue
        med_names = [cm.medication.display for cm in flag.medications[:3]]
        meds_str = ", ".join(med_names) if med_names else "none listed"
        severity_icon = {"critical": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(flag.severity, "•")
        status_label = "ACTIVE" if flag.status == "ACTIVE" else "HISTORICAL"
        safety_flags.append(
            f"- {severity_icon} **{flag.label}** ({flag.severity}, {status_label}): {meds_str}"
        )
        if flag.surgical_note:
            safety_flags.append(f"  Action: {flag.surgical_note}")

    # --- Drug interactions ---
    from api.core.interaction_checker import check_interactions
    active_class_keys = [f.class_key for f in raw_flags if f.status == "ACTIVE"]
    interactions_raw = check_interactions(active_class_keys)
    for item in interactions_raw:
        drug_a_label = item.drug_a.replace("_", " ").title()
        drug_b_label = item.drug_b.replace("_", " ").title()
        interactions_list.append(
            f"- **{item.severity.upper()}**: {drug_a_label} + {drug_b_label} — {item.clinical_effect}"
        )
        if item.management:
            interactions_list.append(f"  Management: {item.management}")

    # --- Active medications (from SOF medication_episode, deduplicated) ---
    active_meds: list[str] = []
    historical_meds: list[str] = []

    try:
        if sof_conn is not None:
            med_rows = sof_conn.execute(
                """SELECT display, drug_class, latest_status, is_active,
                          start_date, end_date, duration_days, request_count
                   FROM medication_episode
                   WHERE patient_ref = ?
                   ORDER BY is_active DESC, start_date DESC""",
                (patient_ref,),
            ).fetchall()

            for row in med_rows:
                dur = _duration_str(row["start_date"], row["end_date"])
                reason = medication_reasons.get(row["display"].strip().lower(), "")
                reason_str = f" — for {reason}" if reason else ""
                drug_class = f" [{row['drug_class']}]" if row["drug_class"] else ""

                if row["is_active"]:
                    active_meds.append(
                        f"- **{row['display']}**{drug_class}{reason_str} | Since {_fmt_date(row['start_date'])} ({dur}) | {row['request_count']} Rx"
                    )
                else:
                    historical_meds.append(
                        f"- {row['display']}{drug_class}{reason_str} | {_fmt_date(row['start_date'])} → {_fmt_date(row['end_date'])} ({dur})"
                    )

        if not active_meds and not historical_meds:
            active_meds, historical_meds = _build_record_medication_context(record, _DRUG_CLASSIFIER)

        # --- Active conditions (from SOF) ---
        active_conditions: list[str] = []
        resolved_conditions: list[str] = []

        if sof_conn is not None:
            cond_rows = sof_conn.execute(
                """SELECT display, clinical_status, onset_date
                   FROM condition
                   WHERE patient_ref = ?
                   ORDER BY onset_date""",
                (patient_ref,),
            ).fetchall()

            for row in cond_rows:
                dur = _duration_str(row["onset_date"])
                if row["clinical_status"] in ("active", "recurrence", "relapse"):
                    active_conditions.append(
                        f"- **{row['display']}** | Since {_fmt_date(row['onset_date'])} ({dur})"
                    )
                else:
                    resolved_conditions.append(
                        f"- {row['display']} ({row['clinical_status']}) | Onset {_fmt_date(row['onset_date'])}"
                    )
        if not active_conditions and not resolved_conditions:
            active_conditions, resolved_conditions = _build_record_condition_context(record)

        # --- Key labs (from SOF observation_latest) ---
        key_labs: list[str] = []

        if sof_conn is not None:
            loinc_list = ",".join(f"'{k}'" for k in KEY_LAB_LOINCS.keys())
            lab_rows = sof_conn.execute(
                f"""SELECT loinc_code, display, value_quantity, value_unit, effective_date
                   FROM observation_latest
                   WHERE patient_ref = ? AND loinc_code IN ({loinc_list})
                   ORDER BY effective_date DESC""",
                (patient_ref,),
            ).fetchall()

            for row in lab_rows:
                lab_name = KEY_LAB_LOINCS.get(row["loinc_code"], row["display"])
                value = row["value_quantity"]
                unit = row["value_unit"] or ""
                date = _fmt_date(row["effective_date"])
                if value is not None:
                    # Round to reasonable precision
                    try:
                        val_str = f"{float(value):.1f}" if float(value) != int(float(value)) else str(int(float(value)))
                    except (ValueError, TypeError):
                        val_str = str(value)
                    key_labs.append(f"- **{lab_name}**: {val_str} {unit} ({date})")

        if not key_labs:
            key_labs = _build_record_lab_context(record)

        # --- Clinical notes and narrative document context ---
        clinical_notes = _build_published_clinical_note_context(
            patient_id,
            published_run=active_published_run,
        )
        if not clinical_notes:
            clinical_notes = _build_record_clinical_note_context(record)

        # --- Recent encounters (from SOF, last 10 with diagnoses) ---
        recent_encounters: list[str] = []

        if sof_conn is not None:
            enc_rows = sof_conn.execute(
                """SELECT e.class_code, e.type_text, e.period_start,
                          GROUP_CONCAT(c.display, '; ') as diagnoses
                   FROM encounter e
                   LEFT JOIN condition c ON c.encounter_ref = 'urn:uuid:' || e.id
                   WHERE e.patient_ref = ?
                   GROUP BY e.id
                   ORDER BY e.period_start DESC
                   LIMIT 10""",
                (patient_ref,),
            ).fetchall()

            for row in enc_rows:
                cls = {"AMB": "Ambulatory", "IMP": "Inpatient", "EMER": "Emergency", "VR": "Virtual"}.get(row["class_code"], row["class_code"])
                date = _fmt_date(row["period_start"])
                dx = f" — **{row['diagnoses']}**" if row["diagnoses"] else ""
                type_text = row["type_text"] or ""
                recent_encounters.append(f"- {date} | {cls} | {type_text}{dx}")

        if not recent_encounters:
            recent_encounters = _build_record_encounter_context(record)

        # --- Procedures summary (from FHIR, grouped) ---
        procedures_summary: list[str] = []
        from collections import Counter
        proc_counts: Counter[str] = Counter()
        for p in record.procedures:
            proc_counts[p.code.label()] += 1
        for proc_name, count in proc_counts.most_common(10):
            if count > 1:
                procedures_summary.append(f"- {proc_name} (×{count})")
            else:
                procedures_summary.append(f"- {proc_name}")

        # --- Notable absences ---
        absences: list[str] = []
        all_class_keys = {f.class_key for f in raw_flags}
        critical_classes = {"anticoagulants", "antiplatelets", "opioids", "immunosuppressants"}
        for cls in critical_classes - all_class_keys:
            label = cls.replace("_", " ").title()
            absences.append(f"- No {label} (current or historical)")
        for flag in raw_flags:
            if flag.status == "NONE" and flag.severity == "critical":
                absences.append(f"- No {flag.label} found")

        # Check for allergies
        if not record.allergies:
            absences.append("- No allergies recorded")
        else:
            for allergy in record.allergies[:5]:
                safety_flags.append(f"- ⚠️ **Allergy**: {allergy.code.label()} (criticality: {allergy.criticality or 'unknown'})")

        # T8b: read LLM-augmented context from disk. Generation happens at
        # publish/intake time (D8); the request path is purely a disk read.
        patient_voice_ctx = _load_patient_voice_context(patient_id)
        episode_briefs = _load_episode_briefs(patient_id)
        caveats = _load_caveats(patient_id)

        return ClinicalContext(
            patient_summary=patient_summary,
            safety_flags=safety_flags,
            interactions=interactions_list,
            active_medications=active_meds,
            active_conditions=active_conditions,
            key_labs=key_labs,
            clinical_notes=clinical_notes,
            recent_encounters=recent_encounters,
            procedures_summary=procedures_summary,
            historical_meds=historical_meds,
            resolved_conditions=resolved_conditions,
            absences=absences,
            patient_voice=patient_voice_ctx,
            episode_briefs=episode_briefs,
            caveats=caveats,
        )
    finally:
        if sof_conn is not None:
            sof_conn.close()


# ---------------------------------------------------------------------------
# T8b loaders — disk reads, no LLM
# ---------------------------------------------------------------------------


def _load_patient_voice_context(patient_id: str) -> PatientVoiceContext | None:
    """Read the cached PatientVoiceSummary if present."""
    try:
        from lib.patient_voice import load_summary
    except ImportError:
        return None
    summary = load_summary(patient_id)
    if summary is None or not summary.summary:
        return None
    return PatientVoiceContext(summary=summary.summary, citations=list(summary.citations))


def _load_episode_briefs(patient_id: str) -> list[EpisodeBrief]:
    """Read episode metadata + each episode's Composition summary section."""
    import json as _json

    episodes_path = _REPO_ROOT / "data" / "narratives" / patient_id / "episodes.json"
    if not episodes_path.exists():
        return []
    try:
        bundle = _json.loads(episodes_path.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return []
    briefs: list[EpisodeBrief] = []
    for entry in bundle.get("entry") or []:
        episode = (entry or {}).get("resource") or {}
        if episode.get("resourceType") != "EpisodeOfCare":
            continue
        ep_id = str(episode.get("id") or "")
        slug = ep_id[len("episode-"):] if ep_id.startswith("episode-") else ep_id
        type_arr = episode.get("type") or []
        type_text = (
            (type_arr[0] or {}).get("text")
            or (((type_arr[0] or {}).get("coding") or [{}])[0]).get("display")
            or "(unspecified)"
        ) if type_arr else "(unspecified)"
        period = episode.get("period") or {}
        one_liner = _read_summary_section(patient_id, slug)
        briefs.append(
            EpisodeBrief(
                episode_id=ep_id,
                type=type_text,
                period_start=str(period.get("start") or ""),
                period_end=str(period.get("end")) if period.get("end") else None,
                one_liner=one_liner,
            )
        )
    return briefs


def _read_summary_section(patient_id: str, episode_slug: str) -> str:
    """Pull the 'Summary' section text from a Composition's current.json."""
    import json as _json
    import re as _re

    path = _REPO_ROOT / "data" / "narratives" / patient_id / episode_slug / "current.json"
    if not path.exists():
        return "(narrative not yet generated — publish to regenerate)"
    try:
        composition = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return "(narrative unreadable)"
    for section in composition.get("section") or []:
        if str(section.get("title", "")).lower() == "summary":
            div = (section.get("text") or {}).get("div") or ""
            return _re.sub(r"<[^>]+>", "", div).strip() or "(empty summary)"
    return "(no summary section)"


def _load_caveats(patient_id: str) -> list[HarmonizationCaveat]:
    """Read T7 caveats.json if present."""
    import json as _json

    path = _REPO_ROOT / "data" / "patient-context" / patient_id / "caveats.json"
    if not path.exists():
        return []
    try:
        payload = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return []
    out: list[HarmonizationCaveat] = []
    for entry in payload.get("entry") or []:
        resource = (entry or {}).get("resource") or {}
        if resource.get("resourceType") != "Observation":
            continue
        components = {
            (c.get("code") or {}).get("text"): c.get("valueString", "")
            for c in (resource.get("component") or [])
            if isinstance(c, dict)
        }
        dissent = components.get("dissenting_sources", "")
        out.append(
            HarmonizationCaveat(
                fact_path=str(components.get("fact_path", "")),
                verdict=str(components.get("verdict", "")),
                confidence=str(components.get("confidence", "medium")),
                rationale=str(components.get("rationale", "")),
                dissenting_sources=[s for s in dissent.split(";") if s],
            )
        )
    return out
