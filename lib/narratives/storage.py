"""Disk layout for per-episode narratives (T5 / §D4).

Layout::

    data/narratives/<patient_id>/
        episodes.json                                    ← T4 seed
        <episode-slug>/
            current.json                                 ← latest Composition
            history/
                2026-05-12T14-30-00Z.json                ← prior versions

The current narrative is overwritten on every regeneration. The prior
``current.json`` (if any) is moved into ``history/<its-date>.json``
**before** the new one is written, and the new Composition carries
``relatesTo[0]`` pointing at the prior id with code ``replaces``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
NARRATIVE_STORE_ROOT = Path(
    os.getenv("ATLAS_NARRATIVE_STORE_PATH", REPO_ROOT / "data" / "narratives")
)


def episode_slug_for(episode: dict[str, Any]) -> str:
    """Derive the on-disk slug for an EpisodeOfCare resource.

    Uses ``EpisodeOfCare.id`` minus a leading ``episode-`` prefix when
    present, so an id of ``episode-cardiometabolic`` lands in
    ``cardiometabolic/`` rather than ``episode-cardiometabolic/``.
    """
    raw_id = str(episode.get("id") or "").strip()
    if not raw_id:
        raise ValueError("episode must have an id")
    if raw_id.startswith("episode-"):
        return raw_id[len("episode-") :]
    return raw_id


def history_dir_for(patient_id: str, episode_slug: str, *, root: Path | None = None) -> Path:
    return (root or NARRATIVE_STORE_ROOT) / patient_id / episode_slug / "history"


def current_path_for(patient_id: str, episode_slug: str, *, root: Path | None = None) -> Path:
    return (root or NARRATIVE_STORE_ROOT) / patient_id / episode_slug / "current.json"


def load_current_narrative(
    patient_id: str, episode_slug: str, *, root: Path | None = None
) -> dict[str, Any] | None:
    path = current_path_for(patient_id, episode_slug, root=root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _archive_path_for(history: Path, prior: dict[str, Any]) -> Path:
    """Compute a stable, filesystem-safe archive path from a prior Composition.

    Uses the prior's ``date`` (its generation timestamp) so versions
    sort chronologically. Falls back to "now" if the date is missing.
    """
    raw = str(prior.get("date") or datetime.now(timezone.utc).isoformat())
    safe = re.sub(r"[^0-9A-Za-z]+", "-", raw).strip("-")[:64] or "unknown"
    return history / f"{safe}.json"


def write_current_narrative(
    patient_id: str,
    composition: dict[str, Any],
    *,
    root: Path | None = None,
) -> Path:
    """Atomically replace the current narrative for an episode.

    1. If a prior ``current.json`` exists, copy it into
       ``history/<its-date>.json``.
    2. Mutate the incoming composition's ``relatesTo[0]`` to point at
       the prior's id with ``code='replaces'`` (only when a prior
       existed). Existing ``relatesTo`` entries are preserved as
       ``relatesTo[1:]``.
    3. Mark the prior's ``status='superseded'`` in history.
    4. Write the new composition to ``current.json``.

    Returns the path written.
    """
    episode_slug = _episode_slug_from_composition(composition)
    current = current_path_for(patient_id, episode_slug, root=root)
    history = history_dir_for(patient_id, episode_slug, root=root)
    current.parent.mkdir(parents=True, exist_ok=True)
    history.mkdir(parents=True, exist_ok=True)

    prior = load_current_narrative(patient_id, episode_slug, root=root)
    if prior is not None:
        prior_for_archive = dict(prior)
        prior_for_archive["status"] = "superseded"
        archive_path = _archive_path_for(history, prior_for_archive)
        archive_path.write_text(
            json.dumps(prior_for_archive, indent=2), encoding="utf-8"
        )
        # Wire the new composition to point back at the prior.
        prior_id = prior_for_archive.get("id")
        if prior_id:
            relates = list(composition.get("relatesTo") or [])
            relates.insert(
                0,
                {
                    "code": "replaces",
                    "targetReference": {"reference": f"Composition/{prior_id}"},
                },
            )
            composition["relatesTo"] = relates

    current.write_text(json.dumps(composition, indent=2), encoding="utf-8")
    return current


def _episode_slug_from_composition(composition: dict[str, Any]) -> str:
    """Recover the episode slug from a Composition resource.

    Reads the ``episode-ref`` extension we attach in §3.3 / §13. Falls
    back to the composition id when the extension is missing (older
    fixtures).
    """
    episode_ref = ""
    for ext in composition.get("extension") or []:
        if not isinstance(ext, dict):
            continue
        if ext.get("url", "").endswith("/episode-ref"):
            value = (ext.get("valueReference") or {}).get("reference", "")
            if value:
                episode_ref = value
                break
    if not episode_ref:
        comp_id = str(composition.get("id") or "")
        if "narrative-" in comp_id:
            tail = comp_id.split("narrative-", 1)[1]
            tail = re.split(r"-\d{4}-\d{2}-\d{2}", tail, maxsplit=1)[0]
            tail = tail.replace("-current", "")
            if tail:
                return tail
        raise ValueError(f"could not derive episode slug from composition id {comp_id!r}")
    slug = episode_ref.split("/", 1)[-1]
    if slug.startswith("episode-"):
        slug = slug[len("episode-") :]
    return slug
