"""
Demo-mode seed files for the Caspian workspace.

The frontend shows a ``demo-seed/`` folder in the FilesPane only when the
session is demo AND the capability ``show_caspian_seed_files`` is on. The
files in that folder are *virtual* — they are never written to disk and have
no on-disk presence. ``list_workspace()`` merges in the descriptors at the
top of the tree; ``read_workspace_file()`` renders the content on demand.

Three files are exposed:

- ``demo-seed/welcome.md`` — an orientation page explaining the sample
  workspace policy (read-only, ephemeral, run a workflow to see output).
- ``demo-seed/sample-pre-op-briefing.md`` — a pre-baked pre-op clearance
  briefing rendered in the same markdown shape as a real workflow output
  (banner, fact rail, sections, citation tokens). This is the showpiece:
  reviewers see what a real artifact looks like without spending an LLM
  call. Keep the format aligned with ``_artifact_to_markdown`` in
  ``api/core/workflow_runner.py`` so the rendering looks the same.
- ``demo-seed/sample-user-instructions.md`` — a short, illustrative example
  of the user-instructions override format. Marked as a sample at the top
  so reviewers don't mistake it for an editable file.

The descriptor shape matches the file-tree node format the FilesPane consumes
(see ``api/core/caspian_workspace._file``). All entries report
``kind="demo-seed"`` and ``editable=False``.
"""

from __future__ import annotations

from typing import Final


# ---------------------------------------------------------------------------
# Public path constants
# ---------------------------------------------------------------------------

DEMO_SEED_PREFIX: Final[str] = "demo-seed/"

WELCOME_PATH: Final[str] = "demo-seed/welcome.md"
SAMPLE_BRIEFING_PATH: Final[str] = "demo-seed/sample-pre-op-briefing.md"
SAMPLE_INSTRUCTIONS_PATH: Final[str] = "demo-seed/sample-user-instructions.md"


# ---------------------------------------------------------------------------
# Content (kept inline so the module is self-contained and deterministic)
# ---------------------------------------------------------------------------

_WELCOME_MD = """# Welcome to the sample Caspian workspace

This is a **read-only sample** workspace. It exists so you can see how Caspian
organises a patient working directory without signing in. A few things to
know before you explore:

- **Sample data only.** The patient record, the workflow output, and the
  example user-instructions in this folder are illustrative — not a real
  chart.
- **Read-only.** You cannot edit, save, or upload files in demo mode. The
  Edit button is hidden and the agent's `write_file` tool is disabled.
- **No persistence.** Anything you do in demo lives in the browser tab.
  Refresh and it's gone. Sign in to get a workspace that survives the
  session.
- **The showpiece is `sample-pre-op-briefing.md`.** Open it to see the
  shape of a real Caspian workflow output — banner, fact rail, sections,
  and citation chips that link back to the underlying resources.

## Try the workflows

Use the workflow buttons in the top toolbar to run **Pre-op review**,
**Medication safety**, or **Longitudinal synthesis**. Each one generates a
fresh artifact that lands in the `workflow-runs/` folder. In demo mode the
file isn't kept after this session — sign in if you want to save copies into
your own `notes/`.

## What you can do here

- Read every file in this folder.
- Run workflows and inspect the artifact + trace.
- Ask Caspian questions in the chat pane. The agent has read access to the
  chart context but cannot write to the workspace.

Sign in (top-right) to unlock writing, durable notes, and the full agent
toolset.
"""


