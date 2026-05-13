"""
Caspian-workspace models — workflow runs (pre-packaged review packets that
produce a structured artifact) and the per-patient on-disk file
workspace (list / read / write / save-as-note).

Consumed by `api/routers/workflows.py`, `api/routers/caspian_files.py`,
and `api/core/workflow_runner.py`.

This module pulls in `ProviderAssistantCitation` and `TraceDetail` from
`api.models.assistant` for the workflow-run response shape, and imports
`Capabilities` from `api.core.access_policy` at module bottom so the
`CaspianFileListResponse.capabilities` forward reference resolves via an
explicit `model_rebuild()` call (matches the pre-split layout).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field
from typing_extensions import Annotated

from api.models.assistant import ProviderAssistantCitation, TraceDetail


# ---------------------------------------------------------------------------
# Caspian workflow runs — pre-packaged review packets that produce a
# structured artifact rendered in the workbench rather than a chat reply.
# See data/workflows/*.json for the prompt packets that drive these.
# ---------------------------------------------------------------------------


class WorkflowBanner(BaseModel):
    """Disposition banner shown at the top of the artifact."""
    status: Literal[
        "clear",
        "review",
        "hold",
        "critical",
        "stable",
        "evolving",
        "deteriorating",
    ]
    label: str = Field(min_length=1, max_length=80)
    headline: str = Field(min_length=1, max_length=240)
    action_label: str | None = Field(default=None, max_length=40)


class WorkflowFactCell(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=80)
    tone: Literal["default", "tier", "caution"] = "default"


class WorkflowTableSection(BaseModel):
    kind: Literal["table"] = "table"
    title: str = Field(min_length=1, max_length=120)
    columns: list[str] = Field(min_length=1, max_length=8)
    # Each row is the same length as `columns`. Cells are strings; citation
    # IDs are encoded inline as `c_<id>` and the frontend renders them as
    # clickable chips that route to the inspector.
    rows: list[list[str]] = Field(default_factory=list)
    empty_note: str | None = Field(default=None, max_length=200)


class WorkflowNarrativeSection(BaseModel):
    kind: Literal["narrative"] = "narrative"
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


WorkflowSection = Annotated[
    WorkflowTableSection | WorkflowNarrativeSection,
    Discriminator("kind"),
]


class WorkflowArtifact(BaseModel):
    """The structured packet returned by a workflow run."""
    workflow_id: str = Field(min_length=1, max_length=80)
    workflow_title: str = Field(min_length=1, max_length=120)
    workflow_type: str = Field(min_length=1, max_length=80)
    artifact_id: str = Field(min_length=1, max_length=120)
    generated_at: datetime
    banner: WorkflowBanner
    fact_rail: list[WorkflowFactCell] = Field(default_factory=list, max_length=8)
    sections: list[WorkflowSection] = Field(default_factory=list, max_length=12)
    chat_narration: str = Field(min_length=1, max_length=400)
    # Set to the relative workspace path (e.g. "workflow-runs/2026-05-12-pre-op-…")
    # once the runner persists the artifact to the Caspian file workspace.
    # Stays None for demo/guest sessions where artifacts are not persisted.
    file_path: str | None = Field(default=None, max_length=240)
    # File-kind taxonomy — workflow artifacts are always "generated".
    kind: Literal["generated"] = "generated"


class WorkflowRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=200)
    workflow_id: Literal[
        "preop_review_v1",
        "medication_safety_v1",
        "longitudinal_synthesis_v1",
    ]


class WorkflowRunResponse(BaseModel):
    patient_id: str
    artifact: WorkflowArtifact
    citations: list[ProviderAssistantCitation] = Field(default_factory=list)
    trace: TraceDetail | None = None


# ---------------------------------------------------------------------------
# Caspian file workspace — per-patient on-disk working directory.
# See api/core/caspian_workspace.py.
# ---------------------------------------------------------------------------


class CaspianFileNode(BaseModel):
    """One file node in the workspace tree.

    The list endpoint actually returns a free-form ``tree: list[dict]`` because
    the file/folder/group discriminator is awkward to model in Pydantic — but
    every file leaf in that tree carries this shape (id/name/ext/icon/dirty/
    editable/kind).
    """
    type: Literal["file"] = "file"
    name: str
    id: str
    ext: str = ""
    icon: str = "FileText"
    dirty: bool = False
    editable: bool = False
    kind: Literal["system", "user", "generated", "demo-seed"] = "user"


class CaspianFileListResponse(BaseModel):
    """Tree of files under (session, patient). Tree is freeform JSON because the
    server enforces the FileTreeNode shape; the frontend has its own typed union.

    ``capabilities`` echoes the current session's policy so the FilesPane can
    render the right affordances (sample-workspace banner, edit button, etc.).
    """
    workspace_key: str
    tree: list[dict]
    capabilities: "Capabilities | None" = None


class CaspianFileReadResponse(BaseModel):
    path: str
    content: str
    mtime: datetime | None
    editable: bool
    kind: Literal["markdown", "json", "text"]
    file_kind: Literal["system", "user", "generated", "demo-seed"] = "user"


class CaspianFileWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)


class CaspianFileWriteResponse(BaseModel):
    path: str
    bytes: int
    mtime: datetime


class SaveAsNoteRequest(BaseModel):
    """Copy a generated workflow-run artifact into the user's notes/ folder.

    The route enforces that ``source_path`` lives under ``workflow-runs/`` and
    that the session is authenticated; the workspace layer enforces atomic
    write + path scoping. Filename collisions in ``notes/`` are resolved by
    suffixing ``-2``, ``-3``, … to the basename.
    """
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=200)
    source_path: str = Field(min_length=1, max_length=200)


# Late import + forward-ref resolution: api.core.access_policy imports from
# api.core.auth which is fine, but api.core.access_policy.Capabilities is the
# canonical source. We re-export it here so callers can `from api.models import
# Capabilities` without dragging in api.core.access_policy directly.
from api.core.access_policy import Capabilities as Capabilities  # noqa: E402

CaspianFileListResponse.model_rebuild()
