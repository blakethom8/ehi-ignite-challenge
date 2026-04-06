"""
Provider-facing chart assistant logic.

Design goals:
- Fast, deterministic chart-grounded answers.
- Direct and concise style.
- Opinionated recommendations with explicit pushback when evidence is weak.
- Evidence citations for every answer.
"""

from __future__ import annotations

import re
import sys as _sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from api.core.condition_ranker import ConditionRanker
from api.core.interaction_checker import check_interactions
from api.core.loader import load_patient


_PATIENT_JOURNEY = Path(__file__).parent.parent.parent / "patient-journey"
if str(_PATIENT_JOURNEY) not in _sys.path:
    _sys.path.insert(0, str(_PATIENT_JOURNEY))
from core.drug_classifier import DrugClassifier  # noqa: E402

_DRUG_MAPPING = _PATIENT_JOURNEY / "data" / "drug_classes.json"
_CLASSIFIER = DrugClassifier(mapping_path=_DRUG_MAPPING)
_CONDITION_RANKER = ConditionRanker()


_STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "what", "when", "where",
    "which", "about", "into", "been", "were", "your", "their", "they", "patient", "chart", "history",
    "please", "would", "could", "should", "can", "show", "tell", "give", "need", "help", "there", "than",
    "then", "also", "just", "over", "under", "more", "less", "most", "very", "any", "all",
}

_INTENT_EXPANSIONS: dict[str, set[str]] = {
    "anticoagulant": {"blood", "thinner", "warfarin", "eliquis", "xarelto", "heparin", "apixaban"},
    "blood": {"anticoagulant", "antiplatelet", "bleeding", "inr"},
    "thinner": {"anticoagulant", "antiplatelet", "bleeding"},
    "surgery": {"preop", "pre-op", "anesthesia", "bleeding", "hold", "interaction"},
    "preop": {"surgery", "anesthesia", "clearance"},
    "anesthesia": {"surgery", "opioid", "ace", "arb", "bleeding"},
    "opioid": {"oxycodone", "hydrocodone", "fentanyl", "pain"},
    "allergy": {"allergies", "criticality", "reaction"},
    "interaction": {"interactions", "contraindicated", "major", "moderate"},
    "last": {"recent", "latest", "encounter", "visit"},
    "visit": {"encounter", "timeline", "date"},
    "condition": {"diagnosis", "diagnoses", "problem"},
    "medication": {"med", "drug", "prescription", "active", "stopped"},
}


@dataclass
class AssistantCitationPayload:
    source_type: str
    resource_id: str
    label: str
    detail: str
    event_date: datetime | None


@dataclass
class _Fact:
    text: str
    citation: AssistantCitationPayload
    keywords: set[str]
    tags: set[str]
    priority: int


@dataclass
class AssistantResult:
    answer: str
    confidence: str
    citations: list[AssistantCitationPayload]
    follow_ups: list[str]


def _tokenize(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9-]+", text.lower())
    return {token for token in raw if len(token) > 2 and token not in _STOP_WORDS}


def _expand_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        expanded.update(_INTENT_EXPANSIONS.get(token, set()))
    return expanded


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "unknown date"
    return dt.strftime("%b %d, %Y")


def _detect_intent(query_tokens: set[str]) -> str:
    if {"anticoagulant", "antiplatelet", "blood", "thinner", "warfarin", "eliquis", "xarelto"} & query_tokens:
        return "anticoag"
    if {"opioid", "oxycodone", "hydrocodone", "fentanyl", "pain"} & query_tokens:
        return "opioid"
    if {"surgery", "preop", "pre-op", "anesthesia", "clearance", "safe"} & query_tokens:
        return "preop_safety"
    if {"interaction", "contraindicated", "major", "moderate"} & query_tokens:
        return "interactions"
    if {"allergy", "allergies", "criticality", "reaction"} & query_tokens:
        return "allergy"
    if {"last", "latest", "recent", "visit", "encounter"} & query_tokens:
        return "recent_encounter"
    return "general"


