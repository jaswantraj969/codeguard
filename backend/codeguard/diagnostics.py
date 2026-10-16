"""The diagnostic model shared by every stage (SRS addendum §5.1).

This is a shared contract: changes need approval from all three members.
"""

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    rule_id: str
    severity: Severity
    message: str
    line: int
    column: int
    explanation: str
    end_line: int | None = None
    end_column: int | None = None  # exclusive
    fix_hint: str | None = None