_SAMPLE_BRIEFING_MD = """# Pre-op Clearance Briefing — Sample

> **REVIEW · Hold elective surgery pending anticoagulation plan.** Two
> active anticoagulants and a recent INR spike push this case out of the
> "clear" lane. The combination flagged in MedicationRequest:abc-123 and
> Observation:def-456 below is the load-bearing finding.

| Risk tier | Surgical class | Last clearance | Most recent INR |
| --- | --- | --- | --- |
| Moderate-high | Inpatient (elective) | 2025-11-12 | 3.4 (Observation:def-456) |

## Active medications driving the hold

| Medication | Drug class | Status | Source |
| --- | --- | --- | --- |
| Warfarin 5 mg daily | Anticoagulant (Vitamin K antagonist) | Active | MedicationRequest:abc-123 |
| Apixaban 5 mg BID | Anticoagulant (Factor Xa inhibitor) | Active — overlapping | MedicationRequest:abc-789 |
| Aspirin 81 mg daily | Antiplatelet | Active | MedicationRequest:abc-202 |

The overlapping warfarin + apixaban prescriptions are the most likely
explanation for the recent INR drift. The chart doesn't show a documented
bridging plan; that's the first thing to confirm with the prescribing
service.

## Recent labs

- **INR 3.4** on 2025-12-01 (Observation:def-456) — up from 2.1 four weeks
  earlier (Observation:def-455). Therapeutic range for this patient is
  2.0-3.0.
- **Hemoglobin 11.8 g/dL** on 2025-12-01 (Observation:def-501) — stable.
- **Platelets 188 × 10^9/L** on 2025-12-01 (Observation:def-510) — stable.
- **Creatinine 1.1 mg/dL** on 2025-12-01 (Observation:def-520) — eGFR 64.

## Recommended actions

1. Confirm with cardiology / hematology whether the apixaban was a
   transition (in which case the warfarin should have been stopped) or a
   true duplicate.
2. Hold elective procedure until INR is in the 1.5 - 2.0 pre-op window
   and the anticoagulant plan is consolidated to a single agent.
3. Re-check INR within 48 hours of any dosing change
   (Procedure:lab-recheck-001).
4. If the apixaban is genuinely needed for stroke prevention, document a
   bridging plan with low-molecular-weight heparin per institutional
   protocol.

## Anesthesia notes

No contraindications to general anesthesia in the chart. The patient's most
recent A1c (5.9%) and BP readings (avg 128/78) are within preferred
pre-op bands. The single open item is the anticoagulation conflict above —
once that's resolved, this becomes a routine clearance.

---

_Sample artifact. In a real run the citation chips above link back to the
resources in the patient's chart; here they're shown verbatim so you can
see the shape of the output._
"""


_SAMPLE_INSTRUCTIONS_MD = """# Sample user instructions

> **Sample only.** Sign in to author your own instructions. Anything you
> write here in demo is ignored — this file is read-only.

Use `user-instructions.md` to teach Caspian how to talk about *this*
patient's chart. The content is appended to the system prompt on every
chat turn for this workspace, so keep it short and durable.

## Examples

- Always prefer SI units when summarising labs.
- Don't abbreviate drug names — write "Apixaban" instead of "Apx" so the
  briefing reads cleanly out loud.
- Treat NSAIDs as contraindicated for this patient (history of GI bleed,
  see Condition:cond-204).
- Refer to the patient as "they" in summaries.
- When the chart mentions "the procedure", default to the most recent
  scheduled one (Procedure:proc-309) unless the question says otherwise.

## What goes here vs. notes/

| Use `user-instructions.md` for | Use `notes/` for |
| --- | --- |
| Durable preferences that apply to every turn | Per-incident notes, drafts, ad-hoc rationale |
| Stylistic overrides ("write SI units", "no abbreviations") | A medication-review summary you want to save |
| Long-lived clinical context ("treat NSAIDs as contraindicated") | Output of a workflow run that you want to keep |

Sign in to get an editable `user-instructions.md` of your own.
"""


_FILES: Final[dict[str, str]] = {
    WELCOME_PATH: _WELCOME_MD,
    SAMPLE_BRIEFING_PATH: _SAMPLE_BRIEFING_MD,
    SAMPLE_INSTRUCTIONS_PATH: _SAMPLE_INSTRUCTIONS_MD,
}


# Display order in the FilesPane.
_ORDERED_PATHS: Final[tuple[str, ...]] = (
    WELCOME_PATH,
    SAMPLE_BRIEFING_PATH,
    SAMPLE_INSTRUCTIONS_PATH,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_demo_seed_path(rel_path: str) -> bool:
    """True if ``rel_path`` refers to one of the virtual demo-seed files."""
    return rel_path in _FILES


def render_demo_seed_file(rel_path: str) -> str | None:
    """Return the rendered content for a demo-seed path, or None if unknown."""
    return _FILES.get(rel_path)


def list_demo_seed_files() -> list[dict]:
    """Return tree-node descriptors for the three virtual demo-seed files.

    Shape matches ``api/core/caspian_workspace._file``. All entries are
    ``kind="demo-seed"`` and ``editable=False`` — demo seeds are always
    read-only regardless of session.
    """
    descriptors: list[dict] = []
    for path in _ORDERED_PATHS:
        name = path.rsplit("/", 1)[-1]
        ext = name.rsplit(".", 1)[1].lower() if "." in name else ""
        descriptors.append(
            {
                "type": "file",
                "name": name,
                "id": path,
                "ext": ext,
                "icon": "FileText",
                "dirty": False,
                "editable": False,
                "kind": "demo-seed",
            }
        )
    return descriptors


__all__ = [
    "DEMO_SEED_PREFIX",
    "WELCOME_PATH",
    "SAMPLE_BRIEFING_PATH",
    "SAMPLE_INSTRUCTIONS_PATH",
    "is_demo_seed_path",
    "render_demo_seed_file",
    "list_demo_seed_files",
]
