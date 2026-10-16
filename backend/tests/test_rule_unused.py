"""SEM-UNUSED (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import diagnostics, in_main

RULE = "SEM-UNUSED"


def unused_names(source: str) -> list[str]:
    return [d.message.split("'")[1] for d in diagnostics(source, RULE)]


def test_srs_demo_unused_initializer() -> None:
    # TC-02 and the SRS demo: int unused = 50;
    (d,) = diagnostics(in_main("int x = 10;\nint unused = 50;\nreturn x;"), RULE)
    assert (d.line, d.column, d.end_column, d.severity) == (3, 5, 11, Severity.WARNING)
    assert d.message == "Variable 'unused' is declared but its value is never read."
    assert d.explanation and d.fix_hint


@pytest.mark.parametrize(
    "body",
    [
        "int x;",  # never mentioned
        "int x = 1;",  # initializer only
        "int x; x = 5;",  # plain assignment only
        "int x = 0; x++;",  # standalone increment
        "int x = 0; ++x; x--;",
        "int x = 0; x += 1; x *= 2;",  # standalone compound assignment
        'int x; scanf("%d", &x);',  # TC-35: &x is a write, not a read
        "int x; for (x = 0; ; x++) { break; }",  # for init/update are writes
    ],
)
def test_written_but_never_read(body: str) -> None:
    assert unused_names(in_main(body + "\nreturn 0;")) == ["x"]


def test_unused_in_nested_scopes_and_for_init() -> None:
    source = in_main("{ int a = 1; }\nfor (int i = 0; ; ) { break; }\nreturn 0;")
    assert unused_names(source) == ["a", "i"]


@pytest.mark.parametrize(
    "body",
    [
        "int x = 1; return x;",
        "int x = 1; int y = x + 1; return y;",
        "int x = 1; if (x) { } return 0;",
        "int x = 0; while (x < 3) x++; return 0;",
        'int x = 1; printf("%d", x); return 0;',
        "int x = 1; int y = x++; return y;",  # increment whose value is used
        "int x = 1; int y = (x += 1); return y;",
        "int x = 1; x = x + 1; return 0;",  # x read on the right
        "int x; x; return 0;",  # a bare read is a read
        "int i; for (i = 0; i < 3; i++) { } return 0;",  # read in the condition
    ],
)
def test_does_not_fire_when_read(body: str) -> None:
    assert unused_names(in_main(body)) == []


def test_parameters_and_globals_are_excluded() -> None:
    assert unused_names("int g;\nint f(int unused_param) { return 0; }") == []
