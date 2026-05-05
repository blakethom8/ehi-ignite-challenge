# Format-Agnostic Health Record Ingestion
## Product Definition, Vision & Specs

*Created: March 29, 2026*

---

## The Problem

The EHI Ignite Challenge is built around FHIR — but the real world is not.

A patient's health history doesn't arrive in a clean FHIR bundle. It arrives as:

- **PDFs** — discharge summaries, operative reports, referral letters, lab printouts
- **Scanned paper records** — faxed records, old charts from legacy systems
- **Free-text clinical notes** — typed narrative from office visits
- **HL7 v2 messages** — the old standard, still dominant in many hospitals
- **CDA / CCD documents** — another legacy format used in transitions of care
- **CSV / Excel exports** — some EHRs still export this way
- **Proprietary EHR exports** — Epic, Cerner, Athena, eClinicalWorks all export slightly differently
- **FHIR R4** — the ideal, but not universal yet

Any tool that only accepts FHIR will fail in real clinical deployment. The format-agnostic ingestion layer is the bridge between the messy real world and the clean structured data model the Patient Journey Application needs.

---

## Product Vision

**An upstream ingestion and normalization service that accepts health records in any format and outputs a standardized FHIR R4 bundle (or our internal PatientRecord model).**

This is a standalone application — a pre-processing pipeline that sits *upstream* of any FHIR-native application (including the Patient Journey App). It does one job well: take whatever you give it and output clean, structured patient data.

Think of it as a **"universal FHIR converter"** — the ETL layer for health records.

---

## Supported Input Formats (Target)

| Format | Coverage | Extraction Method | Priority |
|---|---|---|---|
| **FHIR R4 JSON/NDJSON** | Modern EHRs (Epic, Cerner) | Native parse | P0 — already done |
| **PDF (digital/text-layer)** | Discharge summaries, reports | LLM extraction | P1 |
| **PDF (scanned image)** | Old paper records | OCR → LLM extraction | P1 |
| **Free-text clinical notes** | Any free-text dump | LLM NER + structuring | P1 |
| **CDA / CCD XML** | Legacy EHR transitions | XML parse → FHIR map | P2 |
| **HL7 v2 messages** | Lab results, ADT feeds | HL7 parser → FHIR map | P2 |
| **CSV / Excel** | Some EHR bulk exports | Tabular mapping | P3 |
| **Proprietary EHR exports** | Epic MyChart, Cerner, Athena | Format-specific adapters | P3 |

---

## Core Architecture

### The Pipeline

```
Input (any format)
       ↓
[Format Detector]          — Identify what type of document this is
       ↓
[Format-Specific Extractor]
  ├─ FHIR → Native FHIR parser (existing)
  ├─ PDF (text) → LLM extraction
  ├─ PDF (scanned) → OCR → LLM extraction
  ├─ CDA/CCD → XML parser → FHIR mapper
  ├─ HL7 v2 → HL7 parser → FHIR mapper
  └─ Free text → LLM NER → structured entities
       ↓
[Entity Normalizer]         — Standardize codes: SNOMED, RxNorm, ICD-10, LOINC
       ↓
[FHIR R4 Builder]           — Construct valid FHIR resources from extracted entities
       ↓
[Output: FHIR R4 Bundle]    — Standard output for any downstream application
```

---

## Key Components

### 1. Format Detector

Inspect the incoming file and determine its type:

- File extension + MIME type
- Content sniffing (JSON? XML? HL7 segment headers? PDF header?)
- Returns: `fhir_r4 | pdf_text | pdf_scanned | cda_xml | hl7v2 | free_text | csv`

---

### 2. PDF Extractor (LLM-backed) — Highest Priority

Most real-world chart history arrives as PDF. Two sub-modes:

**PDF with text layer (digital PDF):**
- Extract raw text using `pdfplumber` or `pymupdf`
- Pass text blocks to LLM with a structured extraction prompt
- LLM identifies and extracts: medications, conditions, procedures, dates, providers, lab values

**PDF without text layer (scanned):**
- Run OCR first (`pytesseract` or cloud OCR)
- Then same LLM extraction flow as above

**LLM Extraction Prompt Pattern:**
```
You are a clinical data extractor. Given the following clinical document text, extract all structured clinical entities.

Return a JSON object with these fields:
- patient: {name, dob, mrn, sex}
- conditions: [{description, icd10_code (if found), onset_date, status}]
- medications: [{name, dose, frequency, start_date, end_date, status}]
- procedures: [{description, cpt_code (if found), date}]
- encounters: [{date, type, provider, facility, reason}]
- lab_results: [{test_name, value, unit, date, reference_range}]
- allergies: [{substance, reaction, severity}]

If a field is not present in the document, omit it. Use ISO 8601 dates. Be conservative — only extract what is clearly stated.

Document:
[extracted text]
```

**Output:** Structured JSON → normalized → FHIR R4 resources

---

### 3. CDA / CCD Parser

CDA (Clinical Document Architecture) and CCD (Continuity of Care Document) are XML-based HL7 standards. Still widely used for transitions of care between hospitals.

- Parse XML using standard Python XML libraries
- Map CDA sections to FHIR resources:
  - Problems section → Condition
  - Medications section → MedicationRequest
  - Results section → Observation
  - Encounters section → Encounter
  - Allergies section → AllergyIntolerance
- Standard libraries: `fhir.resources`, `hl7apy`

---

### 4. HL7 v2 Parser

HL7 v2 is the legacy messaging standard — still used for lab results, ADT (admit/discharge/transfer) feeds, order messages.

- Parse using `hl7apy` or `python-hl7`
- Map message types:
  - ADT_A01/A03 → Encounter
  - ORU_R01 → Observation (lab results)
  - RDE_O11 → MedicationRequest
