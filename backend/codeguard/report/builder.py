"""The analysis pipeline and its report (SRS addendum §4, §8.2).

`build_report(source, toggles)` runs lexer -> parser -> semantic -> optimizer
and returns a Report. `Report.to_json(analysis_id)` produces the 200 response
body as JSON text. Text crosses the worker-process boundary cheaply and safely,
however deep the AST is.
"""

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from codeguard import ast
from codeguard.diagnostics import Diagnostic, Severity
from codeguard.lexer import Token, normalize_source, tokenize
from codeguard.optimizer import OPT_CONSTEXPR, check_constexpr
from codeguard.optimizer import TOGGLEABLE as OPTIMIZER_TOGGLEABLE
from codeguard.parser import parse
from codeguard.report.serialize import (
    ast_to_json,
    diagnostic_to_dict,
    scope_tree_to_dict,
    token_to_dict,
)
from codeguard.semantic import TOGGLEABLE as SEMANTIC_TOGGLEABLE
from codeguard.semantic import Scope, SymbolKind, analyze

# Rule IDs the API's `rules` field may turn on or off (addendum §8.2).
TOGGLEABLE_RULES = SEMANTIC_TOGGLEABLE | OPTIMIZER_TOGGLEABLE

# Teaching-view caps (addendum §7). They limit only the `tokens` and `ast`
# fields; analysis, diagnostics and statistics always cover the full input.
MAX_VIEW_TOKENS = 10_000
MAX_VIEW_AST_NODES = 20_000
MAX_VIEW_AST_DEPTH = 400

SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.SUGGESTION: 2}


class Stage(StrEnum):
    LEXICAL = "lexical"
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    OPTIMIZER = "optimizer"


class StageState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class StageStatus:
    stage: Stage
    status: StageState
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class Statistics:
    variables: int
    functions: int
    errors: int
    warnings: int
    suggestions: int
    tokens: int
    lines: int
    duration_ms: float


@dataclass(slots=True)
class Report:
    status: list[StageStatus]
    diagnostics: list[Diagnostic]
    statistics: Statistics
    tokens: list[Token]  # every token except EOF (the view is capped at serialization)
    unit: ast.TranslationUnit | None  # None unless the syntax stage passed
    file_scope: Scope | None  # None unless the semantic stage ran

    def stage(self, stage: Stage) -> StageStatus:
        return next(s for s in self.status if s.stage is stage)

    def to_json(self, analysis_id: str) -> str:
        tokens_truncated = len(self.tokens) > MAX_VIEW_TOKENS
        ast_json = "null"
        ast_truncated = False
        if self.unit is not None:
            node_count = sum(1 for _ in ast.walk(self.unit))
            if node_count > MAX_VIEW_AST_NODES or ast.depth(self.unit) > MAX_VIEW_AST_DEPTH:
                ast_truncated = True
            else:
                ast_json = ast_to_json(self.unit)
        head = {
            "analysis_id": analysis_id,
            "status": [
                {"stage": s.stage.value, "status": s.status.value, "detail": s.detail}
                for s in self.status
            ],
            "diagnostics": [diagnostic_to_dict(d) for d in self.diagnostics],
            "statistics": {
                "variables": self.statistics.variables,
                "functions": self.statistics.functions,
                "errors": self.statistics.errors,
                "warnings": self.statistics.warnings,
                "suggestions": self.statistics.suggestions,
                "tokens": self.statistics.tokens,
                "lines": self.statistics.lines,
                "duration_ms": self.statistics.duration_ms,
            },
            "tokens": [token_to_dict(t) for t in self.tokens[:MAX_VIEW_TOKENS]],
        }
        tail = {
            "symbols": None if self.file_scope is None else scope_tree_to_dict(self.file_scope),
            "truncated": {"tokens": tokens_truncated, "ast": ast_truncated},
        }

        def dump(value: object) -> str:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

        # {head..., "ast": <iteratively built text>, tail...}
        return dump(head)[:-1] + ',"ast":' + ast_json + "," + dump(tail)[1:]


def count_lines(source: str) -> int:
    if not source:
        return 0
    return source.count("\n") + (0 if source.endswith("\n") else 1)


def sort_key(d: Diagnostic) -> tuple[int, int, int, str]:
    return (d.line, d.column, SEVERITY_ORDER[d.severity], d.rule_id)


def build_report(source: str, toggles: Mapping[str, bool] | None = None) -> Report:
    """Run the whole pipeline on `source`. Never executes or compiles it."""
    started = time.perf_counter()
    toggles = toggles or {}
    normalized = normalize_source(source)
    diagnostics: list[Diagnostic] = []
    status: dict[Stage, StageStatus] = {
        stage: StageStatus(stage, StageState.SKIPPED) for stage in Stage
    }
    unit: ast.TranslationUnit | None = None
    file_scope: Scope | None = None
    variables = functions = 0

    lexed = tokenize(source)
    tokens = lexed.tokens[:-1]  # drop EOF
    diagnostics += lexed.diagnostics
    status[Stage.LEXICAL] = StageStatus(
        Stage.LEXICAL,
        StageState.PASSED if lexed.ok else StageState.FAILED,
        "Stopped reporting after 20 lexical errors." if lexed.errors_truncated else None,
    )

    if lexed.ok:
        parsed = parse(lexed.tokens)
        diagnostics += parsed.diagnostics
        status[Stage.SYNTAX] = StageStatus(
            Stage.SYNTAX,
            StageState.PASSED if parsed.ok else StageState.FAILED,
            "Stopped after 20 syntax errors." if parsed.errors_truncated else None,
        )

        if parsed.ok:
            unit = parsed.unit
            semantic = analyze(unit, lexed.defines, toggles)
            diagnostics += semantic.diagnostics
            file_scope = semantic.model.file_scope
            has_errors = any(d.severity is Severity.ERROR for d in semantic.diagnostics)
            status[Stage.SEMANTIC] = StageStatus(
                Stage.SEMANTIC, StageState.FAILED if has_errors else StageState.PASSED
            )
            kinds = [s.kind for s in semantic.model.symbols]
            variables = kinds.count(SymbolKind.VARIABLE)
            functions = kinds.count(SymbolKind.FUNCTION)

            if toggles.get(OPT_CONSTEXPR, True):
                diagnostics += check_constexpr(
                    unit, normalized.split("\n"), semantic.constant_conditions
                )
            status[Stage.OPTIMIZER] = StageStatus(Stage.OPTIMIZER, StageState.PASSED)

    diagnostics.sort(key=sort_key)
    severities = [d.severity for d in diagnostics]
    statistics = Statistics(
        variables=variables,
        functions=functions,
        errors=severities.count(Severity.ERROR),
        warnings=severities.count(Severity.WARNING),
        suggestions=severities.count(Severity.SUGGESTION),
        tokens=len(tokens),
        lines=count_lines(normalized),
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return Report(
        status=[status[stage] for stage in Stage],
        diagnostics=diagnostics,
        statistics=statistics,
        tokens=tokens,
        unit=unit,
        file_scope=file_scope,
    )
