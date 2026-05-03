# Skill Demo — Hands-On Walkthrough

**Mode:** different from the other lanes. Not study notes — a step-by-step *demo guide* Blake can run himself. The goal is to get fingerprints on Josh's skill so the data-lane abstractions stop feeling abstract.

## Which skill?

Blake said he downloaded a Claude skill. The two candidates are:

- **`request-my-ehi`** — generates the PDF packet to *request* an EHI Export from a provider. Outputs: cover letter + filled ROI form + vendor-specific appendix → merged PDF, optionally faxed. Standalone, no FHIR data needed to demo.
- **`health-record-assistant`** (from `health-skillz`, downloaded as a local-skill ZIP from the redaction-studio web UI) — analyzes a connected patient's records via SMART on FHIR. Requires having connected to a portal and exported a local-skill bundle first.

**Blake — please confirm which one.** This guide will adapt to whichever you ran. (Best guess: `request-my-ehi`, since it's standalone and the easier first demo. Confirm or correct.)

## Provisional demo arc (will firm up once skill is identified)

| #  | Step                                                                          | Output                                       | Status     |
| -- | ----------------------------------------------------------------------------- | -------------------------------------------- | ---------- |
| S01 | Inventory the downloaded bundle: list every file, identify roles              | annotated `tree` of the skill dir            | ⏳ next    |
| S02 | Read `SKILL.md` cold: trace the user-flow Claude is instructed to execute     | annotated walkthrough of the markdown        | ⏳ pending |
| S03 | Install the skill into Claude Code; confirm Claude sees it                    | screenshot / transcript of skill discovery   | ⏳ pending |
| S04 | First run — let Claude execute the happy path with sample inputs              | conversation transcript + generated PDF      | ⏳ pending |
| S05 | Inspect every file Claude wrote during the run                                | per-file annotation                          | ⏳ pending |
| S06 | Adapt: change one thing (e.g., add a vendor, change appendix language)        | diff vs. original                            | ⏳ pending |
| S07 | Compare what you observed against data-lane notes D01–D02 to anchor the model | "the abstract D01 vendor schema is *this file* you just opened" cross-reference | ⏳ pending |

## Practical guardrails for the demo lane

- **Don't fax or upload anything real.** Use a fake fax number, fake provider, fake address. The skill has scripts that hit real services (`send-fax.ts`, `submit-signature`). Keep the demo dry.
- **Snapshot inputs and outputs.** Save the patient JSON, the generated PDF, any intermediate files. These become Blake's reference samples.
- **Capture the conversation transcript.** Even the "boring" chat turns where Claude asks for confirmation are part of how the skill behaves.

## How this lane interacts with the data lane

The demo lane is a **concretizer** for the data lane. Whenever the data lane introduces an abstract shape — vendor metadata schema, FHIR snapshot, redaction profile — the demo lane is where Blake can `cat` the actual file on his machine and see it.

Cross-references go both directions:
- Data lane note "D02 — Vendor metadata" → links to demo-lane `S05` where Blake inspects `vendors.json`.
- Demo-lane S05 → links back up to D02 for the why.

## To start

Reply with:
- **which skill you downloaded** (`request-my-ehi`, `health-record-assistant`, or another)
- **where it lives on disk** (`~/.claude/skills/...`, a `skill.zip`, an unzipped folder, etc.)

Then we'll run S01.
