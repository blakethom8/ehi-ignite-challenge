# Screenshot Manifest — EHI Ignite Phase 1 Submission

Captured: 2026-05-09  
Branch: codex/patient-workspace-harmonization  
Stack: React frontend (Vite :5173) + FastAPI backend (:8000)  
Patient used: Synthea/Shelly431_Corwin846_*** (highly complex, 91 years old, 1,180-patient synthetic corpus)  
Note: All screenshots use synthetic Synthea data. No PHI from any personal portal sources.

---

## 01-source-intake.png

**Surface:** Data Aggregator → Source Intake  
**Patient:** Synthea/Demo123 workspace (showing staged sources, not a clinical patient)  
**Content:** Two staged sources — `cedars-sinai.json` (FHIR JSON export, 16 MB, FHIR ready badge) and `bt_functionhealth_results_11-29-2025.pdf` (PDF report, PDF parsed badge). Shows source count, prepared count, needs-context count, resource type breakdown sidebar.  
**Caption suggestion:** "Each source is classified and prepared before it can influence the harmonized record."  
**Rubric mapping:** Integration & Scaling — demonstrates multi-source ingestion pipeline with typed, staged sources.

---

## 02-harmonized-record.png

**Surface:** Data Aggregator → Harmonized Record  
**Patient:** Synthea/Shelly431_Corwin846_***  
**Content:** Shows workspace sources panel, harmonization run controls, canonical record tabs (Labs, Conditions, Medications, Allergies, Immunizations), canonical lab count (59), cross-source merges, conflicts count. Provenance links visible.  
**Caption suggestion:** "The same clinical fact can be traced across sources, with conflicts routed to review."  
**Rubric mapping:** Interpretability & Ease of Use, Integration — shows canonical record built from multiple sources with provenance.

---

## 03-safety-panel.png

**Surface:** Clinical Insights → Pre-Op Support → Safety Review  
**Patient:** Synthea/Shelly431_Corwin846_***  
**Content:** "2 ACTIVE flags" — NSAIDs (bleeding risk + renal concerns, hold 3–5 days pre-op, 2 meds) and Diabetes Medications (hold metformin 48h pre-op, adjust insulin dosing, 2 meds). Each flag shows severity, rationale, and linked medications.  
**Caption suggestion:** "The record becomes a usable clinical briefing — two flags, two medication groups, one pre-op decision frame."  
**Rubric mapping:** Interpretability & Ease of Use — demonstrates the "5 facts in 30 seconds" north star for high-signal surgical chart review.

---

## 04-assistant-evidence.png

**Surface:** Clinical Insights → Chat (Provider Assistant)  
**Patient:** Synthea/Shelly431_Corwin846_***  
**Content:** Provider Assistant scoped to Shelly431 Corwin846. Right panel shows chart scope: 1,833 clinical facts, 59 lab types, 217 encounters. Agent profile (General chart review), system context (Published chart boundary). Context Library packages visible (Pre-op Medication Holds, Cardiometabolic Review). Starter prompts for clinical questions.  
**Caption suggestion:** "The assistant reasons over a bounded evidence packet assembled from structured chart facts — not the raw record."  
**Rubric mapping:** AI Innovation — shows scoped context boundary, evidence packet framing, clinical context packages.

---

## 05-care-journey.png

**Surface:** FHIR Charts → Care Journey  
**Patient:** Synthea/Shelly431_Corwin846_***  
**Content:** Full Gantt timeline 1953–2021. Medications grouped by drug class (Diabetes, NSAIDs, Other — 9 total, 7 active). Conditions (28 total, 24 active). Procedures (33). Encounters (217: 184 ambulatory, 27 emergency, 6 inpatient). Lab Reports (126). Minimap visible at top for navigation.  
**Caption suggestion:** "Episodes and encounters across 68 years of care — grouped by drug class and condition status."  
**Rubric mapping:** Interpretability & Ease of Use, AI Innovation — longitudinal structured view of a complex patient.

---

## 06-data-lab.png

**Surface:** Internal Tools → Data Lab → Methodology  
**Patient:** N/A (corpus-level methodology view)  
**Content:** "How We Interpret FHIR for Clinical Use Cases" — four design principles (lead with safety-critical signal, compress without losing auditability, surface time-rel trends, declare assumptions). Five pipeline layers: Hard Filters, Episode Compression, Deterministic Interpretation, Batch Enrichment, Context Assembly.  
**Caption suggestion:** "Reviewers can inspect how raw FHIR becomes clinical interpretation — five pipeline layers, declared assumptions."  
**Rubric mapping:** Technical Feasibility, AI Innovation — demonstrates methodology transparency and pipeline structure.

---

## 07-patient-overview.png

**Surface:** FHIR Charts → Clinical Snapshot  
**Patient:** Synthea/Shelly431_Corwin846_***  
**Content:** Patient summary for Shelly431 Corwin846, female, 91 years old, Lynn Massachusetts. Demographics (DOB, ethnicity, QALY 47.978). Complexity: "Highly Complex Complexity — 90/100." Data span 1953–2019. Encounter class breakdown (184 AMB, 27 EMER, 6 IMP). Care activity histogram 1953–2019. Recent encounters visible at bottom.  
**Caption suggestion:** "A complexity-scored patient summary — demographics, data span, encounter mix, and recent activity at a glance."  
**Rubric mapping:** Interpretability & Ease of Use — structured clinical overview with complexity signal.