def _history_context(history: list[dict[str, str]] | None) -> str:
    if not history:
        return ""
    recent_user_turns = [turn.get("content", "") for turn in history if turn.get("role") == "user"][-3:]
    return " ".join(recent_user_turns)


def _build_facts(patient_id: str) -> tuple[list[_Fact], dict]:
    loaded = load_patient(patient_id)
    if loaded is None:
        raise ValueError(f"Patient not found: {patient_id}")

    record, stats = loaded

    facts: list[_Fact] = []

    # Safety and interactions
    raw_flags = _CLASSIFIER.generate_safety_flags(record.medications)
    active_flags = [flag for flag in raw_flags if flag.status == "ACTIVE"]
    historical_flags = [flag for flag in raw_flags if flag.status == "HISTORICAL"]

    for flag in active_flags:
        med_names = [cm.medication.display for cm in flag.medications if cm.is_active]
        detail = f"{flag.label} ({flag.severity}) active; meds: {', '.join(med_names[:4]) or 'none listed'}"
        facts.append(_Fact(
            text=detail,
            citation=AssistantCitationPayload(
                source_type="SafetyFlag",
                resource_id=f"safety:{flag.class_key}",
                label=flag.label,
                detail=flag.surgical_note,
                event_date=None,
            ),
            keywords=_expand_tokens(_tokenize(f"{flag.class_key} {flag.label} {detail} {flag.surgical_note}")),
            tags={"safety", "preop", flag.class_key, flag.severity},
            priority=16,
        ))

    active_keys = [flag.class_key for flag in active_flags]
    interactions = check_interactions(active_keys)
    for item in interactions:
        interaction_text = (
            f"{item.severity.upper()} interaction: {item.drug_a} + {item.drug_b}. "
            f"Effect: {item.clinical_effect}"
        )
        facts.append(_Fact(
            text=interaction_text,
            citation=AssistantCitationPayload(
                source_type="Interaction",
                resource_id=f"interaction:{item.drug_a}:{item.drug_b}",
                label=f"{item.drug_a} + {item.drug_b}",
                detail=item.management,
                event_date=None,
            ),
            keywords=_expand_tokens(_tokenize(f"{item.drug_a} {item.drug_b} {item.severity} {item.mechanism} {item.clinical_effect}")),
            tags={"interaction", item.severity, "safety", "preop"},
            priority=15,
        ))

    # Medication facts
    meds_sorted = sorted(record.medications, key=lambda med: med.authored_on or datetime.min, reverse=True)
    med_class_map = {
        cm.medication.med_id: cm.matched_classes
        for cm in _CLASSIFIER.classify_all(record.medications)
    }
    for med in meds_sorted[:60]:
        classes = med_class_map.get(med.med_id, [])
        classes_text = f" class={', '.join(classes)}" if classes else ""
        detail = f"{med.display} [{med.status}] authored {_fmt_dt(med.authored_on)}{classes_text}"
        priority = 9 if med.status in {"active", "on-hold"} else 5
        facts.append(_Fact(
            text=detail,
            citation=AssistantCitationPayload(
                source_type="MedicationRequest",
                resource_id=med.med_id,
                label=med.display,
                detail=f"status={med.status}; reason={med.reason_display or 'none'}",
                event_date=med.authored_on,
            ),
            keywords=_expand_tokens(_tokenize(f"{med.display} {med.status} {med.reason_display} {' '.join(classes)}")),
            tags={"medication", "active" if med.status in {"active", "on-hold"} else "historical", *classes},
            priority=priority,
        ))

    # Condition facts
    ranked_conditions = _CONDITION_RANKER.rank_all(stats.condition_catalog)
    active_high_risk_conditions = [cond for cond in ranked_conditions if cond.is_active and cond.risk_rank <= 3]

    for cond in ranked_conditions[:40]:
        onset_dt = None
        if cond.onset_dt:
            try:
                onset_dt = datetime.fromisoformat(cond.onset_dt)
            except ValueError:
                onset_dt = None

        detail = (
            f"{cond.display} [{cond.clinical_status}] category={cond.risk_label} "
            f"onset={cond.onset_dt or 'unknown'}"
        )
        priority = 10 if cond.is_active else 5
        facts.append(_Fact(
            text=detail,
            citation=AssistantCitationPayload(
                source_type="Condition",
                resource_id=cond.condition_id,
                label=cond.display,
                detail=f"status={cond.clinical_status}; risk={cond.risk_label}",
                event_date=onset_dt,
            ),
            keywords=_expand_tokens(_tokenize(f"{cond.display} {cond.clinical_status} {cond.risk_category} {cond.risk_label}")),
            tags={"condition", cond.risk_category.lower(), "active" if cond.is_active else "historical"},
            priority=priority,
        ))

    # Allergy facts
    for allergy in record.allergies[:30]:
        allergy_label = allergy.code.label()
        recorded = allergy.recorded_date or allergy.onset_dt
        detail = (
            f"Allergy: {allergy_label}; criticality={allergy.criticality or 'unknown'}; "
            f"category={', '.join(allergy.categories) if allergy.categories else 'unspecified'}"
        )
        priority = 12 if (allergy.criticality or "").lower() == "high" else 8
        facts.append(_Fact(
            text=detail,
            citation=AssistantCitationPayload(
                source_type="AllergyIntolerance",
                resource_id=allergy.allergy_id,
                label=allergy_label,
                detail=f"criticality={allergy.criticality or 'unknown'}",
                event_date=recorded,
            ),
            keywords=_expand_tokens(_tokenize(f"{allergy_label} {allergy.criticality} {' '.join(allergy.categories)}")),
            tags={"allergy", (allergy.criticality or "unknown").lower()},
            priority=priority,
        ))

    # Encounter facts
    encounters = sorted(record.encounters, key=lambda enc: enc.period.start or datetime.min, reverse=True)
    for encounter in encounters[:30]:
        detail = (
            f"Encounter {encounter.class_code or 'UNK'} {encounter.encounter_type or 'unknown type'} "
            f"on {_fmt_dt(encounter.period.start)}"
        )
        facts.append(_Fact(
            text=detail,
            citation=AssistantCitationPayload(
                source_type="Encounter",
                resource_id=encounter.encounter_id,
                label=encounter.encounter_type or "Encounter",
                detail=f"class={encounter.class_code}; reason={encounter.reason_display or 'none'}",
                event_date=encounter.period.start,
            ),
            keywords=_expand_tokens(_tokenize(f"{encounter.class_code} {encounter.encounter_type} {encounter.reason_display}")),
            tags={"encounter", "timeline", "recent"},
            priority=8,
        ))

    summary = {
        "patient_name": stats.name,
        "active_flags": active_flags,
        "historical_flags": historical_flags,
        "interactions": interactions,
        "encounters": encounters,
        "allergies": record.allergies,
        "active_high_risk_condition_count": len(active_high_risk_conditions),
        "parse_warning_count": stats.parse_warning_count,
    }

    return facts, summary


