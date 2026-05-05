# Skills

Per-skill directories implementing the Skill + Agent + Workspace architecture
(`docs/architecture/SKILL-AGENT-WORKSPACE.md`).

Each skill is a self-contained directory:

```
skills/<name>/
  SKILL.md              # YAML frontmatter + markdown body
  workspace.template.md # required for `brief-workspace` skills
  output.schema.json    # required: JSON Schema for the run artifact
  evals/
    rubric.md           # what counts as a correct run
    cohort.json         # optional: hold-out patients with expected outputs
  references/           # optional: long instructional references
  scripts/              # optional: deterministic helpers callable from the skill
```

`SKILL.md` frontmatter contract — enforced by `api/core/skills/loader.py`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | str | yes | Filesystem-safe identifier, must match directory name |
| `version` | str | yes | Semver |
| `audience` | enum | yes | `clinician` \| `patient` \| `regulatory` |
| `shape` | enum | yes | `dashboard` \| `brief-workspace` \| `conversational` |
| `description` | str | yes | One-paragraph summary; first sentence is shown in the marketplace listing |
| `required_tools` | list[str] | yes | Tool ids the runtime must provide |
| `optional_tools` | list[str] | no | Tools used if available |
| `context_packages` | list[str] | no | Pre-loaded context bundle ids |
| `input_schema` | str | no | Path to JSON Schema for brief inputs (relative to skill dir) |
| `output_schema` | str | yes | Path to JSON Schema for the artifact (relative to skill dir) |
| `escalation` | list[obj] | yes for `brief-workspace` | At least one stop-and-ask condition |
| `eval` | obj | no for `Concept`, yes for `Live` | `rubric`, optional `cohort`, optional `metrics` |
| `agent_topology` | enum | no | `flat` (default) \| `planner_executor` |
| `sub_agent_template` | str | no | Required if `agent_topology == planner_executor` |

The loader refuses to register a skill that fails the contract. Skills without
a passing eval ship as `Concept`; skills with one ship as `Live`.

## Adding a new skill

1. Create `skills/<name>/` with the required files above.
2. Run the loader (`uv run python -m api.core.skills.loader skills/<name>`) to
   validate frontmatter + schema parsability.
3. Add tests under `api/tests/test_skills_*.py` if the skill ships scripts.
4. The marketplace surface picks up the skill on next API restart.

## Currently shipping

- **`trial-matching/`** — clinician-facing brief-workspace skill. Reads the
  canonical patient chart, queries ClinicalTrials.gov, parses inclusion
  criteria against the chart, scores fit per trial, writes a citation-grounded
  outreach packet.
