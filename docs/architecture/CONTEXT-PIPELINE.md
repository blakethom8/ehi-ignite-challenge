# Context Engineering Pipeline

> How we transform verbose FHIR patient records into token-efficient, clinician-ready context that makes LLM-powered chart review fast, accurate, and auditable.

---

## The Problem

A single patient's FHIR record can contain **thousands of resources** — 40,000+ observations, 6,000+ encounters, 1,900+ medication requests for a complex patient. Dumping this into an LLM context window is expensive (~$2-5 per conversation), slow (the model spends most of its reasoning parsing structure), and unreliable (raw FHIR leads to hallucinated relationships and missed medications).

**The core insight:** A surgeon reviewing a patient before a procedure doesn't need 40,000 lab values. They need the **right 20 facts in 30 seconds**: active blood thinners, drug interactions, key lab trends, and the current problem list. Everything else is noise.

---

## Our Approach: Pre-Built Clinical Context

Instead of making the LLM parse raw FHIR on the fly, we **pre-process patient data into clinician-ready context** before the conversation starts. By the time a surgeon asks "Is this patient safe for surgery Tuesday?", the system has already:

1. Identified all safety-critical medications (anticoagulants, NSAIDs, immunosuppressants)
2. Detected drug-drug interactions with management guidance
3. Deduplicated medication episodes (47 raw MedicationRequests → 1 episode)
4. Pulled the latest values for 20+ clinically important lab tests
5. Linked medications to their prescribing reasons (Warfarin → for Atrial Fibrillation)
6. Declared notable absences (no allergies, no antiplatelets)

The result: **~1,400 tokens** of structured clinical context that answers the surgeon's key questions without follow-up queries. Compare to ~3,000+ tokens of unstructured, duplicate-heavy facts from a naive approach — or the raw FHIR at 100,000+ tokens.

---

## The 4-Layer Pipeline (Implemented)

```
Raw FHIR Bundle (100K+ tokens)
    │
    ▼
┌─────────────────────────────────────┐
│ Layer 0: Hard Filters               │
│ Drop billing, admin, routine data   │
│ Keep: safety-linked, recent, active │
│ Reduction: ~60-80%                  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Layer 1: Episode Compression        │
│ medication_episode (deduplicated)   │
│ condition (with temporal metadata)  │
│ observation_latest (key labs only)  │
│ encounter (recent, with diagnoses)  │
│ Reduction: ~5-10x                   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Layer 3: Format Optimization        │
│ Structured markdown with headers    │
│ Temporal markers (since, duration)  │
│ Drug class tags, reason linkages    │
│ Safety-first ordering               │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Layer 4: Persona Selection          │
│ Surgical pre-op focus               │
│ Key labs for anesthesia clearance   │
│ Notable absences declared           │
│ Action items on safety flags        │
└─────────────────────────────────────┘
    │
    ▼
Clean Clinical Context (~1,400 tokens)
```

### Layer 0: Hard Filters

**Always drop:** Claims, ExplanationOfBenefit (billing noise), Organization, Practitioner (administrative), DocumentReference shells.

**Always keep:** Anything linked to an active condition, any medication in a surgical-risk drug class, any encounter in the recent period, all allergies.

### Layer 1: Episode Compression

The SQL-on-FHIR warehouse provides pre-compressed data structures:

| Source | What it does | Example |
|--------|-------------|---------|
| `medication_episode` | Groups 47 MedicationRequests into 1 episode with start/end/duration/is_active | 59 Cisplatin entries → 1 episode: "Cisplatin, 2002-2006, stopped" |
| `observation_latest` | Latest value per (patient, LOINC code) via ROW_NUMBER() window function | 40,000 observations → 13 key lab values |
| `condition_active` | Filtered to active/recurrence/relapse only | 1,410 conditions → 674 active |
| `encounter` + `condition` JOIN | Links diagnoses to encounters | "Emergency visit — Sprain of wrist" |

### Layer 3: Format Optimization

Every item carries inline temporal context:

```markdown
- **Warfarin Sodium 5 MG Oral Tablet** [anticoagulants] | Since Nov 20, 2003 (22.4yr) | 1 Rx
  Action: Bleeding risk — must hold before surgery. Check INR/PT.
```

One line answers: what drug, what class, since when, how long, and what to do about it.

### Layer 4: Persona Selection

The context is ordered for a surgeon doing pre-op review:

