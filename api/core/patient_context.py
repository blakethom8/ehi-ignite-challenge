"""Patient Context guided intake service.

This module owns the patient-facing context layer. It does not mutate FHIR,
Atlas gold, or provider-facing assistant state. Patient answers are persisted as
separate patient-reported facts and exported as portable Markdown.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from api.core.loader import load_patient, patient_display_name, path_from_patient_id
from api.models import (
    PatientContextExportResponse,
    PatientContextExportStatus,
    PatientContextFact,
    PatientContextGapCard,
    PatientContextSessionResponse,
    PatientContextTurn,
    PatientContextTurnResponse,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STORE_ROOT = Path(os.getenv("PATIENT_CONTEXT_STORE_PATH", REPO_ROOT / "data" / "patient-context"))
AGENT_PROFILE_DIR = Path(__file__).parent.parent / "agents" / "patient-context"
REPO_ENV_PATH = REPO_ROOT / ".env"
PRIVATE_CEDARS_DEFAULT = (
    REPO_ROOT / "ehi-atlas" / "corpus" / "_sources" / "blake-cedars" / "raw" / "health-records.json"
)
PRIVATE_CEDARS_CHIEF = (
    Path.home()
    / "Chief"
    / "20-projects"
    / "ehi-ignite-challenge"
    / "research"
    / "josh-mandel"
    / "health-records.json"
)


class PatientContextConfigurationError(RuntimeError):
    """Raised when the real guided LLM is not configured."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe[:120] or "patient"


def _session_dir(patient_id: str, session_id: str) -> Path:
    return STORE_ROOT / _safe_id(patient_id) / _safe_id(session_id)


def _session_path(session_id: str, patient_id: str | None = None) -> Path:
    if patient_id:
        return _session_dir(patient_id, session_id) / "session.json"
    matches = list(STORE_ROOT.glob(f"*/{_safe_id(session_id)}/session.json"))
    if not matches:
        raise FileNotFoundError(f"Patient Context session not found: {session_id}")
    return matches[0]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_api_key() -> str:
    env_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if env_key and "YOUR_KEY_HERE" not in env_key:
        return env_key
    if REPO_ENV_PATH.exists():
        file_key = (dotenv_values(REPO_ENV_PATH).get("ANTHROPIC_API_KEY") or "").strip()
        if file_key and "YOUR_KEY_HERE" not in file_key:
            return file_key
    return ""


def _private_cedars_path() -> Path | None:
    configured = os.getenv("PATIENT_CONTEXT_BLAKE_CEDARS_PATH")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend([PRIVATE_CEDARS_DEFAULT, PRIVATE_CEDARS_CHIEF])
    for path in candidates:
        if path.exists():
            return path
    return None


def private_cedars_available() -> bool:
    return _private_cedars_path() is not None


def _load_agent_profile() -> str:
    chunks: list[str] = []
    for name in ("CLAUDE.md", "RULES.md"):
        path = AGENT_PROFILE_DIR / name
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def _patient_label(patient_id: str, source_mode: str) -> str:
    if source_mode == "private_blake_cedars" and private_cedars_available():
        return "Blake Cedars-Sinai record"
    path = path_from_patient_id(patient_id)
    if path:
        return patient_display_name(path)
    return patient_id


def _record_summary(patient_id: str, source_mode: str) -> dict[str, Any]:
    if source_mode == "private_blake_cedars":
        path = _private_cedars_path()
        if path:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and isinstance(raw.get("providers"), list):
                    counts: dict[str, int] = {}
                    for provider in raw.get("providers", []):
                        fhir = provider.get("fhir", {}) if isinstance(provider, dict) else {}
                        if isinstance(fhir, dict):
                            for key, value in fhir.items():
                                if isinstance(value, list):
                                    counts[key] = counts.get(key, 0) + len(value)
                    return {
                        "mode": "private",
                        "path": str(path),
                        "counts": counts,
                        "source_notes": ["Private Cedars-Sinai Health Skillz pull detected locally."],
                    }
            except (OSError, json.JSONDecodeError):
                pass
        return {"mode": "private_missing", "counts": {}, "source_notes": ["Private Cedars source not found locally."]}

    loaded = load_patient(patient_id)
    if loaded is None:
        return {"mode": "unknown", "counts": {}, "source_notes": ["Patient bundle could not be loaded."]}
    record, stats = loaded
    return {
        "mode": "synthea",
        "counts": {
            "conditions": len(record.conditions),
            "medications": len(record.medications),
            "encounters": len(record.encounters),
            "observations": len(record.observations),
            "diagnostic_reports": len(record.diagnostic_reports),
            "allergies": len(record.allergies),
            "claims": len(record.claims),
        },
        "active_conditions": [c.code.label() for c in record.conditions if c.is_active][:8],
        "active_medications": [m.display for m in record.medications if m.status == "active"][:8],
        "parse_warning_count": len(record.parse_warnings),
        "years_of_history": getattr(stats, "years_of_history", 0),
        "source_notes": ["Synthetic FHIR chart loaded from the local Synthea corpus."],
    }


