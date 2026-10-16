"""SEM-UNDECL: a name used with no visible declaration (error).

Reported once per name per function (or once at file scope), at the first use.
"""

from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic

RULE_ID = "SEM-UNDECL"

EXPLAIN_VARIABLE = (
    "C requires every variable to be declared before it is used. "
    "Declare it with a type before this line, and check the spelling."
)
EXPLAIN_FUNCTION = (
    "C needs to know about a function before it is called. Check the spelling, or define "
    "the function in this file. CodeGuard knows only common library functions such as printf."
)


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    seen: set[tuple[str | None, str]] = set()
    for use in model.undeclared:
        name = use.identifier.name
        key = (use.function, name)
        if key in seen:
            continue
        seen.add(key)
        if use.is_call:
            message = f"Function '{name}' is called but never declared."
            explanation, hint = EXPLAIN_FUNCTION, None
        else:
            message = f"'{name}' is used but never declared."
            explanation, hint = EXPLAIN_VARIABLE, f"Declare it first, e.g. 'int {name};'."
        diagnostic = make_diagnostic(
            RULE_ID, Severity.ERROR, message, use.identifier.loc, explanation, hint
        )
        findings.append(Finding(diagnostic, anchor=use.identifier))
    return findings
