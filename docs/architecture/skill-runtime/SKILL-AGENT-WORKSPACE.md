# Skill + Agent + Workspace — Architecture for Clinical Modules

> **Status:** Architecture proposal. Not yet implemented. Captures the product
> framing and system design for moving from hand-built React module pages to
> versioned skill files executed by a generic agent runtime in a workspace the
> agent can mutate.
>
> **Author:** Blake (with research synthesis from sub-agents)
> **Last updated:** 2026-05-04

---

## 1. Why this doc exists

Today, every "Clinical Insight" module is a hand-coded React page. Pre-Op
Support is the gold standard — a deterministic dashboard built on rules over
the FHIR chart, with a verdict, per-domain components, and a methodology
footer. It works because pre-op clearance is *legitimately* a rules problem;
the chart contains the answer.

But most clinical modules aren't shaped like Pre-Op. **Medication Access** is
not the comparison of four hardcoded affordability tiers — it's an open-ended
research task: read formularies, compare coupon cards, look up manufacturer
assistance programs, decide what fits this patient's coverage. **Trial
Matching** is not a per-condition acuity classifier — it's reading
ClinicalTrials.gov, parsing inclusion criteria text, deciding fit per trial,
finding geographic matches, drafting outreach. **Second Opinion**, **Payer
Check**, **Grants**, **Caregiver View** all share this shape: the chart is
the *brief*, not the *answer*.

The team currently fakes those modules with explainer cards and "future
state" mockups. That's why they feel hollow even when the data underneath is
real. The page is dressing up a workflow that hasn't been built yet.

This document specifies the architecture for actually building those
workflows: as **skill files** authored by clinicians, executed by an **agent
runtime** that the user already has shipping (with extensions), inside a
**workspace** the agent can edit and the user can watch live.

The goal is twofold:

1. **Ship modules without writing React for each one.** A new clinical
   workflow becomes a markdown skill file plus a workspace template, not a
   2,000-line page.
2. **Build a marketplace, not a portfolio.** The Context Library scaffolding
   already in the app becomes the natural distribution surface for community
   skills.

---

## 2. Strategic alignment

This proposal is consistent with the project's existing strategic posture:

- **Provenance-first** ([ATLAS-DATA-MODEL.md](ATLAS-DATA-MODEL.md)) — every
  fact carries lineage from bronze → silver → gold. Skill outputs must
  preserve that chain; an agent assertion without a citation back to a FHIR
  resource id (or an external source URL) is not allowed to ship in the
  workspace.
- **Hot path + cold path** — the deterministic dashboards (Pre-Op, Lab
  Explainer, Cardiometabolic) handle the 80% case fast and rules-based. The
  agent runtime handles the open-ended long tail: Med Access, Trial Match,
  Second Opinion, prior-auth packets. This doc is mostly about the cold path.
- **Pre-digested context over raw FHIR** ([CONTEXT-ENGINEERING.md](CONTEXT-ENGINEERING.md))
  — agents reason from intelligence, not structure. Skills consume the
  canonical patient workspace and the existing context packages, not raw
  bundle JSON.

This also aligns with where the industry has converged:

- **Anthropic Agent Skills** are now a stable format across Claude.ai, Claude
  Code, Agent SDK, and the API's code-execution tool. Three-stage progressive
  loading: metadata → `SKILL.md` → siblings. This is the format we adopt
  directly. ([Anthropic engineering post](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills),
  [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview))
- **MCP** has won the data-source-integration layer. Provider-side data
  sources (RxNorm, ClinicalTrials.gov, PubMed) are best published as MCP
  servers; clinical workflows are best published as skills.
- **Plan-as-artifact + approval gate** is universal across Claude Code,
  Cursor, Devin. Long agent runs checkpoint at ambiguous decisions; the human
  approves before execution. We adopt this as the workspace contract.