def build_gap_cards(patient_id: str, source_mode: str) -> list[PatientContextGapCard]:
    summary = _record_summary(patient_id, source_mode)
    counts = summary.get("counts", {})
    active_meds = summary.get("active_medications", [])
    active_conditions = summary.get("active_conditions", [])

    cards = [
        PatientContextGapCard(
            id="sources-missing",
            category="missing_sources",
            title="Confirm other places that may hold records",
            prompt="Which other portals, clinics, labs, pharmacies, insurers, or PDFs should be included but are not in this record yet?",
            why_it_matters="Missing sources are the most common reason a chart summary leaves out important context.",
            priority=5,
            evidence=summary.get("source_notes", []),
        ),
        PatientContextGapCard(
            id="medication-reality",
            category="medication_reality",
            title="Check what medications are actually being taken",
            prompt="Are the listed active medications accurate, and are there any medications, supplements, or recent stops missing from the chart?",
            why_it_matters="Medication lists often lag reality, and medication status affects safety reviews.",
            priority=5,
            evidence=[f"Active medication in chart: {m}" for m in active_meds[:5]]
            or [f"{counts.get('medications', 0)} medication records found."],
        ),
        PatientContextGapCard(
            id="timeline-gaps",
            category="timeline_gap",
            title="Fill care timeline gaps",
            prompt="Were there important visits, hospitalizations, procedures, or changes in health that are not represented in the chart timeline?",
            why_it_matters="A patient story often has transitions that structured records do not explain.",
            priority=4,
            evidence=[
                f"{counts.get('encounters', 0)} encounters and {counts.get('diagnostic_reports', 0)} diagnostic reports found."
            ],
        ),
        PatientContextGapCard(
            id="uncertain-facts",
            category="uncertain_fact",
            title="Clarify uncertain or stale chart facts",
            prompt="Are any listed problems, allergies, lab results, or diagnoses outdated, wrong, or missing important explanation?",
            why_it_matters="The context bundle should separate chart evidence from patient corrections or clarifications.",
            priority=4,
            evidence=[f"Active condition in chart: {c}" for c in active_conditions[:5]]
            or [f"{counts.get('conditions', 0)} condition records found."],
        ),
        PatientContextGapCard(
            id="patient-goals",
            category="qualitative_context",
            title="Capture goals, symptoms, and preferences",
            prompt="What do you most want your clinician to understand about your symptoms, goals, worries, daily function, or care preferences?",
            why_it_matters="This qualitative context rarely appears in exported EHI, but it changes how clinicians interpret the record.",
            priority=3,
            evidence=[],
        ),
    ]
    return cards


def _source_posture(source_mode: str) -> str:
    if source_mode == "private_blake_cedars":
        if private_cedars_available():
            return "Private Cedars proof-of-life mode. Real personal data stays local and generated outputs are gitignored."
        return "Private Cedars mode requested, but no local private source was found. Synthetic fallback is available."
    if source_mode == "synthetic":
        return "Synthetic showcase mode. Safe for public demos and screenshots."
    return "Selected-patient mode. Patient Context is separate from verified chart facts."


def _dump_session(session: PatientContextSessionResponse) -> dict[str, Any]:
    return session.model_dump(mode="json")


def _load_session(session_id: str) -> PatientContextSessionResponse:
    payload = _read_json(_session_path(session_id))
    return PatientContextSessionResponse.model_validate(payload)


