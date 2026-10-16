"""SEM-CONSTCOND (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from tests.semantic_helpers import analyze_source, diagnostics, in_main

RULE = "SEM-CONSTCOND"

ALWAYS_FALSE_IF = "The condition is always false, so this branch never runs."
ALWAYS_TRUE_ELSE = "The condition is always true, so the else branch never runs."
ALWAYS_TRUE_IF = "The condition is always true, so the if is unnecessary."
LOOP_NEVER_RUNS = "The condition is always false, so the loop body never runs."
LOOP_NEVER_ENDS = "The condition is always true, so this loop never ends unless it breaks."


def messages(body: str) -> list[str]:
    return [d.message for d in diagnostics(in_main("int x = 1;\n" + body + "\nreturn x;"), RULE)]


def test_srs_demo_constant_comparison() -> None:
    # TC-07: if (10 > 5)
    (d,) = diagnostics(in_main("int x = 1;\nif (10 > 5) {\n  x = 2;\n}\nreturn x;"), RULE)
    assert (d.line, d.column, d.end_column, d.severity) == (3, 5, 11, Severity.WARNING)
    assert d.message == ALWAYS_TRUE_IF
    assert d.explanation


def test_if_zero_gives_exactly_one_diagnostic() -> None:
    # TC-24
    found = diagnostics(
        in_main("int x = 1;\nif (0) {\n  x = 2;\n  return 3;\n  x = 4;\n}\nreturn x;")
    )
    in_if = sorted((d.line, d.rule_id, d.message) for d in found if d.line in (3, 4, 5, 6))
    assert [(rule, message) for _, rule, message in in_if] == [
        (RULE, ALWAYS_FALSE_IF),
        ("SEM-UNREACH", "This code can never run."),  # x = 4 after the return: a separate construct
    ]
    assert [d.rule_id for d in found if d.line == 3] == [RULE]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("if (0) x = 2;", ALWAYS_FALSE_IF),
        ("if (1) x = 2; else x = 3;", ALWAYS_TRUE_ELSE),
        ("if (2 > 1) x = 2;", ALWAYS_TRUE_IF),
        ("if ((3)) x = 2;", ALWAYS_TRUE_IF),
        ("while (0) x++;", LOOP_NEVER_RUNS),
        ("while (2) { break; }", LOOP_NEVER_ENDS),
        ("while (1 == 1) { break; }", LOOP_NEVER_ENDS),
        ("for (;1;) { break; }", LOOP_NEVER_ENDS),
        ("for (x = 0; 0; x++) { }", LOOP_NEVER_RUNS),
        ("if (0 && x) x = 2;", ALWAYS_FALSE_IF),
        ("if ('a') x = 2;", ALWAYS_TRUE_IF),
    ],
)
def test_fires(body: str, expected: str) -> None:
    assert messages(body) == [expected]


def test_const_variable_condition() -> None:
    assert messages("const int DEBUG = 0;\nif (DEBUG) x = 2;") == [ALWAYS_FALSE_IF]


def test_loop_hint_suggests_the_idiomatic_form() -> None:
    (d,) = diagnostics(in_main("for (;1;) { break; }"), RULE)
    assert d.fix_hint is not None and "for (;;)" in d.fix_hint


@pytest.mark.parametrize(
    "body",
    [
        "while (1) { break; }",  # TC-23
        "while ((1)) { break; }",
        "for (;;) { break; }",
        "if (x) x = 2;",
        "if (x > 0) x = 2;",
        "while (x < 10) x++;",
        "for (x = 0; x < 3; x++) { }",
        "if (1 && x) x = 2;",
        "if (x = 0) x = 2;",  # assignment: not folded
        "if (f()) x = 2;",
    ],
)
def test_does_not_fire(body: str) -> None:
    assert messages(body) == []


def test_define_and_library_names_are_not_folded() -> None:
    source = "#define TRUE 1\nint main(void) { while (TRUE) { break; } if (EOF) { } return 0; }"
    assert diagnostics(source, RULE) == []


def test_reported_conditions_are_exposed_for_the_optimizer() -> None:
    result = analyze_source(in_main("int x = 1;\nif (10 > 5) x = 2;\nreturn x;"))
    (cond,) = result.constant_conditions
    assert (cond.loc.line, cond.loc.column) == (3, 5)
