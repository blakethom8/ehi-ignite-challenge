# Self-Modifying Workspace — Design Addendum

> **Status:** Design addendum to `SKILL-AGENT-WORKSPACE.md`. Captures the
> "save → mutate" loop the parent doc only sketches, before runtime
> primitives are committed to in code.
>
> **Author:** Blake (with Claude)
> **Date:** 2026-05-05

---

## 1. The question

The parent doc defines the workspace as a per-run filesystem the agent
edits and the clinician watches. It mentions forks, per-patient pinning,
and marketplace forks, but it does not pin down what happens when the
clinician *saves* a run. That's the missing piece.

The strawman from the build session:

> "When a user is doing a drug clinical trial search maybe with their
>  clinical data or their FHIR data, when they save that, they can
>  self-modify themselves potentially or self-modify this workspace
>  that they have to do things with it."

This addendum makes that concrete so commit 2 can lock the runtime
contract without retrofitting later.

## 2. What "self-modifying" means here — and what it does not

We deliberately use a constrained definition. Three modifications are
**in scope**; two are **out of scope**.

### In scope

1. **Per-run editing.** The clinician annotates or corrects the agent's
   output post-run. Edits live in the run dir and are part of the
   audit trail. The agent does not read these on future runs of *this*
   run; it's a closed run after `finish()`.

2. **Patient memory layer.** Edits the clinician promotes from a run
   into a per-patient memory directory the agent reads at *every*
   future skill run for that patient. This is the cross-run, cross-skill
   persistence layer.

3. **Forking.** A run can be cloned with edited brief inputs to produce
   a fresh run. The new run's transcript starts clean but inherits the
   patient memory layer.

### Out of scope (deferred or forbidden)

4. **Skill self-modification by the runtime agent — forbidden.** The
   parent doc §6.2 is explicit: the runtime agent "should not rewrite
   application code, silently change FHIR schemas, bypass validation
   gates." Editing `SKILL.md` is a builder-agent operation, not a
   runtime-agent one. Clinicians can fork a skill in the marketplace;
   that's a separate code path with review.

5. **Mid-run inline comments — deferred to a later commit.** The parent
   doc Act 2 mentions "wrong turns get corrected via inline-comment-style
   feedback." That requires UI for inserting comments mid-stream and
   runtime support for re-injecting them into the next agent turn. Worth
   building, but not in commit 2 — defer until we've used the basic
   loop.

## 3. The three save destinations

When the clinician saves a finished run, they pick a destination. The
runtime exposes all three from day one; the UI can introduce them
progressively.

```
┌─────────────────────────────────────────────────────────────────┐
│  Save destination                                                │
├─────────────────────────────────────────────────────────────────┤
│  (A) Annotate this run only                                      │
│      ↓                                                           │
│      /cases/{pid}/{skill}/{run}/clinician_edits.md              │
│                                                                  │
│      Default. Edit lives in the run dir, joins the transcript.  │
│      Closed run; future runs do not read this file.             │
│                                                                  │
│  (B) Pin to patient                                              │
│      ↓                                                           │
│      /cases/{pid}/_memory/pinned.md                              │
│                                                                  │
│      Promote selected facts/notes from this run to a per-patient│
│      memory file. Every future skill run for this patient mounts│
│      this file in the agent's session-start context.            │
│                                                                  │
│  (C) Save as patient context package                             │
│      ↓                                                           │
│      /cases/{pid}/_memory/context_packages/{name}.md             │
│                                                                  │
│      Materialize a richer reusable bundle that future skills can│
│      reference by name in their `context_packages:` frontmatter.│
│      e.g., "patient-trial-preferences", "patient-payer-history".│
└─────────────────────────────────────────────────────────────────┘
```

**Why three, not one.** A clinician's edit can mean different things:
"this is wrong, fix the record" (A), "this is a fact about *this
patient* I want every future agent to know" (B), or "this is reusable
context that other skills will benefit from" (C). Collapsing them into
one save button makes the audit trail ambiguous and the cross-skill
learning weaker. Three buttons map to three real destinations.

## 4. Patient memory layer — the substrate

A new directory per patient, sibling to per-skill case dirs:

