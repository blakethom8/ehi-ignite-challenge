"""
Natural language search — lets clinicians ask questions about a patient
and get evidence-backed answers from the structured FHIR data.

This view provides a keyword/structured search engine over the patient's
clinical data. Queries are matched against medications, conditions,
encounters, procedures, and observations using keyword matching and
drug class awareness.

Note: A future version will integrate LLM-based Q&A (Anthropic Claude)
for true natural language understanding. The current implementation uses
structured keyword search to provide immediate value without API dependency.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import dataclass, field

import streamlit as st

from lib.fhir_parser.models import PatientRecord
from lib.patient_catalog.single_patient import PatientStats

from core.drug_classifier import DrugClassifier, ClassifiedMedication
from core.episode_detector import detect_medication_episodes, detect_condition_episodes


# ---------------------------------------------------------------------------
# Search result types
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result with source and evidence."""
    category: str          # "medication", "condition", "encounter", "procedure", "observation"
    title: str
    detail: str
    date: datetime | None = None
    status: str = ""
    relevance: float = 1.0  # higher = more relevant


# ---------------------------------------------------------------------------
# Search engine
# ---------------------------------------------------------------------------

_CLASSIFIER = DrugClassifier()

# Common clinical question patterns mapped to search categories
_QUESTION_PATTERNS: dict[str, list[str]] = {
    "medication": [
        "blood thinner", "anticoagulant", "opioid", "pain med", "pain medication",
        "ace inhibitor", "arb", "immunosuppressant", "nsaid", "steroid",
        "jak inhibitor", "anticonvulsant", "psych", "antidepressant",
        "stimulant", "diabetes", "insulin", "metformin",
        "taking", "prescribed", "medication", "drug", "med",
    ],
    "condition": [
        "diagnosis", "condition", "disease", "disorder", "syndrome",
        "history of", "diagnosed", "suffer", "chronic",
        "dvt", "diabetes", "hypertension", "cancer", "infection",
    ],
    "encounter": [
        "hospital", "admission", "admitted", "emergency", "er visit",
        "inpatient", "outpatient", "visit", "appointment", "seen",
    ],
    "procedure": [
        "surgery", "surgical", "procedure", "operation", "operated",
        "biopsy", "stent", "replacement", "arthroscopy", "appendectomy",
    ],
    "observation": [
        "lab", "labs", "result", "test", "blood work", "a1c", "inr",
        "hemoglobin", "glucose", "creatinine", "vital", "blood pressure",
    ],
}


def _match_score(query: str, text: str) -> float:
    """Score how well a query matches a text string (0-1)."""
    query_lower = query.lower()
    text_lower = text.lower()

    # Exact substring match
    if query_lower in text_lower:
        return 1.0

    # Word-level matching
    query_words = set(query_lower.split())
    text_words = set(text_lower.split())
    if not query_words:
        return 0.0

    overlap = query_words & text_words
    return len(overlap) / len(query_words)


def _parse_time_filter(query: str) -> tuple[str, datetime | None]:
    """Extract time range from query, return (cleaned query, cutoff date)."""
    now = datetime.now()
    query_lower = query.lower()

    time_phrases = [
        ("last year", timedelta(days=365)),
        ("last 1 year", timedelta(days=365)),
        ("last 2 years", timedelta(days=730)),
        ("last 3 years", timedelta(days=1095)),
        ("last 5 years", timedelta(days=1825)),
        ("last 10 years", timedelta(days=3650)),
        ("last 6 months", timedelta(days=182)),
        ("last 3 months", timedelta(days=91)),
        ("last month", timedelta(days=30)),
        ("past year", timedelta(days=365)),
        ("past 5 years", timedelta(days=1825)),
        ("past 2 years", timedelta(days=730)),
        ("recently", timedelta(days=90)),
        ("current", timedelta(days=0)),  # special: means active now
    ]

    for phrase, delta in time_phrases:
        if phrase in query_lower:
            cleaned = query_lower.replace(phrase, "").strip()
            # Remove trailing question marks and leading "in the" etc.
            for filler in ["in the", "in", "the", "?"]:
                cleaned = cleaned.strip().removeprefix(filler).removesuffix(filler).strip()
            cutoff = now - delta if delta.total_seconds() > 0 else None
            return cleaned, cutoff

    return query, None


