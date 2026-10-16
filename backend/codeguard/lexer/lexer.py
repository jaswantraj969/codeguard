"""Hand-written lexer for the CodeGuard C subset (SRS addendum §2.2, §3.4, §5.4).

The lexer scans the whole source, reporting up to MAX_LEXICAL_ERRORS errors.
After an error it skips the offending character, literal or comment and
carries on, so one typo does not hide the rest of the file's tokens.
"""

import re
import string
from dataclasses import dataclass, field

from codeguard.diagnostics import Diagnostic, Severity
from codeguard.lexer.tokens import (
    KEYWORDS,
    OPERATORS_1,
    OPERATORS_2,
    OPERATORS_3,
    Token,
    TokenType,
    operator_type,
)

LEX_INVALID_CHAR = "LEX-INVALID-CHAR"
LEX_UNTERMINATED_STRING = "LEX-UNTERMINATED-STRING"
LEX_UNTERMINATED_CHAR = "LEX-UNTERMINATED-CHAR"
LEX_UNTERMINATED_COMMENT = "LEX-UNTERMINATED-COMMENT"
LEX_BAD_CHAR_LITERAL = "LEX-BAD-CHAR-LITERAL"
LEX_BAD_ESCAPE = "LEX-BAD-ESCAPE"
LEX_BAD_NUMBER = "LEX-BAD-NUMBER"

MAX_LEXICAL_ERRORS = 20

_IDENT_START = frozenset(string.ascii_letters + "_")
_IDENT_CHARS = frozenset(string.ascii_letters + string.digits + "_")
_DIGITS = frozenset(string.digits)
_OCTAL_DIGITS = frozenset("01234567")
_HEX_DIGITS = frozenset(string.hexdigits)
_BLANKS = frozenset(" \t\v\f")
_SIMPLE_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
    "\\": "\\", "'": "'", '"': '"', "?": "?",
}  # fmt: skip

_INT_SUFFIX = r"(?:[uU](?:ll|LL|[lL])?|(?:ll|LL|[lL])[uU]?)?"
_DECIMAL_RE = re.compile(r"([1-9][0-9]*)" + _INT_SUFFIX)
_OCTAL_RE = re.compile(r"(0[0-7]*)" + _INT_SUFFIX)
_HEX_RE = re.compile(r"0[xX]([0-9a-fA-F]+)" + _INT_SUFFIX)
_FLOAT_RE = re.compile(
    r"((?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|[0-9]+[eE][+-]?[0-9]+)[fFlL]?"
)

_EXPLAIN_INVALID_CHAR = (
    "This character is not part of C syntax outside strings and comments. "
    "Delete it, or put it inside a string or comment if it is meant as text."
)
_EXPLAIN_UNTERMINATED_STRING = (
    'A string must end with a closing " on the same line. Add the missing quote.'
)
_EXPLAIN_UNTERMINATED_CHAR = (
    "A character literal must end with a closing ' on the same line, for example 'a'."
)
_EXPLAIN_UNTERMINATED_COMMENT = (
    "A block comment that starts with /* must end with */. "
    "Everything after the /* was treated as part of the comment."
)
_EXPLAIN_BAD_CHAR_LITERAL = (
    "A character literal holds exactly one ASCII character or one escape sequence, "
    "such as 'a' or '\\n'. Use double quotes for text with several characters."
)
_EXPLAIN_BAD_ESCAPE = (
    "Inside quotes, a backslash starts an escape sequence such as \\n (newline), "
    "\\t (tab) or \\0. Write \\\\ for a literal backslash."
)
_EXPLAIN_OCTAL_DIGIT = (
    "Numbers that start with 0 are octal (base 8), so they cannot contain the digits 8 or 9. "
    "Remove the leading 0 to write a decimal number."
)
_EXPLAIN_BAD_NUMBER = (
    "A number can contain only digits, one decimal point, an exponent such as e10, "
    "and a type suffix. Check for a stray letter or a missing space or operator."
)


@dataclass(frozen=True, slots=True)
class Define:
    """An object-like #define. Its value is recorded as text, never expanded."""

    name: str
    value: str
    line: int
    column: int


