"""Lexer: token classes, values and positions for valid input."""

import pytest

from codeguard.lexer import Token, TokenType, tokenize
from codeguard.lexer.tokens import SUPPORTED_KEYWORDS, UNSUPPORTED_KEYWORDS

T = TokenType


def lex_ok(source: str) -> list[Token]:
    result = tokenize(source)
    assert result.diagnostics == [], result.diagnostics
    assert result.tokens[-1].type is T.EOF
    return result.tokens[:-1]


def kinds(source: str) -> list[tuple[TokenType, str]]:
    return [(t.type, t.lexeme) for t in lex_ok(source)]


def test_srs_acceptance_example() -> None:
    # SRS §3.3: int x = 10;
    assert kinds("int x = 10;") == [
        (T.KEYWORD, "int"),
        (T.IDENTIFIER, "x"),
        (T.ASSIGNMENT, "="),
        (T.INTEGER_LITERAL, "10"),
        (T.SEMICOLON, ";"),
    ]


def test_empty_and_blank_input_give_only_eof() -> None:
    for source in ("", "   \n\t\n"):
        result = tokenize(source)
        assert result.ok
        assert [t.type for t in result.tokens] == [T.EOF]


@pytest.mark.parametrize("word", sorted(SUPPORTED_KEYWORDS | UNSUPPORTED_KEYWORDS))
def test_every_c_keyword_is_a_keyword(word: str) -> None:
    assert kinds(word) == [(T.KEYWORD, word)]


@pytest.mark.parametrize("word", ["main", "printf", "_tmp", "x1", "bool", "size_t", "Int"])
def test_non_keywords_are_identifiers(word: str) -> None:
    assert kinds(word) == [(T.IDENTIFIER, word)]


def test_positions_are_one_based_with_exclusive_end() -> None:
    tokens = lex_ok("int x;\n  return 0;")
    positions = [(t.lexeme, t.line, t.column, t.end_column) for t in tokens]
    assert positions == [
        ("int", 1, 1, 4),
        ("x", 1, 5, 6),
        (";", 1, 6, 7),
        ("return", 2, 3, 9),
        ("0", 2, 10, 11),
        (";", 2, 11, 12),
    ]


def test_tab_counts_as_one_column() -> None:
    (token,) = lex_ok("\tx")
    assert token.column == 2


def test_crlf_and_cr_line_endings_are_normalised() -> None:
    tokens = lex_ok("a\r\nb\rc")
    assert [(t.lexeme, t.line, t.column) for t in tokens] == [("a", 1, 1), ("b", 2, 1), ("c", 3, 1)]


def test_leading_bom_is_dropped() -> None:
    (token,) = lex_ok("﻿x")
    assert (token.lexeme, token.column) == ("x", 1)


def test_eof_token_position_is_end_of_input() -> None:
    eof = tokenize("x\nab").tokens[-1]
    assert (eof.type, eof.line, eof.column) == (T.EOF, 2, 3)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("a+=b++", ["a", "+=", "b", "++"]),
        ("a---b", ["a", "--", "-", "b"]),
        ("x<=y>=z==w!=v", ["x", "<=", "y", ">=", "z", "==", "w", "!=", "v"]),
        ("p&&q||!r", ["p", "&&", "q", "||", "!", "r"]),
        ("a<<=b>>=c", ["a", "<<=", "b", ">>=", "c"]),
        ("a/b%c*d", ["a", "/", "b", "%", "c", "*", "d"]),
    ],
)
def test_operators_use_longest_match(source: str, expected: list[str]) -> None:
    assert [lexeme for _, lexeme in kinds(source)] == expected


