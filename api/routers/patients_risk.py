"""
/api/patients — risk, safety, lab-alert, and interaction endpoints.

This sub-router is mounted by ``api.routers.patients`` (the orchestrator)
which provides the ``/patients`` prefix and ``patients`` tag.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request

from api.core.auth import DEMO_PATIENTS, require_access_session
from api.core.condition_ranker import ConditionRanker
from api.core.interaction_checker import check_interactions
from api.core.loader import (
    list_patient_files,
    load_patient,
    patient_id_from_path,
)
from api.models import (
    InteractionResponse,
    InteractionResult,
    KeyLabsResponse,
    LabAlertFlag,
    LabHistoryPoint,
    LabValue,
    PatientRiskSummary,
    PatientRiskSummaryResponse,
    SafetyFlag,
    SafetyMedication,
    SafetyResponse,
    SurgicalRiskComponent,
    SurgicalRiskResponse,
    TimelineEvent,
    TimelineMonth,
)
from api.routers._patients_shared import (
    _authorized_patient_id,
    _classifier,
)

router = APIRouter(prefix="/patients", tags=["patients"])

_condition_ranker = ConditionRanker()


# ---------------------------------------------------------------------------
# Pre-operative hold/bridge protocol notes — keyed by drug class
# ---------------------------------------------------------------------------

PROTOCOL_NOTES: dict[str, str] = {
    "anticoagulants": (
        "Hold warfarin 5 days pre-op; check INR day of surgery (target <1.5). "
        "Bridge with LMWH (enoxaparin 1 mg/kg SQ BID) for high-thromboembolic-risk patients "
        "(mechanical heart valve, AF with CHA₂DS₂-VASc ≥4, recent VTE <3 months). "
        "Last LMWH dose 24h pre-op. Resume warfarin evening of surgery if hemostasis adequate."
    ),
    "antiplatelets": (
        "Hold aspirin 7 days pre-op (or continue low-dose 81mg if cardiac stent within 12 months — "
        "discuss with cardiologist). Hold clopidogrel/ticagrelor 5–7 days pre-op. "
        "Do NOT hold if drug-eluting stent placed within 12 months without cardiology sign-off."
    ),
    "jak_inhibitors": (
        "Hold 1–2 weeks pre-op per ACR guidelines (tofacitinib: 3 days minimum; "
        "baricitinib/upadacitinib: 3 days minimum). Restart after wound healing confirmed, "
        "typically 2 weeks post-op. Increased infection risk; ensure prophylactic antibiotics given."
    ),
    "immunosuppressants": (
        "Do NOT abruptly discontinue. Consult with prescribing specialist (transplant/rheumatology). "
        "Tacrolimus/cyclosporine: continue at reduced dose, monitor levels day of surgery. "
        "Mycophenolate: typically held 1 week pre-op for elective cases. "
        "Perioperative stress-dose steroids may be needed."
    ),
    "nsaids": (
        "Hold NSAIDs (ibuprofen, naproxen, indomethacin) 3–5 days pre-op due to platelet "
        "dysfunction and renal effects. COX-2 inhibitors (celecoxib) may be continued if needed "
        "for pain control — consult surgeon. Post-op: restart only after renal function confirmed stable."
    ),
    "opioids": (
        "Continue chronic opioids up to day of surgery to avoid withdrawal. "
        "Inform anesthesia team — increased intraoperative and post-op opioid requirements expected. "
        "Consider multimodal analgesia plan. Buprenorphine: consult pain management — "
        "may need dose adjustment or conversion."
    ),
    "anticonvulsants": (
        "Continue anticonvulsants without interruption. Do not hold pre-op. "
        "Ensure IV formulation available if patient unable to take PO post-op. "
        "Phenytoin/carbamazepine: CYP450 inducers — may alter anesthetic metabolism. "
        "Inform anesthesia team."
    ),
    "corticosteroids": (
        "Do NOT abruptly discontinue. Patients on chronic steroids (>5mg prednisone/day for >3 weeks) "
        "may have HPA axis suppression. Administer stress-dose steroids: hydrocortisone 50mg IV "
        "at induction + 25mg q8h x24h for major surgery. Taper back to baseline dose post-op."
    ),
    "maois": (
        "Ideally hold MAOIs 14 days pre-op due to risk of hypertensive crisis and serotonin syndrome "
        "with anesthetic agents. Discuss with psychiatry before stopping. "
        "If surgery cannot be delayed: avoid meperidine, indirect sympathomimetics, and serotonergic agents. "
        "Use direct-acting vasopressors only."
    ),
    "antidiabetics": (
        "Hold metformin 24–48h pre-op (lactic acidosis risk with contrast/renal changes). "
        "Sulfonylureas: hold morning of surgery (hypoglycemia risk). "
        "Insulin: give 50–80% of basal dose morning of surgery; hold mealtime insulin. "
        "Monitor glucose q1–2h intraoperatively; target 140–180 mg/dL. "
        "GLP-1 agonists (semaglutide): hold 1 week pre-op due to gastroparesis risk."
    ),
}

HIGH_RISK_CONDITION_CATEGORIES = {"CARDIAC", "PULMONARY"}
MODERATE_RISK_CONDITION_CATEGORIES = {"RENAL", "HEPATIC", "HEMATOLOGIC", "VASCULAR"}
REVIEW_RISK_CONDITION_CATEGORIES = {"METABOLIC", "NEUROLOGIC", "IMMUNOLOGIC", "ONCOLOGIC"}
COAGULATION_LOINC_CODES = {"6301-6", "34714-6", "5902-2", "3173-2"}


def _component_status(score: int, flagged: bool = False, review: bool = False) -> str:
    if flagged:
        return "FLAGGED"
    if review or score > 0:
        return "REVIEW"
    return "CLEARED"


def _limit_evidence(items: list[str], limit: int = 5) -> list[str]:
    if len(items) <= limit:
        return items
    return items[:limit] + [f"+{len(items) - limit} more"]


# ---------------------------------------------------------------------------
# Lab alert thresholds
# (loinc_code): (display_name, low_critical, low_warning, high_warning, high_critical, unit)
# None = threshold not applicable for that direction
# ---------------------------------------------------------------------------

ALERT_THRESHOLDS: dict[str, tuple[str, float | None, float | None, float | None, float | None, str]] = {
    "718-7":  ("Hemoglobin",  6.0,  8.0,   17.5, 20.0,  "g/dL"),
    "4544-3": ("Hematocrit",  18.0, 24.0,  52.0, 60.0,  "%"),
    "20570-8": ("Hematocrit", 18.0, 24.0,  52.0, 60.0,  "%"),
    "777-3":  ("Platelets",   50.0, 100.0, 400.0, 1000.0, "10*3/uL"),
    "6690-2": ("WBC",         2.0,  4.0,   11.0, 20.0,  "10*3/uL"),
    "6301-6": ("INR",         None, None,  3.0,  5.0,   ""),
    "34714-6": ("INR",        None, None,  3.0,  5.0,   ""),
    "2160-0": ("Creatinine",  None, None,  1.5,  3.0,   "mg/dL"),
    "2823-3": ("Potassium",   3.0,  3.5,   5.5,  6.5,   "mmol/L"),
    "2951-2": ("Sodium",      125.0, 130.0, 148.0, 155.0, "mmol/L"),
    "2345-7": ("Glucose",     50.0, 70.0,  200.0, 400.0, "mg/dL"),
    "3094-0": ("BUN",         None, 7.0,   20.0, 40.0,  "mg/dL"),
    "1751-7": ("Albumin",     None, 2.5,   None, None,  "g/dL"),
    "6768-6": ("Alk Phos",    None, None,  120.0, 300.0, "U/L"),
}


def _lab_reference_label(
    low_reference: float | None,
    high_reference: float | None,
    unit: str,
) -> str:
    unit_suffix = f" {unit}" if unit else ""
    if low_reference is not None and high_reference is not None:
        return f"{low_reference:g}-{high_reference:g}{unit_suffix}"
    if low_reference is not None:
        return f">= {low_reference:g}{unit_suffix}"
    if high_reference is not None:
        return f"<= {high_reference:g}{unit_suffix}"
    return ""


def _interpret_lab_value(
    loinc_code: str,
    value: float | None,
    source_reference_low: float | None = None,
    source_reference_high: float | None = None,
    source_reference_unit: str = "",
) -> tuple[str, str | None, float | None, float | None, str, str]:
    """Return abnormality, alert severity, reference bounds, unit, and label."""
    threshold = ALERT_THRESHOLDS.get(loinc_code)
    has_source_reference = source_reference_low is not None or source_reference_high is not None
    if value is None or (threshold is None and not has_source_reference):
        return "unknown", None, None, None, "", ""

    low_critical: float | None = None
    low_warning: float | None = None
    high_warning: float | None = None
    high_critical: float | None = None
    threshold_unit = ""
    if threshold is not None:
        _display, low_critical, low_warning, high_warning, high_critical, threshold_unit = threshold

    low_reference = source_reference_low if has_source_reference else low_warning
    high_reference = source_reference_high if has_source_reference else high_warning
    unit = source_reference_unit if has_source_reference else threshold_unit
    abnormality = "normal"
    severity: str | None = None
    threshold_direction: str | None = None

    if low_critical is not None and value < low_critical:
        severity = "critical"
        threshold_direction = "low"
    elif high_critical is not None and value > high_critical:
        severity = "critical"
        threshold_direction = "high"
    elif low_warning is not None and value < low_warning:
        severity = "warning"
        threshold_direction = "low"
    elif high_warning is not None and value > high_warning:
        severity = "warning"
        threshold_direction = "high"

    if low_reference is not None and value < low_reference:
        abnormality = "low"
    elif high_reference is not None and value > high_reference:
        abnormality = "high"

    if threshold_direction is not None and threshold_direction != abnormality:
        severity = None

    return (
        abnormality,
        severity,
        low_reference,
        high_reference,
        unit,
        _lab_reference_label(low_reference, high_reference, unit),
    )


def _obs_date_to_date(obs_dt: datetime | None) -> date | None:
    """Extract a date from an observation's effective_dt (datetime or date)."""
    if obs_dt is None:
        return None
    if isinstance(obs_dt, datetime):
        return obs_dt.date()
    return obs_dt  # already a date


