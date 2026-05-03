"""ViewDefinition runner.

Given a ViewDefinition and an iterable of FHIR resources, yields flattened
row dicts. Implements the semantics described in the SQL-on-FHIR v2 spec:

- `where` at the view level filters which resources are included
- `select[]` clauses are combined: each clause's rows are joined against its
  siblings via a cross-product (per the spec, sibling selects produce one row
  together — this is how `forEach` nested selects multiply the row count)
- `forEach` unnests a collection: the row repeats once per element, with the
  child select clause evaluated with `$this` = element
- `forEachOrNull` does the same but preserves a single null row if the
  collection is empty
- `unionAll` is the reverse: each child clause contributes independent rows
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

try:
    from .fhirpath import evaluate
    from .view_definition import Column, SelectClause, ViewDefinition
except ImportError:  # running as a loose script
    from fhirpath import evaluate  # type: ignore
    from view_definition import Column, SelectClause, ViewDefinition  # type: ignore


def _passes_where(resource: dict, where: list[str]) -> bool:
    for expr in where:
        result = evaluate(expr, resource)
        if not result or not all(bool(x) for x in result):
            return False
    return True


def _coerce(value, type_hint: str):
    """Coerce a FHIRPath result (which is always a collection) into the SQL
    column value. Most columns are singletons — we unwrap to the first element.
    Known 'collection' columns keep the list."""
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        if len(value) == 1:
            value = value[0]
        else:
            # Multiple values for a non-collection column — join for readability
            return ", ".join(str(v) for v in value)
    if type_hint in ("integer", "positiveInt", "unsignedInt") and value is not None:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    if type_hint == "decimal" and value is not None:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    if type_hint == "boolean":
        return bool(value)
    return value


def _eval_columns(columns: list[Column], focus: Any) -> dict:
    row: dict = {}
    for col in columns:
        raw = evaluate(col.path, focus)
        if col.collection:
            row[col.name] = raw if raw else None
        else:
            row[col.name] = _coerce(raw, col.type)
    return row


def _eval_select(clause: SelectClause, focus: Any) -> list[dict]:
    """Evaluate a single select clause against a focus, returning a list of
    row fragments.

    Semantics:
    - `forEach` iterates a collection; an empty collection yields zero rows
    - `forEachOrNull` iterates a collection; an empty collection yields one
      row with all nested columns set to null
    - Nested `select[]` are cross-joined with the parent's columns. If any
      nested rowset is empty, the cross-product (and therefore the parent
      row) produces zero rows.
    - `unionAll[]` branches each contribute their own rows, concatenated;
      the parent's own columns are then cross-joined over the concatenated
      set (so each union row inherits the parent's column values).
    """
    targets: list[Any]
    if clause.for_each is not None:
        targets = evaluate(clause.for_each, focus)
        if not targets:
            return []
    elif clause.for_each_or_null is not None:
        targets = evaluate(clause.for_each_or_null, focus)
        if not targets:
            targets = [None]
    else:
        targets = [focus]

    out: list[dict] = []
    for t in targets:
        base = _eval_columns(clause.columns, t) if clause.columns else {}

        # Nested select[] children and unionAll branches both produce rowsets
        # that cross-join with `base`. unionAll branches are concatenated
        # together first, then treated as a single rowset for cross-product.
        rowsets: list[list[dict]] = []
        for child in clause.selects:
            rowsets.append(_eval_select(child, t))
        if clause.union_all:
            union_rows: list[dict] = []
            for branch in clause.union_all:
                union_rows.extend(_eval_select(branch, t))
            rowsets.append(union_rows)

        if not rowsets:
            out.append(base)
            continue

        # Cross-product — if any rowset is empty, the entire parent row is
        # eliminated (matches SQL semantics of joining on an empty child).
        combos: list[dict] = [base]
        for rows in rowsets:
            if not rows:
                combos = []
                break
            new_combos: list[dict] = []
            for combo in combos:
                for r in rows:
                    merged = dict(combo)
                    merged.update(r)
                    new_combos.append(merged)
            combos = new_combos
        out.extend(combos)

    return out


def run_view(view: ViewDefinition, resources: Iterable[dict]) -> Iterator[dict]:
    """Yield flattened rows produced by applying the view to each matching
    resource in the iterable."""
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("resourceType") != view.resource:
            continue
        if not _passes_where(resource, view.where):
            continue

        # Each top-level select clause contributes rows; they are cross-joined
        # together (same semantics as nested sibling selects).
        rowsets: list[list[dict]] = []
        for clause in view.selects:
            rows = _eval_select(clause, resource)
            if rows:
                rowsets.append(rows)

        if not rowsets:
            continue

        combos: list[dict] = [{}]
        for rows in rowsets:
            new_combos: list[dict] = []
            for combo in combos:
                for r in rows:
                    merged = dict(combo)
                    merged.update(r)
                    new_combos.append(merged)
            combos = new_combos

        for row in combos:
            yield row
