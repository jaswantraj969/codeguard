"""Parser: every construct outside the V1 subset gives UNSUPPORTED_CONSTRUCT (§2.4)."""

import pytest

from codeguard.parser.parser import (
    MSG_ARRAYS,
    MSG_BITWISE,
    MSG_CASTS,
    MSG_COMMA,
    MSG_DO,
    MSG_GOTO,
    MSG_POINTERS,
    MSG_SIZEOF,
    MSG_STORAGE,
    MSG_STRUCTS,
    MSG_SWITCH,
    MSG_TERNARY,
    MSG_TYPE_WORDS,
    MSG_TYPEDEF,
    MSG_VARIADIC,
    UNSUPPORTED_CONSTRUCT,
)
from tests.parser_helpers import errors


def in_main(statement: str) -> str:
    return "int main(void) {\n" + statement + "\n}\n"


CASES = [
    # (source, expected message)
    ("int a[5];", MSG_ARRAYS),
    (in_main("int a[5];"), MSG_ARRAYS),
    (in_main("x = a[0];"), MSG_ARRAYS),
    ("int f(int a[]);", MSG_ARRAYS),
    (in_main("int *p;"), MSG_POINTERS),
    (in_main("int a, *p;"), MSG_POINTERS),
    (in_main("x = *p;"), MSG_POINTERS),
    (in_main("x = &y;"), MSG_POINTERS),
    (in_main("f(&y + 1);"), MSG_POINTERS),
    (in_main("x = p->y;"), MSG_POINTERS),
    ("int main(int argc, char *argv[]) { return 0; }", MSG_POINTERS),
    ("char *name(void);", MSG_POINTERS),
    ("struct point { int x; };", MSG_STRUCTS),
    ("union u x;", MSG_STRUCTS),
    ("enum color { RED };", MSG_STRUCTS),
    (in_main("x = s.y;"), MSG_STRUCTS),
    ("typedef int number;", MSG_TYPEDEF),
    (in_main("switch (x) { case 1: break; }"), MSG_SWITCH),
    (in_main("do { x++; } while (x < 3);"), MSG_DO),
    (in_main("goto end;"), MSG_GOTO),
    (in_main("x = a > b ? a : b;"), MSG_TERNARY),
    (in_main("x = (float) y;"), MSG_CASTS),
    (in_main("x = (const int) y;"), MSG_CASTS),
    (in_main("x = sizeof(int);"), MSG_SIZEOF),
    (in_main("x = sizeof x;"), MSG_SIZEOF),
    ("unsigned int x;", MSG_TYPE_WORDS),
    ("long count;", MSG_TYPE_WORDS),
    ("short s;", MSG_TYPE_WORDS),
    ("int long x;", MSG_TYPE_WORDS),
    (in_main("signed char c;"), MSG_TYPE_WORDS),
    ("int x = 10L;", MSG_TYPE_WORDS),
    ("int x = 10u;", MSG_TYPE_WORDS),
    ("double d = 1.0L;", MSG_TYPE_WORDS),
    ("static int counter;", MSG_STORAGE),
    ("extern int shared;", MSG_STORAGE),
    (in_main("register int r;"), MSG_STORAGE),
    (in_main("volatile int v;"), MSG_STORAGE),
    (in_main("x = a | b;"), MSG_BITWISE),
    (in_main("x = a & b;"), MSG_BITWISE),
    (in_main("x = a ^ b;"), MSG_BITWISE),
    (in_main("x = ~a;"), MSG_BITWISE),
    (in_main("x = a << 2;"), MSG_BITWISE),
    (in_main("x = a >> 2;"), MSG_BITWISE),
    (in_main("x |= 1;"), MSG_BITWISE),
    (in_main("x <<= 1;"), MSG_BITWISE),
    (in_main("a = 1, b = 2;"), MSG_COMMA),
    (in_main("for (i = 0, j = 0; i < 3; i++) x = 1;"), MSG_COMMA),
    (in_main("for (i = 0; i < 3; i++, j++) x = 1;"), MSG_COMMA),
    (in_main("x = (a, b);"), MSG_COMMA),
    ("int f(int a, ...);", MSG_VARIADIC),
]


@pytest.mark.parametrize(("source", "message"), CASES)
def test_unsupported_construct_has_specific_message(source: str, message: str) -> None:
    diagnostics = errors(source)
    assert diagnostics, source
    first = diagnostics[0]
    assert first.rule_id == UNSUPPORTED_CONSTRUCT
    assert first.message == message
    assert first.explanation


def test_srs_array_example_message() -> None:
    # TC-27
    (d,) = errors("int main(void) {\n  int a[5];\n  return 0;\n}\n")
    assert (d.rule_id, d.message, d.line, d.column) == (
        UNSUPPORTED_CONSTRUCT,
        "Arrays are not supported in CodeGuard V1.",
        2,
        8,
    )


@pytest.mark.parametrize(
    ("source", "name"),
    [
        (in_main("bool done = 0;"), "bool"),
        (in_main("size_t n;"), "size_t"),
        (in_main("FILE *fp = 0;"), "FILE"),
        ("FILE *log_file;", "FILE"),
        (in_main("for (size_t i = 0; i < 3; i++) x = 1;"), "size_t"),
        ("int f(bool flag);", "bool"),
        ("const bool b = 1;", "bool"),
    ],
)
def test_unknown_type_names(source: str, name: str) -> None:
    d = errors(source)[0]
    assert d.rule_id == UNSUPPORTED_CONSTRUCT
    assert d.message.startswith(f"Unknown type name '{name}'")


def test_labels_are_unsupported() -> None:
    (d,) = errors(in_main("end: return 0;"))
    assert d.rule_id == UNSUPPORTED_CONSTRUCT
    assert "Labels and goto" in d.message


@pytest.mark.parametrize("statement", ['scanf("%d", &x);', 'scanf("%d %f", &a, &b);'])
def test_address_of_as_call_argument_is_supported(statement: str) -> None:
    # TC-35 (parser part): &name directly as an argument is allowed.
    assert errors(in_main(statement)) == []


def test_each_unsupported_construct_is_reported_once_and_recovery_continues() -> None:
    source = in_main("int a[3];\nint *p;\nx = a ? 1 : 2;\nreturn 0;")
    assert [(d.rule_id, d.line) for d in errors(source)] == [
        (UNSUPPORTED_CONSTRUCT, 2),
        (UNSUPPORTED_CONSTRUCT, 3),
        (UNSUPPORTED_CONSTRUCT, 4),
    ]


def test_struct_definition_is_one_diagnostic() -> None:
    assert len(errors("struct s { int x; int y; };\nint main(void) { return 0; }")) == 1
