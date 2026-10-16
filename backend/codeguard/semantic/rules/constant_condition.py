"""SEM-CONSTCOND: an if/while/for condition that folds to a constant (warning).

One merged rule replacing SRS FR-SEM-07, FR-OPT-02 and FR-OPT-03. The semantic
module owns it; the optimizer only reads its results (the anchors are the
reported condition expressions).

Exempt: `while (1)` and `for (;;)`, the idiomatic infinite loops.
"""

from codeguard import ast
from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic

RULE_ID = "SEM-CONSTCOND"

EXPLANATION = (
    "A condition that does not depend on any variable always has the same result. "
    "It is usually a typo or leftover test code."
)


def _strip_parens(expr: ast.Expr) -> ast.Expr:
    while isinstance(expr, ast.Paren):
        expr = expr.inner
    return expr


def is_idiomatic_infinite_loop(node: ast.While | ast.For) -> bool:
    if isinstance(node, ast.For):
        return node.cond is None
    cond = _strip_parens(node.cond)
    return isinstance(cond, ast.IntLiteral) and cond.value == 1


def _message(node: ast.If | ast.While | ast.For, always_true: bool) -> tuple[str, str | None]:
    if isinstance(node, ast.If):
        if not always_true:
            return "The condition is always false, so this branch never runs.", None
        if node.otherwise is not None:
            return "The condition is always true, so the else branch never runs.", None
        return "The condition is always true, so the if is unnecessary.", None
    if not always_true:
        return "The condition is always false, so the loop body never runs.", None
    hint = "For an intended infinite loop, write while (1) or for (;;)."
    return "The condition is always true, so this loop never ends unless it breaks.", hint


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    for node in ast.walk(model.unit):
        if not isinstance(node, ast.If | ast.While | ast.For) or node.cond is None:
            continue
        if not isinstance(node, ast.If) and is_idiomatic_infinite_loop(node):
            continue
        value = model.fold(node.cond)
        if value is None:
            continue
        message, hint = _message(node, value.truthy)
        diagnostic = make_diagnostic(
            RULE_ID, Severity.WARNING, message, node.cond.loc, EXPLANATION, hint
        )
        findings.append(Finding(diagnostic, anchor=node.cond))
    return findings
