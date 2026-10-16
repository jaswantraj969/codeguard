"""Hand-written recursive-descent parser (SRS addendum §3, §4, §4.1, §7).

Recursion safety (§4.1):
  * Binary operators use an iterative operator-precedence loop, so one level of
    parentheses costs a fixed handful of stack frames whatever the precedence.
  * `else if` chains, unary prefix chains and assignment chains are loops.
  * The remaining recursion (blocks, braceless bodies, parentheses) is bounded
    by MAX_STATEMENT_DEPTH and MAX_PAREN_DEPTH.

Error recovery (§4): on a syntax error the parser records a diagnostic, skips
to the next `;` (consumed) or `}` (left for the enclosing block), skipping any
`{ ... }` group it meets as a whole, and carries on. It stops after
MAX_SYNTAX_ERRORS errors. NESTING_TOO_DEEP ends parsing immediately.
"""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar, NoReturn

from codeguard.ast import nodes as ast
from codeguard.diagnostics import Diagnostic, Severity
from codeguard.lexer.tokens import UNSUPPORTED_KEYWORDS, Token, TokenType

SYN_MISSING_SEMICOLON = "SYN-MISSING-SEMICOLON"
SYN_UNMATCHED_BRACE = "SYN-UNMATCHED-BRACE"
SYN_UNMATCHED_PAREN = "SYN-UNMATCHED-PAREN"
SYN_MALFORMED_EXPR = "SYN-MALFORMED-EXPR"
SYN_UNEXPECTED_TOKEN = "SYN-UNEXPECTED-TOKEN"
UNSUPPORTED_CONSTRUCT = "UNSUPPORTED_CONSTRUCT"
NESTING_TOO_DEEP = "NESTING_TOO_DEEP"

MAX_SYNTAX_ERRORS = 20
MAX_STATEMENT_DEPTH = 64
MAX_PAREN_DEPTH = 64
MAX_CHAIN_LENGTH = 256

TYPE_KEYWORDS = frozenset({"int", "char", "float", "double", "void"})

# Binary operators of the subset and their precedence (higher binds tighter).
BINARY_PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "==": 3, "!=": 3,
    "<": 4, ">": 4, "<=": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "%": 6,
}  # fmt: skip

SUPPORTED_ASSIGNMENTS = frozenset({"=", "+=", "-=", "*=", "/=", "%="})
UNARY_OPERATORS = frozenset({"-", "+", "!"})
INC_DEC = frozenset({"++", "--"})

# --- messages ---------------------------------------------------------------

V1 = "in CodeGuard V1"
MSG_ARRAYS = f"Arrays are not supported {V1}."
MSG_POINTERS = f"Pointers are not supported {V1}."
MSG_STRUCTS = f"Structs, unions and enums are not supported {V1}."
MSG_TYPEDEF = f"typedef is not supported {V1}."
MSG_SWITCH = f"switch statements are not supported {V1}; use if/else."
MSG_DO = f"do/while loops are not supported {V1}; use while."
MSG_GOTO = f"goto is not supported {V1}."
MSG_TERNARY = f"The ?: operator is not supported {V1}; use if/else."
MSG_CASTS = f"Casts are not supported {V1}."
MSG_SIZEOF = f"sizeof is not supported {V1}."
MSG_TYPE_WORDS = f"Only int, char, float, double and void are supported {V1}."
MSG_STORAGE = f"Storage classes and qualifiers other than const are not supported {V1}."
MSG_BITWISE = f"Bitwise operators are not supported {V1}."
MSG_COMMA = f"The comma operator is not supported {V1}."
MSG_VARIADIC = f"Variadic functions ('...') are not supported {V1}."

KEYWORD_MESSAGES = {
    **dict.fromkeys(("struct", "union", "enum"), MSG_STRUCTS),
    "typedef": MSG_TYPEDEF,
    **dict.fromkeys(("switch", "case", "default"), MSG_SWITCH),
    "do": MSG_DO,
    "goto": MSG_GOTO,
    "sizeof": MSG_SIZEOF,
    **dict.fromkeys(("unsigned", "signed", "long", "short"), MSG_TYPE_WORDS),
    **dict.fromkeys(
        ("static", "extern", "register", "auto", "volatile", "inline", "restrict"), MSG_STORAGE
    ),
}

PUNCTUATION_MESSAGES = {
    "[": MSG_ARRAYS,
    "]": MSG_ARRAYS,
    "->": MSG_POINTERS,
    ".": MSG_STRUCTS,
    "?": MSG_TERNARY,
    ":": MSG_TERNARY,
    "...": MSG_VARIADIC,
    **dict.fromkeys(("|", "^", "~", "<<", ">>", "&=", "|=", "^=", "<<=", ">>="), MSG_BITWISE),
}

