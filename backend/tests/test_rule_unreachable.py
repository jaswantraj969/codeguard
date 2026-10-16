"""SEM-UNREACH (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import diagnostics, in_main

RULE = "SEM-UNREACH"


def unreachable(source: str) -> list[tuple[int, int, int | None]]:
    return [(d.line, d.column, d.end_line) for d in diagnostics(source, RULE)]


def test_statement_after_return() -> None:
    # TC-06
    (d,) = diagnostics(in_main("int x = 0;\nreturn 0;\nx = 1;\nx = 2;"), RULE)
    assert (d.line, d.column, d.end_line, d.severity) == (4, 1, 5, Severity.WARNING)
    assert d.message == "This code can never run."
    assert d.fix_hint == "Remove this code, or move it before the 'return'."
    assert d.explanation


@pytest.mark.parametrize(
    ("body", "jump"),
    [
        ("while (1) { break;\n x++; }", "break"),
        ("while (x) { continue;\n x++; }", "continue"),
        ("{ return 1;\n int y = 2; }", "return"),
    ],
)
def test_after_each_jump(body: str, jump: str) -> None:
    source = in_main("int x = 0;\n" + body + "\nreturn x;")
    (d,) = diagnostics(source, RULE)
    assert d.fix_hint is not None and f"'{jump}'" in d.fix_hint


def test_reported_once_per_block() -> None:
    source = in_main("return 0;\nreturn 1;\nreturn 2;")
    assert unreachable(source) == [(3, 1, 4)]


@pytest.mark.parametrize(
    "body",
    [
        "int x = 1; return x;",
        "int x = 1; if (x) { return 1; } return 0;",  # return inside a nested block
        "int x = 1; if (x) return 1; else return 2;",  # no flow analysis across branches
        "return 0;;",  # empty statements are ignored
        "int x = 1; while (x) { x--; if (x) break; } return x;",
        "if (0) { return 1; } return 0;",  # if (0) belongs to SEM-CONSTCOND
    ],
)
def test_does_not_fire(body: str) -> None:
    assert unreachable(in_main(body)) == []
