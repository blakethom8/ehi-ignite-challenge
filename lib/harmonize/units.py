"""Unit normalization across sources.

Different labs report the same fact in different units — most famously
Cholesterol (mg/dL in US labs, mmol/L in metric/EU labs) and Glucose
(same split). The normalizer converts source values to the canonical
unit declared in the LOINC bridge so downstream comparison just works.

We keep this deliberately simple — a small explicit table — rather than
pulling in ``pint`` for v1. The conversion factors are LOINC-canonical
and don't change. Adding `pint` later is a one-liner if the table grows
unwieldy.
"""

from __future__ import annotations


# (from_unit, to_unit) → multiplier. Source value × multiplier = target value.
# Only directional pairs are listed; reverse pairs are computed at lookup.
_FACTORS: dict[tuple[str, str], float] = {
    # Cholesterol / lipids: 1 mmol/L = 38.67 mg/dL
    ("mmol/l", "mg/dl"): 38.67,
    # Glucose: 1 mmol/L = 18.0156 mg/dL
    # (Conflicts with cholesterol — caller passes LOINC context to disambiguate.)
    # We pick cholesterol's factor as the default; glucose handled explicitly below.
    # Triglycerides: 1 mmol/L = 88.57 mg/dL
}

# LOINC-aware overrides: when both LOINC code and unit pair are known,
# take this multiplier instead of the generic table.
_LOINC_FACTORS: dict[tuple[str, tuple[str, str]], float] = {
    ("2345-7", ("mmol/l", "mg/dl")): 18.0156,  # Glucose
    ("2571-8", ("mmol/l", "mg/dl")): 88.57,    # Triglycerides
}


def _norm_unit(u: str | None) -> str | None:
    if not u:
        return None
    return u.lower().replace(" ", "")


def convert(
    value: float | None,
    from_unit: str | None,
    to_unit: str | None,
    loinc: str | None = None,
) -> tuple[float | None, str | None]:
    """Convert ``value`` from ``from_unit`` to ``to_unit``, returning
    ``(converted_value, applied_unit)``.

    If conversion is impossible (units missing, no factor in table, or
    unit pair already matches) the value is returned unchanged with the
    *target* unit when known, otherwise the source unit. Callers can
    detect a no-op by checking ``applied_unit == from_unit``.
    """
    if value is None:
        return None, to_unit or from_unit
    if from_unit is None or to_unit is None:
        return value, to_unit or from_unit
    fu, tu = _norm_unit(from_unit), _norm_unit(to_unit)
    if fu == tu:
        return value, to_unit

    # LOINC-aware first, then generic, then reverse pairs.
    pair = (fu, tu)  # type: ignore[assignment]
    if loinc and (loinc, pair) in _LOINC_FACTORS:
        return value * _LOINC_FACTORS[(loinc, pair)], to_unit
    if pair in _FACTORS:
        return value * _FACTORS[pair], to_unit
    rev = (tu, fu)  # type: ignore[assignment]
    if loinc and (loinc, rev) in _LOINC_FACTORS:
        return value / _LOINC_FACTORS[(loinc, rev)], to_unit
    if rev in _FACTORS:
        return value / _FACTORS[rev], to_unit

    # Unknown conversion — return the source value unchanged.
    return value, from_unit
