"""On-disk storage helpers for pipeline clinical QA eval artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.extract.lab.evaluations.models import EvaluationResult
from lib.extract.lab.recorder import REPO_ROOT

DEFAULT_EVAL_ROOT = REPO_ROOT / "data" / "pipeline-evals"


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_evaluation_summary(eval_run_id: str, *, root: Path | None = None) -> EvaluationResult | None:
    eval_root = root or DEFAULT_EVAL_ROOT
    data = load_json(eval_root / "runs" / eval_run_id / "summary.json")
    if not isinstance(data, dict) or not data:
        return None
    return EvaluationResult.model_validate(data)


def list_evaluation_summaries(*, root: Path | None = None) -> list[EvaluationResult]:
    eval_root = root or DEFAULT_EVAL_ROOT
    runs_dir = eval_root / "runs"
    if not runs_dir.exists():
        return []

    summaries: list[EvaluationResult] = []
    for summary_path in runs_dir.glob("*/summary.json"):
        data = load_json(summary_path)
        if not isinstance(data, dict) or not data:
            continue
        try:
            summaries.append(EvaluationResult.model_validate(data))
        except Exception:
            continue
    return sorted(summaries, key=lambda item: item.finished_at or item.created_at, reverse=True)


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
