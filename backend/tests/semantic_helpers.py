"""Helpers for semantic tests."""

from collections.abc import Mapping

from codeguard.diagnostics import Diagnostic
from codeguard.lexer import tokenize
from codeguard.parser import parse
from codeguard.semantic import SemanticResult, analyze


def analyze_source(source: str, toggles: Mapping[str, bool] | None = None) -> SemanticResult:
    lexed = tokenize(source)
    assert lexed.ok, lexed.diagnostics
    parsed = parse(lexed.tokens)
    assert parsed.ok, parsed.diagnostics
    return analyze(parsed.unit, lexed.defines, toggles)


def diagnostics(source: str, rule_id: str | None = None) -> list[Diagnostic]:
    found = analyze_source(source).diagnostics
    return [d for d in found if rule_id is None or d.rule_id == rule_id]


def rule_ids(source: str) -> list[str]:
    return [d.rule_id for d in analyze_source(source).diagnostics]


def in_main(body: str) -> str:
    """Wrap statements in `int main(void) { ... }`, starting on line 2."""
    return "int main(void) {\n" + body + "\n}\n"
