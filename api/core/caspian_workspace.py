"""
Caspian per-patient file workspace.

A workspace is a directory on disk that holds the files the clinician and the
Caspian agent share for one (user|session, patient) pair:

    data/caspian-workspaces/<workspace_key>/
      user-instructions.md       (editable; appended to the chat system prompt)
      notes/                     (user + agent freeform)
      workflow-runs/             (auto-populated when a workflow run completes)

Reads and writes go through this module so we have one place that enforces:
  - workspace-key derivation (auth vs demo)
  - path scoping (no `..`, only writable under the allowed subtrees)
  - atomic writes
  - audit logging via authorize_patient_access()

The virtual `system-context/` tree (the live system prompt, the live patient
context, the workflow packets) is merged in for *listing* and *reading* but
never written to disk — its contents come from `caspian_context_files`.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from api.core.auth import SessionPrincipal
from api.core import caspian_context_files

LOGGER = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKSPACES_ROOT = _REPO_ROOT / "data" / "caspian-workspaces"

# Caps. Keep them generous; the chat tool layer also limits.
MAX_FILE_BYTES = 200_000
MAX_PATH_LENGTH = 200

# File-kind taxonomy:
#   "system"     — virtual system-context tree, always read-only
#   "user"       — clinician-authored files (notes/, user-instructions.md)
#   "generated"  — workflow-run artifacts (workflow-runs/), read-only to users
#   "demo-seed"  — virtual sample files shown only in demo mode (P3)
#
# Writes split:
#   USER_WRITABLE_*       — user-authored paths, gated by session.is_authenticated
#   GENERATED_WRITABLE_*  — system-generated paths (workflow runner), same gate
#
# Demo and guest sessions can never write. The route-layer gate in
# api/routers/caspian_files.py provides defense in depth.
USER_WRITABLE_PREFIXES = ("notes/",)
GENERATED_WRITABLE_PREFIXES = ("workflow-runs/",)
USER_WRITABLE_FILES = {"user-instructions.md"}

# Backwards-compat aliases — keep until all callers migrate.
WRITABLE_PREFIXES = USER_WRITABLE_PREFIXES + GENERATED_WRITABLE_PREFIXES
WRITABLE_FILES = USER_WRITABLE_FILES

USER_INSTRUCTIONS_PATH = "user-instructions.md"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WorkspacePathError(ValueError):
    """A path is malformed or escapes the workspace."""


class WorkspaceForbiddenError(PermissionError):
    """A write target is outside the writable subtree."""


class WorkspaceNotFoundError(FileNotFoundError):
    """No such file under the workspace."""


# ---------------------------------------------------------------------------
# Tree shape — mirrors the frontend FileTreeNode
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceFileTreeNode:
    """Discriminated union sent to the frontend.

    The frontend's FileTreeNode supports three variants:
      type=group  → label
      type=folder → name, expanded, children
      type=file   → name, id, ext, icon, dirty, editable
      type=ref    → id, label, sub  (not used here)

    We model it as a flat dict so the route serializer can pass it through
    without juggling pydantic discriminator config.
    """

    payload: dict


def _group(label: str) -> dict:
    return {"type": "group", "label": label}


def _folder(name: str, children: list[dict], expanded: bool = False) -> dict:
    return {
        "type": "folder",
        "name": name,
        "expanded": expanded,
        "children": children,
    }


def _file(
    name: str,
    path: str,
    *,
    editable: bool,
    kind: str = "user",
    dirty: bool = False,
) -> dict:
    return {
        "type": "file",
        "name": name,
        "id": path,
        "ext": _ext(name),
        "icon": _icon_for_ext(_ext(name)),
        "dirty": dirty,
        "editable": editable,
        "kind": kind,
    }


def _ext(name: str) -> str:
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[1].lower()


def _icon_for_ext(ext: str) -> str:
    if ext == "json":
        return "Braces"
    if ext == "csv":
        return "FileSpreadsheet"
    return "FileText"


# ---------------------------------------------------------------------------
# Workspace key + paths
# ---------------------------------------------------------------------------


_KEY_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_key_part(value: str) -> str:
    """Reduce an identifier to filesystem-safe characters."""
    cleaned = unicodedata.normalize("NFKC", value).strip()
    return _KEY_SAFE.sub("_", cleaned) or "anon"


def workspace_key_for(session: SessionPrincipal, resolved_patient_id: str) -> str:
    """Derive the on-disk key for a (session, patient) pair.

    Demo sessions are scoped by session_id so two demo browsers don't share
    files. Authenticated sessions are scoped by user_id so files survive
    re-login on the same account.
    """
    patient = _sanitize_key_part(resolved_patient_id)
    if session.is_demo:
        return f"demo-{_sanitize_key_part(session.session_id)}--{patient}"
    user_id = session.user_id or session.session_id
    return f"auth-{_sanitize_key_part(user_id)}--{patient}"


def workspace_root(session: SessionPrincipal, resolved_patient_id: str) -> Path:
    return _WORKSPACES_ROOT / workspace_key_for(session, resolved_patient_id)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def _normalize_relative_path(raw: str) -> str:
    """Reject malformed paths; return the canonical relative form."""
    if not raw or not isinstance(raw, str):
        raise WorkspacePathError("path is required")
    if len(raw) > MAX_PATH_LENGTH:
        raise WorkspacePathError(f"path exceeds {MAX_PATH_LENGTH} chars")
    if "\x00" in raw:
        raise WorkspacePathError("path contains null bytes")
    # Normalize separators, drop leading slashes, collapse duplicates.
    normalized = raw.replace("\\", "/").lstrip("/")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if not parts:
        raise WorkspacePathError("path is empty after normalization")
    if any(p == ".." for p in parts):
        raise WorkspacePathError("path may not contain '..'")
    if any(p.startswith(".") and p not in {".gitkeep"} for p in parts):
        # Allow .gitkeep but otherwise prevent hidden files.
        raise WorkspacePathError("hidden paths are not allowed")
    return "/".join(parts)


def _is_user_writable_path(rel_path: str) -> bool:
    """User-authored content (notes/, user-instructions.md)."""
    if rel_path in USER_WRITABLE_FILES:
        return True
    return any(rel_path.startswith(prefix) for prefix in USER_WRITABLE_PREFIXES)


def _is_generated_writable_path(rel_path: str) -> bool:
    """System-generated artifacts (workflow-runs/)."""
    return any(rel_path.startswith(prefix) for prefix in GENERATED_WRITABLE_PREFIXES)


def _is_writable_path(rel_path: str) -> bool:
    """Legacy combined check — kept for back-compat. Prefer the split helpers."""
    return _is_user_writable_path(rel_path) or _is_generated_writable_path(rel_path)


def _kind_for_path(rel_path: str) -> str:
    """Map a workspace-relative path to its file-kind tag."""
    if _is_system_context_path(rel_path):
        return "system"
    if _is_generated_writable_path(rel_path):
        return "generated"
    if _is_user_writable_path(rel_path):
        return "user"
    return "user"


def _is_system_context_path(rel_path: str) -> bool:
    return rel_path == "system-context" or rel_path.startswith("system-context/")


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def _kind_for_ext(ext: str) -> str:
    if ext == "json":
        return "json"
    if ext in {"md", "markdown"}:
        return "markdown"
    return "text"


@dataclass
class FileReadResult:
    path: str
    content: str
    mtime: datetime | None
    editable: bool
    kind: str
    """``kind_for_ext`` — markdown/json/text (legacy content-format field)."""
    file_kind: str = "user"
    """File-kind taxonomy: system / user / generated / demo-seed."""


def read_workspace_file(
    session: SessionPrincipal,
    resolved_patient_id: str,
    raw_path: str,
) -> FileReadResult:
    rel_path = _normalize_relative_path(raw_path)
    ext = _ext(rel_path.rsplit("/", 1)[-1])
    kind = _kind_for_ext(ext)
    file_kind = _kind_for_path(rel_path)

    if _is_system_context_path(rel_path):
        content = caspian_context_files.render_virtual_file(rel_path, resolved_patient_id)
        return FileReadResult(
            path=rel_path,
            content=content,
            mtime=None,
            editable=False,
            kind=kind,
            file_kind="system",
        )

    root = workspace_root(session, resolved_patient_id)
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise WorkspacePathError("path escapes workspace") from exc
    if not target.exists():
        # `user-instructions.md` should always read cleanly even when empty.
        if rel_path == USER_INSTRUCTIONS_PATH:
            return FileReadResult(
                path=rel_path,
                content="",
                mtime=None,
                editable=session.is_authenticated,
                kind="markdown",
                file_kind="user",
            )
        raise WorkspaceNotFoundError(rel_path)
    if not target.is_file():
        raise WorkspacePathError("path is not a file")
    content = target.read_text(encoding="utf-8")
    # Editable iff this is a user-authored path AND the caller is authenticated.
    editable = file_kind == "user" and session.is_authenticated
    return FileReadResult(
        path=rel_path,
        content=content,
        mtime=datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc),
        editable=editable,
        kind=kind,
        file_kind=file_kind,
    )


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


@dataclass
class FileWriteResult:
    path: str
    bytes: int
    mtime: datetime


def _atomic_write(target: Path, encoded: bytes) -> FileWriteResult:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: tmp file in the same dir, then rename.
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp-", suffix=".part")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return FileWriteResult(
        path=str(target.name),
        bytes=len(encoded),
        mtime=datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc),
    )


def _resolve_write_target(
    session: SessionPrincipal,
    resolved_patient_id: str,
    rel_path: str,
) -> Path:
    root = workspace_root(session, resolved_patient_id)
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise WorkspacePathError("path escapes workspace") from exc
    return target


def write_workspace_file(
    session: SessionPrincipal,
    resolved_patient_id: str,
    raw_path: str,
    content: str,
) -> FileWriteResult:
    """Write a USER-authored file. Authenticated sessions only.

    User files live under ``notes/`` or are the bare ``user-instructions.md``.
    Generated workflow-run artifacts must go through ``write_generated_artifact``.
    """
    rel_path = _normalize_relative_path(raw_path)

    if _is_system_context_path(rel_path):
        raise WorkspaceForbiddenError("system-context/ is read-only")
    if not session.is_authenticated:
        raise WorkspaceForbiddenError(
            "Workspace writes require an authenticated session."
        )
    if not _is_user_writable_path(rel_path):
        raise WorkspaceForbiddenError(
            f"Path is not user-writable: {rel_path!r}. "
            "User-writable paths: notes/ or user-instructions.md."
        )

    if not isinstance(content, str):
        raise WorkspacePathError("content must be a string")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise WorkspacePathError(f"content exceeds {MAX_FILE_BYTES} byte limit")

    target = _resolve_write_target(session, resolved_patient_id, rel_path)
    result = _atomic_write(target, encoded)
    return FileWriteResult(
        path=rel_path,
        bytes=result.bytes,
        mtime=result.mtime,
    )


def write_generated_artifact(
    session: SessionPrincipal,
    resolved_patient_id: str,
    raw_path: str,
    content: str,
) -> FileWriteResult:
    """Write a SYSTEM-GENERATED artifact (e.g. a workflow-run output).

    Same authenticated-only gate as user writes. Demo and guest sessions get a
    ``WorkspaceForbiddenError`` — demo workflow runs are not persisted to disk.
    """
    rel_path = _normalize_relative_path(raw_path)

    if not session.is_authenticated:
        raise WorkspaceForbiddenError(
            "Workspace writes require an authenticated session."
        )
    if not _is_generated_writable_path(rel_path):
        raise WorkspaceForbiddenError(
            f"Path is not a generated-artifact path: {rel_path!r}. "
            "Generated paths: workflow-runs/."
        )

    if not isinstance(content, str):
        raise WorkspacePathError("content must be a string")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise WorkspacePathError(f"content exceeds {MAX_FILE_BYTES} byte limit")

    target = _resolve_write_target(session, resolved_patient_id, rel_path)
    result = _atomic_write(target, encoded)
    return FileWriteResult(
        path=rel_path,
        bytes=result.bytes,
        mtime=result.mtime,
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def _list_on_disk(
    root: Path, *, user_editable: bool
) -> tuple[list[dict], list[dict], dict | None]:
    """Return (notes_children, workflow_runs_children, user_instructions_file).

    ``user_editable`` flips the editable flag for user-authored files based on
    the caller's session mode — only authenticated sessions get edit affordance.
    Generated artifacts (workflow-runs/) are never editable regardless of mode.
    """
    notes_children: list[dict] = []
    runs_children: list[dict] = []
    user_instructions: dict | None = None

    if root.exists():
        # user-instructions.md
        ui_target = root / USER_INSTRUCTIONS_PATH
        if ui_target.exists():
            user_instructions = _file(
                USER_INSTRUCTIONS_PATH,
                USER_INSTRUCTIONS_PATH,
                editable=user_editable,
                kind="user",
                dirty=ui_target.stat().st_size > 0,
            )

        # notes/
        notes_dir = root / "notes"
        if notes_dir.is_dir():
            for entry in sorted(notes_dir.iterdir()):
                if not entry.is_file():
                    continue
                if entry.name.startswith("."):
                    continue
                notes_children.append(
                    _file(
                        entry.name,
                        f"notes/{entry.name}",
                        editable=user_editable,
                        kind="user",
                    )
                )

        # workflow-runs/
        runs_dir = root / "workflow-runs"
        if runs_dir.is_dir():
            # Newest first.
            entries = [e for e in runs_dir.iterdir() if e.is_file() and not e.name.startswith(".")]
            entries.sort(key=lambda e: e.stat().st_mtime, reverse=True)
            for entry in entries:
                runs_children.append(
                    _file(
                        entry.name,
                        f"workflow-runs/{entry.name}",
                        editable=False,
                        kind="generated",
                    )
                )

    # user-instructions.md placeholder if not on disk.
    if user_instructions is None:
        user_instructions = _file(
            USER_INSTRUCTIONS_PATH,
            USER_INSTRUCTIONS_PATH,
            editable=user_editable,
            kind="user",
            dirty=False,
        )

    return notes_children, runs_children, user_instructions


def _system_context_tree() -> dict:
    workflows = [
        _file(name, f"system-context/workflows/{name}", editable=False, kind="system")
        for name in (
            "preop_review_v1.md",
            "medication_safety_v1.md",
            "longitudinal_synthesis_v1.md",
        )
    ]
    return _folder(
        "system-context",
        [
            _file(
                "caspian-system-prompt.md",
                "system-context/caspian-system-prompt.md",
                editable=False,
                kind="system",
            ),
            _file(
                "patient-chart-context.md",
                "system-context/patient-chart-context.md",
                editable=False,
                kind="system",
            ),
            _folder("workflows", workflows, expanded=False),
        ],
        expanded=False,
    )


def list_workspace(
    session: SessionPrincipal,
    resolved_patient_id: str,
) -> dict:
    """Return the file tree shape the frontend FilesPane consumes."""
    root = workspace_root(session, resolved_patient_id)
    notes_children, runs_children, user_instructions = _list_on_disk(
        root, user_editable=session.is_authenticated
    )

    tree: list[dict] = [
        _group("Patient workspace"),
        user_instructions,
        _folder("notes", notes_children, expanded=True),
        _folder("workflow-runs", runs_children, expanded=True),
        _group("System context (read-only)"),
        _system_context_tree(),
    ]
    return {
        "workspace_key": workspace_key_for(session, resolved_patient_id),
        "tree": tree,
    }


# ---------------------------------------------------------------------------
# Helpers re-used by the workflow runner
# ---------------------------------------------------------------------------


def workflow_run_filename(workflow_id: str, generated_at: datetime, suffix: str) -> str:
    """Stable filename for a workflow run artifact written to disk."""
    date = generated_at.strftime("%Y-%m-%d")
    slug = re.sub(r"_v\d+$", "", workflow_id)
    return f"{date}-{slug}-{suffix}.md"
