# FHIR Agent Context Engineering Report

This report defines how to feed the right chart context to the agent at the right time.

Goal:
- maximize clinical relevance
- minimize context bloat
- preserve traceable citations
- keep responses fast and defensible

## 1) Current State In This Repository

### Parsing source of truth
- `fhir_explorer/parser/bundle_parser.py` parses each FHIR bundle
- `fhir_explorer/catalog/single_patient.py` computes patient stats
- `api/core/loader.py` wraps this with LRU caching (`maxsize=30`)

### Current evidence extraction path
- `api/core/provider_assistant.py`
  - builds facts from:
    - safety flags (drug classes)
    - class-level interactions
    - medications
    - ranked conditions
    - allergies
    - encounters
  - ranks evidence by intent + keyword overlap + fact priority
  - emits short evidence lines + structured citations

### Current agent context path
- Anthropic tools (`api/core/provider_assistant_agent_sdk.py`) call:
  - `get_relevant_provider_evidence(patient_id, query, history, ...)`
- This means agent context is already query-filtered, not raw-bundle injected.

## 2) Core Problem

FHIR bundles contain too much low-signal data for direct LLM context.

Main overload drivers:
- large observation and report volumes
- repeated historical events with low current relevance
- mixed administrative and clinical resources
- broad question phrasing that pulls too much history

Resulting failure modes:
- response drift
- weak prioritization
- excessive token spend
- confidence inflation when evidence is sparse

## 3) Context Architecture (Recommended)

Use a layered context strategy per question.

### L0: Request envelope (always include)
- patient id
- question
- stance
- short conversation window (same patient only)

### L1: Risk snapshot (always include)
- active safety flags
- major/contraindicated interactions
- high-criticality allergies
- active high-risk conditions count
- parse warning count

### L2: Query-focused evidence (always include)
- top-N evidence units ranked for question intent
- each unit includes citation metadata

### L3: Optional deep evidence (conditional)
Only include when question requires detail:
- medication timelines
- encounter-level detail
- condition progression

### L4: Raw resource excerpts (rare)
Only include if unresolved ambiguity remains after L2/L3.

## 4) TUNE-Style Context Packet (Proposed)

Use a structured intermediate packet before LLM call.

```json
{
  "packet_version": "tune.v1",
  "patient_id": "...",
  "question": "...",
  "intent": "preop_safety",
  "context_budget": {
    "max_units": 24,
    "max_tokens_est": 5000
  },
  "summary": {
    "active_flag_count": 2,
    "interaction_count": 1,
    "high_risk_active_condition_count": 3,
    "parse_warning_count": 0
  },
  "evidence_units": [
    {
      "unit_id": "ev-001",
      "kind": "safety_flag",
      "priority": 0.98,
      "freshness_days": 0,
      "text": "Anticoagulants / Blood Thinners (critical) active...",
      "citation": {
        "source_type": "SafetyFlag",
        "resource_id": "safety:anticoagulants",
        "label": "Anticoagulants / Blood Thinners",
        "event_date": null
      },
      "token_est": 75
    }
  ]
}
```

Why this helps:
- deterministic control of context size
- consistent format for deterministic and agentic modes
- explicit prioritization metadata for auditing

## 5) Retrieval and Ranking Policy

Per question:
1. classify intent (`anticoag`, `preop_safety`, `interactions`, etc.)
2. score candidate facts by:
   - base clinical priority
   - lexical overlap
   - intent boost
   - recency boost
3. apply diversity constraints:
   - do not overfill with one resource type
4. enforce context budget:
   - stop at `max_units` and token estimate threshold

Suggested scoring extension (next step):
- add `recency_weight`
- add `evidence_type_balance_penalty`
- add `question_specificity_penalty` (for vague queries)

## 6) Context Switching And Session Safety

### Current control
- Frontend now stores chat history by `patientId` to prevent cross-patient leakage.

### Additional controls to add
1. server-side `session_id` and `patient_id` binding
2. reject requests where history session patient != request patient
3. optionally persist recent turns server-side and ignore client-supplied history for high-trust mode

## 7) Managing Observation/Lab Volume

Observation strategy:
- aggregate first, expand later

Recommended flow:
1. compute panel-level summaries (trend, latest abnormality, severity)
2. include only abnormal/recent/high-impact observations in L2
3. keep full observation history behind on-demand expansion tools

For agent tools, split endpoints into:
- `query_chart_evidence` (summary-first)
- `get_observation_drilldown(loinc, window)` (deferred detail)

## 8) Proposed Implementation Plan

### Phase A (near-term)
- Introduce context packet builder:
  - new module: `api/core/context_packet.py`
- Replace direct evidence dicts with packet schema in Anthropic tool responses.
- Add configurable budget env vars:
  - `PROVIDER_ASSISTANT_CONTEXT_MAX_UNITS`
  - `PROVIDER_ASSISTANT_CONTEXT_MAX_TOKENS_EST`

### Phase B (retrieval quality)
- Add recency and diversity scoring in `provider_assistant.py`
- Add observation summarizer module with abnormality-first filtering

### Phase C (session integrity)
- Add backend session store (`patient_id`, turn window, timestamps)
- Enforce server-side patient/session consistency checks

### Phase D (evaluation)
- Build fixed eval set by patient risk cohorts:
  - low risk, medium risk, high risk, polypharmacy
- Track:
  - citation precision
  - blocker detection recall
  - token usage
  - response latency

## 9) Engineering Guardrails

- Never pass raw full FHIR bundles directly to the model.
- Always include machine-usable citations for every evidence unit.
- Keep deterministic retrieval as source of truth for evidence selection.
- Keep model role focused on synthesis and recommendation, not raw extraction.

## 10) File-Level Ownership Map For Context Work

- Retrieval/ranking: `api/core/provider_assistant.py`
- Agent tool context interface: `api/core/provider_assistant_agent_sdk.py`
- Parser/cache boundary: `api/core/loader.py`
- Personality constraints: `api/agents/provider-assistant/*.md`
- API contract: `api/models.py`, `api/routers/assistant.py`
- UI patient-context handling: `app/src/pages/Explorer/Assistant.tsx`

## 11) Decision Log (Current)

- Decision: Keep deterministic evidence layer as shared substrate for both runtimes.
- Decision: isolate patient chat history at UI boundary.
- Decision: allow Anthropic mode but preserve deterministic fallback for reliability.
- Pending: formalize TUNE-style packet and server-side session controls.
