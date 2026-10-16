"""SEM-UNREACH: statements after return, break or continue in the same block (warning).

Reported once per block, at the first unreachable statement, with the range
extending to the block's last statement. `if (0)` belongs to SEM-CONSTCOND.
"""

from codeguard import ast
from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic

RULE_ID = "SEM-UNREACH"

EXPLANATION = (
    "Statements after a return, break or continue in the same block are never executed. "
    "Remove them or move them before the jump."
)

JUMP_NAMES = {ast.Return: "return", ast.Break: "break", ast.Continue: "continue"}


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    for node in ast.walk(model.unit):
        if not isinstance(node, ast.Block):
            continue
        items = node.items
        jump_index = next(
            (
                i
                for i, item in enumerate(items)
                if isinstance(item, ast.Return | ast.Break | ast.Continue)
            ),
            None,
        )
        if jump_index is None:
            continue
        rest = [item for item in items[jump_index + 1 :] if not isinstance(item, ast.EmptyStmt)]
        if not rest:
            continue
        first, last = rest[0], rest[-1]
        jump = JUMP_NAMES[type(items[jump_index])]
        loc = ast.Loc(first.loc.line, first.loc.column, last.loc.end_line, last.loc.end_column)
        diagnostic = make_diagnostic(
            RULE_ID,
            Severity.WARNING,
            "This code can never run.",
            loc,
            EXPLANATION,
            fix_hint=f"Remove this code, or move it before the '{jump}'.",
        )
        findings.append(Finding(diagnostic, anchor=first))
    return findings
