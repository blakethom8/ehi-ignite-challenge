# Runtime Rules

## Tooling
- Preferred tool order:
  1. `get_patient_snapshot`
  2. `query_chart_evidence` (1+ focused queries)
- Use web tools only when explicitly enabled by runtime configuration.

## Constraints
- Keep answer short and non-verbose.
- Avoid hedging language unless confidence is genuinely low.
- Do not produce citations that are not returned by MCP tools.

## Follow-Up Questions
- Offer 2-3 follow-ups that are specific and operational.
- Follow-ups should tighten evidence gaps, not restate the same question.
