# Phase 1 Task Queue

Seeded from `docs/JUDGE-WALKTHROUGH.md §4 Prioritized Punch List`. The orchestrator reads this file on every cycle, picks the highest-priority Queued task, classifies it, and dispatches. Never modify this file yourself if you are not the orchestrator.

**Status legend:** `Queued` → `In Progress (dispatched YYYY-MM-DD HH:MM)` → `Completed (hash)` / `⚠ In Progress (failed HH:MM)` / `⛔ Blocked (open question #)`

**Kind legend:** `builder` · `refiner` · `refiner-then-builder`

---

## 🔴 P0 — Demo blockers

### P1-T01 · Fix patient-id contract mismatch
- **Status:** ✅ Completed 2026-04-14 · commit `31789ca` · branch feature/phase1-submission
- **Kind:** builder
- **Rubric target:** Cat 3 Interpretability & Ease of Use (40 pts) · +5 expected
- **Judge quote:** "picking a patient from the sidebar and hitting 'Failed to load patient data.'"
- **Context files:**
  - `CLAUDE.md`
  - `docs/JUDGE-WALKTHROUGH.md` §2 Stop 2 (Clinical Workspace shell) and §4 P0
  - `api/routers/patients.py` (lines 155–196 for `list_patients`, 266–272 for `patient_overview`)
  - `api/core/loader.py` (full file — `load_patient`, `path_from_patient_id`, `patient_id_from_path`)
- **Problem:** `/api/patients` returns bare resource UUIDs via `idx.patient_id` from the corpus cache, but `/api/patients/{id}/overview` resolves the ID against the filename stem. When the corpus cache is live, the contract diverges and every sidebar-driven patient selection 404s. Landing-page cards route correctly because they pass the filename stem.
- **Preferred fix:** resolver-in-loader — add a UUID → filename-stem lookup in `path_from_patient_id` (or upstream in `load_patient`) so both ID shapes work. The public URL stays a clean UUID.
- **Files you may touch:** `api/core/loader.py`, `api/routers/patients.py`
- **Files you must NOT touch:** `fhir_explorer/`, `patient-journey/`, any frontend file
- **Smoke test:**
  ```
  curl -sf http://127.0.0.1:8001/api/patients | python3 -c "import json,sys,urllib.request; d=json.load(sys.stdin); pid=d[0]['id']; print('list id:', pid); r=urllib.request.urlopen(f'http://127.0.0.1:8001/api/patients/{pid}/overview'); print('overview status:', r.status); assert r.status==200"
  ```
- **Acceptance:** both the bare-UUID and filename-stem forms of a patient id return 200 on `/overview` and `/key-labs`.

### P1-T02 · Add "Synthetic data — Synthea R4" posture to the header + landing page
- **Status:** ✅ Completed 2026-04-14 · commit `feae7e5` · branch feature/phase1-submission
- **Kind:** refiner
- **Rubric target:** Cat 4 Privacy, Security, Compliance (15 pts) · +5 expected
- **Judge quote:** "Nothing on-screen says 'this uses synthetic Synthea data, no PHI.' … a judge scoring Cat 4 has nothing to grab onto."
- **Context files:**
  - `docs/JUDGE-WALKTHROUGH.md` §2 Stop 1 (Landing) and §4 P0 item 2
  - `design/DESIGN.md`
  - `app/src/components/Layout.tsx`
  - `app/src/pages/Landing.tsx`
- **What to refine:** Add a small "Synthetic data · Synthea R4" chip next to the "EHI Ignite" wordmark (or a subtle footer line). On the landing page, add a one-line privacy footnote under the hero CTAs: "No PHI. Synthetic Synthea R4 data. Local compute."
- **Files you may touch:** `app/src/components/Layout.tsx`, `app/src/pages/Landing.tsx`, any adjacent CSS/Tailwind config needed for the chip style
- **Files you must NOT touch:** any `.py` file, `api/`, `fhir_explorer/`, test files
- **Before/after check:** screenshot of header + landing page hero, then the same pair after the change. Self-eval: would a Cat-4-scoring panelist now have something to anchor on?

---

## 🟠 P1 — High-impact rubric deltas