- **Citation-or-refuse** has hardened as the clinical-AI guardrail.
  ([Nature 2025](https://www.nature.com/articles/s41598-025-09138-0)) Every
  assertion in the workspace must link back to a FHIR resource id or external
  doc, or it must abstain.

---

## 3. Product description / user experience

### 3.1 The clinical session

A Clinical Insight module run, from the clinician's point of view, is a
**three-act session**:

**Act 1 — The brief.** The clinician opens the module for a patient. The
landing page is what we already build today: a deterministic verdict hero +
per-item cards drawn from the chart. *This is not the answer; it is the
agent's starting context, rendered for the human so they can see what the
agent will see.* For Trial Matching, that's the per-condition anchor list. For
Med Access, the per-medication tier table. For Pre-Op, that's literally the
whole module — Pre-Op needs no further work.

**Act 2 — The work.** The clinician confirms or amends the brief and clicks
**Run**. A workspace opens beside the brief. The agent begins executing the
skill: streaming reasoning, tool calls (querying ClinicalTrials.gov, fetching
formulary data, running SQL against the canonical workspace), and writing
artifacts into the workspace as it goes. The clinician watches sections fill
in live. Critical decisions surface as approval gates the clinician must
acknowledge before the agent proceeds. Wrong turns get corrected via
inline-comment-style feedback that the agent reads on its next turn.

**Act 3 — The artifact.** When the agent finishes, the workspace contains a
durable, exportable, citation-grounded artifact: a trial-match shortlist with
inclusion-criterion-by-criterion fit notes, a medication-access plan with
links to live coupon programs, a prior-auth packet ready to attach to the
payer's portal, a second-opinion brief ready to email a specialist. Each fact
in the artifact has a citation chip — click it and you see either the FHIR
resource it came from or the external page it was scraped from, with a
timestamp.

### 3.2 The trust contract

The module's contract with the clinician is explicit:

1. **Cite or abstain.** Every assertion in the workspace either links back to
   a chart fact or an external source, or it carries a `[uncertain]` marker
   that means "the agent declined to answer; you handle this part."
2. **Show the work.** Every tool call is in the workspace transcript. The
   user can re-open any decision and see exactly which evidence the agent
   used, in what order, with what confidence.
3. **Don't act on the world without consent.** Phase 1 ships
   **artifact-producing** agents only. The agent drafts the prior-auth
   submission; the clinician submits it. The agent finds candidate trials;
   the clinician contacts coordinators. This is a regulatory simplification
   and a trust simplification, and it's what's actually shipping
   commercially right now (vs. agents that submit PA on their own, which are
   only just entering CMS pilots in [Jan 2026](https://www.jonesday.com/en/insights/2025/08/coming-january-2026-cms-launches-ai-program-to-screen-prior-authorization-requests-for-treatments)).
4. **Stop when uncertain.** The skill defines escalation triggers; when the
   agent hits one, it pauses and surfaces a prompt to the human. No
   unresolved-low-confidence outputs ship into the artifact.

### 3.3 The patient-facing variant

Some skills have a patient-facing audience tag. The Lab Result Explainer in
patient mode renders the same panel data as the clinician version, but the
agent runs a different output template: plain-language explanations,
"ask-your-doctor" prompts, no clinical-action recommendations. The skill
**declares its audience**; the runtime swaps the system prompt and the
output schema accordingly. One skill, two harnesses.

### 3.4 The marketplace

The Context Library section already in the app
([ClinicalInsights.tsx:602–733](../app/src/pages/Modules/ClinicalInsights.tsx))
becomes the natural marketplace surface. Today it shows reusable Markdown
context packages. We extend it to host **versioned skill packages**:

- A clinician browses skills by specialty, audience, and deterministic-vs-
  agentic shape.
- Each skill card shows a description, version, last-updated, evaluation
  scores against a hold-out patient cohort, and a "try on selected patient"
  button.
- A clinician can fork a skill (clone it into their org's skill library),
  edit the markdown, and run it locally.
- Anthropic's [`anthropics/skills`](https://github.com/anthropics/skills)
  repo is an upstream we can pull from; community medical libraries (e.g.,
  the [openclaw-medical-skills](https://github.com/openclaw/medical-skills)
  reference repo) become an import format.

### 3.5 What this is *not*

- **Not a generic chat interface over the chart.** Chart Q&A already covers
  the open-investigation case. Skill workspaces are for *known repeatable
  workflows* with structured outputs and evaluation criteria.
- **Not a no-code workflow builder.** Skills are markdown and code; the
  authoring experience is closer to writing a clinical SOP than to wiring a
  Zapier flow.
- **Not an act-on-the-world agent.** Phase 1 explicitly excludes agents that
  submit prior-auth, book appointments, contact patients, or change medical
  records. Those are Phase 2+ with regulatory work attached.
- **Not a replacement for deterministic modules.** Pre-Op Clearance, Lab
  Explainer, Cardiometabolic Briefing, Medication Safety, Kidney Safety are
  all rules-amenable. They stay as React pages. The skill harness is for the
  workflows that aren't.

---

## 4. The three module shapes (decision rule)

When a new clinical workflow is proposed, classify it before building:

| Shape | Definition | When to ship as | Examples |
|---|---|---|---|
| **Dashboard** | The chart contains the answer. Rules over chart facts produce a verdict. ≤30% LLM. | Hand-coded React page (the Pre-Op shell). | Pre-Op Clearance, Lab Explainer, Medication Safety, Cardiometabolic, Kidney Safety, Anesthesia Handoff |
| **Brief + Workspace** | The chart is the *brief*; the answer requires going to the world (web, registries, formularies, payer sites) or producing a structured artifact (letter, packet, plan). ≥60% LLM. | Skill file + workspace template. The brief panel is reused from the Dashboard shape; the workspace is where the agent works. | Med Access, Trial Match, Second Opinion, Payer Check, Grants, Cancer Survivorship, Clinical Profile |
| **Conversational** | The work is open-ended investigation; structure emerges from the conversation. | Existing Chart Q&A interface. | "What changed in this patient's labs over the last year?" |

The decision rule for the messy middle is: **if a clinician would reach for a
browser, a fax machine, or a Word document to finish the work, it's a Brief +
Workspace skill, not a Dashboard.**

---

## 5. Skill file format

We adopt the **Anthropic Agent Skills format** directly — it's what's
shipping across Claude.ai, Claude Code, the Agent SDK, and the Claude API
code-execution tool. ([API docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview))
That gets us interoperability with other agent harnesses for free.

A skill is a directory:

```
skills/
  trial-matching/
    SKILL.md              ← required: frontmatter + instructions
    workspace.template.md ← required for Brief+Workspace skills
    output.schema.json    ← required: structured output shape
    evals/
      patient-cohort.json ← hold-out patients with expected outputs
      rubric.md           ← what counts as a correct run
    references/
      inclusion-criteria-parsing.md
      ctgov-search-tips.md
    scripts/
      score_inclusion_match.py
```

### 5.1 `SKILL.md` — the required surface

```markdown
---
name: trial-matching
version: 1.2.0
audience: clinician          # clinician | patient | regulatory
shape: brief-workspace       # dashboard | brief-workspace | conversational
description: >
  Build a candidate-trial shortlist for a patient. Reads ClinicalTrials.gov,
  parses inclusion criteria against the chart, surfaces fit per trial, and
  produces a clinician-ready outreach packet. Use when the patient has at
  least one active body-system condition and the clinician has flagged
  research as an option of interest.
required_tools:
  - mcp.clinicaltrials_gov
  - mcp.pubmed
  - run_sql              # canonical workspace queries
  - workspace.write
  - workspace.cite
optional_tools:
  - mcp.rxnorm
context_packages:
  - oncology-staging
  - performance-status
input_schema: input.schema.json
output_schema: output.schema.json
escalation:
  - condition: "no anchor condition with verified staging"
    action: "stop_and_ask"
    prompt: "I cannot find verified staging for {anchor}. Confirm or provide?"
  - condition: "trial-fit scores all <40"
    action: "stop_and_summarize"
    prompt: "No strong matches. Summarize gaps and stop."
eval:
  rubric: evals/rubric.md
  cohort: evals/patient-cohort.json
  metrics: [precision_at_5, citation_validity, escalation_correctness]
---

## When to use

Run this skill when ...

## Phase 0 — Verify the brief

Before searching, confirm:
1. At least one active condition has `risk_category != "OTHER"` and
   `clinical_status == "active"`. If not, stop and ask.
2. ...

## Phase 1 — Generate search packet

For each anchor condition:
1. Call `mcp.clinicaltrials_gov.search` with body-system constraint and
   patient age band.
2. ...

## Phase 2 — Score per trial

For each candidate trial returned:
1. Read inclusion criteria via `mcp.clinicaltrials_gov.get_record`.
2. For each inclusion line, classify as: chart-supports | chart-contradicts
   | needs-verification.
3. ...

## Phase 3 — Write artifact

Open `workspace.template.md`. For each scored trial above the threshold:
1. Write a section. Each fact must call `workspace.cite()` with either a
   FHIR resource id or an external URL + access timestamp.
2. ...

## Output schema

See `output.schema.json`. Mandatory fields per trial entry: trial_nct_id,
fit_score (0–100), evidence_tier (T1–T4), supporting_facts[], gaps[],
escalation_triggered (bool).
```

### 5.2 What the format enforces (lessons from the openclaw review)

The user piloted the [openclaw-medical-skills](https://github.com/openclaw/medical-skills)
library and found it "not that useful." The sub-agent review (see Appendix A)
identified the failure mode: **most skills are tool wrappers, not decision
frameworks.** They teach the agent how to call DrugBank but not what to do
with the answer. None enforce output schemas, escalation rules, or
human-in-the-loop checkpoints; many describe outputs ("publication-ready
LaTeX with GRADE grading") that have no schema or implementation behind them.

To not repeat that, our format **requires** what openclaw's leaves optional:

1. **`output_schema` is mandatory.** Skills that produce artifacts must
   declare a JSON schema for what's in the artifact. The runtime validates.
2. **`escalation` is mandatory** for `brief-workspace` skills. At least one
   stop-and-ask condition. The runtime enforces; an agent cannot complete a
   run that should have escalated.
3. **`eval` is mandatory** before promotion to "Live". Each skill ships with
   a hold-out patient cohort and a rubric, and the marketplace shows the
   eval score. Skills without evals stay marked "Concept."
4. **`audience` is mandatory.** No skill works for both clinician and
   patient via the same prompt — output template must differ. Force the
   author to declare.
5. **`context_packages` and `required_tools` are first-class.** The skill
   declares what context bundles it expects pre-loaded and what tools it
   must have access to. The runtime refuses to run a skill whose tools
   aren't available.

We **borrow** what openclaw's better skills do well:
- **Phase-gated workflow** (their `tooluniverse-cancer-variant-interpretation`
  Phase 0→3 ordering): forces dependency ordering and reduces hallucination
  cascades. Adopted as the recommended `## Phase N` body structure.
- **Tool parameter correction tables**: the agent gets a table of common
  `wrong → right` parameter names for each MCP tool, captured once in the
  skill rather than re-discovered every run.
- **Evidence tiering (T1–T4)**: short-hand that's actionable and auditable;
  every fact citation in the workspace gets a tier.
- **Report-first pattern**: the agent opens the workspace template and
  writes section headers before populating, which keeps it honest about
  completeness.

---

## 6. System architecture

### 6.0 Layered architecture — one harness or many?

A natural question reading §5: do we ship one universal harness that runs
all skills, or does each skill ship its own purpose-built harness?

The answer is neither. **The architecture is layered.** Two layers are
universal; one is per-skill:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3 — Per-skill                                        │
│  System prompt, tool subset, output schema, escalation      │
│  conditions, eval cohort, optional agent topology override  │
│                                                             │
│  ALWAYS per-skill. Defined in SKILL.md.                     │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 2 — Default agent loop                               │
│  Multi-turn query, tool dispatch, citation collection,      │
│  escalation check                                           │
│                                                             │
│  ONE by default. Skills can override topology (planner +    │
│  specialist sub-agents, fan-out parsers, etc.) but sit on   │
│  Layer 1.                                                   │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — Universal substrate                              │
│  Workspace filesystem contract, citation graph, tracing,    │
│  escalation primitive, skill loader, MCP protocol           │
│                                                             │
│  ONE. No exceptions. This is the trust contract.            │
└─────────────────────────────────────────────────────────────┘
```

**Why Layer 1 is non-negotiable.** The marketplace argument: a clinician
using two skills must see the same workspace shape, the same approval gates,
the same evidence chips, or there is no trust contract. If Trial Matching's
citations resolve one way and Med Access's another way, this is not a
marketplace — it is a portfolio of one-offs. Today's hand-built module
pages *are* that portfolio. The point of the skill architecture is to
escape it. Specifically, these are uniform across every skill:

- **`workspace.cite()` is the only write path** to `workspace.md`.
  Otherwise an agent could ship uncited claims and the audit trail breaks.
- **Escalation primitive.** "This skill stops on uncertainty" only holds
  if every skill stops the same way.
- **Tracing.** Per-skill cost, escalation-rate, and citation-validity
  dashboards only work if every skill emits the same span shape
  ([api/core/tracing.py](../api/core/tracing.py)).
- **MCP wire protocol.** Skills speaking different tool protocols would
  destroy MCP server reuse — which is the only thing that prevents the
  "tool wrapper" failure mode openclaw fell into.

**Why a single default agent loop (Layer 2) is right for the 80% case.**
Trial Matching, Med Access, Lab Explainer in patient mode, Cardiometabolic,
Pregnancy & Postpartum — most skills work fine with a single multi-turn
loop + tool dispatch. **No need to write a bespoke runtime per skill.**
This also gives us a single place to harden behavior: when we improve
escalation handling, every skill benefits; when we add a new tracing field,
every skill captures it.

**Why per-skill escape hatches in Layer 2 are still important.** The 20%
case is real. Trial Matching, for example, would genuinely benefit from a
planner-executor split: a planner sub-agent decomposes "score 30 candidate
trials" into 30 parallel criterion-parsing calls (each cheaper, each
auditable). Forcing that into a flat loop hurts the skill. Skills that
need a specialist topology declare it in frontmatter:

```yaml
# In SKILL.md frontmatter
agent_topology: planner_executor       # default: flat
sub_agent_template: criterion_parser   # required if planner_executor
```

Skills that don't declare it get the flat default. Skills that override
still sit on the universal substrate, so they still get workspace
mediation, citation enforcement, escalation handling, and tracing.

**Why MCP servers are also universal (not per-skill).** Every skill talks
to the outside world through MCP, and MCP servers are shared.
`mcp.clinicaltrials_gov` is one server, callable by Trial Matching, Cancer
Survivorship, Pregnancy & Postpartum, anyone. The opposite — re-writing a
clinicaltrials.gov client inside every skill — is the exact failure mode
the openclaw review (Appendix A) flagged: "tool wrappers, not decision
frameworks." Each skill re-discovers the same API drift, the same parameter
gotchas, the same rate-limit handling. Universal MCP servers prevent that.

**The headline call.** Universal substrate. Universal default agent loop.
Universal MCP servers. **Per-skill everything that defines the actual
clinical work.** This is how Claude Code works. This is how Anthropic
Skills works. This is how this should work.

The components diagram below should be read with this layering in mind:
the Skill Loader, Workspace Runtime, Tool Harness, and Tracing are Layer 1.
The Agent Runtime is Layer 2. The skill files in the registry are Layer 3.

### 6.1 Components

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Skill Registry (FS)                          │
│  skills/<name>/SKILL.md + workspace.template.md + schemas + scripts  │
└──────────────────────────────────────────────────────────────────────┘
            │ read                              │ list / get
            ▼                                   ▼
┌────────────────────────┐         ┌────────────────────────────────┐
│  Skill Loader          │         │  Marketplace UI                │
│  - parse frontmatter   │◄────────┤  /clinical-insights/skills/... │
│  - validate schemas    │         │  fork / try / install          │
│  - register tools      │         └────────────────────────────────┘
└────────────────────────┘
            │
            │ skill_run(patient_id, skill_name, brief_overrides)
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      Workspace Runtime                                │
│  - allocate workspace dir: /cases/{patient_id}/{skill}/{run_id}/      │
│  - copy workspace.template.md as draft                                │
│  - mount context packages + canonical workspace                       │
│  - stream agent turns to UI; persist transcript                       │
└──────────────────────────────────────────────────────────────────────┘
            │                                   │
            │                                   ▼
            │                       ┌──────────────────────────────┐
            │                       │  Agent Runtime               │
            │                       │  (extended provider_assistant│
            │                       │   _agent_sdk.py)             │
            │                       │  - multi-turn query loop     │
            │                       │  - tool dispatch             │
            │                       │  - citation collection       │
            │                       │  - escalation check          │
            │                       └──────────────────────────────┘
            │                                   │
            ▼                                   ▼
┌──────────────────────────────────┐  ┌──────────────────────────────┐
│  Tool Harness                    │  │  Tracing                     │
│  Local tools:                    │  │  api/core/tracing.py         │
│   - run_sql                      │  │  - per-turn spans            │
│   - workspace.write/cite/escalate│  │  - tokens / cost / errors    │
│   - get_patient_snapshot         │  │  - SQLite + Langfuse         │
│   - query_chart_evidence         │  │                              │
│  MCP servers:                    │  │                              │
│   - clinicaltrials.gov           │  │                              │
│   - rxnorm / openfda             │  │                              │
│   - pubmed                       │  │                              │
└──────────────────────────────────┘  └──────────────────────────────┘
```

### 6.2 What's already shipping (don't rebuild)

The codebase survey (Appendix B) confirmed the following primitives are
already in production:

- **Three-mode agent runtime** in `api/core/provider_assistant_service.py:59`
  with deterministic / context / agent-sdk fallback — the skill runtime
  becomes a fourth mode (or extends `agent-sdk` mode) rather than
  greenfield.
- **MCP-shaped tool registry** in `api/core/provider_assistant_agent_sdk.py:284`
  with three tools: `get_patient_snapshot`, `query_chart_evidence`,
  `run_sql`. SQL tool is SELECT-only-gated, 500-row capped. Citation
  reconstruction at `provider_assistant_agent_sdk.py:475`.
- **Comprehensive tracing** in `api/core/tracing.py:76` — per-turn spans
  with input_tokens / output_tokens / cache_read / cost / duration, exported
  to SQLite (`data/traces.db`) and Langfuse. Skills get observability for
  free.
- **Context packages** scaffolded in `app/src/types/index.ts:576` and
  `app/src/context/ChatContext.tsx:51` — currently UI-shape-only, but the
  type already matches what skills need (id, title, type, summary,
  instructions). Lift this into the skill loader.
- **Provenance graph** in the harmonize layer
  ([api/routers/harmonize.py](../api/routers/harmonize.py)) — every fact
  carries lineage. Workspace citations should resolve through this graph,
  so a "click to see source" links from the artifact through silver →
  bronze → original document.

### 6.3 Workspace runtime

A workspace is a **filesystem directory** the agent can read and write,
mirroring the Claude Code / Cursor / Devin pattern that has hardened across
the industry. ([Plans vs tasks — agent design](https://openwalrus.xyz/blog/plans-vs-tasks-agent-design))

```
/cases/{patient_id}/{skill_name}/{run_id}/
  brief.json              # frozen brief inputs (clinician edits go here)
  workspace.md            # draft artifact, agent edits live
  transcript.jsonl        # per-turn record (prompt, tool calls, tokens, cost)
  citations.jsonl         # every cite() call with source kind + ref
  approvals.jsonl         # every escalation gate + clinician decision
  output.json             # validated against output_schema, locked at finish
  artifacts/
    prior-auth-letter.pdf
    candidate-trials.csv
```

Properties:

1. **Append-only.** Agent edits are diffable; the user can scroll back through
   the entire run.
2. **Forkable.** A workspace can be cloned to "what if I changed the brief?"
   — runs are cheap.
3. **Diffable.** The UI shows the current `workspace.md` with inline
   provenance chips and a sidebar transcript of tool calls.
4. **Quotable.** Every `workspace.cite()` registers a citation chip in the
   markdown that resolves to the source.

The `workspace.write`, `workspace.cite`, and `workspace.escalate` tools are
the only way the agent edits the artifact. There is no free-form file write
to `workspace.md`. The runtime mediates so that:
- every write checks against the output schema,
- every assertion has a citation or an explicit `[uncertain]` marker, and
- escalations actually pause the run.

### 6.4 Tool harness — local tools vs. MCP

We already have a partial split; we make it explicit:

**Local tools (in-process, fast, deterministic):**
- `run_sql` — SELECT-only against the canonical SOF workspace. Already
  ships.
- `get_patient_snapshot` — pre-digested patient context. Already ships.
- `query_chart_evidence` — RAG over chart facts. Already ships.
- `workspace.write(section, content, citations[])` — append/replace section
  of `workspace.md`.
- `workspace.cite(claim, source_kind, source_ref, evidence_tier)` — register
  a citation. `source_kind` ∈ {`fhir_resource`, `external_url`,
  `clinician_input`, `agent_inference`}. `agent_inference` is allowed but
  must carry a tier (T4 by default).
- `workspace.escalate(reason, prompt)` — pause the run, surface the prompt
  to the clinician.

**MCP servers (out-of-process, networked, reusable):**
- `mcp.clinicaltrials_gov` — search / get_record / parse_eligibility.
- `mcp.rxnorm` — drug normalization, ingredient lookup.
- `mcp.openfda` — adverse events, label lookup.
- `mcp.pubmed` — literature search, abstract fetch.
- `mcp.payer_formulary` (future) — coverage lookup.

The split rule: **anything that's a shared data source goes MCP; anything
that's specific to our workspace contract or our chart is local.** This
matches where the industry has converged ([awesome-medical-mcp-servers](https://github.com/sunanhe/awesome-medical-mcp-servers))
and means our MCP servers are independently reusable by any agent harness,
not just ours.

### 6.5 Citation graph

Every assertion in `workspace.md` resolves through the existing Provenance
graph from [ATLAS-DATA-MODEL.md](ATLAS-DATA-MODEL.md):

```
agent claim
  └─ workspace.cite(...)
       └─ source_kind: "fhir_resource"
            └─ resource_id (e.g., Condition/abc-123)
                 └─ silver layer (canonical FHIR R4)
                      └─ bronze layer (raw extracted)
                           └─ original document (PDF, JSON export)
```

For external sources:

```
agent claim
  └─ workspace.cite(...)
       └─ source_kind: "external_url"
            └─ url + access_timestamp + hash
                 └─ persistent snapshot in artifacts/sources/
```

The runtime archives a snapshot of every external source the agent reads, so
that workspace citations resolve even if the source page changes. This is
the audit-trail layer; it's what makes the artifact admissible as evidence
for prior-auth, clinical handoff, or regulatory review.

### 6.6 Tracing + observability

The existing tracing layer (`api/core/tracing.py`) already captures per-span
input/output tokens, cache reads, cost, and duration. Skills add three
trace fields:

- `skill_id` and `skill_version` on the trace.
- `escalation_count` and `escalation_resolutions[]` on the trace.
- `citation_validity_score` (computed offline by the eval harness against
  the cited sources).

This gives skill authors a per-skill dashboard: cost per run, escalation
rate, citation health, eval drift. Without this, a marketplace devolves
into "skills that look impressive but fail in production" — exactly the
openclaw failure mode.

### 6.7 Where agent processes run — the worker phases

The doc up to here has been silent on *where* skill runs actually execute.
That's a real infrastructure call with real tradeoffs, and it changes
across the lifecycle. The destination is **a per-run sandboxed container
on the host**, but Phase 1 ships something simpler. This section captures
the phases so future contributors don't relitigate.

**Destination architecture (what we want eventually):**

```
┌─────────────────────────────────────────────────────────────┐
│  Hetzner host (existing single-server prod box)              │
│                                                              │
│  ┌────────────────┐  ┌──────────────────────────────────┐   │
│  │  FastAPI       │  │ Workspace filesystem              │   │
│  │  (long-lived)  │◄─┤ /var/lib/ehi-ignite/cases/...    │   │
│  │                │  │ Persistent across runs.           │   │
│  └────────┬───────┘  └──────────────────────────────────┘   │
│           │                                                  │
│           │ docker run --rm                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Per-run sandbox container (ephemeral)               │   │
│  │  - mounts /workspace read/write (case dir only)      │   │
│  │  - allow-list network to MCP servers + Anthropic API │   │
│  │  - cgroup limits: cpu=1, mem=2G, time=600s           │   │
│  │  - non-root user, read-only rootfs except /workspace │   │
│  │  - skill files copied in read-only at start         │   │
│  │                                                       │   │
│  │  Runs: agent loop, tool dispatch, skill scripts/     │   │
│  └────────┬─────────────────────────────────────────────┘   │
│           │                                                  │
│           │ HTTPS only, allow-listed                         │
│           ▼                                                  │
│  ┌──────────────────────┐   ┌────────────────────────────┐  │
│  │  MCP servers         │   │  Anthropic API             │  │
│  │  (own containers)    │   │  (off-host)                │  │
│  └──────────────────────┘   └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key boundary:** the **workspace filesystem lives on the host**. FastAPI
mediates writes via the `workspace.write` tool to a host volume. The
**sandbox is ephemeral compute** — it gets the case directory mounted
in, runs the skill, dies. Persistent state, audit trail, citations,
transcripts all live on the host. If the sandbox crashes mid-run, the
partial workspace survives and is replayable.

**Why container, not VM.** Hypervisor-level VMs (KVM) are ~30s boot and
gigabytes of memory each — wrong scale for hundreds of skill turns per
hour. Containers (Docker / Podman) start in milliseconds, get OS-level
isolation via namespaces + cgroups, are mature, and already exist in our
stack via Docker Compose. microVMs (Firecracker, gVisor, Kata) close the
isolation gap at near-container speed and become worth it when we're
running *third-party* code with arbitrary scripts.

#### Worker phases

Each phase is a delta on the previous one. We move forward only when a
trigger fires; we do not sandbox prematurely.

| Phase | Worker shape | When | Threat model | Cost to build |
|---|---|---|---|---|
| **W0** | In-process async task inside FastAPI | Today (provider_assistant_agent_sdk.py runs this way) | Trusted code only. Buggy skill blocks API request handlers. | $0 — already running |
| **W1** | Separate worker process on host (Celery / RQ / native asyncio worker pool) | **Phase 1 (Ignite May 13)** | Trusted code only. Runaway skill no longer blocks API. Same filesystem and network as host. | ~2 hours |
| **W2** | Per-run Docker container on host | **Phase 2** — triggered by any of: importing community skills, accepting real PHI, multi-tenant orgs | Untrusted skill code. Agent restricted to mounted case dir + allow-listed network. | ~1–2 weeks |
| **W3** | Per-run microVM (Firecracker / gVisor) | **Phase 2.5+** — triggered by: hostile third-party scripts, regulated environments demanding hypervisor isolation | Adversarial skill code. Kernel boundary between agent and host. | ~2–4 weeks |
| **W4** | Off-host sandbox service (Modal, e2b, Daytona, or Anthropic code-execution) | **Optional escape hatch** — when ops cost of running our own sandbox exceeds the per-run vendor cost | Same as W2/W3 but operationally outsourced. | Vendor onboarding only |

**Why W1 is right for Phase 1.** Threat model in Phase 1 is benign: all
skill code is ours, all MCP servers are ours, all scripts reviewed before
merge, Synthea data only — no real PHI. The sandbox buys ~zero security
in that environment, while costing real engineering time we don't have
before May 13. The only required Phase 1 hardening is moving the agent
loop out of the request handler so a long-running skill doesn't block API
traffic — that's a 2-hour change.

**What forces W2 (sandbox).** Three triggers, **any one** of which
mandates the migration:

1. **Importing community skills.** First time we accept upstream
   `anthropics/skills` or [openclaw-medical-skills](https://github.com/openclaw/medical-skills)
   into the runtime, third-party Python lands in `scripts/`. Sandbox
   before this merges.
2. **Real PHI.** HIPAA risk analysis wants documentable per-tenant
   isolation; "we trust our code" is not an acceptable answer to an
   auditor.
3. **Multi-tenant orgs.** A skill from org A's library must not be able
   to read org B's workspace files. The host FastAPI process can; a
   per-tenant-mounted sandbox cannot.

The earliest of those probably hits mid-2026. The current architecture
is correct for now, and the migration to W2 is well-scoped (extract the
agent loop into a `docker run` invocation; the workspace contract and
tool harness already enforce the right boundaries).

**What forces W3 (microVM).** Adversarial skill code — e.g., a community
skill author who is hostile, or scripts pulled from arbitrary sources.
Container escape via kernel exploit becomes a credible threat model.
Until we run skills from sources we genuinely don't trust, W2 is enough.

**What never moves into the sandbox** (regardless of phase):

- **FastAPI itself** — stays on the host, mediates workspace writes,
  owns the audit trail.
- **Workspace filesystem** — persistent on host, mounted into the
  sandbox at `/workspace` with the single case directory scoped.
- **MCP servers** — their own long-lived containers, called over HTTPS
  from inside the sandbox. Spinning them per run would break connection
  pooling to upstream APIs (clinicaltrials.gov etc.) and waste
  significant per-run startup cost.
- **Anthropic API call** — sandbox calls out; we don't host the LLM.

#### Migration shape

The key design property: **moving from W1 → W2 should not require
changing skill code or workspace contracts.** Skills already write only
through `workspace.write` / `workspace.cite` / `workspace.escalate`. The
runtime mediates those calls. When we move to W2, those tools become
host-side endpoints the in-sandbox agent calls over a unix socket
mounted into the container; the skill author sees no difference.

If a Phase 1 contributor sees themselves writing skill code that
*requires* sandbox isolation (e.g., expecting a fresh filesystem at
start, expecting outbound network to be blocked, expecting no /etc
access), that's a smell — the skill is leaking infrastructure
assumptions. Skills should be sandbox-agnostic; the runtime decides.

---

## 7. Worked example — Trial Matching as a skill

To make the format concrete, here's how today's hand-built `/trials` page
re-shapes:

### What stays
The current page becomes the **brief panel** (the verdict hero + per-anchor
classification + record-span context). It's already drawing from
`getOverview` + `getConditionAcuity` + `getProcedures` and it's already
organized exactly the way an agent should consume it. Don't delete it; it's
the input view.

### What's added
Beside the brief, a workspace panel. When the clinician clicks **Run**:

1. **Phase 0 (verify):** Agent calls `get_patient_snapshot` and the
   classifyAnchor logic re-runs server-side. If no anchor scores ≥ ANCHOR,
   `workspace.escalate` fires immediately with "no anchor — confirm or
   skip."
2. **Phase 1 (search):** For each ANCHOR, the agent calls
   `mcp.clinicaltrials_gov.search` with body-system + age-band constraints
   from the brief. Returns top N trials per anchor.
3. **Phase 2 (parse):** For each candidate trial, agent calls
   `mcp.clinicaltrials_gov.get_record` and parses inclusion/exclusion
   criteria. For each criterion, classifies against chart facts via
   `query_chart_evidence` (chart-supports / chart-contradicts /
   needs-verification). Each classification carries an evidence tier.
4. **Phase 3 (score):** Per-trial fit_score (0–100) computed from
   inclusion-support counts, weighted by tier. Sub-40 trials dropped.
5. **Phase 4 (write):** Agent opens `workspace.template.md` and writes one
   section per surviving trial:
   - NCT id, title, sponsor, phase, status
   - Why this trial — links back to which anchor it matches
   - Inclusion-by-inclusion fit table with citation chips
   - Gaps to verify before contacting (e.g., "no recent imaging — confirm")
   - Geographic options + contact info
6. **Phase 5 (artifact):** Outreach-ready packet exported as PDF; CSV
   shortlist for the patient's records.

If at any point fit_score for all candidates is < 40, escalation fires:
"No strong matches. I can broaden the search to second-tier anchors or
stop. Which?"

### Eval cohort
20 patients with ≥1 high-acuity condition + known trial enrollment history
(from the Synthea cohort augmented with annotated ground-truth). Rubric:
precision@5, citation validity (does the cited fact actually appear in the
linked FHIR resource?), and escalation correctness (does the agent
correctly stop when a no-match condition is true?).

### Why this is better than today's page
Today's `/trials` page tells the clinician what *would* be useful; the skill
version *does* it. The page-shaped version was honest enough to label its
own future-state preview "Future card." The skill-shaped version replaces
that preview with actual trials.

---

## 8. Marketplace + distribution

The Context Library page already in the app
([ClinicalInsights.tsx:602–733](../app/src/pages/Modules/ClinicalInsights.tsx))
is the obvious home. We extend it from "browse markdown context packages"
to "browse versioned skills":

1. **Public registry** (read-only): pulls from `anthropics/skills` upstream
   + a curated EHI-Ignite skills repo. Each skill listing shows description,
   version, audience, eval scores, last-run cost.
2. **Org library** (read-write): clinicians fork from public, edit locally,
   run on selected patients. Version-controlled in a Git submodule.
3. **Per-patient pinning**: a clinician can pin specific skills to a
   patient's chart so they're one click from the chart view.
4. **Eval gate**: a skill in the org library cannot be marked "Live" (vs.
   "Concept") without a passing eval against the cohort. The marketplace
   shows the eval status as a badge.

This is also how we relate to the broader skill ecosystem:

- **Anthropic Skills** is upstream — we adopt the format exactly.
- **MCP servers** are independent — our `mcp.clinicaltrials_gov` is
  publishable to [mcp.so](https://mcp.so) for any agent harness to use.
- **Community medical skills** (the openclaw-medical-skills repo) are
  importable via the loader, with a "concept" badge until they pass our
  eval cohort.

---

## 9. Phase 1 (Ignite submission) vs Phase 2

Given the May 13, 2026 Phase 1 deadline, the realistic scope:

### Phase 1 — concept + first reference implementation
1. **Doc + format spec** (this file).
2. **Skill loader + workspace runtime** wired into the existing
   `provider_assistant_agent_sdk.py` runtime — minimum viable: load
   `SKILL.md`, validate frontmatter, expose `workspace.write` and
   `workspace.cite` tools, persist to `/cases/{pid}/{skill}/{run_id}/`.
3. **Worker phase W1** — agent loop runs in a separate worker process,
   not in the FastAPI request handler. No sandbox yet (see §6.7).
4. **One reference skill shipped end-to-end** — Trial Matching. The
   `/trials` page becomes the brief panel for it.
5. **One MCP server** — `mcp.clinicaltrials_gov` (or wire to an existing
   community one).
6. **Marketplace listing card** for the one skill, demonstrating the model.

This is enough for the Phase 1 submission to claim "we've moved beyond a
portfolio of dashboards to a marketplace of clinical agents." Pre-Op stays
as the deterministic-dashboard reference exhibit; Trial Matching becomes
the agentic-workspace reference exhibit.

### Phase 2 — depth + breadth
- **Worker phase W2** — per-run Docker sandbox. Triggered by the first of:
  community skill imports, real PHI, or multi-tenant orgs (see §6.7).
- Add Med Access, Second Opinion, Payer Check, Grants as skills.
- Add MCP servers for RxNorm, OpenFDA, PubMed, payer formularies.
- Eval harness with reproducible cohort runs.
- Public skill registry import path.
- Patient-audience variants for the consumer-facing skills (Lab Result
  Explainer in patient mode, Caregiver View).

---

## 10. Open questions / contested calls

These are the places this proposal makes a deliberate call where the
industry hasn't fully converged. Each is a place a future architect should
revisit:

1. **Skills vs. MCP for clinical workflows.** We argue: skills for
   workflows, MCP for shared data. But there's a real argument for the
   opposite: clinical workflows-as-MCP-servers makes them harness-portable.
   We choose skills because Anthropic's progressive-disclosure model
   (metadata → SKILL.md → siblings) is better for long instructional bodies
   than MCP's tool-list shape. Revisit if MCP adds first-class instructional
   content.

2. **Computer-use / browser-driving agents.** We explicitly defer. Browser-
   driving (Claude in Chrome, Anthropic Computer Use) is too brittle for
   clinical-grade audit trails today. Revisit when latency + audit-trail
   gaps close, probably late 2026.

3. **Acting-on-the-world agents.** We explicitly defer. Phase 1 produces
   artifacts the human submits. Phase 2 will need a separate auth layer for
   "submit prior auth on my behalf" — likely modeled on
   [CMS WISeR (Jan 2026)](https://www.jonesday.com/en/insights/2025/08/coming-january-2026-cms-launches-ai-program-to-screen-prior-authorization-requests-for-treatments)
   conventions when those publish.

4. **Eval cohort source.** We use the Synthea cohort for now. For
   marketplace listings to be trustworthy, we eventually need real-world
   evaluation — annotated by clinicians, not synthetic. This is a
   significant Phase 2 cost.

5. **Skill versioning + breaking changes.** Anthropic Skills currently has
   no formal version semantics. We adopt semver in the frontmatter and a
   `--skill-version=` pin in the runtime, but this is ahead of the
   upstream standard. Revisit if Anthropic publishes their own
   versioning convention.

6. **Skill authoring UX.** First version is "edit markdown in your editor +
   commit." A no-code authoring UI is tempting but probably wrong: the
   audience is clinicians who write SOPs, not consumers who write
   workflows. The format is a clinical SOP, not a Zapier flow. Revisit if
   that proves wrong with users.

7. **One harness or many?** Resolved in §6.0: one universal substrate
   (workspace, citations, tracing, escalation, MCP protocol) + one default
   agent loop with frontmatter-declared topology overrides + per-skill
   prompts/tools/schemas. The contested edge is whether the topology
   override (`agent_topology: planner_executor` etc.) belongs in the skill
   format or in a separate registry of agent recipes. We start with
   in-frontmatter; revisit if topologies proliferate beyond ~3 patterns.

---

## Appendix A — openclaw-medical-skills review

See sub-agent report 2026-05-04. Summary: 869 skills as flat
`/skills/<name>/SKILL.md` directories with YAML frontmatter; standard fields
`name`, `description`, `allowed-tools`. Strong examples
(`tooluniverse-clinical-trial-matching`,
`tooluniverse-cancer-variant-interpretation`, `epidemiologist-analyst`)
exhibit phase-gated workflow, evidence-tiering, and tool-parameter
correction tables — patterns we adopt. Weak examples
(`clinical-decision-support`, `drug-interaction-checker`, `adhd-daily-planner`)
are tool wrappers without output schemas, escalation rules, or eval
criteria — failure mode we reject by making those fields mandatory in our
format. **Most skills there are tool wrappers, not decision frameworks; that
is why the user found them not useful.**

---

## Appendix B — codebase primitives that already ship

See sub-agent report 2026-05-04. Confirmed primitives, with line refs:

| Primitive | File | Notes |
|---|---|---|
| Agent runtime (3-mode) | `api/core/provider_assistant_service.py:59` | Skill loader extends `agent-sdk` mode |
| MCP-shaped tool registry | `api/core/provider_assistant_agent_sdk.py:284` | run_sql, get_patient_snapshot, query_chart_evidence |
| Citation reconstruction | `api/core/provider_assistant_agent_sdk.py:475` | Workspace cite() reuses this |
| Tracing + cost capture | `api/core/tracing.py:76` | Skills get observability free |
| Context packages | `app/src/types/index.ts:576`, `app/src/context/ChatContext.tsx:51` | Lift into skill loader |
| Provenance graph | `api/routers/harmonize.py` | Citations resolve through this |
| Canonical workspace facade | `api/routers/canonical.py` | Source-agnostic chart read |

---

## Appendix C — industry signals (May 2026)

See sub-agent report 2026-05-04. Key external anchors this design cites:

- [Anthropic — Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) — format we adopt.
- [Agent Skills overview — Claude API docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — runtime contract.
- [anthropics/skills GitHub](https://github.com/anthropics/skills) — upstream.
- [Plans vs tasks — agent design](https://openwalrus.xyz/blog/plans-vs-tasks-agent-design) — workspace pattern.
- [CareGuardAI multi-agent guardrails](https://arxiv.org/abs/2604.26959) — controller + dual scoring.
- [Nature Sci Reports — LLM guardrails for safety-critical medicine](https://www.nature.com/articles/s41598-025-09138-0) — citation-or-refuse hardening.
- [Comms Medicine — adversarial vulnerability in clinical LLMs](https://www.nature.com/articles/s43856-025-01021-3) — 15–40% hallucination on clinical tasks; argues for verification gates.
- [Jones Day — CMS WISeR AI PA pilot Jan 2026](https://www.jonesday.com/en/insights/2025/08/coming-january-2026-cms-launches-ai-program-to-screen-prior-authorization-requests-for-treatments) — regulatory frame for acting-on-world agents.
- [awesome-medical-mcp-servers](https://github.com/sunanhe/awesome-medical-mcp-servers) — MCP medical ecosystem.

---

*End of document.*
