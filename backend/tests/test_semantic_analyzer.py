"""Semantic stage: rule toggles, one diagnostic per construct, and robustness."""

from codeguard.semantic import ALWAYS_ON, TOGGLEABLE
from tests.c_samples import worst_case
from tests.semantic_helpers import analyze_source, in_main, rule_ids
from tests.test_parser_limits import run_within_frame_budget


def test_toggleable_rules() -> None:
    assert sorted(TOGGLEABLE) == [
        "SEM-CONSTCOND",
        "SEM-DIV0",
        "SEM-DUP",
        "SEM-SHADOW",
        "SEM-UNDECL",
        "SEM-UNREACH",
        "SEM-UNUSED",
    ]
    assert sorted(ALWAYS_ON) == ["SEM-BREAK-CONTEXT"]


def test_rules_can_be_turned_off() -> None:
    source = in_main("int unused = 1;\nif (0) { }\nreturn y;")
    assert rule_ids(source) == ["SEM-UNDECL", "SEM-UNUSED", "SEM-CONSTCOND"]
    result = analyze_source(source, {"SEM-UNUSED": False, "SEM-CONSTCOND": False})
    assert [d.rule_id for d in result.diagnostics] == ["SEM-UNDECL"]
    assert result.constant_conditions == frozenset()


def test_shadowing_wins_over_unused_on_the_same_declaration() -> None:
    source = "int x;\nint main(void) {\n  int x = 1;\n  return 0;\n}\n"
    assert rule_ids(source) == ["SEM-SHADOW"]


def test_unused_shows_when_shadowing_is_turned_off() -> None:
    source = "int x;\nint main(void) {\n  int x = 1;\n  return 0;\n}\n"
    result = analyze_source(source, {"SEM-SHADOW": False})
    assert [d.rule_id for d in result.diagnostics] == ["SEM-UNUSED"]


def test_duplicate_declaration_gets_only_the_duplicate_error() -> None:
    # The second `a` is not entered in the table, so it cannot also be unused or shadowing.
    source = "int a;\nint main(void) {\n  int b = 1;\n  int b = 2;\n  return b;\n}\n"
    assert rule_ids(source) == ["SEM-DUP"]


def test_srs_demo_diagnostics() -> None:
    source = (
        "#include <stdio.h>\n"
        "int main(void) {\n"
        "    int x = 10;\n"
        "    int unused = 50;\n"
        "    if (10 > 5) {\n"
        '        printf("%d\\n", x);\n'
        "    }\n"
        "    return 0;\n"
        "}\n"
    )
    assert [(d.rule_id, d.line) for d in analyze_source(source).diagnostics] == [
        ("SEM-UNUSED", 4),
        ("SEM-CONSTCOND", 5),
    ]


def test_every_semantic_diagnostic_has_an_explanation_and_location() -> None:
    source = (
        "int g;\nint g;\n"
        "int main(void) {\n"
        "  int unused = 1;\n"
        "  int x = 1 / 0;\n"
        "  if (0) { }\n"
        "  { int x = 2; x++; }\n"
        "  return y;\n"
        "  x = 1;\n"
        "}\n"
        "void f(void) { break; }\n"
    )
    found = analyze_source(source).diagnostics
    assert {d.rule_id for d in found} == {
        "SEM-DUP",
        "SEM-UNUSED",
        "SEM-DIV0",
        "SEM-CONSTCOND",
        "SEM-SHADOW",
        "SEM-UNDECL",
        "SEM-UNREACH",
        "SEM-BREAK-CONTEXT",
    }
    for d in found:
        assert d.explanation and d.end_line is not None and d.end_column is not None


def test_worst_case_analysis_within_the_frame_budget() -> None:
    # TC-38 (semantic part): resolver, folding and every rule are iterative.
    result = run_within_frame_budget(lambda: analyze_source(worst_case()))
    assert result.model.symbols


def test_long_expression_chain_is_safe() -> None:
    source = in_main(
        "int x = "
        + " + ".join(["1"] * 5000)
        + ";\nif ("
        + " + ".join(["x"] * 5000)
        + ") { }\nreturn x;"
    )
    result = run_within_frame_budget(lambda: analyze_source(source))
    assert [d.rule_id for d in result.diagnostics] == []
