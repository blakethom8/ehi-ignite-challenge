# Trial Matching — Eval Rubric

A run is **correct** if and only if every metric below passes its threshold.
The eval harness consumes `output.json` for each run in the cohort and emits
a per-run scorecard plus the cohort aggregate.

## Metrics

### `precision_at_5`

Of the top 5 surviving trials by `fit_score`, what fraction are judged
clinically reasonable by a reviewing clinician for this patient?

- **Pass:** ≥ 0.6 (3 of 5 reasonable).
- **Stretch:** ≥ 0.8.
- **How scored:** Each cohort patient has a per-trial gold label
  (`reasonable` / `unreasonable` / `unknown`) for the trials we expect to
  surface. Unknowns are excluded from the denominator.

### `citation_validity`

For every citation in the artifact whose `source_kind` is `fhir_resource`,
does the cited resource id exist in the patient bundle and contain the
claimed fact?

- **Pass:** ≥ 0.95 (≤ 5% invalid citations).
- **How scored:** Replay each citation through the chart loader. A citation
  is invalid if the resource id does not resolve, or if the claim cannot be
  matched to a field in the resource.

For `source_kind == external_url`, validity means the snapshot in
`artifacts/sources/` contains the claimed text.

### `escalation_correctness`

For each cohort patient, does the agent escalate exactly when expected?

- **Pass:** F1 ≥ 0.8 against the gold escalation labels.
- **False positive:** agent escalates when the gold label says it should
  have proceeded.
- **False negative:** agent proceeds when the gold label says it should
  have escalated.

### `excluded_correctness` (informational, not pass/fail)

For each trial the agent marks excluded, does the cited contradicting fact
actually contradict the inclusion criterion? Tracked over time as an
informational metric.

## Cohort

A passing eval requires ≥ 20 cohort patients spanning:

- ≥ 3 body systems (cardiac, oncologic, renal, hematologic, neurologic).
- ≥ 2 patients with `risk_category == OTHER` only (escalation expected).
- ≥ 2 patients with adversarial inclusion criteria (parsing should fail
  gracefully, escalation expected).
- ≥ 4 patients with cross-source harmonized records (citations should
  resolve through the harmonized layer).

Until the cohort is built, this skill ships as `Concept` and the
marketplace badge reflects that.

## Promotion to Live

A skill version is promoted to `Live` when:

1. Cohort size ≥ 20.
2. All three pass-fail metrics are passing.
3. Two consecutive runs against the cohort produce identical artifacts
   (determinism check at fixed `temperature=0`, accounting for retrieved
   ClinicalTrials.gov state).
4. A clinician reviewer signs off on the rubric output.