def _compute_alert_flags(record, today_dt: date) -> list[LabAlertFlag]:
    """
    Scan all observations within the last 30 days against ALERT_THRESHOLDS.
    Returns deduplicated (most recent per LOINC), sorted critical-first then by days_ago.
    """
    cutoff = today_dt.toordinal() - 30

    # Collect all recent, matchable observations grouped by loinc_code
    # Structure: loinc_code → list of (obs, value_float, days_ago)
    candidates: dict[str, list[tuple]] = defaultdict(list)

    for obs in record.observations:
        if obs.loinc_code not in ALERT_THRESHOLDS:
            continue
        if obs.value_type != "quantity" or obs.value_quantity is None:
            continue
        obs_date = _obs_date_to_date(obs.effective_dt)
        if obs_date is None:
            continue
        days_ago = today_dt.toordinal() - obs_date.toordinal()
        if days_ago > 30 or days_ago < 0:
            continue
        candidates[obs.loinc_code].append((obs, obs.value_quantity, days_ago))

    # For trend detection, also gather all historical readings per LOINC (sorted newest-first)
    all_by_loinc: dict[str, list] = defaultdict(list)
    for obs in record.observations:
        if obs.loinc_code in ALERT_THRESHOLDS and obs.value_type == "quantity" and obs.value_quantity is not None:
            all_by_loinc[obs.loinc_code].append(obs)

    for loinc_code in all_by_loinc:
        all_by_loinc[loinc_code].sort(
            key=lambda o: o.effective_dt or datetime.min, reverse=True
        )

    flags: list[LabAlertFlag] = []

    for loinc_code, obs_list in candidates.items():
        # Take the most recent observation for this LOINC (smallest days_ago)
        obs_list.sort(key=lambda t: t[2])  # sort by days_ago ascending
        most_recent_obs, value, days_ago = obs_list[0]

        display_name, low_crit, low_warn, high_warn, high_crit, unit = ALERT_THRESHOLDS[loinc_code]

        severity: str | None = None
        direction: str | None = None

        # Check critical first (harder threshold)
        if low_crit is not None and value < low_crit:
            severity = "critical"
            direction = "low"
        elif high_crit is not None and value > high_crit:
            severity = "critical"
            direction = "high"
        elif low_warn is not None and value < low_warn:
            severity = "warning"
            direction = "low"
        elif high_warn is not None and value > high_warn:
            severity = "warning"
            direction = "high"

        # Check trend (only if no harder flag already set, or to augment a warning)
        if severity is None or severity == "warning":
            history = all_by_loinc.get(loinc_code, [])
            if len(history) >= 3:
                last3_vals = [h.value_quantity for h in history[:3] if h.value_quantity is not None]
                if len(last3_vals) == 3:
                    v0, v1, v2 = last3_vals[0], last3_vals[1], last3_vals[2]
                    # Trending up: each successive reading increases by >5%
                    if v2 != 0 and v1 != 0:
                        r1 = (v1 - v2) / abs(v2)  # v1 vs v2 (older)
                        r2 = (v0 - v1) / abs(v1)  # v0 vs v1 (newer)
                        if r1 > 0.05 and r2 > 0.05 and severity is None:
                            severity = "warning"
                            direction = "trending_up"
                        elif r1 < -0.05 and r2 < -0.05 and severity is None:
                            severity = "warning"
                            direction = "trending_down"

        if severity is None or direction is None:
            continue

        # Build message
        unit_str = f" {unit}" if unit else ""
        if direction == "low":
            msg = f"{display_name} {value}{unit_str} — critically low" if severity == "critical" else f"{display_name} {value}{unit_str} — below normal"
        elif direction == "high":
            msg = f"{display_name} {value}{unit_str} — critically high" if severity == "critical" else f"{display_name} {value}{unit_str} — above normal"
        elif direction == "trending_up":
            msg = f"{display_name} {value}{unit_str} — trending upward over last 3 readings"
        else:
            msg = f"{display_name} {value}{unit_str} — trending downward over last 3 readings"

        flags.append(LabAlertFlag(
            lab_name=display_name,
            loinc_code=loinc_code,
            value=value,
            unit=unit,
            severity=severity,
            direction=direction,
            message=msg,
            days_ago=days_ago,
        ))

    # Sort: critical first, then warning; within severity, sort by days_ago ascending
    flags.sort(key=lambda f: (0 if f.severity == "critical" else 1, f.days_ago))
    return flags


