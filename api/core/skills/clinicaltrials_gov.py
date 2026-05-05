"""ClinicalTrials.gov v2 API client (in-process).

The architecture doc puts shared data sources behind MCP servers (§6.4). For
Phase 1 we ship this as an in-process tool to keep the worker boundary
small; promotion to a standalone MCP server is a follow-up.

The public v2 JSON API requires no auth and supports the queries we need:
- `GET /studies?query.cond=...&filter.overallStatus=RECRUITING&pageSize=N`
- `GET /studies/{nctId}`

Docs: https://clinicaltrials.gov/data-api/api
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Iterable

import httpx


CTGOV_BASE_URL = "https://clinicaltrials.gov/api/v2"
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


# ── Public data shapes ──────────────────────────────────────────────────────


@dataclass
class TrialSummary:
    nct_id: str
    title: str
    status: str
    phases: tuple[str, ...]
    conditions: tuple[str, ...]
    sponsor: str | None
    minimum_age: str | None
    maximum_age: str | None
    sex: str | None
    healthy_volunteers: bool | None
    locations_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "nct_id": self.nct_id,
            "title": self.title,
            "status": self.status,
            "phases": list(self.phases),
            "conditions": list(self.conditions),
            "sponsor": self.sponsor,
            "minimum_age": self.minimum_age,
            "maximum_age": self.maximum_age,
            "sex": self.sex,
            "healthy_volunteers": self.healthy_volunteers,
            "locations_count": self.locations_count,
        }


@dataclass
class TrialRecord:
    nct_id: str
    title: str
    status: str
    phases: tuple[str, ...]
    conditions: tuple[str, ...]
    sponsor: str | None
    brief_summary: str
    detailed_description: str
    eligibility_criteria: str
    inclusion_lines: tuple[str, ...]
    exclusion_lines: tuple[str, ...]
    minimum_age: str | None
    maximum_age: str | None
    sex: str | None
    healthy_volunteers: bool | None
    locations: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    central_contacts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    last_update_submitted: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "nct_id": self.nct_id,
            "title": self.title,
            "status": self.status,
            "phases": list(self.phases),
            "conditions": list(self.conditions),
            "sponsor": self.sponsor,
            "brief_summary": self.brief_summary,
            "detailed_description": self.detailed_description,
            "eligibility_criteria": self.eligibility_criteria,
            "inclusion_lines": list(self.inclusion_lines),
            "exclusion_lines": list(self.exclusion_lines),
            "minimum_age": self.minimum_age,
            "maximum_age": self.maximum_age,
            "sex": self.sex,
            "healthy_volunteers": self.healthy_volunteers,
            "locations": list(self.locations),
            "central_contacts": list(self.central_contacts),
            "last_update_submitted": self.last_update_submitted,
        }


# ── HTTP transport seam (for testing) ───────────────────────────────────────


class CTGovTransport:
    """Wraps httpx.AsyncClient so tests can substitute a stub.

    The transport is *just* the HTTP boundary; parsing and shape conversion
    live in the search/get_record functions below.
    """

    def __init__(
        self,
        base_url: str = CTGOV_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        response = await self._client.get(url, params=_drop_none(params))
        response.raise_for_status()
        return response.json()


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


# ── Public functions ───────────────────────────────────────────────────────


async def search(
    *,
    condition: str,
    status: list[str] | None = None,
    age_band: dict[str, int] | None = None,
    sex: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    transport: CTGovTransport | None = None,
) -> list[TrialSummary]:
    """Search ClinicalTrials.gov for trials matching `condition`.

    `status` is one or more `RECRUITING`, `ENROLLING_BY_INVITATION`, etc.
    `age_band` is `{"min": int, "max": int}` (years).
    `sex` is `"MALE"` / `"FEMALE"` (omit if unknown).
    """
    if not condition.strip():
        raise ValueError("condition is required")
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    own_transport = transport is None
    transport = transport or CTGovTransport()
    try:
        params: dict[str, Any] = {
            "query.cond": condition.strip(),
            "pageSize": page_size,
            "format": "json",
        }
        if status:
            params["filter.overallStatus"] = ",".join(status)
        # The CT.gov v2 API does not support direct sex/age filters as query
        # params on /studies; we surface those constraints in the tool result
        # so the agent can pre-filter, and we filter client-side below as a
        # belt-and-braces.

        data = await transport.get_json("/studies", params)
    finally:
        if own_transport:
            await transport.aclose()

    studies = data.get("studies") or []
    summaries: list[TrialSummary] = []
    for study in studies:
        summary = _summary_from_study(study)
        if summary is None:
            continue
        if not _matches_sex(summary.sex, sex):
            continue
        if not _matches_age_band(summary.minimum_age, summary.maximum_age, age_band):
            continue
        summaries.append(summary)
    return summaries


async def get_record(
    nct_id: str,
    *,
    transport: CTGovTransport | None = None,
) -> TrialRecord:
    """Fetch full study record by NCT id and parse eligibility into lines."""
    nct_id = nct_id.strip().upper()
    if not nct_id.startswith("NCT") or len(nct_id) != 11:
        raise ValueError(f"invalid NCT id '{nct_id}'")

    own_transport = transport is None
    transport = transport or CTGovTransport()
    try:
        data = await transport.get_json(f"/studies/{nct_id}", {"format": "json"})
    finally:
        if own_transport:
            await transport.aclose()

    return _record_from_study(data)


# ── Parsing ─────────────────────────────────────────────────────────────────


def _summary_from_study(study: dict[str, Any]) -> TrialSummary | None:
    proto = study.get("protocolSection") or {}
    ident = proto.get("identificationModule") or {}
    nct = (ident.get("nctId") or "").strip()
    if not nct:
        return None
    title = (
        ident.get("officialTitle")
        or ident.get("briefTitle")
        or "(untitled)"
    ).strip()
    status_module = proto.get("statusModule") or {}
    design = proto.get("designModule") or {}
    conditions_module = proto.get("conditionsModule") or {}
    eligibility = proto.get("eligibilityModule") or {}
    sponsor_module = proto.get("sponsorCollaboratorsModule") or {}
    contacts_module = proto.get("contactsLocationsModule") or {}

    sponsor = (
        ((sponsor_module.get("leadSponsor") or {}).get("name") or "").strip() or None
    )
    locations = contacts_module.get("locations") or []

    return TrialSummary(
        nct_id=nct,
        title=title,
        status=(status_module.get("overallStatus") or "UNKNOWN").strip(),
        phases=tuple((design.get("phases") or [])),
        conditions=tuple((conditions_module.get("conditions") or [])),
        sponsor=sponsor,
        minimum_age=eligibility.get("minimumAge"),
        maximum_age=eligibility.get("maximumAge"),
        sex=eligibility.get("sex"),
        healthy_volunteers=eligibility.get("healthyVolunteers"),
        locations_count=len(locations),
    )


def _record_from_study(study: dict[str, Any]) -> TrialRecord:
    summary = _summary_from_study(study)
    if summary is None:
        raise ValueError("response missing protocolSection.identificationModule.nctId")

    proto = study.get("protocolSection") or {}
    description_module = proto.get("descriptionModule") or {}
    eligibility_module = proto.get("eligibilityModule") or {}
    contacts_module = proto.get("contactsLocationsModule") or {}
    status_module = proto.get("statusModule") or {}

    eligibility_text = (eligibility_module.get("eligibilityCriteria") or "").strip()
    inclusion, exclusion = _parse_eligibility(eligibility_text)

    return TrialRecord(
        nct_id=summary.nct_id,
        title=summary.title,
        status=summary.status,
        phases=summary.phases,
        conditions=summary.conditions,
        sponsor=summary.sponsor,
        brief_summary=(description_module.get("briefSummary") or "").strip(),
        detailed_description=(description_module.get("detailedDescription") or "").strip(),
        eligibility_criteria=eligibility_text,
        inclusion_lines=inclusion,
        exclusion_lines=exclusion,
        minimum_age=summary.minimum_age,
        maximum_age=summary.maximum_age,
        sex=summary.sex,
        healthy_volunteers=summary.healthy_volunteers,
        locations=tuple(contacts_module.get("locations") or ()),
        central_contacts=tuple(contacts_module.get("centralContacts") or ()),
        last_update_submitted=status_module.get("lastUpdateSubmitDate"),
    )


def _parse_eligibility(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split eligibility text into inclusion vs exclusion lines.

    The CT.gov format is informal markdown. We look for an "Inclusion" section
    header and an "Exclusion" section header; lines between them are
    inclusion, lines after exclusion are exclusion. Falls back to all-inclusion
    if no headers are present.
    """
    if not text.strip():
        return ((), ())

    lines = [ln.rstrip() for ln in text.splitlines()]
    inclusion: list[str] = []
    exclusion: list[str] = []
    bucket: list[str] = inclusion

    seen_inclusion_header = False
    for raw in lines:
        line = raw.strip(" -*•\t")
        if not line:
            continue
        lower = line.lower()
        if "inclusion criteria" in lower:
            bucket = inclusion
            seen_inclusion_header = True
            continue
        if "exclusion criteria" in lower:
            bucket = exclusion
            continue
        # Heuristics: one-liner bullets prefixed with - or • already stripped.
        bucket.append(line)

    # If we never saw any header and bucket was the inclusion list, treat the
    # whole text as a single inclusion paragraph rather than dropping it.
    if not seen_inclusion_header and not exclusion and inclusion:
        return (tuple(inclusion), ())
    return (tuple(inclusion), tuple(exclusion))


