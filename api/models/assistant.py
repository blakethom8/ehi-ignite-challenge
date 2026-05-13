"""
Provider Assistant chat models — request/response shapes for the
`/assistant` endpoints (deterministic + Anthropic Agent SDK modes), plus
the trace/tool-call detail records that flow back for transparency.

Consumed by `api/routers/assistant.py` and `api/core/workflow_runner.py`
(which reuses `ProviderAssistantCitation` for workflow-run citations).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Provider Assistant (chat)
# ---------------------------------------------------------------------------

class ProviderAssistantTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content is required")
        return stripped


class ProviderAssistantCitation(BaseModel):
    source_type: str      # "MedicationRequest" | "Condition" | ...
    resource_id: str
    label: str
    detail: str
    event_date: datetime | None = None


class ProviderAssistantContextPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=1500)


class ProviderAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=4000)
    history: list[ProviderAssistantTurn] = Field(default_factory=list, max_length=12)
    context_packages: list[ProviderAssistantContextPackage] = Field(default_factory=list, max_length=8)
    stance: Literal["opinionated", "balanced"] = "opinionated"
    # Per-request overrides (optional — falls back to env config)
    model: Literal[
        "claude-haiku-4-5",
        "claude-sonnet-4-5",
        "claude-sonnet-4-6",
        "claude-opus-4-5",
    ] | None = None
    mode: Literal[
        "deterministic",
        "context",
        "context_single_turn",
        "single_turn",
        "anthropic",
        "anthropic_agent",
        "agent_sdk",
        "anthropic_sdk",
        "cursor",
        "cursor_sdk",
    ] | None = None
    max_tokens: int | None = Field(default=None, ge=128, le=4000)
    # Cursor sidecar model id (e.g. composer-2). Validated against CURSOR_SIDECAR_MODEL_ALLOWLIST when set.
    cursor_model: str | None = Field(default=None, max_length=120)

    @field_validator("cursor_model", mode="before")
    @classmethod
    def _normalize_cursor_model(cls, value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    @field_validator("question")
    @classmethod
    def _question_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question is required")
        return stripped


class ToolCallDetail(BaseModel):
    tool_name: str                 # "run_sql" | "query_chart_evidence" | "get_patient_snapshot"
    input_summary: str             # human-readable input (e.g. the SQL query)
    output_summary: str            # human-readable output (e.g. "12 rows returned")
    duration_ms: float | None = None
    error: str | None = None


class TraceDetail(BaseModel):
    trace_id: str
    duration_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float | None = None
    tool_calls: list[ToolCallDetail] = []
    system_prompt_preview: str = ""   # system prompt the agent received
    retrieved_facts: list[str] = []   # actual fact texts used in the response
    # Transparency metadata
    model_used: str | None = None
    mode_used: str | None = None
    max_tokens_used: int | None = None
    context_token_estimate: int | None = None
    history_turns_sent: int | None = None


class ProviderAssistantResponse(BaseModel):
    patient_id: str
    answer: str
    confidence: str                # "high" | "medium" | "low"
    stance: str
    engine: str = "deterministic"  # "deterministic" | "anthropic-agent-sdk" | "deterministic-fallback"
    citations: list[ProviderAssistantCitation]
    follow_ups: list[str]
    trace: TraceDetail | None = None  # tool calls + context transparency
    # Relative workspace paths the agent wrote during this turn (slice 3+4).
    # Frontend renders them as chips under the message.
    files_created: list[str] = Field(default_factory=list)
