"""Server-declared capability policy for the four user modes.

This module is the single source of truth for "what can a given session do?".
The frontend consumes it via ``GET /api/auth/capabilities`` and renders the UI
accordingly — it never derives policy on its own.

Four modes:
  - ``anonymous``    — no cookie, landing pages only
  - ``demo``         — pre-baked patient session, sandboxed, ephemeral
  - ``authenticated``— signed-in account, full capabilities
  - ``guest``        — temporary harmonization run, scoped to the guest cookie

Add a new capability:
  1. Add the field to ``Capabilities`` below.
  2. Set the value for each mode in ``capabilities_for(...)``.
  3. (Frontend) consume the field via ``useCapabilities()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from api.core.auth import SessionPrincipal


class Capabilities(BaseModel):
    """Per-session capability surface. Always returned by /api/auth/capabilities."""

    mode: Literal["anonymous", "demo", "authenticated", "guest"]
    can_use_caspian: bool
    can_edit_caspian_user_files: bool
    can_write_caspian_notes: bool
    can_run_workflows: bool
    can_use_aggregation_uploads: bool
    can_use_aggregation_profiles: bool
    can_use_harmonize: bool
    can_use_guest_harmonization: bool
    can_use_assistant_tools_write: bool
    show_caspian_seed_files: bool
    persistence_scope: Literal[
        "none", "browser-ephemeral", "browser-persistent", "server-persistent"
    ]


def _anonymous() -> Capabilities:
    return Capabilities(
        mode="anonymous",
        can_use_caspian=False,
        can_edit_caspian_user_files=False,
        can_write_caspian_notes=False,
        can_run_workflows=False,
        can_use_aggregation_uploads=False,
        can_use_aggregation_profiles=False,
        can_use_harmonize=False,
        can_use_guest_harmonization=True,
        can_use_assistant_tools_write=False,
        show_caspian_seed_files=False,
        persistence_scope="none",
    )


def _demo() -> Capabilities:
    return Capabilities(
        mode="demo",
        can_use_caspian=True,
        can_edit_caspian_user_files=False,
        can_write_caspian_notes=False,
        can_run_workflows=True,
        can_use_aggregation_uploads=True,
        can_use_aggregation_profiles=False,
        can_use_harmonize=False,
        can_use_guest_harmonization=True,
        can_use_assistant_tools_write=False,
        show_caspian_seed_files=True,
        persistence_scope="browser-ephemeral",
    )


def _authenticated() -> Capabilities:
    return Capabilities(
        mode="authenticated",
        can_use_caspian=True,
        can_edit_caspian_user_files=True,
        can_write_caspian_notes=True,
        can_run_workflows=True,
        can_use_aggregation_uploads=True,
        can_use_aggregation_profiles=True,
        can_use_harmonize=True,
        can_use_guest_harmonization=True,
        can_use_assistant_tools_write=True,
        show_caspian_seed_files=False,
        persistence_scope="browser-persistent",
    )


def _guest() -> Capabilities:
    return Capabilities(
        mode="guest",
        can_use_caspian=False,
        can_edit_caspian_user_files=False,
        can_write_caspian_notes=False,
        can_run_workflows=False,
        can_use_aggregation_uploads=False,
        can_use_aggregation_profiles=False,
        can_use_harmonize=False,
        can_use_guest_harmonization=True,
        can_use_assistant_tools_write=False,
        show_caspian_seed_files=False,
        persistence_scope="browser-ephemeral",
    )


def capabilities_for(session: "SessionPrincipal | None") -> Capabilities:
    """Resolve the capability surface for a session principal (or anonymous)."""
    if session is None:
        return _anonymous()
    # Use duck-typing for the principal so this module stays import-cycle free
    # with api.core.auth (which transitively imports api.models).
    if getattr(session, "is_authenticated", False):
        return _authenticated()
    if getattr(session, "is_demo", False):
        return _demo()
    if getattr(session, "is_guest", False):
        return _guest()
    # Defensive: unknown modes get the safest possible surface.
    return _anonymous()


__all__ = ["Capabilities", "capabilities_for"]
