"""SEM-DIV0: division or remainder by a constant zero (error).

Fires when the right operand of /, %, /= or %= folds to zero from literals and
const variables with constant initializers. Plain variables never fire.
"""

from codeguard import ast
from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic

RULE_ID = "SEM-DIV0"

EXPLANATION = (
    "Dividing by zero is undefined in C and usually crashes the program. "
    "Check the divisor before dividing."
)


def divisor(node: ast.Node) -> tuple[str, ast.Expr] | None:
    """(operator, right operand) if `node` divides or takes a remainder."""
    if isinstance(node, ast.Binary) and node.op in ("/", "%"):
        return node.op, node.right
    if isinstance(node, ast.Assign) and node.op in ("/=", "%="):
        return node.op[0], node.value
    return None


def divides_by_zero(model: SemanticModel, node: ast.Node) -> bool:
    found = divisor(node)
    if found is None:
        return False
    value = model.fold(found[1])
    return value is not None and value.is_zero


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    for node in ast.walk(model.unit):
        found = divisor(node)
        if found is None or not divides_by_zero(model, node):
            continue
        message = "Division by zero." if found[0] == "/" else "Remainder (%) by zero."
        diagnostic = make_diagnostic(
            RULE_ID,
            Severity.ERROR,
            message,
            node.loc,
            EXPLANATION,
            fix_hint="Make sure the divisor can never be zero.",
        )
        findings.append(Finding(diagnostic, anchor=node))
    return findings
