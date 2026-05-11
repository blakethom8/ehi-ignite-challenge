"""Pydantic mirrors of trust.ts.

The TS file at app/src/components/atlas/trust.ts is the canonical
frontend contract. This module is the canonical backend contract.
Keep them in sync — when one changes, change the other.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AnchorScopeField = Literal[
    "demographics.age-band",
    "demographics.sex",
    "demographics.geography",
    "diagnoses.active",
    "diagnoses.history",
    "medications.active",
    "medications.history",
    "allergies",
    "biomarkers",
    "labs.recent",
    "encounters.recent",
    "performance-status",
]

RedactionPreset = Literal[
    "de-id-v1", "de-id-v2", "de-id-v3", "research-grade", "minimal"
]

PermissionKind = Literal["read-anchor", "call-external", "send-outbound"]

ToolCategory = Literal[
    "clinical-trial",
    "patient",
    "external",
    "outbound",
    "artifact",
    "transparency",
]

ConnectorAuth = Literal["none", "vendor-token", "user-delegated"]

ExportKind = Literal["markdown", "json", "shareable-bundle"]

ModelPresetId = Literal[
    "clinical-high", "clinical-balanced", "marketplace-act", "draft"
]

TrustPostureKind = Literal["consented-external", "internal-cohort"]

ApproverRole = Literal["clinician", "attending", "coordinator", "admin"]

OutboundActionKind = Literal[
    "send-packet",
    "register-patient",
    "submit-application",
    "schedule-followup",
    "post-update",
]

RunState = Literal[
    "awaiting-consent", "running", "waiting", "complete", "failed", "revoked"
]


class VendorIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    keyFingerprint: str


class TrustPosture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    posture: TrustPostureKind
    boundaryLabel: str
    requiresPerRunConsent: bool


class AnchorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: list[AnchorScopeField]
    redactionPreset: RedactionPreset
    ttlSeconds: int = Field(gt=0, le=86400)


class Permission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: PermissionKind
    scope: Optional[list[AnchorScopeField]] = None
    connector: Optional[str] = None
    channel: Optional[str] = None

    @model_validator(mode="after")
    def _shape_per_kind(self) -> "Permission":
        if self.kind == "read-anchor" and not self.scope:
            raise ValueError("read-anchor permission requires scope")
        if self.kind == "call-external" and not self.connector:
            raise ValueError("call-external permission requires connector")
        if self.kind == "send-outbound" and not self.channel:
            raise ValueError("send-outbound permission requires channel")
        return self


class Connector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    endpointPattern: str
    auth: ConnectorAuth = "none"


class PluginToolDecl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    category: ToolCategory
    permission: PermissionKind


class WorkflowDecl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    description: str
    tags: list[str]
    needs: list[str]
    produces: list[str]


class WorkbenchTabSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    kind: str
    renderer: str


class PluginFileSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group: str
    name: str
    icon: str
    dirty: Optional[bool] = None


class PluginAgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avatarInitials: str
    avatarColor: str
    modelPreset: ModelPresetId


class PluginUISpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    homeSections: list[str]
    workbenchTabs: list[WorkbenchTabSpec]
    files: list[PluginFileSeed]
    agent: PluginAgentSpec


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: str
    id: str
    version: str
    vendor: VendorIdentity
    displayName: str
    subtitle: str
    description: str
    icon: str
    color: str
    trust: TrustPosture
    anchor: AnchorSpec
    connectors: list[Connector]
    permissions: list[Permission]
    workflows: list[WorkflowDecl]
    tools: list[PluginToolDecl]
    ui: PluginUISpec
    exports: list[ExportKind]
    signature: str

    @model_validator(mode="after")
    def _declared_connectors_must_exist(self) -> "PluginManifest":
        ids = {c.id for c in self.connectors}
        for p in self.permissions:
            if p.kind == "call-external" and p.connector not in ids:
                raise ValueError(
                    f"permission references undeclared connector: {p.connector}"
                )
        # Each tool's declared permission must be covered somewhere in the
        # manifest's permission set.
        perm_kinds = {p.kind for p in self.permissions}
        for t in self.tools:
            if t.permission not in perm_kinds:
                raise ValueError(
                    f"tool {t.id} requires permission {t.permission} "
                    "but manifest declares no matching permission"
                )
        return self

    @field_validator("permissions")
    @classmethod
    def _at_least_one_permission(cls, v: list[Permission]) -> list[Permission]:
        if not v:
            raise ValueError("manifest must declare at least one permission")
        return v


# ============================================================
# Anchor package
# ============================================================


class AnchorPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: str
    pluginId: str
    pluginVersion: str
    patientId: str
    runId: str
    issuedAt: datetime
    expiresAt: datetime
    redactionPreset: RedactionPreset
    scope: list[AnchorScopeField]
    data: dict
    signature: str


# ============================================================
# Consent
# ============================================================


class ConsentToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pluginId: str
    runId: str
    scope: list[AnchorScopeField]
    issuedAt: datetime
    expiresAt: datetime
    approverId: str
    signature: str


# ============================================================
# Approvals
# ============================================================


class PluginApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["outbound"] = "outbound"
    runId: str
    approvalId: str
    pluginId: str
    action: OutboundActionKind
    description: str
    payloadPreview: str
    destination: str
    redactionPreset: RedactionPreset
    approverRole: ApproverRole
    status: Literal["pending", "approved", "denied", "voided"] = "pending"


# ============================================================
# Provenance
# ============================================================


class UserIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    role: ApproverRole


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    runId: str
    pluginId: str
    pluginVersion: str
    vendor: VendorIdentity
    action: OutboundActionKind
    approver: UserIdentity
    redactionPreset: RedactionPreset
    artifactId: Optional[str] = None
    endpoint: str
    responseStatus: int
    responseSummary: str
    ts: datetime
    signature: str


# ============================================================
# Runs
# ============================================================


class PluginRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    pluginId: str
    pluginVersion: str
    patientId: str
    state: RunState
    workflowId: Optional[str] = None
    title: Optional[str] = None
    step: Optional[str] = None
    elapsed: Optional[str] = None
    consentTokenId: Optional[str] = None
    anchorPackageId: Optional[str] = None
    startedBy: Optional[UserIdentity] = None
    startedAt: datetime
    completedAt: Optional[datetime] = None