def _matches_sex(trial_sex: str | None, requested_sex: str | None) -> bool:
    if not requested_sex:
        return True
    if not trial_sex or trial_sex.upper() == "ALL":
        return True
    return trial_sex.strip().upper() == requested_sex.strip().upper()


def _matches_age_band(
    trial_min: str | None,
    trial_max: str | None,
    requested: dict[str, int] | None,
) -> bool:
    if not requested:
        return True
    rmin = requested.get("min")
    rmax = requested.get("max")
    tmin = _age_str_to_years(trial_min)
    tmax = _age_str_to_years(trial_max)
    if rmin is not None and tmax is not None and tmax < rmin:
        return False
    if rmax is not None and tmin is not None and tmin > rmax:
        return False
    return True


def _age_str_to_years(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.strip().split()
    if not parts:
        return None
    try:
        amount = int(parts[0])
    except ValueError:
        return None
    if len(parts) == 1:
        return amount
    unit = parts[1].lower()
    if unit.startswith("year"):
        return amount
    if unit.startswith("month"):
        return max(0, amount // 12)
    if unit.startswith("week"):
        return 0
    if unit.startswith("day"):
        return 0
    return amount


# ── Sync convenience wrappers ──────────────────────────────────────────────


def search_sync(**kwargs: Any) -> list[TrialSummary]:
    return asyncio.run(search(**kwargs))


def get_record_sync(nct_id: str, **kwargs: Any) -> TrialRecord:
    return asyncio.run(get_record(nct_id, **kwargs))
