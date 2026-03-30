# Context Engineering Strategy

> How we transform raw FHIR patient records into token-efficient, clinician-ready context for LLM consumption.

---

## The Problem

A single patient's FHIR record can range from 34K tokens (simple) to 10.5M tokens (complex). An LLM agent helping a surgeon prepare for a case needs the clinically relevant signal in under ~1,000 tokens — with the ability to pull in more on demand.

Raw FHIR is verbose by design. Every MedicationRequest repeats the full drug name, coding system, status, dates, dosage, requester, and encounter reference. A patient on lisinopril for 15 years might have 47 individual MedicationRequest resources — but the surgeon needs one line plus temporal context.

---

## Why This Matters (Competitive Positioning)

Most health data applications treat the LLM as a downstream consumer — they dump FHIR into the context window and hope the model figures it out. That approach is expensive ($2–5 in conversation tokens for a complex patient), slow (the model spends most of its reasoning on parsing structure, not answering questions), and unreliable (raw FHIR leads to hallucinated relationships, missed medications, and incorrect temporal reasoning).

Our approach inverts this. The **LLM batch enrichment pipeline** is the core innovation — it pre-processes raw clinical data into clinician-ready reasoning artifacts *before the conversation starts*. By the time a surgeon asks "Is this patient safe for surgery Tuesday?", the system has already:

- Scored every clinical episode for surgical relevance (0–10)
- Generated clinical narratives with temporal context and actionable guidance
- Detected cross-episode relationships that pure rule-based systems miss
- Flagged dosage-specific risk levels (5mg vs. 60mg prednisone is a different conversation)
- Produced compact markdown rows ready to drop into a ~450-token context window

The agent isn't reasoning from raw FHIR — it's reasoning from pre-digested clinical intelligence. This produces fundamentally higher quality responses at a fraction of the cost.

**The economics:** ~$0.05 to batch-enrich a complex patient once, cached and reused across all conversations. Compare to the alternative: $2–5 per conversation attempt while the LLM parses raw FHIR on the fly and gets it wrong half the time. The batch enrichment approach is 40–100x cheaper per interaction AND more accurate.

**The moat:** This pipeline is hard to replicate because it requires domain-specific prompt engineering (what matters for surgical planning vs. ER vs. primary care), a temporal model that preserves clinically relevant time relationships, and a layered architecture that knows when to use rules vs. LLM reasoning. It's not just "put FHIR into ChatGPT."

---

## Design Principles

1. **Lead with what kills.** Safety-critical information (bleeding risk drugs, anesthesia interactions, allergies) appears first, always.
2. **Time is the first dimension.** Every piece of clinical data has temporal context — when it started, when it last appeared, whether it's current, how long it's been active. This temporal framing must survive compression.
3. **Compress, don't discard.** Historical data gets compressed into episodes with temporal metadata, not thrown away. The difference between "no opioid history" and "opioid history not shown" is clinically significant.
4. **Declare absences.** Explicitly state what's NOT present. "No anticoagulants" is as important as "on warfarin."
5. **Rules for structure, LLM for meaning.** Use deterministic rules for grouping, filtering, temporal math, and keyword classification. Use LLM batch processing for relevance scoring, clinical narrative generation, ambiguous classification, and cross-episode relationship detection. Rules are fast and free; LLMs add clinical reasoning at ~$0.01–$0.05 per patient.
6. **Tools as the escape hatch.** The initial context is the briefing. A RAG pipeline / tool-use layer lets the LLM pull in deeper detail on demand — full prescription history, lab trends, encounter details — without bloating the default context.

---

## Temporal Model

Time is not just metadata — it's the organizing principle of clinical reasoning. A surgeon doesn't think in terms of FHIR resources; they think in terms of "what's happening now, what happened recently, and what in the past still matters."

### Temporal Attributes Per Episode

Every compressed episode (medication, condition, encounter cluster) should carry these temporal fields:

