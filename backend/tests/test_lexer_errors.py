"""Lexer: LEX-* errors, their positions, and recovery after an error."""

import pytest

from codeguard.diagnostics import Diagnostic, Severity
from codeguard.lexer import tokenize
from codeguard.lexer.lexer import (
    LEX_BAD_CHAR_LITERAL,
    LEX_BAD_ESCAPE,
    LEX_BAD_NUMBER,
    LEX_INVALID_CHAR,
    LEX_UNTERMINATED_CHAR,
    LEX_UNTERMINATED_COMMENT,
    LEX_UNTERMINATED_STRING,
    MAX_LEXICAL_ERRORS,
)


def only_error(source: str) -> Diagnostic:
    diagnostics = tokenize(source).diagnostics
    assert len(diagnostics) == 1, diagnostics
    (diagnostic,) = diagnostics
    assert diagnostic.severity is Severity.ERROR
    assert diagnostic.explanation
    return diagnostic


def test_invalid_character_reports_line_and_column() -> None:
    d = only_error("int x;\nint y @ 2;")
    assert (d.rule_id, d.line, d.column, d.end_column) == (LEX_INVALID_CHAR, 2, 7, 8)
    assert d.message == "Invalid character '@'."


@pytest.mark.parametrize("ch", ["$", "`", "\\", "#"])
def test_other_invalid_characters(ch: str) -> None:
    # '#' is only valid as the first non-blank character of a line.
    assert only_error(f"x {ch} y").rule_id == LEX_INVALID_CHAR


def test_non_ascii_identifier_character_is_invalid() -> None:
    d = only_error("int café;")
    assert (d.rule_id, d.column) == (LEX_INVALID_CHAR, 8)
    assert "U+00E9" in d.message


def test_control_character_is_described_by_code_point() -> None:
    assert only_error("x\x00y").message == "Invalid character U+0000."


def test_lexing_continues_after_an_invalid_character() -> None:
    result = tokenize("a @ b")
    assert [t.lexeme for t in result.tokens] == ["a", "b", ""]


def test_unterminated_string_is_reported_at_the_opening_quote() -> None:
    d = only_error('x = 1;\nputs("hello);\n')
    assert (d.rule_id, d.line, d.column) == (LEX_UNTERMINATED_STRING, 2, 6)
    assert d.fix_hint


def test_unterminated_string_at_end_of_file() -> None:
    assert only_error('"abc').rule_id == LEX_UNTERMINATED_STRING


def test_backslash_newline_inside_string_is_unterminated() -> None:
    # Line splicing is not supported: the string ends at the newline, and the
    # quote on the next line then opens a second unterminated string.
    diagnostics = tokenize('"abc\\\ndef"').diagnostics
    assert [(d.rule_id, d.line) for d in diagnostics] == [
        (LEX_UNTERMINATED_STRING, 1),
        (LEX_UNTERMINATED_STRING, 2),
    ]


def test_scanning_resumes_on_the_next_line_after_unterminated_string() -> None:
    result = tokenize('"oops\nint y = @;')
    assert [d.rule_id for d in result.diagnostics] == [LEX_UNTERMINATED_STRING, LEX_INVALID_CHAR]
    assert [t.lexeme for t in result.tokens][:3] == ["int", "y", "="]


def test_unterminated_char_literal() -> None:
    d = only_error("char c = 'a;\n")
    assert (d.rule_id, d.line, d.column) == (LEX_UNTERMINATED_CHAR, 1, 10)


def test_unterminated_block_comment_is_reported_at_its_start() -> None:
    d = only_error("int x;\n  /* never\nclosed")
    assert (d.rule_id, d.line, d.column, d.end_column) == (LEX_UNTERMINATED_COMMENT, 2, 3, 5)


def test_block_comments_do_not_nest() -> None:
    # The first */ closes the comment, leaving a stray "*/" behind.
    result = tokenize("/* a /* b */ c */")
    assert result.diagnostics == []
    assert [t.lexeme for t in result.tokens] == ["c", "*", "/", ""]


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("''", "Empty character literal"),
        ("'ab'", "more than one character"),
        ("'é'", "not an ASCII character"),
    ],
)
def test_bad_char_literals(source: str, fragment: str) -> None:
    d = only_error(source)
    assert d.rule_id == LEX_BAD_CHAR_LITERAL
    assert fragment in d.message


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        (r'"\q"', "is not a known escape sequence"),
        (r'"\x"', "needs at least one hex digit"),
        (r'"\x100"', "is out of range"),
        (r"'\777'", "is out of range"),
    ],
)
def test_bad_escapes(source: str, fragment: str) -> None:
    d = only_error(source)
    assert d.rule_id == LEX_BAD_ESCAPE
    assert fragment in d.message


def test_bad_escape_position_points_at_the_backslash() -> None:
    d = only_error(r'x = "ab\qc";')
    assert (d.column, d.end_column) == (8, 10)


@pytest.mark.parametrize("source", ["08", "0x", "1e", "123abc", "1.2.3", "0x1G", "1e+"])
def test_bad_numbers(source: str) -> None:
    d = only_error(source)
    assert d.rule_id == LEX_BAD_NUMBER
    assert source in d.message


def test_octal_digit_error_explains_octal() -> None:
    assert "octal" in only_error("x = 09;").explanation


def test_multiple_errors_are_all_reported_in_order() -> None:
    result = tokenize("a @ b\n'xy'\n$")
    assert [(d.rule_id, d.line) for d in result.diagnostics] == [
        (LEX_INVALID_CHAR, 1),
        (LEX_BAD_CHAR_LITERAL, 2),
        (LEX_INVALID_CHAR, 3),
    ]
    assert not result.ok


def test_error_count_is_capped_and_flagged() -> None:
    result = tokenize("@" * (MAX_LEXICAL_ERRORS + 5))
    assert len(result.diagnostics) == MAX_LEXICAL_ERRORS
    assert result.errors_truncated


def test_exactly_the_cap_is_not_flagged() -> None:
    result = tokenize("@" * MAX_LEXICAL_ERRORS)
    assert len(result.diagnostics) == MAX_LEXICAL_ERRORS
    assert not result.errors_truncated
