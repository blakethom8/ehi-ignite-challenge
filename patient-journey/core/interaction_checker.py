"""
Drug interaction checker — identifies potential drug-drug interactions
among a patient's active medications.

Uses a curated interaction matrix of clinically significant interactions
relevant to surgical/pre-op settings. This is a rule-based approach
(no external API dependency) suitable for the contest prototype.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fhir_explorer.parser.models import MedicationRecord

from core.drug_classifier import DrugClassifier


# ---------------------------------------------------------------------------
# Interaction definitions
# ---------------------------------------------------------------------------

# Each tuple: (class_a, class_b, severity, description)
# severity: "critical" | "warning" | "info"
_INTERACTION_RULES: list[tuple[str, str, str, str]] = [
    (
        "anticoagulants", "antiplatelets", "critical",
        "Concurrent use significantly increases bleeding risk. "
        "Consider holding one agent pre-operatively.",
    ),
    (
        "anticoagulants", "nsaids", "critical",
        "NSAIDs potentiate anticoagulant effect and increase GI bleeding risk. "
        "Avoid concurrent use peri-operatively.",
    ),
    (
        "antiplatelets", "nsaids", "warning",
        "Combined antiplatelet and NSAID use increases bleeding risk. "
        "Review necessity of both agents.",
    ),
    (
        "ace_inhibitors", "arbs", "warning",
        "Dual RAAS blockade increases risk of hypotension, hyperkalemia, "
        "and renal impairment. Rarely indicated together.",
    ),
    (
        "ace_inhibitors", "immunosuppressants", "info",
        "ACE inhibitors may potentiate hyperkalemia risk with "
        "calcineurin inhibitors (tacrolimus, cyclosporine).",
    ),
    (
        "opioids", "psych_medications", "warning",
        "Opioids combined with sedating psych medications (SSRIs, SNRIs, "
        "TCAs) increase CNS depression and serotonin syndrome risk.",
    ),
    (
        "opioids", "anticonvulsants", "info",
        "Some anticonvulsants (carbamazepine, phenytoin) induce CYP3A4, "
        "potentially reducing opioid efficacy.",
    ),
    (
        "anticoagulants", "immunosuppressants", "warning",
        "Methotrexate and other immunosuppressants may increase "
        "bleeding risk when combined with anticoagulants.",
    ),
    (
        "nsaids", "immunosuppressants", "warning",
        "NSAIDs reduce renal blood flow and may increase toxicity of "
        "renally-cleared immunosuppressants (methotrexate, cyclosporine).",
    ),
    (
        "stimulants", "psych_medications", "info",
        "Monitor for cardiovascular effects and serotonin syndrome "
        "when combining stimulants with serotonergic medications.",
    ),
    (
        "anticoagulants", "anticonvulsants", "warning",
        "Enzyme-inducing anticonvulsants (phenytoin, carbamazepine) may "
        "reduce warfarin efficacy. Monitor INR closely.",
    ),
    (
        "diabetes_medications", "ace_inhibitors", "info",
        "ACE inhibitors may enhance hypoglycemic effect. "
        "Monitor blood glucose more frequently peri-operatively.",
    ),
    (
        "jak_inhibitors", "immunosuppressants", "critical",
        "Combined immunosuppression markedly increases infection risk. "
        "High concern for post-surgical wound healing and sepsis.",
    ),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DrugInteraction:
    """A detected drug-drug interaction between two medication classes."""
    class_a: str
    class_b: str
    label_a: str
    label_b: str
    severity: str          # "critical" | "warning" | "info"
    description: str
    medications_a: list[MedicationRecord] = field(default_factory=list)
    medications_b: list[MedicationRecord] = field(default_factory=list)


@dataclass
class InteractionReport:
    """Summary of all detected interactions for a patient."""
    interactions: list[DrugInteraction] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    @property
    def total_count(self) -> int:
        return len(self.interactions)

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

def check_interactions(
    medications: list[MedicationRecord],
    classifier: DrugClassifier | None = None,
    active_only: bool = True,
) -> InteractionReport:
    """Check for drug-drug interactions among a patient's medications.

    Args:
        medications: Full medication list from PatientRecord.
        classifier: DrugClassifier instance (created if not provided).
        active_only: If True, only consider active/on-hold medications.

    Returns:
        InteractionReport with all detected interactions.
    """
    if classifier is None:
        classifier = DrugClassifier()

    # Filter to active if requested
    meds = medications
    if active_only:
        meds = [m for m in medications if m.status in ("active", "on-hold")]

    # Build class -> medications mapping
    class_meds: dict[str, list[MedicationRecord]] = {}
    for med in meds:
        classes = classifier.classify_medication(med)
        for cls_key in classes:
            class_meds.setdefault(cls_key, []).append(med)

    # Check each interaction rule
    interactions: list[DrugInteraction] = []
    critical = warning = info = 0

    for class_a, class_b, severity, description in _INTERACTION_RULES:
        meds_a = class_meds.get(class_a, [])
        meds_b = class_meds.get(class_b, [])

        if meds_a and meds_b:
            info_a = classifier.get_class_info(class_a)
            info_b = classifier.get_class_info(class_b)

            interactions.append(DrugInteraction(
                class_a=class_a,
                class_b=class_b,
                label_a=info_a.label if info_a else class_a,
                label_b=info_b.label if info_b else class_b,
                severity=severity,
                description=description,
                medications_a=meds_a,
                medications_b=meds_b,
            ))

            if severity == "critical":
                critical += 1
            elif severity == "warning":
                warning += 1
            else:
                info += 1

    # Sort: critical first
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    interactions.sort(key=lambda i: severity_order.get(i.severity, 9))

    return InteractionReport(
        interactions=interactions,
        critical_count=critical,
        warning_count=warning,
        info_count=info,
    )