- Less critical for single-patient history apps; more important for hospital system integrations

---

### 5. Entity Normalizer

Raw extraction gives you text like "lisinopril 10mg" or "high blood pressure." The normalizer maps these to standard codes:

- **Medications:** drug name → RxNorm code (via RxNav API or local RxNorm dataset)
- **Conditions:** free text → ICD-10 code (via ClinicalBERT or UMLS API)
- **Lab tests:** test name → LOINC code
- **Procedures:** procedure description → CPT code

Normalization is what makes the output interoperable. Without it, two records describing "lisinopril" and "Prinivil" are treated as different drugs.

---

### 6. FHIR R4 Builder

Take normalized entities and construct valid FHIR R4 resources:

- `Patient` resource from demographics
- `Condition` from extracted conditions + ICD-10 codes
- `MedicationRequest` from extracted medications + RxNorm codes
- `Observation` from lab results + LOINC codes
- `Encounter` from visit records
- `AllergyIntolerance` from allergies
- Wrap in a FHIR `Bundle` → output

This output is plug-compatible with the existing `fhir_explorer` parser and the Patient Journey Application.

---

## Application Interface

### Option A: Streamlit Upload UI

Simple drag-and-drop interface:

1. Upload one or multiple files (PDFs, ZIPs, JSON, XML)
2. Format detector runs automatically
3. Extraction progress shown per file
4. Review extracted entities (editable before finalization)
5. Download as FHIR R4 bundle JSON
6. Or: pass directly to Patient Journey App

### Option B: API Endpoint (FastAPI)

`POST /ingest`
- Body: multipart file upload (any supported format)
- Returns: FHIR R4 Bundle JSON
- Supports batch: multiple files → single merged patient bundle

---

## File Structure

```
fhir-ingestion/
├── README.md
├── requirements.txt
├── app.py                         # Streamlit UI (Option A)
├── api.py                         # FastAPI endpoint (Option B)
├── core/
│   ├── __init__.py
│   ├── format_detector.py         # Detect input format
│   ├── entity_normalizer.py       # Map text → standard codes (RxNorm, ICD-10, LOINC)
│   └── fhir_builder.py            # Construct FHIR R4 resources from normalized entities
├── extractors/
│   ├── __init__.py
│   ├── fhir_native.py             # Pass-through for existing FHIR parser
│   ├── pdf_extractor.py           # PDF text extraction + LLM structuring
│   ├── ocr_extractor.py           # Scanned PDF → OCR → text
│   ├── cda_parser.py              # CDA/CCD XML → structured entities
│   ├── hl7_parser.py              # HL7 v2 messages → structured entities
│   └── free_text_extractor.py     # Free-text clinical notes → structured entities
├── prompts/
│   └── clinical_extraction.txt    # LLM prompt templates for extraction
└── tests/
    ├── sample_docs/               # Test PDFs, CDAs, HL7 messages
    ├── test_format_detector.py
    ├── test_pdf_extractor.py
    └── test_fhir_builder.py
```

---

## Relationship to Other Applications

```
Real-world records (PDF, HL7, CDA, free text)
              ↓
    [fhir-ingestion] ← this app
              ↓
    FHIR R4 Bundle (standard output)
              ↓
    [patient-journey] or [fhir_explorer] or any FHIR-native tool
```

This is a **platform-level upstream service.** It doesn't know anything about what the downstream application does — it just produces clean FHIR. Any future application that needs patient data can consume its output.

---

## Contest Framing (EHI Ignite)

This maps to the **cross-system integration** scenario in the EHI Ignite evaluation criteria:

> *"Integrating EHI across different care settings and formats to give a complete picture of the patient"*

The format-agnostic layer is the answer to: "What if the patient has records from a hospital that doesn't support FHIR?" Every healthcare organization has legacy data. This is the bridge.

---

## Coding Session Prompt

> Use this prompt to kick off a new Claude Code session:

```
I'm building a Format-Agnostic Health Record Ingestion service as part of the EHI Ignite Challenge — an HHS-sponsored $490K competition to improve how electronic health information is used clinically.

This is a standalone upstream service that accepts patient health records in any format (FHIR R4, PDF, scanned PDFs, free-text clinical notes, CDA/CCD XML, HL7 v2) and normalizes them into a standard FHIR R4 bundle. It's the ETL layer that sits upstream of any FHIR-native application.

Please read ideas/FORMAT-AGNOSTIC-INGESTION.md for the full product definition, architecture, and specs.

Also orient yourself with the existing FHIR parser in this repo:
- fhir_explorer/parser/bundle_parser.py — existing FHIR bundle parser (we'll reuse this)
- fhir_explorer/parser/models.py — PatientRecord data model (our target internal model)

Build the new application in a new top-level directory: fhir-ingestion/

Start with:
1. core/format_detector.py — detect the format of an uploaded file (fhir_r4, pdf_text, pdf_scanned, cda_xml, hl7v2, free_text)
2. extractors/pdf_extractor.py — extract text from a digital PDF using pdfplumber, then use the Anthropic API (claude-3-5-sonnet) with a structured extraction prompt to pull out medications, conditions, encounters, lab results, allergies, and demographics as JSON
3. core/entity_normalizer.py — normalize extracted medication names to RxNorm codes (via RxNav API) and condition text to ICD-10 codes (rule-based or API)
4. core/fhir_builder.py — construct a FHIR R4 Bundle from normalized entities (Patient, Condition, MedicationRequest, Observation, AllergyIntolerance resources)
5. app.py — a Streamlit UI that accepts a file upload, runs the pipeline, and displays the extracted entities in a review table before outputting the FHIR bundle

Use clean typed Python consistent with the style in fhir_explorer/.
Include unit tests for the format detector and fhir_builder.
```

---

*Created by Chief · March 29, 2026*
