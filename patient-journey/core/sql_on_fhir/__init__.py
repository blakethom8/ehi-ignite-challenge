"""SQL-on-FHIR v2 minimal prototype.

Implements a small, practical subset of the SQL-on-FHIR v2 ViewDefinition spec
(https://build.fhir.org/ig/FHIR/sql-on-fhir-v2/) against raw FHIR R4 JSON
bundles. The goal is to answer the question: "is a ViewDefinition layer on top
of SQLite actually useful for our clinical intelligence app?"

Scope (what we support):
- Top-level ViewDefinition with `resource`, `select[]`, `where[]`
- `select[].column[]` with `name`, `path`, `type`
- `select[].forEach` and `select[].forEachOrNull`
- Nested `select[].select[]`
- `select[].unionAll[]`
- FHIRPath-lite: dotted paths, `.first()`, `.exists()`, `.count()`, `$this`,
  boolean `and`/`or`/`not`, comparison `=`/`!=`, string/number/bool literals,
  `where(...)` filter, `getResourceKey()` / `getReferenceKey()` helpers.

Out of scope: full FHIRPath, date arithmetic, extension navigation via the
`extension.where(url='...')` convenience (we support it via the filter form),
polymorphic `value[x]` resolution.
"""

from .view_definition import ViewDefinition, Column, SelectClause
from .fhirpath import evaluate
from .runner import run_view
from .sqlite_sink import materialize

__all__ = [
    "ViewDefinition",
    "Column",
    "SelectClause",
    "evaluate",
    "run_view",
    "materialize",
]
