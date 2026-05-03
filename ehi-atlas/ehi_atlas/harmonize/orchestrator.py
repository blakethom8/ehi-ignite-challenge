"""Layer-3 harmonize pipeline orchestrator.

Reads silver Bundles for a patient across all sources, runs every harmonize
sub-task in dependency order, and emits gold-tier outputs:

    corpus/gold/patients/<patient>/
        bundle.json          # the merged FHIR Bundle
        provenance.ndjson    # the lineage graph (line-delimited)
        manifest.json        # build version, sources, counts, summary

Pipeline order (per DATA-AGGREGATION-LAYER.md):

    1. Load silver Bundles per source for this patient
    2. (Phase 1 expedient) For sources lacking a real L2 standardizer, synthesize
       a tiny silver Bundle from bronze. Marked with ``lifecycle=stub-silver``.
    3. Annotate every silver resource:
       - clinical-time via temporal.normalize_bundle_temporal
       - UMLS CUIs via code_map.annotate_resource_codings
       - quality via quality.annotate_quality
    4. Cluster + merge:
       - Patient resources → identity.build_identity_index → merged_patient
       - Conditions → condition.merge_all_conditions
       - MedicationRequests → medication.reconcile_episodes + detect_cross_class_flags
       - Observations → observation.dedup_observations
       - (Other resource types: pass through unchanged for Phase 1.)
    5. Detect conflicts:
       - Observation near-matches via conflict.detect_observation_conflicts
       - Medication cross-class via conflict.detect_medication_class_conflicts
    6. Apply conflict-pair extensions
    7. Emit Provenance via ProvenanceWriter:
       - One MERGE per cluster of merged Conditions / Observations
       - One DERIVE per ConflictPair
    8. Write bundle.json (sorted entries for determinism), provenance.ndjson,
       manifest.json

Phase 1 caveat: only Synthea has a real L2 standardizer; other sources fall
through the Stage-2-stub path. As Layer-2 work for synthea-payer / epic-ehi /
ccda / lab-pdf lands, those become real silver inputs.

Phase 1 sources handled:
    - synthea:                     real silver (L2 done, task 2.8)
    - epic-ehi:                    Stage-2-stub: synthesized from SQLite dump
    - lab-pdf:                     Stage-2-stub: creatinine Observation only
    - synthesized-clinical-note:   Stage-2-stub: passthrough FHIR bundle with tags
    - synthea-payer:               Stage-2-stub: passthrough from bronze with tags
    - ccda:                        deferred — returns None (no L2 toolchain yet)
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import tempfile
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ehi_atlas import __version__

# Import every harmonize sub-task
from ehi_atlas.harmonize.identity import (
    fingerprint_from_patient_resource,
    build_identity_index,
    merged_patient_resource,
    CanonicalPatient,
)
from ehi_atlas.harmonize.code_map import annotate_resource_codings
from ehi_atlas.harmonize.temporal import normalize_bundle_temporal
from ehi_atlas.harmonize.quality import annotate_quality
from ehi_atlas.harmonize.condition import merge_all_conditions
from ehi_atlas.harmonize.observation import dedup_observations
from ehi_atlas.harmonize.medication import (
    reconcile_episodes,
    detect_cross_class_flags,
    episode_from_medication_request,
)
from ehi_atlas.harmonize.conflict import (
    detect_observation_conflicts,
    detect_medication_class_conflicts,
    apply_conflict_pairs,
    emit_conflict_provenance,
)
from ehi_atlas.harmonize.provenance import (
    ProvenanceWriter,
    merge_provenance,
    SYS_SOURCE_TAG,
    SYS_LIFECYCLE,
    DEFAULT_RECORDED,
)

logger = logging.getLogger(__name__)

# All known source names in load order
_ALL_SOURCES = [
    "synthea",
    "synthea-payer",
    "ccda",
    "epic-ehi",
    "lab-pdf",
    "synthesized-clinical-note",
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class HarmonizeResult:
    patient_id: str
    bundle_path: Path
    provenance_path: Path
    manifest_path: Path
    source_count: int
    merged_counts: dict[str, int]   # e.g. {"Patient": 1, "Condition": 14, ...}
    conflict_count: int
    bundle_sha256: str


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def harmonize_patient(
    silver_root: Path,
    bronze_root: Path,
    gold_root: Path,
    patient_id: str,
) -> HarmonizeResult:
    """Run the full Layer-3 pipeline for one patient. Idempotent.

    Reads silver Bundles from ``silver_root/<source>/<patient_id>/bundle.json``
    with stub-silver fallback for sources without a real L2 standardizer.
    Writes gold-tier files to ``gold_root/patients/<patient_id>/``.

    Parameters
    ----------
    silver_root : Path
        Root of the silver tier (``corpus/silver/``).
    bronze_root : Path
        Root of the bronze tier (``corpus/bronze/``), used for stub synthesis.
    gold_root : Path
        Root of the gold tier (``corpus/gold/``).
    patient_id : str
        The canonical patient ID (e.g. ``"rhett759"``).
    """
    silver_root = Path(silver_root)
    bronze_root = Path(bronze_root)
    gold_root = Path(gold_root)

    # ------------------------------------------------------------------
    # Step 1: Load silver Bundles per source
    # ------------------------------------------------------------------
    source_bundles: dict[str, dict] = {}  # source_name → bundle dict
    source_paths: list[dict] = []         # for manifest

    for source in _ALL_SOURCES:
        silver_path = silver_root / source / patient_id / "bundle.json"
        if silver_path.exists():
            try:
                with silver_path.open(encoding="utf-8") as fh:
                    bundle = json.load(fh)
                source_bundles[source] = bundle
                source_paths.append({
                    "name": source,
                    "bundle_path": str(silver_path),
                    "fetched_at": DEFAULT_RECORDED,
                })
                logger.info("Loaded real silver for %s/%s", source, patient_id)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load silver %s/%s: %s", source, patient_id, exc)
            continue

        # No silver — try stub synthesizer
        stub_bundle = _synthesize_stub_silver(bronze_root, patient_id, source)
        if stub_bundle is not None:
            source_bundles[source] = stub_bundle
            source_paths.append({
                "name": source,
                "bundle_path": f"(stub-silver from bronze/{source}/{patient_id})",
                "fetched_at": DEFAULT_RECORDED,
            })
            logger.info("Synthesized stub-silver for %s/%s", source, patient_id)
        else:
            logger.info("Skipping source %s — no silver and no stub available", source)

    if not source_bundles:
        raise RuntimeError(
            f"No silver bundles available for patient {patient_id!r} in any source"
        )

    # ------------------------------------------------------------------
    # Step 2: Annotate every silver resource (temporal + code-map + quality)
    # ------------------------------------------------------------------
    for source_name, bundle in source_bundles.items():
        normalize_bundle_temporal(bundle)
        for entry in bundle.get("entry", []):
            resource = entry.get("resource") if isinstance(entry, dict) else None
            if not isinstance(resource, dict):
                continue
            annotate_resource_codings(resource)
            annotate_quality(resource)

    # ------------------------------------------------------------------
    # Step 3: Collect resources by type across all sources
    # ------------------------------------------------------------------
    patients_by_source: dict[str, list[dict]] = {}
    conditions_by_source: dict[str, list[dict]] = {}
    meds_by_source: dict[str, list[dict]] = {}
    obs_by_source: dict[str, list[dict]] = {}
    other_resources: list[dict] = []

    for source_name, bundle in source_bundles.items():
        for entry in bundle.get("entry", []):
            resource = entry.get("resource") if isinstance(entry, dict) else None
            if not isinstance(resource, dict):
                continue
            rtype = resource.get("resourceType", "")
            if rtype == "Patient":
                patients_by_source.setdefault(source_name, []).append(resource)
            elif rtype == "Condition":
                conditions_by_source.setdefault(source_name, []).append(resource)
            elif rtype == "MedicationRequest":
                meds_by_source.setdefault(source_name, []).append(resource)
            elif rtype == "Observation":
                obs_by_source.setdefault(source_name, []).append(resource)
            else:
                other_resources.append(resource)

    # ------------------------------------------------------------------
    # Step 4a: Patient identity — merge across sources
    # ------------------------------------------------------------------
    all_fingerprints = []
    patient_id_override: dict[str, str] = {}

    for source_name, patient_list in patients_by_source.items():
        for pat in patient_list:
            fp = fingerprint_from_patient_resource(source_name, pat)
            all_fingerprints.append(fp)
            # Map every source patient ID to the canonical patient_id
            patient_id_override[fp.local_patient_id] = patient_id

    identity_index = build_identity_index(
        all_fingerprints,
        canonical_id_for=patient_id_override,
    )

    # Get the merged patient resource
    merged_patient: dict | None = None
    if patient_id in identity_index.canonical_patients:
        canon = identity_index.canonical_patients[patient_id]
        merged_patient = merged_patient_resource(canon)
    elif identity_index.canonical_patients:
        # Take whichever canonical patient was created
        first_canon = next(iter(identity_index.canonical_patients.values()))
        merged_patient = merged_patient_resource(first_canon)
        # Override the id to match desired patient_id
        merged_patient["id"] = patient_id

    if merged_patient is None and all_fingerprints:
        # Fallback: build minimal merged patient from first fingerprint
        fp0 = all_fingerprints[0]
        merged_patient = {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {
                "tag": [
                    {"system": SYS_SOURCE_TAG, "code": fp0.source},
                    {"system": SYS_LIFECYCLE, "code": "harmonized"},
                ]
            },
        }

    # ------------------------------------------------------------------
    # Step 4b: Condition merge
    # ------------------------------------------------------------------
    merged_conditions, condition_merge_results = merge_all_conditions(
        conditions_by_source
    )

    # ------------------------------------------------------------------
    # Step 4c: Medication reconciliation + cross-class flags
    # ------------------------------------------------------------------
    merged_meds, med_merge_results = reconcile_episodes(meds_by_source)

    # Build all MedicationEpisodes for cross-class flag detection
    all_episodes = [
        episode_from_medication_request(req) for req in merged_meds
    ]
    # Also include unmerged originals in episode list for flag detection
    all_episodes_for_flags: list = []
    for source_name, reqs in meds_by_source.items():
        for req in reqs:
            ep = episode_from_medication_request(req)
            all_episodes_for_flags.append(ep)

    cross_class_flags = detect_cross_class_flags(all_episodes_for_flags)

    # ------------------------------------------------------------------
    # Step 4d: Observation dedup
    # ------------------------------------------------------------------
    all_observations = [
        obs
        for obs_list in obs_by_source.values()
        for obs in obs_list
    ]
    merged_observations, obs_merge_results = dedup_observations(all_observations)

    # ------------------------------------------------------------------
    # Step 5: Conflict detection
    # ------------------------------------------------------------------
    # Observation conflicts — after dedup so near-matches survived dedup
    # Use pre-merge per-source observations for conflict detection
    obs_conflicts = detect_observation_conflicts(obs_by_source)

    # Medication cross-class conflicts — adapt CrossClassFlag to protocol shape
    med_conflict_flags = _adapt_cross_class_flags(cross_class_flags, meds_by_source)
    med_conflicts = detect_medication_class_conflicts(med_conflict_flags)

    all_conflicts = obs_conflicts + med_conflicts

    # ------------------------------------------------------------------
    # Step 6: Apply conflict-pair extensions to the gold bundle resources
    # ------------------------------------------------------------------
    # Build a reference → resource lookup for the merged gold resources
    resources_by_ref: dict[str, dict] = {}
    for obs in merged_observations:
        obs_id = obs.get("id", "")
        if obs_id:
            resources_by_ref[f"Observation/{obs_id}"] = obs
    for med in merged_meds:
        med_id = med.get("id", "")
        if med_id:
            resources_by_ref[f"MedicationRequest/{med_id}"] = med
    # Also index pre-merge resources in case conflict refs them
    for obs_list in obs_by_source.values():
        for obs in obs_list:
            oid = obs.get("id", "")
            if oid:
                resources_by_ref.setdefault(f"Observation/{oid}", obs)
    for req_list in meds_by_source.values():
        for req in req_list:
            rid = req.get("id", "")
            if rid:
                resources_by_ref.setdefault(f"MedicationRequest/{rid}", req)

    apply_conflict_pairs(all_conflicts, resources_by_ref)

    # After apply_conflict_pairs, propagate any conflict-pair extensions that
    # were attached to silver-tier (pre-merge) dicts forward to the corresponding
    # gold-tier merged dicts.  This is necessary when a merged resource consumed
    # multiple silver originals — apply_conflict_pairs may have mutated one of
    # the originals, but the merged dict is a new object that didn't get the ext.
    from ehi_atlas.harmonize.provenance import EXT_CONFLICT_PAIR, attach_conflict_pair
    for req_list in meds_by_source.values():
        for req in req_list:
            silver_exts = req.get("extension", [])
            for ext in silver_exts:
                if ext.get("url") == EXT_CONFLICT_PAIR:
                    # Find the gold merged resource that absorbed this silver req
                    silver_ref = f"MedicationRequest/{req.get('id', '')}"
                    for gold_med in merged_meds:
                        identifiers = gold_med.get("identifier", [])
                        src_ids = {idn.get("value", "") for idn in identifiers}
                        if req.get("id", "") in src_ids or gold_med.get("id", "") == req.get("id", ""):
                            pair_ref = ext.get("valueReference", {}).get("reference", "")
                            if pair_ref:
                                attach_conflict_pair(gold_med, pair_ref)

    # ------------------------------------------------------------------
    # Step 7: Assemble gold-tier bundle entries
    # ------------------------------------------------------------------
    gold_entries: list[dict] = []

    # 1. Merged patient
    if merged_patient:
        gold_entries.append(_wrap_entry(merged_patient))

    # 2. Merged conditions
    for cond in merged_conditions:
        gold_entries.append(_wrap_entry(cond))

    # 3. Merged medications
    for med in merged_meds:
        gold_entries.append(_wrap_entry(med))

    # 4. Merged observations (deduped)
    for obs in merged_observations:
        gold_entries.append(_wrap_entry(obs))

    # 5. Other resource types (pass-through)
    # Deduplicate by (resourceType, id)
    seen_other_refs: set[str] = set()
    for res in other_resources:
        rtype = res.get("resourceType", "")
        rid = res.get("id", "")
        ref = f"{rtype}/{rid}"
        if ref in seen_other_refs:
            continue
        seen_other_refs.add(ref)
        gold_entries.append(_wrap_entry(res))

    # Sort for determinism: (resourceType, id)
    gold_entries.sort(
        key=lambda e: (
            e.get("resource", {}).get("resourceType", ""),
            e.get("resource", {}).get("id", ""),
        )
    )

    # ------------------------------------------------------------------
    # Step 7b: Write provenance.ndjson
    # ------------------------------------------------------------------
    gold_patient_dir = gold_root / "patients" / patient_id
    gold_patient_dir.mkdir(parents=True, exist_ok=True)

    with ProvenanceWriter(gold_root, patient_id) as pw:
        # MERGE records for condition clusters
        for result in condition_merge_results:
            pw.add(result.provenance)

        # MERGE records for medication episode reconciliations
        for result in med_merge_results:
            pw.add(result.provenance)

        # MERGE records for observation dedup
        for result in obs_merge_results:
            prov = merge_provenance(
                target=f"Observation/{result.merged.get('id', 'unknown')}",
                sources=result.sources,
                rationale=result.rationale,
            )
            pw.add(prov)

        # DERIVE records for conflicts
        emit_conflict_provenance(all_conflicts, pw)

    provenance_path = (gold_root / "patients" / patient_id / "provenance.ndjson")

    # ------------------------------------------------------------------
    # Step 8: Write bundle.json
    # ------------------------------------------------------------------
    gold_bundle: dict = {
        "resourceType": "Bundle",
        "id": f"gold-{patient_id}",
        "type": "collection",
        "meta": {
            "tag": [
                {"system": SYS_LIFECYCLE, "code": "gold"},
            ]
        },
        "entry": gold_entries,
    }

    bundle_path = gold_patient_dir / "bundle.json"
    bundle_json = json.dumps(gold_bundle, indent=2, ensure_ascii=False, sort_keys=True)
    bundle_path.write_text(bundle_json, encoding="utf-8")

    # SHA-256 for idempotency check
    bundle_sha256 = hashlib.sha256(bundle_json.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Step 9: Write manifest.json
    # ------------------------------------------------------------------
    # Count resources by type in the gold bundle
    merged_counts: dict[str, int] = {}
    for entry in gold_entries:
        rtype = entry.get("resource", {}).get("resourceType", "unknown")
        merged_counts[rtype] = merged_counts.get(rtype, 0) + 1

    # Count provenance records from the ndjson
    prov_count = 0
    if provenance_path.exists():
        with provenance_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    prov_count += 1
    merged_counts["Provenance"] = prov_count

    manifest: dict = {
        "patient_id": patient_id,
        "harmonizer_version": __version__,
        "built_at": DEFAULT_RECORDED,
        "sources": source_paths,
        "resource_counts": merged_counts,
        "merge_summary": {
            "conditions_merged": len(condition_merge_results),
            "medications_reconciled": len(med_merge_results),
            "observations_deduped": len(obs_merge_results),
            "conflicts_detected": len(all_conflicts),
        },
    }

    manifest_path = gold_patient_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return HarmonizeResult(
        patient_id=patient_id,
        bundle_path=bundle_path,
        provenance_path=provenance_path,
        manifest_path=manifest_path,
        source_count=len(source_bundles),
        merged_counts=merged_counts,
        conflict_count=len(all_conflicts),
        bundle_sha256=bundle_sha256,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap_entry(resource: dict) -> dict:
    """Wrap a FHIR resource dict into a Bundle.entry dict."""
    rtype = resource.get("resourceType", "Unknown")
    rid = resource.get("id", str(uuid.uuid4()))
    return {
        "fullUrl": f"{rtype}/{rid}",
        "resource": resource,
    }


def _make_stub_tag(source: str) -> list[dict]:
    """Return the meta.tag list for a stub-silver resource."""
    return [
        {"system": SYS_SOURCE_TAG, "code": source},
        {"system": SYS_LIFECYCLE, "code": "stub-silver"},
    ]


def _add_stub_meta(resource: dict, source: str) -> dict:
    """Ensure the resource has the stub-silver meta tags."""
    meta = resource.setdefault("meta", {})
    existing_tags: list = meta.get("tag", [])
    # Keep any non-source-tag / non-lifecycle existing tags
    filtered = [
        t for t in existing_tags
        if isinstance(t, dict)
        and t.get("system") not in (SYS_SOURCE_TAG, SYS_LIFECYCLE)
    ]
    filtered.extend(_make_stub_tag(source))
    meta["tag"] = filtered
    return resource


def _adapt_cross_class_flags(
    flags: list,
    meds_by_source: dict[str, list[dict]],
) -> list:
    """Adapt CrossClassFlag from medication.py to the protocol shape expected by conflict.py.

    medication.CrossClassFlag has: ingredient_a, ingredient_b, sources_a (list),
    sources_b (list), common_class_label.

    conflict.CrossClassFlagProtocol expects: ingredient_a, ingredient_b, class_label,
    source_a (str), source_b (str), resource_a_reference, resource_b_reference.

    This adapter creates lightweight objects bridging the two representations.
    """
    from dataclasses import dataclass as _dc

    @_dc
    class _AdaptedFlag:
        ingredient_a: str
        ingredient_b: str
        class_label: str
        source_a: str
        source_b: str
        resource_a_reference: str
        resource_b_reference: str

    def _find_med_ref(rxcui: str, sources: list[str], meds_by_src: dict) -> str:
        """Find the first MedicationRequest reference for this rxcui in the given sources."""
        for src in sources:
            for req in meds_by_src.get(src, []):
                med_cc = req.get("medicationCodeableConcept", {})
                for coding in med_cc.get("coding", []):
                    if (
                        coding.get("system") == "http://www.nlm.nih.gov/research/umls/rxnorm"
                        and coding.get("code") == rxcui
                    ):
                        return f"MedicationRequest/{req.get('id', 'unknown')}"
        return f"MedicationRequest/unknown-rxcui-{rxcui}"

    adapted = []
    for flag in flags:
        source_a = flag.sources_a[0] if flag.sources_a else "unknown"
        source_b = flag.sources_b[0] if flag.sources_b else "unknown"
        ref_a = _find_med_ref(flag.ingredient_a, flag.sources_a, meds_by_source)
        ref_b = _find_med_ref(flag.ingredient_b, flag.sources_b, meds_by_source)
        adapted.append(
            _AdaptedFlag(
                ingredient_a=flag.ingredient_a,
                ingredient_b=flag.ingredient_b,
                class_label=flag.common_class_label,
                source_a=source_a,
                source_b=source_b,
                resource_a_reference=ref_a,
                resource_b_reference=ref_b,
            )
        )
    return adapted


# ---------------------------------------------------------------------------
# Stub-silver dispatcher
# ---------------------------------------------------------------------------


def _synthesize_stub_silver(
    bronze_root: Path, patient_id: str, source: str
) -> dict | None:
    """Dispatch to the appropriate stub-silver synthesizer for a given source.

    Returns None when no synthesis is available for the source or the bronze
    data is missing.
    """
    if source == "epic-ehi":
        return _stub_silver_from_epic_ehi_bronze(bronze_root, patient_id)
    if source == "lab-pdf":
        return _stub_silver_from_lab_pdf_bronze(bronze_root, patient_id)
    if source == "synthesized-clinical-note":
        return _stub_silver_from_synthesized_clinical_note_bronze(bronze_root, patient_id)
    if source == "synthea-payer":
        return _stub_silver_from_synthea_payer_bronze(bronze_root, patient_id)
    # ccda — deferred (no L2 toolchain)
    return None


# ---------------------------------------------------------------------------
# Phase-1 stub-silver synthesizers — REMOVE WHEN L2 LANDS PER SOURCE
# ---------------------------------------------------------------------------


def _stub_silver_from_epic_ehi_bronze(bronze_root: Path, patient_id: str) -> dict | None:
    """Stage-2-stub: replace with real Epic L2 standardizer per task 2.x.

    Read bronze epic-ehi/<patient_id>/data.sqlite.dump, restore it into a
    temporary SQLite database, and emit a tiny silver Bundle covering just
    enough resources to exercise Layer 3.

    Resources emitted:
    - Patient (from PAT_PATIENT)
    - Conditions (from PROBLEM_LIST, ICD-10 only — forces UMLS-CUI merge with
      Synthea SNOMED codes for Artifact 1)
    - MedicationRequests (from ORDER_MED with RxNorm codes)
    - Observations (from ORDER_RESULTS joined with LNC_DB_MAIN for LOINC)

    Every resource tagged with lifecycle=stub-silver + source-tag=epic-ehi.
    Returns None if the bronze dump is missing.
    """
    dump_path = bronze_root / "epic-ehi" / patient_id / "data.sqlite.dump"
    if not dump_path.exists():
        return None

    try:
        with open(dump_path, encoding="utf-8") as fh:
            sql_dump = fh.read()
    except OSError as exc:
        logger.warning("Cannot read epic-ehi dump at %s: %s", dump_path, exc)
        return None

    # Restore to a temporary in-memory SQLite
    tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_db_fd)
    try:
        conn = sqlite3.connect(tmp_db_path)
        conn.executescript(sql_dump)

        entries: list[dict] = []
        # Epic SQLite data stores patient IDs uppercase (e.g. RHETT759)
        pat_id_upper = patient_id.upper()

        # --- Patient ---
        patient_row = conn.execute(
            "SELECT PAT_ID, PAT_MRN_ID, PAT_NAME, BIRTH_DATE, SEX_C_NAME FROM PAT_PATIENT "
            "WHERE PAT_ID = ? LIMIT 1",
            (pat_id_upper,),
        ).fetchone()
        if patient_row is None:
            # Fallback: take any patient from the dump
            patient_row = conn.execute(
                "SELECT PAT_ID, PAT_MRN_ID, PAT_NAME, BIRTH_DATE, SEX_C_NAME FROM PAT_PATIENT LIMIT 1"
            ).fetchone()
        if patient_row:
            pat_id, mrn, name_raw, birth_date, sex = patient_row
            # name format: "FAMILY,Given" — split on comma
            name_parts = name_raw.split(",", 1) if name_raw else ["Unknown", ""]
            family = name_parts[0].strip().title()
            given = name_parts[1].strip().title() if len(name_parts) > 1 else ""
            gender_map = {"Male": "male", "Female": "female"}
            patient_res: dict = {
                "resourceType": "Patient",
                "id": f"epic-{pat_id.lower()}",
                "meta": {"tag": _make_stub_tag("epic-ehi")},
                "identifier": [{"system": "urn:epic:mrn", "value": mrn}],
                "name": [{"use": "official", "family": family, "given": [given] if given else []}],
                "birthDate": birth_date,
                "gender": gender_map.get(sex, "unknown"),
            }
            entries.append({"fullUrl": f"Patient/epic-{pat_id.lower()}", "resource": patient_res})

        # --- Conditions (PROBLEM_LIST with ICD-10 only) ---
        try:
            prob_rows = conn.execute(
                "SELECT PROBLEM_LIST_ID, PAT_ID, DX_NAME, ICD10_CODE, ONSET_DATE, "
                "PROBLEM_STATUS_C_NAME "
                "FROM PROBLEM_LIST WHERE PAT_ID = ? AND ICD10_CODE != ''",
                (pat_id_upper,),
            ).fetchall()
        except sqlite3.OperationalError:
            prob_rows = []

        for row in prob_rows:
            prob_id, pat_id_col, prob_name, icd10, noted_date, status = row
            clinical_status_code = "active" if (status or "").lower() == "active" else "inactive"
            cond_res: dict = {
                "resourceType": "Condition",
                "id": f"epic-cond-{prob_id.lower()}",
                "meta": {"tag": _make_stub_tag("epic-ehi")},
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": clinical_status_code,
                    }]
                },
                "verificationStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed",
                    }]
                },
                "code": {
                    "coding": [{
                        "system": "http://hl7.org/fhir/sid/icd-10-cm",
                        "code": icd10,
                        "display": prob_name,
                    }],
                    "text": prob_name,
                },
                "subject": {"reference": f"Patient/epic-{(patient_id or pat_id_col).lower()}"},
            }
            if noted_date:
                cond_res["onsetDateTime"] = noted_date
            entries.append({
                "fullUrl": f"Condition/epic-cond-{prob_id.lower()}",
                "resource": cond_res,
            })

        # --- MedicationRequests (ORDER_MED) ---
        try:
            med_rows = conn.execute(
                "SELECT ORDER_MED_ID, PAT_ID, MED_DISPLAY, RXNORM_CODE, START_DATE, END_DATE, "
                "ORDER_STATUS_C_NAME "
                "FROM ORDER_MED WHERE PAT_ID = ?",
                (pat_id_upper,),
            ).fetchall()
        except sqlite3.OperationalError:
            med_rows = []

        for row in med_rows:
            med_id, pat_id_col, med_name, rxcui, start_date, end_date, status = row
            fhir_status_map = {
                "Active": "active",
                "Discontinued": "stopped",
                "Stopped": "stopped",
                "Completed": "completed",
                "Cancelled": "cancelled",
            }
            fhir_status = fhir_status_map.get(status, "unknown")
            med_coding: dict = {"display": med_name or ""}
            if rxcui:
                med_coding["system"] = "http://www.nlm.nih.gov/research/umls/rxnorm"
                med_coding["code"] = rxcui

            med_res: dict = {
                "resourceType": "MedicationRequest",
                "id": f"epic-med-{med_id.lower()}",
                "meta": {"tag": _make_stub_tag("epic-ehi")},
                "status": fhir_status,
                "intent": "order",
                "medicationCodeableConcept": {
                    "coding": [med_coding],
                    "text": med_name,
                },
                "subject": {"reference": f"Patient/epic-{(patient_id or pat_id_col).lower()}"},
            }
            if start_date:
                med_res["authoredOn"] = start_date

            if start_date or end_date:
                validity: dict = {}
                if start_date:
                    validity["start"] = start_date
                if end_date:
                    validity["end"] = end_date
                med_res["dispenseRequest"] = {"validityPeriod": validity}

            entries.append({
                "fullUrl": f"MedicationRequest/epic-med-{med_id.lower()}",
                "resource": med_res,
            })

        # --- Observations (ORDER_RESULTS joined with LNC_DB_MAIN for LOINC) ---
        # NOTE: ORDER_RESULTS.COMPON_LNC_ID is NULL for most rows; the join
        # uses COMPONENT_ID on ORDER_RESULTS joined against LNC_DB_MAIN.COMPONENT_ID
        # (the 3-pass heuristic from inspection task 1.6).
        try:
            result_rows = conn.execute(
                """
                SELECT r.RESULT_ID, r.PAT_ID, r.COMPONENT_ID, l.LNC_CODE, l.LNC_DISPLAY,
                       r.RESULT_DATE, r.ORD_VALUE, r.REFERENCE_UNIT
                FROM ORDER_RESULTS r
                LEFT JOIN LNC_DB_MAIN l ON r.COMPONENT_ID = l.COMPONENT_ID
                WHERE r.PAT_ID = ?
                """,
                (pat_id_upper,),
            ).fetchall()
        except sqlite3.OperationalError:
            result_rows = []

        for row in result_rows:
            (res_id, pat_id_col, comp_id, lnc_code, lnc_display,
             result_date, value_numeric, unit) = row

            obs_res: dict = {
                "resourceType": "Observation",
                "id": f"epic-obs-{res_id.lower()}",
                "meta": {"tag": _make_stub_tag("epic-ehi")},
                "status": "final",
                "subject": {"reference": f"Patient/epic-{(patient_id or pat_id_col).lower()}"},
            }

            if lnc_code:
                obs_res["code"] = {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": lnc_code,
                        "display": lnc_display or "",
                    }]
                }
            else:
                # No LOINC — use local component ID as fallback; won't merge
                obs_res["code"] = {
                    "coding": [{
                        "system": "urn:epic:component-id",
                        "code": comp_id or res_id,
                    }]
                }

            if result_date:
                obs_res["effectiveDateTime"] = result_date

            if value_numeric is not None:
                try:
                    obs_res["valueQuantity"] = {
                        "value": float(value_numeric),
                        "unit": unit or "",
                        "system": "http://unitsofmeasure.org",
                        "code": unit or "",
                    }
                except (TypeError, ValueError):
                    obs_res["valueString"] = str(value_numeric)

            entries.append({
                "fullUrl": f"Observation/epic-obs-{res_id.lower()}",
                "resource": obs_res,
            })

        conn.close()

    except Exception as exc:
        logger.warning("Failed to synthesize epic-ehi stub for %s: %s", patient_id, exc)
        try:
            conn.close()
        except Exception:
            pass
        return None
    finally:
        try:
            os.unlink(tmp_db_path)
        except OSError:
            pass

    if not entries:
        return None

    return {
        "resourceType": "Bundle",
        "id": f"stub-epic-ehi-{patient_id}",
        "type": "collection",
        "entry": entries,
    }


def _stub_silver_from_lab_pdf_bronze(bronze_root: Path, patient_id: str) -> dict | None:
    """Stage-2-stub: replace with real lab-pdf L2 standardizer per task 2.x.

    Emits a tiny silver Bundle with the creatinine Observation matching
    Artifact 5 (LOINC 2160-0, value 1.4 mg/dL on 2025-09-12).

    Phase 2 replaces this with real vision-extraction-driven silver via 4.3
    wired to a Layer-2 lab-pdf step.

    Tags every resource with lifecycle=stub-silver so it's distinguishable.
    Returns None if bronze is missing.
    """
    bronze_pdf = bronze_root / "lab-pdf" / patient_id / "data.pdf"
    if not bronze_pdf.exists():
        return None

    # Emit the Artifact 5 creatinine observation (known values from the synthesized PDF)
    obs_creatinine: dict = {
        "resourceType": "Observation",
        "id": f"lab-pdf-obs-creatinine-{patient_id}",
        "meta": {"tag": _make_stub_tag("lab-pdf")},
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "laboratory",
                "display": "Laboratory",
            }]
        }],
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "2160-0",
                "display": "Creatinine [Mass/volume] in Serum or Plasma",
            }],
            "text": "Creatinine",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": "2025-09-12",
        "valueQuantity": {
            "value": 1.4,
            "unit": "mg/dL",
            "system": "http://unitsofmeasure.org",
            "code": "mg/dL",
        },
    }

    return {
        "resourceType": "Bundle",
        "id": f"stub-lab-pdf-{patient_id}",
        "type": "collection",
        "entry": [
            {
                "fullUrl": f"Observation/lab-pdf-obs-creatinine-{patient_id}",
                "resource": obs_creatinine,
            }
        ],
    }


def _stub_silver_from_synthesized_clinical_note_bronze(
    bronze_root: Path, patient_id: str
) -> dict | None:
    """Stage-2-stub: replace with real synthesized-clinical-note L2 standardizer per task 2.x.

    The synthesized-clinical-note bronze is already a FHIR Bundle (DocumentReference +
    Binary). This is nearly a passthrough — it adds source-tag and lifecycle=stub-silver
    tags to each resource so it joins the rest of the pipeline cleanly.

    Returns None if bronze is missing.
    """
    bronze_json = bronze_root / "synthesized-clinical-note" / patient_id / "data.json"
    if not bronze_json.exists():
        return None

    try:
        with bronze_json.open(encoding="utf-8") as fh:
            bundle = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot load synthesized-clinical-note bronze: %s", exc)
        return None

    # Tag every resource with stub-silver metadata
    for entry in bundle.get("entry", []):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict):
            _add_stub_meta(resource, "synthesized-clinical-note")

    # Ensure the bundle itself is tagged
    bundle.setdefault("meta", {})["tag"] = _make_stub_tag("synthesized-clinical-note")

    return bundle


def _stub_silver_from_synthea_payer_bronze(
    bronze_root: Path, patient_id: str
) -> dict | None:
    """Stage-2-stub: passthrough from synthea-payer bronze with stub-silver tags.

    The synthea-payer bronze is a FHIR Bundle with Claim + ExplanationOfBenefit
    resources. Tags each resource with lifecycle=stub-silver so it flows into
    the pipeline as a recognized source. Since these are Claim/EoB types, they
    will pass through as 'other' resources in the orchestrator (no merge logic
    for them in Phase 1).

    Returns None if bronze is missing.
    """
    bronze_json = bronze_root / "synthea-payer" / patient_id / "data.json"
    if not bronze_json.exists():
        return None

    try:
        with bronze_json.open(encoding="utf-8") as fh:
            bundle = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot load synthea-payer bronze: %s", exc)
        return None

    for entry in bundle.get("entry", []):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict):
            _add_stub_meta(resource, "synthea-payer")

    bundle.setdefault("meta", {})["tag"] = _make_stub_tag("synthea-payer")
    return bundle
