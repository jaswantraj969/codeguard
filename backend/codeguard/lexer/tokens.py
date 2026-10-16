"""Token model for the CodeGuard C subset (SRS addendum §3.4)."""

from dataclasses import dataclass
from enum import StrEnum


class TokenType(StrEnum):
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    INTEGER_LITERAL = "INTEGER_LITERAL"
    FLOAT_LITERAL = "FLOAT_LITERAL"
    CHAR_LITERAL = "CHAR_LITERAL"
    STRING_LITERAL = "STRING_LITERAL"
    ASSIGNMENT = "ASSIGNMENT"
    OPERATOR = "OPERATOR"
    SEMICOLON = "SEMICOLON"
    COMMA = "COMMA"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    EOF = "EOF"


SUPPORTED_KEYWORDS = frozenset(
    {
        "int", "char", "float", "double", "void", "const",
        "if", "else", "while", "for", "break", "continue", "return",
    }
)  # fmt: skip

# Reserved C keywords that the parser reports as UNSUPPORTED_CONSTRUCT (§2.4).
UNSUPPORTED_KEYWORDS = frozenset(
    {
        "auto", "case", "default", "do", "enum", "extern", "goto", "inline",
        "long", "register", "restrict", "short", "signed", "sizeof", "static",
        "struct", "switch", "typedef", "union", "unsigned", "volatile",
        "_Alignas", "_Alignof", "_Atomic", "_Bool", "_Complex", "_Generic",
        "_Imaginary", "_Noreturn", "_Static_assert", "_Thread_local",
    }
)  # fmt: skip

KEYWORDS = SUPPORTED_KEYWORDS | UNSUPPORTED_KEYWORDS

ASSIGNMENT_OPERATORS = frozenset(
    {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}
)

PUNCTUATION_TYPES = {
    ";": TokenType.SEMICOLON,
    ",": TokenType.COMMA,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
}

# Every operator and punctuator the lexer recognises, longest first per length.
# Unsupported ones (e.g. "->", "<<", "?") are still lexed so the parser can
# report UNSUPPORTED_CONSTRUCT instead of a confusing lexical error.
OPERATORS_3 = frozenset({"<<=", ">>=", "..."})
OPERATORS_2 = frozenset(
    {
        "++", "--", "->", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
        "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    }
)  # fmt: skip
OPERATORS_1 = frozenset("+-*/%<>=!&|^~?:.,;(){}[]")


def operator_type(lexeme: str) -> TokenType:
    if lexeme in PUNCTUATION_TYPES:
        return PUNCTUATION_TYPES[lexeme]
    if lexeme in ASSIGNMENT_OPERATORS:
        return TokenType.ASSIGNMENT
    return TokenType.OPERATOR


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    lexeme: str
    line: int
    column: int
    end_line: int
    end_column: int  # exclusive
    # Decoded literal value: int for integer and char literals, float for
    # floating literals, str for string literals; None otherwise.
    value: int | float | str | None = None
