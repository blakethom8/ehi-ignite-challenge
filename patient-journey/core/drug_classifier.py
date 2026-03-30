"""
Drug classifier — maps medication names and RxNorm codes to drug classes
and surgical risk flags.

Uses a static JSON mapping (data/drug_classes.json) for keyword and
RxNorm-based classification. Designed for the pre-op surgical safety panel.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from fhir_explorer.parser.models import MedicationRecord


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DrugClassInfo:
    """Metadata for a drug class category."""
    class_key: str = ""
    label: str = ""
    severity: str = ""          # "critical" | "warning" | "info"
    surgical_note: str = ""
    keywords: list[str] = field(default_factory=list)
    rxnorm_codes: list[str] = field(default_factory=list)


@dataclass
class ClassifiedMedication:
    """A medication matched to one or more drug classes."""
    medication: MedicationRecord
    matched_classes: list[str] = field(default_factory=list)
    # Whether this med is currently active vs historical
    is_active: bool = False


@dataclass
class SafetyFlag:
    """A pre-op safety flag for a drug class."""
    class_key: str
    label: str
    severity: str
    surgical_note: str
    status: str                  # "ACTIVE" | "HISTORICAL" | "NONE"
    medications: list[ClassifiedMedication] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class DrugClassifier:
    """Classifies medications into surgical-risk drug classes."""

    def __init__(self, mapping_path: Path | None = None) -> None:
        if mapping_path is None:
            mapping_path = Path(__file__).parent.parent / "data" / "drug_classes.json"
        self._classes: dict[str, DrugClassInfo] = {}
        self._load_mapping(mapping_path)

    def _load_mapping(self, path: Path) -> None:
        with open(path) as f:
            raw = json.load(f)
        for key, data in raw.items():
            self._classes[key] = DrugClassInfo(
                class_key=key,
                label=data["label"],
                severity=data["severity"],
                surgical_note=data["surgical_note"],
                keywords=[kw.lower() for kw in data["keywords"]],
                rxnorm_codes=data.get("rxnorm_codes", []),
            )

    @property
    def class_keys(self) -> list[str]:
        return list(self._classes.keys())

    def get_class_info(self, class_key: str) -> DrugClassInfo | None:
        return self._classes.get(class_key)

    def classify_medication(self, med: MedicationRecord) -> list[str]:
        """Return list of drug class keys that this medication matches."""
        matched: list[str] = []
        display_lower = med.display.lower()

        for key, info in self._classes.items():
            # Check RxNorm code match
            if med.rxnorm_code and med.rxnorm_code in info.rxnorm_codes:
                matched.append(key)
                continue

            # Check keyword match against display name
            for keyword in info.keywords:
                if keyword in display_lower:
                    matched.append(key)
                    break

        return matched

    def classify_all(
        self, medications: list[MedicationRecord]
    ) -> list[ClassifiedMedication]:
        """Classify a full medication list. Returns only medications that
        match at least one drug class."""
        results: list[ClassifiedMedication] = []
        for med in medications:
            classes = self.classify_medication(med)
            if classes:
                is_active = med.status in ("active", "on-hold")
                results.append(ClassifiedMedication(
                    medication=med,
                    matched_classes=classes,
                    is_active=is_active,
                ))
        return results

    def generate_safety_flags(
        self, medications: list[MedicationRecord]
    ) -> list[SafetyFlag]:
        """Generate the full pre-op safety panel flags.

        Returns one SafetyFlag per drug class, sorted by severity
        (critical first), with status indicating whether any medication
        in that class is currently active.
        """
        classified = self.classify_all(medications)

        # Group classified meds by class
        by_class: dict[str, list[ClassifiedMedication]] = {
            key: [] for key in self._classes
        }
        for cm in classified:
            for cls_key in cm.matched_classes:
                by_class[cls_key].append(cm)

        severity_order = {"critical": 0, "warning": 1, "info": 2}
        flags: list[SafetyFlag] = []

        for key, info in self._classes.items():
            meds_in_class = by_class[key]
            if not meds_in_class:
                status = "NONE"
            elif any(cm.is_active for cm in meds_in_class):
                status = "ACTIVE"
            else:
                status = "HISTORICAL"

            flags.append(SafetyFlag(
                class_key=key,
                label=info.label,
                severity=info.severity,
                surgical_note=info.surgical_note,
                status=status,
                medications=meds_in_class,
            ))

        flags.sort(key=lambda f: (
            severity_order.get(f.severity, 9),
            0 if f.status == "ACTIVE" else 1 if f.status == "HISTORICAL" else 2,
        ))

        return flags