def test_operator_and_punctuation_types() -> None:
    assert kinds("( ) { } [ ] ; , = %= + ->") == [
        (T.LPAREN, "("),
        (T.RPAREN, ")"),
        (T.LBRACE, "{"),
        (T.RBRACE, "}"),
        (T.LBRACKET, "["),
        (T.RBRACKET, "]"),
        (T.SEMICOLON, ";"),
        (T.COMMA, ","),
        (T.ASSIGNMENT, "="),
        (T.ASSIGNMENT, "%="),
        (T.OPERATOR, "+"),
        (T.OPERATOR, "->"),
    ]


def test_unsupported_punctuation_is_lexed_without_errors() -> None:
    # The parser reports these as UNSUPPORTED_CONSTRUCT, not the lexer.
    lexemes = [lexeme for _, lexeme in kinds("a[0] s.f p->f c?1:2 &x a|b a^b ~a a<<1 a>>1 ...")]
    for op in ["[", "]", ".", "->", "?", ":", "&", "|", "^", "~", "<<", ">>", "..."]:
        assert op in lexemes


@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("0", 0),
        ("42", 42),
        ("017", 15),
        ("0x1F", 31),
        ("0XfF", 255),
        ("10u", 10),
        ("10UL", 10),
        ("7ll", 7),
    ],
)
def test_integer_literals(source: str, value: int) -> None:
    (token,) = lex_ok(source)
    assert (token.type, token.lexeme, token.value) == (T.INTEGER_LITERAL, source, value)


@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("1.5", 1.5),
        (".5", 0.5),
        ("1.", 1.0),
        ("1e3", 1000.0),
        ("2.5e-3", 0.0025),
        ("3.0f", 3.0),
        ("1E+2F", 100.0),
        ("1.0L", 1.0),
    ],
)
def test_floating_literals(source: str, value: float) -> None:
    (token,) = lex_ok(source)
    assert (token.type, token.lexeme, token.value) == (T.FLOAT_LITERAL, source, value)


def test_number_followed_by_operator_is_split() -> None:
    assert [lexeme for _, lexeme in kinds("1+2-3e2+x")] == ["1", "+", "2", "-", "3e2", "+", "x"]


@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("'a'", 97),
        ("'0'", 48),
        ("' '", 32),
        ("'\"'", 34),
        (r"'\n'", 10),
        (r"'\t'", 9),
        (r"'\0'", 0),
        (r"'\\'", 92),
        (r"'\''", 39),
        (r"'\x41'", 65),
        (r"'\101'", 65),
        (r"'\?'", 63),
    ],
)
def test_char_literals(source: str, value: int) -> None:
    (token,) = lex_ok(source)
    assert (token.type, token.lexeme, token.value) == (T.CHAR_LITERAL, source, value)


def test_string_literal_value_is_decoded() -> None:
    (token,) = lex_ok(r'"a\tb\n\"q\"\\"')
    assert token.type is T.STRING_LITERAL
    assert token.value == 'a\tb\n"q"\\'


def test_string_may_contain_comment_markers_and_non_ascii() -> None:
    (token,) = lex_ok('"// not /* a comment */ café"')
    assert token.value == "// not /* a comment */ café"


def test_adjacent_strings_are_separate_tokens() -> None:
    assert kinds('"ab" "cd"') == [(T.STRING_LITERAL, '"ab"'), (T.STRING_LITERAL, '"cd"')]


def test_empty_string() -> None:
    (token,) = lex_ok('""')
    assert token.value == ""


def test_comments_are_skipped_and_lines_still_counted() -> None:
    source = "int a; // trailing\n/* block\n   spanning\n   lines */ int b; /**/ int/* x */c;"
    tokens = lex_ok(source)
    assert [t.lexeme for t in tokens] == ["int", "a", ";", "int", "b", ";", "int", "c", ";"]
    b = tokens[4]
    assert (b.line, b.column) == (4, 17)


def test_line_comment_at_end_of_file_without_newline() -> None:
    assert kinds("x // end") == [(T.IDENTIFIER, "x")]


def test_division_is_not_a_comment() -> None:
    assert [lexeme for _, lexeme in kinds("a / b /= c")] == ["a", "/", "b", "/=", "c"]