@dataclass(slots=True)
class LexResult:
    tokens: list[Token]  # always ends with an EOF token
    defines: list[Define]
    diagnostics: list[Diagnostic] = field(default_factory=list)
    errors_truncated: bool = False

    @property
    def ok(self) -> bool:
        return not self.diagnostics


def tokenize(source: str) -> LexResult:
    """Convert C source text into tokens, #define records and lexical errors."""
    return _Lexer(source).run()


def normalize_source(source: str) -> str:
    """Drop a leading BOM and normalise line endings to \\n (§3.4)."""
    if source.startswith("﻿"):
        source = source[1:]
    return source.replace("\r\n", "\n").replace("\r", "\n")


def _describe_char(ch: str) -> str:
    if ch.isprintable() and ch.isascii():
        return f"'{ch}'"
    if ch.isprintable():
        return f"'{ch}' (U+{ord(ch):04X})"
    return f"U+{ord(ch):04X}"


class _Lexer:
    def __init__(self, source: str) -> None:
        self.src = normalize_source(source)
        self.n = len(self.src)
        self.pos = 0
        self.line = 1
        self.line_start = 0  # index of the first character of the current line
        self.at_line_start = True  # only blanks seen since the last newline
        self.tokens: list[Token] = []
        self.defines: list[Define] = []
        self.diagnostics: list[Diagnostic] = []
        self.errors_truncated = False

    # --- position helpers -------------------------------------------------

    def column_of(self, index: int) -> int:
        return index - self.line_start + 1

    def advance_to(self, index: int) -> None:
        """Move to index, keeping line bookkeeping correct across newlines."""
        newlines = self.src.count("\n", self.pos, index)
        if newlines:
            self.line += newlines
            self.line_start = self.src.rfind("\n", self.pos, index) + 1
        self.pos = index

    def error(
        self,
        rule_id: str,
        message: str,
        explanation: str,
        start: int,
        end: int,
        fix_hint: str | None = None,
    ) -> None:
        """Record an error spanning src[start:end] on the current line."""
        if len(self.diagnostics) >= MAX_LEXICAL_ERRORS:
            self.errors_truncated = True
            return
        self.diagnostics.append(
            Diagnostic(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=message,
                line=self.line,
                column=self.column_of(start),
                end_line=self.line,
                end_column=self.column_of(end),
                explanation=explanation,
                fix_hint=fix_hint,
            )
        )

    def emit(
        self, token_type: TokenType, start: int, end: int, value: int | float | str | None = None
    ) -> None:
        self.tokens.append(
            Token(
                type=token_type,
                lexeme=self.src[start:end],
                line=self.line,
                column=self.column_of(start),
                end_line=self.line,
                end_column=self.column_of(end),
                value=value,
            )
        )

    # --- main loop --------------------------------------------------------

    def run(self) -> LexResult:
        src = self.src
        while self.pos < self.n:
            ch = src[self.pos]
            if ch == "\n":
                self.pos += 1
                self.line += 1
                self.line_start = self.pos
                self.at_line_start = True
                continue
            if ch in _BLANKS:
                self.pos += 1
                continue
            if ch == "#" and self.at_line_start:
                self.skip_directive()
                continue
            self.at_line_start = False
            nxt = src[self.pos + 1] if self.pos + 1 < self.n else ""
            if ch == "/" and nxt == "/":
                end = src.find("\n", self.pos)
                self.pos = self.n if end == -1 else end
            elif ch == "/" and nxt == "*":
                self.skip_block_comment()
            elif ch in _IDENT_START:
                self.scan_identifier()
            elif ch in _DIGITS or (ch == "." and nxt in _DIGITS):
                self.scan_number()
            elif ch == '"':
                self.scan_string()
            elif ch == "'":
                self.scan_char()
            else:
                self.scan_operator_or_invalid(ch)

        eof_column = self.column_of(self.pos)
        self.tokens.append(Token(TokenType.EOF, "", self.line, eof_column, self.line, eof_column))
        return LexResult(self.tokens, self.defines, self.diagnostics, self.errors_truncated)

    # --- comments and preprocessor ----------------------------------------

    def skip_block_comment(self) -> None:
        start = self.pos
        end = self.src.find("*/", start + 2)
        if end == -1:
            self.error(
                LEX_UNTERMINATED_COMMENT,
                "This block comment is never closed with */.",
                _EXPLAIN_UNTERMINATED_COMMENT,
                start,
                start + 2,
                fix_hint="Add */ where the comment should end.",
            )
            self.advance_to(self.n)
        else:
            self.advance_to(end + 2)

    def skip_directive(self) -> None:
        """Skip a # line plus any backslash-continued lines (§2.2)."""
        self.record_define()
        end = self.pos
        while True:
            newline = self.src.find("\n", end)
            if newline == -1:
                end = self.n
                break
            if self.src[end:newline].rstrip(" \t").endswith("\\"):
                end = newline + 1
                continue
            end = newline
            break
        self.advance_to(end)

    def record_define(self) -> None:
        """Register `#define NAME value`; ignore function-like macros."""
        src, i = self.src, self.pos + 1
        while i < self.n and src[i] in " \t":
            i += 1
        if not src.startswith("define", i):
            return
        i += len("define")
        if i >= self.n or src[i] not in " \t":
            return
        while i < self.n and src[i] in " \t":
            i += 1
        name_start = i
        if i >= self.n or src[i] not in _IDENT_START:
            return
        while i < self.n and src[i] in _IDENT_CHARS:
            i += 1
        if i < self.n and src[i] == "(":
            return  # function-like macro: ignored (§2.2)
        line_end = src.find("\n", i)
        value = src[i : self.n if line_end == -1 else line_end]
        for marker in ("//", "/*"):
            cut = value.find(marker)
            if cut != -1:
                value = value[:cut]
        self.defines.append(
            Define(
                name=src[name_start:i],
                value=value.strip().rstrip("\\").strip(),
                line=self.line,
                column=self.column_of(name_start),
            )
        )

    # --- tokens -----------------------------------------------------------

    def scan_identifier(self) -> None:
        start, src, i = self.pos, self.src, self.pos + 1
        while i < self.n and src[i] in _IDENT_CHARS:
            i += 1
        word = src[start:i]
        self.emit(TokenType.KEYWORD if word in KEYWORDS else TokenType.IDENTIFIER, start, i)
        self.pos = i

    def scan_number(self) -> None:
        """Scan a C preprocessing number, then validate it against §3.4."""
        start, src, i = self.pos, self.src, self.pos + 1
        while i < self.n:
            c = src[i]
            if c in _IDENT_CHARS or c == ".":
                i += 1
            elif c in "+-" and src[i - 1] in "eEpP":
                i += 1
            else:
                break
        text = src[start:i]
        self.pos = i

        if match := _FLOAT_RE.fullmatch(text):
            self.emit(TokenType.FLOAT_LITERAL, start, i, float(match.group(1)))
        elif match := _HEX_RE.fullmatch(text):
            self.emit(TokenType.INTEGER_LITERAL, start, i, int(match.group(1), 16))
        elif match := _OCTAL_RE.fullmatch(text):
            self.emit(TokenType.INTEGER_LITERAL, start, i, int(match.group(1), 8))
        elif match := _DECIMAL_RE.fullmatch(text):
            self.emit(TokenType.INTEGER_LITERAL, start, i, int(match.group(1)))
        else:
            octal_digit_error = (
                len(text) > 1
                and text[0] == "0"
                and text[1] in _DIGITS
                and all(c in _DIGITS for c in text)
            )
            self.error(
                LEX_BAD_NUMBER,
                f"'{text}' is not a valid number.",
                _EXPLAIN_OCTAL_DIGIT if octal_digit_error else _EXPLAIN_BAD_NUMBER,
                start,
                i,
            )

    def read_escape(self, backslash: int) -> tuple[str | None, int]:
        """Decode the escape starting at src[backslash] == '\\'.

        Returns (decoded character, index after the escape). The character is
        None, and an error is recorded, when the escape is invalid.
        """
        src, i = self.src, backslash + 1
        c = src[i]  # callers guarantee a non-newline character follows
        if c in _SIMPLE_ESCAPES:
            return _SIMPLE_ESCAPES[c], i + 1
        if c in _OCTAL_DIGITS:
            end = i
            while end < min(i + 3, self.n) and src[end] in _OCTAL_DIGITS:
                end += 1
            value = int(src[i:end], 8)
            if value > 0xFF:
                self.bad_escape(backslash, end, "is out of range for a char")
                return None, end
            return chr(value), end
        if c == "x":
            end = i + 1
            while end < self.n and src[end] in _HEX_DIGITS:
                end += 1
            if end == i + 1:
                self.bad_escape(backslash, end, "needs at least one hex digit")
                return None, end
            value = int(src[i + 1 : end], 16)
            if value > 0xFF:
                self.bad_escape(backslash, end, "is out of range for a char")
                return None, end
            return chr(value), end
        self.bad_escape(backslash, i + 1, "is not a known escape sequence")
        return None, i + 1

    def bad_escape(self, start: int, end: int, reason: str) -> None:
        self.error(
            LEX_BAD_ESCAPE,
            f"'{self.src[start:end]}' {reason}.",
            _EXPLAIN_BAD_ESCAPE,
            start,
            end,
        )

    def scan_quoted(self, quote: str) -> tuple[list[tuple[str, bool]], int, bool]:
        """Scan from the opening quote to the closing one on the same line.

        Returns (units, index after the literal, terminated). Each unit is a
        (character, came_from_escape) pair; invalid escapes produce no unit.
        """
        src, i = self.src, self.pos + 1
        units: list[tuple[str, bool]] = []
        while i < self.n:
            c = src[i]
            if c == quote:
                return units, i + 1, True
            if c == "\n":
                break
            if c == "\\":
                if i + 1 >= self.n or src[i + 1] == "\n":
                    i += 1
                    break
                decoded, i = self.read_escape(i)
                if decoded is not None:
                    units.append((decoded, True))
                continue
            units.append((c, False))
            i += 1
        return units, i, False

    def scan_string(self) -> None:
        start = self.pos
        units, end, terminated = self.scan_quoted('"')
        if not terminated:
            self.error(
                LEX_UNTERMINATED_STRING,
                "This string is missing its closing quote.",
                _EXPLAIN_UNTERMINATED_STRING,
                start,
                end,
                fix_hint='Add " at the end of the string.',
            )
        else:
            self.emit(TokenType.STRING_LITERAL, start, end, "".join(c for c, _ in units))
        self.pos = end

    def scan_char(self) -> None:
        start = self.pos
        diagnostics_before = len(self.diagnostics)
        units, end, terminated = self.scan_quoted("'")
        self.pos = end
        if not terminated:
            self.error(
                LEX_UNTERMINATED_CHAR,
                "This character literal is missing its closing quote.",
                _EXPLAIN_UNTERMINATED_CHAR,
                start,
                end,
                fix_hint="Add ' after the character.",
            )
            return
        if len(self.diagnostics) > diagnostics_before:
            return  # an invalid escape was already reported
        literal = self.src[start:end]
        if not units:
            problem = "Empty character literal ''."
        elif len(units) > 1:
            problem = f"{literal} contains more than one character."
        elif not units[0][1] and not units[0][0].isascii():
            problem = f"{literal} is not an ASCII character."
        else:
            self.emit(TokenType.CHAR_LITERAL, start, end, ord(units[0][0]))
            return
        self.error(LEX_BAD_CHAR_LITERAL, problem, _EXPLAIN_BAD_CHAR_LITERAL, start, end)

    def scan_operator_or_invalid(self, ch: str) -> None:
        start, src = self.pos, self.src
        for length, table in ((3, OPERATORS_3), (2, OPERATORS_2), (1, OPERATORS_1)):
            candidate = src[start : start + length]
            if candidate in table:
                self.emit(operator_type(candidate), start, start + length)
                self.pos = start + length
                return
        self.error(
            LEX_INVALID_CHAR,
            f"Invalid character {_describe_char(ch)}.",
            _EXPLAIN_INVALID_CHAR,
            start,
            start + 1,
        )
        self.pos = start + 1
