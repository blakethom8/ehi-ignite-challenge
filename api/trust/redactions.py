"""De-identification presets.

Each preset takes a *raw* patient slice and produces a redacted slice
suitable for handing to a plugin. The presets are deliberately simple
in v1 — they are enforced at compile-time, not learned. Adding a new
preset = new entry here + manifest validator already accepts the
literal.

Preset semantics:

  ``de-id-v1``       — strip direct identifiers (name, MRN, DOB, address)
  ``de-id-v2``       — de-id-v1 + bucket ages into 5-year bands
  ``de-id-v3``       — de-id-v2 + truncate geography to first 3 ZIP digits
  ``research-grade`` — de-id-v3 + drop free-text notes
  ``minimal``        — passthrough (identifiers preserved; required for PAP/PA)
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

PRESETS: dict[str, Callable[[dict], dict]] = {}


def register(name: str) -> Callable[[Callable[[dict], dict]], Callable[[dict], dict]]:
    def _decorator(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        PRESETS[name] = fn
        return fn

    return _decorator


_DIRECT_IDENTIFIERS = {
    "name",
    "first_name",
    "last_name",
    "mrn",
    "ssn",
    "dob",
    "date_of_birth",
    "address",
    "phone",
    "email",
    "patient_name",
}


def _strip_keys(d: Any, keys: set[str]) -> Any:
    if isinstance(d, dict):
        return {k: _strip_keys(v, keys) for k, v in d.items() if k not in keys}
    if isinstance(d, list):
        return [_strip_keys(v, keys) for v in d]
    return d


def _age_band(age: int) -> str:
    lo = (age // 5) * 5
    return f"{lo}-{lo + 4}"


def _zip3(z: str) -> str:
    digits = "".join(ch for ch in z if ch.isdigit())
    return (digits[:3] + "**") if digits else "***"


@register("de-id-v1")
def _v1(slice_: dict) -> dict:
    return _strip_keys(deepcopy(slice_), _DIRECT_IDENTIFIERS)


@register("de-id-v2")
def _v2(slice_: dict) -> dict:
    out = _v1(slice_)
    # Replace age with age band on demographics if present.
    demo = out.get("demographics") or {}
    if isinstance(demo, dict) and "age" in demo:
        try:
            demo["age-band"] = _age_band(int(demo["age"]))
        except (TypeError, ValueError):
            demo["age-band"] = "unknown"
        del demo["age"]
        out["demographics"] = demo
    # The slice may also project age-band directly as a scope-keyed value.
    return out


@register("de-id-v3")
def _v3(slice_: dict) -> dict:
    out = _v2(slice_)
    demo = out.get("demographics") or {}
    if isinstance(demo, dict):
        if "zip" in demo:
            demo["zip3"] = _zip3(str(demo["zip"]))
            del demo["zip"]
        if "geography" in demo and isinstance(demo["geography"], dict):
            geo = demo["geography"]
            if "zip" in geo:
                geo["zip3"] = _zip3(str(geo["zip"]))
                del geo["zip"]
            for k in ("address", "city", "street"):
                geo.pop(k, None)
        out["demographics"] = demo
    return out


@register("research-grade")
def _research(slice_: dict) -> dict:
    out = _v3(slice_)
    # Drop free-text notes anywhere they live.
    return _strip_keys(out, {"note", "notes", "text", "narrative"})


@register("minimal")
def _minimal(slice_: dict) -> dict:
    # Passthrough — used where the receiving system requires identifiers
    # (PAP enrollment, PA submission). The consent gate is the audit.
    return deepcopy(slice_)


def apply_preset(name: str, slice_: dict) -> dict:
    if name not in PRESETS:
        raise ValueError(f"unknown redaction preset: {name}")
    return PRESETS[name](slice_)
