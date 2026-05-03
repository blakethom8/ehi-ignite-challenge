"""Epic EHI Export adapter (Layer 1).

Supports two distinct flows, both producing bronze records under
``bronze/epic-ehi/<patient_id>/``:

Flow A — "josh-fixture"
    Copies Josh Mandel's redacted SQLite dump verbatim.
    Purpose: parser-shape validation (415 tables, real Epic schema).
    Consent posture: open (Josh published intentionally).

Flow B — "rhett759"
    Projects Rhett759's Synthea FHIR Bundle into a minimal Epic-EHI
    SQLite database.  The resulting ``data.sqlite.dump`` emulates the
    on-disk format of a real Epic EHI export so that Layer 2 can parse
    both sources with the same code path.

    Projection deliberately introduces three showcase-artifact anchors:
      - Artifact 1: Conditions use ICD-10 codes only (no SNOMED) — creates
        a coding-system divergence from the Synthea source that Layer 3
        resolves via the hand-curated crosswalk / UMLS CUI.
      - Artifact 2: Simvastatin (Synthea) is swapped for atorvastatin
        marked discontinued in Q3 2025 — creates a cross-source medication
        conflict that Layer 3 flags and explains.
      - Artifact 5: A creatinine observation (LOINC 2160-0, 1.4 mg/dL,
        2025-09-12) is included in ORDER_RESULTS / LNC_DB_MAIN — the same
        value appears in the synthesized lab PDF, enabling the
        PDF ↔ FHIR ↔ Epic three-way merge.

Privacy posture:
    josh-fixture  → ``open``  (Josh's own published data)
    rhett759      → ``constructed`` (synthesized projection)
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import io
from pathlib import Path
from typing import Any

from .base import Adapter, SourceMetadata
from ehi_atlas.terminology import lookup_cross

# Frozen timestamp — matches every other Phase 1 adapter for idempotency.
ACQUISITION_TS = "2000-01-01T00:00:00+00:00"

# Rhett759 Synthea bundle filename
_RHETT759_BUNDLE = "Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61.json"

# Artifact 2: atorvastatin RxCUI and metadata
_ATORVASTATIN_RXCUI = "83367"
_ATORVASTATIN_DISPLAY = "Atorvastatin 40 MG Oral Tablet"
_ATORVASTATIN_DISCONTINUED = "2025-09-01"  # Q3 2025

# Artifact 5: creatinine anchor (matches synthesized lab PDF date exactly)
_CREATININE_LOINC = "2160-0"
_CREATININE_DISPLAY = "Creatinine [Mass/volume] in Serum or Plasma"
_CREATININE_VALUE = 1.4
_CREATININE_UNIT = "mg/dL"
_CREATININE_DATE = "2025-09-12"

# SNOMED system URI (as used in Synthea)
_SNOMED_SYSTEM = "http://snomed.info/sct"

# Showcase LOINC codes to pull from Synthea observations into ORDER_RESULTS
# (superset of what the lab PDF covers, plus vitals)
_SHOWCASE_LOINCS = {
    "38483-4",   # Creatinine (Synthea's code; we'll remap to 2160-0 per Epic projection)
    "6299-2",    # BUN / Urea nitrogen
    "33914-3",   # eGFR
    "2947-0",    # Sodium (Synthea code)
    "6298-4",    # Potassium (Synthea code)
    "2069-3",    # Chloride (Synthea code)
    "20565-8",   # CO2
    "2339-0",    # Glucose (Synthea random glucose)
    "4548-4",    # HbA1c
    "49765-1",   # Calcium (Synthea code)
    "2885-2",    # Protein
    "1751-7",    # Albumin
    "1742-6",    # ALT
    "1920-8",    # AST
    "6768-6",    # Alk phos
    "1975-2",    # Total bilirubin
    "718-7",     # Hemoglobin
    "55284-4",   # Blood pressure (component obs)
    "39156-5",   # BMI
    "29463-7",   # Body weight
    "8302-2",    # Body height
    "2093-3",    # Total cholesterol
    "2085-9",    # HDL cholesterol
    "18262-6",   # LDL cholesterol
    "2571-8",    # Triglycerides
    "19926-5",   # FEV1/FVC (COPD marker)
}

# Map Synthea LOINC codes to canonical Epic/showcase LOINCs where they differ
_LOINC_REMAP: dict[str, tuple[str, str]] = {
    "38483-4": (_CREATININE_LOINC, _CREATININE_DISPLAY),
    "2947-0":  ("2951-2", "Sodium [Moles/volume] in Serum or Plasma"),
    "6298-4":  ("2823-3", "Potassium [Moles/volume] in Serum or Plasma"),
    "2069-3":  ("2075-0", "Chloride [Moles/volume] in Serum or Plasma"),
    "49765-1": ("17861-6", "Calcium [Mass/volume] in Serum or Plasma"),
    "2339-0":  ("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
}


class EpicEhiAdapter(Adapter):
    """Layer 1 adapter for Epic EHI Export → SQLite dump → bronze.

    Supports two flows:
      - "josh-fixture": copy Josh Mandel's redacted dump for parser validation
      - "rhett759": project Rhett759's Synthea data into Epic-EHI shape
                    (showcase patient, three artifact anchors)
    """

    name = "epic-ehi"

    def _corpus_sources_root(self) -> Path:
        """Resolve the corpus/_sources/ root from self.source_root.

        We support two source_root conventions:
          1. corpus/_sources/josh-epic-ehi/raw/  (preferred, from tests + stage-bronze)
             → parent.parent = corpus/_sources/
          2. corpus/_sources/epic-ehi/raw/  (CLI convention: src_name/raw)
             → parent.parent = corpus/_sources/

        Both cases give the same result: parent.parent.
        """
        return self.source_root.parent.parent

    def _synthea_bundle_path(self) -> Path:
        """Resolve the Rhett759 Synthea bundle path relative to corpus/_sources/."""
        return (
            self._corpus_sources_root()
            / "synthea" / "raw" / _RHETT759_BUNDLE
        )

    def _josh_dump_path(self) -> Path:
        """Resolve Josh's dump path, checking both naming conventions."""
        # Try the standard source_root first (set by instantiator)
        direct = self.source_root / "db.sqlite.dump"
        if direct.exists():
            return direct
        # Fall back: the CLI names it epic-ehi/raw/ but dump lives in josh-epic-ehi/raw/
        fallback = (
            self._corpus_sources_root()
            / "josh-epic-ehi" / "raw" / "db.sqlite.dump"
        )
        return fallback

    def list_patients(self) -> list[str]:
        """Return patient IDs whose source inputs exist on disk."""
        patients: list[str] = []
        if self._josh_dump_path().exists():
            patients.append("josh-fixture")
        if self._synthea_bundle_path().exists():
            patients.append("rhett759")
        return sorted(patients)

    def ingest(self, patient_id: str) -> SourceMetadata:
        """Read source, write bronze record. Idempotent."""
        if patient_id == "josh-fixture":
            return self._ingest_josh_fixture()
        elif patient_id == "rhett759":
            return self._ingest_rhett759_projection()
        raise ValueError(
            f"Unknown Epic EHI patient: {patient_id!r}. "
            "Valid IDs: 'josh-fixture', 'rhett759'."
        )

    # ------------------------------------------------------------------
    # Flow A — Josh fixture
    # ------------------------------------------------------------------

    def _ingest_josh_fixture(self) -> SourceMetadata:
        """Copy Josh Mandel's SQLite dump verbatim to bronze."""
        src = self._josh_dump_path()
        if not src.exists():
            raise FileNotFoundError(
                f"Josh Epic EHI dump not found: {src}. "
                "Run corpus acquisition first (see corpus/_sources/josh-epic-ehi/)."
            )
        dst_dir = self.bronze_dir("josh-fixture")
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "data.sqlite.dump"
        shutil.copyfile(src, dst)

        metadata = SourceMetadata(
            source=self.name,
            patient_id="josh-fixture",
            fetched_at=ACQUISITION_TS,
            document_type="epic-ehi-export-sqlite",
            license="MIT",
            consent="open",
            sha256=self.hash_file(dst),
            notes=(
                "Josh Mandel's redacted Epic EHI Export, restored as SQLite dump. "
                "Used as parser-shape fixture; NOT the showcase patient. Showcase "
                "patient projected into Epic-EHI shape under patient_id='rhett759'."
            ),
        )
        self.write_metadata("josh-fixture", metadata)
        return metadata

    # ------------------------------------------------------------------
    # Flow B — Rhett759 projection
    # ------------------------------------------------------------------

    def _ingest_rhett759_projection(self) -> SourceMetadata:
        """Project Rhett759's Synthea FHIR Bundle into Epic-EHI SQLite shape.

        This method reads Rhett759's Synthea Bundle and projects a carefully
        chosen subset into Epic-EHI table structures, writing a .sqlite.dump
        file that can be restored and queried exactly like Josh's real export.

        Tables produced (5 of Epic's 415):
          PAT_PATIENT    — one row (demographics)
          PAT_ENC        — top 10 most-recent encounters
          PROBLEM_LIST   — active conditions, ICD-10 coded only (drops SNOMED)
          ORDER_MED      — active medications; simvastatin swapped for atorvastatin
          ORDER_RESULTS  — top ~30 lab/vital observations (LOINC via LNC_DB_MAIN join)
          LNC_DB_MAIN    — LOINC lookup table for codes referenced by ORDER_RESULTS

        Deliberate projection artifacts (documented for Layer 3 harmonization):
          Artifact 1 anchor:
            ICD-10 codes only in PROBLEM_LIST (no SNOMED). Synthea uses SNOMED.
            Layer 3 merges via UMLS CUI in the handcrafted crosswalk.

          Artifact 2 anchor:
            Simvastatin (Synthea RxCUI 36567) replaced by atorvastatin
            (RxCUI 83367) with status='Discontinued' and end_date=2025-09-01.
            Both are HMG-CoA reductase inhibitors; Layer 3 flags the conflict
            and resolves via the statin class CUI.

          Artifact 5 anchor:
            Creatinine row (LOINC 2160-0, 1.4 mg/dL, 2025-09-12) included in
            ORDER_RESULTS, pointing to LNC_DB_MAIN for the LOINC code.
            The synthesized lab PDF (Stage 1.9) has the same value + date.
            Layer 3's observation dedup merges all three sources via LOINC.

        LOINC routing:
            Per the INSPECTION.md finding, Epic stores LOINC codes on
            LNC_DB_MAIN, not directly on ORDER_RESULTS.COMPON_LNC_ID.
            The projection emulates this: COMPON_LNC_ID is NULL on
            ORDER_RESULTS rows; lookup goes through LNC_DB_MAIN.COMPONENT_ID.
        """
        bundle_path = self._synthea_bundle_path()
        if not bundle_path.exists():
            raise FileNotFoundError(
                f"Rhett759 Synthea bundle not found: {bundle_path}. "
                "Run corpus acquisition first (see corpus/_sources/synthea/)."
            )

        bundle = json.loads(bundle_path.read_text())
        resources = [
            e["resource"]
            for e in bundle.get("entry", [])
            if "resource" in e
        ]

        # Build in-memory SQLite DB
        conn = sqlite3.connect(":memory:")
        try:
            self._create_tables(conn)
            self._insert_patient(conn, resources)
            self._insert_encounters(conn, resources)
            self._insert_conditions(conn, resources)
            self._insert_medications(conn, resources)
            obs_loincs = self._insert_observations(conn, resources)
            self._insert_lnc_db_main(conn, obs_loincs)
            conn.commit()

            # Dump to SQL text (iterdump produces a reproducible, sorted output)
            dump_lines = list(conn.iterdump())
            dump_text = "\n".join(dump_lines) + "\n"
        finally:
            conn.close()

        dst_dir = self.bronze_dir("rhett759")
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "data.sqlite.dump"
        dst.write_text(dump_text, encoding="utf-8")

        metadata = SourceMetadata(
            source=self.name,
            patient_id="rhett759",
            fetched_at=ACQUISITION_TS,
            document_type="epic-ehi-export-sqlite",
            license="MIT",
            consent="constructed",
            sha256=self.hash_file(dst),
            notes=(
                "Synthea Rhett759 data projected into Epic-EHI SQLite shape. "
                "Tables: PAT_PATIENT, PAT_ENC, PROBLEM_LIST, ORDER_MED, "
                "ORDER_RESULTS, LNC_DB_MAIN. "
                "Artifact 1: ICD-10-only conditions (no SNOMED). "
                "Artifact 2: simvastatin → atorvastatin discontinued 2025-09. "
                "Artifact 5: creatinine 1.4 mg/dL 2025-09-12 (LOINC 2160-0 via LNC_DB_MAIN). "
                "LOINC not on ORDER_RESULTS.COMPON_LNC_ID — join via LNC_DB_MAIN per INSPECTION finding."
            ),
        )
        self.write_metadata("rhett759", metadata)
        return metadata

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Create the Epic-shape tables in the in-memory SQLite DB."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS PAT_PATIENT (
                PAT_ID          TEXT PRIMARY KEY,
                PAT_MRN_ID      TEXT,
                PAT_NAME        TEXT,
                BIRTH_DATE      TEXT,
                SEX_C_NAME      TEXT,
                ETHNIC_GROUP_C_NAME TEXT
            );

            CREATE TABLE IF NOT EXISTS PAT_ENC (
                PAT_ENC_CSN_ID  TEXT PRIMARY KEY,
                PAT_ID          TEXT,
                CONTACT_DATE    TEXT,
                ENC_TYPE_C_NAME TEXT,
                VISIT_PROV_ID   TEXT,
                APPT_STATUS_C_NAME TEXT
            );

            CREATE TABLE IF NOT EXISTS PROBLEM_LIST (
                PROBLEM_LIST_ID TEXT PRIMARY KEY,
                PAT_ID          TEXT,
                DX_ID           TEXT,
                DX_NAME         TEXT,
                ICD10_CODE      TEXT,
                ONSET_DATE      TEXT,
                PROBLEM_STATUS_C_NAME TEXT
            );

            CREATE TABLE IF NOT EXISTS ORDER_MED (
                ORDER_MED_ID    TEXT PRIMARY KEY,
                PAT_ID          TEXT,
                PAT_ENC_CSN_ID  TEXT,
                MEDICATION_ID   TEXT,
                MED_DISPLAY     TEXT,
                RXNORM_CODE     TEXT,
                START_DATE      TEXT,
                END_DATE        TEXT,
                ORDER_STATUS_C_NAME TEXT,
                SIG_TEXT        TEXT
            );

            CREATE TABLE IF NOT EXISTS ORDER_RESULTS (
                RESULT_ID       TEXT PRIMARY KEY,
                PAT_ID          TEXT,
                PAT_ENC_CSN_ID  TEXT,
                COMPONENT_ID    TEXT,
                COMPON_LNC_ID   TEXT,
                RESULT_DATE     TEXT,
                ORD_VALUE       TEXT,
                REFERENCE_UNIT  TEXT,
                RESULT_FLAG_C_NAME TEXT
            );

            CREATE TABLE IF NOT EXISTS LNC_DB_MAIN (
                COMPONENT_ID    TEXT PRIMARY KEY,
                LNC_CODE        TEXT,
                LNC_DISPLAY     TEXT,
                COMPONENT_NAME  TEXT,
                UNIT            TEXT
            );
        """)

    # ------------------------------------------------------------------
    # Row insertion helpers
    # ------------------------------------------------------------------

    def _insert_patient(
        self, conn: sqlite3.Connection, resources: list[dict]
    ) -> None:
        """Insert one PAT_PATIENT row for Rhett759."""
        patient = next(
            (r for r in resources if r["resourceType"] == "Patient"), None
        )
        if patient is None:
            raise ValueError("No Patient resource found in Synthea bundle.")

        name_obj = patient.get("name", [{}])[0]
        family = name_obj.get("family", "Unknown")
        given = (name_obj.get("given") or ["Unknown"])[0]
        full_name = f"{family.upper()},{given}"

        conn.execute(
            """
            INSERT OR REPLACE INTO PAT_PATIENT
            (PAT_ID, PAT_MRN_ID, PAT_NAME, BIRTH_DATE, SEX_C_NAME, ETHNIC_GROUP_C_NAME)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "RHETT759",
                "SYN-RHETT759",
                full_name,
                patient.get("birthDate", ""),
                patient.get("gender", "").capitalize(),
                "",
            ),
        )

    def _insert_encounters(
        self, conn: sqlite3.Connection, resources: list[dict]
    ) -> None:
        """Insert top 10 most-recent encounters into PAT_ENC."""
        encounters = [r for r in resources if r["resourceType"] == "Encounter"]
        encounters.sort(
            key=lambda x: x.get("period", {}).get("start", ""), reverse=True
        )

        for i, enc in enumerate(encounters[:10]):
            period = enc.get("period", {})
            contact_date = (period.get("start") or "")[:10]
            enc_type = (
                enc.get("type", [{}])[0]
                .get("coding", [{}])[0]
                .get("display", "Office Visit")
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO PAT_ENC
                (PAT_ENC_CSN_ID, PAT_ID, CONTACT_DATE, ENC_TYPE_C_NAME,
                 VISIT_PROV_ID, APPT_STATUS_C_NAME)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"ENC{i + 1:06d}",
                    "RHETT759",
                    contact_date,
                    enc_type,
                    "PROV001",
                    "Completed",
                ),
            )

    def _insert_conditions(
        self, conn: sqlite3.Connection, resources: list[dict]
    ) -> None:
        """Insert active conditions into PROBLEM_LIST using ICD-10 codes only.

        Artifact 1 anchor: SNOMED codes from Synthea are dropped. Only ICD-10
        codes (from the hand-curated crosswalk) are stored in PROBLEM_LIST.
        This creates the cross-source coding divergence that Layer 3 resolves.
        """
        conditions = [
            r
            for r in resources
            if r["resourceType"] == "Condition"
            and r.get("clinicalStatus", {})
            .get("coding", [{}])[0]
            .get("code")
            == "active"
        ]

        for i, cond in enumerate(conditions):
            codings = cond.get("code", {}).get("coding", [])
            snomed_code = None
            display = cond.get("code", {}).get("text", "Unknown condition")

            for coding in codings:
                sys = coding.get("system", "")
                if "snomed" in sys.lower():
                    snomed_code = coding.get("code")
                    display = coding.get("display", display)
                    break

            # Resolve ICD-10 via crosswalk
            icd10_code = ""
            icd10_display = display
            if snomed_code:
                xwalk_row = lookup_cross(_SNOMED_SYSTEM, snomed_code)
                if xwalk_row and xwalk_row.get("icd_10_cm"):
                    icd10_code = xwalk_row["icd_10_cm"]["code"]
                    icd10_display = xwalk_row["icd_10_cm"]["display"]

            onset = cond.get("onsetDateTime", "")[:10] if cond.get("onsetDateTime") else ""

            conn.execute(
                """
                INSERT OR REPLACE INTO PROBLEM_LIST
                (PROBLEM_LIST_ID, PAT_ID, DX_ID, DX_NAME, ICD10_CODE,
                 ONSET_DATE, PROBLEM_STATUS_C_NAME)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"PROB{i + 1:06d}",
                    "RHETT759",
                    f"DX{i + 1:04d}",
                    icd10_display or display,  # ICD-10 display name preferred
                    icd10_code,
                    onset,
                    "Active",
                ),
            )

    def _insert_medications(
        self, conn: sqlite3.Connection, resources: list[dict]
    ) -> None:
        """Insert medications into ORDER_MED with the Artifact 2 swap.

        Artifact 2 anchor: Simvastatin (RxCUI 36567) from Synthea is replaced
        by atorvastatin (RxCUI 83367) with status='Discontinued' and
        end_date='2025-09-01'. Both are statins; Layer 3 flags this conflict
        and groups them via the statin class CUI (C0360714).
        """
        med_requests = [r for r in resources if r["resourceType"] == "MedicationRequest"]

        # Prefer active medications, then stopped, then all others
        active_meds = [m for m in med_requests if m.get("status") == "active"]
        stopped_meds = [m for m in med_requests if m.get("status") == "stopped"]
        other_meds = [m for m in med_requests if m.get("status") not in ("active", "stopped")]

        # Take top 8 active + 2 stopped for a realistic medication list
        selected = (active_meds[:8] + stopped_meds[:2] + other_meds[:0])[:10]

        inserted_med_ids: set[str] = set()

        for i, med in enumerate(selected):
            code_obj = med.get("medicationCodeableConcept", {})
            codings = code_obj.get("coding", [])
            rxnorm_code = ""
            display = code_obj.get("text", "Unknown medication")

            for coding in codings:
                sys = coding.get("system", "")
                if "rxnorm" in sys.lower():
                    rxnorm_code = coding.get("code", "")
                    display = coding.get("display", display)
                    break

            # Artifact 2: swap simvastatin → atorvastatin discontinued Q3 2025
            status = med.get("status", "active").capitalize()
            end_date = ""
            if rxnorm_code == "316672" or "simvastatin" in display.lower() or rxnorm_code == "36567":
                rxnorm_code = _ATORVASTATIN_RXCUI
                display = _ATORVASTATIN_DISPLAY
                status = "Discontinued"
                end_date = _ATORVASTATIN_DISCONTINUED

            # Skip duplicates (same RxNorm code already inserted)
            if rxnorm_code and rxnorm_code in inserted_med_ids:
                continue
            if rxnorm_code:
                inserted_med_ids.add(rxnorm_code)

            date_written = med.get("authoredOn", "")[:10] if med.get("authoredOn") else ""

            conn.execute(
                """
                INSERT OR REPLACE INTO ORDER_MED
                (ORDER_MED_ID, PAT_ID, PAT_ENC_CSN_ID, MEDICATION_ID, MED_DISPLAY,
                 RXNORM_CODE, START_DATE, END_DATE, ORDER_STATUS_C_NAME, SIG_TEXT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"MED{i + 1:06d}",
                    "RHETT759",
                    "ENC000001",
                    f"MEDID{i + 1:04d}",
                    display,
                    rxnorm_code,
                    date_written,
                    end_date,
                    status,
                    "",
                ),
            )

    def _insert_observations(
        self, conn: sqlite3.Connection, resources: list[dict]
    ) -> dict[str, tuple[str, str, str | None]]:
        """Insert showcase observations into ORDER_RESULTS.

        Artifact 5 anchor: A creatinine row (LOINC 2160-0, 1.4 mg/dL,
        2025-09-12) is always inserted regardless of what Synthea has.
        This matches the synthesized lab PDF's creatinine row exactly.

        LOINC routing: COMPON_LNC_ID is left NULL on ORDER_RESULTS rows,
        emulating the Epic export pattern. LOINC codes live in LNC_DB_MAIN
        (see _insert_lnc_db_main). A join is required to resolve LOINC.

        Returns:
            obs_loincs: dict mapping COMPONENT_ID → (loinc_code, loinc_display, unit)
                        Used by _insert_lnc_db_main to populate the lookup table.
        """
        obs_all = [r for r in resources if r["resourceType"] == "Observation"]

        # Filter to showcase LOINC subset
        showcase_obs: list[dict] = []
        for obs in obs_all:
            codings = obs.get("code", {}).get("coding", [])
            for coding in codings:
                if coding.get("code") in _SHOWCASE_LOINCS:
                    showcase_obs.append(obs)
                    break

        # Sort by date descending, take latest occurrence of each LOINC
        showcase_obs.sort(
            key=lambda x: x.get("effectiveDateTime", ""), reverse=True
        )
        seen_loincs: set[str] = set()
        deduped: list[dict] = []
        for obs in showcase_obs:
            codings = obs.get("code", {}).get("coding", [])
            loinc = next(
                (c.get("code") for c in codings if c.get("code") in _SHOWCASE_LOINCS),
                None,
            )
            if loinc and loinc not in seen_loincs:
                seen_loincs.add(loinc)
                deduped.append(obs)

        # Cap at 30 rows (project brief)
        deduped = deduped[:30]

        # obs_loincs: COMPONENT_ID → (loinc_code, loinc_display, unit)
        obs_loincs: dict[str, tuple[str, str, str | None]] = {}

        # Artifact 5: insert the anchor creatinine row first (fixed values)
        creatinine_component_id = "COMP_CREATININE"
        canonical_loinc, canonical_display = _LOINC_REMAP.get(
            "38483-4", (_CREATININE_LOINC, _CREATININE_DISPLAY)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO ORDER_RESULTS
            (RESULT_ID, PAT_ID, PAT_ENC_CSN_ID, COMPONENT_ID, COMPON_LNC_ID,
             RESULT_DATE, ORD_VALUE, REFERENCE_UNIT, RESULT_FLAG_C_NAME)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RES_CREATININE_ARTIFACT5",
                "RHETT759",
                "ENC000001",
                creatinine_component_id,
                None,  # NULL — per INSPECTION finding; join via LNC_DB_MAIN
                _CREATININE_DATE,
                str(_CREATININE_VALUE),
                _CREATININE_UNIT,
                "",
            ),
        )
        obs_loincs[creatinine_component_id] = (
            canonical_loinc,
            canonical_display,
            _CREATININE_UNIT,
        )

        # Insert remaining showcase observations
        for i, obs in enumerate(deduped):
            codings = obs.get("code", {}).get("coding", [])
            raw_loinc = next(
                (c.get("code") for c in codings if c.get("code") in _SHOWCASE_LOINCS),
                None,
            )
            if not raw_loinc:
                continue

            # Skip creatinine — already inserted as Artifact 5
            if raw_loinc == "38483-4":
                continue

            # Remap to canonical LOINC if needed
            if raw_loinc in _LOINC_REMAP:
                loinc_code, loinc_display = _LOINC_REMAP[raw_loinc]
            else:
                loinc_code = raw_loinc
                loinc_display = (
                    next(
                        (c.get("display", "") for c in codings if c.get("code") == raw_loinc),
                        "",
                    )
                )

            # Extract value (handle component obs like BP)
            value_str = ""
            unit = ""
            val_q = obs.get("valueQuantity", {})
            if val_q:
                value_str = str(round(val_q.get("value", 0), 4))
                unit = val_q.get("unit", "")
            elif obs.get("component"):
                # BP: take systolic as primary value
                for comp in obs.get("component", []):
                    comp_code = comp.get("code", {}).get("coding", [{}])[0].get("code", "")
                    if comp_code == "8480-6":
                        vq = comp.get("valueQuantity", {})
                        value_str = str(round(vq.get("value", 0), 2))
                        unit = vq.get("unit", "mm[Hg]")
                        break

            eff_date = (obs.get("effectiveDateTime") or "")[:10]
            component_id = f"COMP_{loinc_code.replace('-', '_')}"

            # Skip if we already have a row for this component
            if component_id in obs_loincs:
                continue

            conn.execute(
                """
                INSERT OR REPLACE INTO ORDER_RESULTS
                (RESULT_ID, PAT_ID, PAT_ENC_CSN_ID, COMPONENT_ID, COMPON_LNC_ID,
                 RESULT_DATE, ORD_VALUE, REFERENCE_UNIT, RESULT_FLAG_C_NAME)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"RES{i + 1:06d}",
                    "RHETT759",
                    "ENC000001",
                    component_id,
                    None,  # NULL — join via LNC_DB_MAIN
                    eff_date,
                    value_str,
                    unit,
                    "",
                ),
            )
            obs_loincs[component_id] = (loinc_code, loinc_display, unit or None)

        return obs_loincs

    def _insert_lnc_db_main(
        self,
        conn: sqlite3.Connection,
        obs_loincs: dict[str, tuple[str, str, str | None]],
    ) -> None:
        """Populate LNC_DB_MAIN with the LOINC codes referenced by ORDER_RESULTS.

        Per the INSPECTION.md finding, Epic stores LOINC codes in LNC_DB_MAIN,
        not directly on ORDER_RESULTS.COMPON_LNC_ID.  The join path is:
            ORDER_RESULTS.COMPONENT_ID → LNC_DB_MAIN.COMPONENT_ID → LNC_CODE

        We only insert the LOINC codes that appear in our ORDER_RESULTS rows
        (minimal subset — not the full 100k-row LOINC table).
        """
        for component_id, (loinc_code, loinc_display, unit) in obs_loincs.items():
            conn.execute(
                """
                INSERT OR REPLACE INTO LNC_DB_MAIN
                (COMPONENT_ID, LNC_CODE, LNC_DISPLAY, COMPONENT_NAME, UNIT)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    component_id,
                    loinc_code,
                    loinc_display,
                    loinc_display,
                    unit or "",
                ),
            )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, patient_id: str) -> list[str]:
        """Check that the bronze record exists and has the expected structure.

        For josh-fixture: checks the dump file exists and can be restored.
        For rhett759: additionally verifies the 6 required tables are present.
        """
        errors: list[str] = []
        dst_dir = self.bronze_dir(patient_id)
        dump_path = dst_dir / "data.sqlite.dump"
        metadata_path = dst_dir / "metadata.json"

        # 1. dump file exists
        if not dump_path.exists():
            errors.append(f"data.sqlite.dump missing at {dump_path}")
            return errors

        # 2. dump can be restored to a SQLite DB
        try:
            conn = sqlite3.connect(":memory:")
            dump_sql = dump_path.read_text(encoding="utf-8")
            conn.executescript(dump_sql)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()
        except Exception as exc:
            errors.append(f"data.sqlite.dump cannot be restored: {exc}")
            return errors

        # 3. for rhett759, check required tables
        if patient_id == "rhett759":
            required_tables = {
                "PAT_PATIENT",
                "PAT_ENC",
                "PROBLEM_LIST",
                "ORDER_MED",
                "ORDER_RESULTS",
                "LNC_DB_MAIN",
            }
            missing = required_tables - tables
            if missing:
                errors.append(
                    f"rhett759 dump missing tables: {sorted(missing)}"
                )

        # 4. metadata.json exists and is valid
        if not metadata_path.exists():
            errors.append(f"metadata.json missing at {metadata_path}")
        else:
            try:
                raw_meta = json.loads(metadata_path.read_text())
            except json.JSONDecodeError as exc:
                errors.append(f"metadata.json is not valid JSON: {exc}")
                raw_meta = {}
            required_fields = {
                "source", "patient_id", "fetched_at", "license", "consent", "sha256"
            }
            missing_fields = required_fields - set(raw_meta.keys())
            if missing_fields:
                errors.append(
                    f"metadata.json missing fields: {sorted(missing_fields)}"
                )

        return errors
