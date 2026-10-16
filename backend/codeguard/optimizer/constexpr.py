"""OPT-CONSTEXPR: an arithmetic expression made only of literals (suggestion).

Fires on each *maximal* subexpression built from integer/floating literals with
+ - * / %, unary + -, and parentheses, unless it is already a single literal
(`5`, `-5`, `(5)`). It never fires inside a condition already reported by
SEM-CONSTCOND, or when folding fails (division by zero, overflow), and never
rewrites the user's source (addendum §5.3). Traversal is iterative (§4.1).
"""

from codeguard import ast
from codeguard.diagnostics import Diagnostic, Severity
from codeguard.semantic.folding import fold

RULE_ID = "OPT-CONSTEXPR"

ARITHMETIC_OPERATORS = frozenset({"+", "-", "*", "/", "%"})

EXPLANATION = (
    "This calculation uses only fixed numbers, so its result is always the same. "
    "Writing the result directly can make the code clearer; the compiler does this for you "
    "anyway."
)
INTEGER_DIVISION_NOTE = " Integer division truncates toward zero, so the remainder is dropped."


def _strip_sign_and_parens(node: ast.Node) -> ast.Node:
    while isinstance(node, ast.Paren) or (isinstance(node, ast.Unary) and node.op in "+-"):
        node = node.inner if isinstance(node, ast.Paren) else node.operand
    return node


def is_single_literal(node: ast.Node) -> bool:
    return isinstance(_strip_sign_and_parens(node), ast.IntLiteral | ast.FloatLiteral)


def literal_only_nodes(root: ast.Node) -> set[ast.Node]:
    """Every node whose value is built only from numeric literals and arithmetic."""
    literal_only: set[ast.Node] = set()
    for node in ast.walk_postorder(root):
        match node:
            case ast.IntLiteral() | ast.FloatLiteral():
                ok = True
            case ast.Paren():
                ok = node.inner in literal_only
            case ast.Unary():
                ok = node.op in ("+", "-") and node.operand in literal_only
            case ast.Binary():
                ok = (
                    node.op in ARITHMETIC_OPERATORS
                    and node.left in literal_only
                    and node.right in literal_only
                )
            case _:
                ok = False
        if ok:
            literal_only.add(node)
    return literal_only


def source_text(lines: list[str], loc: ast.Loc) -> str:
    """The source covered by `loc`, with line breaks collapsed to single spaces."""
    if loc.line == loc.end_line:
        return lines[loc.line - 1][loc.column - 1 : loc.end_column - 1]
    parts = [lines[loc.line - 1][loc.column - 1 :]]
    parts += lines[loc.line : loc.end_line - 1]
    parts.append(lines[loc.end_line - 1][: loc.end_column - 1])
    return " ".join(part.strip() for part in parts)


def _has_integer_division(root: ast.Node) -> bool:
    """True if a `/` in this literal-only expression divides two integer operands."""
    has_float: dict[ast.Node, bool] = {}
    for node in ast.walk_postorder(root):
        children = node.children()
        has_float[node] = isinstance(node, ast.FloatLiteral) or any(has_float[c] for c in children)
        if isinstance(node, ast.Binary) and node.op == "/" and not has_float[node]:
            return True
    return False


def check(
    unit: ast.TranslationUnit,
    source_lines: list[str],
    skip: frozenset[ast.Node] = frozenset(),
) -> list[Diagnostic]:
    """Find constant arithmetic. `skip` holds condition nodes SEM-CONSTCOND reported."""
    literal_only = literal_only_nodes(unit)
    diagnostics = []
    stack: list[ast.Node] = [unit]
    while stack:
        node = stack.pop()
        if node in skip:
            continue
        if node not in literal_only:
            stack.extend(reversed(node.children()))
            continue
        # A maximal literal-only expression: report it once, never its parts.
        if is_single_literal(node):
            continue
        value = fold(node)
        if value is None:
            continue  # division by zero (SEM-DIV0's job) or overflow
        text = " ".join(source_text(source_lines, node.loc).split())
        result = value.text()
        explanation = EXPLANATION
        if _has_integer_division(node):
            explanation += INTEGER_DIVISION_NOTE
        diagnostics.append(
            Diagnostic(
                rule_id=RULE_ID,
                severity=Severity.SUGGESTION,
                message=f"'{text}' can be written as {result}.",
                line=node.loc.line,
                column=node.loc.column,
                end_line=node.loc.end_line,
                end_column=node.loc.end_column,
                explanation=explanation,
                fix_hint=f"Replace with {result}.",
            )
        )
    return diagnostics
