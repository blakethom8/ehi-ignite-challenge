"""Typed application configuration.

All FastAPI-side environment variable reads route through this module via
:func:`get_settings`. The cache holds the most recent instance, but
:func:`get_settings` re-instantiates ``Settings`` whenever the relevant slice
of ``os.environ`` has changed since the last call — so tests can mutate
env vars with ``monkeypatch.setenv`` and the next read picks up the new
values without explicit ``cache_clear()``. Call ``get_settings.cache_clear()``
to drop the cached instance unconditionally (used by the conftest autouse
hook to keep tests from leaking state).

Missing required secrets fail fast at the first ``get_settings`` call:
- ``ANTHROPIC_API_KEY`` is required when ``ENVIRONMENT in {"prod","production"}``.
- Signing-key secrets (``EHI_SESSION_SECRET``, ``GUEST_HARMONIZATION_SECRET``,
  ``ATLAS_SIGNING_KEY``) are validated lazily by the modules that load them
  (``api.core.auth``, ``api.core.guest_harmonization``, ``api.trust.keys``)
  because they each have a dev-mode disk-based fallback. Settings exposes
  them as optional strings.

The lib/ tree continues to read environment variables directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from typing import Annotated, Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_ROOT = _REPO_ROOT / "data"


def _csv_or_list(raw: Any) -> Any:
    """Accept CSV strings for ``list[str]`` env vars; pass lists through.

    pydantic-settings parses ``list[str]`` env vars as JSON by default, but
    our deploy config uses plain CSV (e.g. ``ALLOWED_HOSTS=a,b,c``). This
    coerces the CSV form before validation.
    """
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    return raw


class Settings(BaseSettings):
    """Single typed source of truth for ``api/`` environment variables.

    Field names are lower-cased; the matching env var is the upper-cased
    form (``anthropic_api_key`` ← ``ANTHROPIC_API_KEY``). ``extra="ignore"``
    so unrelated env vars never break boot.
    """

    @model_validator(mode="before")
    @classmethod
    def _empty_string_is_unset(cls, data: Any) -> Any:
        # Docker compose / shell exports pass declared-but-unset vars as `FOO=`
        # (empty string). Pydantic v2 won't coerce "" into typed numeric or
        # boolean fields, so treat empty strings as missing and let the field
        # default kick in.
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data

    # ── Core ────────────────────────────────────────────────────────────────
    environment: str = "development"

    # ── Hosts / CORS ────────────────────────────────────────────────────────
    # ``NoDecode`` disables pydantic-settings' default JSON parsing so the CSV
    # form ``ALLOWED_HOSTS=a,b,c`` round-trips through ``_split_csv`` below.
    allowed_hosts: Annotated[list[str], NoDecode] = [
        "ehi.healthcaredataai.com",
        "localhost",
        "127.0.0.1",
        "testserver",
    ]
    cors_allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://ehi.healthcaredataai.com",
    ]

    # ── Anthropic ───────────────────────────────────────────────────────────
    anthropic_api_key: str | None = None

    # ── Provider assistant ──────────────────────────────────────────────────
    provider_assistant_mode: str = "deterministic"
    provider_assistant_model: str = "claude-sonnet-4-5"
    provider_assistant_max_response_tokens: int = 2000
    provider_assistant_max_turns: int = 6
    provider_assistant_max_budget_usd: float | None = None
    provider_assistant_allow_client_overrides: bool | None = None
    provider_assistant_fallback_to_deterministic: bool = True
    provider_assistant_enable_web_search: bool = False
    provider_assistant_enable_web_fetch: bool = False

    # ── Cursor sidecar ──────────────────────────────────────────────────────
    cursor_sidecar_url: str | None = None
    cursor_sidecar_model: str = "composer-2"
    cursor_sidecar_model_allowlist: str | None = None
    cursor_sidecar_timeout_s: float = 120.0
    cursor_internal_tool_secret: str | None = None

    # ── Patient demo / catalog limits ───────────────────────────────────────
    ehi_demo_patient_limit: int = 20

    # ── Auth / sessions ─────────────────────────────────────────────────────
    ehi_auth_db_path: Path = _DATA_ROOT / "auth.db"
    ehi_session_secret_path: Path = _DATA_ROOT / "atlas-session.key"
    ehi_session_secret: str | None = None
    ehi_auth_session_idle_hours: int = 12
    ehi_auth_session_max_days: int = 7
    ehi_auth_bootstrap_email: str | None = None
    ehi_auth_bootstrap_password: str | None = None
    ehi_auth_bootstrap_name: str | None = None
    ehi_auth_bootstrap_role: str | None = None

    # ── Plugin trust / signing ──────────────────────────────────────────────
    atlas_signing_key: str | None = None

    # ── Audit + traces API auth ─────────────────────────────────────────────
    audit_api_token: str | None = None
    traces_api_enabled: bool = False
    traces_api_token: str | None = None

    # ── LLM tracing (observability) ─────────────────────────────────────────
    tracing_enabled: bool = False
    traces_db_path: Path = Path("data/traces.db")
    tracing_sample_rate: float = 1.0
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── Aggregation upload + profile stores ─────────────────────────────────
    aggregation_upload_store_path: Path = _DATA_ROOT / "aggregation-uploads"
    aggregation_profile_store_path: Path = _DATA_ROOT / "aggregation-profiles"
    aggregation_max_upload_bytes: int = 25 * 1024 * 1024
    ccda_lab_max_upload_bytes: int = 25 * 1024 * 1024

    # ── Published charts ────────────────────────────────────────────────────
    published_chart_store_path: Path = _DATA_ROOT / "published-charts"

    # ── Harmonization runs ──────────────────────────────────────────────────
    harmonization_run_store_path: Path = _DATA_ROOT / "harmonization-runs"

    # ── Guest harmonization (temporary, cookie-scoped) ──────────────────────
    guest_harmonization_root: Path = _DATA_ROOT / "guest-harmonization"
    guest_harmonization_secret_path: Path = _DATA_ROOT / "atlas-guest-harmonization.key"
    guest_harmonization_secret: str | None = None
    guest_harmonization_ttl_hours: int = 24
    guest_harmonization_max_file_bytes: int = 10 * 1024 * 1024
    guest_harmonization_max_pdf_pages: int = 60
    guest_harmonization_max_pages_per_pdf: int = 40
    guest_harmonization_global_daily_page_budget: int = 5000
    guest_harmonization_pdf_pipeline: str = "multipass-fhir"
    guest_harmonization_event_cap: int = 200

    # ── Patient context ─────────────────────────────────────────────────────
    patient_context_store_path: Path = _DATA_ROOT / "patient-context"
    patient_context_model: str | None = None
    patient_context_blake_cedars_path: Path | None = None

    # ── FHIR converter (C-CDA) ──────────────────────────────────────────────
    fhir_converter_url: str | None = None
    fhir_converter_bin: str | None = None
    fhir_converter_template_dir: str | None = None
    fhir_converter_bearer_token: str | None = None
    fhir_converter_api_version: str = "2024-05-01-preview"
    fhir_converter_timeout_seconds: float = 30.0
    fhir_converter_required: bool = False
    fhir_converter_root_template: str | None = None

    # ── Skills runtime ──────────────────────────────────────────────────────
    skills_cases_path: Path = _DATA_ROOT / "cases"
    skills_worker_concurrency: int = 2
    skills_run_mode: str = ""
    skills_agent_model: str = "claude-sonnet-4-6"
    skills_agent_max_turns: int = 30
    skills_agent_max_tokens: int = 4096

    # ── SOF (SQL-on-FHIR) materializer ──────────────────────────────────────
    sof_auto_materialize: bool = True
    sof_patient_limit: int | None = None
    sof_db_path: Path | None = None
    sof_fhir_dir: Path | None = None

    # ── Workspace events ────────────────────────────────────────────────────
    events_db_path: Path = _DATA_ROOT / "events.db"
    events_redaction_preset: str = "events-strict"
    events_retention_days: int = 90

    # ── Plugin demo fixtures ────────────────────────────────────────────────
    plugin_anchor_use_fixtures: bool = False

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Normalized accessors ───────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("allowed_hosts", "cors_allowed_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: Any) -> Any:
        return _csv_or_list(v)

    @field_validator(
        "ehi_auth_session_idle_hours",
        "ehi_auth_session_max_days",
        "guest_harmonization_ttl_hours",
        "guest_harmonization_max_pdf_pages",
        "guest_harmonization_max_pages_per_pdf",
        mode="after",
    )
    @classmethod
    def _at_least_one(cls, v: int) -> int:
        # Mirror existing ``max(1, int(...))`` clamps from auth / guest modules.
        return max(1, v)

    @field_validator("guest_harmonization_max_file_bytes", mode="after")
    @classmethod
    def _at_least_1kib(cls, v: int) -> int:
        return max(1024, v)

    @field_validator("guest_harmonization_event_cap", mode="after")
    @classmethod
    def _at_least_20(cls, v: int) -> int:
        return max(20, v)

    @field_validator(
        "guest_harmonization_global_daily_page_budget",
        "events_retention_days",
        mode="after",
    )
    @classmethod
    def _nonnegative(cls, v: int) -> int:
        return max(0, v)

    @field_validator("ehi_demo_patient_limit", mode="after")
    @classmethod
    def _at_least_one_patient(cls, v: int) -> int:
        return max(1, v)

    @field_validator("provider_assistant_max_turns", mode="after")
    @classmethod
    def _at_least_two_turns(cls, v: int) -> int:
        return max(2, v)

    @field_validator("tracing_sample_rate", mode="after")
    @classmethod
    def _clamp_sample_rate(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @model_validator(mode="after")
    def _check_required_secrets(self) -> "Settings":
        # In production, ANTHROPIC_API_KEY has no safe fallback — fail at boot.
        # Signing-key secrets are checked by their respective loaders (each has
        # a dev-mode disk fallback that's unsafe to rely on in production).
        if self.is_production and not (self.anthropic_api_key or "").strip():
            raise ValueError(
                "ANTHROPIC_API_KEY is required when ENVIRONMENT=production."
            )
        return self


_cached_settings: Settings | None = None
_cached_env_snapshot: tuple[tuple[str, str | None], ...] | None = None
_TRACKED_ENV_VARS: tuple[str, ...] = tuple(
    name.upper() for name in Settings.model_fields.keys()
)


def _env_snapshot() -> tuple[tuple[str, str | None], ...]:
    return tuple((name, os.environ.get(name)) for name in _TRACKED_ENV_VARS)


def get_settings() -> Settings:
    """Return the cached ``Settings`` instance, refreshing on env changes.

    The cache is invalidated automatically when any tracked env var has
    changed since the last call (so ``monkeypatch.setenv`` Just Works in
    tests). Call :func:`get_settings.cache_clear` to drop the instance
    unconditionally — the conftest autouse hook does this between tests
    to avoid cross-test state leakage.
    """
    global _cached_settings, _cached_env_snapshot
    snapshot = _env_snapshot()
    if _cached_settings is None or snapshot != _cached_env_snapshot:
        _cached_settings = Settings()  # type: ignore[call-arg]
        _cached_env_snapshot = snapshot
    return _cached_settings


def _cache_clear() -> None:
    global _cached_settings, _cached_env_snapshot
    _cached_settings = None
    _cached_env_snapshot = None


# Provide the same ``cache_clear`` surface as ``functools.lru_cache`` so test
# fixtures can call ``get_settings.cache_clear()`` like they would on any
# other cached function.
get_settings.cache_clear = _cache_clear  # type: ignore[attr-defined]
