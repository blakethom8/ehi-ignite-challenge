# Harmonization vs. Claude — Head-to-Head Evaluation Guide

*Status: load-bearing for the Phase 1 narrative. Last updated: 2026-05-12.*

> **Purpose.** This is the runbook for empirically answering the question that keeps coming up: *"Does Atlas's PDF → FHIR → harmonization pipeline actually do anything that a clinician couldn't get from uploading the same PDFs to Claude.ai?"* It defines a fixed question set, a paired-response capture protocol, an LLM-as-judge blind evaluation, and a results structure that lets us re-run the test as the pipeline evolves.

If this test shows Atlas indistinguishable from raw Claude on the realistic user inputs, the harmonization wedge is in trouble and we should re-evaluate the demo framing. If it shows Atlas winning meaningfully on multi-source / provenance / cohort questions, those become the Phase 1 talking points.

---

## Why this exists

A clinician handed five real patient PDFs to Claude.ai and asked fuzzy chart-review questions. Claude.ai answered well. The toolchain was `pdftotext -layout | grep | read` — no extraction pipeline, no FHIR, no harmonization. This raised a legitimate strategic question: where, exactly, does the multi-pass extraction + harmonization stack earn its keep?

The honest answer from [PDF-PROCESSOR.md](./PDF-PROCESSOR.md) is that the pipeline earns its keep on:

1. **Multi-source longitudinal queries** (trajectory of HDL across 5 years and 4 sources)
2. **Cross-source identity resolution** (same medication appearing in Cedars FHIR text-only + Cedars PDF + Function Health)
3. **Vision-wins** (imaging findings in narrative that the structured EHR never coded)
4. **Provenance / citation** (click any fact → see the exact source PDF + page + bbox)
5. **Cohort / structured queries** (list every lab above reference range, grouped, sorted, deterministic)
6. **Determinism + auditability** (same input → same FHIR Bundle, every time)

This eval is the empirical test of those six claims.

---

## The two systems

### System A — Atlas (harmonized stack)

- **Interface:** Caspian chat at `https://ehi.healthcaredataai.com/caspian` (or local `http://localhost:5173/caspian`)
- **Underlying data:** the `blake-real` harmonization workspace, which merges:
  - Cedars-Sinai FHIR pull (`cedars-healthskillz-download/health-records.json`)
  - Cedars-Sinai Health Summary PDF (extracted via `multipass-fhir` → `extracted-cedars-healthsummary.json`)
  - Function Health PDF · 2024-07-26 (extracted)
  - Function Health PDF · 2024-07-29 (extracted)
  - Function Health PDF · 2025-11-29 (extracted)
- **What this exercises:** the full pipeline — multi-pass extraction, harmonization (`lib/harmonize/`), Provenance graph, `run_sql` tool over `data/sof.db`, Caspian agent SDK reasoning.

### System B — Vanilla Claude (baseline)

