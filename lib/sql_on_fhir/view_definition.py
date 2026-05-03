"""ViewDefinition dataclass model — the subset of the SQL-on-FHIR v2 spec
we actually use. Loaded from JSON matching the canonical structure:

    {
      "resource": "Patient",
      "status": "active",
      "select": [
        {
          "column": [{"name": "id", "path": "id", "type": "id"}],
          "where": [],
          "forEach": "name",
          "select": [...],
          "unionAll": [...]
        }
      ],
      "where": [{"path": "active = true"}]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Column:
    name: str
    path: str
    type: str = "string"
    collection: bool = False
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Column":
        return cls(
            name=data["name"],
            path=data.get("path", data["name"]),
            type=data.get("type", "string"),
            collection=data.get("collection", False),
            description=data.get("description", ""),
        )


@dataclass
class SelectClause:
    columns: List[Column] = field(default_factory=list)
    for_each: Optional[str] = None
    for_each_or_null: Optional[str] = None
    selects: List["SelectClause"] = field(default_factory=list)
    union_all: List["SelectClause"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "SelectClause":
        return cls(
            columns=[Column.from_dict(c) for c in data.get("column", [])],
            for_each=data.get("forEach"),
            for_each_or_null=data.get("forEachOrNull"),
            selects=[cls.from_dict(s) for s in data.get("select", [])],
            union_all=[cls.from_dict(s) for s in data.get("unionAll", [])],
        )


@dataclass
class ViewDefinition:
    name: str
    resource: str
    selects: List[SelectClause] = field(default_factory=list)
    where: List[str] = field(default_factory=list)
    status: str = "active"
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ViewDefinition":
        return cls(
            name=data.get("name", data.get("resource", "unnamed")),
            resource=data["resource"],
            selects=[SelectClause.from_dict(s) for s in data.get("select", [])],
            where=[w["path"] for w in data.get("where", [])],
            status=data.get("status", "active"),
            description=data.get("description", ""),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ViewDefinition":
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def all_columns(self) -> List[Column]:
        """Flat list of every column declared anywhere in this view."""
        cols: list[Column] = []

        def walk(sel: SelectClause) -> None:
            cols.extend(sel.columns)
            for child in sel.selects:
                walk(child)
            for child in sel.union_all:
                walk(child)

        for s in self.selects:
            walk(s)
        return cols
