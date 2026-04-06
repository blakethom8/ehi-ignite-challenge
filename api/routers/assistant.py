"""
/api/assistant — provider-facing conversational chart assistant.
"""

from fastapi import APIRouter, HTTPException

from api.core.provider_assistant_service import answer_provider_question
from api.models import (
    ProviderAssistantRequest,
    ProviderAssistantResponse,
    ProviderAssistantCitation,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ProviderAssistantResponse)
def provider_chat(payload: ProviderAssistantRequest) -> ProviderAssistantResponse:
    """
    Chat endpoint for provider Q&A over a single patient's chart.

    Behavior is intentionally direct and concise, with explicit pushback when
    evidence is weak or conflicting.
    """
    if not payload.patient_id:
        raise HTTPException(status_code=422, detail="patient_id is required")
    if not payload.question.strip():
        raise HTTPException(status_code=422, detail="question is required")

    try:
        result = answer_provider_question(
            patient_id=payload.patient_id,
            question=payload.question,
            history=[turn.model_dump() for turn in payload.history],
            stance=payload.stance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ProviderAssistantResponse(
        patient_id=payload.patient_id,
        answer=result.answer,
        confidence=result.confidence,
        stance=payload.stance,
        engine=result.engine,
        citations=[
            ProviderAssistantCitation(
                source_type=c.source_type,
                resource_id=c.resource_id,
                label=c.label,
                detail=c.detail,
                event_date=c.event_date,
            )
            for c in result.citations
        ],
        follow_ups=result.follow_ups,
    )
