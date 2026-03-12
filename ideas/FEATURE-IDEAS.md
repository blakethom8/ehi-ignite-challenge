# Feature Ideas — EHI Agent Platform

## Core Architecture Principle

> **The aggregator is the foundation. Once data is pooled and summarized into the portal, you spawn specialized agents against it.**

This mirrors the enterprise assistant architecture: the agent has a workspace (patient's EHI), reads it at session start, and tools/agents spawn from there. The EHI export IS the workspace.

---

## The Platform Vision: "MedContext"

A patient-controlled AI layer that sits on top of their EHI export and enables intelligent agents.

### Layer 1 — Data Aggregation & Normalization (Foundation)
Ingest single-patient FHIR exports from one or multiple health systems. Normalize into a unified patient model. This is the prerequisite to everything else.

**What it does:**
- Accept FHIR R4 ZIP uploads (from Epic, Cerner, any EHR)
- Parse all resource types into a structured database
- Deduplicate (same condition from two hospitals)
- Build a "master patient record" spanning all systems
- Generate a plain-language baseline summary

**Why it's hard:** Vendor format inconsistency. Epic's FHIR ≠ Cerner's FHIR. Entity resolution across systems (same patient, different IDs). Deduplication without merging distinct events.

**Data required:** Patient, Condition, Medication, Encounter, Observation, Coverage  
**FHIR resources:** All of them  
**EHIgnite fit:** ✅ Summarization (required) + Integration across settings

---

## Specialized Agents (Spawn Once Data Is Aggregated)

---

### Agent 1 — Rare Disease Funding Finder 💊

**The problem:** Drugs for rare diseases cost $50K–$500K/year. Insurance often denies. Patient advocacy organizations, pharmaceutical manufacturers, and government programs offer assistance — but patients don't know they exist, let alone how to apply.

**What the agent does:**
1. Reads patient's conditions (Condition resources → SNOMED codes → disease names)
2. Identifies rare diseases (orphan disease status via NORD database)
3. Web-searches for: manufacturer PAPs (patient assistance programs), foundation grants, NIH programs, state-level programs, 340B eligibility
4. Cross-references patient's insurance status (Coverage resource) + meds (MedicationRequest)
5. Generates a ranked list of funding sources with eligibility criteria and application links

**Example output:**
> "Based on your diagnosis of IgA Nephropathy and current Nefecon (Tarpeyo) prescription, you may qualify for: (1) Calliditas Patient Assistance Program — free drug if income <$100K/family of 4; (2) American Kidney Fund grants up to $3,600/year; (3) NKF financial assistance program..."

**Data used:** Condition (SNOMED), MedicationRequest (RxNorm), Coverage (insurer, plan type), Patient (demographics for eligibility)  
**Tools needed:** Web search (Brave API or similar), NORD API, NPI/drug database  
**Prior art:** We've already built this pattern — web search + LLM synthesis is proven  
**EHIgnite fit:** ✅ Participant-defined use case (potentially strongest submission angle)

---

### Agent 2 — Claims & Billing Intelligence Agent 📋

**The problem:** Patients are routinely overbilled, denied incorrectly, and unaware of claims they could file. The EHI export contains their full Claim + ExplanationOfBenefit (EOB) history. Almost nobody actually uses this data.

**What the agent does:**

**Use Case 2a — Underpaid / Denied Claim Finder:**
1. Read all EOB resources (insurance responses to claims)
2. Identify claims marked "denied" or underpaid relative to the service billed
3. Identify common denial reasons (prior auth missing, out-of-network, coding errors)
4. Generate appeal letter template for each denied claim with the specific codes + rationale

**Use Case 2b — Unclaimed Benefits Finder:**
1. Read Coverage resource (what plan they have)
2. Compare benefits utilization against what the plan covers
3. "You have $500/year dental benefit — you've used $0 in 3 years"
4. "Your plan covers mental health visits at 100% in-network — you've never used this"

**Use Case 2c — Medical Bill Auditor:**
1. Match billed CPT codes (in Claim) against what was actually documented in Encounter + Procedure
2. Flag upcoding, duplicate billing, services that don't match the visit
3. Give patient a script to call the billing department

**Data used:** Claim, ExplanationOfBenefit, Coverage, Encounter, Procedure  
**Tools needed:** Insurance plan benefit databases (payer-specific), CPT code lookup  
**EHIgnite fit:** ✅ Payer workflow (one of the 4 named scenarios)

---

### Agent 3 — Payer-Provider Network Navigator 🗺️

**The problem:** When a patient sees a new doctor, they often have no idea if that doctor is in-network. This is a disaster waiting to happen — a $40 copay visit becomes a $3,000 bill. The EHI export has the patient's Coverage (insurance + plan) and their CareTeam (current providers with NPIs).

**What the agent does:**
1. Read Coverage resource — extract insurer, plan name, member ID, plan type (HMO/PPO/EPO)
2. Read CareTeam and Practitioner resources — current providers with NPIs
3. When patient asks "Is Dr. Smith at Cedars-Sinai in my network?":
   - Look up NPI → NPPES for provider details
   - Query insurer's provider directory API (or web scrape if no API)
   - Return: in-network / out-of-network / need referral / need prior auth
4. For new referrals: "My cardiologist referred me to Dr. Jones — is he in-network?"
5. Proactive: "Your primary care doctor retired. Here are 5 in-network PCPs accepting new patients near you."

**Why this is important:** The payer-provider relationship breakdown is one of healthcare's biggest friction points. The data to solve it exists — NPI registries are public, insurer directories are (legally) accessible.

**Data used:** Coverage, CareTeam, Practitioner (NPIs), Patient (zip code)  
**External data:** NPPES NPI Registry (free), CMS Doctors & Clinicians dataset, payer provider directory APIs  
**We have this:** CMS DuckDB on Hetzner already has 2.7M providers + network data  
**EHIgnite fit:** ✅ Interactive patient tools + Integration

---

### Agent 4 — Second Opinion Prep Package 🩺

**The problem:** A patient wants a second opinion at a different hospital. They need to bring their records. What do they send? A 500-page printout? The full FHIR ZIP? Neither works.

**What the agent does:**
1. Read full EHI export
2. Ask patient: "What's the reason for the second opinion? What specialty?"
3. Generate a curated clinical brief optimized for that specialty:
   - Cardiology brief: focus on cardiac conditions, echo reports, stress tests, cath results, cardiac meds
   - Oncology brief: cancer diagnosis timeline, treatments, response to therapy, current regimen
   - Nephrology brief: kidney function labs (creatinine, GFR) over time, proteinuria, meds affecting kidneys
4. Format as a clean PDF or structured FHIR document
5. Optionally: generate a cover letter for the receiving physician

**For the physician on the receiving end:**
- Accept incoming FHIR ZIP
- Display as specialty-specific structured view
- Highlight critical safety info (allergies, implants, current meds)
- Flag potential issues with proposed treatment plan

**Data used:** All clinical resources, filtered by specialty-relevant codes  
**EHIgnite fit:** ✅ Summarization (required) + Domain filtering

---

### Agent 5 — Medication Reconciliation & Safety Agent 💊

**The problem:** When patients transition between care settings (hospital discharge, new specialist), medication lists get out of sync. Patients end up on conflicting drugs from different providers who can't see each other's prescriptions.

**What the agent does:**
1. Extract all active MedicationRequest resources across all EHR sources
2. Identify duplicates (same drug, different dosage from different systems)
3. Run drug-drug interaction check (OpenFDA interaction API or similar)
4. Flag: duplicates, interactions, drugs that contraindicate given patient conditions
5. Generate a single reconciled medication list
6. Produce patient-friendly card: "What you're taking, why, and what to watch for"

**Extreme value case:** The complex patient (Marine542 in our dataset) is on tacrolimus (transplant immunosuppressant) + other meds. Tacrolimus has severe interactions with dozens of common drugs. A new provider who doesn't know about the transplant could prescribe something that causes rejection.

**Data used:** MedicationRequest, Condition (for contraindications), AllergyIntolerance  
**External:** OpenFDA Drug Interaction API, RxNorm API  
**EHIgnite fit:** ✅ Summarization + Interactive patient tools

---

### Agent 6 — Care Gap & Preventive Care Advisor 📅

**The problem:** Preventive care screenings are routinely missed. Patients with diabetes should get annual eye exams, nephrology check-ins, A1C every 3 months. Patients over 50 should get colonoscopies. The data to know who's overdue is right there in the EHI export.

**What the agent does:**
1. Read conditions, age, gender → determine what screenings are clinically indicated
2. Read Observation, Procedure, Encounter history → check when last done
3. USPSTF guideline database → what's recommended, at what frequency
4. Output: "You are overdue for these screenings. Here's how to schedule them."
5. Bonus: for multi-system patients, deduplicate — "You got your A1C at Hospital A in January, don't need it again at Hospital B in March."

**Data used:** Condition, Patient (age/gender), Observation, Procedure, Encounter  
**EHIgnite fit:** ✅ Summarization + Interactive patient tools

---

## Phase 1 Submission Strategy

Given the May 13 deadline for concept + wireframes, the strongest competition submission would be:

### Core Pitch: "FHIR Aggregator + Agent Launcher"

**Required element (summarization):** The aggregator layer produces a plain-language health summary. This is the entry point for every user — patient or provider.

**Primary scenario (chose one for Phase 1):** Recommend going with **Interactive Patient Tools** (Q&A) because:
- Most universal (every patient can use it)
- Highest AI judges scoring potential
- Easiest to demo convincingly in wireframes
- Natural entry into other agents

**Differentiators for winning:**
1. Multi-EHR stitching (Phase 1 bonus for interoperability) — show that you can merge an Epic export + a Cerner export into one unified record
2. Azure deployment — data stays in patient's environment, directly addresses privacy/security criteria
3. Agent architecture — show that the aggregator spawns specialized sub-agents (demonstrate at least 2: Q&A + one of the above)

### Phase 2 Build Order (if we win Phase 1)
1. FHIR parser + normalization engine (the foundation)
2. Conversational Q&A agent (demo-ready for judging)
3. Network navigator (payer-provider intelligence) — our CMS data is the moat here
4. Claims intelligence agent (high patient value, unique angle)
5. Rare disease funding finder (most differentiated, highest emotional impact)

---

## Technical Architecture Notes

### Ingestion Layer
- Accept ZIP upload containing FHIR R4 NDJSON or individual Bundle JSON
- Parser handles both formats
- Normalize to internal canonical model (or keep as FHIR + build query layer)
- DuckDB for local analysis; Postgres for persistence

### The "Patient Workspace" Pattern
Mirrors the enterprise assistant architecture:
- `workspace/PATIENT.md` — plain-language profile generated from FHIR Patient resource
- `workspace/ACTIVE_CONDITIONS.md` — current problem list
- `workspace/MEDICATIONS.md` — current med list
- `workspace/COVERAGE.md` — insurance details
- `workspace/memory/` — conversation history, agent outputs
- `workspace/reports/` — generated documents

The LLM agent reads these files at session start, then calls tools for deeper queries.

### Deployment
- Single-patient: run locally or in patient's Azure environment
- Zero data egress — FHIR parsing and LLM processing happen in-environment
- HIPAA-compatible: no PHI to third-party APIs
- For enterprise (hospital) use: deploy as Azure Container App per patient (our existing pattern)

---

## Open Questions (Need Clinical Input)

*Questions for Taylor (MD) or other clinical advisors:*

1. When you see a new patient with a complex history, what's the ONE thing you wish you had in 60 seconds?
2. How often do you get a patient's records from another system — and when you do, what's the first thing you look for?
3. What's the most dangerous medication reconciliation scenario you encounter regularly?
4. When patients ask about their bills, what's the most common confusion/dispute?
5. What preventive care screenings get missed most often in your patient population?
6. Have you ever had a patient show up and you didn't know about a major diagnosis (transplant, rare disease) because records didn't follow them?
