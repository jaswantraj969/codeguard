"""SEM-SHADOW (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import diagnostics, in_main

RULE = "SEM-SHADOW"


def shadows(source: str) -> list[str]:
    return [d.message for d in diagnostics(source, RULE)]


def test_local_hides_global() -> None:
    # TC-19
    (d,) = diagnostics("int x = 1;\nint main(void) {\n  int x = 2;\n  return x;\n}\n", RULE)
    assert (d.line, d.column, d.severity) == (3, 7, Severity.WARNING)
    assert d.message == "'x' hides the variable declared on line 1."
    assert d.explanation and d.fix_hint


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            in_main("int a = 1;\n{ int a = 2; return a; }"),
            "'a' hides the variable declared on line 2.",
        ),
        ("int n;\nint f(int n) { return n; }", "'n' hides the variable declared on line 1."),
        (
            "int f(int p) { { int p = 2; return p; } }",
            "'p' hides the parameter declared on line 1.",
        ),
        (
            "int helper(void) { return 1; }\nint main(void) { int helper = 2; return helper; }",
            "'helper' hides the function declared on line 1.",
        ),
        (
            in_main("for (int i = 0; i < 1; i++) { int i = 5; i++; }\nreturn 0;"),
            "'i' hides the variable declared on line 2.",
        ),
    ],
)
def test_fires(source: str, message: str) -> None:
    assert shadows(source) == [message]


@pytest.mark.parametrize(
    "source",
    [
        in_main("int a = 1;\n{ int b = a; return b; }"),
        in_main("{ int a = 1; a++; }\n{ int a = 2; return a; }"),  # siblings, not nested
        "int f(int a) { return a; }\nint g(int a) { return a; }",
        "#define N 1\nint main(void) { int N2 = N; return N2; }",
        "int main(void) { int printf = 1; return printf; }",  # library names are not considered
    ],
)
def test_does_not_fire(source: str) -> None:
    assert shadows(source) == []