EXPLAIN_UNSUPPORTED = (
    "CodeGuard V1 analyzes a teaching subset of C. This is valid C but outside that subset, "
    "so the later analysis stages are skipped."
)
EXPLAIN_NESTING = (
    "The code is nested more deeply than CodeGuard allows: 64 levels of blocks, 64 levels of "
    "parentheses, or 256 links in an else-if, unary or assignment chain. Simplify the code, "
    "for example by moving inner parts into separate functions."
)
EXPLAIN_MISSING_SEMICOLON = (
    "In C, every statement and declaration ends with a semicolon. Add ';' at the position shown."
)
EXPLAIN_UNCLOSED_BRACE = (
    "Every '{' needs a matching '}'. Check that each block you opened is closed."
)
EXPLAIN_STRAY_BRACE = "This '}' has no matching '{'. Remove it or add the missing '{'."
EXPLAIN_UNCLOSED_PAREN = "Every '(' needs a matching ')'. Add the missing ')'."
EXPLAIN_STRAY_PAREN = "This ')' has no matching '('. Remove it or add the missing '('."
EXPLAIN_MALFORMED = (
    "The expression is incomplete: an operator is missing an operand, or something other "
    "than a value appears where a value is needed."
)
EXPLAIN_BAD_TARGET = "Only a variable can appear on the left of an assignment or with ++ and --."
EXPLAIN_UNEXPECTED = (
    "This token does not fit here in the C grammar. "
    "Check for a typo or a missing symbol just before it."
)


@dataclass(slots=True)
class ParseResult:
    unit: ast.TranslationUnit
    diagnostics: list[Diagnostic] = field(default_factory=list)
    errors_truncated: bool = False

    @property
    def ok(self) -> bool:
        return not self.diagnostics


def parse(tokens: list[Token]) -> ParseResult:
    """Parse a token list that ends with EOF (the lexer's output)."""
    return _Parser(tokens).run()


class _Recover(Exception):
    """A syntax error was recorded; unwind to the nearest recovery point."""


class _Abort(Exception):
    """Stop parsing entirely (nesting limit or error cap)."""


def _loc(start: Token | ast.Loc, end: Token | ast.Loc) -> ast.Loc:
    return ast.Loc(start.line, start.column, end.end_line, end.end_column)