1. **Safety flags** (what could kill the patient on the table)
2. **Drug interactions** (what combinations are dangerous)
3. **Active medications** (what they're currently taking)
4. **Active conditions** (the problem list)
5. **Key lab values** (anesthesia clearance data)
6. **Recent encounters** (what happened lately)
7. **Procedures** (surgical history)
8. **Historical medications** (what they used to take)
9. **Notable absences** (explicitly: no allergies, no antiplatelets)

---

## Before and After

### Before: Naive Fact Corpus

```
Total facts: 114
Duplicate chemo entries: 59 (52%)
Lab values: 0
Structure: flat list of text strings
Token estimate: ~3,000+
Medication reasons: none
Absences declared: none
```

### After: Context Builder Pipeline

```
Total facts: 81
Duplicate entries: 0
Lab values: 13 (HbA1c, creatinine, eGFR, INR, platelets...)
Structure: markdown with headers, temporal markers
Token estimate: ~1,400
Medication reasons: resolved from FHIR reasonReference
Absences: explicitly declared
```

**55% fewer tokens. Zero duplicates. Key labs included. Fully structured.**

---

## Assistant Architecture

### Three Engine Modes

| Mode | Latency | How it works | When to use |
|------|---------|--------------|-------------|
| **deterministic** | ~0.15s | Rule-based keyword ranking, no LLM | Development, no API key |
| **context** (recommended) | ~3-5s | Context builder → single Claude call | **Pitch demos, production** |
| **agent_sdk** | ~15-30s | Multi-turn agent with tool calls | Research, complex queries |

### Context Mode Flow

```
1. Build clinical context (deterministic, ~150ms)
   └─ context_builder.py → ~1,400 tokens of clean markdown

2. Single Claude API call (~3-5s)
   └─ System prompt: clinical context + instructions
   └─ User message: the question
   └─ Response: direct answer with citations

3. Return structured response
   └─ Answer text
   └─ Confidence level
   └─ Citations (from deterministic fact corpus)
   └─ Follow-up suggestions
   └─ Full trace (context, tokens, cost)
```

Set `PROVIDER_ASSISTANT_MODE=context` in `.env` to enable.

---

## Key Design Decisions

### Why not just dump FHIR into the context?

1. **Cost**: Raw FHIR for a complex patient is 100K+ tokens. At Sonnet pricing, that's ~$0.30 per question just for input tokens. Our ~1,400 token context costs ~$0.004. That's **75x cheaper**.

2. **Speed**: More input tokens = slower response. 100K tokens takes 10-15s just to process. 1,400 tokens processes in <1s.

3. **Accuracy**: LLMs get confused by repetitive data. 59 identical Cisplatin entries don't make the model more confident — they make it over-index on chemotherapy and miss the Warfarin that actually matters for surgery.

### Why not use RAG (retrieval-augmented generation)?

RAG adds a retrieval step that searches for relevant chunks. But clinical data isn't unstructured text — it's structured resources with temporal relationships. RAG would:
- Miss cross-resource relationships (Warfarin prescribed *because of* Atrial Fibrillation)
- Lose temporal context (when was the last INR? RAG returns the value but not the trend)
- Require embedding the entire FHIR record (expensive, one-time cost per patient)

Our approach uses **structured queries** (SQL on the warehouse) and **deterministic episode compression** — faster, cheaper, and more predictable than embedding-based retrieval.

### Why declare absences?

"No anticoagulants" is as clinically important as "on warfarin." If the context doesn't explicitly state absences, the LLM may hedge: "I don't see anticoagulants in the data, but they might be prescribed elsewhere." With explicit absence declarations, the LLM can confidently say: "No anticoagulant therapy — proceed without bridging protocol."

---

## Data Sources

| Data | Source | Query Target |
|------|--------|-------------|
| Medication episodes | SQL-on-FHIR warehouse | `medication_episode` (derived table) |
| Active conditions | SQL-on-FHIR warehouse | `condition` / `condition_active` |
| Key lab values | SQL-on-FHIR warehouse | `observation_latest` (derived view) |
| Recent encounters | SQL-on-FHIR warehouse | `encounter` LEFT JOIN `condition` |
| Medication reasons | FHIR bundle | `MedicationRequest.reasonReference` → `Condition` |
| Safety flags | Drug classifier | `patient-journey/data/drug_classes.json` |
| Drug interactions | Interaction checker | `api/core/interaction_checker.py` |
| Procedures | FHIR bundle | `Procedure` resources (grouped by name) |
| Allergies | FHIR bundle | `AllergyIntolerance` resources |

---

## Key Lab Values Tracked

The pipeline tracks 20+ LOINC codes that matter for surgical pre-op clearance:

| LOINC | Lab | Why It Matters |
|-------|-----|---------------|
| 6301-6 | INR | Anticoagulation monitoring (Warfarin patients) |
| 5902-2 | PT | Coagulation status |
| 4548-4 | HbA1c | Diabetes control (affects wound healing) |
| 2160-0 | Creatinine | Renal function (drug dosing, contrast safety) |
| 33914-3 | eGFR | Renal function |
| 718-7 | Hemoglobin | Anemia (blood loss risk) |
| 777-3 | Platelets | Bleeding risk |
| 6690-2 | WBC | Infection risk |
| 2947-0 | Sodium | Electrolyte balance |
| 6298-4 | Potassium | Cardiac risk |
| 2339-0 | Glucose | Diabetes management |
| 1742-6 | ALT | Liver function |
| 1920-8 | AST | Liver function |

---

## Future: Layer 2 (LLM Batch Enrichment)

Layer 2 is not yet implemented. It would add:

- **Relevance scoring** (0-10) per episode for surgical planning
- **Clinical narrative generation** ("Patient has been on warfarin 5mg daily since 2019 for atrial fibrillation. Last INR 2.3, within therapeutic range.")
- **Cross-episode relationship detection** ("Warfarin prescribed for: Atrial Fibrillation")
- **Dosage interpretation** ("Prednisone 60mg = high-dose immunosuppression, affects wound healing")

Estimated cost: ~$0.05 per patient, cached and reused across all conversations.

---

## Files

| File | Purpose |
|------|---------|
| `api/core/context_builder.py` | The pipeline — builds ClinicalContext from patient data |
| `api/core/provider_assistant_context.py` | Single-turn Claude call using the clean context |
| `api/core/provider_assistant_service.py` | Mode selector (deterministic / context / agent_sdk) |
| `patient-journey/CONTEXT-ENGINEERING.md` | Original design spec (5-layer vision) |
| `patient-journey/core/sql_on_fhir/` | SQL-on-FHIR warehouse (data foundation) |
| `patient-journey/data/drug_classes.json` | Drug classification mapping |

---

*Last updated: April 13, 2026*
