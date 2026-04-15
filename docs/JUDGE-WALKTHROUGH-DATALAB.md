# Judge Walkthrough — Data Lab / Analysis Section

**Walked:** 2026-04-14 on local dev (`http://localhost:5173` against API on `:8001`)
**Lens:** Panelist scoring against the official [ehignitechallenge.org](https://ehignitechallenge.org/) rubric.
**Companion to:** [`docs/JUDGE-WALKTHROUGH.md`](./JUDGE-WALKTHROUGH.md) — this doc covers the six pages under `app/src/pages/Analysis/` that the first walkthrough did not touch. Conclusions in §3 update the scorecard in the companion doc.

**Viewport caveat:** the preview tool rendered at a ~531px viewport, which puts these pages in their mobile/tablet breakpoint. Copy, structure, and hierarchy were evaluated via `innerText` and DOM inspection (viewport-independent). Visual density, line length, and multi-column layout judgments will need a desktop re-verify before anything ships — see finding DL-F1.

---

## 1. Why this walkthrough exists

The first walkthrough covered the Clinical workspace (`/explorer/*`). It left the Data Lab side — toggled via the top-right "Clinical / Data Lab" pill — entirely uncovered. The user pointed out in the 2026-04-14 Q&A round that an existing Methodology page lives here and that the whole section needs a thorough UX pass. This doc is that pass, performed as a judge.

The Data Lab is a bigger strategic deal than I initially thought. It is the product's **public-facing interpretability and trust surface** — the thing a reviewer visits to answer "is this team serious about what they claim to do with FHIR?" That question maps directly to the two heaviest rubric categories:

- **Cat 5 (AI Innovation, +20 bonus)** rewards "transparent, explainable AI methods."
- **Cat 3 (Interpretability & Ease of Use, 40 pts)** rewards "novelty in making EHI actionable and readable" for "clinicians, patients, care teams."

If the Data Lab reads well to a reviewer, we recover several points the Clinical walkthrough left on the table.

---

## 2. The Walk-through

### Stop 1 — Data Lab Overview (`/analysis`)

**What a judge sees:** the header shifts from "Clinical Intelligence Workspace" to "**Data Analysis & Methodology Environment**" and the theme tints mint/teal to signal "you are in a different mode." Left sidebar has six entries (Overview, FHIR Primer, Flight School, Methodology, Definitions, Coverage), each with a tight one-line subtitle. A "Corpus Snapshot" panel up top shows `Patients 1,180 · Resources 527,113`. The main pane opens with a "DATA REVIEW ENVIRONMENT" badge and an H1 "FHIR Data Definitions and Methodology."

The body lays out:
- Three **learning goals** (understand bundle contents, map clinical questions to fields, separate trustworthy from sparse signals)
- **Four corpus stats:** 1,180 patient bundles · 46,868 encounters · 527,113 resources · 1.8 avg active meds
- **Data-to-Insight Pipeline** — four numbered stages (Ingest → Structure → Interpret → Explain), each with a 1-line description and a typed "Output" line
- **Clinical Question Mapping** — three example questions ("Is this patient safe for surgery this week?", "What changed recently that I should care about?", "Which fields are dependable vs sparse?") each mapped to the specific FHIR resources they touch
- **"What this section covers" / "Why it matters" / "Guardrails"** — three explanatory blocks
- **Killer line, verbatim:** *"We treat absence as a first-class signal: no active anticoagulants, no high-criticality allergies, and no recent adverse trends must be represented explicitly, not implied."*

**Strengths**
- ✅ **The framing sentence.** "Absence is a first-class signal" is the kind of phrase a panelist writes down. It signals methodological maturity better than any feature list could.
- ✅ **The pipeline diagram is rubric-perfect.** Four named stages, each with a typed output. A Cat 5 judge has an instant answer to "how do you make this explainable?" — you show them the pipeline.
- ✅ **Clinical Question Mapping** preempts the "what is this actually for?" critique. It takes three real clinician questions and maps each to the specific FHIR resources that answer them. This is the single clearest artifact of Cat 1 (Relevance) alignment anywhere in the app.
- ✅ **Corpus numbers are specific and real** — 1,180 / 46,868 / 527,113 / 1.8. Not "thousands of records" hand-waving.
- ✅ **Mint/teal mode theme change** is a subtle but effective cue that this is a *different product* — the "public-facing tutorial surface" language in the body reinforces it.

**Issues**
- ⚠️ **No link from the Clinical side to here.** A judge who enters via the landing page's "Open Clinical Dashboard" CTA has no reason to know this section exists unless they notice the Clinical/Data Lab toggle in the top-right. If the Data Lab is where the heavy rubric points live, we should surface a "Why you can trust these flags — see Methodology →" link directly from the Safety Panel and the Assistant response.
- ⚠️ **The H1 is "FHIR Data Definitions and Methodology" on a page called Overview.** Two different headings for the same surface creates micro-doubt. The page is the *orientation / goals* page; call it that.
- ⚠️ **"Data-to-Insight Pipeline"** is a slightly corporate phrase. "How a FHIR bundle becomes a surgical briefing" would land harder.

---

### Stop 2 — FHIR Primer (`/analysis/fhir-primer`)

**What a judge sees:** an H1 "Understanding the Data: FHIR R4 from the Ground Up," an introduction that names the **21st Century Cures Act** and the **ONC information-blocking rules** by name, then a numbered outline starting with "1. What is FHIR?" and building out through "2. Anatomy of a FHIR Bundle" (with real JSON pulled verbatim from the corpus) and "3. Core Resource Types — Real JSON Examples." A "Typical resource distribution in a single patient bundle" table shows per-resource-type ranges: Observation ~250–1,300 (60–70%), DiagnosticReport ~50–130, Encounter ~20–110, Claim/EOB ~40–220, Procedure ~10–40, Condition ~5–20, MedicationRequest ~3–15, Immunization ~8–15.

**Strengths**
- ✅ **This is the single most differentiated page in the submission.** Most EHI Ignite entries will assume the judge already knows FHIR. This one teaches it — from "what is a Bundle" through actual JSON examples pulled from the corpus — and it does so in the *product itself*, not in the submission PDF.
- ✅ **Citing Cures Act and ONC information-blocking rules by name** signals regulatory fluency. Cat 4 (Privacy/Compliance) judges will notice.
- ✅ **"This is exactly what the raw data looks like before our parser normalizes it."** Provenance of the examples is explicit — a judge can trust they are not sanitized.
- ✅ **Resource-type ranges table** sets correct expectations. Observation at 60–70% of every bundle is a non-obvious fact that will stick.
- ✅ **"Observation resources dominate every bundle. A single encounter can generate 10–30 observations. This is normal — not noise."** Pre-empting a reviewer complaint before they make it is the mark of a confident submission.

**Issues**
- ⚠️ **Length risk.** The page is dense — a reviewer with 10 minutes may bounce before reaching the JSON examples. Consider a "Tl;dr — three things you need to know about FHIR bundles" card at the very top.
- ⚠️ **No TOC / jump links.** At this length, a right-rail TOC is table-stakes for document UX. With sections numbered 1, 2, 3 this is a 15-minute fix.
- ⚠️ **The JSON examples in the doc are rendered as static `<pre>` blocks (presumably).** If we made them *live* — hover over a field name to see its coverage % pulled from the Coverage page — we'd collapse three pages (Primer, Definitions, Coverage) into one unified experience and it would unambiguously be the best page of the submission.

---

### Stop 3 — Flight School (`/analysis/flight-school`)

**What a judge sees:** an H1 "Learn the data model, then make clinical decisions with confidence," a `PROGRESS 0% · 0 of 5 lessons completed` bar, then a "Mode / Outcome / Personality Target" introduction block, then five lessons as cards:

1. **Orientation: Know Your FHIR Ground Truth** — 3 source facts (identity, timeline scope, active treatment)
2. **Temporal Reasoning: What Is Active vs Historical** — compare most-recent encounter to prior year
3. **Safety Logic: Drug Classes and Interactions** — draft a pre-op hold/monitor plan
4. **Reliability: Don't Over-Trust Sparse Fields** — pick two fields <70% coverage, explain confidence impact
5. **Provider Chat: Ask, Verify, Decide** — use retrieval while keeping evidence explicit

Each lesson has: **Why this matters · Exercise · Complete when · Jump to views · Prompt ideas · Mark complete**.

**Strengths**
- ✅ **This page is a strategic lever.** Most Phase 1 submissions hand the reviewer an app and say "evaluate it." This one hands them an **evaluation curriculum**. It literally tells the judge what to click and what to conclude. That is a pattern most submissions will not have.
- ✅ **"Jump to views"** on every lesson — each lesson has direct links into the Clinical workspace. The Data Lab isn't a dead-end tutorial, it is a *front door* that then pushes the reviewer into the live surfaces.
- ✅ **"Prompt ideas"** on each lesson — these are pre-loaded Assistant prompts that showcase the strongest Assistant behavior. A lazy reviewer will use them verbatim and see the app at its best.
- ✅ **"Personality Target: Direct, concise, responsive, and willing to challenge unsafe assumptions."** Makes the Assistant's behavior a declared contract, not a surprise.
- ✅ **Lesson 4 ("Don't Over-Trust Sparse Fields") is the most unusual page in the whole submission.** It actively instructs the reviewer to find places the app *should push back* — signaling the team values honesty over demo-polish. Cat 5 eats this up.

**Issues**
- ⚠️ **Progress tracking appears local-only.** "0 of 5 lessons completed" suggests localStorage; a reviewer refreshing the page or using a different browser loses state. For a submission video you want the progress bar to visibly advance, then persist across reloads.
- ⚠️ **No way to start Lesson 1 in place.** Each lesson has a "Jump to views" link but no embedded sample question or prefilled Assistant prompt. The friction is 1 click too many — if the exercise is "ask the Assistant 'what are the top 5 facts I should know about this patient before pre-op planning?'", the card should have a button that does exactly that with one tap.
- ⚠️ **No indication of who should take this.** A one-line subhead like "For reviewers evaluating this submission · ~15 minutes" would anchor the audience.
- ⚠️ **"Mark complete" buttons are present but there's no payoff for completing all five.** A "You've finished Flight School — submit your review with confidence" end state would close the loop and make the curriculum feel deliberate.

---

### Stop 4 — Methodology (`/analysis/methodology`)

**What a judge sees:** an H1 "How We Interpret FHIR for Clinical Use Cases," then a four-bullet design-principles block:

- **Lead with safety-critical signal** — anticoagulants, antiplatelets, immunosuppressants, active high-risk conditions, adverse labs
- **Time is the primary lens** — `first_seen`, `last_seen`, `duration`, `recency`; UI favors NOW/RECENT before historical detail
- **Compress without losing auditability** — MedicationRequest → episodes, each episode retains source refs
- **Declare absences explicitly** — "no active anticoagulants" is a rendered state, not a silence

Then a **Pipeline Layers** block: Layer 0 (Hard Filters) → Layer 1 (Episode Compression) → Layer 2 (Deterministic Interpretation) → Layer 3 (Batch Enrichment — planned) → Layer 4 (Context Assembly).

Then a **Quality and Interpretability Gates** block: every risk flag maps to an explicit source record set; low-coverage fields are tagged; temporal contradictions are parse warnings; methodology is deterministic-first, probabilistic-second.

**Strengths**
- ✅ **This is the page I should have linked in my Clinical walkthrough as the answer to "how do you explain the complexity score."** It exists. It's rigorous. It names specific drug classes, specific temporal fields, specific layers, specific quality gates.
- ✅ **"Rules-first interpretability"** is a thesis statement. Cat 5 rewards submissions that have a stance; this has a stance.
- ✅ **"The methodology layer is deterministic first; probabilistic enrichment is additive."** Reads like a pre-emptive response to the "LLMs hallucinate" objection. A judge evaluating AI innovation will score this directly.
- ✅ **Layer 3 marked `(planned)`** — the page is honest about what's implemented and what isn't. Better to signal this explicitly than to let a reviewer wonder.

**Issues**
- ⚠️ **No diagram.** Five named layers with typed inputs and outputs *begs* for a visual. Even an SVG rectangle stack with arrows would quintuple retention. Today it's a bullet list of bullet lists.
- ⚠️ **No concrete example.** The page describes the pipeline abstractly but never walks a *specific record* through it. A sidebar showing "Naproxen 220 mg → Layer 0 kept it → Layer 1 folded 3 refills into one episode → Layer 2 tagged it NSAID::active → Layer 4 surfaced 'Hold 3–5 days pre-op'" would be the single most convincing content in the submission.
- ⚠️ **"Batch Enrichment (planned)"** is shown with no date or commitment. If Phase 2 is where it lands, say so inline.
- ⚠️ **Not linked from the Assistant response.** When the Assistant shows its `build_clinical_context` tool call, "4 sections" should link to this methodology page.

---

### Stop 5 — Definitions (`/analysis/definitions`)

**What a judge sees:** an H1 "Canonical Data Definitions" and an opening line that reads like a software contract: *"These definitions are the contract between ingestion and product logic. If a feature cannot map to one of these canonical fields or derived definitions, we treat it as speculative and out-of-scope for clinical decision support."*

Below: a table with four columns — `RESOURCE | CORE FIELDS | INTERPRETATION | USED BY` — covering `PatientRecord.summary`, `EncounterRecord`, `MedicationRecord`, `ConditionRecord`, `ObservationRecord`, `ProcedureRecord`, `ImmunizationRecord`, `AllergyRecord`. Each row names the actual typed fields (`clinical_status`, `onset_dt`, `loinc_code`, `value_quantity`), the interpretation role, and which downstream product surfaces consume it.

Then **Derived Definitions**: Medication Episode, Risk Tier, Safety Flag, Field Coverage Label — each with Source → Output.

Closing with a **Traceability Rule**: *"Every insight must trace back to one of three layers: canonical parser fields, deterministic derived definitions, or documented enrichment output. This is the baseline for explainability and for contest reviewers validating methodological rigor."*

And a **Practical check**: *"If a UI element has no field-level lineage, mark it as prototype-only and keep it out of clinical action paths."*

**Strengths**
- ✅ **"Contract between ingestion and product logic"** — this is how a mature platform team talks. Judges who have evaluated mid-pack Phase 1 submissions elsewhere will register this as a level-up.
- ✅ **Table with USED BY column** is the thing that pulls it all together. Every field has a named downstream consumer. This is how you prove the data model is not academic.
- ✅ **"Contest reviewers validating methodological rigor"** — the doc explicitly acknowledges the reviewer is the reader. That is a self-aware, high-confidence move.
- ✅ **Traceability Rule is the thesis.** "Every insight traces back to canonical parser / deterministic derived / documented enrichment." Three-way partition, each layer is named on this page or a sibling page. Cat 5 is answered as thoroughly as I've seen in any submission of any type.

**Issues**
- ⚠️ **Dense wall of table.** At desktop width this is probably fine; at mobile (where I saw it) the table clearly overflows. Need a desktop verify, and possibly card-ify the table for narrow viewports.
- ⚠️ **No search / filter on the table.** Eight resource rows today, but if the schema grows, a filter becomes necessary.
- ⚠️ **"Derived Definitions" is stored in different markup from the resource table.** Consistency: render derived definitions in the same row format as canonical, with a "(derived)" badge. Right now it reads like two different authors glued their sections together.
- ⚠️ **No reverse index.** Every Clinical surface — Overview, Safety, Timeline — should carry a small `?` chip that links into this page at the specific definition it was rendered from.

---

### Stop 6 — Coverage (`/analysis/coverage`)

**What a judge sees:** an H1 "Field Coverage and Data Quality Signals" and a short opener that explains coverage is derived from corpus-level prevalence. Four stat cards: `Patients Profiled 1,180 · Fields Tracked 21 · Allergy Records 567 · High Criticality Patients 0`. Below, fields grouped by resource type with coverage %, tier (Always / Usually / Rarely), and the literal count (e.g. `Present in 1,153 of 1,180 patients`). Bottom: "Fields Requiring Caution" block — currently `medication.dosage_text — 0.0% coverage`. Then an "Allergy Category Mix" block showing `food 567`, and a "Top Allergy Substances" list (Allergy to mould 77, Dander 73, Grass pollen 64, Tree pollen 61, House dust mite 57, Shellfish 53, Nut 26, Fish 25 — all `criticality: low`).

**Strengths**
- ✅ **"Fields Requiring Caution" surfaces its own gaps.** The page volunteers that `medication.dosage_text` is 0.0%. This is the opposite of a vanity dashboard — it shows a judge the weak spots up front.
- ✅ **Tier labels (Always / Usually / Sometimes / Rarely)** are a clean abstraction layer over raw percentages. A reviewer can scan for "Rarely" rows faster than for "<50%" rows.
- ✅ **"Present in 1,124 of 1,180 patients"** — using the absolute count alongside the percentage builds trust. Percentages alone feel hand-wavy; `1124/1180` does not.
- ✅ **21 fields tracked is enough to feel thorough without being overwhelming.**

**Issues**
- 🚨 **First-paint is a broken-looking skeleton.** On initial load, all four stat cards show `...` and three sub-sections show `Loading field coverage...` / `Loading allergy profile...` / `Loading top substances...`. Content fills in after ~3s. A reviewer who skims the page for 5 seconds will see placeholders everywhere, conclude the page is broken, and leave. Fix: render the stat cards with actual values in the first paint (they come from the same endpoint, probably a single request — server-side render or a skeleton that doesn't use the literal word "Loading").
- ⚠️ **`High Criticality Patients = 0`** is unexplained. Is this because the Synthea corpus doesn't generate high-criticality allergies, or because our processing pipeline isn't tagging them? The page should footnote which.
- ⚠️ **`Allergy Category Mix: food 567`** — single-category mix is a silent red flag. Synthea generates only food-category allergies? If so, say it: *"Note: Synthea R4 generates food-category allergies exclusively — this corpus does not exercise environmental or medication-allergy processing."* That's a perfect Cat 5 move because it is candid about a data-source limitation.
- ⚠️ **Top allergy substances are all `criticality: low`.** Same issue — if the corpus has no moderate/high criticality, we should say so, and note what the pre-op workflow would do differently on a real EHR corpus.
- ⚠️ **No per-patient drill-down.** "Present in 1,153 of 1,180 patients" — clicking "1,153" should open a list of those patients. "1,180 / 1,180" doesn't need a drill, but the <100% fields do.
- ⚠️ **No field-level provenance.** For each row, a "See this field in raw FHIR" link would make Cat 5 a slam dunk.

---

## 3. Updated Scorecard — The Data Lab Moves the Numbers

The first walkthrough scored the submission at **78 / 100 + 14 bonus = 92 / 120** on Clinical surfaces alone. Incorporating the Data Lab content as a panelist who reads both sides changes several cells:

| Category | Weight | Clinical-only | With Data Lab | Delta | Why |
|---|---:|---:|---:|---:|---|
| 1. Relevance & Problem Alignment | 25 | 20 | **22** | +2 | "Clinical Question Mapping" on `/analysis` explicitly ties three real clinician questions to the FHIR resources that answer them. |
| 2. Integration & Scaling | 20 | 10 | **11** | +1 | Definitions page names `USED BY` for every canonical field — modest scaling signal but not a big lift. |
| 3. Interpretability & Ease of Use | 40 | 27 | **32** | +5 | Flight School is genuinely novel interpretability-as-curriculum. FHIR Primer teaches reviewers the format in-product. Both land hard on "novelty in making EHI actionable and readable." |
| 4. Privacy, Security, Compliance | 15 | 7 | **9** | +2 | FHIR Primer cites Cures Act and ONC information-blocking rules by name. Still no explicit "synthetic data · no PHI" posture (fixed by P1-T02). |
| 5. Bonus: AI Innovation | +20 | +14 | **+18** | +4 | Methodology page articulates a "rules-first, deterministic-first" thesis. Definitions page publishes a Traceability Rule. Coverage page declares its own gaps. All three land on "transparent, explainable AI methods." |
| **Total** | **120** | **92** | **104** | **+12** | |

**Revised baseline: ~92 / 100 + 18 bonus = 104 / 120**, before any P1 or P2 queue work lands.

This is a meaningful upward revision. The Data Lab is carrying weight I did not credit it with in the first pass, and that changes the prioritization: **P1-T14 was the right task to close** (methodology page already exists), but it means Phase 1 polish should aggressively *surface* the Data Lab to Clinical-side reviewers, not build duplicate content inside the Clinical workspace.

---

## 4. New Punch List (Data Lab Findings)

> Priority tags follow the companion doc's convention: 🔴 P0 · 🟠 P1 · 🟡 P2 · 🟢 P3.

### 🔴 P0 — Must ship before any submission video
> *(None from the Data Lab side. The only P0 in the submission remains the Clinical-side patient-id bug, already queued as P1-T01.)*

### 🟠 P1 — High-impact rubric deltas

- **DL-T01 · Fix Coverage page first-paint placeholders.** Replace `...` / `Loading...` literal text with real first-paint content (SSR, inline fixture, or at minimum a non-textual skeleton bar). **Builder task.** *Cat 3 Interpretability +1.*
- **DL-T02 · Surface the Data Lab from Clinical-side entry points.** Add a subtle "Why you can trust these flags — see Methodology →" link on the Safety Panel and inside the Assistant's tool-call chip. Add a "First time? Take the 15-minute Flight School →" banner to `/explorer` when no patient is selected. **Refiner-then-builder.** *Cat 3 +2, Cat 5 +2 — the single highest-ROI Data Lab task.*
- **DL-T03 · Pipeline diagram on the Methodology page.** Replace the bullet-list "Pipeline Layers" block with an SVG diagram of Layer 0 → Layer 4 showing typed inputs, outputs, and an example record traced through it (the Naproxen example from §2 Stop 4 above is the one to use). **Refiner-then-builder.** *Cat 5 +2.*
- **DL-T04 · Annotate Coverage page data-source limitations.** Footnote `High Criticality Patients = 0` and the food-only allergy mix with an explicit "Synthea R4 corpus characteristic — see note" link. Being candid about the corpus's limits is a Cat 5 win. **Refiner.** *Cat 5 +1, Cat 4 +1.*
- **DL-T05 · Flight School "run this lesson" button.** Each lesson card today has a "Jump to views" link; add a primary button that does the lesson's exercise in one tap (pre-filled Assistant prompt, pre-navigated to the right view). **Refiner-then-builder.** *Cat 3 +1.*

### 🟡 P2 — Polish that compounds

- **DL-T06 · Right-rail TOC on FHIR Primer.** The page is long enough to warrant anchor navigation. **Refiner.** *Cat 3 +0.5.*
- **DL-T07 · Rename `/analysis` H1 and page title.** The sidebar says "Overview · Orientation and goals"; the H1 says "FHIR Data Definitions and Methodology"; the container says "Data Review Environment." Pick one and repeat it. **Refiner.** *Cat 3 +0.5.*
- **DL-T08 · Flight School progress persistence.** Local-only progress is fragile on demo day. Either persist to a localStorage namespace that survives hard-reloads, or wire to a tiny `/api/flight-school/progress` endpoint. **Builder.** *Cat 3 +0.5.*
- **DL-T09 · Reverse index from Clinical → Definitions.** Each definitional term in the Clinical surfaces (complexity score, risk tier, safety flag, episode) becomes a hoverable chip that links to its entry in `/analysis/definitions`. **Refiner-then-builder.** *Cat 5 +1.*
- **DL-T10 · "Methodology" link inside Assistant tool-call chip.** When the `build_clinical_context` chip renders in an Assistant response, the "4 sections" text should be a link to `/analysis/methodology#layers`. **Refiner.** *Cat 5 +0.5.*
- **DL-T11 · Live-data hover on FHIR Primer JSON examples.** Hovering a field name in a JSON example shows its corpus coverage percentage pulled from the Coverage page. Collapses Primer + Coverage into one unified reviewer experience. **Builder.** *Cat 3 +1, Cat 5 +1.*
- **DL-T12 · Completion payoff on Flight School.** An end state after Lesson 5 — "You've finished Flight School — review with confidence" — that closes the curriculum loop. **Refiner.** *Cat 3 +0.5.*

### 🟢 P3 — Strategic / research-adjacent

- **DL-T13 · Cross-link the Clinical/Data Lab toggle to a mode label.** Today it is a pill toggle; a one-line subtitle ("For clinicians" / "For reviewers") removes ambiguity. **Refiner.** Overlaps with Clinical-side P1-T12.
- **DL-T14 · "For patients" third mode.** Deferred per Q2 Phase 1 decision, but worth noting that the Data Lab architecture (separate mode, separate theme, separate sidebar) is the right shape to accept a third mode in Phase 2.
- **DL-T15 · Desktop viewport verify.** Because the walkthrough was captured at ~531px, every Data Lab layout and density judgment in §2 is un-verified at desktop widths. A one-pass desktop re-walk (screenshots at 1440×900) should be scheduled before any of DL-T01–T12 land. Logged as finding **DL-F1**.

---

## 5. What a Panelist Remembers 10 Minutes Later (Data Lab edition)

**Stick:**
1. **"We treat absence as a first-class signal."** Phrase of the submission.
2. **Flight School.** A five-lesson curriculum that tells the reviewer what to click and what to conclude.
3. **Coverage page that flags its own weak fields.** `medication.dosage_text at 0.0%` shown in "Fields Requiring Caution."

**Lose points on:**
1. **Coverage page first-paint is a broken-looking skeleton.** A fast skimmer leaves.
2. **No link from Clinical to Methodology.** The best explainability content in the submission is invisible to a reviewer who only walks the Clinical side.
3. **Pipeline is described, not drawn.** Five layers in bullets where an SVG would own the page.

Fix those three and the Data Lab stops being a hidden asset and starts being the second-best pitch in the submission (behind the Clinical Safety Panel, which it now supports explicitly).

---

## 6. Takeaways That Change The Phase 1 Strategy

1. **The Data Lab is load-bearing.** The companion walkthrough's scorecard underestimated Cat 5 by ~4 bonus points because it never saw `/analysis/methodology`. The *existence* of rigorous methodology, definitions, and coverage pages is a Cat 5 win on its own — the work now is making sure a reviewer actually finds them.
2. **Do not build a second methodology page in Clinical.** The companion doc's P1-T14 correctly closed; the right move is DL-T02 (surface the existing one).
3. **The submission already has a reviewer curriculum.** Flight School is a strategic asset most submissions will not have. The Phase 1 PDF should explicitly tell panelists to take the 15-minute Flight School track *before* they walk the app — it will pre-load the exact vocabulary ("episodes," "risk tier," "safety flags," "coverage tiers," "traceability") our other pages depend on.
4. **Cat 3 and Cat 5 are closer to target than the companion doc estimated.** The remaining gap is concentrated in Cat 2 (Integration & Scaling, still weakest) and Cat 4 (Privacy posture, still invisible). Those are the two places Phase 1 polish should push hardest.
5. **Responsive behavior of the Data Lab needs a desktop re-verify.** Everything in §2 was evaluated via text content; nothing was verified at desktop widths. DL-F1 / DL-T15.

---

*All DL-T01 → DL-T15 items have been added to `.claude/phase1-queue.md` and P1-T19 (Data Lab UX review pass) in that queue is unblocked by this doc.*
