"""Constant folding with C semantics (addendum §5.2)."""

import pytest

from codeguard import ast
from codeguard.semantic import Const, fold
from tests.parser_helpers import expr_of
from tests.semantic_helpers import analyze_source


def value_of(expression: str) -> Const | None:
    return fold(expr_of(expression))


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("10 + 20", Const(30, False)),
        ("2 + 3 * 4", Const(14, False)),
        ("(2 + 3) * 4", Const(20, False)),
        ("7 / 2", Const(3, False)),
        ("-7 / 2", Const(-3, False)),  # truncates toward zero
        ("7 / -2", Const(-3, False)),
        ("-7 % 3", Const(-1, False)),  # sign of the dividend
        ("7 % -3", Const(1, False)),
        ("7.0 / 2", Const(3.5, True)),
        ("1 + 0.5", Const(1.5, True)),
        ("'a' + 1", Const(98, False)),
        ("10 > 5", Const(1, False)),
        ("10 <= 5", Const(0, False)),
        ("3 == 3", Const(1, False)),
        ("3 != 3", Const(0, False)),
        ("!0", Const(1, False)),
        ("!5", Const(0, False)),
        ("-(3)", Const(-3, False)),
        ("+4", Const(4, False)),
        ("1 && 2", Const(1, False)),
        ("0 || 0.0", Const(0, False)),
        ("2147483647", Const(2147483647, False)),
    ],
)
def test_folds_with_c_semantics(expression: str, expected: Const) -> None:
    assert value_of(expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("0 && x", Const(0, False)),
        ("1 || x", Const(1, False)),
        ("0 && f()", Const(0, False)),
    ],
)
def test_logical_operators_short_circuit(expression: str, expected: Const) -> None:
    assert value_of(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "x",
        "x + 1",
        "1 && x",  # not short-circuited: depends on x
        "0 || x",
        "f(1)",
        '"text"',
        "x = 3",
        "x++",
        "1 / 0",
        "5 % 0",
        "1.0 / 0.0",
        "2147483647 + 1",  # int overflow
        "-2147483647 - 2",
        "3000000000",  # does not fit in an int
        "5.0 % 2",  # % needs integers
        "1e308 * 10",  # not finite
    ],
)
def test_non_constants(expression: str) -> None:
    assert value_of(expression) is None


def test_const_variables_with_constant_initializers_fold() -> None:
    result = analyze_source(
        "const int A = 2;\n"
        "int main(void) {\n"
        "  const int b = A * 3;\n"
        "  const int c = b - 6;\n"
        "  int plain = 4;\n"
        "  const int d = plain;\n"
        "  return b + c + d + plain;\n"
        "}\n"
    )
    values = {s.name: s.const_value for s in result.model.symbols}
    assert values["A"] == Const(2, False)
    assert values["b"] == Const(6, False)
    assert values["c"] == Const(0, False)
    assert values["plain"] is None  # not const
    assert values["d"] is None  # const, but initialized from a variable


def test_const_self_reference_is_not_constant() -> None:
    result = analyze_source("int main(void) { const int a = a + 1; return a; }")
    (a,) = [s for s in result.model.symbols if s.name == "a"]
    assert a.const_value is None


def test_defines_never_fold() -> None:
    result = analyze_source("#define N 0\nint main(void) { return 1 / N; }")
    assert result.diagnostics == []


def test_folding_is_iterative_for_deep_expressions() -> None:
    expr = expr_of(" + ".join(["1"] * 5000))
    assert ast.depth(expr) == 5000
    assert fold(expr) == Const(5000, False)


@pytest.mark.parametrize(
    ("const", "text"),
    [
        (Const(30, False), "30"),
        (Const(-3, False), "-3"),
        (Const(2.5, True), "2.5"),
        (Const(3.0, True), "3.0"),
        (Const(1e20, True), "1e+20"),
    ],
)
def test_const_text(const: Const, text: str) -> None:
    assert const.text() == text
