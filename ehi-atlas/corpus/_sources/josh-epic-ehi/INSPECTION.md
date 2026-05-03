# INSPECTION.md — Josh Mandel's Epic EHI SQLite Dump

**Inspected:** 2026-04-29 by sub-agent (task 1.6)  
**Source dump:** `raw/db.sqlite.dump` (1.6 MB on disk, expands to 4.5 MB SQLite)  
**SHA pinned:** `188d93814515636afd9f027f2d5efebfd00260c7`

---

## 1. Summary Stats

| Metric | Value |
|--------|-------|
| Dump file size | 1.6 MB (SQL text) |
| SQLite DB size | 4.5 MB (restored) |
| Total tables | 415 |
| Total rows (all tables) | 7,294 |
| Tables with zero rows | 0 (all populated) |
| Distinct patients | 1 (Josh Mandel — Z7004242) |
| Encounter date range | 2018-08-09 through 2024-11-07 |
| Schemas in `raw/schemas/` | 6,631 JSON files |
| Processed JSON in `raw/json/` | 414 files |
| TSV tables in `raw/tsv/` | 552 files |

This is a single-patient export. Every row in every table belongs to one patient (PAT_ID = `Z7004242`).

---

## 2. Top 10 Tables

### 1. MSG_TXT — 435 rows
**Columns:** `MESSAGE_ID TEXT (PK), LINE INTEGER (PK), MSG_TXT TEXT`

Multi-line message body table. Each row is one line of a patient-facing or provider-facing inbox message.

```
MESSAGE_ID   LINE  MSG_TXT
19025649     1     Appointment Request From: Joshua C Mandel
19025649     3     With Provider: Puneet S Dhillon, MD [Assoc Physicians Internal Medicine]
```

**FHIR mapping:** `Communication` resource (body text component). Also feeds `DocumentReference` for appointment letters.

---

### 2. MYC_MESG_RTF_TEXT — 337 rows
**Columns:** `MESSAGE_ID TEXT (PK), LINE INTEGER (PK), RTF_TXT TEXT`

RTF-encoded body of MyChart inbox messages (parallel to MSG_TXT but richer formatting). Referencing `MYC_MESG.MESSAGE_ID`.

**FHIR mapping:** `Communication` (content as base64 attachment).

---

### 3. IP_FLOWSHEET_ROWS — 241 rows
**Columns:** `INPATIENT_DATA_ID TEXT (PK), LINE INTEGER (PK), FLO_MEAS_ID TEXT, FLO_MEAS_ID_DISP_NAME TEXT, IP_LDA_ID TEXT, ROW_VARIANCE_C_NAME TEXT`

Defines *which* flowsheet rows (vital signs, assessments, screening questions) apply to an inpatient data record. The display names include Depression PHQ-2 items, domestic violence screening, and travel history.

```
FLO_MEAS_ID  FLO_MEAS_ID_DISP_NAME
8693         Have you ever been in a relationship where you've been hurt, threatened, or abused?
4671         Have you felt little interest or pleasure in doing things over the past 2 weeks? (RETIRED)
```

**FHIR mapping:** `Observation` (survey instrument items). Pairs with IP_FLWSHT_MEAS for values.

---

### 4. IP_FLWSHT_MEAS — 192 rows
**Columns:** `FSD_ID TEXT (PK), LINE INTEGER (PK), OCCURANCE INTEGER, RECORDED_TIME TEXT, ENTRY_TIME TEXT, TAKEN_USER_ID TEXT, TAKEN_USER_ID_NAME TEXT, FLT_ID TEXT, FLT_ID_DISPLAY_NAME TEXT, ABNORMAL_C_NAME TEXT` (24 total columns)

Actual flowsheet measurement values (vital signs, nursing assessments). `FLT_ID_DISPLAY_NAME` identifies the flowsheet template (e.g., "Travel"). Values not stored in this table directly — they live in `IP_FLO_GP_DATA` (90 rows) and `IP_DATA_STORE`.

**FHIR mapping:** `Observation` (component/value from linked tables).

---

### 5. ABN_FOLLOW_UP — 168 rows
**Columns:** `NOTE_CSN_ID NUMERIC (PK), NOTE_ID TEXT, CONTACT_DATE_REAL NUMERIC, CONTACT_DATE TEXT, CONTACT_NUM TEXT, NOTE_STATUS_C_NAME TEXT, AUTHOR_USER_ID TEXT, AUTHOR_PRVD_TYPE_C_NAME TEXT, ENTRY_INSTANT_DTTM TEXT` (20 total columns)

Abnormal result follow-up notes — one record per note contact. Tracks cosign requirements, author type, note status, and document type. Most `NOTE_STATUS_C_NAME` values are empty in this export.

