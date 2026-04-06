# Product Roadmap — EHI Ignite Challenge

> Strategic direction, near-term build priorities, and open questions.
> Last updated: April 5, 2026

---

## Where We Are

The Explorer application is largely feature-complete for the **data review** phase. A clinician can now:

- Pull up any of 1,180 patients in under 300ms
- See their full encounter history with linked resource detail
- Review active conditions ranked by surgical risk
- Check all medications against 10 surgical risk drug classes
- Scan key lab panels with historical trend sparklines
- View their allergy list with cross-reactivity warnings
- Browse immunization and procedure history by year
- Inspect the raw FHIR JSON for any encounter

The corpus-level tools (Corpus page, Field Coverage Profiler) give data analysts visibility into what's actually in the dataset.

---

## The Big Remaining Bet: Patient Journey App

The Explorer was always the warm-up. The real product is the **Patient Journey** view — a clinician-facing application designed for the 30-second chart review scenario. It lives at `/journey` today as a placeholder.

The core insight from our positioning research: clinicians don't need more records. They need the right 5 facts in 30 seconds. The Patient Journey app is that product.

### What it should be

**The 30-second briefing format.** When a surgeon opens a patient chart before a case, they should see:

1. **Surgical Risk Score** — a single composite number (1-10) with the top 3 contributing factors
2. **Critical Medication Alerts** — only the ACTIVE flags that require action (hold warfarin, check INR)
3. **Key Comorbidities** — top 3 conditions by surgical relevance (Cardiac, Pulmonary, Metabolic first)
4. **Recent Labs Summary** — just the values that matter for this case (INR, Creatinine, Hgb, Platelets)
5. **Anesthesia Notes** — OSA, GERD, difficult airway, prior anesthesia complications

This is not a dashboard with 8 sections. It is a clinical briefing card.

### What makes it different from Explorer

| Explorer | Patient Journey |
|---|---|
| Full data transparency | Curated, prioritized briefing |
| All conditions listed | Top 3 surgical risk conditions |
| All medications shown | Only medications that affect the case |
| Raw FHIR accessible | No raw data exposed |
| For analysts | For surgeons |
| Self-service exploration | Push to decision |

---

## Near-Term Build Queue

### High Priority — Complete before Phase 1 demo

**1. Patient Journey MVP** (High complexity)
- Single-page clinical briefing: risk score + top alerts + key labs + anesthesia note
- Should load in <1 second (all data already cached from Explorer)
- Design: card-based, clinical red/amber/green coloring, no prose — bullets only
- The surgical risk score needs a weighting algorithm: CARDIAC=high, PULMONARY=high, ACTIVE anticoagulants=critical, etc.

**2. NL Search / Clinical Q&A** (High complexity)
- Claude Haiku endpoint: `POST /api/patients/{id}/ask`
- Context builder: 5-layer pipeline (demographics → conditions → meds → recent encounters → observations)
- Streaming response to the frontend
- Citation links back to the source encounter/condition/observation
- This is the "wow" feature for the demo

**3. Structured Data Export** (Medium complexity)
- `GET /api/corpus/export?format=csv` — downloads normalized tables
- Patients table, encounters table, conditions table, medications table, observations table
- Enables external research pipelines without re-parsing bundles

### Medium Priority — Phase 2 / Prototype

**4. Drug-Drug Interaction Checker** (High complexity)
- When a patient has multiple active medications, check for known interactions
- Could use a static interaction database (DrugBank, OpenFDA) or Claude-powered lookup
- Surface as alerts in the Safety page and the Patient Journey briefing

**5. Observation Distributions** (Medium complexity)
- Corpus-level: for each LOINC code, show min/max/mean/stdev across all patients
- Per-patient: show where this patient's lab values fall relative to the population
- Useful for "is this patient's creatinine unusually high for this dataset?"

**6. Patient Comparison Mode** (High complexity)
- Multi-select patients in the sidebar
- Side-by-side comparison: complexity score, conditions, medications, lab values
- Use case: researcher comparing a cohort of diabetic patients with cardiac comorbidities