### P1-T03 · Consolidate the Clinical Workspace sidebar into three groups
- **Status:** Queued (unblocked 2026-04-14)
- **Kind:** refiner-then-builder
- **Rubric target:** Cat 3 Interpretability & Ease of Use (40 pts) · +3 expected
- **Judge quote:** "15 items directly contradicts '5 facts in 30 seconds.'"
- **Context files:** `docs/JUDGE-WALKTHROUGH.md` §2 Stop 2 and §4 P1 item 3, `app/src/components/Layout.tsx`, `design/DESIGN.md`, `phase1-plan.md` (resolved Q1)
- **Approved groupings (user decision 2026-04-14):**
  - **Pre-op essentials:** Overview · Safety · Interactions · Clearance · Anesthesia
  - **Longitudinal:** Timeline · Care Journey · Patient Journey · Conditions · Procedures · Immunizations
  - **Context & data:** Corpus · Distributions · Assistant
  - **Advanced drawer** (collapsed by default): any views the refiner deems rarely-used after walking the app.
- **What to do:** Refiner pass finalizes section headers, order within each group, and decides which (if any) items move into the Advanced drawer. Builder pass implements the `<aside>` markup with labelled groups and a collapsible Advanced drawer.

### P1-T04 · Inline citations in Assistant answers
- **Status:** Queued
- **Kind:** builder
- **Rubric target:** Cat 5 AI Innovation bonus (+20) · +3 expected
- **Judge quote:** "'Patient is currently taking Naproxen 220 MG' should be linked to the underlying MedicationRequest ID."
- **Context files:** `docs/JUDGE-WALKTHROUGH.md` §2 Stop 5 and §4 P1 item 4, `api/core/provider_assistant.py`, `api/core/provider_assistant_agent_sdk.py`, `app/src/pages/Explorer/Assistant.tsx`
- **What to build:** each claim in the Assistant response carries a `[ref:MedicationRequest/<id>]` anchor that, on hover, shows a popover with the raw FHIR fragment. Retrieval already has the IDs — they just need to be threaded through the response contract.
- **Smoke test:** send the seeded "Is this patient safe for surgery this week?" prompt and assert the response JSON contains at least one `ref` field resolving to a real resource ID.

### P1-T05 · Expand the Surgery Hold banner to show 3–5 action bullets
- **Status:** Queued
- **Kind:** refiner-then-builder
- **Rubric target:** Cat 3 Interpretability & Ease of Use (40 pts) · +2 expected
- **Judge quote:** "'Top concern: Hypertension' is one concern; for a 90/100 complexity patient there are surely more."
- **Context files:** `docs/JUDGE-WALKTHROUGH.md` §2 Stop 3 and §4 P1 item 5, `app/src/pages/Explorer/Overview.tsx`, `api/routers/patients.py` (safety endpoint)
- **Refiner pass:** decide the phrasing template ("Hold NSAIDs 3–5d", "Hold metformin 48h", "No anticoagulants on board"). **Builder pass:** extend the overview response to return up to 5 one-line actions derived from existing safety flags, and render them in the banner.

### P1-T06 · Click-to-reveal medications on Safety cards
- **Status:** Queued
- **Kind:** refiner-then-builder
- **Rubric target:** Cat 3 (40 pts) + Cat 5 (+20) · +2 expected total
- **Judge quote:** "'2 meds' is a count, not an affordance."
- **Context files:** `docs/JUDGE-WALKTHROUGH.md` §2 Stop 4 and §4 P1 item 6, `app/src/pages/Explorer/Safety.tsx`
- **What to do:** the `2 meds` chip becomes a disclosure trigger. Expanded state lists drug name, dose, route, onset date, and a link to the raw FHIR MedicationRequest.

### P1-T07 · Fix landing-page CTA routing ambiguity
- **Status:** Queued
- **Kind:** refiner
- **Rubric target:** Cat 3 (40 pts) · +1 expected
- **Judge quote:** "'Open Clinical Dashboard' and 'Explore the Data' both route to /explorer."
- **Context files:** `app/src/pages/Landing.tsx`, `app/src/App.tsx` (routing), `docs/JUDGE-WALKTHROUGH.md` §2 Stop 1 and §4 P1 item 7
- **What to do:** "Explore the Data" should route to a Data Lab / corpus entry. If that destination doesn't exist yet, pick the most-honest target (`/explorer?view=corpus`) and coordinate naming with the sidebar IA (P1-T03).

