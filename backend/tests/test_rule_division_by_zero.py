"""SEM-DIV0 (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import diagnostics, in_main

RULE = "SEM-DIV0"


def div0(body: str) -> list[str]:
    return [d.message for d in diagnostics(in_main(body), RULE)]


def test_literal_division_by_zero() -> None:
    # TC-05
    (d,) = diagnostics(in_main("int y = 10 / 0;\nreturn y;"), RULE)
    assert (d.line, d.column, d.end_column, d.severity) == (2, 9, 15, Severity.ERROR)
    assert d.message == "Division by zero."
    assert d.explanation and d.fix_hint


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("int x = 4; int y = x % 0; return y;", "Remainder (%) by zero."),  # TC-22
        ("const int z = 0; int x = 4; int y = x / z; return y;", "Division by zero."),  # TC-21
        ("int x = 4; int y = x / (2 - 2); return y;", "Division by zero."),
        ("int x = 4; int y = x / 0.0; return y;", "Division by zero."),
        ("int x = 4; int y = x / '\\0'; return y;", "Division by zero."),
        ("int x = 4; x /= 0; return x;", "Division by zero."),
        ("int x = 4; x %= 0; return x;", "Remainder (%) by zero."),
        ("const int a = 3; const int b = a - 3; int x = 4; return x / b;", "Division by zero."),
        ("int x = 4; return x / (0 && x);", "Division by zero."),
    ],
)
def test_fires(body: str, message: str) -> None:
    assert div0(body) == [message]


def test_global_const_divisor() -> None:
    assert len(diagnostics("const int Z = 0;\nint main(void) { return 5 / Z; }", RULE)) == 1


@pytest.mark.parametrize(
    "body",
    [
        "int x = 4; int y = 2; return x / y;",  # TC-20
        "int x = 4; int z = 0; return x / z;",  # plain variable assigned 0
        "int x = 4; int z; z = 0; return x % z;",
        "int x = 4; return x / 2;",
        "int x = 4; return 0 / x;",  # zero dividend is fine
        "int x = 4; return x * 0;",
        "int x = 4; return x / (x - x);",  # not constant
        "const int z = 1; int x = 4; return x / z;",
        "int x = 4; return x / f();",
    ],
)
def test_does_not_fire(body: str) -> None:
    assert div0(body) == []


def test_defined_zero_is_not_folded() -> None:
    assert diagnostics("#define ZERO 0\nint main(void) { return 1 / ZERO; }", RULE) == []


def test_const_parameter_is_not_constant() -> None:
    assert diagnostics("int f(const int d) { return 10 / d; }", RULE) == []
