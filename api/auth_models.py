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