### P1-T08 · Explain the complexity score with a tooltip + methodology link
- **Status:** Queued
- **Kind:** refiner
- **Rubric target:** Cat 5 AI Innovation (+20) · +1 expected
- **Judge quote:** "'90/100' needs a tooltip or footnote pointing at the scoring methodology."
- **Context files:** `app/src/pages/Explorer/Overview.tsx`, `fhir_explorer/catalog/single_patient.py` (where `complexity_score` is computed — read only)
- **What to do:** hover tooltip with a 1-paragraph explanation and a link to `/explorer/methodology` (the methodology page, P1-T14).

---

## 🟡 P2 — Polish that compounds

### P1-T09 · Stream Assistant responses
- **Status:** Queued · **Kind:** builder · **Rubric target:** Cat 3 (40) · +1
- **Judge quote:** "Latency from tap-to-answer is ~20–30s … streaming tokens would halve perceived wait time."
- **Context:** `api/routers/assistant.py`, `api/core/provider_assistant_agent_sdk.py`, `app/src/pages/Explorer/Assistant.tsx`

### P1-T10 · Elevate the tool-call chip in Assistant to the top of each answer
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 5 (+20) · +1
- **Judge quote:** "Move it to the top of the response as a clickable 'Chart evidence used: 15 facts / 236 tokens' chip."
- **Context:** `app/src/pages/Explorer/Assistant.tsx`

### P1-T11 · Print pre-op summary button on Safety / Overview
- **Status:** Queued · **Kind:** builder · **Rubric target:** Cat 2 Integration & Scaling (20) · +2
- **Judge quote:** "A 'Print pre-op summary' or 'Copy to handoff note' button would land directly."
- **Context:** `app/src/pages/Explorer/Overview.tsx`, `app/src/pages/Explorer/Safety.tsx`, possibly a new `api/routers/handoff.py` endpoint

### P1-T12 · Microcopy on Opinionated/Balanced and Clinical/Data Lab toggles
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 3 (40) · +0.5
- **Context:** `app/src/components/AgentSettingsPanel.tsx`, `app/src/components/Layout.tsx`

### P1-T13 · Reconcile "Clinical Intelligence Workspace" vs "Clinical Workspace"
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 3 (40) · +0.5
- **Context:** `app/src/components/Layout.tsx`, `app/src/pages/Explorer/*`

### P1-T14 · ~~Methodology page at `/explorer/methodology`~~ **SUPERSEDED**
- **Status:** Closed 2026-04-14 — superseded by P1-T19 (Data Lab / Analysis section UX review pass).
- **Reason:** The Analysis section already contains a Methodology page (`app/src/pages/Analysis/Methodology.tsx`), along with Definitions, Coverage, FlightSchool, and FhirPrimer. Creating a new methodology page in the Clinical workspace would duplicate coverage. The right move is a UX review pass over the existing Analysis section — tracked as P1-T19.

---

## 🟢 P3 — Strategic / research-adjacent