def _strip_parens(expr: ast.Expr) -> ast.Expr:
    while isinstance(expr, ast.Paren):
        expr = expr.inner
    return expr


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        assert tokens and tokens[-1].type is TokenType.EOF
        self.tokens = tokens
        self.i = 0
        self.diagnostics: list[Diagnostic] = []
        self.errors_truncated = False
        self.last_error_index = -1
        self.statement_depth = 0
        self.paren_depth = 0

    # --- token helpers ----------------------------------------------------

    @property
    def tok(self) -> Token:
        return self.tokens[self.i]

    @property
    def prev(self) -> Token:
        return self.tokens[self.i - 1]

    def peek(self, offset: int = 1) -> Token:
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def at(self, lexeme: str) -> bool:
        tok = self.tok
        return tok.lexeme == lexeme and tok.type not in _LITERAL_TYPES

    def at_eof(self) -> bool:
        return self.tok.type is TokenType.EOF

    def advance(self) -> Token:
        tok = self.tok
        if tok.type is not TokenType.EOF:
            self.i += 1
        return tok

    def accept(self, lexeme: str) -> Token | None:
        return self.advance() if self.at(lexeme) else None

    # --- diagnostics ------------------------------------------------------

    def report(
        self,
        rule_id: str,
        message: str,
        explanation: str,
        where: Token | ast.Loc,
        fix_hint: str | None = None,
    ) -> None:
        if self.i == self.last_error_index:
            return  # never two errors at the same token position
        if len(self.diagnostics) >= MAX_SYNTAX_ERRORS:
            self.errors_truncated = True
            raise _Abort
        self.last_error_index = self.i
        self.diagnostics.append(
            Diagnostic(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=message,
                line=where.line,
                column=where.column,
                end_line=where.end_line,
                end_column=where.end_column,
                explanation=explanation,
                fix_hint=fix_hint,
            )
        )

    def fail(
        self,
        rule_id: str,
        message: str,
        explanation: str,
        where: Token | ast.Loc,
        fix_hint: str | None = None,
    ) -> NoReturn:
        self.report(rule_id, message, explanation, where, fix_hint)
        raise _Recover

    def unsupported(self, message: str, where: Token | ast.Loc | None = None) -> NoReturn:
        self.fail(UNSUPPORTED_CONSTRUCT, message, EXPLAIN_UNSUPPORTED, where or self.tok)

    def too_deep(self, what: str) -> NoReturn:
        self.report(NESTING_TOO_DEEP, f"Too deeply nested: {what}.", EXPLAIN_NESTING, self.tok)
        raise _Abort

    def unsupported_message(self, tok: Token) -> str | None:
        """The UNSUPPORTED_CONSTRUCT message for a token that can never be valid here."""
        if tok.type is TokenType.KEYWORD and tok.lexeme in UNSUPPORTED_KEYWORDS:
            return KEYWORD_MESSAGES.get(tok.lexeme, f"'{tok.lexeme}' is not supported {V1}.")
        if tok.type in _LITERAL_TYPES:
            return None
        return PUNCTUATION_MESSAGES.get(tok.lexeme)

    def unexpected(self, expected: str) -> NoReturn:
        """Report the current token as out of place (unsupported if it is a known construct)."""
        tok = self.tok
        message = self.unsupported_message(tok)
        if message is not None:
            self.unsupported(message)
        if tok.type is TokenType.EOF:
            self.fail(
                SYN_UNEXPECTED_TOKEN,
                f"Unexpected end of file; expected {expected}.",
                EXPLAIN_UNEXPECTED,
                tok,
            )
        self.fail(
            SYN_UNEXPECTED_TOKEN,
            f"Unexpected '{tok.lexeme}'; expected {expected}.",
            EXPLAIN_UNEXPECTED,
            tok,
        )

    def expect(self, lexeme: str, expected: str | None = None) -> Token:
        if self.at(lexeme):
            return self.advance()
        self.unexpected(expected or f"'{lexeme}'")

    def expect_identifier(self, expected: str = "a name") -> Token:
        if self.tok.type is TokenType.IDENTIFIER:
            return self.advance()
        if self.at("*"):
            self.unsupported(MSG_POINTERS)
        self.unexpected(expected)

    def expect_close_paren(self, opener: Token) -> Token:
        if self.at(")"):
            return self.advance()
        if self.unsupported_message(self.tok) is None and (
            self.at(";") or self.at("{") or self.at("}") or self.at_eof()
        ):
            self.fail(
                SYN_UNMATCHED_PAREN,
                f"The '(' on line {opener.line} is never closed.",
                EXPLAIN_UNCLOSED_PAREN,
                opener,
                fix_hint="Add ')' to close it.",
            )
        self.unexpected("')'")

    def expect_semicolon(self) -> None:
        """Consume ';'. A missing ';' at a line end is reported and assumed present."""
        if self.accept(";"):
            return
        tok = self.tok
        if tok.lexeme == ")" and tok.type is TokenType.RPAREN:
            self.fail(
                SYN_UNMATCHED_PAREN, "This ')' has no matching '('.", EXPLAIN_STRAY_PAREN, tok
            )
        if tok.lexeme == "," and tok.type is TokenType.COMMA:
            self.unsupported(MSG_COMMA)
        prev = self.prev
        if self.unsupported_message(tok) is None and (
            tok.type is TokenType.EOF or tok.lexeme == "}" or tok.line > prev.end_line
        ):
            missing = ast.Loc(prev.end_line, prev.end_column, prev.end_line, prev.end_column + 1)
            self.report(
                SYN_MISSING_SEMICOLON,
                "Missing ';' at the end of this statement.",
                EXPLAIN_MISSING_SEMICOLON,
                missing,
                fix_hint="Add ';' here.",
            )
            return
        self.unexpected("';'")

    # --- recovery ---------------------------------------------------------

    def synchronize(self) -> None:
        """Skip to just after the next ';', or to the next '}' (not consumed).

        A '{ ... }' group met on the way is skipped as a whole (with a ';' right
        after it) and ends the skip, so a broken statement does not swallow the
        block that belongs to it.
        """
        while not self.at_eof():
            if self.at(";"):
                self.advance()
                return
            if self.at("}"):
                return
            if self.at("{"):
                self.skip_braced_group()
                self.accept(";")  # e.g. the ';' after `struct S { ... }`
                return
            self.advance()

    def skip_braced_group(self) -> None:
        level = 0
        while not self.at_eof():
            tok = self.advance()
            if tok.type is TokenType.LBRACE:
                level += 1
            elif tok.type is TokenType.RBRACE:
                level -= 1
                if level == 0:
                    return

    def parse_items[T](self, parse_one: Callable[[], T], stop_at_brace: bool) -> list[T]:
        """Parse items until EOF (or '}' when stop_at_brace), recovering after errors."""
        items: list[T] = []
        while not self.at_eof():
            if self.at("}"):
                if stop_at_brace:
                    break
                self.report(
                    SYN_UNMATCHED_BRACE,
                    "This '}' has no matching '{'.",
                    EXPLAIN_STRAY_BRACE,
                    self.tok,
                )
                self.advance()
                continue
            start = self.i
            try:
                items.append(parse_one())
            except _Recover:
                self.synchronize()
                if self.i == start and not self.at("}"):
                    self.advance()  # guarantee progress
        return items

    # --- entry point ------------------------------------------------------

    def run(self) -> ParseResult:
        items: list[ast.TopLevel] = []
        with contextlib.suppress(_Abort):
            items = self.parse_items(self.parse_external_decl, stop_at_brace=False)
        first, last = self.tokens[0], self.tokens[-1]
        unit = ast.TranslationUnit(_loc(first, last), tuple(items))
        return ParseResult(unit, self.diagnostics, self.errors_truncated)

    # --- declarations -----------------------------------------------------

    def at_type_start(self) -> bool:
        tok = self.tok
        if tok.type is not TokenType.KEYWORD:
            return False
        return (
            tok.lexeme in TYPE_KEYWORDS or tok.lexeme == "const" or tok.lexeme in KEYWORD_MESSAGES
        )

    def looks_like_unknown_type(self) -> bool:
        """`name name ...` or `name *name =` at the start of a declaration (§2.4)."""
        if self.tok.type is not TokenType.IDENTIFIER:
            return False
        nxt = self.peek()
        if nxt.type is TokenType.IDENTIFIER:
            return True
        return (
            nxt.lexeme == "*"
            and self.peek(2).type is TokenType.IDENTIFIER
            and self.peek(3).lexeme in ("=", ";", ",", "[")
        )

    def report_unknown_type(self) -> NoReturn:
        self.unsupported(
            f"Unknown type name '{self.tok.lexeme}': only int, char, float, double and void "
            f"are supported (bool, size_t, FILE and typedef names are not)."
        )

    def parse_type(self) -> ast.TypeSpec:
        start = self.tok
        const = self.accept("const") is not None
        tok = self.tok
        if tok.type is TokenType.KEYWORD and tok.lexeme in TYPE_KEYWORDS:
            self.advance()
            if self.at("const"):
                self.unsupported("Write const before the type, e.g. 'const int'.")
            return ast.TypeSpec(_loc(start, tok), tok.lexeme, const)
        if tok.type is TokenType.IDENTIFIER and (self.peek().type is TokenType.IDENTIFIER or const):
            self.report_unknown_type()
        self.unexpected("a type (int, char, float, double or void)")

    def parse_external_decl(self) -> ast.TopLevel:
        if self.looks_like_unknown_type():
            self.report_unknown_type()
        if self.tok.type is TokenType.IDENTIFIER and self.peek().lexeme == "(":
            self.fail(
                SYN_UNEXPECTED_TOKEN,
                f"'{self.tok.lexeme}' needs a return type, e.g. 'int {self.tok.lexeme}(void)'.",
                "In C, a function definition starts with its return type.",
                self.tok,
            )
        if not self.at_type_start():
            self.unexpected("a declaration or function definition")
        start = self.tok
        type_spec = self.parse_type()
        name = self.expect_identifier()
        if self.at("("):
            return self.parse_function(start, type_spec, name)
        return self.finish_declaration(start, type_spec, name)

    def parse_declaration(self) -> ast.DeclStmt:
        start = self.tok
        decl = self.parse_decl_list(start)
        self.expect_semicolon()
        return ast.DeclStmt(_loc(start, self.prev), decl.decls)

    def finish_declaration(
        self, start: Token, type_spec: ast.TypeSpec, name: Token
    ) -> ast.DeclStmt:
        decls = self.parse_declarators(type_spec, name)
        self.expect_semicolon()
        return ast.DeclStmt(_loc(start, self.prev), decls)

    def parse_decl_list(self, start: Token) -> ast.DeclStmt:
        """`decl_specifiers init_declarator { , init_declarator }` without the ';'."""
        type_spec = self.parse_type()
        name = self.expect_identifier()
        if self.at("("):
            self.fail(
                SYN_UNEXPECTED_TOKEN,
                "Functions can only be declared or defined at file scope.",
                "C does not allow a function to be declared inside another function here. "
                "Move it outside, before the function that uses it.",
                self.tok,
            )
        decls = self.parse_declarators(type_spec, name)
        return ast.DeclStmt(_loc(start, self.prev), decls)

    def parse_declarators(self, type_spec: ast.TypeSpec, name: Token) -> tuple[ast.VarDecl, ...]:
        decls = [self.parse_init_declarator(type_spec, name)]
        while self.accept(","):
            if self.at("*"):
                self.unsupported(MSG_POINTERS)
            decls.append(self.parse_init_declarator(type_spec, self.expect_identifier()))
        return tuple(decls)

    def parse_init_declarator(self, type_spec: ast.TypeSpec, name: Token) -> ast.VarDecl:
        if self.at("["):
            self.unsupported(MSG_ARRAYS)
        init: ast.Expr | None = None
        if self.accept("="):
            init = self.parse_expression()
        elif self.tok.type is TokenType.ASSIGNMENT:
            self.unexpected("'=' or ';'")
        end: Token | ast.Loc = name if init is None else init.loc
        return ast.VarDecl(_loc(name, end), type_spec, name.lexeme, _loc(name, name), init)

    def parse_function(
        self, start: Token, return_type: ast.TypeSpec, name: Token
    ) -> ast.FunctionDef | ast.FunctionProto:
        opener = self.expect("(")
        params = self.parse_params()
        self.expect_close_paren(opener)
        if self.at("{"):
            for param in params:
                if param.name is None:
                    self.fail(
                        SYN_UNEXPECTED_TOKEN,
                        "Each parameter of a function definition needs a name.",
                        "Only a prototype may leave parameter names out, e.g. 'int f(int);'.",
                        param.loc,
                    )
            body = self.parse_block()
            return ast.FunctionDef(
                _loc(start, self.prev), return_type, name.lexeme, _loc(name, name), params, body
            )
        self.expect_semicolon()
        return ast.FunctionProto(
            _loc(start, self.prev), return_type, name.lexeme, _loc(name, name), params
        )

    def parse_params(self) -> tuple[ast.Param, ...]:
        if self.at(")"):
            return ()
        if self.at("void") and self.peek().lexeme == ")":
            self.advance()
            return ()
        params = [self.parse_param()]
        while self.accept(","):
            params.append(self.parse_param())
        return tuple(params)

    def parse_param(self) -> ast.Param:
        if self.at("..."):
            self.unsupported(MSG_VARIADIC)
        if self.looks_like_unknown_type() or (
            self.tok.type is TokenType.IDENTIFIER and self.peek().lexeme in ("*", ",", ")")
        ):
            self.report_unknown_type()
        start = self.tok
        type_spec = self.parse_type()
        if self.at("*"):
            self.unsupported(MSG_POINTERS)
        if self.tok.type is TokenType.IDENTIFIER:
            name = self.advance()
            if self.at("["):
                self.unsupported(MSG_ARRAYS)
            return ast.Param(_loc(start, name), type_spec, name.lexeme, _loc(name, name))
        if not (self.at(",") or self.at(")")):
            self.unexpected("a parameter name, ',' or ')'")
        return ast.Param(_loc(start, self.prev), type_spec, None, None)

    # --- statements -------------------------------------------------------

    def enter_statement(self) -> None:
        self.statement_depth += 1
        if self.statement_depth > MAX_STATEMENT_DEPTH:
            self.too_deep(f"more than {MAX_STATEMENT_DEPTH} levels of nested statements")

    def parse_block(self) -> ast.Block:
        opener = self.expect("{")
        self.enter_statement()
        try:
            items = self.parse_items(self.parse_block_item, stop_at_brace=True)
        finally:
            self.statement_depth -= 1
        if not self.accept("}"):
            self.report(
                SYN_UNMATCHED_BRACE,
                f"The '{{' on line {opener.line} is never closed.",
                EXPLAIN_UNCLOSED_BRACE,
                opener,
                fix_hint="Add '}' to close the block.",
            )
        return ast.Block(_loc(opener, self.prev), tuple(items))

    def parse_body(self) -> ast.Stmt:
        """The body of if/else/while/for: a block, or one statement counted as a level."""
        if self.at("{"):
            return self.parse_block()
        self.enter_statement()
        try:
            if self.at_type_start() or self.looks_like_unknown_type():
                if self.unsupported_message(self.tok) is not None:
                    self.unexpected("a statement")
                self.fail(
                    SYN_UNEXPECTED_TOKEN,
                    "A declaration cannot be the whole body of an if, else or loop.",
                    "Wrap the body in braces { } if it needs its own variable.",
                    self.tok,
                )
            return self.parse_statement()
        finally:
            self.statement_depth -= 1

    def parse_block_item(self) -> ast.BlockItem:
        if self.at("{"):
            return self.parse_block()  # skip parse_statement: one frame less per level
        if self.at_type_start():
            return self.parse_declaration()
        if self.looks_like_unknown_type():
            self.report_unknown_type()
        return self.parse_statement()

    def parse_statement(self) -> ast.Stmt:
        tok = self.tok
        if tok.type is TokenType.LBRACE:
            return self.parse_block()
        if tok.type is TokenType.SEMICOLON:
            self.advance()
            return ast.EmptyStmt(_loc(tok, tok))
        if tok.type is TokenType.KEYWORD:
            handler = self.statement_handlers.get(tok.lexeme)
            if handler is not None:
                return handler(self)
            if tok.lexeme in KEYWORD_MESSAGES and tok.lexeme != "sizeof":
                self.unsupported(KEYWORD_MESSAGES[tok.lexeme])
        if tok.type is TokenType.IDENTIFIER and self.peek().lexeme == ":":
            self.unsupported("Labels and goto are not supported in CodeGuard V1.")
        expr = self.parse_expression()
        self.expect_semicolon()
        return ast.ExprStmt(_loc(tok, self.prev), expr)

    def parse_condition(self) -> ast.Expr:
        opener = self.expect("(")
        if self.at(")"):
            self.fail(SYN_MALFORMED_EXPR, "The condition is empty.", EXPLAIN_MALFORMED, self.tok)
        cond = self.parse_expression()
        self.expect_close_paren(opener)
        return cond

    def parse_if(self) -> ast.If:
        links: list[tuple[Token, ast.Expr, ast.Stmt]] = []
        otherwise: ast.Stmt | None = None
        while True:
            if_tok = self.expect("if")
            cond = self.parse_condition()
            then = self.parse_body()
            links.append((if_tok, cond, then))
            if not self.accept("else"):
                break
            if self.at("if"):
                if len(links) > MAX_CHAIN_LENGTH:
                    self.too_deep(f"more than {MAX_CHAIN_LENGTH} links in an else-if chain")
                continue
            otherwise = self.parse_body()
            break
        # Build the chain bottom-up: each `else if` becomes the else branch of the one before.
        node = otherwise
        for if_tok, cond, then in reversed(links):
            end = then.loc if node is None else node.loc
            node = ast.If(_loc(if_tok, end), cond, then, node)
        assert isinstance(node, ast.If)
        return node

    def parse_while(self) -> ast.While:
        start = self.expect("while")
        cond = self.parse_condition()
        body = self.parse_body()
        return ast.While(_loc(start, body.loc), cond, body)

    def parse_for(self) -> ast.For:
        start = self.expect("for")
        opener = self.expect("(")
        init: ast.DeclStmt | ast.Expr | None = None
        if self.at_type_start():
            init = self.parse_decl_list(self.tok)
        elif self.looks_like_unknown_type():
            self.report_unknown_type()
        elif not self.at(";"):
            init = self.parse_expression()
        self.expect_for_separator()
        cond = None if self.at(";") else self.parse_expression()
        self.expect_for_separator()
        update = None if self.at(")") else self.parse_expression()
        if self.at(","):
            self.unsupported(MSG_COMMA)
        self.expect_close_paren(opener)
        body = self.parse_body()
        return ast.For(_loc(start, body.loc), init, cond, update, body)

    def expect_for_separator(self) -> None:
        if self.at(","):
            self.unsupported(MSG_COMMA)
        self.expect(";", "';' between the parts of a for loop")

    def parse_return(self) -> ast.Return:
        start = self.expect("return")
        value = None
        if not self.at(";") and not self.at("}"):
            value = self.parse_expression()
        self.expect_semicolon()
        return ast.Return(_loc(start, self.prev), value)

    def parse_break(self) -> ast.Break:
        start = self.advance()
        self.expect_semicolon()
        return ast.Break(_loc(start, self.prev))

    def parse_continue(self) -> ast.Continue:
        start = self.advance()
        self.expect_semicolon()
        return ast.Continue(_loc(start, self.prev))

    def parse_else_without_if(self) -> NoReturn:
        self.fail(
            SYN_UNEXPECTED_TOKEN,
            "This 'else' has no matching 'if'.",
            "An else must directly follow the statement or block of an if. "
            "Check for a stray ';' after the if's closing ')' or a missing brace.",
            self.tok,
        )

    statement_handlers: ClassVar[dict[str, Callable[["_Parser"], ast.Stmt]]] = {
        "if": parse_if,
        "while": parse_while,
        "for": parse_for,
        "return": parse_return,
        "break": parse_break,
        "continue": parse_continue,
        "else": parse_else_without_if,
    }

    # --- expressions ------------------------------------------------------

    def parse_expression(self) -> ast.Expr:
        """An assignment expression (the subset has no comma operator).

        Right-associative assignment chains are parsed with a loop (§4.1).
        """
        targets: list[tuple[ast.Identifier, str]] = []
        expr = self.parse_binary()
        while self.tok.type is TokenType.ASSIGNMENT:
            op = self.tok
            if op.lexeme not in SUPPORTED_ASSIGNMENTS:
                self.unsupported(MSG_BITWISE)
            target = _strip_parens(expr)
            if not isinstance(target, ast.Identifier):
                self.fail(
                    SYN_MALFORMED_EXPR,
                    f"The left side of '{op.lexeme}' must be a variable.",
                    EXPLAIN_BAD_TARGET,
                    expr.loc,
                )
            if len(targets) >= MAX_CHAIN_LENGTH:
                self.too_deep(f"more than {MAX_CHAIN_LENGTH} chained assignments")
            self.advance()
            targets.append((target, op.lexeme))
            expr = self.parse_binary()
        for target, op_lexeme in reversed(targets):
            expr = ast.Assign(_loc(target.loc, expr.loc), op_lexeme, target, expr)
        return expr

    def parse_binary(self) -> ast.Expr:
        """Iterative operator-precedence parsing of all binary levels (§3.3, §4.1)."""
        operands: list[ast.Expr] = [self.parse_unary()]
        operators: list[str] = []

        def reduce() -> None:
            right = operands.pop()
            left = operands.pop()
            operands.append(ast.Binary(_loc(left.loc, right.loc), operators.pop(), left, right))

        while True:
            tok = self.tok
            precedence = (
                BINARY_PRECEDENCE.get(tok.lexeme) if tok.type is TokenType.OPERATOR else None
            )
            if precedence is None:
                if tok.type is TokenType.OPERATOR and tok.lexeme == "&":
                    self.unsupported(MSG_BITWISE)
                if tok.type is TokenType.OPERATOR and tok.lexeme in PUNCTUATION_MESSAGES:
                    self.unsupported(PUNCTUATION_MESSAGES[tok.lexeme])
                if tok.type is TokenType.LBRACKET:
                    self.unsupported(MSG_ARRAYS)
                break
            while operators and BINARY_PRECEDENCE[operators[-1]] >= precedence:
                reduce()
            operators.append(tok.lexeme)
            self.advance()
            operands.append(self.parse_unary())
        while operators:
            reduce()
        return operands[0]

    def parse_unary(self) -> ast.Expr:
        """Prefix operators, collected with a loop rather than recursion (§4.1)."""
        prefix: list[Token] = []
        while self.tok.type is TokenType.OPERATOR:
            lexeme = self.tok.lexeme
            if lexeme in ("*", "&"):
                self.unsupported(MSG_POINTERS)
            if lexeme == "~":
                self.unsupported(MSG_BITWISE)
            if lexeme in INC_DEC:
                operator = self.advance()
                operand = self.parse_postfix(self.parse_primary())
                target = _strip_parens(operand)
                if not isinstance(target, ast.Identifier):
                    self.fail(
                        SYN_MALFORMED_EXPR,
                        f"'{lexeme}' can only be applied to a variable.",
                        EXPLAIN_BAD_TARGET,
                        operand.loc,
                    )
                expr: ast.Expr = ast.IncDec(_loc(operator, operand.loc), lexeme, True, target)
                return self.wrap_prefix(prefix, expr)
            if lexeme not in UNARY_OPERATORS:
                break
            if len(prefix) >= MAX_CHAIN_LENGTH:
                self.too_deep(f"more than {MAX_CHAIN_LENGTH} unary operators in a row")
            prefix.append(self.advance())
        if self.at("sizeof"):
            self.unsupported(MSG_SIZEOF)
        # Postfix handling is a separate, non-recursive step, so each level of
        # parentheses costs only parse_expression -> parse_binary -> parse_unary
        # -> parse_primary on the stack.
        return self.wrap_prefix(prefix, self.parse_postfix(self.parse_primary()))

    @staticmethod
    def wrap_prefix(prefix: list[Token], expr: ast.Expr) -> ast.Expr:
        for operator in reversed(prefix):
            expr = ast.Unary(_loc(operator, expr.loc), operator.lexeme, expr)
        return expr

    def parse_postfix(self, expr: ast.Expr) -> ast.Expr:
        tok = self.tok
        if tok.type is TokenType.OPERATOR and tok.lexeme in INC_DEC:
            target = _strip_parens(expr)
            if not isinstance(target, ast.Identifier):
                self.fail(
                    SYN_MALFORMED_EXPR,
                    f"'{tok.lexeme}' can only be applied to a variable.",
                    EXPLAIN_BAD_TARGET,
                    expr.loc,
                )
            self.advance()
            expr = ast.IncDec(_loc(expr.loc, tok), tok.lexeme, False, target)
            if self.tok.type is TokenType.OPERATOR and self.tok.lexeme in INC_DEC:
                self.fail(
                    SYN_MALFORMED_EXPR,
                    f"'{self.tok.lexeme}' cannot be applied to the result of '{tok.lexeme}'.",
                    EXPLAIN_BAD_TARGET,
                    self.tok,
                )
        tok = self.tok
        if tok.type is TokenType.LBRACKET:
            self.unsupported(MSG_ARRAYS)
        if tok.lexeme in (".", "->") and tok.type is TokenType.OPERATOR:
            self.unsupported(PUNCTUATION_MESSAGES[tok.lexeme])
        if tok.type is TokenType.LPAREN and not isinstance(expr, ast.Identifier):
            self.fail(
                SYN_MALFORMED_EXPR,
                "Only a function name can be called.",
                "A call must name the function directly, e.g. f(1).",
                tok,
            )
        return expr

    def enter_paren(self) -> None:
        self.paren_depth += 1
        if self.paren_depth > MAX_PAREN_DEPTH:
            self.too_deep(f"more than {MAX_PAREN_DEPTH} levels of nested parentheses")

    def parse_primary(self) -> ast.Expr:
        tok = self.tok
        kind = tok.type
        if kind is TokenType.INTEGER_LITERAL:
            if tok.lexeme[-1] in "uUlL":
                self.unsupported(MSG_TYPE_WORDS)
            self.advance()
            assert isinstance(tok.value, int)
            return ast.IntLiteral(_loc(tok, tok), tok.value, tok.lexeme)
        if kind is TokenType.FLOAT_LITERAL:
            if tok.lexeme[-1] in "lL":
                self.unsupported(MSG_TYPE_WORDS)
            self.advance()
            assert isinstance(tok.value, float)
            return ast.FloatLiteral(_loc(tok, tok), tok.value, tok.lexeme)
        if kind is TokenType.CHAR_LITERAL:
            self.advance()
            assert isinstance(tok.value, int)
            return ast.CharLiteral(_loc(tok, tok), tok.value, tok.lexeme)
        if kind is TokenType.STRING_LITERAL:
            return self.parse_strings()
        if kind is TokenType.IDENTIFIER:
            self.advance()
            name = ast.Identifier(_loc(tok, tok), tok.lexeme)
            if self.at("("):
                return self.parse_call(name)
            return name
        if kind is TokenType.LPAREN:
            nxt = self.peek()
            if nxt.type is TokenType.KEYWORD and (
                nxt.lexeme in TYPE_KEYWORDS
                or nxt.lexeme == "const"
                or nxt.lexeme in KEYWORD_MESSAGES
            ):
                if nxt.lexeme == "sizeof":
                    self.unsupported(MSG_SIZEOF, nxt)
                self.unsupported(MSG_CASTS)
            self.advance()
            self.enter_paren()
            try:
                inner = self.parse_expression()
                if self.at(","):
                    self.unsupported(MSG_COMMA)
                self.expect_close_paren(tok)
            finally:
                self.paren_depth -= 1
            return ast.Paren(_loc(tok, self.prev), inner)
        message = self.unsupported_message(tok)
        if message is not None:
            self.unsupported(message)
        prev = self.prev if self.i > 0 else None
        if prev is not None and prev.type in (TokenType.OPERATOR, TokenType.ASSIGNMENT):
            what = f"Missing a value after '{prev.lexeme}'."
        elif tok.type is TokenType.EOF:
            what = "Expected an expression before the end of the file."
        else:
            what = f"Expected an expression before '{tok.lexeme}'."
        self.fail(SYN_MALFORMED_EXPR, what, EXPLAIN_MALFORMED, tok)

    def parse_strings(self) -> ast.StringLiteral:
        first = self.tok
        parts: list[str] = []
        texts: list[str] = []
        while self.tok.type is TokenType.STRING_LITERAL:
            tok = self.advance()
            assert isinstance(tok.value, str)
            parts.append(tok.value)
            texts.append(tok.lexeme)
        return ast.StringLiteral(_loc(first, self.prev), "".join(parts), " ".join(texts))

    def parse_call(self, callee: ast.Identifier) -> ast.Call:
        opener = self.expect("(")
        self.enter_paren()
        try:
            args: list[ast.Expr | ast.AddressOf] = []
            if not self.at(")"):
                args.append(self.parse_argument())
                while self.accept(","):
                    args.append(self.parse_argument())
            self.expect_close_paren(opener)
        finally:
            self.paren_depth -= 1
        return ast.Call(_loc(callee.loc, self.prev), callee, tuple(args))

    def parse_argument(self) -> ast.Expr | ast.AddressOf:
        """An argument, or `&name` directly as an argument (for scanf, §2.1)."""
        if self.tok.type is TokenType.OPERATOR and self.tok.lexeme == "&":
            amp = self.tok
            name = self.peek()
            if name.type is TokenType.IDENTIFIER and self.peek(2).lexeme in (",", ")"):
                self.advance()
                self.advance()
                target = ast.Identifier(_loc(name, name), name.lexeme)
                return ast.AddressOf(_loc(amp, name), target)
            self.unsupported(MSG_POINTERS)
        return self.parse_expression()


_LITERAL_TYPES = frozenset(
    {
        TokenType.INTEGER_LITERAL,
        TokenType.FLOAT_LITERAL,
        TokenType.CHAR_LITERAL,
        TokenType.STRING_LITERAL,
    }
)