- **Interface:** [claude.ai](https://claude.ai) chat with the Claude Opus 4.7 model (match the model used by Caspian for fairness)
- **Inputs attached to the conversation:** the four PDFs only —
  - `HealthSummary_May_03_2026/Cedars-HealthSummary.pdf`
  - `blake_function_pdfs/2024-07-26.pdf`
  - `blake_function_pdfs/2024-07-29.pdf`
  - `blake_function_pdfs/2025-11-29.pdf`
- **What this exercises:** Claude's built-in PDF reading + reasoning. No extraction pipeline, no FHIR, no harmonization, no SQL warehouse. This simulates a patient or clinician who has the PDFs but not Atlas.

### Why the Cedars FHIR JSON is excluded from System B

The product story is *"normalize and harmonize across record types from PDFs alone"* ([PDF-PROCESSOR.md Decision 2](./PDF-PROCESSOR.md)). Most patients don't have SMART portal access; most providers don't ship structured FHIR. The realistic head-to-head is *"the user has the PDFs."* Handing System B the Cedars FHIR JSON would turn the comparison into a routing-engine test, not a harmonization test.

Note: the Cedars FHIR pull *is* used inside System A as one of the harmonized sources — that's the entire point. The asymmetry is the test.

---

## The question set

Ten questions, two per category. Categories are chosen to span where each system is *expected* to perform differently. A well-shaped result has System A winning B / C / D / E and tying or losing A — that's the evidence the wedge is real.

| # | Category | Question |
|---|---|---|
| 1 | A. Single-doc fuzzy | "Summarize my most recent Cedars-Sinai visit. What was it for, what was found, and what was the plan?" |
| 2 | A. Single-doc fuzzy | "What did my November 2025 Function Health lab panel test for, and were there any abnormal results?" |
| 3 | B. Longitudinal | "What is my HDL cholesterol trajectory across all my records? List every reading with date and source, and tell me whether it's trending up, down, or flat." |
| 4 | B. Longitudinal | "Has my creatinine ever been outside the normal reference range? Show every creatinine reading you can find across all my documents, with date and source." |
| 5 | C. Vision-wins | "Are there any imaging findings, exam findings, or pathology results in my documents that were never formally coded onto my active problem list? List each one with its source." |
| 6 | C. Cross-source | "Which medications appear in more than one of my documents (cross-source confirmed), and which appear in only one (single-source)?" |
| 7 | D. Provenance | "What is my most recent hemoglobin A1c value, and exactly which document — including section or approximate page — does that value come from?" |
| 8 | D. Provenance | "Which source documents contributed to my list of active medications, and how many medications came from each source?" |
| 9 | E. Cohort | "List every lab value I have above its reference range in the last 24 months. Group by lab name, show the date, the value, the reference range, and the source for each." |
| 10 | E. Cohort | "Build a problem list from all my documents combined and deduplicated. For each problem, indicate whether it is confirmed by multiple sources or only one." |

### Frozen question set policy

These ten questions are **frozen for the v1 run**. Do not edit them mid-eval — re-runs must use the same questions to be comparable. If you need to amend the set, save it as v2 in this doc with a new dated section and run a fresh full eval; do not silently change v1.

---

## Run protocol

### Setup (do once)

1. Confirm the `blake-real` workspace is live in System A:
   - Open `https://ehi.healthcaredataai.com/caspian` (or local equivalent)
   - Confirm the workspace selector shows "Blake Thomson — real EHI exports" and the source rail shows all five sources
2. Open a new Claude.ai conversation (System B). Attach the four PDFs listed above. Verify all four uploaded successfully.
3. Create a run directory: `data/evals/harmonization-vs-claude/<YYYY-MM-DD>_run-NN/`. Inside, create:
   - `README.md` — see template below
   - One subdirectory per question: `q01/` through `q10/`
4. Generate per-question A/B assignment (which system is labeled "Response A" vs "Response B" in the judge prompt). Use a coin flip or a fixed seed. Record in `assignments.json`:
   ```json
   {
     "q01": {"A": "atlas", "B": "claude"},
     "q02": {"A": "claude", "B": "atlas"},
     "q03": {"A": "atlas", "B": "claude"},
     ...
   }
   ```
   Random per question — never let the judge see a stable pattern.

### Per question (do ten times)

For each question `qNN`:

1. **Run System A.** Paste the question verbatim into Caspian. Wait for the full response (including any tool-call streaming). Copy the final answer + any visible citations into `qNN/atlas_response.md`. Do not edit; preserve formatting.
2. **Run System B.** Paste the same question verbatim into the Claude.ai conversation (the one with the four PDFs already attached). Copy the response into `qNN/claude_response.md`.
3. **Anonymize.** Strip any system-identifying language from both responses:
   - Remove headers / branding (e.g., "Caspian thinks...", "I'm Claude...")
   - Remove tool-call traces that name internal tools (`run_sql`, `harmonize_lookup`, etc.) — replace with `[tool call: data lookup]` so the judge sees that *a* tool fired but not which system's tooling
   - Keep all factual content, citations, structure, formatting
4. **Save anonymized versions** as `qNN/response_a.md` and `qNN/response_b.md` per the assignment in step 4 of setup. These are the files the judge sees.
5. **Save the question** verbatim as `qNN/question.md`.

### Judging (do ten times, fresh judge conversation per question)

Open a fresh Claude conversation (no project memory, no carry-over context). For each question:

1. Paste the judge prompt below verbatim.
2. Paste the question.
3. Paste `response_a.md`.
4. Paste `response_b.md`.
5. Save the judge's JSON output to `qNN/judge.json`.

**Use a fresh conversation per question.** Carry-over context can bias the judge toward one system's stylistic patterns.

---

## Judge prompt (copy-paste verbatim)

```
You are evaluating two AI responses to a clinical chart-review question
about a real patient's medical records. The patient has five source
documents covering 2024-2025:

  - A Cedars-Sinai Health Summary PDF (multi-page, includes encounters,
    problems, medications, labs, imaging narratives)
  - Three Function Health Quest lab report PDFs (2024-07-26, 2024-07-29,
    2025-11-29) — multi-page panels covering metabolic, lipid, hormone,
    inflammatory, and other markers
  - (One system also has access to a structured Cedars FHIR pull;
    the other does not. You do not know which is which.)

You will see the question, then Response A and Response B. You do NOT
know which system produced which response. Evaluate them fairly and
independently.

Score each response on a 0-3 scale:
  0 = missing or wrong
  1 = poor
  2 = adequate
  3 = excellent

Dimensions:

  1. CORRECTNESS — Are the facts stated true and supportable from the
     source material? Penalize hallucinated values, made-up dates,
     invented citations, or confident-sounding claims that can't be
     verified.

  2. CITATION QUALITY — Does the response trace specific facts back
     to specific documents (or pages, sections, bbox locators)? A
     response that says "your HDL was 67" without saying which document
     scores lower than one that says "your HDL was 67 in the Cedars
     Health Summary PDF, lipid panel section."

  3. CLINICAL UTILITY — Would a clinician doing 30-second chart review
     find this useful? Is it specific, decisive, and time-saving — or
     vague and hedging?

  4. MULTI-SOURCE SYNTHESIS — Does the response correctly integrate
     information across multiple source documents (build a trajectory,
     dedupe a list, compare across sources)? Mark "NA" if the question
     does not require multi-source synthesis.

Then pick a winner: "A", "B", or "tie".

Be skeptical. A polished-sounding response with unverifiable claims
is worse than a shorter, citation-anchored one. If both responses make
unverifiable claims, score them both low on correctness.

Output STRICT JSON, nothing else:

{
  "response_a": {
    "correctness": <int 0-3>,
    "citation": <int 0-3>,
    "utility": <int 0-3>,
    "synthesis": <int 0-3 or "NA">
  },
  "response_b": {
    "correctness": <int 0-3>,
    "citation": <int 0-3>,
    "utility": <int 0-3>,
    "synthesis": <int 0-3 or "NA">
  },
  "winner": "A" | "B" | "tie",
  "rationale": "<2-3 sentence explanation of the winner choice>"
}

QUESTION:
<paste question here>

RESPONSE A:
<paste response_a.md here>

RESPONSE B:
<paste response_b.md here>
```

---

## Results structure

```
data/evals/harmonization-vs-claude/
└── 2026-05-12_run-01/
    ├── README.md                    # run metadata
    ├── assignments.json             # per-question A/B → system mapping
    ├── q01/
    │   ├── question.md
    │   ├── atlas_response.md        # raw (kept for audit)
    │   ├── claude_response.md       # raw
    │   ├── response_a.md            # anonymized, per assignment
    │   ├── response_b.md            # anonymized
    │   └── judge.json
    ├── q02/ ... q10/
    └── scorecard.md                 # aggregated results
```

### `README.md` template (one per run)

```markdown
# Eval Run: YYYY-MM-DD run-NN

- **Run date:** YYYY-MM-DD
- **Operator:** <name>
- **Atlas git SHA:** <git rev-parse HEAD>
- **Atlas environment:** prod | local
- **System A endpoint:** <URL>
- **System B model:** <e.g., claude-opus-4-7 on claude.ai>
- **System B attachments:** <4 PDF filenames>
- **Judge model:** <e.g., claude-opus-4-7 via claude.ai, fresh conversation per question>
- **Question set version:** v1 (from HARMONIZATION-VS-CLAUDE-EVAL.md)
- **Notes:** <anything weird that happened — failed uploads, retries, etc.>
```

### `scorecard.md` template (one per run, filled in after all 10 judgings)

```markdown
# Scorecard — <run id>

## Per-question results

| Q  | Category         | Atlas pos | Winner    | Atlas score (C/Cit/U/S) | Claude score (C/Cit/U/S) | Rationale (1 line) |
|----|------------------|-----------|-----------|-------------------------|--------------------------|--------------------|
| 1  | Single-doc fuzzy | A         | tie       | 3/2/3/NA                | 3/2/3/NA                 | Both summarize well |
| 2  | Single-doc fuzzy | B         | claude    | ...                     | ...                      | ...                |
| 3  | Longitudinal     | A         | atlas     | ...                     | ...                      | ...                |
| 4  | Longitudinal     | ...       | ...       | ...                     | ...                      | ...                |
| 5  | Vision-wins      | ...       | ...       | ...                     | ...                      | ...                |
| 6  | Cross-source     | ...       | ...       | ...                     | ...                      | ...                |
| 7  | Provenance       | ...       | ...       | ...                     | ...                      | ...                |
| 8  | Provenance       | ...       | ...       | ...                     | ...                      | ...                |
| 9  | Cohort           | ...       | ...       | ...                     | ...                      | ...                |
| 10 | Cohort           | ...       | ...       | ...                     | ...                      | ...                |

(Atlas pos = whether Atlas was Response A or Response B per the blind assignment.)

## Aggregate

| Category         | Atlas wins | Claude wins | Ties | Atlas avg total (out of 12) | Claude avg total |
|------------------|-----------:|------------:|-----:|----------------------------:|-----------------:|
| Single-doc fuzzy | 0          | 1           | 1    | ...                         | ...              |
| Longitudinal     | ...        | ...         | ...  | ...                         | ...              |
| Vision-wins      | ...        | ...         | ...  | ...                         | ...              |
| Cross-source     | ...        | ...         | ...  | ...                         | ...              |
| Provenance       | ...        | ...         | ...  | ...                         | ...              |
| Cohort           | ...        | ...         | ...  | ...                         | ...              |
| **Total**        | **N**      | **N**       | **N**| ...                         | ...              |

## Interpretation

Three-sentence read of the result. Specifically address:
  - Did Atlas win on Longitudinal / Vision-wins / Provenance / Cohort?
    (the four categories where the wedge should manifest)
  - Did Atlas lose on Single-doc fuzzy? (acceptable if ties; concerning if losses)
  - Any surprising patterns?

## Follow-ups

- Pipeline issues observed: <e.g., "Caspian failed to cite for Q7 — file a bug">
- Question-set issues observed: <e.g., "Q5 was ambiguous; tighten wording for v2">
- Next eval candidates: <e.g., "re-run after Move AE ships LOINC bridge v2">
```

---

## Aggregation rules

- **Score totals:** sum the four dimensions per response. Treat `"NA"` synthesis as worth 0 in the total but flag it (so a 3/3/3/NA scores 9, not "9-with-asterisk-treated-as-12"). Synthesis NA is only valid on single-doc-fuzzy questions; if the judge marks it NA on a longitudinal/cohort question, that's a judge failure and the question should be re-judged.
- **Category wins:** count per category. A win on a longitudinal question is worth the same as a win on a single-doc question — we do NOT pre-weight categories. The category breakdown is the analysis tool.
- **The pass condition for the wedge:** Atlas must win (or strongly outscore) Claude on **at least 3 of the 4 wedge categories** (Longitudinal, Vision-wins, Provenance, Cohort) AND must not lose any single-doc-fuzzy question by more than 1 point on aggregate score. If either condition fails, the pipeline isn't yet earning its keep on these inputs and the demo framing needs revision.

---

## Known caveats and threats to validity

This is a small eval. Be honest about its limits.

1. **N=1 patient.** All ten questions are about Blake's records. A different patient's records might surface different strengths and weaknesses. We accept this for v1 because (a) this is the realistic Phase 1 demo dataset and (b) we already have ground truth and provenance set up for `blake-real`. Future iterations should add a second patient (e.g., from the Synthea demo collection — Move S) to test generalization.
2. **Judge model is also Claude.** Using Claude to judge two Claude responses risks self-preference bias. The blind A/B assignment + fresh-conversation-per-question protocol mitigates but doesn't eliminate it. If a result is suspicious, re-judge with GPT-4 or Gemini as a sanity check.
3. **System B (Claude.ai) is a moving target.** The vanilla baseline gets stronger as Anthropic ships better PDF handling, longer context, tool use, etc. A win today may not be a win in six months. Each run records the System B model version in `README.md` so we can track drift.
4. **The "anonymize tool-call traces" step requires care.** Caspian responses are likely to be structurally different (more citations, tool calls, structured tables) from Claude.ai responses (more prose, fewer citations). The judge cannot be perfectly blinded to *style*. We accept this — the question is not "can the judge guess which is which" but "given the style differences, does the judge still prefer the substance of Response X for the right reasons." Read the rationale field carefully.
5. **Question framing matters.** All ten questions are phrased in natural language. A more structured question set ("output a CSV") would systematically advantage System A. The natural-language framing is the realistic clinical scenario and is intentional.
6. **Caspian determinism.** Caspian's agent loop is non-deterministic at temperature > 0. The same question may produce different responses across runs. We accept this for v1; if it matters, run each System A question 3× and pick the median-quality response (subjective, document the choice).

---

## First-run checklist

Use this on the day you actually run the eval. Tick boxes as you go.

- [ ] Atlas is reachable (`/caspian` loads, `blake-real` workspace is selected, source rail shows 5 sources)
- [ ] Claude.ai conversation is open with all 4 PDFs attached and verified readable (ask "What documents do you have access to?" first)
- [ ] Run directory created under `data/evals/harmonization-vs-claude/`
- [ ] `assignments.json` written with randomized A/B per question
- [ ] Q01 — Atlas response captured → Claude response captured → anonymized → judged → saved
- [ ] Q02 → Q10 (same pattern)
- [ ] `scorecard.md` filled in
- [ ] Anything weird logged in the run's `README.md`
- [ ] Notable wins/losses cross-linked into `PIPELINE-LOG.md` so the experiment journal stays the source of truth

---

## What changes when this doc changes

- **Question set is amended** → save the new set as v2 in a new dated section here; do NOT edit v1 in place. Old runs reference v1; new runs reference v2.
- **A new harmonization capability ships** that would change expected results → no change to this doc, just run a fresh eval against the same v1 questions and compare scorecards.
- **The Claude.ai baseline gains a capability** (e.g., MCP, native medical knowledge) → no change to the protocol; the System B `README.md` field records what was available at run time. Score drift across runs is itself the signal.
- **An eval surfaces a pipeline regression** → file in `PIPELINE-LOG.md`, link the eval run, fix, re-run.

---

## Cross-references

| For depth on... | Read |
|---|---|
| Why this test exists (the original "is harmonization worth it" review) | Conversation log 2026-05-12 |
| PDF processor architecture decisions | [PDF-PROCESSOR.md](./PDF-PROCESSOR.md) |
| Pipeline experiment journal | [PIPELINE-LOG.md](./PIPELINE-LOG.md) |
| Harmonization layer worked example (HDL) | [HARMONIZATION-WORKED-EXAMPLE.md](./HARMONIZATION-WORKED-EXAMPLE.md) |
| Harmonization layer implementation | `lib/harmonize/` |
| `blake-real` workspace definition | [`api/core/harmonize_service.py`](../../../api/core/harmonize_service.py) (`_COLLECTIONS["blake-real"]`) |
| Caspian agent runtime | [`api/core/provider_assistant_agent_sdk.py`](../../../api/core/provider_assistant_agent_sdk.py) |
