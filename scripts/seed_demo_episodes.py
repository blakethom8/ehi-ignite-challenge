"""Hand-seed two EpisodeOfCare resources for the Phase 1 demo patient.

T4 of LLM-CONTEXT-AUGMENTATION-PLAN.md. Auto-detection is Phase 2 (P1);
for now we curate two episodes manually so the narrative generator (T5)
has stable targets to write Compositions against.

The default demo patient is **Lorenzo669** — picked for a rich
cardiometabolic chart (Prediabetes → Diabetes → CKD → Hypertriglyceridemia
→ Metabolic Syndrome → Coronary Heart Disease) plus a clean acute
diagnostic workup (Suspected lung cancer → NSCLC → TNM Stage 1, all
within ~2 weeks of 2006-09).

Run:
    uv run python scripts/seed_demo_episodes.py
    # or override:
    uv run python scripts/seed_demo_episodes.py --patient-id <stem-or-uuid>

Idempotent — overwrites ``data/narratives/<patient_id>/episodes.json``
on every run. Picks the same two conditions for the same patient
deterministically.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from api.core.loader import path_from_patient_id  # noqa: E402


DEFAULT_PATIENT_ID = "Lorenzo669_Cuellar188_2c57a897-8381-44a6-920f-e074fa6f74cf"


EPISODE_TYPE_SYSTEM = "http://atlas.healthcaredataai.com/fhir/CodeSystem/episode-type"
EPISODE_NARRATIVE_ID_URL = (
    "http://atlas.healthcaredataai.com/fhir/StructureDefinition/episode-narrative-id"
)


def _load_conditions(bundle_path: Path) -> list[dict[str, Any]]:
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    return [
        entry["resource"]
        for entry in data.get("entry", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("resource"), dict)
        and entry["resource"].get("resourceType") == "Condition"
    ]


def _find_by_display(conditions: list[dict[str, Any]], needle: str) -> dict[str, Any] | None:
    n = needle.lower()
    for c in conditions:
        coding = (c.get("code") or {}).get("coding") or [{}]
        display = (coding[0].get("display") or c.get("code", {}).get("text") or "").lower()
        if n in display:
            return c
    return None


def _patient_ref(bundle_path: Path) -> str:
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    for entry in data.get("entry", []):
        resource = (entry or {}).get("resource") or {}
        if resource.get("resourceType") == "Patient":
            return f"Patient/{resource['id']}"
    raise SystemExit(f"No Patient resource in bundle {bundle_path}")


def _episode_cardiometabolic(
    patient_ref: str, conditions: list[dict[str, Any]]
) -> dict[str, Any]:
    diabetes = _find_by_display(conditions, "Diabetes") or {}
    ckd = _find_by_display(conditions, "Chronic kidney disease") or {}
    chd = _find_by_display(conditions, "Coronary Heart Disease") or {}
    metsyn = _find_by_display(conditions, "Metabolic syndrome") or {}
    period_start = diabetes.get("onsetDateTime", "1980-01-01")[:10]

    diagnosis: list[dict[str, Any]] = []
    for rank, cond in enumerate((diabetes, chd, ckd, metsyn), start=1):
        if cond:
            diagnosis.append(
                {"condition": {"reference": f"Condition/{cond['id']}"}, "rank": rank}
            )

    return {
        "resourceType": "EpisodeOfCare",
        "id": "episode-cardiometabolic",
        "status": "active",
        "patient": {"reference": patient_ref},
        "period": {"start": period_start},
        "type": [
            {
                "coding": [
                    {
                        "system": EPISODE_TYPE_SYSTEM,
                        "code": "chronic-condition-management",
                        "display": "Cardiometabolic management",
                    }
                ],
                "text": "Cardiometabolic management",
            }
        ],
        "diagnosis": diagnosis,
        "extension": [
            {
                "url": EPISODE_NARRATIVE_ID_URL,
                "valueReference": {
                    "reference": "Composition/narrative-cardiometabolic-current"
                },
            }
        ],
    }


def _episode_lung_cancer_workup(
    patient_ref: str, conditions: list[dict[str, Any]]
) -> dict[str, Any]:
    suspected = _find_by_display(conditions, "Suspected lung cancer") or {}
    nsclc = _find_by_display(conditions, "Non-small cell lung cancer") or {}
    tnm = _find_by_display(conditions, "TNM stage") or {}
    start = (suspected.get("onsetDateTime") or "2006-09-01")[:10]
    end = (tnm.get("onsetDateTime") or "2006-09-30")[:10]

    diagnosis: list[dict[str, Any]] = []
    for rank, cond in enumerate((suspected, nsclc, tnm), start=1):
        if cond:
            diagnosis.append(
                {"condition": {"reference": f"Condition/{cond['id']}"}, "rank": rank}
            )

    return {
        "resourceType": "EpisodeOfCare",
        "id": "episode-lung-cancer-workup",
        "status": "finished",
        "patient": {"reference": patient_ref},
        "period": {"start": start, "end": end},
        "type": [
            {
                "coding": [
                    {
                        "system": EPISODE_TYPE_SYSTEM,
                        "code": "diagnostic-workup",
                        "display": "Lung cancer workup",
                    }
                ],
                "text": "Lung cancer workup",
            }
        ],
        "diagnosis": diagnosis,
        "extension": [
            {
                "url": EPISODE_NARRATIVE_ID_URL,
                "valueReference": {
                    "reference": "Composition/narrative-lung-cancer-workup-current"
                },
            }
        ],
    }


def seed_episodes(patient_id: str, *, out_root: Path | None = None) -> Path:
    bundle = path_from_patient_id(patient_id)
    if bundle is None:
        raise SystemExit(f"Could not resolve patient_id {patient_id!r} to a Synthea bundle")
    conditions = _load_conditions(bundle)
    if not conditions:
        raise SystemExit(f"Patient {patient_id} has no Condition resources")
    patient_ref = _patient_ref(bundle)

    episodes = [
        _episode_cardiometabolic(patient_ref, conditions),
        _episode_lung_cancer_workup(patient_ref, conditions),
    ]

    # Drop any episode where we couldn't find ANY of the curated diagnoses
    # — without diagnoses the narrative generator has nothing to cite.
    episodes = [e for e in episodes if e.get("diagnosis")]
    if not episodes:
        raise SystemExit(
            f"None of the curated episode templates matched conditions in {patient_id}'s chart"
        )

    out_dir = (out_root or REPO_ROOT / "data" / "narratives") / patient_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "episodes.json"
    out_path.write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": [{"resource": e} for e in episodes]}, indent=2),
        encoding="utf-8",
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--patient-id",
        default=DEFAULT_PATIENT_ID,
        help=f"Synthea patient ID (default: {DEFAULT_PATIENT_ID})",
    )
    args = parser.parse_args(argv)
    out_path = seed_episodes(args.patient_id)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
