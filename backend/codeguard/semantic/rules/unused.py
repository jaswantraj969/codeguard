"""SEM-UNUSED: a local variable whose value is never read (warning).

What counts as a read is decided by the resolver (see semantic/model.py).
Parameters and globals are excluded.
"""

from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic

RULE_ID = "SEM-UNUSED"

EXPLANATION = (
    "A variable whose value is never read has no effect on the program. "
    "Remove it, or use it where you meant to."
)


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    for symbol in model.symbols:
        if not symbol.is_local_variable or symbol.reads > 0:
            continue
        diagnostic = make_diagnostic(
            RULE_ID,
            Severity.WARNING,
            f"Variable '{symbol.name}' is declared but its value is never read.",
            symbol.name_loc,
            EXPLANATION,
            fix_hint="Remove the variable, or use its value.",
        )
        findings.append(Finding(diagnostic, anchor=symbol.decl))
    return findings
