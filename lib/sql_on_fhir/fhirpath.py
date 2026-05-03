"""Minimal FHIRPath evaluator — only what our ViewDefinitions actually use.

FHIRPath is a large spec. We implement a practical subset that covers the
canonical SQL-on-FHIR test suite (basic / forEach) and the US Core-flavored
ViewDefinitions we author for Synthea bundles.

Semantics:
- Every expression evaluates to a *collection* (Python list). A missing field
  yields `[]`. A scalar field yields `[value]`. An array field yields the list.
- `.first()` → collection with 0 or 1 elements
- `.exists()` → always `[True]` or `[False]`
- `.count()` → `[n]`
- `where(expr)` → filter the current collection using `expr` evaluated against
  each element as `$this`
- Boolean ops (`and`, `or`, `not`) are three-valued: empty collection is
  treated as false in boolean context.
- `=` / `!=` compare the singleton value of each side; empty → empty (false).

This is not spec-complete. It is "enough to run the prototype ViewDefinitions
and understand whether the layer pays for itself."
"""

from __future__ import annotations

import re
from typing import Any, Iterable, List


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    \s+
  | (?P<STRING>'(?:[^'\\]|\\.)*')
  | (?P<NUMBER>\d+(?:\.\d+)?)
  | (?P<DOT>\.)
  | (?P<LPAREN>\()
  | (?P<RPAREN>\))
  | (?P<COMMA>,)
  | (?P<EQ>=)
  | (?P<NEQ>!=)
  | (?P<IDENT>\$this|[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m:
            raise ValueError(f"Cannot tokenize FHIRPath at {pos}: {expr!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind is None:  # whitespace
            continue
        tokens.append((kind, m.group()))
    return tokens


# ---------------------------------------------------------------------------
# Parser — recursive descent with precedence: or < and < equality < unary(not) < path
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def eat(self, kind: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if tok is None or (kind and tok[0] != kind):
            raise ValueError(f"Expected {kind}, got {tok}")
        self.pos += 1
        return tok

    def parse(self):
        node = self.parse_or()
        if self.pos != len(self.tokens):
            raise ValueError(f"Unexpected trailing tokens: {self.tokens[self.pos:]}")
        return node

    def parse_or(self):
        left = self.parse_and()
        while self._match_ident("or"):
            right = self.parse_and()
            left = ("or", left, right)
        return left

    def parse_and(self):
        left = self.parse_equality()
        while self._match_ident("and"):
            right = self.parse_equality()
            left = ("and", left, right)
        return left

    def parse_equality(self):
        left = self.parse_unary()
        while True:
            tok = self.peek()
            if tok and tok[0] == "EQ":
                self.eat("EQ")
                right = self.parse_unary()
                left = ("eq", left, right)
            elif tok and tok[0] == "NEQ":
                self.eat("NEQ")
                right = self.parse_unary()
                left = ("neq", left, right)
            else:
                return left

    def parse_unary(self):
        if self._match_ident("not"):
            return ("not", self.parse_unary())
        return self.parse_path()

    def parse_path(self):
        node = self.parse_atom()
        while True:
            tok = self.peek()
            if tok and tok[0] == "DOT":
                self.eat("DOT")
                ident = self.eat("IDENT")[1]
                # function call?
                nxt = self.peek()
                if nxt and nxt[0] == "LPAREN":
                    self.eat("LPAREN")
                    args: list = []
                    if self.peek() and self.peek()[0] != "RPAREN":
                        args.append(self.parse_or())
                        while self.peek() and self.peek()[0] == "COMMA":
                            self.eat("COMMA")
                            args.append(self.parse_or())
                    self.eat("RPAREN")
                    node = ("call", node, ident, args)
                else:
                    node = ("field", node, ident)
            else:
                return node

    def parse_atom(self):
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected end of expression")
        if tok[0] == "LPAREN":
            self.eat("LPAREN")
            node = self.parse_or()
            self.eat("RPAREN")
            return node
        if tok[0] == "STRING":
            self.eat("STRING")
            return ("literal", tok[1][1:-1].replace("\\'", "'"))
        if tok[0] == "NUMBER":
            self.eat("NUMBER")
            val = float(tok[1]) if "." in tok[1] else int(tok[1])
            return ("literal", val)
        if tok[0] == "IDENT":
            self.eat("IDENT")
            ident = tok[1]
            if ident in ("true", "false"):
                return ("literal", ident == "true")
            # Possible function call at root (rare)
            nxt = self.peek()
            if nxt and nxt[0] == "LPAREN":
                self.eat("LPAREN")
                args: list = []
                if self.peek() and self.peek()[0] != "RPAREN":
                    args.append(self.parse_or())
                    while self.peek() and self.peek()[0] == "COMMA":
                        self.eat("COMMA")
                        args.append(self.parse_or())
                self.eat("RPAREN")
                return ("call", ("this",), ident, args)
            if ident == "$this":
                return ("this",)
            return ("root_field", ident)
        raise ValueError(f"Unexpected token {tok}")

    def _match_ident(self, name: str) -> bool:
        tok = self.peek()
        if tok and tok[0] == "IDENT" and tok[1] == name:
            self.eat("IDENT")
            return True
        return False


def _parse(expr: str):
    return _Parser(_tokenize(expr)).parse()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def _as_collection(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if x is not None]
    return [v]


def _truthy(coll: List[Any]) -> bool:
    if not coll:
        return False
    if len(coll) == 1 and isinstance(coll[0], bool):
        return coll[0]
    return True


def _eval_node(node, ctx: Any, root: Any) -> List[Any]:
    kind = node[0]

    if kind == "literal":
        return [node[1]]

    if kind == "this":
        return _as_collection(ctx)

    if kind == "root_field":
        # bare identifier at start of path: look up on ctx (the focus)
        return _field_access(_as_collection(ctx), node[1])

    if kind == "field":
        parent = _eval_node(node[1], ctx, root)
        return _field_access(parent, node[2])

    if kind == "call":
        target = _eval_node(node[1], ctx, root)
        return _invoke(target, node[2], node[3], ctx, root)

    if kind == "and":
        return [_truthy(_eval_node(node[1], ctx, root)) and _truthy(_eval_node(node[2], ctx, root))]
    if kind == "or":
        return [_truthy(_eval_node(node[1], ctx, root)) or _truthy(_eval_node(node[2], ctx, root))]
    if kind == "not":
        return [not _truthy(_eval_node(node[1], ctx, root))]

    if kind in ("eq", "neq"):
        left = _eval_node(node[1], ctx, root)
        right = _eval_node(node[2], ctx, root)
        if not left or not right:
            return []  # empty propagation
        l0 = left[0] if len(left) == 1 else left
        r0 = right[0] if len(right) == 1 else right
        return [l0 == r0] if kind == "eq" else [l0 != r0]

    raise ValueError(f"Unknown node: {node}")


def _field_access(parent: Iterable[Any], name: str) -> List[Any]:
    out: list = []
    for p in parent:
        if isinstance(p, dict) and name in p:
            val = p[name]
            if isinstance(val, list):
                out.extend([x for x in val if x is not None])
            elif val is not None:
                out.append(val)
    return out


def _invoke(target: List[Any], name: str, args: list, ctx: Any, root: Any) -> List[Any]:
    if name == "first":
        return target[:1]
    if name == "last":
        return target[-1:]
    if name == "count":
        return [len(target)]
    if name == "exists":
        return [len(target) > 0]
    if name == "empty":
        return [len(target) == 0]
    if name == "where":
        if len(args) != 1:
            raise ValueError("where() expects 1 argument")
        out = []
        for item in target:
            if _truthy(_eval_node(args[0], item, root)):
                out.append(item)
        return out
    if name == "getResourceKey":
        # ViewDefinition convention: stable primary key for a resource.
        # We use "{resourceType}/{id}" which matches reference targets.
        out = []
        for item in target:
            if isinstance(item, dict) and "id" in item and "resourceType" in item:
                out.append(f"{item['resourceType']}/{item['id']}")
            elif isinstance(item, dict) and "id" in item:
                out.append(item["id"])
        return out
    if name == "getReferenceKey":
        # Pull the referenced resource key from a Reference (e.g. "Patient/abc")
        out = []
        type_filter = None
        if args:
            lit = _eval_node(args[0], ctx, root)
            if lit:
                type_filter = lit[0]
        for item in target:
            if not isinstance(item, dict):
                continue
            ref = item.get("reference")
            if not ref:
                continue
            if type_filter and not ref.startswith(f"{type_filter}/"):
                continue
            out.append(ref)
        return out
    if name == "ofType":
        # Minimal: filter elements whose 'resourceType' or Python type matches
        if not args:
            return target
        type_name = _eval_node(args[0], ctx, root)
        tn = type_name[0] if type_name else None
        return [x for x in target if isinstance(x, dict) and x.get("resourceType") == tn]
    raise ValueError(f"Unsupported FHIRPath function: {name}")


def evaluate(expr: str, focus: Any) -> List[Any]:
    """Evaluate a FHIRPath-lite expression against `focus`. Returns a collection."""
    if expr is None:
        return []
    expr = expr.strip()
    if not expr:
        return _as_collection(focus)
    tree = _parse(expr)
    return _eval_node(tree, focus, focus)
