---
name: trial-matching
version: 0.1.0
audience: clinician
shape: brief-workspace
description: >
  Build a candidate-trial shortlist for a patient. Reads ClinicalTrials.gov,
  parses inclusion criteria against the chart, surfaces fit per trial, and
  produces a clinician-ready outreach packet. Use when the patient has at
  least one active body-system condition that could anchor a trial search and
  the clinician has flagged research as an option of interest.
required_tools:
  - get_patient_snapshot
  - query_chart_evidence
  - run_sql
  - workspace.write
  - workspace.cite
  - workspace.escalate
  - mcp.clinicaltrials_gov.search
  - mcp.clinicaltrials_gov.get_record
optional_tools:
  - mcp.pubmed.search
  - mcp.rxnorm.lookup
context_packages: []
output_schema: output.schema.json
escalation:
  - condition: no_anchor_condition
    description: No active condition has risk_category != OTHER.
    action: stop_and_ask
    prompt: >
      I cannot find an active anchor condition with a recognized body-system
      category. Confirm the patient should still be searched, or provide a
      target condition.
  - condition: all_fit_scores_below_threshold
    description: Every candidate trial scored below the fit threshold.
    action: stop_and_summarize
    prompt: >
      No strong matches in the first pass. I will summarize the gaps and
      stop. Re-run with broader anchors if you'd like a wider search.
  - condition: inclusion_criteria_unparseable
    description: ClinicalTrials.gov returned a record whose eligibility text could not be parsed.
    action: stop_and_ask
    prompt: >
      Trial {nct_id} has eligibility text I cannot reliably parse. Skip this
      trial, include it as needs-verification, or stop the run?
eval:
  rubric: evals/rubric.md
  metrics: [precision_at_5, citation_validity, escalation_correctness]
agent_topology: flat
---

# Trial Matching

## When to use

Run this skill for a patient when:

- The chart has at least one active condition with a known body-system risk
  category (cardiac, oncologic, renal, hepatic, hematologic, neurologic,
  metabolic, respiratory, infectious, psychiatric).
- The clinician wants a candidate-trial shortlist with fit notes, not a raw
  ClinicalTrials.gov dump.
- The output destination is a patient-facing outreach packet, not a
  dashboard.

Do not run this skill for:

- Open-ended chart Q&A — use the conversational chart assistant instead.
- Pre-op clearance or other rules-amenable workflows — those are
  deterministic dashboards.

## Phase 0 — Verify the brief

Before searching, confirm:

1. Call `get_patient_snapshot(patient_id)`. Read `active_conditions` and
   `risk_categories`.
2. Identify anchor conditions: active, `risk_category != "OTHER"`, onset
   within the last 10 years OR currently flagged as `recurrence` /
   `relapse`.
3. If zero anchors, fire `workspace.escalate("no_anchor_condition", ...)` and
   stop.
4. For each anchor, capture: SNOMED/ICD codes, body system, onset date,
   most recent acuity signal.

## Phase 1 — Generate search packet

For each anchor condition:

1. Call `mcp.clinicaltrials_gov.search` with:
   - `condition`: anchor display name
   - `status`: ["RECRUITING", "ENROLLING_BY_INVITATION"]
   - `age_band`: derived from `Patient.birthDate`
   - `sex`: from `Patient.gender` (do not pass if `unknown`)
   - `location_radius`: optional, default unset (clinician-supplied)
2. Take the top 30 results per anchor. Deduplicate by NCT id across anchors.

Common parameter mistakes for `mcp.clinicaltrials_gov.search`:

| Wrong | Right |
|---|---|
| `disease=` | `condition=` |
| `recruiting=true` | `status=["RECRUITING"]` |
| `sex=null` | omit the field |
| `age=45` | `age_band={"min": 18, "max": 65}` |

## Phase 2 — Parse inclusion / exclusion

For each candidate trial:

1. Call `mcp.clinicaltrials_gov.get_record(nct_id)`. Extract:
   - `eligibilityCriteria` (free text)
   - `minimumAge`, `maximumAge`, `sex`, `healthyVolunteers`
   - `studyType`, `phases`