| Field | Why It Matters | Example |
|-------|---------------|---------|
| **first_seen** | When this first appeared in the record | "Lisinopril first prescribed 2011-03-14" |
| **last_seen** | Most recent occurrence or prescription | "Last refill 2026-01-20" |
| **duration** | How long this has been part of the patient's history | "15.0 years" |
| **is_current** | Whether this is active right now | Active / Stopped / Resolved |
| **recency** | How recently it was relevant (days since last_seen) | "68 days ago" |
| **frequency** | How often this recurs (encounters, refills) | "~3.1 prescriptions/year" |
| **gaps** | Any interruptions in continuity | "Gap: 2018-06 to 2019-01 (7 months)" |
| **trend** | For labs/vitals — direction of change | "A1C trending down: 8.2 → 7.1 over 18mo" |

### Temporal Tiers for Context Inclusion

Not all time periods are equal. A surgeon's temporal priority stack:

```
NOW        → Active medications, active conditions, allergies       [ALWAYS INCLUDE]
RECENT     → Last 30 days: encounters, lab values, procedures       [INCLUDE WITH DETAIL]
PERIOP     → Last 6 months: relevant to surgical planning           [INCLUDE SUMMARIZED]
HISTORICAL → 6mo–full history: compressed episodes                  [INCLUDE AS ONE-LINERS]
ARCHIVED   → Available via tool retrieval only                      [ON-DEMAND VIA RAG]
```

### Temporal Context in Output Format

Every item in the compressed context carries inline temporal markers:

```
CURRENT MEDICATIONS (Surgical Risk):
  🔴 Warfarin 5mg daily | Anticoagulant | Since 2019-08 (6.6yr) | Last Rx: 2026-01-20 (68d ago) | HOLD PRE-OP
  ⚠️ Lisinopril 10mg daily | ACE Inhibitor | Since 2011-03 (15yr) | Last Rx: 2026-02-15 (42d ago) | Hold morning of surgery

STOPPED MEDICATIONS (Recent):
  ⚪ Ibuprofen 400mg PRN | NSAID | 2024-01 → 2025-09 (1.7yr) | Stopped 6mo ago
  ⚪ Metformin 1000mg BID | Diabetes | 2018-05 → 2025-06 (7.1yr) | Stopped 9mo ago

HISTORICAL (Compressed):
  Amoxicillin — 3 courses over 2015–2022 (acute infections, all resolved)
  Oxycodone — single 7-day course post-procedure, 2020-04. No ongoing use.
```

Notice each line answers: what, how much, what class, since when, how long, last activity, and what to do about it. The surgeon can scan this in seconds.

### Temporal Questions the Context Must Answer

For Max (neurosurgeon) reviewing a patient pre-op, these are the temporal questions the context must answer without requiring a follow-up query:

- **"Is this patient on blood thinners RIGHT NOW?"** → Active medication list with safety flags
- **"When did they last take it?"** → last_seen / recency field
- **"How long have they been on it?"** → duration field
- **"Have they ever been on opioids?"** → Historical compressed episodes with dates
- **"Any recent surgeries or procedures?"** → Perioperative window encounters
- **"Are their labs trending the wrong direction?"** → Trend field on recent observations
- **"When was their last visit?"** → Most recent encounter date

If a question CAN'T be answered from the initial context, the LLM agent uses the RAG tool layer to retrieve it.

---

## The 5-Layer Pipeline

### Layer 0: Hard Filters (Parse-Time Noise Removal)

Remove entire resource categories that never matter for clinical reasoning:

**Always drop:**
- Claims, ExplanationOfBenefit (billing noise)
- Organization, Practitioner, PractitionerRole, Location (administrative)
- Device references (unless implants)
- DocumentReference shells (metadata without content)

