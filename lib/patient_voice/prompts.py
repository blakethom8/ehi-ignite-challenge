"""Prompt templates for the patient-voice classifier.

Each prompt has a version string baked into its constant name. The
classifier persists ``prompt_version`` in the cache key so a bump
auto-invalidates stale classifications.
"""

from __future__ import annotations


TURN_CLASSIFIER_PROMPT_VERSION = "v1"


TURN_CLASSIFIER_PROMPT_V1 = """\
You are extracting structured FHIR-shaped facts from one turn of a patient's own words.

Patient turn (verbatim):
\"\"\"
{turn_content}
\"\"\"

Linked gap card: {gap_title} — {gap_prompt}
Today's date (ISO): {today_iso}

Classify into exactly one of:
  med_statement  — patient is describing a medication they take, started, or stopped
  condition      — patient is describing a diagnosis or disease they have / had
  goal           — patient is describing what they want from their care
  generic        — anything else (preferences, symptoms, worries, social context)

If med_statement, also extract:
  status         — one of "active" or "stopped"
  drug_text      — the medication name as the patient said it (lowercase, no dose)
  effective_end_iso  — ONLY if status="stopped"; compute from phrases like
                       "3 weeks ago" / "last month" relative to today_iso.
                       Format: YYYY-MM-DD. Omit if patient didn't say when.

If condition, also extract:
  condition_text — the condition as the patient said it (free text; no codes)
  onset_period   — [start_iso, end_iso] in YYYY-MM-DD form, conservative.
                   For "summer 2022" use ["2022-06-01", "2022-08-31"].
                   For "last year" use the full calendar year ending before today.

If goal, also extract:
  goal_text      — the goal in the patient's words (one sentence)

NEVER extract codes (RxNorm, ICD, SNOMED, LOINC). The harmonizer attaches
those later. NEVER paraphrase or interpret beyond what the patient said.

Return JSON ONLY, no prose, in exactly this shape (omit irrelevant keys):
{{
  "kind": "med_statement|condition|goal|generic",
  "status": "active|stopped",
  "drug_text": "...",
  "effective_end_iso": "YYYY-MM-DD",
  "condition_text": "...",
  "onset_period": ["YYYY-MM-DD", "YYYY-MM-DD"],
  "goal_text": "..."
}}
"""


def render_turn_classifier_prompt(
    *,
    turn_content: str,
    gap_title: str,
    gap_prompt: str,
    today_iso: str,
) -> str:
    """Render the classifier prompt with concrete inputs."""
    return TURN_CLASSIFIER_PROMPT_V1.format(
        turn_content=turn_content.strip(),
        gap_title=gap_title or "(none)",
        gap_prompt=gap_prompt or "",
        today_iso=today_iso,
    )