2. Split criteria into inclusion lines and exclusion lines.
3. For each inclusion line, call `query_chart_evidence(claim=line)` and
   classify the result as one of:
   - `chart-supports` — chart fact directly satisfies the criterion.
     Capture the resource id.
   - `chart-contradicts` — chart fact rules the patient out. Stop scoring
     this trial; mark as **excluded**.
   - `needs-verification` — chart is silent. Capture the gap.
4. For each exclusion line, mirror the logic; `chart-supports` against an
   exclusion means the patient is **excluded**.
5. Tag each classification with an evidence tier:
   - `T1` — direct chart fact with clear citation
   - `T2` — derived from harmonized record (canonical fact)
   - `T3` — agent inference from chart context
   - `T4` — agent guess; only allowed for `needs-verification`

If `eligibilityCriteria` could not be parsed (no inclusion lines extracted),
fire `workspace.escalate("inclusion_criteria_unparseable", nct_id=...)`.

## Phase 3 — Score fit per trial

For each non-excluded trial:

```
fit_score =  100 * (
                 0.6 * supports_inclusion_weighted
               + 0.3 * (1 - needs_verification_ratio)
               + 0.1 * recruitment_proximity_boost
             )
```

Where:
- `supports_inclusion_weighted` = sum of inclusion supports weighted by
  evidence tier (T1=1.0, T2=0.8, T3=0.5, T4=0.0), divided by total
  inclusion lines.
- `needs_verification_ratio` = count of `needs-verification` / total
  inclusion lines.
- `recruitment_proximity_boost` = 1.0 if a recruiting site is within
  50 miles of patient zip, 0.5 if within 200 miles, 0.0 otherwise. If
  patient zip unavailable, omit this term and renormalize.

Drop trials with `fit_score < 40`. If all trials drop, fire
`workspace.escalate("all_fit_scores_below_threshold")`.

## Phase 4 — Write artifact

Open `workspace.template.md`. For each surviving trial in fit_score
descending order, write one section. Each fact must be wrapped in a
`workspace.cite` call. The citation registry will refuse uncited claims.

For each section:

1. NCT id, title, sponsor, phase, status, recruitment locations.
2. Why this trial — link back to which anchor condition matched. Cite
   the anchor's `Condition` resource id.
3. Inclusion-by-inclusion fit table:
   - Criterion (verbatim from ClinicalTrials.gov)
   - Status (`chart-supports` / `needs-verification`)
   - Citation (FHIR resource id or `[T4: agent inference]`)
4. Gaps to verify before contacting — list every `needs-verification`
   line, ordered by criticality.
5. Outreach next steps — the trial's contact name, phone, email if
   present in the record.

After writing the per-trial sections, write a top-level summary section
with: total trials reviewed, surviving, excluded reasons distribution,
overall confidence note, and any escalation decisions the clinician
already approved during the run.

## Phase 5 — Validate output

Before finishing, the runtime validates the artifact against
`output.schema.json`. The agent does not call validation directly; the
workspace runtime invokes it on `finish()`. If validation fails, the
agent receives the error report and may revise the artifact (one
revision pass; the second failure stops the run with `workspace.escalate`).

## Output contract

See `output.schema.json` for the full shape. Mandatory per-trial fields:

- `nct_id` (string, pattern `^NCT\d{8}$`)
- `fit_score` (integer 0–100)
- `evidence_tier` (enum T1–T4 — the *worst* tier among supporting facts)
- `supporting_facts` (array of citation objects)
- `gaps` (array of strings — `needs-verification` lines)
- `excluded` (boolean — true if the trial was ruled out, with `excluded_reason`)
- `escalation_triggered` (boolean)

## Notes

- **Cite or abstain.** No fact ships in the artifact without a citation
  back to a FHIR resource id or an external URL with access timestamp.
  The runtime enforces this; the agent must not work around it.
- **Stop on uncertainty.** The escalation triggers in frontmatter are
  the contract. If a new uncertain condition comes up that isn't in the
  list, default to `workspace.escalate` rather than guessing.
- **Don't act on the world.** This skill drafts the outreach packet;
  the clinician (or the patient with clinician sign-off) makes contact.
  The skill must never directly contact a trial coordinator.