**Conditionally drop:**
- Routine wellness encounters with no linked conditions/procedures
- Routine vitals (BMI, height, weight) — keep only latest value
- Resolved conditions with <30 day duration, no linked medications, and >5 years ago
- Immunization history (unless specifically relevant — e.g., tetanus for wound cases)

**Always keep:**
- Anything linked to an active condition
- Any medication in a surgical-risk drug class (any time period)
- Any encounter in the last 2 years
- All allergies (regardless of age)

*Expected reduction: 60–80% of raw token volume.*

### Layer 1: Episode Compression

Group individual FHIR resources into clinical episodes with full temporal metadata:

**Medication Episodes:**
- Group MedicationRequests by normalized drug name
- Compute: first_seen, last_seen, duration, is_current, frequency, gaps
- Attach drug class and severity from the classifier
- 47 MedicationRequests → 1 episode record (~20 tokens vs ~2,000)

**Condition Episodes:**
- Group by condition code
- Link to related encounters and medications via encounter_id
- Compute: onset, resolution, duration, is_active, recurrence count
- Attach related medication episodes

**Encounter Clusters:**
- Group encounters by type and time proximity
- "12 wellness visits 2018–2025" instead of 12 individual records
- Preserve detail only for encounters with linked procedures or significant findings

*Expected reduction: 5–10x on remaining data after Layer 0.*

### Layer 2: LLM Batch Enrichment (Feature Engineering)

Layers 0 and 1 are deterministic — rules, grouping, temporal math. But clinical data has nuance that rules can't catch. This layer uses an LLM to batch-process episodes *before* they enter the context window, producing structured, pre-classified outputs that are cached and reused.

**Why not just rules?**

Rule-based classification works well for clear-cut cases (warfarin → anticoagulant). But it breaks down for:
- **Ambiguous drug purposes:** Methotrexate is an immunosuppressant *or* a chemotherapy agent depending on dose and indication. A rule sees the drug name; an LLM can read the linked condition (rheumatoid arthritis vs. lymphoma) and classify correctly.
- **Clinical relationships between episodes:** A patient started on warfarin 3 months after a DVT diagnosis, then switched to apixaban — that's a treatment narrative. Rules see two separate medication episodes; an LLM sees anticoagulation management for a thromboembolic event.
- **Relevance scoring:** Is a resolved case of acute bronchitis from 8 years ago relevant to a neurosurgery pre-op? A rule can only say "resolved + old = low priority." An LLM can reason about whether the condition has any surgical implications.
- **Dosage interpretation:** "Prednisone 60mg daily" vs "Prednisone 5mg daily" — both are immunosuppressants, but the clinical significance for surgical wound healing is very different. An LLM can flag the high-dose case.

**The batch processing model:**

This is NOT real-time. When a patient record is loaded (or updated), we run a one-time batch enrichment pipeline that processes all episodes through an LLM and caches the results. The enriched data is then available instantly for context building and conversation.

```
Raw FHIR Bundle
    ↓
Layer 0–1: Rule-based filtering + episode compression
    ↓
┌─────────────────────────────────────────────────┐
│         Layer 2: LLM Batch Enrichment            │
│                                                   │
│  Input: Episode objects with temporal metadata    │
│                                                   │
│  Processing (per episode or grouped):             │
│   • Clinical relevance scoring (0–10)             │
│   • Surgical relevance classification             │
│   • Episode narrative summary (1–2 sentences)     │
│   • Cross-episode relationship detection          │
│   • Structured output → cached markdown rows      │
│                                                   │
│  Output: Enriched episodes with LLM annotations   │
└─────────────────────────────────────────────────┘
    ↓
Layer 3–4: Format optimization + persona selection
    ↓
Final context (~450 tokens)
```

**Desired outputs from batch enrichment:**

