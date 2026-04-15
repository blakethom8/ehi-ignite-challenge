# Judge Walkthrough — EHI Ignite Challenge Submission

**Walked:** 2026-04-14 on local dev (`http://localhost:5173` against API on `:8001`)
**Patient used:** Shelly431 Corwin846 (High Surgical Risk featured profile)
**Lens:** Panelist scoring against the official [ehignitechallenge.org](https://ehignitechallenge.org/) rubric.

---

## 1. The Rubric We Are Being Scored On

| # | Category | Weight | What it rewards |
|---|---|---|---|
| 1 | Relevance & Problem Alignment | 25 | How well the tool addresses real usability challenges in single-patient EHI exports; real-world scenario fit. |
| 2 | Integration & Scaling | 20 | Practicality inside clinical workflows, consensus standards, multi-patient / multi-provider / multi-EHR. |
| 3 | **Interpretability & Ease of Use** | **40** | Novelty in making EHI actionable and readable; user-centered design; ease of use for clinicians, patients, care teams. |
| 4 | Privacy, Security, Compliance | 15 | HIPAA & privacy adherence; customizable privacy settings. |
| 5 | **Bonus: AI Innovation** | **+20** | Transparent, explainable AI methods that are privacy-compliant. |

**Total: 100 + 20 bonus.** Category 3 is the heaviest single category — every UI decision echoes here.

---

## 2. The Walk-through

### Stop 1 — Landing (`/`)

**What a judge sees:** the value prop headline "*The right 5 facts in 30 seconds*", the use-case narrative (*"A surgeon has 60 seconds between cases…"*), three feature tiles (Safety Panel / Care Journey / Provider Assistant), and a "Featured Patients" row of six curated clinical profiles with real stats (High Surgical Risk, Low Risk, Polypharmacy, Drug Interactions, Pediatric, Elderly Complex).

**Strengths**
- ✅ Use case is *explicit and named*: pre-operative chart review for a specific primary user (surgeon). This is exactly what rubric Cat 1 rewards — "real-world problem-solving alignment with identified scenarios."
- ✅ North-star metric — "5 facts in 30 seconds" — is visible in hero copy and again in the use-case block. A judge reading the Phase 1 PDF alone will remember this phrase.
- ✅ Six curated profile cards let a judge self-select an interesting clinical phenotype instead of scrolling a generic patient list.

**Issues**
- ⚠️ **Two CTAs, one destination.** "Open Clinical Dashboard" and "Explore the Data" both route to `/explorer`. A judge who clicks "Explore the Data" expecting a different surface lands on the clinical workspace and will wonder if something broke.
- ⚠️ **Missing explicit call-out of the need case numbers.** The copy is qualitative ("thousands of records deep"). Shelly has *2,282 resources, 66.5 years of history, 59 unique lab types*. If those headline numbers appeared as a ticker in the hero, the "need" case would land with numeric force.
- ⚠️ No indication anywhere on the landing page that this uses **Synthea synthetic data** — a judge scoring Cat 4 (Privacy) is going to want to know whether real PHI touched this system.

---

### Stop 2 — Clinical Workspace shell (`/explorer`)

**What a judge sees:** sidebar titled "Clinical Workspace" with ~15 view entries (Overview, Assistant, Safety, Interactions, Timeline, Care Journey, Conditions, Procedures, Immunizations, Clearance, Anesthesia, Corpus, Distributions, Patient Journey…), a top-right Clinical/Data Lab toggle, and an empty-state "Choose a patient to begin."

**Strengths**
- ✅ Sidebar iconography is clean and scannable.
- ✅ The empty state explains what the user will get once they pick a patient (demographics, FHIR resource distribution, conditions/meds/allergies/immunizations).
- ✅ A floating chat widget is available globally (bottom-right).

**Issues**
- 🚨 **CRITICAL BUG — Overview fails to load when a patient is chosen from the sidebar list.** Root cause confirmed: `/api/patients` returns bare resource UUIDs (`eec393be-…`) because it reads from the corpus cache via `idx.patient_id`, but `/api/patients/{id}/overview` expects the **filename stem** (`Shelly431_Corwin846_eec393be-…`) because `load_patient()` resolves to `<DATA_DIR>/<patient_id>.json`. The bug only appears on the corpus-cache path; the fallback path (no cache) works because it calls `patient_id_from_path`. Evidence:
  - Network: `GET /api/patients/eec393be-2569-46db-a974-33d7c853d690/overview → 404`
  - Same network trace after entering via the landing-page card: `GET /api/patients/Shelly431_Corwin846_9da0dcfc-…/overview → 200`.
  - This is the very first interaction a judge does after hitting the clinical dashboard. **Do not ship Phase 1 with this.**
- ⚠️ **Sidebar is overloaded.** 15 items directly contradicts "5 facts in 30 seconds." A Cat 3 judge counting clicks and cognitive load will deduct here. Suggested groupings:
  - **Pre-op essentials:** Overview · Safety · Interactions · Clearance · Anesthesia
  - **Longitudinal:** Timeline · Care Journey · Patient Journey · Conditions · Procedures · Immunizations
  - **Context & data:** Corpus · Distributions · Assistant
  Or collapse rarely-used items into an "Advanced" drawer.
- ⚠️ **"Clinical" vs "Data Lab" toggle at top right is ambiguous.** Clicking Data Lab didn't appear to visibly change anything in a patient-selected state. If the two modes exist for different audiences (clinician vs challenge evaluator), say so with a label ("For clinicians / For reviewers").
- ⚠️ **Title mismatch** — top bar says "Clinical Intelligence Workspace", sidebar header says "Clinical Workspace". Pick one.

---

### Stop 3 — Overview with a loaded patient (`/explorer?patient=Shelly431_…`)

*Reached by clicking a Featured Patient card from the landing page — the happy path.*

**What a judge sees:** a red banner "*Surgery Hold — Review Required*" with three status pills (Medications: REVIEW · Conditions: FLAGGED · Labs: CLEARED), "Top concern: Hypertension," patient demographics (Female · 91 yrs · Lynn, MA), a "Highly Complex Complexity · 90/100" badge, and a row of vital-signs-style stat cards (2,282 total resources, 1,833 clinical, 443 billing, 217 encounters, 66.5 years of history, 59 unique lab types). Below: demographics, data span, resource distribution chart.

**This is the hero screen.** It is the single strongest evidence that the team built to the "5 facts in 30 seconds" mandate. If I am judging, I want this to be what I see in the demo video.

**Strengths**
- ✅ **Surgery Hold banner = the deliverable.** Immediately answers "can this patient go to the OR?" with a single glance.
- ✅ Complexity score and age + location are anchored at eye level.
- ✅ Stat cards convert abstract "EHI export" numbers into legible health-literacy data points.
- ✅ "View Raw FHIR" button present — transparency for a technical judge who wants to verify provenance.

**Issues**
- ⚠️ **Banner sub-copy is thin.** "Top concern: Hypertension" is one concern; for a 90/100 complexity patient there are surely more. A 2–3 bullet summary under the banner ("Hold NSAIDs 3–5d · Hold metformin 48h · No anticoagulants on board") would *be* the 5-facts promise made visible without requiring a click.
- ⚠️ **Complexity score is unexplained.** "90/100" needs a tooltip or footnote pointing at the scoring methodology — Cat 5 (AI Innovation) rewards explainability.
- ⚠️ The "Clearance → Safety" nav-chip pair inside the banner is a good idea but easy to miss; they read as secondary buttons rather than the primary action.

---

### Stop 4 — Safety Panel (`/explorer/safety`)

**What a judge sees:** patient name + "Pre-Op Safety Review" header, a red "2 ACTIVE flags" pill, and two actionable cards:

1. **NSAIDs · ACTIVE** — "Increased bleeding risk + renal concerns. Typically held 3–5 days pre-op." · `PRE-OP PROTOCOL` drawer · `2 meds`
2. **Diabetes Medications · ACTIVE** — "Hold metformin 48h pre-op (contrast/renal risk). Adjust insulin dosing." · `2 meds`

**Strengths**
- ✅ **This is the highest-signal screen in the app.** Each card is literally an action a surgeon can take: hold NSAIDs 3–5 days, hold metformin 48h. That is "actionable" made concrete.
- ✅ Flags are categorized by drug class, not raw med name — correct clinical abstraction.
- ✅ Severity and action window are in the same sentence as the flag name.
- ✅ Expandable protocol drawers separate the "what" from the "how" — good progressive disclosure.

**Issues**
- ⚠️ **No citations visible on the card.** The strongest claim the app can make is "we derived this from the patient's actual record." Each flag should show the source medication(s) by name with an onset date and a "View in raw FHIR" link. Without this a judge will ask "how do I trust this?"
- ⚠️ **"2 meds" is a count, not an affordance** — hovering or clicking should expand to the actual drug names with start dates. Right now the click target is unclear.
- ⚠️ **No "cleared" section.** The banner on Overview said "Labs: CLEARED" — a judge will want to see *why* labs are cleared. A collapsed "3 checks passed" card at the bottom would reinforce the thoroughness of the review.
- ⚠️ **No printable / exportable handoff.** Cat 2 (Integration) rewards workflow fit; a "Print pre-op summary" or "Copy to handoff note" button would land directly.

---

### Stop 5 — Provider Assistant (`/explorer/assistant`)

**What a judge sees:** a chat surface with a patient-scoped header ("Shelly431 Corwin846 · chart-grounded Q&A"), Opinionated/Balanced tone toggles, a "Sonnet 4.5 | Context (Recommended)" model picker, and four seeded prompts:
- "Is this patient safe for surgery this week?"
- "Any active blood thinner or interaction risk?"
- "What changed recently that affects peri-op risk?"
- "Summarize the active problem list."

After sending the first seeded prompt: a `build_clinical_context` tool call is displayed inline (`fact_count: 15, token_estimate: 236, sections: [safety_flags, active_medica…]`), followed by a structured answer:

> # SAFETY ASSESSMENT: NOT SAFE FOR SURGERY THIS WEEK
>
> ## IMMEDIATE CONCERNS
> - ACTIVE BLEEDING RISK — MUST ADDRESS: Naproxen 220 MG (NSAID); HOLD for 3–5 days
> - DIABETES MANAGEMENT — REQUIRES PROTOCOL: Metformin 500 MG ER + Humulin 70/30; metformin 48h pre-op; insulin dosing needs perioperative adjustment
>
> ## SUPPORTING DATA
> **Positive factors:** No anticoagulants, no antiplatelets, no immunosuppressants, recent GI procedures evaluated.
> **Missing critical information:** No recent labs, no surgery type specified, no allergy documentation.
>
> ## DIRECT ANSWER
> NO — not safe to proceed this week without:
> 1. Confirming NSAID discontinuation ≥3 days pre-op
> 2. Implementing perioperative diabetes protocol
> 3. Obtaining baseline labs (CBC, CMP, HbA1c)

**Strengths (this is the app's most rubric-aligned surface)**
- ✅ **Visible tool call with fact count, token estimate, and sections** — textbook "transparent, explainable AI methods." This should be the centerpiece of the Phase 1 PDF's "AI Innovation" section.
- ✅ **Decisive verdict up top.** Many clinical Q&A tools hedge; this one says "NOT SAFE" and then backs it up. Judges will remember that.
- ✅ **"Missing critical information" section.** The model is volunteering what it does *not* know. This is the single most underrated feature for clinical trust and it is live.
- ✅ **Numbered action list** at the bottom — a judge can screenshot this and paste it into their scoresheet unedited.
- ✅ **Named drugs, specific doses, specific protocols** — not a generic advisory.
- ✅ Seeded prompts lower the activation energy for a demo.
- ✅ Model/context picker is surfaced (not buried in a settings cog).

**Issues**
- ⚠️ **Tool-call line is tiny and gray.** Move it to the top of the response as a "Chart evidence used: 15 facts / 236 tokens — see 4 sections" chip that is *clickable* and expands the retrieved facts inline. Right now a judge has to notice and squint at it.
- ⚠️ **No inline citations in the answer body.** "Patient is currently taking Naproxen 220 MG" should be linked to the underlying `MedicationRequest` ID. This is a 5-minute fix that dramatically lifts Cat 5 (AI Innovation — explainability).
- ⚠️ **Latency from tap-to-answer is ~20–30s** on the seeded prompt. Streaming tokens would halve perceived wait time.
- ⚠️ **Tone toggle ("Opinionated" / "Balanced") is unexplained.** A one-line microcopy under the toggles would remove ambiguity.

---

## 3. Scorecard — As If I Were A Panelist Today

> Scored against the app in its current state, *not* the ideal Phase 1 submission.

| Category | Weight | Today | Gap | Notes |
|---|---:|---:|---:|---|
| 1. Relevance & Problem Alignment | 25 | **20** | 5 | Use case is explicit and specific. Gap: no explicit stated "real-world scenario alignment" beyond the pre-op pitch; add 1–2 sentences about multi-specialty applicability (anesthesia, ED triage, psychiatry) to sidestep a "narrow wedge" deduction. |
| 2. Integration & Scaling | 20 | **10** | 10 | Largest gap. The app loads one Synthea bundle at a time; no multi-provider reconciliation, no export to handoff note, no EHR integration story told. A "Print pre-op summary" button + a 1-paragraph scaling narrative in the PDF would recover ~6 pts. |
| 3. Interpretability & Ease of Use | 40 | **27** | 13 | Hero screen and Safety Panel are strong. Cost: sidebar bloat (15 items), landing-page CTA routing bug, critical Overview load bug from the sidebar, latency on Assistant. Fix the critical bug and tighten the sidebar → recover ~8 pts. |
| 4. Privacy, Security, Compliance | 15 | **7** | 8 | Nothing on-screen says "this uses synthetic Synthea data, no PHI." No visible compliance posture — just a GitHub link. Add a "Synthetic data — Synthea R4" badge in the header, a one-page "Privacy & Compliance" view (HIPAA stance, auth roadmap, data handling), and recover most of this. |
| 5. Bonus: AI Innovation | +20 | **+14** | +6 | Tool-call transparency is live and the answer structure is exemplary. Recover remaining bonus with inline citations (MedicationRequest IDs), a "Methodology" page describing how the drug classifier + episode detector + safety flags work, and token/cost receipts on every Assistant turn. |
| **Total** | **100 +20** | **78** | **+22** | |

**Today's score: ~78 / 100 + 14 bonus = 92 / 120.** Comfortable mid-pack. **With the fixes in §4 the target is 90+ / 100 + 18 bonus.**

---

## 4. Prioritized Punch List (Feeds the Build Queue)

> Priority tags: 🔴 blocker for demo · 🟠 high-impact rubric delta · 🟡 polish that compounds.

### 🔴 P0 — Must ship before any submission video is recorded
1. **Fix the patient-id contract mismatch.** `list_patients()` returns `idx.patient_id` (bare UUID); `load_patient()` expects the filename stem. Either: (a) change `list_patients()` to emit filename-stem IDs, or (b) add a UUID → filename-stem resolver in `load_patient()`. Prefer (b) — it means the public URL can stay a clean UUID.
2. **Add a `Synthetic data — Synthea R4` badge in the top bar**, and a privacy footnote ("No PHI. Local compute.") on the landing page.

### 🟠 P1 — High-impact rubric deltas
3. **Tighten the sidebar to three groups.** Pre-op essentials / Longitudinal / Context & data. Collapse rarely-used views into an "Advanced" drawer.
4. **Inline citations in the Assistant.** Each specific claim should carry the resource ID it came from, with a hover preview of the raw FHIR fragment.
5. **Expand the Overview "Surgery Hold" banner** to show 3–5 bullet actions directly under the title — do not require a click for the 5 facts.
6. **Click-to-reveal on Safety cards:** "2 meds" should expand to the actual drug names, doses, and start dates.
7. **Unify CTA routing on landing page.** "Explore the Data" should go to a data-lab / corpus entry, not the clinical workspace.
8. **Explain the complexity score.** A tooltip linked to a methodology page.

### 🟡 P2 — Polish that compounds
9. **Stream Assistant responses** instead of waiting on the full payload.
10. **Elevate the tool-call chip** in the Assistant to the top of the answer as "Chart evidence: 15 facts · 236 tok · 4 sections" — clickable to expand.
11. **"Print pre-op summary"** button on Safety / Overview — direct Cat 2 points.
12. **Microcopy on Opinionated / Balanced toggle**, and on Clinical / Data Lab toggle.
13. **Reconcile "Clinical Intelligence Workspace" vs "Clinical Workspace"** — pick one.
14. **Add a Methodology page** (`/explorer/methodology`) that documents the drug classifier, episode detector, safety flag logic, and the SQL-on-FHIR warehouse layers — one URL a judge can visit for Cat 5.

### 🟢 P3 — Strategic / research-adjacent
15. **Patient-advocacy angle.** The app currently targets clinicians. Cat 3 *explicitly mentions patients and care teams* — a "Patient View" mode (same data, lay-language summaries, "questions to ask your surgeon") would unlock points we are leaving on the table.
16. **Multi-patient view.** A cohort screen showing risk flags across the 1,180-patient corpus would directly answer Cat 2's "multi-patient scalability" criterion.
17. **Medication reconciliation across providers** — the headline use case FHIR uniquely enables. Even a mock demonstrating cross-source dedup would be a differentiator.

---

## 5. What a Panelist Remembers 10 Minutes Later

From this walk, the things that would actually stick:

1. **"5 facts in 30 seconds"** — the phrase, the red Surgery Hold banner, and the stat cards on Overview.
2. **NSAIDs → hold 3–5 days · Metformin → hold 48h.** The Safety Panel cards read like a clinical checklist, not a dashboard.
3. **The Assistant showed its work** — a tool-call receipt and a "missing critical information" section that *admits uncertainty*.

And the things that would lose us points:

1. **The click that failed** — picking a patient from the sidebar and hitting "Failed to load patient data."
2. **The dense sidebar** that contradicted the "5 facts" promise the moment a judge saw it.
3. **No visible privacy / data-origin posture** — a judge scoring Cat 4 has nothing to grab onto.

Fix those three things and the walk becomes a clean hit on the rubric's two biggest categories (40 + 20 = 60% of the score).

---

*Appendix — every concrete P0/P1/P2 item above has a matching task entry in `.claude/phase1-queue.md`, ready to be picked up by the phase1 build loop.*
