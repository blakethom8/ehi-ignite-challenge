"""Shared workspace primitives — currently the unified events log only.

H0.5 explicitly ships the narrow events-table slice. The full
sessions/artifacts unification described in AGENTIC-HARNESS.md remains
deferred until a fourth plugin or a session-mismatch bug forces the
issue (see .claude/backend-hardening-plan.md §"Items deferred").
"""

from api.workspace.events import (
    WORKSPACE_CASPIAN,
    WORKSPACE_PLUGIN,
    WORKSPACE_SKILL,
    query_events,
    record_event,
)

__all__ = [
    "WORKSPACE_CASPIAN",
    "WORKSPACE_PLUGIN",
    "WORKSPACE_SKILL",
    "query_events",
    "record_event",
]