**FHIR mapping:** `DocumentReference` (note metadata). Body text in `HNO_PLAIN_TEXT`.

---

### 6. V_EHI_HNO_LINKED_PATS / HNO_INFO — 152 rows each
`HNO_INFO` schema:

**Columns:** `NOTE_ID TEXT (PK), NOTE_TYPE_NOADD_C_NAME TEXT, PAT_ENC_CSN_ID NUMERIC, IP_NOTE_TYPE_C_NAME TEXT, CREATE_INSTANT_DTTM TEXT, CURRENT_AUTHOR_ID TEXT, CURRENT_AUTHOR_ID_NAME TEXT, HNO_RECORD_TYPE_C_NAME TEXT, ACTIVE_C_NAME TEXT` (20+ columns)

Clinical note header table. Each `NOTE_ID` is one note document; most fields were empty in the sample (redaction or optional fields). `V_EHI_HNO_LINKED_PATS` is a view (still materialized in the dump) that links notes to patient encounters.

**FHIR mapping:** `DocumentReference` + `Composition` (clinical notes).

---

### 7. REFERRAL_HIST — 130 rows
**Columns:** `REFERRAL_ID NUMERIC (PK), LINE INTEGER (PK), CHANGE_DATE TEXT, CHANGE_TYPE_C_NAME TEXT, NEW_RFL_STATUS_C_NAME TEXT, PREVIOUS_VALUE TEXT, AUTH_HX_NOTE_ID TEXT`

Audit history for referrals. Events include "Create Referral", "Refreshed Coverages", "Change Coverage". One referral can have many history lines.

**FHIR mapping:** `ServiceRequest` (+ `Task` for workflow state changes).

---

### 8. SERVICE_BENEFITS — 126 rows
**Columns:** `RECORD_ID NUMERIC (PK), LINE INTEGER (PK), CVG_FOR_SVC_TYPE_ID NUMERIC, CVG_SVC_TYPE_ID NUMERIC, CVG_SVC_TYPE_ID_SERVICE_TYPE_NAME TEXT, COPAY_AMOUNT NUMERIC, DEDUCTIBLE_AMOUNT NUMERIC, COINS_PERCENT NUMERIC, FAMILY_TIER_SVC_C_NAME TEXT, NET_LVL_SVC_C_NAME TEXT, RTE_COPAY_AMOUNT NUMERIC`

Insurance benefit details per service type (copay, deductible, coinsurance percentages). In/Out-of-network split.

**FHIR mapping:** `Coverage` / `CoverageEligibilityResponse` (benefit components).

---

### 9. IB_MESSAGE_THREAD — 120 rows
**Columns:** `THREAD_ID NUMERIC (PK), LINE INTEGER (PK), MESSAGE_ID TEXT, ROUTING_COMMENT TEXT`

Inbox message thread membership — links `THREAD_ID` to the individual `MESSAGE_ID` records that form the conversation.

**FHIR mapping:** `Communication` (thread/in-reply-to structure).

---

### 10. PAT_ENC — 111 rows
**Columns:** `PAT_ENC_CSN_ID NUMERIC (PK), PAT_ID TEXT, PAT_ENC_DATE_REAL NUMERIC, CONTACT_DATE TEXT, PCP_PROV_ID TEXT, VISIT_PROV_ID TEXT, VISIT_PROV_TITLE_NAME TEXT, DEPARTMENT_ID NUMERIC, APPT_STATUS_C_NAME TEXT, HOSP_ADMSN_TYPE_C_NAME TEXT, HOSP_ADMSN_TIME TEXT, HOSP_DISCHRG_TIME TEXT, BMI NUMERIC, BSA NUMERIC, INPATIENT_DATA_ID TEXT` (97 total columns)

The central encounter table. Encounter types span outpatient office visits, inpatient (Elective), telephone, and canceled/scheduled appointments. 111 total encounters from 2018 to 2024, all for a single patient. 97 columns — extremely wide, including billing, referral, copay, and messaging metadata.

```
PAT_ENC_CSN_ID  CONTACT_DATE         APPT_STATUS_C_NAME
720803470       2018-08-09           Completed
724619887       2018-08-09           (blank)
724623985       2018-08-09           (blank)
```

**FHIR mapping:** `Encounter` (primary clinical entity).

---

## 3. Logical-Table Merge Heuristics (from `02-merge-related-tables.ts`)

Josh's script runs three passes to cluster physical tables into logical groups:

