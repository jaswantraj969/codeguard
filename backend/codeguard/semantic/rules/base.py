"""The interface every semantic rule module implements."""

from collections.abc import Callable
from dataclasses import dataclass

from codeguard import ast
from codeguard.diagnostics import Diagnostic, Severity
from codeguard.semantic.model import SemanticModel


@dataclass(frozen=True, slots=True)
class Finding:
    """A diagnostic plus the construct it is about.

    The analyzer uses `anchor` to apply the one-diagnostic-per-construct policy
    (addendum §5.1). Findings without an anchor are always kept.
    """

    diagnostic: Diagnostic
    anchor: ast.Node | None = None


# A rule module exposes RULE_ID and `check(model) -> list[Finding]`.
Check = Callable[[SemanticModel], list[Finding]]


def make_diagnostic(
    rule_id: str,
    severity: Severity,
    message: str,
    loc: ast.Loc,
    explanation: str,
    fix_hint: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        rule_id=rule_id,
        severity=severity,
        message=message,
        line=loc.line,
        column=loc.column,
        end_line=loc.end_line,
        end_column=loc.end_column,
        explanation=explanation,
        fix_hint=fix_hint,
    )
