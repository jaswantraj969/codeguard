"""SEM-UNDECL (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import diagnostics, in_main

RULE = "SEM-UNDECL"


def undeclared(source: str) -> list[tuple[int, int, str]]:
    return [(d.line, d.column, d.message) for d in diagnostics(source, RULE)]


def test_undeclared_variable() -> None:
    # TC-04
    (d,) = diagnostics(in_main("y = 5;\nreturn 0;"), RULE)
    assert (d.line, d.column, d.severity) == (2, 1, Severity.ERROR)
    assert d.message == "'y' is used but never declared."
    assert d.explanation and d.fix_hint == "Declare it first, e.g. 'int y;'."


def test_undeclared_function_call() -> None:
    (d,) = diagnostics(in_main("return compute(2);"), RULE)
    assert d.message == "Function 'compute' is called but never declared."
    assert "printf" in d.explanation


def test_use_before_declaration() -> None:
    assert undeclared(in_main("x = 1;\nint x;\nreturn x;")) == [
        (2, 1, "'x' is used but never declared.")
    ]


def test_global_declared_after_use() -> None:
    assert undeclared("int main(void) { return later; }\nint later = 3;") == [
        (1, 25, "'later' is used but never declared.")
    ]


def test_variable_out_of_scope_after_its_block() -> None:
    assert undeclared(in_main("{ int inner = 1; inner++; }\nreturn inner;")) == [
        (3, 8, "'inner' is used but never declared.")
    ]


def test_for_loop_variable_out_of_scope_after_the_loop() -> None:
    assert len(undeclared(in_main("for (int i = 0; i < 3; i++) { }\nreturn i;"))) == 1


def test_reported_once_per_name_per_function() -> None:
    source = "int f(void) { return q + q + q; }\nint g(void) { return q + r; }\nint h = q;\n"
    assert [(line, msg) for line, _, msg in undeclared(source)] == [
        (1, "'q' is used but never declared."),
        (2, "'q' is used but never declared."),
        (2, "'r' is used but never declared."),
        (3, "'q' is used but never declared."),
    ]


def test_define_used_before_its_line_is_undeclared() -> None:
    assert len(undeclared("int main(void) { return N; }\n#define N 3\n")) == 1


@pytest.mark.parametrize(
    "source",
    [
        # TC-25: library call with #include
        '#include <stdio.h>\nint main(void) { printf("hi"); return 0; }',
        # TC-26: #define name
        "#define N 10\nint main(void) { return N; }",
        # library constants
        "int main(void) { int c = getchar(); return c == EOF; }",
        # call to a function defined later in the file
        "int main(void) { return helper(); }\nint helper(void) { return 1; }",
        # prototype
        "int helper(void);\nint main(void) { return helper(); }",
        # recursion
        "int fact(int n) { return n * fact(n - 1); }",
        # parameters and globals
        "int g = 1;\nint f(int p) { return p + g; }",
        # enclosing scope
        in_main("int x = 1;\n{ { x++; } }\nreturn x;"),
        # other library functions from the data file
        'int main(void) { return abs(-3) + strlen("ab"); }',
    ],
)
def test_does_not_fire(source: str) -> None:
    assert undeclared(source) == []
