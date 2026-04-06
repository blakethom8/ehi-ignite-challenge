"""
Condition acuity ranker — ranks active conditions by surgical relevance.

Surgical risk categories (high to low priority):
  CARDIAC: heart conditions, arrhythmia, CHF, CAD, MI, valve disease
  PULMONARY: COPD, asthma, OSA, pulmonary hypertension, interstitial lung
  METABOLIC: diabetes, obesity, thyroid, adrenal, electrolyte disorders
  RENAL: CKD, ESRD, dialysis, nephrotic syndrome
  HEPATIC: cirrhosis, hepatitis, liver failure
  HEMATOLOGIC: anemia, coagulopathy, thrombocytopenia, sickle cell
  NEUROLOGIC: seizure disorder, stroke, Parkinson's, dementia, neuropathy
  IMMUNOLOGIC: HIV, lupus, rheumatoid arthritis, inflammatory bowel
  ONCOLOGIC: cancer, malignancy, chemotherapy, radiation
  VASCULAR: peripheral artery disease, DVT, aortic aneurysm
  OTHER: everything else
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RankedCondition:
    condition_id: str
    display: str
    clinical_status: str
    onset_dt: str | None        # ISO string
    risk_category: str          # e.g. "CARDIAC"
    risk_rank: int              # 1=highest surgical risk, ascending
    risk_label: str             # e.g. "Cardiac"
    is_active: bool


class ConditionRanker:
    """Static keyword-based ranker for surgical risk categorisation."""

    CATEGORY_KEYWORDS: dict[str, tuple[int, str, list[str]]] = {
        # key: (rank, label, [keywords...])
        "CARDIAC": (1, "Cardiac", [
            "heart failure",
            "chf",
            "coronary",
            "arrhythmia",
            "atrial fibrillation",
            "myocardial",
            "cardiomyopathy",
            "valve",
            "aortic stenosis",
            "hypertrophic",
            "cardiac",
            "hypertension",
            "hypertensive",
            "heart disease",
            "pericarditis",
            "endocarditis",
        ]),
        "PULMONARY": (2, "Pulmonary", [
            "copd",
            "asthma",
            "sleep apnea",
            "pulmonary",
            "respiratory failure",
            "pneumonia",
            "interstitial lung",
            "bronchiectasis",
            "emphysema",
            "bronchitis",
            "pleural",
            "respiratory",
        ]),
        "METABOLIC": (3, "Metabolic", [
            "diabetes",
            "diabetic",
            "obesity",
            "hyperthyroid",
            "hypothyroid",
            "cushing",
            "addison",
            "metabolic syndrome",
            "hyperglycemia",
            "hypoglycemia",
            "thyroid",
            "electrolyte",
            "hyponatremia",
            "hyperkalemia",
        ]),
        "RENAL": (4, "Renal", [
            "kidney",
            "renal",
            "glomerulo",
            "nephrotic",
            "dialysis",
            "chronic kidney",
            "end-stage renal",
            "esrd",
            "acute kidney",
            "nephropathy",
            "proteinuria",
        ]),
        "HEPATIC": (5, "Hepatic", [
            "liver",
            "cirrhosis",
            "hepatitis",
            "hepatic",
            "portal hypertension",
            "liver failure",
            "liver disease",
            "cholangitis",
            "biliary",
            "jaundice",
        ]),
        "HEMATOLOGIC": (6, "Hematologic", [
            "anemia",
            "thrombocytopenia",
            "coagulopathy",
            "hemophilia",
            "sickle cell",
            "polycythemia",
            "leukemia",
            "lymphoma",
            "myelodysplastic",
            "von willebrand",
            "bleeding disorder",
            "thrombophilia",
        ]),
        "NEUROLOGIC": (7, "Neurologic", [
            "seizure",
            "epilepsy",
            "stroke",
            "parkinson",
            "dementia",
            "neuropathy",
            "multiple sclerosis",
            "myasthenia",
            "transient ischemic",
            "tia",
            "cerebrovascular",
            "alzheimer",
            "peripheral neuropathy",
        ]),
        "IMMUNOLOGIC": (8, "Immunologic", [
            "hiv",
            "lupus",
            "rheumatoid",
            "crohn",
            "ulcerative colitis",
            "sjogren",
            "psoriasis",
            "vasculitis",
            "immunodeficiency",
            "autoimmune",
            "inflammatory bowel",
            "systemic lupus",
        ]),
        "ONCOLOGIC": (9, "Oncologic", [
            "cancer",
            "carcinoma",
            "malignant",
            "tumor",
            "neoplasm",
            "metastatic",
            "lymphoma",
            "myeloma",
            "sarcoma",
            "melanoma",
            "leukemia",
            "malignancy",
        ]),
        "VASCULAR": (10, "Vascular", [
            "peripheral artery",
            "peripheral vascular",
            "deep vein",
            "dvt",
            "aneurysm",
            "atherosclerosis",
            "claudication",
            "aortic",
            "carotid",
            "ischemia",
            "thrombosis",
        ]),
    }

    def rank_condition(self, display: str) -> tuple[str, int, str]:
        """
        Return (category, rank, label) for a condition display string.

        Matches by checking if any keyword appears in display.lower().
        Returns the highest-priority (lowest rank number) match.
        Defaults to ("OTHER", 99, "Other") if no match found.
        """
        display_lower = display.lower()

        best_rank = 99
        best_category = "OTHER"
        best_label = "Other"

        for category, (rank, label, keywords) in self.CATEGORY_KEYWORDS.items():
            if rank >= best_rank:
                # Already have a better or equal match; skip unless this one
                # could still beat best_rank
                continue
            for keyword in keywords:
                if keyword in display_lower:
                    if rank < best_rank:
                        best_rank = rank
                        best_category = category
                        best_label = label
                    break  # Found a match in this category; move to next category

        return (best_category, best_rank, best_label)

    def rank_all(self, conditions: list) -> list[RankedCondition]:
        """
        Rank a list of ConditionSummary-like objects by surgical relevance.

        Accepts objects with: .condition_id, .display, .clinical_status,
        .onset_dt, .is_active attributes.

        Returns a list sorted by (risk_rank, display) ascending.
        """
        ranked: list[RankedCondition] = []

        for cond in conditions:
            category, rank, label = self.rank_condition(cond.display)

            # Normalise onset_dt to ISO string or None
            onset_str: str | None = None
            if cond.onset_dt is not None:
                try:
                    onset_str = cond.onset_dt.isoformat()
                except AttributeError:
                    onset_str = str(cond.onset_dt)

            ranked.append(RankedCondition(
                condition_id=cond.condition_id,
                display=cond.display,
                clinical_status=cond.clinical_status,
                onset_dt=onset_str,
                risk_category=category,
                risk_rank=rank,
                risk_label=label,
                is_active=cond.is_active,
            ))

        return sorted(ranked, key=lambda r: (r.risk_rank, r.display))
