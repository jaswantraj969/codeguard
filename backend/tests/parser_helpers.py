"""Helpers for parser tests."""

from codeguard import ast
from codeguard.diagnostics import Diagnostic
from codeguard.lexer import tokenize
from codeguard.parser import ParseResult, parse


def parse_source(source: str) -> ParseResult:
    lexed = tokenize(source)
    assert lexed.ok, lexed.diagnostics
    return parse(lexed.tokens)


def parse_ok(source: str) -> ast.TranslationUnit:
    result = parse_source(source)
    assert result.diagnostics == [], result.diagnostics
    return result.unit


def errors(source: str) -> list[Diagnostic]:
    return parse_source(source).diagnostics


def rule_ids(source: str) -> list[str]:
    return [d.rule_id for d in errors(source)]


def body_of(source: str) -> tuple[ast.BlockItem, ...]:
    """Parse `source` as the body of `int main(void) { ... }` and return its items."""
    unit = parse_ok("int main(void) {\n" + source + "\n}")
    main = unit.items[-1]
    assert isinstance(main, ast.FunctionDef)
    return main.body.items


def expr_of(source: str) -> ast.Expr:
    """Parse `source` as an expression statement inside main and return the expression."""
    (stmt,) = body_of(source + ";")
    assert isinstance(stmt, ast.ExprStmt)
    return stmt.expr


def sexpr(node: ast.Node) -> str:
    """A compact, fully parenthesised rendering used to check precedence."""
    match node:
        case ast.IntLiteral() | ast.FloatLiteral() | ast.CharLiteral() | ast.StringLiteral():
            return node.text
        case ast.Identifier():
            return node.name
        case ast.Paren():
            return sexpr(node.inner)
        case ast.Unary():
            return f"({node.op} {sexpr(node.operand)})"
        case ast.IncDec():
            where = "pre" if node.prefix else "post"
            return f"({where}{node.op} {node.target.name})"
        case ast.Binary():
            return f"({node.op} {sexpr(node.left)} {sexpr(node.right)})"
        case ast.Assign():
            return f"({node.op} {node.target.name} {sexpr(node.value)})"
        case ast.AddressOf():
            return f"(& {node.target.name})"
        case ast.Call():
            args = " ".join(sexpr(arg) for arg in node.args)
            return f"(call {node.callee.name}{' ' + args if args else ''})"
    raise AssertionError(f"unexpected node {node!r}")
