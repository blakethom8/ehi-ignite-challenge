"""Auth/session API models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


AuthMode = Literal["anonymous", "demo", "authenticated"]
AuthRole = Literal["consumer", "clinician", "attending", "coordinator", "admin"]


class AuthUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: AuthRole = "clinician"


class DemoPatientMetadata(BaseModel):
    care_setting: str = ""
    clinical_focus: str = ""
    complexity: str = ""
    tags: list[str] = Field(default_factory=list)


class DemoPatientOption(BaseModel):
    id: str
    name: str
    description: str = ""
    short_journey: str = ""
    metadata: DemoPatientMetadata = Field(default_factory=DemoPatientMetadata)


class AuthSessionResponse(BaseModel):
    mode: AuthMode
    user: AuthUserResponse | None = None
    active_patient_id: str | None = None
    active_patient_name: str | None = None
    active_demo_patient: DemoPatientOption | None = None
    expires_at: datetime | None = None
    available_demo_patients: list[DemoPatientOption] = Field(default_factory=list)


class AuthLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)


class AuthSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name is required.")
        return normalized


class AuthDemoRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=120)


class AuthPatientSelectionRequest(BaseModel):
    patient_id: str | None = Field(default=None, max_length=120)


# ---------------------------------------------------------------------------
# Self-service account models
# ---------------------------------------------------------------------------


class AccountUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name is required.")
        return normalized


class AccountPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


# ---------------------------------------------------------------------------
# Admin response models
# ---------------------------------------------------------------------------


AuthAccountStatus = Literal["active", "disabled"]


class AdminUserSummary(BaseModel):
    id: str
    email: str
    display_name: str
    role: AuthRole
    status: AuthAccountStatus
    created_at: datetime
    last_login_at: datetime | None = None
    workspace_count: int = 0
    storage_bytes: int = 0


class AdminWorkspaceSummary(BaseModel):
    id: str
    display_name: str
    created_at: datetime
    updated_at: datetime
    source_count: int = 0
    storage_bytes: int = 0


class AdminUserDetail(AdminUserSummary):
    workspaces: list[AdminWorkspaceSummary] = Field(default_factory=list)


class AdminAuditEvent(BaseModel):
    id: str
    created_at: datetime
    session_id: str | None = None
    user_id: str | None = None
    mode: str | None = None
    patient_id: str | None = None
    event_type: str
    payload: dict[str, object] = Field(default_factory=dict)


class AdminAuditListResponse(BaseModel):
    events: list[AdminAuditEvent] = Field(default_factory=list)


class AdminSessionSummary(BaseModel):
    id: str
    mode: str
    user_id: str | None = None
    user_email: str | None = None
    user_display_name: str | None = None
    active_patient_id: str | None = None
    active_patient_name: str | None = None
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None = None


class AdminPatchUserRequest(BaseModel):
    role: AuthRole | None = None
    status: AuthAccountStatus | None = None


class AdminActionResponse(BaseModel):
    ok: bool = True