**7. Resource Linkage Graph** (High complexity)
- Interactive visualization: encounters as nodes, resources as edges
- Shows which conditions/observations/procedures are linked to which encounters
- Useful for data quality assessment (orphaned resources = parsing gaps)

---

## LLM Context Engineering Pipeline

The clinical Q&A feature requires a 5-layer context pipeline (documented in `patient-journey/CONTEXT-ENGINEERING.md`):

**Layer 1 — Structured facts** (always included)
Demographics, current medications, active conditions, recent vitals. ~800 tokens. No prose.

**Layer 2 — Risk flags** (always included)
Safety flags from drug classifier + condition acuity ranker output. ~200 tokens.

**Layer 3 — Encounter summary** (recent 5 encounters)
Date, type, reason, linked resource counts. ~400 tokens.

**Layer 4 — Lab context** (when asked about labs/vitals)
Key lab panel values with trend directions. ~300 tokens.

**Layer 5 — Full encounter detail** (on demand)
When the question references a specific visit, inject the full encounter detail. ~1,000 tokens.

Total context budget: ~2,500 tokens per query (leaves room for Claude's reasoning in a 4K window).

The pipeline lives in `api/core/context_builder.py` (TODO) and is called by `api/routers/search.py` (TODO).

---

## Deployment Plan

The app is designed to deploy on a Hetzner CX21 VPS (~€4.85/mo) using Docker Compose + nginx + Let's Encrypt SSL. See `architecture/DEPLOYMENT.md` for full setup.

For the Phase 1 demo (May 13, 2026), we should have a live URL rather than a local demo. This gives judges the ability to explore the app themselves.

**Pre-deployment checklist:**
- [ ] Build `deploy/Dockerfile.api` and `deploy/Dockerfile.app`
- [ ] Configure `deploy/nginx.conf` for SSL termination
- [ ] Test `docker-compose -f deploy/docker-compose.prod.yml up` locally
- [ ] Provision Hetzner server, install Docker
- [ ] Point domain DNS to Hetzner IP
- [ ] Run deploy script, verify SSL cert issued

---

## Open Questions

**1. What is the primary demo patient?**
We need one "showcase patient" who has: active cardiac condition, an anticoagulant, recent labs, multiple encounters, and at least one interesting allergy. Synthea patients are synthetic but we should pick the most compelling one and make sure it renders well in the Patient Journey view.

**2. Should the surgical risk score be rule-based or LLM-generated?**
A rule-based score (weighted sum of condition acuity ranks + active drug class flags) is deterministic and explainable. An LLM-generated score is more nuanced but less defensible. For Phase 1, rule-based is safer. For Phase 2, LLM with citation would be powerful.

**3. What is the right frame for the Phase 1 concept submission?**
Options:
- "Clinical decision support for pre-operative medication review" (narrow, defensible)
- "AI-powered patient briefing for specialist consultations" (broader, more ambitious)
- "FHIR-native clinical intelligence platform" (positioning as infrastructure)

The podcast research suggests the positioning should emphasize the medication safety angle — that's where the EHI data is most actionable and where clinicians feel the most pain.

**4. Real data vs. synthetic data for the demo?**
Synthea data is safe to demo publicly. Real EHI export data (from the sample bulk datasets) would be more compelling but requires careful de-identification verification. The bulk dataset samples in `data/sample-bulk-fhir-datasets-10-patients/` should be explored.

---

## Technical Debt

- **In-memory cache eviction:** The LRU cache holds 30 patients. With 1,180 patients, analysts jumping between many patients will cause cache churn. Consider Redis or a persistent cache for production.
- **Corpus stats endpoint is slow on cold start:** Loading all 1,180 bundles takes ~30-60 seconds on first call. Consider a pre-computed stats file that's refreshed periodically.
- **No authentication:** The API is completely open. For a public demo, this is acceptable. For production clinical use, this needs JWT auth or at minimum IP allowlisting.
- **Error boundaries:** The React app has no global error boundary. A failed API call can crash the page with no recovery. Add a top-level `<ErrorBoundary>` in `App.tsx`.
- **Mobile responsiveness:** The app is designed for desktop (sidebar + main content). It's not usable on mobile. Not a priority for Phase 1 but worth noting.
