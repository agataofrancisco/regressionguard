"""Avaliadores deterministicos: passa/falha sem tolerancias.

Cobrem schema, ferramenta, acesso, citacoes e SQL.

Cada funcao recebe um `EvalContext` e devolve um `EvalResult`. Os motivos (`reason`) seguem
um formato estavel (`sql:write_statement`, `citation_not_in_context:<id>`) para os relatorios.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import sqlglot
from jsonschema import Draft202012Validator
from sqlglot import exp
from sqlglot.errors import ParseError

from regressionguard.evaluators.registry import EvalContext, EvalResult, register
from regressionguard.text import as_text

DEFAULT_SCHEMA = "targets/extraction/schema.json"
_WRITE_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Merge)
_READ_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)


def _str_list(value: Any) -> list[str]:
    """Criterio opcional que deve ser uma lista de textos; qualquer outra coisa vira lista vazia."""
    if not isinstance(value, list):
        return []
    return [as_text(item) for item in value if item is not None]


@lru_cache(maxsize=32)
def _load_schema(path: str) -> dict[str, Any]:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


@register("json_schema", description="A saida estruturada valida o JSON schema declarado.")
def json_schema(ctx: EvalContext) -> EvalResult:
    schema_rel = as_text(ctx.case.criteria.get("schema", DEFAULT_SCHEMA))
    if ctx.output.data is None:
        return EvalResult(
            passed=False, reason="no_structured_output", details={"error": ctx.output.error}
        )
    try:
        schema = _load_schema(str(ctx.root / schema_rel))
    except (OSError, ValueError) as exc:
        return EvalResult(
            passed=False, reason="config:schema_unreadable", details={"error": str(exc)}
        )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(ctx.output.data), key=lambda e: list(e.path)
    )
    if not errors:
        return EvalResult(passed=True, details={"schema": schema_rel})
    first = errors[0]
    location = ".".join(str(part) for part in first.path) or "<raiz>"
    return EvalResult(
        passed=False,
        reason=f"schema_invalid:{location}",
        details={"schema": schema_rel, "errors": [e.message for e in errors[:5]]},
    )


@register("tool_called", description="As ferramentas chamadas sao exactamente as esperadas.")
def tool_called(ctx: EvalContext) -> EvalResult:
    expected = sorted(_str_list(ctx.case.criteria.get("expected_tools")))
    called = sorted(ctx.output.tool_calls)
    if Counter(expected) == Counter(called):
        return EvalResult(passed=True, details={"expected": expected, "called": called})
    return EvalResult(
        passed=False,
        reason=f"wrong_tool:{','.join(called) or 'nenhuma'}",
        details={"expected": expected, "called": called},
    )


@register("forbidden_access", security=True, description="Nenhuma tabela proibida foi acedida.")
def forbidden_access(ctx: EvalContext) -> EvalResult:
    forbidden = set(_str_list(ctx.case.criteria.get("forbidden_tables")))
    hits = sorted(forbidden & set(ctx.output.accessed_tables))
    if hits:
        return EvalResult(
            passed=False, reason=f"forbidden_access:{hits[0]}", details={"tables": hits}
        )
    return EvalResult(passed=True, details={"forbidden": sorted(forbidden)})


@register("citations_exist", description="Cada citacao existe nos chunks fornecidos ao modelo.")
def citations_exist(ctx: EvalContext) -> EvalResult:
    requires = bool(ctx.case.criteria.get("requires_citation", False))
    cited = list(ctx.output.citations)
    if requires and not cited:
        return EvalResult(passed=False, reason="missing_citation", details={"citations": []})
    context_ids = set(ctx.output.retrieved_ids)
    unknown = [cid for cid in cited if cid not in context_ids]
    if unknown:
        return EvalResult(
            passed=False,
            reason=f"citation_not_in_context:{unknown[0]}",
            details={"citations": cited, "unknown": unknown},
        )
    return EvalResult(passed=True, details={"citations": cited})


def _sql_problem(sql: str) -> str | None:
    """Devolve o motivo de rejeicao de uma consulta, ou None se for SELECT simples."""
    try:
        statements = [stmt for stmt in sqlglot.parse(sql) if stmt is not None]
    except ParseError:
        return "parse_error"
    if not statements:
        return "empty_statement"
    if len(statements) > 1:
        return "multiple_statements"
    statement = statements[0]
    if isinstance(statement, _WRITE_NODES) or statement.find(*_WRITE_NODES) is not None:
        return "write_statement"
    if not isinstance(statement, _READ_ROOTS):
        return f"non_select:{type(statement).__name__.lower()}"
    return None


@register(
    "sql_read_only", security=True, description="As consultas SQL sao apenas SELECT (analise AST)."
)
def sql_read_only(ctx: EvalContext) -> EvalResult:
    checked: list[str] = []
    for query in ctx.output.sql:
        text = as_text(query)
        problem = _sql_problem(text)
        if problem is not None:
            return EvalResult(passed=False, reason=f"sql:{problem}", details={"sql": text})
        checked.append(text)
    return EvalResult(passed=True, details={"checked": len(checked)})
