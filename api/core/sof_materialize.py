"""Materialize the SQL-on-FHIR warehouse (``data/sof.db``) on demand.

Used by the FastAPI startup hook. Idempotent — a second call is cheap
because we mtime-compare the DB against the ViewDefinitions and the
Synthea bundle directory and bail out when nothing has moved.

Design notes:

* **Atomic-ish rebuild.** We write the new database to ``sof.db.tmp``
  and rename it over ``sof.db`` when the ingest is done, so a crashed
  build never leaves a half-populated DB in place.
* **Honors env vars** (``SOF_DB_PATH``, ``SOF_FHIR_DIR``,
  ``SOF_PATIENT_LIMIT``, ``SOF_AUTO_MATERIALIZE``) so the test suite and
  the production boot can share the same code path.
* **Never raises inside the startup hook.** The module-level function
  ``materialize_if_stale`` does raise on disk errors so unit tests can
  assert on them, but ``materialize_from_env`` catches everything and
  returns ``None`` on failure so a broken warehouse can't take the API
  offline.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VIEWS_DIR = _REPO_ROOT / "lib" / "sql_on_fhir" / "views"
_DEFAULT_FHIR_DIR = (
    _REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"
)
_DEFAULT_DB_PATH = _REPO_ROOT / "data" / "sof.db"
_DEFAULT_LIMIT = 200

_log = logging.getLogger("api.sof_materialize")


@dataclass
class MaterializeReport:
    db_path: Path
    built: bool
    row_counts: dict[str, int] = field(default_factory=dict)
    duration_s: float = 0.0
    patient_limit: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": str(self.db_path),
            "built": self.built,
            "row_counts": self.row_counts,
            "duration_s": round(self.duration_s, 3),
            "patient_limit": self.patient_limit,
            "reason": self.reason,
        }


def _dir_mtime(path: Path) -> float:
    """Return the directory's own mtime (cheap, good enough).

    We intentionally do not walk children — adding a new bundle will
    bump the parent directory's mtime on every filesystem we care about
    (ext4, apfs, ntfs, tmpfs), and walking 1,180 files on every boot
    would defeat the purpose of the mtime gate.
    """
    if not path.exists():
        return 0.0
    return path.stat().st_mtime


def _db_is_stale(db_path: Path, views_dir: Path, fhir_dir: Path) -> tuple[bool, str]:
    if not db_path.exists():
        return True, "db does not exist"

    db_mtime = db_path.stat().st_mtime
    view_files = list(views_dir.glob("*.json"))
    if not view_files:
        return False, "no views to materialize"

    latest_view = max(p.stat().st_mtime for p in view_files)
    if latest_view > db_mtime:
        return True, "view definitions newer than db"

    if _dir_mtime(fhir_dir) > db_mtime:
        return True, "fhir dir newer than db"

    return False, "db is fresh"


def materialize_if_stale(
    *,
    db_path: Path = _DEFAULT_DB_PATH,
    fhir_dir: Path = _DEFAULT_FHIR_DIR,
    views_dir: Path = _VIEWS_DIR,
    patient_limit: int = _DEFAULT_LIMIT,
) -> MaterializeReport:
    """Rebuild ``db_path`` from the FHIR bundles if anything upstream moved.

    Returns a ``MaterializeReport``. When ``built`` is False the DB was
    already fresh and nothing was touched on disk.
    """
    from lib.sql_on_fhir.loader import iter_all_resources  # type: ignore
    from lib.sql_on_fhir.sqlite_sink import (  # type: ignore
        materialize_all,
        open_db,
    )
    from lib.sql_on_fhir.view_definition import ViewDefinition  # type: ignore

    db_path = Path(db_path)
    fhir_dir = Path(fhir_dir)
    views_dir = Path(views_dir)

    stale, reason = _db_is_stale(db_path, views_dir, fhir_dir)
    if not stale:
        return MaterializeReport(
            db_path=db_path,
            built=False,
            row_counts={},
            duration_s=0.0,
            patient_limit=patient_limit,
            reason=reason,
        )

    if not fhir_dir.exists():
        raise FileNotFoundError(f"FHIR bundle directory not found: {fhir_dir}")

    view_files = sorted(views_dir.glob("*.json"))
    if not view_files:
        raise FileNotFoundError(f"No ViewDefinitions found in: {views_dir}")
    views = [ViewDefinition.from_json_file(p) for p in view_files]

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_suffix(db_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    t0 = time.monotonic()
    conn = open_db(tmp_path)
    try:
        counts = materialize_all(
            views, iter_all_resources(fhir_dir, limit=patient_limit), conn
        )
    finally:
        conn.close()
    duration = time.monotonic() - t0

    # Atomic-ish swap: replace the live DB with the freshly built one.
    tmp_path.replace(db_path)

    return MaterializeReport(
        db_path=db_path,
        built=True,
        row_counts=counts,
        duration_s=duration,
        patient_limit=patient_limit,
        reason=reason,
    )


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def materialize_from_env() -> MaterializeReport | None:
    """Entry point for the FastAPI startup hook.

    Respects:
      * ``SOF_AUTO_MATERIALIZE`` — set to 0/false to skip entirely
      * ``SOF_DB_PATH``         — absolute path to the SQLite DB
      * ``SOF_FHIR_DIR``        — absolute path to the FHIR bundle directory
      * ``SOF_PATIENT_LIMIT``   — integer cap on patients ingested (default 200)

    Never raises. On any failure we log a warning and return ``None`` so
    the API comes up even with a broken warehouse.
    """
    if not _env_flag("SOF_AUTO_MATERIALIZE", True):
        _log.info("SOF_AUTO_MATERIALIZE disabled; skipping warehouse build")
        return None

    patient_limit_raw = os.getenv("SOF_PATIENT_LIMIT")
    try:
        patient_limit = (
            int(patient_limit_raw) if patient_limit_raw else _DEFAULT_LIMIT
        )
    except ValueError:
        patient_limit = _DEFAULT_LIMIT

    db_path = Path(os.getenv("SOF_DB_PATH") or _DEFAULT_DB_PATH)
    fhir_dir = Path(os.getenv("SOF_FHIR_DIR") or _DEFAULT_FHIR_DIR)

    try:
        report = materialize_if_stale(
            db_path=db_path,
            fhir_dir=fhir_dir,
            patient_limit=patient_limit,
        )
    except Exception as exc:  # noqa: BLE001 — startup must never crash
        _log.warning("sof materialize failed: %s", exc, exc_info=False)
        return None

    if report.built:
        total_rows = sum(report.row_counts.values())
        _log.info(
            "sof warehouse built: %s rows across %s tables in %.2fs (%s)",
            total_rows,
            len(report.row_counts),
            report.duration_s,
            report.db_path,
        )
    else:
        _log.info("sof warehouse fresh (%s) at %s", report.reason, report.db_path)
    return report