| Output | Description | Example |
|--------|-------------|---------|
| **Relevance score** | 0–10 rating of how relevant this episode is to surgical planning | Warfarin episode → 10, Acute pharyngitis 2018 → 1 |
| **Relevance rationale** | One-line explanation of why this matters (or doesn't) | "Active anticoagulant — direct bleeding risk for any surgical procedure" |
| **Episode narrative** | 1–2 sentence clinical summary with temporal context | "Patient has been on warfarin 5mg daily since Aug 2019 for atrial fibrillation. Last INR 2.3 (2026-01-15), within therapeutic range." |
| **Cross-episode links** | Relationships between episodes that rules can't detect | "Warfarin prescribed for: Atrial fibrillation (active since 2019)" |
| **Reclassified structure** | Episode data restructured into a compact, LLM-ready row | See format below |

**The reclassified row format:**

The LLM doesn't just score episodes — it produces the final compressed representation. Each episode becomes a structured markdown row that's ready to drop into context:

```markdown
| Drug | Class | Risk | Status | Timeline | Clinical Note |
|------|-------|------|--------|----------|---------------|
| Warfarin 5mg | Anticoagulant | 🔴 CRITICAL | Active 6.6yr | Since 2019-08, last Rx 68d ago | For A-fib. INR 2.3 (in range). HOLD pre-op, bridge with LMWH per protocol. |
| Lisinopril 10mg | ACE Inhibitor | ⚠️ Warning | Active 15yr | Since 2011-03, last Rx 42d ago | For HTN. Well-controlled. Hold morning of surgery. |
| Oxycodone 5mg | Opioid | ⚠️ Warning | Historical | 7 days in 2020-04 | Single post-procedure course. No tolerance concern. |
```

That "Clinical Note" column is where the LLM adds value that rules can't — it synthesizes the indication, current status, relevant lab values, and actionable surgical guidance into one phrase.

**Rule-based vs. LLM: when to use which**

| Task | Approach | Why |
|------|----------|-----|
| Drug name → class mapping | Rules | Deterministic, fast, keyword/code matching is sufficient |
| Active vs. stopped status | Rules | Direct from FHIR status field |
| Temporal metadata (duration, recency) | Rules | Pure date math |
| Episode grouping | Rules | Name normalization + date sorting |
| Relevance to specific clinical scenario | LLM | Requires medical reasoning |
| Cross-episode relationships | LLM | Requires understanding indication chains |
| Dosage significance | LLM | "5mg vs 60mg prednisone" requires clinical context |
| Episode narrative generation | LLM | Natural language synthesis |
| Ambiguous classification | LLM | Same drug, different purpose depending on context |

The general principle: **rules for structure, LLM for meaning.** Rules organize and compress the data; the LLM interprets and annotates it.

**Cost model:**

Using Haiku (fastest, cheapest) for batch enrichment:
- Input: ~200–500 tokens per episode (episode data + classification prompt)
- Output: ~50–100 tokens per episode (structured row + scores)
- Typical patient: 20–60 episodes
- **Cost per patient: ~$0.01–$0.05** (Haiku pricing)
- Complex patient (200+ episodes): ~$0.10–$0.20

This is a one-time cost per patient load. Results are cached and reused across all conversations about that patient. Even at the high end, it's negligible compared to the value of accurate clinical context.

**Batch processing strategies:**

1. **Per-episode classification** — Send each episode individually with a structured prompt. Simple, parallelizable, but misses cross-episode relationships.

2. **Grouped classification** — Send all medication episodes together, all condition episodes together. The LLM can see relationships within each group (e.g., drug A prescribed for condition B).

3. **Full-record pass** — Send the entire compressed record (post Layer 0–1) in one prompt. Most expensive but catches everything — cross-episode relationships, treatment narratives, global relevance scoring. Feasible for most patients at the post-compression token count.

Likely best approach: **grouped classification with a relationship-detection pass.** Run medications and conditions as two batch calls, then one final pass that looks at cross-episode links. Three LLM calls total, parallelizable, and catches the important relationships.

### Layer 3: Format Optimization

Use the most token-efficient format for each data type:

| Data Type | Best Format | Why |
|-----------|-------------|-----|
| Medication list | Markdown table | Structured, scannable, minimal tokens |
| Safety flags | Structured block with icons | Needs to be visually prominent |
| Conditions | Markdown table or one-liners | Structured list |
| Lab values | Markdown table | Tabular data is naturally tabular |
| Patient summary | Natural language sentence | Narrative is most natural here |
| Absence declarations | Simple list | "No X. No Y. No Z." |
| Encounter history | Compressed natural language | "12 wellness visits, 3 ER visits (2018–2025)" |

**Token efficiency benchmarks (same data, different formats):**

| Format | Tokens | vs JSON |
|--------|--------|---------|
| JSON (pretty-printed) | 875 | baseline |
| JSON (compact, one line) | 609 | -30% |
| TOON-style (header + pipe-delimited rows) | 413 | -53% |
| Natural language | 297 | -66% |
| Markdown tables | 188 | -79% |

### Layer 4: Persona-Aware Selection

Different clinicians need different slices. The context builder accepts a persona that controls which sections appear and in what detail.

**Surgical Pre-Op Persona (Max):**
1. Safety flags and hold instructions (top)
2. Active medications with drug class tags
3. Active conditions (one-liner each)
4. Allergies (always, full list)
5. Recent procedures (last 2 years)
6. Absence declarations (which risk classes are NOT present)
7. Historical medication episodes (compressed one-liners)

**Omit for surgical persona:** Immunization history, care plans, goals, routine vitals, wellness encounters.

**Estimated output: ~450 tokens for a complete surgical briefing.**

---

## The RAG Escape Hatch

The initial context is the briefing — optimized for the common case. But clinical conversations are unpredictable. The LLM agent needs a way to pull in more data when the conversation requires it.

### Tool-Based Retrieval Layer

The LLM agent has access to tool functions that query the full patient record on demand:

| Tool | What It Retrieves | When to Use |
|------|-------------------|-------------|
| `get_medication_history(drug_name)` | Full prescription timeline for a specific drug | "Tell me more about their warfarin history" |
| `get_lab_trend(loinc_code, period)` | Time-series lab values | "What's their INR been doing?" |
| `get_encounter_detail(encounter_id)` | Full encounter with all linked resources | "What happened at that ER visit?" |
| `get_condition_detail(condition_code)` | Condition with linked meds and encounters | "Tell me about their diabetes management" |
| `get_procedures(period)` | Procedure list with dates and details | "Any surgeries in the last 5 years?" |
| `search_records(query)` | NL search across all resources | "Has this patient ever had a DVT?" |

### How Initial Context + Tools Work Together

```
┌─────────────────────────────────────────────────────┐
│                  Raw FHIR Bundle                     │
│            (34K – 10.5M tokens per patient)           │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌──────────────────────┴──────────────────────────────┐
│  Layer 0–1: Rule-Based Processing (deterministic)    │
│  Hard filters → Episode grouping → Temporal metadata  │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌──────────────────────┴──────────────────────────────┐
│  Layer 2: LLM Batch Enrichment (one-time, cached)    │
│  Relevance scoring · Clinical narratives ·            │
│  Cross-episode links · Reclassified markdown rows     │
│  Cost: ~$0.01–$0.05/patient · Runs once on load      │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌──────────────────────┴──────────────────────────────┐
│  Layer 3–4: Format + Persona Selection               │
│  Markdown tables · Temporal markers · Absence decl.   │
│  Persona: surgical pre-op, ER, primary care, etc.     │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌──────────────────────┴──────────────────────────────┐
│         Initial Context (~450 tokens)                │
│  Safety flags, active meds, conditions,              │
│  allergies, absences, LLM-generated narratives       │
├─────────────────────────────────────────────────────┤
│    LLM Agent (conversation + reasoning)              │
├─────────────────────────────────────────────────────┤
│         Tool Layer (on-demand RAG)                    │
│  Full patient record available via tool calls         │
│  Episode index, lab trends, encounter details         │
└─────────────────────────────────────────────────────┘
```

The initial context answers 80% of surgical planning questions. The tool layer handles the remaining 20% — follow-up questions, deep dives, and edge cases — without those tokens sitting in context from the start.

This is the key insight: **we don't need to fit everything in the context window. We need to fit the right things in the context window and make everything else one tool call away.**

---

## Existing Work to Build On

### Signal vs. Noise (fhir_explorer)

The `fhir_explorer/views/signal_filter.py` already implements:
- 5-tier resource classification (Always Include → Exclude Default)
- Recency windowing with configurable cutoff
- Token budget estimation per tier
- Plain-text context generation with deduplication
- Absence declarations

This is the general-purpose engine. The patient-journey context builder specializes it for clinical personas.

### Patient Journey Core Modules

Already built in `patient-journey/core/`:
- `drug_classifier.py` — 12 surgical-risk drug classes with severity tiers
- `episode_detector.py` — MedicationEpisode and ConditionEpisode grouping
- `drug_classes.json` — keyword + RxNorm classification rules

### What Needs to Be Built

| Module | Purpose | Status |
|--------|---------|--------|
| `core/temporal.py` | Temporal metadata computation for episodes | Not started |
| `core/batch_enrichment.py` | LLM batch classification, scoring, and narrative generation | Not started |
| `core/context_builder.py` | Main pipeline: filter → compress → enrich → format → select | Not started |
| `core/rag_tools.py` | Tool functions for on-demand record retrieval | Not started |
| `data/enrichment_prompts/` | Structured prompts for batch LLM classification tasks | Not started |
| `data/enrichment_cache/` | Cached LLM enrichment results per patient | Not started |
| Persona configs | JSON/dict configs for different clinical roles | Not started |
| Integration with NL search view | Wire context builder into the chat interface | Not started |

---

## Next Steps

1. **Build `core/temporal.py`** — Compute temporal metadata (first_seen, last_seen, duration, recency, frequency, gaps, trend) for medication and condition episodes. This enriches the episode objects from episode_detector.py.

2. **Build `core/batch_enrichment.py`** — LLM batch processing pipeline. Design the classification prompts (structured output: relevance score, rationale, narrative, cross-episode links). Implement caching so enrichment runs once per patient load. Start with grouped classification (medications batch, conditions batch, then a relationship pass).

3. **Design enrichment prompts** — Create structured prompt templates in `data/enrichment_prompts/` that produce consistent, parseable outputs. The prompts should guide the LLM to produce the reclassified markdown row format directly — each episode becomes a single row with drug, class, risk, status, timeline, and clinical note columns.

4. **Build `core/context_builder.py`** — Implement the full 5-layer pipeline. Orchestrates: hard filters → episode compression → temporal enrichment → LLM batch enrichment → format optimization → persona selection. Falls back gracefully to rule-based-only output if LLM enrichment is unavailable or too slow.

5. **Build `core/rag_tools.py`** — Tool functions that query the full PatientRecord. These become the function-calling tools available to the LLM agent during conversation. The RAG layer is always the backup for anything not in the initial context.

6. **Add a "Context Preview" view** — Similar to Signal vs. Noise but in the Patient Journey app, showing the compressed context with token counts, persona selection, and side-by-side comparison of rule-based vs. LLM-enriched output.

7. **Wire into NL search** — The natural language search view uses the context builder for its system prompt and the RAG tools for follow-up retrieval.

8. **Benchmark and iterate** — Test on complex patients (Robert854_Botsford977), measure token counts, compare rule-based vs. LLM-enriched context quality, verify that temporal questions are answerable from the initial context without tool calls. Track cost per patient across the complexity spectrum.

---

*Last updated: March 29, 2026*