def create_session(patient_id: str, source_mode: str) -> PatientContextSessionResponse:
    session_id = uuid.uuid4().hex[:12]
    gap_cards = build_gap_cards(patient_id, source_mode)
    first = gap_cards[0]
    first_turn = PatientContextTurn(
        id=uuid.uuid4().hex,
        role="assistant",
        content=(
            "I’ll help build a Patient Context packet that stays separate from the verified chart. "
            f"First: {first.prompt}"
        ),
        created_at=_now(),
        linked_gap_id=first.id,
    )
    session = PatientContextSessionResponse(
        session_id=session_id,
        patient_id=patient_id,
        patient_label=_patient_label(patient_id, source_mode),
        source_mode=source_mode,  # type: ignore[arg-type]
        source_posture=_source_posture(source_mode),
        gap_cards=gap_cards,
        turns=[first_turn],
        facts=[],
        export_status=PatientContextExportStatus(),
    )
    root = _session_dir(patient_id, session_id)
    _write_json(root / "session.json", _dump_session(session))
    _write_json(root / "gap_cards.json", {"gap_cards": [g.model_dump(mode="json") for g in gap_cards]})
    (root / "answers.jsonl").touch()
    return session


def get_session(session_id: str) -> PatientContextSessionResponse:
    return _load_session(session_id)


def _gap_lookup(session: PatientContextSessionResponse) -> dict[str, PatientContextGapCard]:
    return {gap.id: gap for gap in session.gap_cards}


def _next_open_gap(session: PatientContextSessionResponse) -> PatientContextGapCard | None:
    for gap in sorted(session.gap_cards, key=lambda g: (-g.priority, g.id)):
        if gap.status == "open":
            return gap
    return None


def _build_llm_prompt(session: PatientContextSessionResponse, patient_message: str, selected_gap_id: str | None) -> str:
    gaps = "\n".join(
        f"- {gap.id} [{gap.status}] {gap.title}: {gap.prompt}" for gap in session.gap_cards
    )
    facts = "\n".join(f"- {fact.summary}" for fact in session.facts[-8:]) or "(none yet)"
    history = "\n".join(f"{turn.role}: {turn.content}" for turn in session.turns[-8:])
    return f"""Patient label: {session.patient_label}
Source posture: {session.source_posture}
Selected gap id: {selected_gap_id or "(none)"}

Gap checklist:
{gaps}

Captured Patient Context facts:
{facts}

Recent conversation:
{history}

Patient just said:
{patient_message}

Return JSON only with:
{{
  "assistant_message": "your next response to the patient",
  "captured_summary": "neutral one-sentence summary of the patient's answer",
  "confidence": "high|medium|low",
  "next_gap_id": "gap id to continue with or null"
}}
"""


def _parse_llm_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
    return {}


def _call_patient_context_llm(session: PatientContextSessionResponse, message: str, selected_gap_id: str | None) -> dict[str, Any]:
    api_key = _resolve_api_key()
    if not api_key:
        raise PatientContextConfigurationError(
            "ANTHROPIC_API_KEY is required for Patient Context guided turns. Set it in .env or the environment."
        )

    import anthropic

    model = os.getenv("PATIENT_CONTEXT_MODEL", os.getenv("PROVIDER_ASSISTANT_MODEL", "claude-sonnet-4-5"))
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=900,
        system=_load_agent_profile(),
        messages=[{"role": "user", "content": _build_llm_prompt(session, message, selected_gap_id)}],
    )
    text = response.content[0].text if response.content else ""
    parsed = _parse_llm_json(text)
    if not parsed.get("assistant_message"):
        parsed["assistant_message"] = text.strip() or "Thank you. What else should your care team understand?"
    return parsed