```
/cases/{patient_id}/
  _memory/
    pinned.md                 # destination (B)
    context_packages/         # destination (C)
      patient-trial-prefs.md
      patient-payer-history.md
    notes.jsonl               # event log: each save w/ source run + actor
  trial-matching/
    {run_id_1}/...
    {run_id_2}/...
  med-access/
    {run_id_3}/...
```

Properties:

1. **Append-only event log.** Every save writes a `notes.jsonl` event
   with timestamp, actor, source run id, and destination. The current
   `pinned.md` and context packages are derived from the event log on
   read; the runtime can replay history if anything corrupts.
2. **Citation-preserving.** A pinned fact carries its citation chip
   from the originating run. The next agent that reads the memory layer
   sees the citation and can resolve it back to the source.
3. **Mounted at session start.** When *any* skill starts a run for this
   patient, the runner reads `_memory/pinned.md` and any context
   packages declared in the skill's frontmatter, and prepends them to
   the agent's system prompt as `# Patient memory` and
   `# Context: {name}` sections.
4. **Read-only to the agent.** The agent cannot write to `_memory/`
   directly. Promotion happens via clinician action through the runtime
   API, never through agent tool calls. This preserves the audit
   contract (the agent never silently modifies a patient's longitudinal
   record).

## 5. Run lifecycle with save destinations

```
created
  → running (agent + tool calls + workspace.write/cite/escalate)
  → escalated (paused for clinician)
  → running (resumed)
  → validated (output.json passes schema)
  → finished (workspace locked)
  ─── clinician picks save destination ───
  → saved:run        (clinician_edits.md written; default)
  → saved:patient    (pinned.md updated; future runs see it)
  → saved:package    (new context package materialized)
  → archived         (old runs hidden but retained)
```

A run can transition through multiple save destinations — the clinician
can save annotations to the run, *then* later promote a subset to the
patient memory layer.

## 6. What this means for commit 2 (the runtime)

Concretely, commit 2 must include:

1. `Workspace` class with `write/cite/escalate` plus `finalize()`.
2. Save-destination API: `save_to_run(edits)`, `pin_to_patient(facts)`,
   `save_as_context_package(name, content)`.
3. `PatientMemory` class with read/write through the event log.
4. Runner mounts the patient memory in the agent's session-start
   context.
5. REST endpoints for the three save actions.

What commit 2 does **not** need to include:
- Mid-run inline comments (§2 item 5).
- Skill marketplace forks (handled outside the runtime).
- A diff-aware UI for editing the workspace (that's commit 3).

## 7. Flexibility we preserve

The save-destination set is **open at the type level** — the underlying
runtime models save destinations as a registered enum, not a hardcoded
three. Adding a fourth (e.g., "save to org library") later doesn't
require changing the workspace contract; it requires registering a new
destination handler. This is the flexibility hook the build session
flagged.

## 8. What we explicitly do not promise yet

- **Time-bounded retention.** We don't yet decide how long
  `_memory/notes.jsonl` events are kept, when context packages are
  garbage-collected, or whether the patient (vs the clinician) can
  prune the layer. These are real questions; they belong in a separate
  governance doc when we have a real PHI deployment.
- **Cross-patient memory.** Out of scope. There is no shared memory
  layer across patients in this design. Cross-patient learning is a
  marketplace-skill upgrade (the *skill* improves), not a runtime
  feature.
- **Patient-as-actor.** In the patient-audience variant, the patient
  may also save runs. Today the actor on the save is captured in
  `notes.jsonl` and the runtime treats clinician/patient saves
  identically. Whether that's the right policy is a Phase-2 question.

## 9. Open question for next decision

When the clinician promotes a fact from a run to the patient memory
layer, **does the source run's `clinician_edits.md` get updated to
reflect the promotion?** Two answers:

- **Yes (recommended):** the run carries an "I promoted this fact to
  patient memory" event, so anyone replaying the audit trail sees the
  full context.
- **No:** the run is closed at finalize; promotion lives only in
  `_memory/notes.jsonl`.

I lean yes — preserves audit completeness — but it's a small extra
write and a small contract addition. **Will go with yes in commit 2
unless told otherwise.**
