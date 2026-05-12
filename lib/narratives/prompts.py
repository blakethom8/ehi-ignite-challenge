"""Prompt templates for the per-episode narrative generator.

Versioned constants so the tracing span ``narrative.generate`` captures
``prompt_version`` and any bump auto-invalidates downstream comparisons.
"""

from __future__ import annotations


EPISODE_NARRATIVE_PROMPT_VERSION = "v1"


EPISODE_NARRATIVE_PROMPT_V1 = """\
You are a clinical writer. Produce a one-page narrative for ONE episode of
a patient's care. Cite resources by ID. Do not invent facts. Quote
patient turns verbatim where they shed light on the episode.

Episode
-------
type:      {episode_type}
period:    {period_start} → {period_end}
diagnoses: {diagnosis_refs}

Resources you may cite (ID list — DO NOT cite anything else)
-----------------------------------------------------------
Conditions:        {condition_ids}
Medications (merged): {medication_ids}
Observations (merged): {observation_ids}
Encounters:        {encounter_ids}
Patient turns:     {patient_turn_ids}

Harmonized facts in this episode window
---------------------------------------
{fact_table}

Patient's own words (verbatim, with turn ids)
---------------------------------------------
{patient_turns_block}

Output requirements
-------------------
Return JSON ONLY, no prose, no markdown fence. Exactly this shape:

{{
  "summary":         "<plain text, ≤200 chars>",
  "timeline":        "<markdown bullet list; each bullet should cite at least one [[ref:Resource/id]]>",
  "key_facts":       "<markdown paragraphs with [[ref:Resource/id]] markers>",
  "patient_words":   "<verbatim quoted turns with [[ref:turn-<id>]] markers; empty string if no relevant turns>",
  "open_questions":  "<markdown bullet list of what you couldn't reconcile; empty string if none>"
}}

Rules
-----
- Use ONLY the resource IDs listed above. Any other ID is a hallucination.
- Use the EXACT syntax `[[ref:Resource/id]]` for citations. Example:
  `Lisinopril started 2019-08 [[ref:MedicationRequest/merged-rxnorm-29046]].`
- For patient turns use `[[ref:turn-<id>]]` (NOT a FHIR resource type).
- Do not paraphrase patient quotes — copy verbatim from "Patient's own words" above.
- The summary section MUST stand on its own as a single readable sentence.
"""


def render_episode_narrative_prompt(
    *,
    episode: dict,
    condition_ids: list[str],
    medication_ids: list[str],
    observation_ids: list[str],
    encounter_ids: list[str],
    patient_turn_ids: list[str],
    fact_table: str,
    patient_turns_block: str,
) -> str:
    """Render the per-episode narrative prompt."""
    period = episode.get("period") or {}
    period_start = period.get("start", "?")
    period_end = period.get("end") or "ongoing"

    type_arr = episode.get("type") or []
    type_text = ""
    if type_arr and isinstance(type_arr, list):
        first = type_arr[0]
        if isinstance(first, dict):
            type_text = first.get("text") or (
                ((first.get("coding") or [{}])[0]).get("display", "")
            )
    if not type_text:
        type_text = "(unspecified)"

    diagnosis_refs = ", ".join(
        (d.get("condition") or {}).get("reference", "")
        for d in (episode.get("diagnosis") or [])
        if isinstance(d, dict)
    ) or "(none)"

    return EPISODE_NARRATIVE_PROMPT_V1.format(
        episode_type=type_text,
        period_start=period_start,
        period_end=period_end,
        diagnosis_refs=diagnosis_refs,
        condition_ids=", ".join(condition_ids) or "(none)",
        medication_ids=", ".join(medication_ids) or "(none)",
        observation_ids=", ".join(observation_ids) or "(none)",
        encounter_ids=", ".join(encounter_ids) or "(none)",
        patient_turn_ids=", ".join(patient_turn_ids) or "(none)",
        fact_table=fact_table or "(none)",
        patient_turns_block=patient_turns_block or "(none)",
    )
