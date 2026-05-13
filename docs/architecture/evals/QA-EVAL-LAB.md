# Q&A Eval Lab

## Purpose

Q&A Eval Lab is the downstream clinical usefulness workbench for the internal PDF-to-FHIR pipeline lab.

Pipeline Lab answers: "What FHIR Bundle did this parser produce?"

Q&A Eval Lab answers: "Can an answer harness use that Bundle to answer the clinical question correctly, with evidence, without hallucinating, and with acceptable time/tool cost?"

The north star is the clinical review product goal: can a clinician get the right 5 facts in 30 seconds?

## Current Shape

The module lives as a first-class Internal Tools page at:

`/analysis/qa-eval-lab`

It reads evaluation artifacts from:

`data/pipeline-evals/runs/<eval-run-id>/`

Each evaluation run is tied back to a saved extraction run under:

- `data/pdf-lab/runs/<run-id>/`
- `data/local-model-lab/runs/<run-id>/`

The current page is question-centered:

- questions are listed on the left
- the selected question shows the expected answer and actual response side by side
- comparison metrics show correctness, completeness, citation quality, hallucination avoidance, abstention quality, and clinical usefulness
- cited evidence and missing/unsupported facts are visible for review
- harness metadata shows runner, answer model, grader, context builder, latency, and tool-call count

Pipeline Lab still shows a compact downstream QA score, but detailed review belongs in Q&A Eval Lab.

## Evaluation Model

The backend abstraction is intentionally modular:

- `ContextBuilder`: converts a pipeline Bundle into question-answering context
- `ClinicalQuestionRunner`: answers a clinical question from that context
- `AnswerGrader`: grades the answer against expected behavior and available evidence
- `EvaluationSuite`: stores reusable clinical QA test cases
- `EvaluationResult`: stores summary scores and per-question outputs

The first implemented suite is deterministic and small on purpose: a renal impairment smoke test. It proves the artifact and UI workflow before we spend time wiring expensive model graders or agentic harnesses.

## Artifact Contract

Each eval run should remain inspectable on disk:

```text
data/pipeline-evals/runs/<eval-run-id>/
  suite.json
  manifest.json
  pipeline_run_ref.json
  context.json
  questions/<question-id>/prompt.txt
  questions/<question-id>/answer.json
  questions/<question-id>/grade.json
  questions/<question-id>/evidence.json
  summary.json
```

Agent and harness outputs should normalize into `answer.json` with fields like:

- `answer`
- `abstained`
- `citations`
- `claims`
- `tool_call_count`
- `tool_calls`
- `latency_ms`
- `cost_usd`
- `answer_model`
- `prompt_template_id`
- `response_format_version`

This lets us compare deterministic runners, hosted LLMs, local models, coding-agent harnesses, and multi-tool agentic systems in one scoreboard.

## Future Vision

The module should evolve from a results viewer into a test development workbench.

Near-term:

- add more clinical test cases: perioperative medication risks, abnormal labs, active diabetes evidence, missing-data handoff risk
- support multiple suites and suite filtering
- add a "run suite" control for selected pipeline run + answer harness + grader
- expose prompt/template version and context builder version more clearly
- show answer latency and tool-call trace as first-class comparison columns

Medium-term:

- add model-graded evaluation using Opus or another high-accuracy grader
- compare multiple answers for the same question side by side
- rank harnesses by clinical usefulness, not just extraction volume
- flag unsupported claims and citations that do not exist in the Bundle
- support abstention scoring when the extracted record lacks required facts

Long-term:

- use this as the acceptance harness for new parser and agentic QA work
- treat Q&A Eval Lab as the bridge between extraction engineering and clinical product readiness
- build reviewer workflows for adjudicating grader decisions
- create stable benchmark suites that can be run across coding platforms, agent runtimes, local models, and hosted models

The success metric is not "more resources extracted." It is whether a downstream clinical system can produce the right answer, cite the right facts, and know when not to answer.
