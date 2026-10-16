"""SEM-SHADOW: an inner declaration hides an outer one (warning).

Considers user variables, parameters and functions; library and #define names
are ignored.
"""

from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic

RULE_ID = "SEM-SHADOW"

EXPLANATION = (
    "Inside this scope, the name refers to the new variable, not the outer one. "
    "This is legal but often a mistake; consider a different name."
)


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    for shadow in model.shadows:
        symbol, outer = shadow.symbol, shadow.outer
        diagnostic = make_diagnostic(
            RULE_ID,
            Severity.WARNING,
            f"'{symbol.name}' hides the {outer.kind.value} declared on line {outer.line}.",
            symbol.name_loc,
            EXPLANATION,
            fix_hint="Rename the inner one.",
        )
        findings.append(Finding(diagnostic, anchor=symbol.decl))
    return findings