def add_turn(session_id: str, message: str, selected_gap_id: str | None) -> PatientContextTurnResponse:
    session = _load_session(session_id)
    gap_by_id = _gap_lookup(session)
    next_open_gap = _next_open_gap(session)
    linked_gap_id = selected_gap_id if selected_gap_id in gap_by_id else (next_open_gap.id if next_open_gap else None)

    patient_turn = PatientContextTurn(
        id=uuid.uuid4().hex,
        role="patient",
        content=message.strip(),
        created_at=_now(),
        linked_gap_id=linked_gap_id,
    )

    llm_payload = _call_patient_context_llm(session, message.strip(), linked_gap_id)
    summary = str(llm_payload.get("captured_summary") or message.strip()).strip()
    confidence = str(llm_payload.get("confidence") or "medium").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    fact = PatientContextFact(
        id=uuid.uuid4().hex,
        linked_gap_id=linked_gap_id,
        statement=message.strip(),
        summary=summary[:800],
        confidence=confidence,  # type: ignore[arg-type]
        created_at=_now(),
    )

    next_gap_id = llm_payload.get("next_gap_id")
    if not isinstance(next_gap_id, str) or next_gap_id not in gap_by_id:
        next_gap = _next_open_gap(session)
        next_gap_id = next_gap.id if next_gap else None

    assistant_turn = PatientContextTurn(
        id=uuid.uuid4().hex,
        role="assistant",
        content=str(llm_payload.get("assistant_message", "")).strip(),
        created_at=_now(),
        linked_gap_id=next_gap_id,
    )

    updated_gaps: list[PatientContextGapCard] = []
    for gap in session.gap_cards:
        if gap.id == linked_gap_id:
            gap.status = "answered"
        updated_gaps.append(gap)

    session.turns.extend([patient_turn, assistant_turn])
    session.facts.append(fact)
    session.gap_cards = updated_gaps

    root = _session_path(session_id).parent
    with (root / "answers.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(fact.model_dump_json() + "\n")
    _write_json(root / "session.json", _dump_session(session))
    _write_json(root / "gap_cards.json", {"gap_cards": [g.model_dump(mode="json") for g in session.gap_cards]})

    payload = _dump_session(session)
    payload["assistant_message"] = assistant_turn.model_dump(mode="json")
    return PatientContextTurnResponse.model_validate(payload)


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None captured yet."


def export_markdown(session_id: str) -> PatientContextExportResponse:
    session = _load_session(session_id)
    root = _session_path(session_id).parent
    generated_at = _now()
    facts = session.facts
    open_gaps = [gap for gap in session.gap_cards if gap.status == "open"]
    answered_gaps = [gap for gap in session.gap_cards if gap.status == "answered"]

    patient_context = f"""# Patient Context

Patient: {session.patient_label}
Generated: {generated_at.isoformat()}
Source posture: {session.source_posture}

## Patient-Reported Context
{_markdown_list([f.summary for f in facts])}

## Original Patient Wording
{_markdown_list([f"{f.created_at.date()}: {f.statement}" for f in facts])}

## Boundary
These notes are patient-reported context. They are not verified clinical chart facts and should not be merged into the medical record without review.
"""

    questions = f"""# Questions For Care Team

## Still Open
{_markdown_list([f"{gap.title}: {gap.prompt}" for gap in open_gaps])}

## Answered During Intake
{_markdown_list([gap.title for gap in answered_gaps])}
"""

    sources = f"""# Sources

Patient: {session.patient_label}

## Source Posture
{session.source_posture}

## Gap Checklist
{_markdown_list([f"[{gap.status}] {gap.title} — {gap.why_it_matters}" for gap in session.gap_cards])}
"""

    agent = f"""# Agent Instructions

You are reading a Patient Context bundle produced by EHI Atlas.

- Treat `PATIENT_CONTEXT.md` as patient-reported context, not verified chart truth.
- Preserve source boundaries between chart evidence and patient answers.
- Use `QUESTIONS.md` to guide follow-up with the patient or care team.
- Use `SOURCES.md` to understand missing sources and provenance posture.
- Do not diagnose, prescribe, or infer facts that are not stated.
"""

    files = {
        "PATIENT_CONTEXT.md": patient_context,
        "QUESTIONS.md": questions,
        "SOURCES.md": sources,
        "AGENT.md": agent,
    }
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")

    export_status = PatientContextExportStatus(
        generated=True,
        files=sorted(files.keys()),
        generated_at=generated_at,
    )
    session.export_status = export_status
    _write_json(root / "session.json", _dump_session(session))

    return PatientContextExportResponse(
        session_id=session_id,
        generated_at=generated_at,
        files=sorted(files.keys()),
        preview=patient_context[:2000],
    )