def _score_fact(fact: _Fact, query_tokens: set[str], intent: str) -> int:
    overlap = len(fact.keywords & query_tokens)
    score = fact.priority + overlap * 4

    if intent == "preop_safety" and ("safety" in fact.tags or "interaction" in fact.tags):
        score += 8
    if intent == "anticoag" and ({"anticoagulants", "antiplatelets"} & fact.tags):
        score += 8
    if intent == "opioid" and "opioids" in fact.tags:
        score += 8
    if intent == "interactions" and "interaction" in fact.tags:
        score += 8
    if intent == "allergy" and "allergy" in fact.tags:
        score += 8
    if intent == "recent_encounter" and "encounter" in fact.tags:
        score += 8

    return score


def _collect_citations(facts: list[_Fact], max_items: int = 6) -> list[AssistantCitationPayload]:
    seen: set[tuple[str, str]] = set()
    citations: list[AssistantCitationPayload] = []
    for fact in facts:
        key = (fact.citation.source_type, fact.citation.resource_id)
        if key in seen:
            continue
        citations.append(fact.citation)
        seen.add(key)
        if len(citations) >= max_items:
            break
    return citations


def _direct_answer(intent: str, summary: dict, question: str) -> tuple[str, str, str | None]:
    active_flags = summary["active_flags"]
    interactions = summary["interactions"]
    allergies = summary["allergies"]
    encounters = summary["encounters"]

    if intent == "anticoag":
        active = [f for f in active_flags if f.class_key in {"anticoagulants", "antiplatelets"}]
        if active:
            meds = []
            for flag in active:
                meds.extend(cm.medication.display for cm in flag.medications if cm.is_active)
            msg = "Short answer: Yes. Active blood-thinner risk is present."
            rec = (
                "Recommendation: do not proceed until a documented hold/bridge plan is in place for these meds: "
                f"{', '.join(meds[:4]) or 'see citations'}."
            )
            return msg, "high", rec
        hist = [f for f in summary["historical_flags"] if f.class_key in {"anticoagulants", "antiplatelets"}]
        if hist:
            return (
                "Short answer: No active blood thinner found, but there is historical exposure.",
                "medium",
                "Recommendation: verify stop dates and indication before final clearance.",
            )
        return (
            "Short answer: No anticoagulant or antiplatelet class was detected in current active medications.",
            "medium",
            "Recommendation: still verify outside-medication bleeding risks (coag labs, procedures, history).",
        )

    if intent == "opioid":
        active = [f for f in active_flags if f.class_key == "opioids"]
        if active:
            return (
                "Short answer: Yes. Active opioid exposure is present.",
                "high",
                "Recommendation: flag anesthesia and pain teams now; assume higher peri-op analgesic requirements.",
            )
        hist = [f for f in summary["historical_flags"] if f.class_key == "opioids"]
        if hist:
            return (
                "Short answer: No active opioid class found, but historical opioid exposure exists.",
                "medium",
                "Recommendation: confirm timing, duration, and any tolerance or dependence risk before surgery.",
            )
        return (
            "Short answer: No opioid class was detected in this chart snapshot.",
            "medium",
            None,
        )

    if intent == "interactions":
        if interactions:
            top = interactions[0]
            if top.severity == "contraindicated":
                rec = "Recommendation: stop and resolve contraindicated combinations before proceeding."
            elif top.severity == "major":
                rec = "Recommendation: treat as high priority; adjust regimen or monitoring before surgery."
            else:
                rec = "Recommendation: proceed only with explicit mitigation documented."
            return (
                f"Short answer: Interaction risk is present ({len(interactions)} class-level interaction(s)).",
                "high",
                rec,
            )
        return (
            "Short answer: No known class-level interaction was detected among active medication classes.",
            "medium",
            "Recommendation: this does not exclude molecule-level interactions outside the current rule set.",
        )

    if intent == "allergy":
        if not allergies:
            return ("Short answer: No allergy records were found.", "medium", None)
        high = [a for a in allergies if (a.criticality or "").lower() == "high"]
        if high:
            return (
                f"Short answer: Yes. High-criticality allergies are present ({len(high)}).",
                "high",
                "Recommendation: hard-stop for reconciliation; verify allergens and peri-op alternatives.",
            )
        return (
            f"Short answer: Allergy history exists ({len(allergies)} records), without high-criticality flags.",
            "medium",
            "Recommendation: still verify reaction context before medication/procedure orders.",
        )

    if intent == "recent_encounter":
        if not encounters:
            return ("Short answer: No encounters found in this chart.", "low", "Recommendation: verify data ingestion completeness.")
        latest = encounters[0]
        return (
            f"Short answer: Latest encounter was {latest.encounter_type or 'Encounter'} on {_fmt_dt(latest.period.start)}.",
            "high",
            None,
        )

    if intent == "preop_safety":
        critical_active = [f for f in active_flags if f.severity == "critical"]
        major_or_contra = [i for i in interactions if i.severity in {"major", "contraindicated"}]
        high_allergy = [a for a in allergies if (a.criticality or "").lower() == "high"]
        high_risk_condition_count = summary.get("active_high_risk_condition_count", 0)

        if critical_active or major_or_contra or high_allergy:
            return (
                "Short answer: No — do not clear yet based on current chart risk signals.",
                "high",
                "Recommendation: resolve active critical medication risk, major interactions, and allergy constraints before clearance.",
            )

        if active_flags or high_risk_condition_count >= 2:
            return (
                "Short answer: No hard stop detected, but active risk burden still requires targeted review.",
                "medium",
                "Recommendation: proceed only after documenting hold/continue decisions and confirming active high-risk conditions are optimized.",
            )

        return (
            "Short answer: No obvious blocker from current safety flags and interactions.",
            "medium",
            "Recommendation: confirm labs, procedure context, and non-medication risk factors before final clearance.",
        )

    # General mode
    if "safe" in question.lower() and "surgery" in question.lower():
        return (
            "Short answer: I cannot give final surgical clearance from one question alone.",
            "low",
            "Recommendation: ask for explicit bleeding, interaction, allergy, and recent-encounter risk checks.",
        )

    return (
        "Short answer: Here is the most relevant chart evidence for your question.",
        "medium",
        None,
    )


