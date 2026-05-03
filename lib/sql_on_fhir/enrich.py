"""Row-level enrichment hooks for the SQL-on-FHIR materializer.

The pure ViewDefinition runtime can only surface fields that are
reachable via FHIRPath-lite. Anything derived — drug classes, episodes,
severity scores — has to be computed in Python and spliced into the
row before it hits the SQLite sink. That's what this module is for.

An ``Enrichment`` binds three things together:

1. ``view_name`` — the ViewDefinition name to attach to (e.g.
   ``medication_request``).
2. ``columns`` — the extra ``Column`` entries to append to the
   declared schema. The sink uses these to extend the ``CREATE TABLE``
   statement and the INSERT column list.
3. ``enrich_row`` — a callable that mutates a row dict in place,
   populating the enrichment columns. It sees the row after the
   FHIRPath runtime has already written every declared column.

The default registry exposes ``medication_request`` →
``drug_class``, backed by the same ``data/drug_classes.json`` mapping
used by ``patient-journey/core/drug_classifier.py``. Keeping both
paths on the same mapping file means the surgical safety panel and
the SQL warehouse never disagree about what counts as, say, an
anticoagulant.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

try:
    from .view_definition import Column
except ImportError:  # running as a loose script
    from view_definition import Column  # type: ignore


RowEnricher = Callable[[dict], None]


@dataclass
class Enrichment:
    """Extra columns + a row-mutator for a single ViewDefinition."""

    view_name: str
    columns: list[Column]
    enrich_row: RowEnricher

    def apply(self, row: dict) -> None:
        """Mutate ``row`` in place to add every enrichment column."""
        self.enrich_row(row)
        # Guarantee every declared column exists in the row so the sink
        # can read them positionally without a KeyError. A missing
        # classification becomes NULL in SQLite.
        for col in self.columns:
            row.setdefault(col.name, None)


# ---------------------------------------------------------------------------
# Drug classifier (medication_request)
# ---------------------------------------------------------------------------


DrugClassClassifier = Callable[[Optional[str], Optional[str]], Optional[str]]


def _default_drug_classes_path() -> Path:
    """Return the canonical drug_classes.json path.

    Shared with ``lib.clinical.drug_classifier`` so the warehouse-build
    enrichment and the in-memory classifier read from the same mapping
    file.
    """
    return Path(__file__).resolve().parents[1] / "clinical" / "drug_classes.json"


def load_drug_classifier(
    mapping_path: Path | None = None,
) -> DrugClassClassifier:
    """Return a ``classify(rxnorm_code, display) -> class_key | None`` fn.

    The returned function is pure and safe to call from any thread.
    Resolution precedence: **RxNorm code** first, **keyword match**
    against the display/medication_text string second. First class key
    that matches wins — multi-match is not exposed here; the SQL
    warehouse stores a single canonical drug class per row so cohort
    queries can ``GROUP BY drug_class`` without double-counting.
    """
    path = Path(mapping_path) if mapping_path else _default_drug_classes_path()
    if not path.exists():
        # Degrade gracefully: never raise at warehouse-build time.
        def _noop(_rx: str | None, _disp: str | None) -> str | None:
            return None

        return _noop

    with open(path) as f:
        raw = json.load(f)

    # Pre-compile the mapping into a list of tuples so the hot path is
    # a trivial Python loop and never re-parses JSON per row.
    entries: list[tuple[str, list[str], set[str]]] = []
    for key, data in raw.items():
        keywords = [kw.lower() for kw in data.get("keywords", [])]
        rxnorm_codes = {str(c) for c in data.get("rxnorm_codes", [])}
        entries.append((key, keywords, rxnorm_codes))

    def classify(
        rxnorm_code: str | None, display: str | None
    ) -> str | None:
        # 1) Exact RxNorm match
        if rxnorm_code:
            rx = str(rxnorm_code)
            for key, _kws, rx_set in entries:
                if rx in rx_set:
                    return key
        # 2) Case-insensitive keyword match on display / medication text
        if display:
            lowered = display.lower()
            for key, kws, _rx_set in entries:
                for kw in kws:
                    if kw and kw in lowered:
                        return key
        return None

    return classify


def medication_request_enrichment(
    mapping_path: Path | None = None,
) -> Enrichment:
    """Build the default ``medication_request`` enrichment.

    Adds a single ``drug_class`` TEXT column populated from the shared
    drug_classes.json mapping.
    """
    classify = load_drug_classifier(mapping_path)

    def _enrich(row: dict) -> None:
        row["drug_class"] = classify(
            row.get("rxnorm_code"),
            row.get("medication_text") or row.get("rxnorm_display"),
        )

    return Enrichment(
        view_name="medication_request",
        columns=[
            Column(
                name="drug_class",
                path="<enriched>",
                type="string",
                description="Canonical drug class key (anticoagulants, antiplatelets, …) derived from RxNorm and display text at ingest time.",
            )
        ],
        enrich_row=_enrich,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def default_enrichments() -> dict[str, Enrichment]:
    """Return the default view_name → Enrichment registry.

    Callers that want a pure (no enrichment) build can pass
    ``enrichments={}`` to the sink instead.
    """
    return {
        "medication_request": medication_request_enrichment(),
    }


def enrichment_columns(
    view_name: str, enrichments: dict[str, Enrichment] | None
) -> list[Column]:
    """Convenience accessor — extra columns for one view, or ``[]``."""
    if not enrichments:
        return []
    spec = enrichments.get(view_name)
    return list(spec.columns) if spec else []
