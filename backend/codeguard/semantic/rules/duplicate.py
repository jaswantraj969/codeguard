"""SEM-DUP: the same name declared twice in the same scope (error)."""

from codeguard import ast
from codeguard.diagnostics import Severity
from codeguard.semantic.model import SemanticModel
from codeguard.semantic.rules.base import Finding, make_diagnostic
from codeguard.semantic.symbols import SymbolKind

RULE_ID = "SEM-DUP"

EXPLANATION = (
    "Each name can be declared only once in the same scope. "
    "Rename one of them or remove the second declaration."
)


def check(model: SemanticModel) -> list[Finding]:
    findings = []
    for dup in model.duplicates:
        both_functions = (
            isinstance(dup.decl, ast.FunctionDef) and dup.first.kind is SymbolKind.FUNCTION
        )
        if both_functions:
            message = f"Function '{dup.name}' is already defined (line {dup.first.line})."
        else:
            message = f"'{dup.name}' is already declared in this scope (line {dup.first.line})."
        diagnostic = make_diagnostic(
            RULE_ID,
            Severity.ERROR,
            message,
            dup.name_loc,
            EXPLANATION,
            fix_hint="Rename one of them or remove this declaration.",
        )
        findings.append(Finding(diagnostic, anchor=dup.decl))
    return findings