def search_patient(
    record: PatientRecord,
    query: str,
) -> list[SearchResult]:
    """Search a patient's record using keyword matching.

    Handles queries like:
    - "blood thinners" → finds anticoagulant medications
    - "surgeries in the last 5 years" → filters procedures by date
    - "diabetes" → finds conditions, medications, and labs
    """
    if not query.strip():
        return []

    cleaned_query, time_cutoff = _parse_time_filter(query)
    results: list[SearchResult] = []

    # Determine which categories to emphasize
    query_lower = cleaned_query.lower()

    # --- Search drug classes first (handles "blood thinners", "opioids", etc.) ---
    for class_key in _CLASSIFIER.class_keys:
        info = _CLASSIFIER.get_class_info(class_key)
        if info is None:
            continue

        # Check if query matches this drug class
        class_terms = [info.label.lower(), class_key.replace("_", " ")]
        class_terms.extend(info.keywords[:5])  # top keywords

        class_match = any(
            term in query_lower or query_lower in term
            for term in class_terms
        )

        if not class_match:
            continue

        # Find all medications in this class
        for med in record.medications:
            classes = _CLASSIFIER.classify_medication(med)
            if class_key in classes:
                if time_cutoff and med.authored_on and med.authored_on < time_cutoff:
                    continue
                results.append(SearchResult(
                    category="medication",
                    title=f"{med.display} ({info.label})",
                    detail=(
                        f"Status: {med.status} · "
                        f"{'Prescribed: ' + med.authored_on.strftime('%b %Y') if med.authored_on else 'Date unknown'}"
                        f"{' · Dose: ' + med.dosage_text if med.dosage_text else ''}"
                        f"{' · Reason: ' + med.reason_display if med.reason_display else ''}"
                    ),
                    date=med.authored_on,
                    status=med.status,
                    relevance=1.0 if med.status == "active" else 0.7,
                ))

    # --- Search medications by name ---
    for med in record.medications:
        score = _match_score(cleaned_query, med.display)
        if score < 0.5:
            # Also check reason
            if med.reason_display:
                score = max(score, _match_score(cleaned_query, med.reason_display) * 0.8)
        if score < 0.5:
            continue
        if time_cutoff and med.authored_on and med.authored_on < time_cutoff:
            continue

        # Avoid duplicates from drug class search
        if any(r.category == "medication" and med.display in r.title for r in results):
            continue

        results.append(SearchResult(
            category="medication",
            title=med.display,
            detail=(
                f"Status: {med.status} · "
                f"{'Prescribed: ' + med.authored_on.strftime('%b %Y') if med.authored_on else 'Date unknown'}"
                f"{' · Dose: ' + med.dosage_text if med.dosage_text else ''}"
            ),
            date=med.authored_on,
            status=med.status,
            relevance=score,
        ))

    # --- Search conditions ---
    for cond in record.conditions:
        text = f"{cond.code.display} {cond.code.text}"
        score = _match_score(cleaned_query, text)
        if score < 0.4:
            continue
        if time_cutoff and cond.onset_dt and cond.onset_dt < time_cutoff:
            continue

        results.append(SearchResult(
            category="condition",
            title=cond.code.label(),
            detail=(
                f"Status: {cond.clinical_status} · "
                f"{'Onset: ' + cond.onset_dt.strftime('%b %Y') if cond.onset_dt else 'Onset unknown'}"
                f"{' · Resolved: ' + cond.abatement_dt.strftime('%b %Y') if cond.abatement_dt else ''}"
            ),
            date=cond.onset_dt,
            status=cond.clinical_status,
            relevance=score * (1.2 if cond.is_active else 0.8),
        ))

    # --- Search encounters ---
    for enc in record.encounters:
        text = f"{enc.encounter_type} {enc.reason_display} {enc.class_code}"
        score = _match_score(cleaned_query, text)

        # Boost hospital/ER matches
        if any(term in query_lower for term in ["hospital", "admission", "inpatient"]):
            if enc.class_code == "IMP":
                score = max(score, 0.8)
        if any(term in query_lower for term in ["emergency", "er visit", "er"]):
            if enc.class_code == "EMER":
                score = max(score, 0.8)

        if score < 0.4:
            continue

        enc_date = enc.period.start
        if time_cutoff and enc_date and enc_date < time_cutoff:
            continue

        results.append(SearchResult(
            category="encounter",
            title=f"{enc.encounter_type or enc.class_code} — {enc.reason_display or 'No reason listed'}",
            detail=(
                f"Class: {enc.class_code} · "
                f"{'Date: ' + enc_date.strftime('%b %d, %Y') if enc_date else 'Date unknown'}"
                f"{' · Provider: ' + enc.provider_org if enc.provider_org else ''}"
            ),
            date=enc_date,
            status=enc.status,
            relevance=score,
        ))

    # --- Search procedures ---
    for proc in record.procedures:
        text = f"{proc.code.display} {proc.code.text} {proc.reason_display}"
        score = _match_score(cleaned_query, text)

        # Boost if query mentions surgery/procedure generically — show all procedures
        if any(term in query_lower for term in [
            "surgery", "surgeries", "procedure", "procedures", "operation", "operations",
        ]):
            score = max(score, 0.7)

        if score < 0.3:
            continue

        proc_date = proc.performed_period.start if proc.performed_period else None
        if time_cutoff and proc_date and proc_date < time_cutoff:
            continue

        results.append(SearchResult(
            category="procedure",
            title=proc.code.label(),
            detail=(
                f"Status: {proc.status} · "
                f"{'Date: ' + proc_date.strftime('%b %d, %Y') if proc_date else 'Date unknown'}"
                f"{' · Reason: ' + proc.reason_display if proc.reason_display else ''}"
            ),
            date=proc_date,
            status=proc.status,
            relevance=score,
        ))

    # --- Search observations/labs ---
    for obs in record.observations:
        text = f"{obs.display} {obs.category}"
        score = _match_score(cleaned_query, text)

        if any(term in query_lower for term in ["lab", "labs", "test", "result", "blood work"]):
            if obs.category in ("laboratory", "vital-signs"):
                score = max(score, 0.3)
                score = max(score, _match_score(
                    cleaned_query.replace("lab", "").replace("labs", "").replace("test", "").strip() or cleaned_query,
                    obs.display,
                ))

        if score < 0.4:
            continue

        if time_cutoff and obs.effective_dt and obs.effective_dt < time_cutoff:
            continue

        # Format value
        value_str = ""
        if obs.value_type == "quantity" and obs.value_quantity is not None:
            value_str = f"{obs.value_quantity} {obs.value_unit}"
        elif obs.value_concept_display:
            value_str = obs.value_concept_display

        results.append(SearchResult(
            category="observation",
            title=obs.display,
            detail=(
                f"Category: {obs.category} · "
                f"{'Value: ' + value_str + ' · ' if value_str else ''}"
                f"{'Date: ' + obs.effective_dt.strftime('%b %d, %Y') if obs.effective_dt else 'Date unknown'}"
            ),
            date=obs.effective_dt,
            status=obs.status,
            relevance=score,
        ))

    # Sort by relevance (highest first), then by date (most recent first)
    results.sort(key=lambda r: (-r.relevance, -(r.date or datetime.min).timestamp()))

    return results


