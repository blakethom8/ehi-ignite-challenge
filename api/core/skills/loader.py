"""Skill manifest loader and validator.

A skill is a directory under `skills/` containing a `SKILL.md` file with a
YAML frontmatter block followed by a markdown body, plus optional siblings:
`workspace.template.md`, `output.schema.json`, `evals/rubric.md`,
`evals/cohort.json`, `references/*.md`, `scripts/*.py`.

The loader parses the frontmatter, validates it against the contract in
`docs/architecture/skill-runtime/SKILL-AGENT-WORKSPACE.md` §5.1–5.2, parses the JSON
schemas it references, and returns a typed `Skill` object. The runtime
refuses to register a skill that fails validation; the marketplace UI
surfaces validation errors as the badge that gates "Live" promotion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "skills"

_AUDIENCES = frozenset({"clinician", "patient", "regulatory"})
_SHAPES = frozenset({"dashboard", "brief-workspace", "conversational"})
_TOPOLOGIES = frozenset({"flat", "planner_executor"})
_ESCALATION_ACTIONS = frozenset(
    {"stop_and_ask", "stop_and_summarize", "stop_and_revise"}
)
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


class SkillManifestError(ValueError):
    """Raised when a SKILL.md fails the contract.

    The message names the skill directory and the field that failed. The
    runtime surfaces this directly to the marketplace UI as a validation
    error — keep messages short and actionable.
    """

    def __init__(self, skill_dir: Path, field: str, reason: str) -> None:
        self.skill_dir = skill_dir
        self.field = field
        self.reason = reason
        super().__init__(f"{skill_dir.name}: {field} — {reason}")


@dataclass(frozen=True)
class EscalationTrigger:
    condition: str
    description: str
    action: str
    prompt: str


@dataclass(frozen=True)
class EvalSpec:
    rubric: str
    cohort: str | None
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class SkillManifest:
    name: str
    version: str
    audience: str
    shape: str
    description: str
    required_tools: tuple[str, ...]
    optional_tools: tuple[str, ...]
    context_packages: tuple[str, ...]
    output_schema_path: str
    input_schema_path: str | None
    workspace_template_path: str | None
    escalation: tuple[EscalationTrigger, ...]
    eval: EvalSpec | None
    agent_topology: str
    sub_agent_template: str | None


@dataclass(frozen=True)
class Skill:
    manifest: SkillManifest
    skill_dir: Path
    body: str
    output_schema: dict[str, Any]
    workspace_template: str | None

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def is_live_eligible(self) -> bool:
        """A skill is eligible for Live promotion only if it carries an eval spec.

        The marketplace shows a `Concept` badge for skills without an eval; it
        promotes to `Live` only after the eval cohort actually passes (a
        signal recorded outside this loader).
        """
        return self.manifest.eval is not None


def load_skill(skill_dir: Path) -> Skill:
    """Load and validate one skill directory. Raises `SkillManifestError`."""
    skill_dir = Path(skill_dir).resolve()
    if not skill_dir.is_dir():
        raise SkillManifestError(skill_dir, "skill_dir", "not a directory")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SkillManifestError(skill_dir, "SKILL.md", "missing")

    raw = skill_md.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(skill_dir, raw)
    manifest = _build_manifest(skill_dir, frontmatter)

    output_schema = _load_json(
        skill_dir,
        "output_schema",
        skill_dir / manifest.output_schema_path,
    )

    workspace_template: str | None = None
    if manifest.workspace_template_path is not None:
        template_path = skill_dir / manifest.workspace_template_path
        if not template_path.is_file():
            raise SkillManifestError(
                skill_dir,
                "workspace.template.md",
                f"declared but missing at {manifest.workspace_template_path}",
            )
        workspace_template = template_path.read_text(encoding="utf-8")

    if manifest.input_schema_path is not None:
        _load_json(skill_dir, "input_schema", skill_dir / manifest.input_schema_path)

    if manifest.eval is not None:
        rubric_path = skill_dir / manifest.eval.rubric
        if not rubric_path.is_file():
            raise SkillManifestError(
                skill_dir, "eval.rubric", f"missing at {manifest.eval.rubric}"
            )
        if manifest.eval.cohort is not None:
            cohort_path = skill_dir / manifest.eval.cohort
            if not cohort_path.is_file():
                raise SkillManifestError(
                    skill_dir, "eval.cohort", f"missing at {manifest.eval.cohort}"
                )
            _load_json(skill_dir, "eval.cohort", cohort_path)

    return Skill(
        manifest=manifest,
        skill_dir=skill_dir,
        body=body,
        output_schema=output_schema,
        workspace_template=workspace_template,
    )


def load_all_skills(root: Path | None = None) -> list[Skill]:
    """Load every skill directory under `root` (defaults to `SKILLS_ROOT`).

    A directory is considered a skill iff it contains a SKILL.md file.
    Validation errors are raised; callers wanting partial-success behavior
    should iterate skill dirs themselves and catch `SkillManifestError`.
    """
    root = Path(root) if root is not None else SKILLS_ROOT
    if not root.is_dir():
        return []
    skills: list[Skill] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "SKILL.md").is_file():
            continue
        skills.append(load_skill(child))
    return skills


def _split_frontmatter(skill_dir: Path, raw: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(raw)
    if match is None:
        raise SkillManifestError(
            skill_dir, "frontmatter", "SKILL.md must begin with a YAML --- block"
        )
    yaml_text, body = match.group(1), match.group(2)
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise SkillManifestError(
            skill_dir, "frontmatter", f"invalid YAML: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SkillManifestError(
            skill_dir, "frontmatter", "must be a YAML mapping"
        )
    return data, body


def _build_manifest(skill_dir: Path, fm: dict[str, Any]) -> SkillManifest:
    name = _required_str(skill_dir, fm, "name")
    if not _NAME_RE.match(name):
        raise SkillManifestError(
            skill_dir,
            "name",
            "must be lowercase alphanumeric with hyphens (no leading/trailing hyphen)",
        )
    if name != skill_dir.name:
        raise SkillManifestError(
            skill_dir,
            "name",
            f"must match directory name (got '{name}', dir '{skill_dir.name}')",
        )

    version = _required_str(skill_dir, fm, "version")
    if not _SEMVER_RE.match(version):
        raise SkillManifestError(
            skill_dir, "version", f"must be semver (got '{version}')"
        )

    audience = _required_enum(skill_dir, fm, "audience", _AUDIENCES)
    shape = _required_enum(skill_dir, fm, "shape", _SHAPES)
    description = _required_str(skill_dir, fm, "description").strip()
    if len(description) < 20:
        raise SkillManifestError(
            skill_dir, "description", "must be at least 20 characters"
        )

    required_tools = _required_str_tuple(skill_dir, fm, "required_tools")
    if not required_tools:
        raise SkillManifestError(
            skill_dir, "required_tools", "must declare at least one tool"
        )
    optional_tools = _optional_str_tuple(skill_dir, fm, "optional_tools")
    context_packages = _optional_str_tuple(skill_dir, fm, "context_packages")

    output_schema_path = _required_str(skill_dir, fm, "output_schema")
    input_schema_path = _optional_str(skill_dir, fm, "input_schema")

    workspace_template_path: str | None = None
    if shape == "brief-workspace":
        candidate = skill_dir / "workspace.template.md"
        if not candidate.is_file():
            raise SkillManifestError(
                skill_dir,
                "workspace.template.md",
                "required for shape=brief-workspace",
            )
        workspace_template_path = "workspace.template.md"

    escalation = _build_escalation(skill_dir, fm.get("escalation"), shape)
    eval_spec = _build_eval(skill_dir, fm.get("eval"))

    agent_topology = _optional_enum(
        skill_dir, fm, "agent_topology", _TOPOLOGIES, default="flat"
    )
    sub_agent_template = _optional_str(skill_dir, fm, "sub_agent_template")
    if agent_topology == "planner_executor" and sub_agent_template is None:
        raise SkillManifestError(
            skill_dir,
            "sub_agent_template",
            "required when agent_topology=planner_executor",
        )

    return SkillManifest(
        name=name,
        version=version,
        audience=audience,
        shape=shape,
        description=description,
        required_tools=required_tools,
        optional_tools=optional_tools,
        context_packages=context_packages,
        output_schema_path=output_schema_path,
        input_schema_path=input_schema_path,
        workspace_template_path=workspace_template_path,
        escalation=escalation,
        eval=eval_spec,
        agent_topology=agent_topology,
        sub_agent_template=sub_agent_template,
    )


def _build_escalation(
    skill_dir: Path, raw: Any, shape: str
) -> tuple[EscalationTrigger, ...]:
    if raw is None:
        if shape == "brief-workspace":
            raise SkillManifestError(
                skill_dir,
                "escalation",
                "required for shape=brief-workspace (declare at least one stop_and_ask)",
            )
        return ()
    if not isinstance(raw, list):
        raise SkillManifestError(skill_dir, "escalation", "must be a list")
    if shape == "brief-workspace" and not raw:
        raise SkillManifestError(
            skill_dir,
            "escalation",
            "must declare at least one trigger for brief-workspace skills",
        )
    triggers: list[EscalationTrigger] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SkillManifestError(
                skill_dir, f"escalation[{idx}]", "must be a mapping"
            )
        condition = _required_str(skill_dir, item, "condition", path=f"escalation[{idx}]")
        action = _required_str(skill_dir, item, "action", path=f"escalation[{idx}]")
        if action not in _ESCALATION_ACTIONS:
            raise SkillManifestError(
                skill_dir,
                f"escalation[{idx}].action",
                f"must be one of {sorted(_ESCALATION_ACTIONS)}",
            )
        prompt = _required_str(skill_dir, item, "prompt", path=f"escalation[{idx}]").strip()
        description = (item.get("description") or "").strip() or condition
        triggers.append(
            EscalationTrigger(
                condition=condition,
                description=description,
                action=action,
                prompt=prompt,
            )
        )
    return tuple(triggers)


def _build_eval(skill_dir: Path, raw: Any) -> EvalSpec | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SkillManifestError(skill_dir, "eval", "must be a mapping")
    rubric = _required_str(skill_dir, raw, "rubric", path="eval")
    cohort = _optional_str(skill_dir, raw, "cohort", path="eval")
    metrics_raw = raw.get("metrics") or []
    if not isinstance(metrics_raw, list) or not all(isinstance(m, str) for m in metrics_raw):
        raise SkillManifestError(skill_dir, "eval.metrics", "must be a list of strings")
    return EvalSpec(rubric=rubric, cohort=cohort, metrics=tuple(metrics_raw))


def _required_str(
    skill_dir: Path, fm: dict[str, Any], key: str, *, path: str | None = None
) -> str:
    field = path + "." + key if path else key
    if key not in fm:
        raise SkillManifestError(skill_dir, field, "missing")
    value = fm[key]
    if not isinstance(value, str) or not value.strip():
        raise SkillManifestError(skill_dir, field, "must be a non-empty string")
    return value.strip()


def _optional_str(
    skill_dir: Path, fm: dict[str, Any], key: str, *, path: str | None = None
) -> str | None:
    if key not in fm or fm[key] is None:
        return None
    field = path + "." + key if path else key
    value = fm[key]
    if not isinstance(value, str) or not value.strip():
        raise SkillManifestError(skill_dir, field, "must be a non-empty string when present")
    return value.strip()


def _required_enum(
    skill_dir: Path, fm: dict[str, Any], key: str, allowed: Iterable[str]
) -> str:
    value = _required_str(skill_dir, fm, key)
    if value not in allowed:
        raise SkillManifestError(
            skill_dir, key, f"must be one of {sorted(allowed)} (got '{value}')"
        )
    return value


def _optional_enum(
    skill_dir: Path,
    fm: dict[str, Any],
    key: str,
    allowed: Iterable[str],
    *,
    default: str,
) -> str:
    if key not in fm or fm[key] is None:
        return default
    return _required_enum(skill_dir, fm, key, allowed)


def _required_str_tuple(
    skill_dir: Path, fm: dict[str, Any], key: str
) -> tuple[str, ...]:
    raw = fm.get(key)
    if raw is None:
        raise SkillManifestError(skill_dir, key, "missing")
    return _coerce_str_tuple(skill_dir, key, raw)


def _optional_str_tuple(
    skill_dir: Path, fm: dict[str, Any], key: str
) -> tuple[str, ...]:
    raw = fm.get(key)
    if raw is None:
        return ()
    return _coerce_str_tuple(skill_dir, key, raw)


def _coerce_str_tuple(skill_dir: Path, key: str, raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise SkillManifestError(skill_dir, key, "must be a list")
    out: list[str] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise SkillManifestError(
                skill_dir, f"{key}[{idx}]", "must be a non-empty string"
            )
        out.append(item.strip())
    return tuple(out)


def _load_json(skill_dir: Path, field: str, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SkillManifestError(skill_dir, field, f"file not found: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillManifestError(
            skill_dir, field, f"invalid JSON in {path.name}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SkillManifestError(
            skill_dir, field, f"{path.name} must be a JSON object at the root"
        )
    return data


def main(argv: list[str] | None = None) -> int:
    """CLI: validate one or more skill directories.

    Usage: `uv run python -m api.core.skills.loader [skill_dir ...]`
    With no arguments, validates every skill under `SKILLS_ROOT`.
    """
    import sys

    args = list(argv) if argv is not None else sys.argv[1:]
    targets = [Path(a) for a in args] if args else None

    if targets is None:
        skills = load_all_skills()
        if not skills:
            print(f"No skills found under {SKILLS_ROOT}")
            return 0
        for skill in skills:
            print(
                f"OK  {skill.name} v{skill.manifest.version} "
                f"({skill.manifest.shape}, audience={skill.manifest.audience})"
            )
        return 0

    failures = 0
    for target in targets:
        try:
            skill = load_skill(target)
        except SkillManifestError as exc:
            print(f"FAIL {target}: {exc}")
            failures += 1
            continue
        print(
            f"OK  {skill.name} v{skill.manifest.version} "
            f"({skill.manifest.shape}, audience={skill.manifest.audience})"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