def _compute_timeline_events(record, today_dt: date) -> list[TimelineMonth]:
    """
    Build 6-month monthly buckets of LOINC observations for ALERT_THRESHOLDS codes.

    For each calendar month in the last 6 months (oldest → newest):
    - Find all observations matching any tracked LOINC code
    - For each code with a value in that month, record change_direction vs prior month
    - Only include months with at least one event
    """
    # Build a list of (year, month) tuples covering the last 6 months, oldest first
    months: list[tuple[int, int]] = []
    y, m = today_dt.year, today_dt.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()  # oldest first

    # Collect all observations for tracked LOINC codes with quantity values
    # Keyed by (loinc_code, year, month) → list of (date, value, display, unit)
    obs_by_code_month: dict[tuple[str, int, int], list[tuple[date, float, str, str]]] = defaultdict(list)

    for obs in record.observations:
        if obs.loinc_code not in ALERT_THRESHOLDS:
            continue
        if obs.value_type != "quantity" or obs.value_quantity is None:
            continue
        obs_date = _obs_date_to_date(obs.effective_dt)
        if obs_date is None:
            continue
        obs_by_code_month[(obs.loinc_code, obs_date.year, obs_date.month)].append(
            (obs_date, obs.value_quantity, obs.display or ALERT_THRESHOLDS[obs.loinc_code][0], obs.value_unit or ALERT_THRESHOLDS[obs.loinc_code][5])
        )

    result_months: list[TimelineMonth] = []

    # Track prior month value per loinc_code for change_direction
    prior_month_values: dict[str, float] = {}

    for yr, mo in months:
        events: list[TimelineEvent] = []

        for loinc_code, (display_name, _lc, _lw, _hw, _hc, unit) in ALERT_THRESHOLDS.items():
            bucket = obs_by_code_month.get((loinc_code, yr, mo))
            if not bucket:
                continue

            # Use the most recent observation in that month
            bucket.sort(key=lambda t: t[0], reverse=True)
            obs_date, value, obs_display, obs_unit = bucket[0]

            # Compute change_direction vs prior month
            prior = prior_month_values.get(loinc_code)
            if prior is None:
                change_direction = "stable"
            else:
                pct = (value - prior) / abs(prior) if prior != 0 else 0.0
                if pct > 0.05:
                    change_direction = "up"
                elif pct < -0.05:
                    change_direction = "down"
                else:
                    change_direction = "stable"

            events.append(TimelineEvent(
                loinc_code=loinc_code,
                display_name=obs_display if obs_display else display_name,
                value=value,
                unit=obs_unit if obs_unit else unit,
                date=obs_date.isoformat(),
                change_direction=change_direction,
            ))

            # Update prior for next month's comparison
            prior_month_values[loinc_code] = value

        if events:
            import calendar as _cal
            label = f"{_cal.month_abbr[mo]} {yr}"
            result_months.append(TimelineMonth(
                month=f"{yr:04d}-{mo:02d}",
                label=label,
                events=events,
            ))

    return result_months


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/risk-summary", response_model=PatientRiskSummaryResponse)
def patient_risk_summary(request: Request) -> PatientRiskSummaryResponse:
    session = require_access_session(request)
    summary = _cached_patient_risk_summary()
    if not session.is_demo:
        return summary
    by_id = {item.id: item for item in summary.patients}
    return PatientRiskSummaryResponse(
        patients=[
            item.model_copy(update={"id": demo.alias_id, "name": demo.name})
            for demo in DEMO_PATIENTS
            if (item := by_id.get(demo.actual_patient_id)) is not None
        ]
    )


