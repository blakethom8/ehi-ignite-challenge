"""Skill + Agent + Workspace runtime.

See `docs/architecture/skill-runtime/SKILL-AGENT-WORKSPACE.md` for the architecture; this
package implements Layer 1 of the three-layer model: skill loading,
workspace primitives, and the citation graph contract.

Public surface today (Phase 1, commit 1 — skill format + loader):

- `Skill`, `SkillManifest`, `EscalationTrigger`, `EvalSpec`
- `SkillManifestError`
- `load_skill(skill_dir)`, `load_all_skills(root)`
- `SKILLS_ROOT`
"""

from api.core.skills.loader import (
    EscalationTrigger,
    EvalSpec,
    SKILLS_ROOT,
    Skill,
    SkillManifest,
    SkillManifestError,
    load_all_skills,
    load_skill,
)


__all__ = [
    "EscalationTrigger",
    "EvalSpec",
    "SKILLS_ROOT",
    "Skill",
    "SkillManifest",
    "SkillManifestError",
    "load_all_skills",
    "load_skill",
]