### P1-T15 · ~~Patient View mode (lay-language summaries)~~ **DEFERRED TO PHASE 2**
- **Status:** Deferred 2026-04-14 (user decision — resolved open question #2)
- **Kind:** refiner-then-builder · **Rubric target:** Cat 3 (40) · +3
- **Judge quote:** "Cat 3 explicitly mentions patients and care teams — deferring is leaving points on the table."
- **Reason for defer:** Phase 1 scope is already dense; the user chose to absorb the lost Cat 3 points and focus on making the existing clinician-facing surfaces land harder. Reopen in Phase 2 planning.

### P1-T16 · Small supporting cohort view
- **Status:** Queued (unblocked 2026-04-14)
- **Kind:** builder · **Rubric target:** Cat 2 Integration & Scaling (20) · +3
- **Judge quote:** "A cohort screen showing risk flags across the 1,180-patient corpus would directly answer Cat 2's multi-patient scalability criterion."
- **Scope (user decision 2026-04-14):** **Small and supporting, not a centerpiece.** The product's identity stays single-patient pre-op review. One page, one table: all 1,180 patients with their complexity tier, active critical flags, and a "View" link that drops into the single-patient Overview. Filter by critical-flag presence and by complexity tier. No heavy aggregation charts. The page exists purely so a judge scoring Cat 2 can answer "does this scale to a cohort?" with "yes — click here."
- **Context files:** `api/routers/patients.py` (`/risk-summary` endpoint already exists — wire it into a new page), `app/src/pages/` (new), `docs/JUDGE-WALKTHROUGH.md` §4 P3 item 16

### P1-T17 · Medication reconciliation across providers (mock or live)
- **Status:** Queued · **Kind:** builder · **Rubric target:** Cat 2 (20) + Cat 1 (25) · +3
- **Judge quote:** "The headline use case FHIR uniquely enables."
- **Context:** `api/core/` (new module), design mockup first

---

## New tasks — added 2026-04-14 from Q&A round 1

### P1-T18 · Audit the Overview page audience and clean it up
- **Status:** ⛔ Blocked (open question #5 — Overview audience decision)
- **Kind:** refiner-then-builder
- **Rubric target:** Cat 3 Interpretability & Ease of Use (40 pts) · +3 expected
- **User concern (2026-04-14):** "The patient summary page is not useful. We're really just talking about the main chart on that. It just reaches resources that are a fit if it is a fit, and there is IR data on there." Paraphrased: the Overview page renders stat cards, demographics, data span, and a resource-distribution chart, and none of those work hard enough for any single audience. Before touching layout, decide who the page is *for*.
- **Context files:** `app/src/pages/Explorer/Overview.tsx`, `api/routers/patients.py` (overview endpoint, lines 266+), `design/DESIGN.md`, `phase1-plan.md` (open question #5), `docs/JUDGE-WALKTHROUGH.md` §2 Stop 3
- **Blocker:** open question #5 — pick (a) Surgeon briefing, (b) Reviewer / data completeness, or (c) two-page toggle. Until that's answered, the refiner has nothing to anchor the layout decisions against.
- **Post-unblock plan:**
  - **Refiner pass 1:** produce a wireframe screenshot of the chosen direction, annotate which blocks get promoted / demoted / removed, and self-evaluate against Cat 3.
  - **Builder pass:** implement the new block order, extend the overview endpoint with any new fields needed (e.g. actions list if (a) is chosen — this overlaps with P1-T05, so sequence P1-T05 first).
  - **Refiner pass 2:** copy polish on the new blocks.
- **Sequencing note:** P1-T05 (expand Surgery Hold banner with action bullets) should land **before** this task if the user picks option (a), since the action bullets become the new top of the Overview.

### P1-T19 · ~~Data Lab / Analysis section UX review pass~~ **SUPERSEDED**
- **Status:** Closed 2026-04-14 — superseded by DL-T01 → DL-T15 after the Data Lab walkthrough landed.
- **Reason:** This task was a placeholder for "walk the Data Lab and see what's there." The walkthrough has happened (`docs/JUDGE-WALKTHROUGH-DATALAB.md`) and produced a concrete, prioritized list of 15 ship-able tasks. Dispatching T19 would be redundant with DL-T01 → DL-T15.

### P1-T20 · ~~Second judge walkthrough — Data Lab / Analysis section~~ **COMPLETED**
- **Status:** Completed 2026-04-14 — orchestrator performed the walk and wrote `docs/JUDGE-WALKTHROUGH-DATALAB.md`.
- **Output:** 15 new ship-able tasks (DL-T01 → DL-T15) added to this queue. Scorecard revised upward in `phase1-plan.md`. P1-T19 closed as superseded.

---

## Data Lab tasks — added 2026-04-14 from `docs/JUDGE-WALKTHROUGH-DATALAB.md`

> All DL-* tasks trace to a specific section and judge quote in the Data Lab walkthrough. Priority tags follow the same 🔴/🟠/🟡/🟢 convention.

### 🟠 P1 — High-impact Data Lab deltas

#### DL-T01 · Fix Coverage page first-paint placeholders
- **Status:** Queued · **Kind:** builder
- **Rubric target:** Cat 3 Interpretability (40 pts) · +1 expected
- **Judge quote:** "A reviewer who skims the page for 5 seconds will see placeholders everywhere, conclude the page is broken, and leave."
- **Context files:** `app/src/pages/Analysis/Coverage.tsx`, `api/routers/` (whichever endpoint serves coverage data), `docs/JUDGE-WALKTHROUGH-DATALAB.md` §2 Stop 6
- **What to build:** Replace literal `...` and `Loading field coverage...` / `Loading allergy profile...` / `Loading top substances...` text with non-textual skeleton bars. Prefer a single endpoint that returns all four stat cards + the field list in one response so first paint is substantive.
- **Smoke test:** `curl -sf http://127.0.0.1:8001/api/<coverage-endpoint>` returns 200 with `patients_profiled > 0` in the first paint payload, and the page never renders the literal string "Loading" in production.

#### DL-T02 · Surface the Data Lab from Clinical entry points
- **Status:** Queued · **Kind:** refiner-then-builder
- **Rubric target:** Cat 3 (40) +2 · Cat 5 AI Innovation (+20) +2 · +4 expected total
- **Judge quote:** "The best explainability content in the submission is invisible to a reviewer who only walks the Clinical side."
- **Context files:** `app/src/pages/Explorer/Safety.tsx`, `app/src/pages/Explorer/Assistant.tsx`, `app/src/pages/Explorer/Overview.tsx` (empty state when no patient), `docs/JUDGE-WALKTHROUGH-DATALAB.md` §6 Takeaway 3
- **What to do:** Refiner pass finalizes the exact phrasing and placement of three entry points — (a) "Why you can trust these flags — see Methodology →" chip on Safety Panel cards, (b) "4 sections" text in the Assistant's tool-call chip becomes a link to `/analysis/methodology`, (c) a "First time here? Take the 15-minute Flight School →" banner on the Clinical empty state. Builder pass ships them.
- **Why this is the highest-ROI Data Lab task:** turns a hidden rubric asset into a visible one without writing new content.

#### DL-T03 · Pipeline diagram on Methodology page
- **Status:** Queued · **Kind:** refiner-then-builder
- **Rubric target:** Cat 5 (+20) · +2 expected
- **Judge quote:** "Five named layers with typed inputs and outputs begs for a visual."
- **Context files:** `app/src/pages/Analysis/Methodology.tsx`, `docs/JUDGE-WALKTHROUGH-DATALAB.md` §2 Stop 4
- **What to do:** Refiner pass designs an SVG diagram of Layer 0 → Layer 4 showing typed inputs and outputs, plus a worked example traced through it — use the Naproxen example from §2 Stop 4 of the walkthrough: *"Naproxen 220 mg → Layer 0 kept it → Layer 1 folded 3 refills into one episode → Layer 2 tagged it NSAID::active → Layer 4 surfaced 'Hold 3–5 days pre-op'."* Builder pass implements the SVG (or an `<img>` if a graphic is easier).
- **Verification:** before/after screenshot pair and a self-eval against Cat 5 — would a reviewer now understand the pipeline without reading the bullet list?

#### DL-T04 · Annotate Coverage page data-source limitations
- **Status:** Queued · **Kind:** refiner
- **Rubric target:** Cat 5 (+20) +1 · Cat 4 Privacy (15) +1 · +2 expected
- **Judge quote:** "Being candid about the corpus's limits is a Cat 5 win."
- **Context files:** `app/src/pages/Analysis/Coverage.tsx`, `docs/JUDGE-WALKTHROUGH-DATALAB.md` §2 Stop 6
- **What to refine:** Add footnotes to the "High Criticality Patients = 0" stat card and the "Allergy Category Mix: food 567" block, each explicitly stating that this reflects a Synthea R4 corpus characteristic, not a product gap. The note on allergies should end with: "On a real EHR corpus, this page would also surface moderate- and high-criticality allergies and drive the pre-op allergy-warning path."

#### DL-T05 · Flight School "run this lesson" button
- **Status:** Queued · **Kind:** refiner-then-builder
- **Rubric target:** Cat 3 (40) · +1 expected
- **Judge quote:** "The friction is 1 click too many."
- **Context files:** `app/src/pages/Analysis/FlightSchool.tsx`, `app/src/pages/Explorer/Assistant.tsx` (for prefilled prompt wiring), `docs/JUDGE-WALKTHROUGH-DATALAB.md` §2 Stop 3
- **What to do:** Each lesson card gains a primary button that pre-navigates to the right view *and* pre-fills the exercise's Assistant prompt, so the reviewer taps once to run the lesson. Refiner picks the button labels and prompt strings; builder wires the routing + query-string handoff into Assistant.

### 🟡 P2 — Data Lab polish that compounds

#### DL-T06 · Right-rail TOC on FHIR Primer
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 3 (40) · +0.5
- **Judge quote:** "At this length, a right-rail TOC is table-stakes."
- **Context:** `app/src/pages/Analysis/FhirPrimer.tsx`

#### DL-T07 · Rename /analysis H1 and reconcile page titles
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 3 (40) · +0.5
- **Judge quote:** "Two different headings for the same surface creates micro-doubt."
- **Context:** `app/src/pages/Analysis/Overview.tsx`, `app/src/components/Layout.tsx`

#### DL-T08 · Flight School progress persistence
- **Status:** Queued · **Kind:** builder · **Rubric target:** Cat 3 (40) · +0.5
- **Judge quote:** "A reviewer refreshing the page or using a different browser loses state."
- **Context:** `app/src/pages/Analysis/FlightSchool.tsx`; minimally localStorage with a namespaced key, or a tiny `/api/flight-school/progress` endpoint

#### DL-T09 · Reverse index from Clinical surfaces to Definitions
- **Status:** Queued · **Kind:** refiner-then-builder · **Rubric target:** Cat 5 (+20) · +1
- **Judge quote:** "Every Clinical surface should carry a small `?` chip that links into this page at the specific definition it was rendered from."
- **Context:** `app/src/pages/Explorer/Overview.tsx`, `app/src/pages/Explorer/Safety.tsx`, `app/src/pages/Analysis/Definitions.tsx`, `app/src/components/` for a shared `<DefinitionLink>` component

#### DL-T10 · Methodology link inside Assistant tool-call chip
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 5 (+20) · +0.5
- **Judge quote:** "The 'sections' text should be a link to `/analysis/methodology#layers`."
- **Context:** `app/src/pages/Explorer/Assistant.tsx`
- **Note:** overlaps with DL-T02 part (b) — ship together.

#### DL-T11 · Live-data hover on FHIR Primer JSON examples
- **Status:** Queued · **Kind:** builder · **Rubric target:** Cat 3 (40) +1 · Cat 5 (+20) +1 · +2 expected
- **Judge quote:** "Collapses Primer + Coverage into one unified reviewer experience and would unambiguously be the best page of the submission."
- **Context:** `app/src/pages/Analysis/FhirPrimer.tsx`, whichever endpoint serves Coverage data, a new `<FieldWithCoverage>` component
- **Note:** depends on DL-T01 (Coverage endpoint must be first-paint-stable).

#### DL-T12 · Completion payoff on Flight School
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 3 (40) · +0.5
- **Judge quote:** "An end state after Lesson 5 that closes the curriculum loop."
- **Context:** `app/src/pages/Analysis/FlightSchool.tsx`

### 🟢 P3 — Strategic / research-adjacent

#### DL-T13 · Clinical/Data Lab toggle mode label
- **Status:** Queued · **Kind:** refiner · **Rubric target:** Cat 3 (40) · +0.5
- **Note:** Overlaps with Clinical-side P1-T12. Coordinate so one task ships both pieces.

#### DL-T14 · Phase 2 "For patients" mode architecture note
- **Status:** Deferred to Phase 2 · **Kind:** note-only
- **Note:** The Data Lab pattern (separate mode, separate theme, separate sidebar) is the right shape to accept a third "For patients" mode when P1-T15 reopens.

#### DL-T15 · Desktop viewport verify of all Data Lab pages
- **Status:** Queued · **Kind:** meta (orchestrator-native)
- **Rubric target:** protects DL-T01 → DL-T12 from shipping based on mobile-viewport assumptions
- **Judge quote:** "Every Data Lab layout and density judgment in §2 is un-verified at desktop widths."
- **What to do:** The orchestrator performs a focused re-walk of all six Analysis pages at 1440×900, captures screenshots, and patches `docs/JUDGE-WALKTHROUGH-DATALAB.md` with any desktop-specific findings. Any new bugs or polish items surfaced become sub-tasks appended to this queue.
- **Why meta:** same logic as P1-T20 — walkthroughs produce the source of truth that polish/feature tasks cite, so they are orchestrator-native and do not go through builder/refiner sub-agents.

---

## Completed

*(Empty — the orchestrator appends here as tasks close.)*
