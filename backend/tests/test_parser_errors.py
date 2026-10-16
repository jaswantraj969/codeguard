"""Parser: SYN-* errors, positions, panic-mode recovery and the error cap."""

import pytest

from codeguard.diagnostics import Severity
from codeguard.parser.parser import (
    MAX_SYNTAX_ERRORS,
    SYN_MALFORMED_EXPR,
    SYN_MISSING_SEMICOLON,
    SYN_UNEXPECTED_TOKEN,
    SYN_UNMATCHED_BRACE,
    SYN_UNMATCHED_PAREN,
)
from tests.parser_helpers import errors, parse_source, rule_ids


def test_missing_semicolon_is_reported_on_the_line_where_it_belongs() -> None:
    (d,) = errors("int main(void) {\n    int x = 5\n    int y = 6;\n    return x + y;\n}")
    assert d.rule_id == SYN_MISSING_SEMICOLON
    assert (d.line, d.column) == (2, 14)  # just after "5"
    assert d.severity is Severity.ERROR
    assert d.explanation and d.fix_hint


def test_missing_semicolon_before_closing_brace() -> None:
    (d,) = errors("int main(void) { return 0 }")
    assert (d.rule_id, d.line, d.column) == (SYN_MISSING_SEMICOLON, 1, 26)


def test_missing_semicolon_after_declaration_at_file_scope() -> None:
    (d,) = errors("int g = 1\nint main(void) { return g; }")
    assert (d.rule_id, d.line) == (SYN_MISSING_SEMICOLON, 1)


def test_missing_semicolon_keeps_the_next_statement() -> None:
    result = parse_source("int main(void) {\n  int a = 1\n  int b = 2;\n}")
    (main,) = result.unit.items
    assert len(main.children()[-1].children()) == 2  # both declarations kept


def test_unclosed_brace_is_reported_at_the_opening_brace() -> None:
    (d,) = errors("int main(void) {\n  if (1) {\n    x = 1;\n}\n")
    assert (d.rule_id, d.line, d.column) == (SYN_UNMATCHED_BRACE, 1, 16)
    assert "never closed" in d.message


def test_stray_closing_brace() -> None:
    (d,) = errors("int main(void) { return 0; }\n}")
    assert (d.rule_id, d.line, d.column) == (SYN_UNMATCHED_BRACE, 2, 1)


def test_unclosed_paren_is_reported_at_the_opening_paren() -> None:
    (d,) = errors("int main(void) {\n  if (x > (1 + 2) {\n    y = 2;\n  }\n}")
    assert (d.rule_id, d.line, d.column) == (SYN_UNMATCHED_PAREN, 2, 6)


def test_unclosed_call_paren() -> None:
    (d,) = errors('int main(void) {\n  printf("hi";\n}')
    assert (d.rule_id, d.line, d.column) == (SYN_UNMATCHED_PAREN, 2, 9)


def test_stray_closing_paren() -> None:
    (d,) = errors("int main(void) { x = 1); }")
    assert (d.rule_id, d.column) == (SYN_UNMATCHED_PAREN, 23)


@pytest.mark.parametrize(
    ("statement", "fragment"),
    [
        ("x = ;", "Missing a value after '='"),
        ("x = 1 + ;", "Missing a value after '+'"),
        ("x = * ;", None),  # unary * is a pointer: unsupported, not malformed
        ("if () x = 1;", "The condition is empty"),
        ("a + b = 3;", "left side of '=' must be a variable"),
        ("5++;", "'++' can only be applied to a variable"),
        ("++(a + b);", "'++' can only be applied to a variable"),
        ("x++++;", "cannot be applied to the result"),
        ("(f)(1);", "Only a function name can be called"),
    ],
)
def test_malformed_expressions(statement: str, fragment: str | None) -> None:
    (d,) = errors("int main(void) { " + statement + " }")
    if fragment is None:
        assert d.rule_id == "UNSUPPORTED_CONSTRUCT"
    else:
        assert d.rule_id == SYN_MALFORMED_EXPR
        assert fragment in d.message


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("main() { return 0; }", "needs a return type"),
        ("int main(void) { int f(void); }", "only be declared or defined at file scope"),
        ("int main(void) { if (x) int y = 1; }", "cannot be the whole body"),
        ("int main(void) { else x = 1; }", "has no matching 'if'"),
        ("int f(int) { return 0; }", "needs a name"),
        ("int main(void) { int 5; }", "expected a name"),
        ("x = 1;", "expected a declaration or function definition"),
        ("int main(void) { return 0; ", None),
    ],
)
def test_unexpected_tokens(source: str, fragment: str | None) -> None:
    diagnostics = errors(source)
    assert diagnostics, source
    if fragment is not None:
        (d,) = diagnostics
        assert d.rule_id == SYN_UNEXPECTED_TOKEN
        assert fragment in d.message


def test_three_independent_errors_are_all_reported() -> None:
    source = "int main(void) {\n  int a = ;\n  b = 2 +;\n  c = (3;\n  return 0;\n}\n"
    assert [(d.rule_id, d.line) for d in errors(source)] == [
        (SYN_MALFORMED_EXPR, 2),
        (SYN_MALFORMED_EXPR, 3),
        (SYN_UNMATCHED_PAREN, 4),
    ]


def test_errors_in_separate_functions_are_all_reported() -> None:
    source = (
        "int f(void) { return 1 + ; }\n"
        "int g(void) { while (x y) { x = 1; } return 0; }\n"
        "int h(void) { int a = 1\n return a; }\n"
    )
    assert [(d.rule_id, d.line) for d in errors(source)] == [
        (SYN_MALFORMED_EXPR, 1),
        (SYN_UNEXPECTED_TOKEN, 2),
        (SYN_MISSING_SEMICOLON, 3),
    ]


def test_recovery_skips_a_whole_block_after_a_broken_header() -> None:
    # The broken while condition must not let its body's '}' close main.
    diagnostics = errors("int main(void) {\n  while (x y) {\n    a = 1;\n  }\n  return 0;\n}\n")
    assert [d.line for d in diagnostics] == [2]


def test_valid_code_after_errors_is_still_in_the_ast() -> None:
    result = parse_source("int f(void) { return 1 + ; }\nint g(void) { return 2; }\n")
    names = [getattr(item, "name", None) for item in result.unit.items]
    assert "g" in names


def test_no_two_errors_at_the_same_token() -> None:
    assert len(errors("int main(void) { x = 1 +")) == 1


def test_error_count_is_capped_at_twenty() -> None:
    source = "int main(void) {\n" + "x = ;\n" * (MAX_SYNTAX_ERRORS + 5) + "}\n"
    result = parse_source(source)
    assert len(result.diagnostics) == MAX_SYNTAX_ERRORS
    assert result.errors_truncated


def test_exactly_twenty_errors_is_not_truncated() -> None:
    source = "int main(void) {\n" + "x = ;\n" * MAX_SYNTAX_ERRORS + "}\n"
    result = parse_source(source)
    assert len(result.diagnostics) == MAX_SYNTAX_ERRORS
    assert not result.errors_truncated


def test_every_syntax_error_has_an_explanation() -> None:
    source = "int main(void) {\n  int a = ;\n  b = 2 +;\n  c = (3;\n  else x;\n}\n}"
    for d in errors(source):
        assert d.explanation, d
        assert d.end_line is not None and d.end_column is not None


def test_valid_input_has_no_diagnostics() -> None:
    assert rule_ids("int main(void) { return 0; }") == []