### Pass 1: `same-logical-table` merging
Two tables are considered the same logical table if:
- Their normalized names match after stripping underscores and digits (`normalizeTableName`), **OR**
- They share identical primary key structure, identical row count, and the PK does not look like a LINE-based composite (unless there are 3+ distinct values).

When a merge set is identified, the table chosen as the canonical parent is ranked by:
1. Whether it appears in `preferredParents = ["ORDER_PROC", "ORD_DOSING_PARAMS"]`
2. Most common first-segment prefix (most "sibling" tables sharing that prefix)
3. Fewest PK segments
4. Shortest name (as tiebreaker)

Columns from the merged child are appended to the parent schema with a `mergedFrom` tag. Conflicting column values throw an error and the merge is aborted for that pair.

### Pass 2: Parent/child relationship (`has-child-table`)
A table B is treated as a child of A if:
- A's PK is a strict prefix of B's PK (same types, same order), AND
- 90%+ of B's rows have a matching parent row in A (fudge factor: 0.1).

Hardcoded overrides bypass the prefix check:
```typescript
const hardcoded = {
  "ORDER_RPTD_SIG_TEXT": ["ORDER_RPTD_SIG_HX"],
  "ORDER_SUMMARY": ["ORDER_PROC", "ORDER_MED"],
  "ORDER_STATUS": ["ORDER_PROC", "ORDER_MED"],
  "ORDER_PENDING": ["ORDER_PROC", "ORDER_MED"]
}
```

Best parent selection favors: preferred parents → fewest PK levels above child → fewest name segments → longest common name prefix.

### Pass 3: Foreign-key discovery
Columns matching `/(_I|_ID|_GUID|_PTR|_USER|_SOURCE|_LOC|HX)$/` are tested as foreign keys to single-PK tables where 90%+ of values resolve. When multiple candidate target tables exist, the one with the fewest name segments and longest common prefix with the source table wins.

**Adapter implication:** The lift for `epic_ehi.py` is to replicate these three passes in Python, mapping (tableName → merged schema + FK graph), then use that graph to drive FHIR resource assembly.

---

## 4. Epic Table → Likely FHIR Resource Mapping

| Epic Table(s) | FHIR Resource | Key Join |
|---|---|---|
| `PAT_ENC` | `Encounter` | `PAT_ENC_CSN_ID` |
| `PATIENT` | `Patient` | `PAT_ID` |
| `PROBLEM_LIST`, `CLARITY_EDG` | `Condition` | `DX_ID → DX_NAME` |
| `ORDER_MED`, `CLARITY_MEDICATION` | `MedicationRequest` | `MEDICATION_ID` |
| `ORDER_PROC`, `ORDER_RESULTS`, `CLARITY_COMPONENT` | `ServiceRequest` + `Observation` | `ORDER_PROC_ID`, `COMPONENT_ID` |
| `PAT_ALLERGIES`, `ALLERGY`, `ALLERGY_REACTIONS` | `AllergyIntolerance` | `ALLERGY_RECORD_ID` |
| `CLARITY_IMMUNZATN`, `IMM_ADMIN` | `Immunization` | `IMMUNZATN_ID` |
| `REFERRAL`, `REFERRAL_HIST` | `ServiceRequest` (referral) | `REFERRAL_ID` |
| `HNO_INFO`, `HNO_PLAIN_TEXT`, `ABN_FOLLOW_UP` | `DocumentReference` / `Composition` | `NOTE_ID / NOTE_CSN_ID` |
| `MSG_TXT`, `MYC_MESG`, `IB_MESSAGE_THREAD` | `Communication` | `MESSAGE_ID / THREAD_ID` |
| `SOCIAL_HX` | `Observation` (social history) | `PAT_ENC_CSN_ID` |
| `IP_FLOWSHEET_ROWS`, `IP_FLWSHT_MEAS` | `Observation` (flowsheet/vitals) | `INPATIENT_DATA_ID / FSD_ID` |
| `COVERAGE`, `SERVICE_BENEFITS` | `Coverage` / `CoverageEligibilityResponse` | `RECORD_ID` |
| `LNC_DB_MAIN` | Code system reference (LOINC) | `COMPONENT_ID` in ORDER_RESULTS |
| `CLARITY_EDG` | Code system reference (ICD-10 diagnoses) | `DX_ID` |

Note: `ORDER_RESULTS` has a `COMPON_LNC_ID` column but all 27 rows in this export have it empty — LOINC codes are on `LNC_DB_MAIN` and must be joined via `COMPONENT_ID`.

---

## 5. PHI Redaction Observations

**Redaction mechanism:** `00-redact.js` runs regex-replace over every TSV before ingestion. The redaction terms are loaded from `.redaction-terms.json` (gitignored — not in the public repo). Redaction is term-based text substitution using a fuzzy character-gap regex (allows up to 5 separator chars between letters).

