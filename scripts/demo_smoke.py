"""End-to-end Phase 1 smoke (T9).

Exercises the data-layer beats of the §6 demo arc without spinning up
uvicorn or hitting a browser. UI beats (3-render, 4-render, 5-render,
6-render) are validated structurally by checking that the artifacts
the UI reads exist and carry the expected shape.

Run::

    uv run python scripts/demo_smoke.py

Exits 0 on success. On failure prints which beat broke and exits 1.

Uses Fake* backends throughout so no Anthropic key or budget is
needed. The Sonnet/Haiku backends are unit-tested separately.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


DEMO_PATIENT_ID = "Lorenzo669_Cuellar188_2c57a897-8381-44a6-920f-e074fa6f74cf"


# ---------------------------------------------------------------------------
# Beat assertions
# ---------------------------------------------------------------------------


def _fail(beat: str, msg: str) -> None:
    print(f"✗ beat {beat} failed: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(beat: str, msg: str) -> None:
    print(f"✓ {beat}: {msg}")


def beat_1_seed_episodes_exist() -> Path:
    """§6 beat 4 prerequisite: hand-seeded episodes.json exists for the demo patient."""
    path = REPO_ROOT / "data" / "narratives" / DEMO_PATIENT_ID / "episodes.json"
    if not path.exists():
        _fail("1", f"missing {path} — run scripts/seed_demo_episodes.py first")
    bundle = json.loads(path.read_text(encoding="utf-8"))
    episodes = [e["resource"] for e in bundle.get("entry") or []]
    if len(episodes) < 2:
        _fail("1", f"expected ≥2 episodes, found {len(episodes)}")
    _ok("1", f"{len(episodes)} hand-seeded episodes ({', '.join(e['id'] for e in episodes)})")
    return path


def beat_2_patient_voice_to_fhir(tmp_root: Path) -> Path:
    """§6 beat 2: patient_context session exports as FHIR.

    Builds a synthetic PatientContextSessionResponse (no live LLM), runs
    T1's adapter, and verifies the on-disk bundle.
    """
    from lib.patient_voice import (
        FakeTurnClassifier,
        TurnClassification,
        session_to_fhir_bundle,
    )

    session = {
        "session_id": "sess-smoke",
        "patient_id": DEMO_PATIENT_ID,
        "patient_label": "Demo Patient",
        "source_mode": "selected_patient",
        "source_posture": "demo",
        "gap_cards": [
            {
                "id": "medication-reality",
                "category": "medication_reality",
                "title": "Meds",
                "prompt": "Anything different?",
                "why_it_matters": "demo",
                "status": "answered",
                "priority": 5,
                "evidence": [],
            }
        ],
        "turns": [
            {
                "id": "t_4f2c9b",
                "role": "patient",
                "content": "I stopped lisinopril about 3 weeks ago — was making me cough.",
                "created_at": "2026-05-11T14:23:00+00:00",
                "linked_gap_id": "medication-reality",
            },
            {
                "id": "t_fish",
                "role": "patient",
                "content": "Also taking fish oil every morning, my cardiologist suggested it.",
                "created_at": "2026-05-11T14:24:00+00:00",
                "linked_gap_id": "medication-reality",
            },
        ],
        "facts": [],
        "export_status": {"generated": False, "files": [], "generated_at": None},
    }
    classifier = FakeTurnClassifier(
        by_turn_id={
            "t_4f2c9b": TurnClassification(
                kind="med_statement",
                status="stopped",
                drug_text="lisinopril",
                effective_end_iso="2026-04-20",
            ),
            "t_fish": TurnClassification(
                kind="med_statement",
                status="active",
                drug_text="fish oil",
            ),
        }
    )
    bundle = session_to_fhir_bundle(session, classifier=classifier, today_iso="2026-05-11")
    fhir_dir = tmp_root / "patient-context" / DEMO_PATIENT_ID / "fhir"
    fhir_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = fhir_dir / "sess-smoke.json"
    bundle_path.write_text(json.dumps(bundle, indent=2))

    entries = bundle.get("entry") or []
    if len(entries) != 2:
        _fail("2", f"expected 2 entries, got {len(entries)}")
    stopped = next(
        (e["resource"] for e in entries if e["resource"].get("status") == "stopped"),
        None,
    )
    if stopped is None:
        _fail("2", "no stopped MedicationStatement found")
    if stopped["medicationCodeableConcept"]["text"] != "lisinopril":
        _fail("2", f"expected lisinopril, got {stopped['medicationCodeableConcept']['text']}")
    if stopped["effectivePeriod"]["end"] != "2026-04-20":
        _fail("2", f"unexpected effective end {stopped['effectivePeriod']['end']}")
    _ok("2", f"FHIR bundle at {bundle_path.name} — 2 entries, stopped lisinopril + active fish oil")
    return bundle_path


def beat_3_harmonize_with_status_override(tmp_root: Path) -> dict:
    """§6 beat 3: merged record shows status=stopped + override provenance."""
    from lib.harmonize.medications import merge_medications
    from lib.harmonize.observations import SourceBundle
    from lib.harmonize.provenance import RESOLUTION_RULE_URL, mint_provenance
    from lib.patient_voice import patient_voice_source_bundles

    cedars = SourceBundle(
        label="Cedars-Sinai",
        observations=[
            {
                "resourceType": "MedicationRequest",
                "id": "mr-cedars-lisinopril",
                "status": "active",
                "authoredOn": "2025-09-01T00:00:00+00:00",
                "medicationCodeableConcept": {
                    "text": "Lisinopril 10 MG Oral Tablet",
                    "coding": [
                        {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "29046"}
                    ],
                },
            }
        ],
    )
    patient_bundles = patient_voice_source_bundles(
        DEMO_PATIENT_ID,
        resource_type="MedicationRequest",
        store_root=tmp_root / "patient-context",
    )
    if not patient_bundles:
        _fail("3", "patient_voice ingest produced no bundles")
    merged_list = merge_medications([cedars, *patient_bundles])
    lisinopril = next((m for m in merged_list if "lisinopril" in m.canonical_name.lower()), None)
    if lisinopril is None:
        _fail("3", "no merged lisinopril row")
    if lisinopril.canonical_status != "stopped":
        _fail("3", f"expected status=stopped, got {lisinopril.canonical_status}")
    if lisinopril.is_active:
        _fail("3", "is_active should be False after patient override")

    provenance = mint_provenance(lisinopril)
    patient_entities = [
        e for e in provenance["entity"]
        if any(
            ext.get("url") == RESOLUTION_RULE_URL
            and ext.get("valueString") == "patient-voice-status-override"
            for ext in e.get("extension", [])
        )
    ]
    if not patient_entities:
        _fail("3", "no entity carries patient-voice-status-override")
    _ok("3", f"merged lisinopril → stopped, override rule on {len(patient_entities)} entity(s)")
    return provenance


def beat_4_narratives_regenerated(tmp_root: Path) -> list[Path]:
    """§6 beat 4: per-episode narratives written with the patient turn cited."""
    from lib.narratives import FakeNarrativeGenerator
    from lib.narratives.generator import _Sections

    # Repoint the narrative store to tmp so we don't dirty the repo.
    os.environ["ATLAS_NARRATIVE_STORE_PATH"] = str(tmp_root / "narratives")
    # Reload so the constant picks up the env var.
    import importlib
    import lib.narratives.storage as storage_mod

    importlib.reload(storage_mod)
    import lib.narratives as narratives_mod

    importlib.reload(narratives_mod)
    from api.core import narrative_service as svc

    importlib.reload(svc)

    # Re-copy the episodes.json into the tmp narrative store.
    src = REPO_ROOT / "data" / "narratives" / DEMO_PATIENT_ID / "episodes.json"
    dst_dir = tmp_root / "narratives" / DEMO_PATIENT_ID
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / "episodes.json")

    # Force the patient_voice store to read from tmp.
    os.environ["PATIENT_CONTEXT_STORE_PATH"] = str(tmp_root / "patient-context")
    import lib.patient_voice.summarize as summarize_mod

    importlib.reload(summarize_mod)
    from lib.patient_voice import FakeVoiceSummarizer

    fake_summary = FakeVoiceSummarizer(
        summary="Patient stopped lisinopril ~3 weeks ago; started fish oil daily.",
        citations=["turn-t_4f2c9b", "turn-t_fish"],
    )
    fake_narrative = FakeNarrativeGenerator(
        default=_Sections(
            summary="Lorenzo's cardiometabolic story.",
            timeline="- Diabetes onset 1984",
            key_facts="Chronic management.",
            patient_words='"I stopped lisinopril about 3 weeks ago."',
            open_questions="",
        )
    )
    written = svc.regenerate_all_episodes(
        DEMO_PATIENT_ID,
        generator=fake_narrative,
        voice_summarizer=fake_summary,
    )
    if not written:
        _fail("4", "regenerate_all_episodes wrote nothing")
    _ok("4", f"wrote {len(written)} narrative(s) + voice summary")
    return written


def beat_6_caveats_written(tmp_root: Path) -> None:
    """§6 beat 6: conflicts panel — caveats.json has the lisinopril override."""
    from lib.harmonize.adjudicator import (
        FakeConflictAdjudicator,
        adjudicate_merged_record,
        write_caveats,
    )
    from lib.harmonize.medications import merge_medications
    from lib.harmonize.observations import SourceBundle
    from lib.patient_voice import patient_voice_source_bundles

    cedars = SourceBundle(
        label="Cedars-Sinai",
        observations=[
            {
                "resourceType": "MedicationRequest",
                "id": "mr-cedars-lisinopril-beat6",
                "status": "active",
                "authoredOn": "2025-09-01T00:00:00+00:00",
                "medicationCodeableConcept": {
                    "text": "Lisinopril 10 MG Oral Tablet",
                    "coding": [
                        {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "29046"}
                    ],
                },
            }
        ],
    )
    patient_bundles = patient_voice_source_bundles(
        DEMO_PATIENT_ID,
        resource_type="MedicationRequest",
        store_root=tmp_root / "patient-context",
    )
    merged = merge_medications([cedars, *patient_bundles])
    caveats = adjudicate_merged_record(
        DEMO_PATIENT_ID,
        merged_medications=merged,
        adjudicator=FakeConflictAdjudicator(),
    )
    if not caveats:
        _fail("6", "no caveats produced for lisinopril override")
    status_caveats = [c for c in caveats if c.fact_path.endswith(".status")]
    if not status_caveats:
        _fail("6", "no status caveat found")
    c = status_caveats[0]
    if c.verdict != "stopped":
        _fail("6", f"expected verdict=stopped, got {c.verdict}")
    if c.confidence != "high":
        _fail("6", f"expected confidence=high, got {c.confidence}")

    # Persist to tmp so beat 5 also reads them when ClinicalContext loads.
    os.environ["PATIENT_CONTEXT_STORE_PATH"] = str(tmp_root / "patient-context")
    import importlib
    import lib.harmonize.adjudicator as adjudicator_mod

    importlib.reload(adjudicator_mod)
    path = adjudicator_mod.write_caveats(DEMO_PATIENT_ID, caveats)
    if not path.exists():
        _fail("6", f"caveats.json not written to {path}")
    _ok("6", f"caveats written ({len(caveats)} entries), lisinopril verdict=stopped")


def beat_5_clinical_context_leads_with_patient_voice(tmp_root: Path) -> None:
    """§6 beat 5: Caspian's prompt opens with the patient's words."""
    import importlib

    # Repoint context_builder's repo root at tmp so it reads the seeded artifacts.
    import api.core.context_builder as ctx_mod

    original_root = ctx_mod._REPO_ROOT
    ctx_mod._REPO_ROOT = tmp_root.parent  # the tmp top-level holds data/...
    try:
        # The loaders look for data/narratives and data/patient-context. We
        # arranged tmp_root = .../data, so set _REPO_ROOT = parent.
        from api.core.context_builder import (
            EpisodeBrief,
            PatientVoiceContext,
            _load_caveats,
            _load_episode_briefs,
            _load_patient_voice_context,
            ClinicalContext,
        )

        voice = _load_patient_voice_context(DEMO_PATIENT_ID)
        if voice is None:
            _fail("5", "patient voice context not loaded from tmp store")
        if "lisinopril" not in voice.summary.lower():
            _fail("5", f"summary missing lisinopril: {voice.summary}")
        briefs = _load_episode_briefs(DEMO_PATIENT_ID)
        if not briefs:
            _fail("5", "episode briefs list is empty")
        caveats = _load_caveats(DEMO_PATIENT_ID)  # may be empty since T7 not run

        ctx = ClinicalContext(
            patient_summary="Lorenzo Cuellar",
            safety_flags=[],
            interactions=[],
            active_medications=[],
            active_conditions=[],
            key_labs=[],
            clinical_notes=[],
            recent_encounters=[],
            procedures_summary=[],
            historical_meds=[],
            resolved_conditions=[],
            absences=[],
            patient_voice=voice,
            episode_briefs=briefs,
            caveats=caveats,
        )
        prompt = ctx.to_prompt()
        if "In the patient's own words:" not in prompt:
            _fail("5", "prompt doesn't lead with patient voice")
        if "CARE EPISODES" not in prompt:
            _fail("5", "prompt missing CARE EPISODES section")
        _ok(
            "5",
            f"ClinicalContext.to_prompt() opens with patient voice + "
            f"{len(briefs)} episode brief(s) + {len(caveats)} caveat(s)",
        )
    finally:
        ctx_mod._REPO_ROOT = original_root


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    print(f"Phase 1 demo smoke for {DEMO_PATIENT_ID}\n")
    beat_1_seed_episodes_exist()
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td) / "data"
        tmp_root.mkdir()
        beat_2_patient_voice_to_fhir(tmp_root)
        beat_3_harmonize_with_status_override(tmp_root)
        beat_4_narratives_regenerated(tmp_root)
        beat_6_caveats_written(tmp_root)
        beat_5_clinical_context_leads_with_patient_voice(tmp_root)
    print("\n✓ all data-layer beats pass")
    print(
        "Frontend rendering (UI cards/drawer/panel) requires the running "
        "app; the data shapes for those panels are validated above."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
