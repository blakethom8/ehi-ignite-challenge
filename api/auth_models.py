"""Auth/session API models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AuthMode = Literal["anonymous", "demo", "authenticated"]


class AuthUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: Literal["clinician", "attending", "coordinator", "admin"] = "clinician"


class DemoPatientOption(BaseModel):
    id: str
    name: str
    description: str = ""


class AuthSessionResponse(BaseModel):
    mode: AuthMode
    user: AuthUserResponse | None = None
    active_patient_id: str | None = None
    active_patient_name: str | None = None
    expires_at: datetime | None = None
    available_demo_patients: list[DemoPatientOption] = Field(default_factory=list)


class AuthLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)


class AuthDemoRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=120)


class AuthPatientSelectionRequest(BaseModel):
    patient_id: str | None = Field(default=None, max_length=120)
