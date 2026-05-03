"""SQL-on-FHIR demo.

Loads a configurable number of Synthea bundles, runs every ViewDefinition in
`views/` against them, writes the result into a SQLite database, and prints a
handful of clinically meaningful queries to demonstrate what the layer buys us.

Run from the repo root:

    python patient-journey/core/sql_on_fhir/demo.py --limit 25
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make the sibling modules importable whether run as a script or a module.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import loader  # type: ignore  # noqa: E402
from sqlite_sink import materialize, open_db  # type: ignore  # noqa: E402
from view_definition import ViewDefinition  # type: ignore  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE_DIR = REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"
VIEWS_DIR = _THIS_DIR / "views"


DEMO_QUERIES: list[tuple[str, str]] = [
    (
        "Corpus sizes after materialization",
        """
        SELECT
          (SELECT COUNT(*) FROM patient)             AS patients,
          (SELECT COUNT(*) FROM condition)           AS conditions,
          (SELECT COUNT(*) FROM medication_request)  AS med_requests,
          (SELECT COUNT(*) FROM observation)         AS observations,
          (SELECT COUNT(*) FROM encounter)           AS encounters
        """,
    ),
    (
        "Top 10 most common SNOMED conditions",
        """
        SELECT code_display, COUNT(*) AS n
        FROM condition
        WHERE code_system = 'http://snomed.info/sct'
        GROUP BY code_display
        ORDER BY n DESC
        LIMIT 10
        """,
    ),
    (
        "Top 10 most prescribed RxNorm medications",
        """
        SELECT rxnorm_display, COUNT(*) AS n
        FROM medication_request
        GROUP BY rxnorm_display
        ORDER BY n DESC
        LIMIT 10
        """,
    ),
    (
        "Patients on Ibuprofen / Aspirin / Naproxen / Warfarin (any status)",
        """
        SELECT p.given_name || ' ' || p.family_name AS name,
               m.rxnorm_display, m.status
        FROM medication_request m
        JOIN patient p ON m.patient_ref = 'urn:uuid:' || p.id
        WHERE m.rxnorm_display LIKE '%Ibuprofen%'
           OR m.rxnorm_display LIKE '%Aspirin%'
           OR m.rxnorm_display LIKE '%Naproxen%'
           OR m.rxnorm_display LIKE '%Warfarin%'
        LIMIT 10
        """,
    ),
    (
        "Average BMI per patient (LOINC 39156-5), at least 2 readings",
        """
        SELECT p.given_name || ' ' || p.family_name AS name,
               ROUND(AVG(o.value_quantity), 1) AS avg_bmi,
               COUNT(*) AS n_readings
        FROM observation o
        JOIN patient p ON o.patient_ref = 'urn:uuid:' || p.id
        WHERE o.loinc_code = '39156-5'
        GROUP BY p.id
        HAVING n_readings >= 2
        ORDER BY avg_bmi DESC
        LIMIT 10
        """,
    ),
    (
        "Patients with an active condition AND a currently-active medication",
        """
        SELECT DISTINCT p.given_name || ' ' || p.family_name AS name,
               c.code_display AS condition,
               m.rxnorm_display AS medication
        FROM patient p
        JOIN condition c
          ON c.patient_ref = 'urn:uuid:' || p.id AND c.clinical_status = 'active'
        JOIN medication_request m
          ON m.patient_ref = 'urn:uuid:' || p.id AND m.status = 'active'
        LIMIT 10
        """,
    ),
]


def load_views() -> list[ViewDefinition]:
    return [ViewDefinition.from_json_file(p) for p in sorted(VIEWS_DIR.glob("*.json"))]


def run(limit: int, bundle_dir: Path, db_path: Path) -> None:
    print(f"Loading up to {limit} bundles from {bundle_dir}")
    print(f"Writing SQLite database to {db_path}\n")

    views = load_views()
    print(f"Loaded {len(views)} ViewDefinitions: {[v.name for v in views]}\n")

    conn = open_db(db_path)
    try:
        for view in views:
            start = time.perf_counter()
            resources = loader.iter_all_resources(bundle_dir, limit=limit)
            n = materialize(view, resources, conn)
            elapsed = time.perf_counter() - start
            print(f"  materialized {view.name:<20} {n:>8} rows  ({elapsed:5.2f}s)")

        print("\n" + "=" * 72)
        print("Demo queries")
        print("=" * 72)

        for label, sql in DEMO_QUERIES:
            print(f"\n# {label}")
            print(_format_sql(sql))
            try:
                cursor = conn.execute(sql)
                rows = cursor.fetchall()
                cols = [d[0] for d in cursor.description]
            except Exception as exc:  # pragma: no cover
                print(f"  ERROR: {exc}")
                continue
            if not rows:
                print("  (no rows)")
                continue
            _print_table(cols, rows)
    finally:
        conn.close()


def _format_sql(sql: str) -> str:
    lines = [line.strip() for line in sql.strip().splitlines() if line.strip()]
    return "  " + "\n  ".join(lines)


def _print_table(cols: list[str], rows: list[tuple]) -> None:
    str_rows = [[str(v) if v is not None else "" for v in row] for row in rows]
    widths = [max(len(c), *(len(r[i]) for r in str_rows)) for i, c in enumerate(cols)]
    header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    sep = "-+-".join("-" * w for w in widths)
    print("  " + header)
    print("  " + sep)
    for r in str_rows:
        print("  " + " | ".join(r[i].ljust(widths[i]) for i in range(len(cols))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25, help="max bundles to load")
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument(
        "--db",
        type=Path,
        default=REPO_ROOT / "data" / "sof_demo.db",
        help="output SQLite path",
    )
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    if args.db.exists():
        args.db.unlink()
    run(limit=args.limit, bundle_dir=args.bundle_dir, db_path=args.db)


if __name__ == "__main__":
    main()
