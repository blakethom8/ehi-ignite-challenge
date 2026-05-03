"""Head-to-head benchmark: SQL-on-FHIR vs the existing Python parser.

Answers the practical question: "Does the SQL-on-FHIR layer pay for itself?"

We measure three things for each approach against the same Synthea bundles:

1. **Ingest time** — time to turn raw FHIR JSON into a query-ready form
   (PatientRecord objects vs. SQLite tables).
2. **Query time** — time to answer five realistic clinical/analytical
   questions once data is loaded.
3. **Code surface** — lines of code required to express each query.

Output is a markdown-friendly summary written to stdout (and optionally to a
file with `--out`).

Run:

    python patient-journey/core/sql_on_fhir/benchmark.py --limit 50
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import loader as sof_loader  # type: ignore  # noqa: E402
from sqlite_sink import materialize, materialize_all, open_db  # type: ignore  # noqa: E402
from view_definition import ViewDefinition  # type: ignore  # noqa: E402

# Prior approach
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from lib.fhir_parser.bundle_parser import parse_bundle  # type: ignore  # noqa: E402

DEFAULT_BUNDLE_DIR = REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"
VIEWS_DIR = _THIS_DIR / "views"


# ---------------------------------------------------------------------------
# Queries — each pair must return the same semantic answer
# ---------------------------------------------------------------------------


def q1_python_top_conditions(records):
    """Top-10 most common conditions across the corpus (Python approach)."""
    from collections import Counter
    counter: Counter = Counter()
    for r in records:
        for c in r.conditions:
            display = c.code.display if c.code else None
            if display:
                counter[display] += 1
    return counter.most_common(10)


def q1_sql_top_conditions(conn):
    return conn.execute(
        """
        SELECT code_display, COUNT(*) AS n
        FROM condition
        WHERE code_system = 'http://snomed.info/sct'
        GROUP BY code_display
        ORDER BY n DESC
        LIMIT 10
        """
    ).fetchall()


def q2_python_top_meds(records):
    from collections import Counter
    counter: Counter = Counter()
    for r in records:
        for m in r.medications:
            if m.display:
                counter[m.display] += 1
    return counter.most_common(10)


def q2_sql_top_meds(conn):
    return conn.execute(
        """
        SELECT rxnorm_display, COUNT(*) AS n
        FROM medication_request
        GROUP BY rxnorm_display
        ORDER BY n DESC
        LIMIT 10
        """
    ).fetchall()


def q3_python_nsaid_patients(records):
    """Patients prescribed Ibuprofen/Naproxen/Aspirin/Warfarin (any status)."""
    keywords = ("Ibuprofen", "Naproxen", "Aspirin", "Warfarin")
    out = []
    for r in records:
        for m in r.medications:
            if m.display and any(k in m.display for k in keywords):
                out.append((r.summary.name, m.display, m.status))
    return out


def q3_sql_nsaid_patients(conn):
    return conn.execute(
        """
        SELECT p.given_name || ' ' || p.family_name AS name,
               m.rxnorm_display, m.status
        FROM medication_request m
        JOIN patient p ON m.patient_ref = 'urn:uuid:' || p.id
        WHERE m.rxnorm_display LIKE '%Ibuprofen%'
           OR m.rxnorm_display LIKE '%Naproxen%'
           OR m.rxnorm_display LIKE '%Aspirin%'
           OR m.rxnorm_display LIKE '%Warfarin%'
        """
    ).fetchall()


def q4_python_active_cond_active_med(records):
    """Patients with at least one active condition and one active medication."""
    out = []
    for r in records:
        active_conds = [c for c in r.conditions if (c.clinical_status or "").lower() == "active"]
        active_meds = [m for m in r.medications if (m.status or "").lower() == "active"]
        if active_conds and active_meds:
            for c in active_conds:
                for m in active_meds:
                    cd = c.code.display if c.code else None
                    out.append((r.summary.name, cd, m.display))
    return out


def q4_sql_active_cond_active_med(conn):
    return conn.execute(
        """
        SELECT p.given_name || ' ' || p.family_name AS name,
               c.code_display, m.rxnorm_display
        FROM patient p
        JOIN condition c
          ON c.patient_ref = 'urn:uuid:' || p.id AND c.clinical_status = 'active'
        JOIN medication_request m
          ON m.patient_ref = 'urn:uuid:' || p.id AND m.status = 'active'
        """
    ).fetchall()


def q5_python_avg_bmi(records):
    """Avg BMI per patient (LOINC 39156-5), at least 2 readings."""
    out = []
    for r in records:
        values = [
            o.value_quantity
            for o in r.observations
            if o.loinc_code == "39156-5" and o.value_quantity is not None
        ]
        if len(values) >= 2:
            out.append((r.summary.name, round(sum(values) / len(values), 1), len(values)))
    out.sort(key=lambda x: -x[1])
    return out[:10]


def q5_sql_avg_bmi(conn):
    return conn.execute(
        """
        SELECT p.given_name || ' ' || p.family_name AS name,
               ROUND(AVG(o.value_quantity), 1) AS avg_bmi,
               COUNT(*) AS n
        FROM observation o
        JOIN patient p ON o.patient_ref = 'urn:uuid:' || p.id
        WHERE o.loinc_code = '39156-5'
        GROUP BY p.id
        HAVING n >= 2
        ORDER BY avg_bmi DESC
        LIMIT 10
        """
    ).fetchall()


QUERIES = [
    ("Top 10 SNOMED conditions", q1_python_top_conditions, q1_sql_top_conditions),
    ("Top 10 RxNorm medications", q2_python_top_meds, q2_sql_top_meds),
    ("Patients on NSAID/anticoagulant", q3_python_nsaid_patients, q3_sql_nsaid_patients),
    ("Active condition × active medication", q4_python_active_cond_active_med, q4_sql_active_cond_active_med),
    ("Avg BMI ≥ 2 readings", q5_python_avg_bmi, q5_sql_avg_bmi),
]


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


def _median(times: list[float]) -> float:
    return statistics.median(times) * 1000.0  # ms


def _time(fn, *args, repeats: int = 3) -> tuple[float, object]:
    times = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn(*args)
        # Materialize generator results if needed
        if hasattr(result, "__iter__") and not isinstance(result, (list, tuple, dict, str)):
            result = list(result)
        times.append(time.perf_counter() - start)
    return _median(times), result


def _load_python(bundle_dir: Path, limit: int) -> tuple[float, list]:
    start = time.perf_counter()
    records = []
    for path in sorted(bundle_dir.glob("*.json"))[:limit]:
        records.append(parse_bundle(path))
    return time.perf_counter() - start, records


def _load_sql(bundle_dir: Path, limit: int, db_path: Path) -> tuple[float, "sqlite3.Connection"]:
    if db_path.exists():
        db_path.unlink()
    conn = open_db(db_path)
    views = [ViewDefinition.from_json_file(p) for p in sorted(VIEWS_DIR.glob("*.json"))]
    start = time.perf_counter()
    resources = sof_loader.iter_all_resources(bundle_dir, limit=limit)
    materialize_all(views, resources, conn)
    return time.perf_counter() - start, conn


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(limit: int, bundle_dir: Path) -> str:
    buf = io.StringIO()
    def p(*args, **kwargs):
        print(*args, **kwargs, file=buf)

    p(f"# SQL-on-FHIR vs Python Parser — Benchmark (n={limit} bundles)\n")

    # --- Ingest ---
    py_ingest, py_records = _load_python(bundle_dir, limit)
    sql_ingest, conn = _load_sql(bundle_dir, limit, REPO_ROOT / "data" / "sof_bench.db")

    p("## Ingest (parse bundles → query-ready form)\n")
    p("| Approach       | Time (s) | Loaded                       |")
    p("|----------------|---------:|------------------------------|")
    p(f"| Python parser  | {py_ingest:7.2f}  | {len(py_records)} PatientRecord objects |")
    # Collect SQL counts
    sql_counts = {}
    for table in ("patient", "condition", "medication_request", "observation", "encounter"):
        sql_counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    sql_desc = ", ".join(f"{k}={v}" for k, v in sql_counts.items())
    p(f"| SQL-on-FHIR    | {sql_ingest:7.2f}  | SQLite rows: {sql_desc} |")
    p()

    # --- Queries ---
    p("## Query latency (median of 3 runs, ms)\n")
    p("| Query                                | Python (ms) | SQL (ms) | Δ (×)  | Same answer? |")
    p("|--------------------------------------|------------:|---------:|-------:|-------------:|")
    totals_py, totals_sql = 0.0, 0.0
    for label, py_fn, sql_fn in QUERIES:
        py_ms, py_res = _time(py_fn, py_records)
        sql_ms, sql_res = _time(sql_fn, conn)
        ratio = (py_ms / sql_ms) if sql_ms > 0 else float("inf")
        totals_py += py_ms
        totals_sql += sql_ms

        # Normalize answers for comparison
        same = _same_answers(py_res, sql_res)
        flag = "✓" if same else "≈" if _close_answers(py_res, sql_res) else "✗"
        p(f"| {label:<36} | {py_ms:11.2f} | {sql_ms:8.2f} | {ratio:5.1f}× | {flag:^12} |")
    p(f"| **Total**                            | {totals_py:11.2f} | {totals_sql:8.2f} | {(totals_py/totals_sql if totals_sql else 0):5.1f}× |              |")
    p()

    # --- Code surface ---
    p("## Query code surface (lines of non-trivial logic)\n")
    p("| Query                                | Python LOC | SQL LOC |")
    p("|--------------------------------------|-----------:|--------:|")
    py_src = Path(__file__).read_text()
    for label, py_fn, sql_fn in QUERIES:
        py_lines = _count_fn_lines(py_src, py_fn.__name__)
        sql_lines = _count_fn_sql_lines(py_src, sql_fn.__name__)
        p(f"| {label:<36} | {py_lines:10} | {sql_lines:7} |")
    p()

    conn.close()
    return buf.getvalue()


def _same_answers(py_res, sql_res) -> bool:
    try:
        py_norm = sorted(tuple(x) for x in py_res)
        sql_norm = sorted(tuple(x) for x in sql_res)
        return py_norm == sql_norm
    except Exception:
        return False


def _close_answers(py_res, sql_res) -> bool:
    try:
        return len(list(py_res)) == len(list(sql_res))
    except Exception:
        return False


def _count_fn_lines(src: str, name: str) -> int:
    """Count non-empty, non-comment lines in the body of a Python function."""
    lines = src.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {name}("):
            start = i + 1
            break
    if start is None:
        return 0
    count = 0
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if not line.startswith((" ", "\t")):  # dedented → function ended
            break
        count += 1
    return count


def _count_fn_sql_lines(src: str, name: str) -> int:
    """For the SQL-variant functions, count the SQL statement lines only
    (strips boilerplate like conn.execute() and return)."""
    lines = src.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {name}("):
            start = i + 1
            break
    if start is None:
        return 0
    in_sql = False
    count = 0
    for line in lines[start:]:
        stripped = line.strip()
        if not line.startswith((" ", "\t")) and stripped:  # dedent
            break
        if '"""' in stripped:
            in_sql = not in_sql
            continue
        if in_sql and stripped:
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--out", type=Path, default=None, help="write report to this file")
    args = parser.parse_args()
    report = run(args.limit, args.bundle_dir)
    print(report)
    if args.out:
        args.out.write_text(report)
        print(f"[wrote report to {args.out}]", file=sys.stderr)


if __name__ == "__main__":
    main()