---

## 08-atlas-data-flow.png

**Surface:** Landing / main Atlas Data Flow visual  
**Patient:** N/A (platform overview)  
**Content:** Four source types at the top (`FHIR bundle`, `C-CDA`, `PDF`, `Portal export`) feeding `Harmonize + prepare`, then four downstream environments at the bottom (`FHIR Charts`, `Caspian`, `Plugins`, `Export package`). Includes the line “One patient record. Multiple downstream environments.”  
**Caption suggestion:** "Atlas harmonizes multiple source types into one prepared patient record, then supports multiple downstream environments from that shared layer."  
**Rubric mapping:** Description of Solution and Problem Addressed, Innovation, Technical Feasibility — quickly shows the two-pronged architecture and portability claim.

---

## 09-source-intake-refresh.png

**Surface:** Patient workflow → Source Intake  
**Patient:** Blake Thomson demo workspace  
**Content:** Upload surface for portal exports, PDFs, screenshots, CSVs, and device data. Shows three sources staged, prepared counts, needs-context counts, and a selected PDF with extracted FHIR candidate bundle details.  
**Caption suggestion:** "Source Intake: portal exports, PDFs, and FHIR files enter one patient workflow; parsed documents can already emit candidate FHIR resources before harmonization."  
**Rubric mapping:** Wireframes / Mockups, Technical Feasibility — demonstrates multi-source intake and PDF-to-FHIR candidate generation.

---

## 10-harmonized-record-refresh.png

**Surface:** Patient workflow → Harmonized Record  
**Patient:** Blake Thomson demo workspace  
**Content:** Canonical labs table with cross-source merge counts, selected fact detail, source list, and raw FHIR Provenance JSON. Shows the harmonization layer explicitly rather than just the output view.  
**Caption suggestion:** "Harmonized Record: cross-source merges, canonical facts, and provenance lineage show how Atlas turns document inputs into a reusable FHIR-based record."  
**Rubric mapping:** Wireframes / Mockups, Innovation, Technical Feasibility — shows the provenance-backed FHIR output model directly.

---

## 11-chart-history-refresh.png

**Surface:** FHIR Charts → History  
**Patient:** Blake Thomson demo workspace  
**Content:** Encounter timeline with imported lab-report source events, office visits, immunization source events, filters, and resource links. Emphasizes chart-review chronology built from the prepared record.  
**Caption suggestion:** "FHIR Charts: encounters, imported lab events, and office visits are organized into a chart-review timeline instead of scattered documents."  
**Rubric mapping:** Wireframes / Mockups, Interpretability and Ease of Use — demonstrates chart-ready chronology built from the harmonized record.

---

## 12-caspian-review-refresh.png

**Surface:** Caspian → Clinical review  
**Patient:** Blake Thomson demo workspace  
**Content:** Pre-op clearance review workflow with evidence-backed disposition, generated markdown summary, inspector evidence panel, and file workspace.  
**Caption suggestion:** "Caspian: a pre-op workflow turns the record into a review disposition, evidence-backed summary, and shareable clinical note."  
**Rubric mapping:** Wireframes / Mockups, Innovation, Potential Impact — shows pre-guided clinical workflow over the prepared record.

---

## 13-caspian-chat-refresh.png

**Surface:** Caspian → Clinical review chat surface  
**Patient:** Blake Thomson demo workspace  
**Content:** Conversation view showing tool calls, evidence references, files created, and the clinician’s request for a shareable summary PDF.  
**Caption suggestion:** "Caspian can show the conversational workflow and the file outputs created from the same evidence boundary."  
**Rubric mapping:** Wireframes / Mockups, Innovation — shows the assistant/chat side of the clinical workspace.

---

## 14-plugin-marketplace-refresh.png

**Surface:** Plugin marketplace  
**Patient:** N/A (platform-level)  
**Content:** Three plug-ins — Medication Access, Second Opinion, and Trial Finder — each showing a workflow description, an external boundary, and an approval-aware workspace entry point.  
**Caption suggestion:** "Plugin marketplace: Medication Access, Second Opinion, and Trial Finder each define a workflow boundary, an external system boundary, and an approval model."  
**Rubric mapping:** Wireframes / Mockups, Innovation, Potential Impact — demonstrates scoped downstream workflows beyond the core app.

---

## 15-trial-finder-refresh.png

**Surface:** Trial Finder plug-in workspace  
**Patient:** Hollister demo workspace  
**Content:** Candidate-board workflow with a consented external registry boundary, ranked trials, approval request, and workbench artifacts such as shortlist and manifest files.  
**Caption suggestion:** "Trial Finder: Atlas can pass a consented patient anchor into a workflow that ranks candidate trials and pauses outbound actions pending approval."  
**Rubric mapping:** Wireframes / Mockups, Innovation, Potential Impact — shows plug-ins engaging the external world while preserving approval and consent controls.
