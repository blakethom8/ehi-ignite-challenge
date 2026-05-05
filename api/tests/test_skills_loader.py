"""Tests for `api.core.skills.loader`.

Covers the trial-matching reference skill and a battery of negative cases
that exercise the manifest contract from `docs/architecture/SKILL-AGENT-WORKSPACE.md`
§5.1–5.2.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from api.core.skills.loader import (
    SKILLS_ROOT,
    SkillManifestError,
    load_all_skills,
    load_skill,
)


# ── Reference skill: trial-matching ─────────────────────────────────────────


def test_trial_matching_skill_loads() -> None:
    skill = load_skill(SKILLS_ROOT / "trial-matching")

    assert skill.name == "trial-matching"
    assert skill.manifest.version == "0.1.0"
    assert skill.manifest.audience == "clinician"
    assert skill.manifest.shape == "brief-workspace"
    assert skill.manifest.agent_topology == "flat"
    assert skill.manifest.sub_agent_template is None


def test_trial_matching_required_tools_include_workspace_primitives() -> None:
    skill = load_skill(SKILLS_ROOT / "trial-matching")
    tools = set(skill.manifest.required_tools)

    # The universal substrate primitives — see §6.4 of the architecture doc.
    assert "workspace.write" in tools
    assert "workspace.cite" in tools
    assert "workspace.escalate" in tools


def test_trial_matching_escalation_triggers_present() -> None:
    skill = load_skill(SKILLS_ROOT / "trial-matching")
    conditions = {trigger.condition for trigger in skill.manifest.escalation}

    # Architecture doc §5.1 calls these out as the must-have triggers.
    assert "no_anchor_condition" in conditions
    assert "all_fit_scores_below_threshold" in conditions
    for trigger in skill.manifest.escalation:
        assert trigger.action in {
            "stop_and_ask",
            "stop_and_summarize",
            "stop_and_revise",
        }
        assert trigger.prompt


def test_trial_matching_output_schema_parses_and_requires_nct_id() -> None:
    skill = load_skill(SKILLS_ROOT / "trial-matching")
    schema = skill.output_schema

    # The artifact must enforce nct_id format and fit_score bounds.
    trial_def = schema["$defs"]["trial"]
    assert trial_def["properties"]["nct_id"]["pattern"] == "^NCT\\d{8}$"
    assert trial_def["properties"]["fit_score"]["maximum"] == 100
    assert "supporting_facts" in trial_def["required"]
    assert "escalation_triggered" in trial_def["required"]


def test_trial_matching_workspace_template_loaded() -> None:
    skill = load_skill(SKILLS_ROOT / "trial-matching")

    assert skill.workspace_template is not None
    assert "Trial Matching" in skill.workspace_template
    assert "TRIAL_SECTIONS_START" in skill.workspace_template


def test_trial_matching_eval_spec_present() -> None:
    skill = load_skill(SKILLS_ROOT / "trial-matching")
    spec = skill.manifest.eval

    assert spec is not None
    assert spec.rubric == "evals/rubric.md"
    assert "precision_at_5" in spec.metrics
    assert "citation_validity" in spec.metrics


def test_trial_matching_is_live_eligible() -> None:
    skill = load_skill(SKILLS_ROOT / "trial-matching")
    assert skill.is_live_eligible is True


def test_load_all_skills_includes_trial_matching() -> None:
    skills = load_all_skills()
    names = {s.name for s in skills}
    assert "trial-matching" in names


# ── Negative cases on synthetic fixtures ───────────────────────────────────


def _write_skill(
    tmp_path: Path,
    name: str,
    *,
    frontmatter: str,
    body: str = "# Skill body\n",
    extras: dict[str, str] | None = None,
) -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\n{frontmatter.strip()}\n---\n\n{body}", encoding="utf-8"
    )
    for relative, content in (extras or {}).items():
        target = skill_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return skill_dir


_VALID_SCHEMA = json.dumps({"type": "object", "properties": {}})


_MINIMAL_BRIEF_WORKSPACE_FM = textwrap.dedent(
    """\
    name: {name}
    version: 0.1.0
    audience: clinician
    shape: brief-workspace
    description: Reference skill used to exercise the manifest validator.
    required_tools:
      - workspace.write
    output_schema: output.schema.json
    escalation:
      - condition: nothing_to_do
        action: stop_and_ask
        prompt: Confirm you really want to run this.
    """
)


def _minimal_brief_workspace_extras() -> dict[str, str]:
    return {
        "workspace.template.md": "# Template\n",
        "output.schema.json": _VALID_SCHEMA,
    }


def test_missing_skill_md_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "broken"
    skill_dir.mkdir()
    with pytest.raises(SkillManifestError, match="SKILL.md"):
        load_skill(skill_dir)


def test_no_frontmatter_block_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "no-frontmatter"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# just a markdown body\n", encoding="utf-8")
    with pytest.raises(SkillManifestError, match="frontmatter"):
        load_skill(skill_dir)


def test_name_must_match_directory(tmp_path: Path) -> None:
    skill_dir = _write_skill(
        tmp_path,
        "real-name",
        frontmatter=_MINIMAL_BRIEF_WORKSPACE_FM.format(name="other-name"),
        extras=_minimal_brief_workspace_extras(),
    )
    with pytest.raises(SkillManifestError, match="must match directory name"):
        load_skill(skill_dir)


def test_invalid_semver_rejected(tmp_path: Path) -> None:
    fm = _MINIMAL_BRIEF_WORKSPACE_FM.format(name="bad-version").replace(
        "version: 0.1.0", "version: v1"
    )
    skill_dir = _write_skill(
        tmp_path,
        "bad-version",
        frontmatter=fm,
        extras=_minimal_brief_workspace_extras(),
    )
    with pytest.raises(SkillManifestError, match="version"):
        load_skill(skill_dir)


def test_unknown_audience_rejected(tmp_path: Path) -> None:
    fm = _MINIMAL_BRIEF_WORKSPACE_FM.format(name="bad-audience").replace(
        "audience: clinician", "audience: marketing"
    )
    skill_dir = _write_skill(
        tmp_path,
        "bad-audience",
        frontmatter=fm,
        extras=_minimal_brief_workspace_extras(),
    )
    with pytest.raises(SkillManifestError, match="audience"):
        load_skill(skill_dir)


def test_brief_workspace_requires_workspace_template(tmp_path: Path) -> None:
    extras = _minimal_brief_workspace_extras()
    extras.pop("workspace.template.md")
    skill_dir = _write_skill(
        tmp_path,
        "no-template",
        frontmatter=_MINIMAL_BRIEF_WORKSPACE_FM.format(name="no-template"),
        extras=extras,
    )
    with pytest.raises(SkillManifestError, match="workspace.template.md"):
        load_skill(skill_dir)


def test_brief_workspace_requires_at_least_one_escalation(tmp_path: Path) -> None:
    fm = textwrap.dedent(
        """\
        name: no-escalation
        version: 0.1.0
        audience: clinician
        shape: brief-workspace
        description: Skill missing the mandatory escalation list.
        required_tools:
          - workspace.write
        output_schema: output.schema.json
        """
    )
    skill_dir = _write_skill(
        tmp_path,
        "no-escalation",
        frontmatter=fm,
        extras=_minimal_brief_workspace_extras(),
    )
    with pytest.raises(SkillManifestError, match="escalation"):
        load_skill(skill_dir)


def test_unknown_escalation_action_rejected(tmp_path: Path) -> None:
    fm = _MINIMAL_BRIEF_WORKSPACE_FM.format(name="bad-action").replace(
        "action: stop_and_ask", "action: nuke_everything"
    )
    skill_dir = _write_skill(
        tmp_path,
        "bad-action",
        frontmatter=fm,
        extras=_minimal_brief_workspace_extras(),
    )
    with pytest.raises(SkillManifestError, match="escalation"):
        load_skill(skill_dir)


def test_planner_executor_requires_sub_agent_template(tmp_path: Path) -> None:
    fm = (
        _MINIMAL_BRIEF_WORKSPACE_FM.format(name="planner-only")
        + "agent_topology: planner_executor\n"
    )
    skill_dir = _write_skill(
        tmp_path,
        "planner-only",
        frontmatter=fm,
        extras=_minimal_brief_workspace_extras(),
    )
    with pytest.raises(SkillManifestError, match="sub_agent_template"):
        load_skill(skill_dir)


def test_missing_output_schema_file_rejected(tmp_path: Path) -> None:
    extras = _minimal_brief_workspace_extras()
    extras.pop("output.schema.json")
    skill_dir = _write_skill(
        tmp_path,
        "no-schema",
        frontmatter=_MINIMAL_BRIEF_WORKSPACE_FM.format(name="no-schema"),
        extras=extras,
    )
    with pytest.raises(SkillManifestError, match="output_schema"):
        load_skill(skill_dir)


def test_invalid_output_schema_json_rejected(tmp_path: Path) -> None:
    extras = _minimal_brief_workspace_extras()
    extras["output.schema.json"] = "{ not valid json"
    skill_dir = _write_skill(
        tmp_path,
        "broken-schema",
        frontmatter=_MINIMAL_BRIEF_WORKSPACE_FM.format(name="broken-schema"),
        extras=extras,
    )
    with pytest.raises(SkillManifestError, match="invalid JSON"):
        load_skill(skill_dir)


def test_dashboard_skill_does_not_require_workspace_template(tmp_path: Path) -> None:
    fm = textwrap.dedent(
        """\
        name: dashboard-only
        version: 0.1.0
        audience: clinician
        shape: dashboard
        description: A dashboard-shaped skill, not a workspace skill.
        required_tools:
          - run_sql
        output_schema: output.schema.json
        """
    )
    skill_dir = _write_skill(
        tmp_path,
        "dashboard-only",
        frontmatter=fm,
        extras={"output.schema.json": _VALID_SCHEMA},
    )
    skill = load_skill(skill_dir)
    assert skill.manifest.shape == "dashboard"
    assert skill.workspace_template is None
    assert skill.is_live_eligible is False  # no eval spec


def test_required_tools_must_be_non_empty(tmp_path: Path) -> None:
    fm = _MINIMAL_BRIEF_WORKSPACE_FM.format(name="no-tools").replace(
        "required_tools:\n  - workspace.write", "required_tools: []"
    )
    skill_dir = _write_skill(
        tmp_path,
        "no-tools",
        frontmatter=fm,
        extras=_minimal_brief_workspace_extras(),
    )
    with pytest.raises(SkillManifestError, match="required_tools"):
        load_skill(skill_dir)
