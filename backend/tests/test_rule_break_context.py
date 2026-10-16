"""SEM-BREAK-CONTEXT (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import analyze_source, diagnostics, in_main

RULE = "SEM-BREAK-CONTEXT"


def messages(source: str) -> list[str]:
    return [d.message for d in diagnostics(source, RULE)]


def test_break_outside_a_loop() -> None:
    # TC-37 (semantic part; the parser test checks the syntax stage passes)
    (d,) = diagnostics("void f(void) {\n  break;\n}\n", RULE)
    assert (d.line, d.column, d.severity) == (2, 3, Severity.ERROR)
    assert d.message == "'break' can only be used inside a loop."
    assert d.explanation


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("continue;", ["'continue' can only be used inside a loop."]),
        ("if (1) { break; }", ["'break' can only be used inside a loop."]),
        ("while (1) { } break;", ["'break' can only be used inside a loop."]),
        ("{ { continue; } }", ["'continue' can only be used inside a loop."]),
    ],
)
def test_fires(body: str, expected: list[str]) -> None:
    assert messages(in_main(body)) == expected


@pytest.mark.parametrize(
    "body",
    [
        "while (1) { break; }",
        "for (;;) { continue; }",
        "while (1) { if (1) { break; } }",
        "for (;;) { { { continue; } } }",
        "while (1) break;",
        "for (;;) while (1) break;",
    ],
)
def test_does_not_fire(body: str) -> None:
    assert messages(in_main(body)) == []


def test_cannot_be_turned_off() -> None:
    result = analyze_source(in_main("break;"), {RULE: False})
    assert [d.rule_id for d in result.diagnostics] == [RULE]