def _follow_ups(intent: str) -> list[str]:
    if intent == "anticoag":
        return [
            "What is the documented indication and stop/bridge plan?",
            "Any recent INR or bleeding-related labs that change risk?",
            "Do recent procedures or active conditions increase bleeding risk further?",
        ]
    if intent == "interactions":
        return [
            "Which specific medications are driving each interaction class?",
            "What mitigation is documented (hold, swap, monitor)?",
            "Any contraindicated pair that requires immediate escalation?",
        ]
    if intent == "preop_safety":
        return [
            "What are the top 3 blockers to clearance right now?",
            "Which risks are active vs historical?",
            "What concrete actions should happen before surgery date?",
        ]
    if intent == "allergy":
        return [
            "Which high-criticality allergens directly affect peri-op orders?",
            "Are allergen details complete or missing reaction context?",
            "What safe alternatives are documented?",
        ]
    return [
        "What is the strongest evidence for that conclusion?",
        "Where should we push back due to missing or sparse chart data?",
        "What is the next concrete clinical action from this evidence?",
    ]


def answer_provider_question(
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None = None,
    stance: str = "opinionated",
) -> AssistantResult:
    facts, summary = _build_facts(patient_id)

    query = f"{question} {_history_context(history)}".strip()
    tokens = _expand_tokens(_tokenize(query))
    intent = _detect_intent(tokens)

    scored = sorted(
        ((fact, _score_fact(fact, tokens, intent)) for fact in facts),
        key=lambda item: item[1],
        reverse=True,
    )

    # Keep only meaningfully relevant facts; always allow some fallback context.
    top_facts = [fact for fact, score in scored if score >= 10][:8]
    if not top_facts:
        top_facts = [fact for fact, _score in scored[:5]]

    short_answer, confidence, recommendation = _direct_answer(intent, summary, question)

    evidence_lines: list[str] = []
    for fact in top_facts[:4]:
        evidence_lines.append(f"- {fact.text}")

    answer_parts = [short_answer]
    if evidence_lines:
        answer_parts.append("Evidence:")
        answer_parts.extend(evidence_lines)

    if summary["parse_warning_count"] > 0:
        answer_parts.append(
            f"Pushback: parser reported {summary['parse_warning_count']} warning(s); avoid over-confident conclusions without verification."
        )

    if confidence == "low" and not recommendation:
        recommendation = "Recommendation: I need a narrower question or additional chart context to give a defensible answer."

    if recommendation:
        if stance == "balanced":
            recommendation = recommendation.replace("Recommendation:", "Suggested next step:")
        answer_parts.append(recommendation)

    citations = _collect_citations(top_facts, max_items=6)

    return AssistantResult(
        answer="\n".join(answer_parts),
        confidence=confidence,
        citations=citations,
        follow_ups=_follow_ups(intent),
    )
