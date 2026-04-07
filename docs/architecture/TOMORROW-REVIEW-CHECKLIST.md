# Tomorrow Review Checklist

Use this as a quick pass before the next feature sprint.

## 1) Provider Experience

1. Run 5-10 real provider-style questions across different patients and verify answers stay direct, non-verbose, and clinically actionable.
2. Check that the assistant pushes back clearly when chart evidence is thin, conflicting, or stale.
3. Confirm follow-up questions are useful next actions (not generic filler).

## 2) Context Quality

1. For each test query, inspect the `agent_query` trace and confirm the context includes only relevant chart evidence.
2. Verify large bundles are not flooding prompt context with low-value observations or repetitive labs.
3. Confirm citations map to the same high-signal facts shown in the final answer.

## 3) Tool Calls & Traceability

1. Confirm expected spans appear for Anthropic runs: `baseline_evidence`, `agent_query`, `get_patient_snapshot`, `query_chart_evidence`.
2. Spot-check tool-call arguments/results for correctness on at least 3 patients.
3. Review `/api/traces/summary` for latency and token/cost outliers.

## 4) Safety & Controls

1. Ensure `TRACES_API_ENABLED` is disabled outside trusted/internal environments unless auth is added.
2. Verify no secrets are committed and `.env` remains ignored.
3. Validate deterministic fallback behavior only where explicitly intended.

## 5) Code Health

1. Remove dead env vars, stale docs references, and duplicate helper logic.
2. Confirm tests cover Anthropic mode, fallback mode, and traces endpoint behavior.
3. Run lint/tests before any new merge:
   - `cd app && npm run lint`
   - `uv run python -m unittest -v api.tests.test_assistant_api`