**What was redacted:**
- `PATIENT.ZIP` → `"REDACTED"` (literal string)
- `PATIENT.SSN` → `"REDACTED"`
- Address fields within `HNO_PLAIN_TEXT` note text → `"REDACTED"` (inline)

**What was NOT redacted (visible PHI):**
- `PATIENT.PAT_NAME` = `"MANDEL,JOSHUA C"` — full name visible
- `PATIENT.HOME_PHONE` = `"617-894-1015"` — phone number visible
- `PATIENT.EMAIL_ADDRESS` = `"jmandel@alum.mit.edu"` — email visible
- `PATIENT.BIRTH_DATE` = `"1982-10-26"` — DOB visible
- `PATIENT.PAT_MRN_ID` = `"APL324672"` — MRN visible
- `PAT_ID` = `"Z7004242"` throughout all tables
- Provider names throughout (`DHILLON, PUNEET S`, `RAMMELKAMP, ZOE L`, etc.)
- Pharmacy names and addresses in `ORDER_MED` (Madison, WI Walgreens, CVS locations)
- `MSG_TXT` contains Josh's full name in appointment request messages
- `HNO_PLAIN_TEXT` contains provider names, practice name ("Assoc Physicians"), and the word "REDACTED" appears inline for address fields

**Assessment:** This is Josh's own data published intentionally. He redacted address and SSN but left name, phone, email, DOB, and MRN. The data is public by intent. For our adapter, we should treat all `_NAME` columns and the `PATIENT` table as PHI-bearing and apply our own privacy gate before any downstream emission.

---

## 6. Gotchas / Surprises for the Adapter Author (task 2.3)

1. **Single-patient export.** All 7,294 rows are one person. The adapter must not assume multi-patient exports — real deployments will have exactly one `PAT_ID` per export file. Index by `PAT_ID` but don't depend on it for uniqueness across files.

2. **97-column PAT_ENC.** The encounter table is massively wide — billing, clinical, scheduling, copay, referral, and messaging metadata all collapsed into one row. The FHIR adapter will need to selectively project columns; not everything maps to `Encounter`.

3. **No LOINC codes on ORDER_RESULTS rows.** `COMPON_LNC_ID` column exists but is empty in this export. LOINC codes must be joined through `LNC_DB_MAIN` via `COMPONENT_ID`. Adapter must not assume the shortcut column is populated.

4. **PROBLEM_LIST uses internal `DX_ID`, not ICD codes.** `DX_ID` is an Epic internal identifier. To get a diagnostic code, join to `CLARITY_EDG.DX_ID` for the display name; actual ICD-10 codes were not present in this export's `CLARITY_EDG` table (only name). The adapter will need a separate crosswalk or the `PAT_ENC_DX` + diagnosis tables for coded values.

5. **V_ prefix tables are views, materialized in the dump.** `V_EHI_HNO_LINKED_PATS` (152 rows) is treated as a regular table in the SQLite dump. The adapter should detect and skip view-origin tables (prefixed `V_`) or use them as denormalized shortcuts rather than source of truth.

6. **Note text is multi-line with LINE keys.** `HNO_PLAIN_TEXT`, `MSG_TXT`, `MYC_MESG_RTF_TEXT` all use `(parent_id, LINE)` composite PKs. Reassembling a note requires sorting by LINE and concatenating. RTF content in `MYC_MESG_RTF_TEXT` needs stripping before use.

7. **ABN_FOLLOW_UP is the densest table but semantically note-metadata, not clinical content.** Its 168 rows are note contact records tied to the HNO system. Don't confuse row count with clinical richness — the actual text is in HNO_PLAIN_TEXT (120 rows of note lines, ~15-20 actual notes).

8. **Merge heuristics have a 10% fudge factor.** Josh's `isValidPrefixRelationship` allows up to 10% orphaned child rows. The Python adapter should honor this tolerance or risk failing on slightly inconsistent real-world exports.

9. **IP_FLWSHT_MEAS values are in a separate table.** Flowsheet measurements reference `IP_FLO_GP_DATA` and `IP_DATA_STORE` for actual numeric/text values — the measurement table itself only carries metadata (time, user, template). A three-table join is required for vital sign values.

10. **Messaging tables (MSG_TXT, MYC_MESG, IB_MESSAGE_THREAD) are the most populated.** 435 + 337 + 120 = 892 rows just for messaging. This is clinically important (patient-provider communication, medication renewal requests, referral coordination) but not currently mapped in most EHI adapters. These should map to `Communication` resources and are a differentiator worth implementing.