# ---------------------------------------------------------------------------
# Streamlit view
# ---------------------------------------------------------------------------

_CATEGORY_ICONS = {
    "medication": "\U0001f48a",
    "condition": "\U0001f3e5",
    "encounter": "\U0001f4c5",
    "procedure": "\U0001f52a",
    "observation": "\U0001f9ea",
}

_STATUS_COLORS = {
    "active": "red",
    "on-hold": "orange",
    "stopped": "gray",
    "completed": "green",
    "resolved": "green",
    "inactive": "gray",
}

_EXAMPLE_QUERIES = [
    "blood thinners",
    "opioid history",
    "surgeries in the last 5 years",
    "diabetes",
    "hospitalizations",
    "immunosuppressants",
    "labs last year",
    "ACE inhibitors",
]


def render(record: PatientRecord, stats: PatientStats) -> None:
    """Render the natural language search view."""
    st.header("Clinical Search")
    st.caption(
        "Search this patient's record by medication, condition, procedure, "
        "encounter, or lab result. Understands drug classes and time ranges."
    )

    # Search input
    query = st.text_input(
        "Ask a question about this patient",
        placeholder='e.g., "Has this patient been on blood thinners in the last 5 years?"',
        key="nl_search_query",
    )

    # Example queries as quick buttons
    st.markdown("**Quick searches:**")
    cols = st.columns(4)
    for i, example in enumerate(_EXAMPLE_QUERIES):
        if cols[i % 4].button(example, key=f"example_{i}", use_container_width=True):
            query = example

    if not query:
        # Show data summary when no query
        st.markdown("---")
        st.subheader("Patient Data Summary")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Medications", len(record.medications))
        c2.metric("Conditions", len(record.conditions))
        c3.metric("Encounters", len(record.encounters))
        c4.metric("Procedures", len(record.procedures))
        c5.metric("Observations", len(record.observations))
        return

    # Run search
    st.markdown("---")
    results = search_patient(record, query)

    if not results:
        st.warning(f"No results found for \"{query}\". Try a different search term.")
        return

    # Summary
    categories = {}
    for r in results:
        categories[r.category] = categories.get(r.category, 0) + 1

    summary_parts = [f"**{len(results)} results found**"]
    for cat, count in sorted(categories.items()):
        icon = _CATEGORY_ICONS.get(cat, "")
        summary_parts.append(f"{icon} {count} {cat}{'s' if count != 1 else ''}")

    st.markdown(" · ".join(summary_parts))

    # Category filter
    all_cats = sorted(categories.keys())
    if len(all_cats) > 1:
        selected_cats = st.multiselect(
            "Filter by category",
            options=all_cats,
            default=all_cats,
            format_func=lambda c: f"{_CATEGORY_ICONS.get(c, '')} {c.title()}",
        )
    else:
        selected_cats = all_cats

    # Display results
    displayed = 0
    max_results = 50

    for result in results:
        if result.category not in selected_cats:
            continue
        if displayed >= max_results:
            st.info(f"Showing first {max_results} results. Refine your search for more specific results.")
            break

        icon = _CATEGORY_ICONS.get(result.category, "")
        status_color = _STATUS_COLORS.get(result.status, "gray")

        with st.container():
            col_icon, col_content = st.columns([0.05, 0.95])
            with col_icon:
                st.markdown(f"### {icon}")
            with col_content:
                status_badge = f":{status_color}[{result.status}]" if result.status else ""
                st.markdown(f"**{result.title}** {status_badge}")
                st.caption(result.detail)

        displayed += 1
