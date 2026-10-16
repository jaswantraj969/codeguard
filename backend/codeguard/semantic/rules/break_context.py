"""SEM-BREAK-CONTEXT: break or continue outside a loop (error, always on).

A semantic constraint check, not a syntax error: the code matches the grammar,
but C forbids it (addendum §5.3).
"""

from codeguard import ast
from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic

RULE_ID = "SEM-BREAK-CONTEXT"

EXPLANATION = (
    "break leaves the nearest loop and continue jumps to its next iteration, so both need "
    "an enclosing while or for loop. switch is not supported in CodeGuard V1."
)


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    stack: list[tuple[ast.Node, bool]] = [(model.unit, False)]  # (node, inside a loop body)
    while stack:
        node, in_loop = stack.pop()
        if isinstance(node, ast.Break | ast.Continue) and not in_loop:
            keyword = "break" if isinstance(node, ast.Break) else "continue"
            diagnostic = make_diagnostic(
                RULE_ID,
                Severity.ERROR,
                f"'{keyword}' can only be used inside a loop.",
                node.loc,
                EXPLANATION,
            )
            findings.append(Finding(diagnostic, anchor=node))
            continue
        loop_body = node.body if isinstance(node, ast.While | ast.For) else None
        for child in reversed(node.children()):
            stack.append((child, in_loop or child is loop_body))
    return findings