@lru_cache(maxsize=1)
def _cached_patient_risk_summary() -> PatientRiskSummaryResponse:
    """
    Return all patients enriched with risk tier and critical safety flags.

    NOTE: This iterates all 1,180 patient files and calls the drug classifier
    for each. First call is slow (~30-60s). Subsequent calls per patient are
    instant because load_patient() is LRU-cached.
    """
    files = list_patient_files()
    results: list[PatientRiskSummary] = []

    for path in files:
        patient_id = patient_id_from_path(path)
        result = load_patient(patient_id)
        if result is None:
            continue

        record, stats = result

        # Classify medications to find active critical-severity drug classes
        raw_flags = _classifier.generate_safety_flags(record.medications)
        active_critical_classes: list[str] = [
            flag.class_key
            for flag in raw_flags
            if flag.status == "ACTIVE" and flag.severity == "critical"
        ]

        results.append(PatientRiskSummary(
            id=patient_id,
            name=stats.name,
            complexity_tier=stats.complexity_tier,
            has_critical_flag=len(active_critical_classes) > 0,
            active_critical_classes=active_critical_classes,
        ))

    return PatientRiskSummaryResponse(patients=results)


@router.get("/{patient_id}/key-labs", response_model=KeyLabsResponse)
def patient_key_labs(patient_id: str, request: Request) -> KeyLabsResponse:
    """
    Return the most recent value + trend for clinically important lab panels.

    Panels covered:
    - Hematology: CBC labs (Hemoglobin, Hematocrit, Platelets, WBC)
    - Metabolic: BMP/CMP (Sodium, Potassium, Creatinine, BUN, Glucose)
    - Coagulation: INR, PT, PTT
    - Cardiac: Troponin, BNP, proBNP
    """
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, _ = result

    # LOINC code → (panel name, display label)
    PANEL_LOINC: dict[str, tuple[str, str]] = {
        # Hematology
        "718-7":   ("Hematology", "Hemoglobin"),
        "20570-8": ("Hematology", "Hematocrit"),
        "777-3":   ("Hematology", "Platelets"),
        "6690-2":  ("Hematology", "WBC"),
        # Metabolic
        "2951-2":  ("Metabolic", "Sodium"),
        "2823-3":  ("Metabolic", "Potassium"),
        "2160-0":  ("Metabolic", "Creatinine"),
        "3094-0":  ("Metabolic", "BUN"),
        "2345-7":  ("Metabolic", "Glucose"),
        # Coagulation
        "34714-6": ("Coagulation", "INR"),
        "5902-2":  ("Coagulation", "PT"),
        "3173-2":  ("Coagulation", "PTT"),
        # Cardiac
        "10839-9": ("Cardiac", "Troponin"),
        "42637-9": ("Cardiac", "BNP"),
        "33762-6": ("Cardiac", "proBNP"),
    }

    # Group observations by LOINC code, keeping only quantity observations
    obs_by_loinc: dict[str, list] = defaultdict(list)
    for obs in record.observations:
        if obs.loinc_code in PANEL_LOINC and obs.value_type == "quantity" and obs.value_quantity is not None:
            obs_by_loinc[obs.loinc_code].append(obs)

    # Build panels dict: panel_name → list[LabValue]
    panels: dict[str, list[LabValue]] = {}

    for loinc_code, (panel_name, default_display) in PANEL_LOINC.items():
        observations = obs_by_loinc.get(loinc_code)
        if not observations:
            continue

        # Sort by effective_dt descending (most recent first); None dates go last
        observations_sorted = sorted(
            observations,
            key=lambda o: o.effective_dt or datetime.min,
            reverse=True,
        )

        most_recent = observations_sorted[0]

        # Compute trend by comparing the two most recent readings
        trend: str | None = None
        if len(observations_sorted) >= 2:
            v0 = most_recent.value_quantity          # most recent
            v1 = observations_sorted[1].value_quantity  # previous
            if v0 is not None and v1 is not None and v1 != 0:
                pct_change = (v0 - v1) / abs(v1)
                if pct_change > 0.05:
                    trend = "up"
                elif pct_change < -0.05:
                    trend = "down"
                else:
                    trend = "stable"

        # Build history: take up to 10 readings, oldest first
        history_obs = observations_sorted[:10]
        history_obs.reverse()  # oldest first for sparkline
        history = []
        for obs in history_obs:
            if obs.value_quantity is None:
                continue
            point_abnormality, point_severity, _low, _high, _unit, _label = _interpret_lab_value(
                loinc_code,
                obs.value_quantity,
                obs.reference_low,
                obs.reference_high,
                obs.reference_unit or obs.value_unit or "",
            )
            history.append(
                LabHistoryPoint(
                    effective_dt=obs.effective_dt,
                    value=obs.value_quantity,
                    abnormality=point_abnormality,  # type: ignore[arg-type]
                    alert_severity=point_severity,  # type: ignore[arg-type]
                )
            )

        abnormality, alert_severity, reference_low, reference_high, reference_unit, reference_label = _interpret_lab_value(
            loinc_code,
            most_recent.value_quantity,
            most_recent.reference_low,
            most_recent.reference_high,
            most_recent.reference_unit or most_recent.value_unit or "",
        )

        lab = LabValue(
            loinc_code=loinc_code,
            display=most_recent.display or default_display,
            value=most_recent.value_quantity,
            unit=most_recent.value_unit or "",
            effective_dt=most_recent.effective_dt,
            trend=trend,
            is_abnormal=abnormality in {"low", "high"} if abnormality != "unknown" else None,
            abnormality=abnormality,  # type: ignore[arg-type]
            alert_severity=alert_severity,  # type: ignore[arg-type]
            reference_low=reference_low,
            reference_high=reference_high,
            reference_unit=reference_unit or most_recent.value_unit or "",
            reference_range_label=reference_label,
            history=history,
        )

        if panel_name not in panels:
            panels[panel_name] = []
        panels[panel_name].append(lab)

    # Compute alert flags for recent labs (last 30 days)
    today = datetime.now().date()
    alert_flags = _compute_alert_flags(record, today)

    # Compute 6-month timeline events
    timeline_events = _compute_timeline_events(record, today)

    return KeyLabsResponse(
        patient_id=requested_patient_id,
        panels=panels,
        alert_flags=alert_flags,
        timeline_events=timeline_events,
    )


