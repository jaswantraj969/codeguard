"""SEM-DUP (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import diagnostics, in_main

RULE = "SEM-DUP"


def dups(source: str) -> list[tuple[int, int, str]]:
    return [(d.line, d.column, d.message) for d in diagnostics(source, RULE)]


def test_same_variable_twice_in_a_block() -> None:
    # TC-03
    (d,) = diagnostics(in_main("int x = 1;\nint x = 2;\nreturn x;"), RULE)
    assert (d.line, d.column, d.severity) == (3, 5, Severity.ERROR)
    assert d.message == "'x' is already declared in this scope (line 2)."
    assert d.explanation and d.fix_hint


def test_duplicate_in_one_declaration_list() -> None:
    assert dups("int a, b, a;") == [(1, 11, "'a' is already declared in this scope (line 1).")]


def test_global_duplicate() -> None:
    assert len(dups("int g;\nint g;")) == 1


def test_parameter_and_local_share_a_scope() -> None:
    assert dups("int f(int a) { int a = 2; return a; }") == [
        (1, 20, "'a' is already declared in this scope (line 1).")
    ]


def test_duplicate_parameters() -> None:
    assert len(dups("int f(int a, int a) { return a; }")) == 1


def test_function_defined_twice() -> None:
    assert dups("int f(void) { return 1; }\nint f(void) { return 2; }") == [
        (2, 5, "Function 'f' is already defined (line 1).")
    ]


def test_variable_and_function_with_the_same_name() -> None:
    assert dups("int f;\nint f(void) { return 1; }") == [
        (2, 5, "'f' is already declared in this scope (line 1).")
    ]


@pytest.mark.parametrize(
    "source",
    [
        in_main("int x = 1;\n{ int x = 2; x++; }\nreturn x;"),  # different scopes: shadowing
        "int f(int);\nint f(int a) { return a; }",  # prototype then definition
        "int f(int);\nint f(int);\nint f(int a) { return a; }",  # repeated prototypes
        "#define N 1\n#define N 1\nint main(void) { return N; }",  # repeated #define
        "int f(int a) { return a; }\nint g(int a) { return a; }",  # params of different functions
        in_main("for (int i = 0; i < 2; i++) { }\nfor (int i = 0; i < 2; i++) { }"),
    ],
)
def test_does_not_fire(source: str) -> None:
    assert dups(source) == []
