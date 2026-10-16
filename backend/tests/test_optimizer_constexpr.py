"""OPT-CONSTEXPR (addendum §5.3): positive and negative cases."""

import pytest

from codeguard.diagnostics import Severity
from codeguard.report import build_report
from tests.semantic_helpers import in_main

RULE = "OPT-CONSTEXPR"


def suggestions(source: str, toggles: dict[str, bool] | None = None) -> list[str]:
    report = build_report(source, toggles)
    return [d.message for d in report.diagnostics if d.rule_id == RULE]


def in_body(body: str) -> str:
    return in_main("int x = 1;\nint y = 2;\n" + body + "\nreturn x + y;")


def test_srs_constant_expression() -> None:
    # TC-08
    report = build_report(in_main("int x = 10 + 20;\nreturn x;"))
    (d,) = [d for d in report.diagnostics if d.rule_id == RULE]
    assert d.message == "'10 + 20' can be written as 30."
    assert (d.line, d.column, d.end_column, d.severity) == (2, 9, 16, Severity.SUGGESTION)
    assert d.fix_hint == "Replace with 30."
    assert d.explanation


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("x = 1 + 2 + 3;", ["'1 + 2 + 3' can be written as 6."]),  # maximal: one suggestion
        ("x = (2 + 3) * 4;", ["'(2 + 3) * 4' can be written as 20."]),
        ("x = -(2 + 3);", ["'-(2 + 3)' can be written as -5."]),
        ("x = 2 * 3 + y;", ["'2 * 3' can be written as 6."]),
        ("x = y + (4 - 1);", ["'(4 - 1)' can be written as 3."]),
        ("x = 1.5 * 2;", ["'1.5 * 2' can be written as 3.0."]),
        ("x = 10 % 4;", ["'10 % 4' can be written as 2."]),
        ("x = f(60 * 60);", ["'60 * 60' can be written as 3600."]),
        ("x = 1 +\n    2;", ["'1 + 2' can be written as 3."]),  # line breaks collapsed
        ("x = y + 1 + 2;", []),  # (y + 1) + 2: no literal-only subexpression
    ],
)
def test_fires_on_maximal_literal_expressions(body: str, expected: list[str]) -> None:
    assert suggestions(in_body(body)) == expected


def test_integer_division_explains_truncation() -> None:
    report = build_report(in_body("x = 7 / 2;"))
    (d,) = [d for d in report.diagnostics if d.rule_id == RULE]
    assert d.message == "'7 / 2' can be written as 3."
    assert "truncates" in d.explanation


def test_global_and_const_initializers() -> None:
    source = "int seconds = 24 * 60 * 60;\nint main(void) { const int k = 2 + 2; return k; }"
    assert suggestions(source) == [
        "'24 * 60 * 60' can be written as 86400.",
        "'2 + 2' can be written as 4.",
    ]


@pytest.mark.parametrize(
    "body",
    [
        "x = 5;",
        "x = -5;",
        "x = (5);",
        "x = -(5);",
        "x = y + 1;",
        "x = 'a' + 1;",  # character literals are excluded
        "x = 1 && 2;",  # not arithmetic
        "x = 3 > 2;",
        "x = 2147483647 + 1;",  # overflow: not folded
        "x = 1e308 * 10;",  # not finite
        "const int k = 2; x = k * 3;",  # const variables are not literals
    ],
)
def test_does_not_fire(body: str) -> None:
    assert suggestions(in_body(body)) == []


def test_division_by_zero_is_only_div0() -> None:
    # TC-05: exactly one diagnostic, from SEM-DIV0.
    report = build_report(in_main("int y = 10 / 0;\nreturn y;"))
    assert [d.rule_id for d in report.diagnostics if d.line == 2] == ["SEM-DIV0"]


def test_expression_containing_a_division_by_zero_is_skipped() -> None:
    assert suggestions(in_body("x = 1 + 2 / 0;")) == []


def test_constant_condition_is_only_constcond() -> None:
    # TC-07: if (10 > 5) gives SEM-CONSTCOND only, and its parts are not suggested.
    report = build_report(in_body("if (2 + 3 > 4) x = 3;"))
    assert [d.rule_id for d in report.diagnostics if d.line == 4] == ["SEM-CONSTCOND"]


def test_non_constant_condition_can_contain_a_suggestion() -> None:
    assert suggestions(in_body("while (2 + 3 > x) x++;")) == ["'2 + 3' can be written as 5."]


def test_condition_is_suggested_when_constcond_is_off() -> None:
    toggles = {"SEM-CONSTCOND": False}
    assert suggestions(in_body("if (2 + 3 > 4) x = 3;"), toggles) == [
        "'2 + 3' can be written as 5."
    ]


def test_can_be_turned_off() -> None:
    assert suggestions(in_body("x = 1 + 2;"), {RULE: False}) == []


def test_source_is_never_rewritten() -> None:
    source = in_body("x = 1 + 2;")
    report = build_report(source)
    assert any(d.rule_id == RULE for d in report.diagnostics)
    assert "1 + 2" in source  # FR-OPT-06: suggestions only