@router.get("/{patient_id}/safety", response_model=SafetyResponse)
def patient_safety(patient_id: str, request: Request) -> SafetyResponse:
    """Pre-op safety flags — drug class risk classification."""
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    raw_flags = _classifier.generate_safety_flags(record.medications)

    flags: list[SafetyFlag] = []
    for rf in raw_flags:
        medications = [
            SafetyMedication(
                med_id=cm.medication.med_id,
                display=cm.medication.display,
                status=cm.medication.status,
                authored_on=cm.medication.authored_on,
                is_active=cm.is_active,
            )
            for cm in rf.medications
        ]
        flags.append(SafetyFlag(
            class_key=rf.class_key,
            label=rf.label,
            severity=rf.severity,
            surgical_note=rf.surgical_note,
            status=rf.status,
            medications=medications,
            protocol_note=PROTOCOL_NOTES.get(rf.class_key),
        ))

    active_flag_count = sum(1 for f in flags if f.status == "ACTIVE")
    historical_flag_count = sum(1 for f in flags if f.status == "HISTORICAL")

    return SafetyResponse(
        patient_id=requested_patient_id,
        name=stats.name,
        flags=flags,
        active_flag_count=active_flag_count,
        historical_flag_count=historical_flag_count,
    )


@router.get("/{patient_id}/interactions", response_model=InteractionResponse)
def patient_interactions(patient_id: str, request: Request) -> InteractionResponse:
    """Drug-drug interaction checker — flags known dangerous interactions between active medications."""
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    # Get safety flags to find active classes and their med names
    flags = _classifier.generate_safety_flags(record.medications)
    active_flags = [f for f in flags if f.status == "ACTIVE"]
    active_keys = [f.class_key for f in active_flags]

    # Build label map and med name map from flags
    label_map = {f.class_key: f.label for f in flags}
    med_map = {
        f.class_key: [cm.medication.display for cm in f.medications if cm.is_active]
        for f in active_flags
    }

    interactions = check_interactions(active_keys)

    results = [
        InteractionResult(
            drug_a=i.drug_a,
            drug_a_label=label_map.get(i.drug_a, i.drug_a),
            drug_b=i.drug_b,
            drug_b_label=label_map.get(i.drug_b, i.drug_b),
            severity=i.severity,
            mechanism=i.mechanism,
            clinical_effect=i.clinical_effect,
            management=i.management,
            drug_a_meds=med_map.get(i.drug_a, []),
            drug_b_meds=med_map.get(i.drug_b, []),
        )
        for i in interactions
    ]

    return InteractionResponse(
        patient_id=requested_patient_id,
        active_class_keys=active_keys,
        interactions=results,
        contraindicated_count=sum(1 for r in results if r.severity == "contraindicated"),
        major_count=sum(1 for r in results if r.severity == "major"),
        moderate_count=sum(1 for r in results if r.severity == "moderate"),
        has_interactions=len(results) > 0,
    )


