# Phase 1 Submission Plan — EHI Ignite Challenge

**Owner:** Blake (user — this doc is user-editable; the orchestrator never writes to it)
**Deadline:** May 13, 2026 (Phase 1 PDF submission — 10-page narrative + wireframes)
**Branch policy:** feature branches only; no direct pushes to `master` without explicit approval
**Source of truth for *why* tasks exist:** [docs/JUDGE-WALKTHROUGH.md](../docs/JUDGE-WALKTHROUGH.md)

---

## Goal

Land at **95+ / 100 + 19 bonus = 114+ / 120** on the official rubric by May 13. Today's walk-through score (both Clinical and Data Lab walks combined) is **92 / 100 + 18 bonus = 104 / 120**. The gap is ~10 points, concentrated in the two categories where the Data Lab can't help us: **Cat 2 Integration & Scaling** and **Cat 4 Privacy**.

| Category | Weight | Today | Target | Delta |
|---|---:|---:|---:|---:|
| 1. Relevance & Problem Alignment | 25 | 22 | 24 | +2 |
| 2. Integration & Scaling | 20 | 11 | 17 | +6 |
| 3. Interpretability & Ease of Use | 40 | 32 | 37 | +5 |
| 4. Privacy, Security, Compliance | 15 | 9 | 14 | +5 |
| 5. Bonus: AI Innovation | +20 | +18 | +19 | +1 |
| **Total** | **120** | **92** | **111** | **+19** |

*Numbers revised 2026-04-14 after the Data Lab walkthrough (`docs/JUDGE-WALKTHROUGH-DATALAB.md`) raised the Cat 3 and Cat 5 baselines. Cat 2 and Cat 4 remain the biggest unclosed gaps — those are where Phase 1 polish must push hardest.*

Every task in the queue traces to one of these deltas.

---

## Strategy

1. **Ship the walk-through punch list first.** §4 of `JUDGE-WALKTHROUGH.md` is already prioritized (🔴 P0 → 🟠 P1 → 🟡 P2 → 🟢 P3). The queue (`phase1-queue.md`) seeds directly from that list.
2. **P0 before P1 before P2.** P0 is "the demo is broken" work. P1 is "the rubric needs this" work. P2 is polish that compounds. P3 is research-adjacent and only lands if P0–P2 close early.
3. **Builder and refiner work are distinct.** The orchestrator classifies every task before dispatching. IA decisions are refiner work; the markup change to ship an IA decision is builder work. When both are needed, refiner goes first so the builder has the final shape to implement.
4. **Every commit cites a rubric category.** If a task can't name a rubric category and expected points recovered, it doesn't belong in the queue.
5. **The submission PDF is a separate track.** This plan is about *the app*. The 10-page PDF narrative is a separate body of work the user writes; the orchestrator never touches it.

---

## Guardrails

- **Never touch `fhir_explorer/parser/`** — read-only contract inherited from the SQL-on-FHIR review.
- **Never touch `patient-journey/`** — legacy reference code only.
- **Never touch `docs/JUDGE-WALKTHROUGH.md`** — it is a timestamped snapshot of "how today's app scores." If the judge view changes, the user re-walks and updates the doc; tasks do not mutate it.
- **Never touch this plan (`phase1-plan.md`)** — only the user edits it.
- **Every task must have a smoke test (builder) or a before/after screenshot pair + self-eval (refiner).** No verification, no completion.
- **No backwards-compat shims or feature flags** unless explicitly justified — we are shipping to a rubric, not a user base.

---

## Open questions (block tasks with `⛔` when unanswered)

*All four original questions resolved on 2026-04-14. New questions surfaced by the answers are tracked below.*

### Resolved

1. **Sidebar grouping names.** ✅ **Resolved 2026-04-14** — approved as *Pre-op essentials / Longitudinal / Context & data*. An "Advanced" drawer at the bottom holds rarely-used items. Unblocks P1-T03.

2. **Patient View mode.** ✅ **Resolved 2026-04-14** — **deferred to Phase 2.** Cat 3 points lost are acceptable; the bigger concern the user raised is that the existing Overview / patient summary page is not pulling its weight for *any* audience. Defer P1-T15 (Patient View), add a new P1-level task to audit and clean the Overview page (P1-T18).

3. **Methodology page scope.** ✅ **Resolved 2026-04-14** — **do not build a new one.** The Analysis section (`app/src/pages/Analysis/*`) already contains a Methodology page, plus Definitions / Coverage / FlightSchool / FhirPrimer / Overview. The right move is a thorough UX review pass over that entire Data Lab / Analysis area, not a new page in the Clinical workspace. P1-T14 is closed out as superseded; add a new task (P1-T19) to walk and review the Analysis section.

4. **Cohort view.** ✅ **Resolved 2026-04-14** — **build it, but small and supporting, not a centerpiece.** The product's identity is single-patient pre-op review; a cohort screen exists purely to answer Cat 2's multi-patient scalability criterion. Keep it to one page showing risk flags across the 1,180-patient corpus, drilling into individual patient records. Unblocks P1-T16 with scope note "small supporting cohort, not centerpiece."

### New questions surfaced (blockers until answered)

5. **Overview page audience.** The existing `/explorer` Overview renders stat cards, demographics, data span, and a resource-distribution chart for a patient. The user's read: it's not clearly useful — for the surgeon it's too broad, for the data reviewer it's too thin. Before touching copy and layout, we need to decide who the Overview is *for*. Options:
   - (a) **Surgeon briefing** — rename to "Briefing," lead with Surgery Hold banner + 5 action bullets + allergies, demote the resource-distribution chart to a collapsed "Data coverage" drawer.
   - (b) **Reviewer / data completeness** — keep the stats cards, lead with "what this chart does and doesn't contain," add coverage metrics, move the clinical summary to Safety/Clearance.
   - (c) **Two pages** — "Briefing" (surgeon) and "Chart Quality" (reviewer), accessed from a segmented toggle at the top.
   Blocks P1-T18.

6. **Data Lab / Analysis section walk-through gap.** ✅ **Resolved 2026-04-14** — orchestrator performed the second walkthrough. `docs/JUDGE-WALKTHROUGH-DATALAB.md` now exists as a companion to the Clinical walkthrough. Scorecard revised upward: the baseline is now **92/100 + 18 bonus = 104/120** (vs. the Clinical-only estimate of 92/120). 15 new tasks (DL-T01 → DL-T15) added to the queue. P1-T19 is unblocked and superseded by DL-T01 → DL-T15 — this is no longer a "review" task but a concrete list of ship-able changes.

The orchestrator **never** guesses on blocked items. It stops the cycle and surfaces the blocker to the user.

---

## Definition of done

1. **Queue is empty** of all P0 and P1 items. P2 is >50% complete. P3 has been triaged (either scheduled or deferred to Phase 2 with a note).
2. **Build log** shows a rubric category delta for every entry. Summing those deltas reaches the 16-point target.
3. **A fresh walk-through** — the user re-does the `JUDGE-WALKTHROUGH.md` exercise from scratch — hits all three "strengths remembered" notes from §5 and none of the three "losses remembered" notes.
4. **The 10-page Phase 1 PDF** is drafted, reviews well, and cites specific in-app screens the panelists will see live.
