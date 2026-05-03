"""
Patient classification script — loads all 1,180 synthetic FHIR bundles,
computes risk metrics and drug class flags, then categorises patients into
clinical showcase buckets.

Run from repo root:
    uv run python scripts/classify_patients.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — ensure repo root and patient-journey are importable
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "patient-journey"))

from lib.fhir_parser.bundle_parser import parse_bundle
from lib.patient_catalog.single_patient import compute_patient_stats
from core.drug_classifier import DrugClassifier

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"
DRUG_MAPPING = REPO_ROOT / "patient-journey" / "data" / "drug_classes.json"
OUTPUT_PATH = REPO_ROOT / "scripts" / "patient_classifications.json"

TODAY = date(2026, 4, 14)

# Known risky combos: (class_a, class_b) — order-independent
RISKY_COMBOS: list[tuple[str, str]] = [
    ("anticoagulants", "nsaids"),
    ("anticoagulants", "antiplatelets"),
    ("opioids", "psych_medications"),      # CNS depression risk
    ("ace_inhibitors", "nsaids"),           # renal risk
    ("arbs", "nsaids"),                     # renal risk
    ("immunosuppressants", "jak_inhibitors"),  # double immunosuppression
]

# SNOMED display substrings for chronic-disease-cascade detection
DIABETES_KEYWORDS = ["diabetes"]
CKD_KEYWORDS = ["chronic kidney", "renal"]
CARDIOVASCULAR_KEYWORDS = [
    "coronary", "heart failure", "hypertension",
    "atrial fibrillation", "ischemic heart",
]
NEUROPATHY_KEYWORDS = ["neuropathy"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _age_from_dob(dob: date | None) -> float:
    if dob is None:
        return 0.0
    delta = TODAY - dob
    return delta.days / 365.25


def _condition_matches(display: str, keywords: list[str]) -> bool:
    low = display.lower()
    return any(kw in low for kw in keywords)


# ---------------------------------------------------------------------------
# Per-patient analysis
# ---------------------------------------------------------------------------

def analyse_patient(filepath: Path, classifier: DrugClassifier) -> dict | None:
    """Parse one bundle and return a flat dict of metrics + flags."""
    try:
        record = parse_bundle(str(filepath))
    except Exception as exc:
        print(f"  WARN: failed to parse {filepath.name}: {exc}", file=sys.stderr)
        return None

    stats = compute_patient_stats(record)
    s = record.summary

    # --- basic counts ---
    n_conditions = len(record.conditions)
    n_medications = len(record.medications)
    n_observations = len(record.observations)
    n_encounters = len(record.encounters)
    n_procedures = len(record.procedures)
    n_immunizations = len(record.immunizations)
    n_allergies = len(record.allergies)

    total_resources = (
        n_conditions + n_medications + n_observations
        + n_encounters + n_procedures + n_immunizations + n_allergies
    )

    active_conditions = [c for c in record.conditions if c.is_active]
    active_meds = [m for m in record.medications if m.status in ("active", "on-hold")]

    # --- age ---
    age = _age_from_dob(s.birth_date)

    # --- drug classification ---
    classified = classifier.classify_all(record.medications)
    active_classified = classifier.classify_all(active_meds)

    drug_classes_present: set[str] = set()
    active_drug_classes: set[str] = set()
    for cm in classified:
        drug_classes_present.update(cm.matched_classes)
    for cm in active_classified:
        active_drug_classes.update(cm.matched_classes)

    # key flags
    has_anticoagulants = "anticoagulants" in active_drug_classes
    has_immunosuppressants = "immunosuppressants" in active_drug_classes
    has_insulin = any(
        "insulin" in m.display.lower() for m in active_meds
    )
    has_opioids = "opioids" in active_drug_classes
    has_nsaids = "nsaids" in active_drug_classes
    polypharmacy = len(active_meds) >= 5
    high_condition_burden = len(active_conditions) >= 10

    # --- risky combos ---
    risky_combo_hits: list[str] = []
    for a, b in RISKY_COMBOS:
        if a in active_drug_classes and b in active_drug_classes:
            risky_combo_hits.append(f"{a}+{b}")

    # --- chronic disease cascade ---
    active_displays = [c.code.label() for c in active_conditions]
    has_diabetes = any(_condition_matches(d, DIABETES_KEYWORDS) for d in active_displays)
    has_ckd = any(_condition_matches(d, CKD_KEYWORDS) for d in active_displays)
    has_cv = any(_condition_matches(d, CARDIOVASCULAR_KEYWORDS) for d in active_displays)
    has_neuropathy = any(_condition_matches(d, NEUROPATHY_KEYWORDS) for d in active_displays)
    chronic_cascade = has_diabetes and (has_ckd or has_cv or has_neuropathy)

    return {
        "patient_id": filepath.stem,
        "name": s.name,
        "age": round(age, 1),
        "gender": s.gender,
        "deceased": s.deceased,
        "total_resources": total_resources,
        "n_conditions": n_conditions,
        "n_active_conditions": len(active_conditions),
        "n_medications": n_medications,
        "n_active_medications": len(active_meds),
        "n_observations": n_observations,
        "n_encounters": n_encounters,
        "n_procedures": n_procedures,
        "n_immunizations": n_immunizations,
        "n_allergies": n_allergies,
        "drug_classes": sorted(drug_classes_present),
        "active_drug_classes": sorted(active_drug_classes),
        "complexity_score": stats.complexity_score,
        "complexity_tier": stats.complexity_tier,
        # flags
        "has_anticoagulants": has_anticoagulants,
        "has_immunosuppressants": has_immunosuppressants,
        "has_insulin": has_insulin,
        "has_opioids": has_opioids,
        "has_nsaids": has_nsaids,
        "polypharmacy": polypharmacy,
        "high_condition_burden": high_condition_burden,
        # cascade
        "chronic_cascade": chronic_cascade,
        "risky_combos": risky_combo_hits,
    }


# ---------------------------------------------------------------------------
# Category classifiers
# ---------------------------------------------------------------------------

def classify_into_categories(patients: list[dict]) -> dict[str, list[dict]]:
    """Assign each patient to zero or more showcase categories."""
    categories: dict[str, list[dict]] = {
        "high_surgical_risk": [],
        "low_risk_routine": [],
        "polypharmacy": [],
        "potential_drug_interactions": [],
        "pediatric": [],
        "elderly_complex": [],
        "chronic_disease_cascade": [],
        "minimal_record": [],
    }

    for p in patients:
        tier = p["complexity_tier"]
        age = p["age"]
        n_act_cond = p["n_active_conditions"]
        n_act_med = p["n_active_medications"]

        # High Surgical Risk
        if tier in ("complex", "highly_complex") and n_act_cond >= 10 and n_act_med >= 5:
            categories["high_surgical_risk"].append(p)

        # Low Risk / Routine
        if tier == "simple" and n_act_cond <= 3 and n_act_med <= 2 and 18 <= age <= 55:
            categories["low_risk_routine"].append(p)

        # Polypharmacy (8+ concurrent meds)
        if n_act_med >= 8:
            categories["polypharmacy"].append(p)

        # Potential Drug Interactions
        if p["risky_combos"]:
            categories["potential_drug_interactions"].append(p)

        # Pediatric
        if age < 18 and not p["deceased"]:
            categories["pediatric"].append(p)

        # Elderly Complex
        if age >= 70 and n_act_cond >= 5:
            categories["elderly_complex"].append(p)

        # Chronic Disease Cascade
        if p["chronic_cascade"]:
            categories["chronic_disease_cascade"].append(p)

        # Minimal Record
        if p["total_resources"] < 50:
            categories["minimal_record"].append(p)

    return categories


def pick_best_example(patients: list[dict], category: str) -> dict | None:
    """Pick the single most representative patient for a category."""
    if not patients:
        return None

    # Scoring heuristic per category — higher is more representative
    def score(p: dict) -> float:
        if category == "high_surgical_risk":
            return p["n_active_conditions"] + p["n_active_medications"] + p["complexity_score"]
        if category == "low_risk_routine":
            # Prefer alive, younger, fewest resources
            return -(p["n_active_conditions"] + p["n_active_medications"] + p["total_resources"])
        if category == "polypharmacy":
            return p["n_active_medications"]
        if category == "potential_drug_interactions":
            return len(p["risky_combos"]) * 10 + p["n_active_medications"]
        if category == "pediatric":
            return -p["age"]  # youngest
        if category == "elderly_complex":
            return p["age"] + p["n_active_conditions"]
        if category == "chronic_disease_cascade":
            return p["n_active_conditions"] + p["n_active_medications"]
        if category == "minimal_record":
            return -p["total_resources"]  # fewest resources
        return 0.0

    return max(patients, key=score)


# ---------------------------------------------------------------------------
# Population statistics
# ---------------------------------------------------------------------------

def compute_population_stats(patients: list[dict]) -> dict:
    tier_counts = Counter(p["complexity_tier"] for p in patients)
    age_buckets = Counter()
    for p in patients:
        a = p["age"]
        if a < 18:
            age_buckets["0-17"] += 1
        elif a < 30:
            age_buckets["18-29"] += 1
        elif a < 45:
            age_buckets["30-44"] += 1
        elif a < 60:
            age_buckets["45-59"] += 1
        elif a < 70:
            age_buckets["60-69"] += 1
        elif a < 80:
            age_buckets["70-79"] += 1
        else:
            age_buckets["80+"] += 1

    med_count_buckets = Counter()
    for p in patients:
        n = p["n_active_medications"]
        if n == 0:
            med_count_buckets["0"] += 1
        elif n <= 2:
            med_count_buckets["1-2"] += 1
        elif n <= 4:
            med_count_buckets["3-4"] += 1
        elif n <= 7:
            med_count_buckets["5-7"] += 1
        elif n <= 11:
            med_count_buckets["8-11"] += 1
        else:
            med_count_buckets["12+"] += 1

    flag_counts = {
        "has_anticoagulants": sum(1 for p in patients if p["has_anticoagulants"]),
        "has_immunosuppressants": sum(1 for p in patients if p["has_immunosuppressants"]),
        "has_insulin": sum(1 for p in patients if p["has_insulin"]),
        "has_opioids": sum(1 for p in patients if p["has_opioids"]),
        "polypharmacy_5plus": sum(1 for p in patients if p["polypharmacy"]),
        "high_condition_burden_10plus": sum(1 for p in patients if p["high_condition_burden"]),
        "any_risky_combo": sum(1 for p in patients if p["risky_combos"]),
        "chronic_disease_cascade": sum(1 for p in patients if p["chronic_cascade"]),
    }

    return {
        "total_patients": len(patients),
        "deceased_count": sum(1 for p in patients if p["deceased"]),
        "tier_distribution": dict(tier_counts),
        "age_histogram": dict(sorted(age_buckets.items())),
        "medication_count_distribution": dict(sorted(med_count_buckets.items())),
        "flag_counts": flag_counts,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  Patient Classification Script")
    print("=" * 70)

    # Init classifier
    classifier = DrugClassifier(mapping_path=DRUG_MAPPING)

    # Discover files
    files = sorted(DATA_DIR.glob("*.json"))
    print(f"\nFound {len(files)} patient bundle files in {DATA_DIR.relative_to(REPO_ROOT)}")

    # Parse all patients
    t0 = time.time()
    patients: list[dict] = []
    errors = 0
    for i, fp in enumerate(files, 1):
        if i % 100 == 0 or i == len(files):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i:>4}/{len(files)}] {rate:.0f} patients/sec ...", end="\r")
        result = analyse_patient(fp, classifier)
        if result is None:
            errors += 1
        else:
            patients.append(result)

    elapsed = time.time() - t0
    print(f"\n\nParsed {len(patients)} patients in {elapsed:.1f}s ({len(patients)/elapsed:.0f}/sec)")
    if errors:
        print(f"  ({errors} files failed to parse)")

    # Classify
    categories = classify_into_categories(patients)

    # Build output
    output: dict = {
        "generated": TODAY.isoformat(),
        "population_stats": compute_population_stats(patients),
        "categories": {},
    }

    for cat_key, cat_patients in categories.items():
        best = pick_best_example(cat_patients, cat_key)
        output["categories"][cat_key] = {
            "count": len(cat_patients),
            "best_example": {
                "patient_id": best["patient_id"],
                "name": best["name"],
                "age": best["age"],
                "complexity_tier": best["complexity_tier"],
                "n_active_conditions": best["n_active_conditions"],
                "n_active_medications": best["n_active_medications"],
                "total_resources": best["total_resources"],
                "drug_classes": best["active_drug_classes"],
                "risky_combos": best["risky_combos"],
            } if best else None,
            "patient_ids": [p["patient_id"] for p in cat_patients],
        }

    # Write JSON
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nJSON output written to {OUTPUT_PATH.relative_to(REPO_ROOT)}")

    # --- Human-readable summary ---
    print("\n" + "=" * 70)
    print("  POPULATION OVERVIEW")
    print("=" * 70)

    pop = output["population_stats"]
    print(f"\n  Total patients:  {pop['total_patients']}")
    print(f"  Deceased:        {pop['deceased_count']}")

    print(f"\n  Complexity tiers:")
    for tier in ["simple", "moderate", "complex", "highly_complex"]:
        n = pop["tier_distribution"].get(tier, 0)
        pct = n / pop["total_patients"] * 100
        bar = "#" * int(pct / 2)
        print(f"    {tier:<18} {n:>5}  ({pct:5.1f}%)  {bar}")

    print(f"\n  Age distribution:")
    for bucket in ["0-17", "18-29", "30-44", "45-59", "60-69", "70-79", "80+"]:
        n = pop["age_histogram"].get(bucket, 0)
        pct = n / pop["total_patients"] * 100
        bar = "#" * int(pct / 2)
        print(f"    {bucket:<8} {n:>5}  ({pct:5.1f}%)  {bar}")

    print(f"\n  Active medication counts:")
    for bucket in ["0", "1-2", "3-4", "5-7", "8-11", "12+"]:
        n = pop["medication_count_distribution"].get(bucket, 0)
        pct = n / pop["total_patients"] * 100
        bar = "#" * int(pct / 2)
        print(f"    {bucket:<8} {n:>5}  ({pct:5.1f}%)  {bar}")

    print(f"\n  Key flags:")
    for flag, count in pop["flag_counts"].items():
        pct = count / pop["total_patients"] * 100
        print(f"    {flag:<35} {count:>5}  ({pct:5.1f}%)")

    print("\n" + "=" * 70)
    print("  SHOWCASE CATEGORIES")
    print("=" * 70)

    CATEGORY_LABELS = {
        "high_surgical_risk": "High Surgical Risk",
        "low_risk_routine": "Low Risk / Routine",
        "polypharmacy": "Polypharmacy (8+ meds)",
        "potential_drug_interactions": "Potential Drug Interactions",
        "pediatric": "Pediatric (<18)",
        "elderly_complex": "Elderly Complex (70+, 5+ conditions)",
        "chronic_disease_cascade": "Chronic Disease Cascade",
        "minimal_record": "Minimal Record (<50 resources)",
    }

    for cat_key, info in output["categories"].items():
        label = CATEGORY_LABELS.get(cat_key, cat_key)
        print(f"\n  {label}")
        print(f"  {'~' * len(label)}")
        print(f"    Patients: {info['count']}")
        best = info["best_example"]
        if best:
            print(f"    Best example: {best['name']} (ID: {best['patient_id']})")
            print(f"      Age {best['age']} | Tier: {best['complexity_tier']} | "
                  f"{best['n_active_conditions']} active conditions | "
                  f"{best['n_active_medications']} active meds | "
                  f"{best['total_resources']} resources")
            if best["drug_classes"]:
                print(f"      Drug classes: {', '.join(best['drug_classes'])}")
            if best["risky_combos"]:
                print(f"      Risky combos: {', '.join(best['risky_combos'])}")
        else:
            print(f"    (no patients in this category)")

    print("\n" + "=" * 70)
    print("  Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()