@router.get("/{patient_id}/surgical-risk", response_model=SurgicalRiskResponse)
def patient_surgical_risk(patient_id: str, request: Request) -> SurgicalRiskResponse:
    """
    Deterministic surgical risk score for pre-op clearance review.

    This is intentionally rules-based and transparent. It is not a prediction
    model; it summarizes chart signals that should trigger surgeon/anesthesia
    review before proceeding.
    """
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    raw_flags = _classifier.generate_safety_flags(record.medications)
    active_flags = [f for f in raw_flags if f.status == "ACTIVE"]
    historical_flags = [f for f in raw_flags if f.status == "HISTORICAL"]
    active_critical = [f for f in active_flags if f.severity == "critical"]
    active_warning = [f for f in active_flags if f.severity == "warning"]
    historical_critical = [f for f in historical_flags if f.severity == "critical"]
    historical_warning = [f for f in historical_flags if f.severity == "warning"]

    if active_critical:
        medication_score = 35
    elif active_warning:
        medication_score = 22
    elif historical_critical:
        medication_score = 10
    elif historical_warning:
        medication_score = 5
    else:
        medication_score = 0

    medication_evidence: list[str] = []
    for flag in [*active_critical, *active_warning, *historical_critical, *historical_warning]:
        med_names = [
            cm.medication.display
            for cm in flag.medications
            if cm.is_active or flag.status == "HISTORICAL"
        ]
        suffix = f": {', '.join(med_names[:3])}" if med_names else ""
        medication_evidence.append(f"{flag.status.title()} {flag.label}{suffix}")

    medication_component = SurgicalRiskComponent(
        key="medications",
        label="Medication holds",
        score=medication_score,
        max_score=35,
        status=_component_status(
            medication_score,
            flagged=bool(active_critical),
            review=bool(active_warning or historical_critical or historical_warning),
        ),
        rationale=(
            "Active critical medication classes create a hold-level signal; "
            "active warning classes or relevant historical exposure create review-level signals."
        ),
        evidence=_limit_evidence(medication_evidence),
    )

    ranked_conditions = [r for r in _condition_ranker.rank_all(stats.condition_catalog) if r.is_active]
    high_conditions = [r for r in ranked_conditions if r.risk_category in HIGH_RISK_CONDITION_CATEGORIES]
    moderate_conditions = [r for r in ranked_conditions if r.risk_category in MODERATE_RISK_CONDITION_CATEGORIES]
    review_conditions = [r for r in ranked_conditions if r.risk_category in REVIEW_RISK_CONDITION_CATEGORIES]
    condition_score = min(
        30,
        len(high_conditions) * 12 + len(moderate_conditions) * 8 + len(review_conditions) * 4,
    )
    condition_component = SurgicalRiskComponent(
        key="conditions",
        label="Active condition burden",
        score=condition_score,
        max_score=30,
        status=_component_status(
            condition_score,
            flagged=bool(high_conditions),
            review=bool(moderate_conditions or review_conditions),
        ),
        rationale=(
            "Active cardiac or pulmonary conditions are hold-level; renal, hepatic, "
            "hematologic, vascular, metabolic, neurologic, immunologic, and oncologic "
            "conditions add review weight."
        ),
        evidence=_limit_evidence([
            f"{r.risk_label}: {r.display}"
            for r in [*high_conditions, *moderate_conditions, *review_conditions]
        ]),
    )

    today = datetime.now().date()
    lab_alerts = _compute_alert_flags(record, today)
    critical_labs = [flag for flag in lab_alerts if flag.severity == "critical"]
    warning_labs = [flag for flag in lab_alerts if flag.severity == "warning"]
    has_coagulation_data = any(obs.loinc_code in COAGULATION_LOINC_CODES for obs in record.observations)
    has_active_anticoagulant = any(flag.class_key == "anticoagulants" for flag in active_flags)

    if critical_labs:
        lab_score = 15
    elif warning_labs:
        lab_score = 10
    elif has_active_anticoagulant and not has_coagulation_data:
        lab_score = 8
    else:
        lab_score = 0

    lab_evidence = [flag.message for flag in [*critical_labs, *warning_labs]]
    if has_active_anticoagulant and not has_coagulation_data:
        lab_evidence.append("Active anticoagulant with no INR/PT/PTT observation found in the FHIR bundle")

    lab_component = SurgicalRiskComponent(
        key="labs",
        label="Lab readiness",
        score=lab_score,
        max_score=15,
        status=_component_status(
            lab_score,
            flagged=bool(critical_labs),
            review=bool(warning_labs or (has_active_anticoagulant and not has_coagulation_data)),
        ),
        rationale=(
            "Recent critical lab alerts are hold-level. Warning alerts or missing "
            "coagulation data for an active anticoagulant require review."
        ),
        evidence=_limit_evidence(lab_evidence),
    )

    high_allergies = [
        allergy for allergy in record.allergies if (allergy.criticality or "").lower() == "high"
    ]
    med_allergies = [
        allergy for allergy in record.allergies if "medication" in [c.lower() for c in allergy.categories]
    ]
    if high_allergies and med_allergies:
        allergy_score = 10
    elif high_allergies:
        allergy_score = 6
    elif record.allergies:
        allergy_score = 4
    else:
        allergy_score = 0

    allergy_component = SurgicalRiskComponent(
        key="allergies",
        label="Allergy criticality",
        score=allergy_score,
        max_score=10,
        status=_component_status(
            allergy_score,
            flagged=bool(high_allergies and med_allergies),
            review=bool(record.allergies),
        ),
        rationale=(
            "High-criticality medication allergies are hold-level; other documented "
            "allergies are review-level perioperative context."
        ),
        evidence=_limit_evidence([
            f"{allergy.code.label() or 'Allergy'} ({allergy.criticality or 'unknown criticality'})"
            for allergy in record.allergies
        ]),
    )

    interactions = check_interactions([f.class_key for f in active_flags])
    major_interactions = [
        interaction
        for interaction in interactions
        if interaction.severity in {"contraindicated", "major"}
    ]
    moderate_interactions = [interaction for interaction in interactions if interaction.severity == "moderate"]
    if major_interactions:
        interaction_score = 10
    elif moderate_interactions:
        interaction_score = 6
    else:
        interaction_score = 0

    interaction_component = SurgicalRiskComponent(
        key="interactions",
        label="Drug interaction screen",
        score=interaction_score,
        max_score=10,
        status=_component_status(
            interaction_score,
            flagged=bool(major_interactions),
            review=bool(moderate_interactions),
        ),
        rationale=(
            "Known active drug-class interactions add hold or review weight based "
            "on severity."
        ),
        evidence=_limit_evidence([
            f"{interaction.drug_a} + {interaction.drug_b}: {interaction.clinical_effect}"
            for interaction in [*major_interactions, *moderate_interactions]
        ]),
    )

    components = [
        medication_component,
        condition_component,
        lab_component,
        allergy_component,
        interaction_component,
    ]
    total_score = min(100, sum(component.score for component in components))

    if total_score >= 50:
        tier = "HIGH"
        disposition = "HOLD"
    elif total_score >= 25:
        tier = "MODERATE"
        disposition = "REVIEW"
    else:
        tier = "LOW"
        disposition = "CLEARED"

    return SurgicalRiskResponse(
        patient_id=requested_patient_id,
        name=stats.name,
        score=total_score,
        max_score=100,
        tier=tier,
        disposition=disposition,
        rule_version="preop-rules-v1",
        components=components,
        methodology_notes=[
            "Score is deterministic and derived only from parsed FHIR bundle fields.",
            "Medication holds contribute up to 35 points; active critical classes dominate this component.",
            "Active surgical condition categories contribute up to 30 points using the static condition ranker.",
            "Labs, allergies, and known drug-class interactions add readiness and anesthesia review signals.",
            "This is a briefing and triage aid, not an autonomous clearance decision.",
        ],
    )
