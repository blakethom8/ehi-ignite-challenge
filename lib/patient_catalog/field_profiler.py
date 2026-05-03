"""
Field presence analysis across a list of FHIR resources.

Recursively flattens FHIR resource dicts into dot-notation paths
and computes presence percentages — answers "what fields can we
rely on vs. what's optional?"
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class FieldPresence:
    field_path: str
    present_count: int
    total_count: int
    presence_pct: float
    sample_values: list[str] = field(default_factory=list)

    @property
    def tier(self) -> str:
        if self.presence_pct == 100.0:
            return "always"
        elif self.presence_pct >= 80.0:
            return "usually"
        elif self.presence_pct >= 20.0:
            return "sometimes"
        else:
            return "rarely"


@dataclass
class FieldProfile:
    resource_type: str
    sample_size: int
    fields: list[FieldPresence]

    @property
    def always_present(self) -> list[FieldPresence]:
        return [f for f in self.fields if f.tier == "always"]

    @property
    def usually_present(self) -> list[FieldPresence]:
        return [f for f in self.fields if f.tier == "usually"]

    @property
    def sometimes_present(self) -> list[FieldPresence]:
        return [f for f in self.fields if f.tier == "sometimes"]

    @property
    def rarely_present(self) -> list[FieldPresence]:
        return [f for f in self.fields if f.tier == "rarely"]


def profile_resources(
    resources: list[dict],
    resource_type: str = "",
    max_depth: int = 4,
    max_samples: int = 5,
) -> FieldProfile:
    """
    Profile field presence across a list of raw FHIR resource dicts.

    Args:
        resources: List of raw resource dicts (same type).
        resource_type: Label for the profile (e.g. "Condition").
        max_depth: How deep to recurse into nested objects.
        max_samples: Max distinct sample values to collect per field.

    Returns:
        FieldProfile with presence percentages for every field path.
    """
    n = len(resources)
    if n == 0:
        return FieldProfile(resource_type=resource_type, sample_size=0, fields=[])

    # path -> set of doc indices where it's present
    path_presence: dict[str, set[int]] = defaultdict(set)
    # path -> list of sample string values
    path_samples: dict[str, list[str]] = defaultdict(list)

    for idx, resource in enumerate(resources):
        _walk(resource, "", idx, path_presence, path_samples, max_depth, max_samples)

    fields = []
    for path, doc_set in sorted(path_presence.items()):
        count = len(doc_set)
        pct = (count / n) * 100.0
        samples = path_samples.get(path, [])
        fields.append(FieldPresence(
            field_path=path,
            present_count=count,
            total_count=n,
            presence_pct=round(pct, 1),
            sample_values=samples[:max_samples],
        ))

    # Sort by presence desc, then alphabetically
    fields.sort(key=lambda f: (-f.presence_pct, f.field_path))

    return FieldProfile(
        resource_type=resource_type,
        sample_size=n,
        fields=fields,
    )


def _walk(
    obj: object,
    prefix: str,
    doc_idx: int,
    presence: dict[str, set[int]],
    samples: dict[str, list[str]],
    max_depth: int,
    max_samples: int,
    depth: int = 0,
) -> None:
    """Recursively walk a nested dict/list, recording field paths."""
    if depth > max_depth:
        return

    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            presence[path].add(doc_idx)

            # Collect a sample string representation of leaf values
            if isinstance(value, (str, int, float, bool)) and len(samples[path]) < max_samples:
                str_val = str(value)
                if str_val not in samples[path]:
                    samples[path].append(str_val)

            _walk(value, path, doc_idx, presence, samples, max_depth, max_samples, depth + 1)

    elif isinstance(obj, list) and obj:
        # Represent all list items under a single [*] path
        list_path = f"{prefix}[*]"
        presence[list_path].add(doc_idx)
        for item in obj:
            _walk(item, list_path, doc_idx, presence, samples, max_depth, max_samples, depth + 1)
