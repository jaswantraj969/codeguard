"""JSON serialization of the report parts (SRS addendum §8.2).

The AST is written to JSON text with an explicit stack: Python's `json` and
`pickle` both recurse, and a long `1 + 1 + ...` chain makes a very deep tree
(§4.1). The other parts are shallow and use plain dicts.
"""

import json
from typing import Any

from codeguard import ast
from codeguard.diagnostics import Diagnostic
from codeguard.lexer import Token
from codeguard.semantic import Scope

MAX_LABEL_LENGTH = 60


def stage_of(rule_id: str) -> str:
    """The pipeline stage a diagnostic belongs to (lets the UI separate syntax errors)."""
    if rule_id.startswith("LEX-"):
        return "lexical"
    if rule_id.startswith("SYN-") or rule_id in ("UNSUPPORTED_CONSTRUCT", "NESTING_TOO_DEEP"):
        return "syntax"
    if rule_id.startswith("OPT-"):
        return "optimizer"
    return "semantic"


def diagnostic_to_dict(d: Diagnostic) -> dict[str, Any]:
    return {
        "rule_id": d.rule_id,
        "severity": d.severity.value,
        "stage": stage_of(d.rule_id),
        "message": d.message,
        "line": d.line,
        "column": d.column,
        "end_line": d.end_line,
        "end_column": d.end_column,
        "explanation": d.explanation,
        "fix_hint": d.fix_hint,
    }


def token_to_dict(t: Token) -> dict[str, Any]:
    return {"type": t.type.value, "lexeme": t.lexeme, "line": t.line, "column": t.column}


def scope_tree_to_dict(root: Scope) -> dict[str, Any]:
    """The scope tree with each scope's symbols, built iteratively."""

    def convert(scope: Scope) -> dict[str, Any]:
        return {
            "id": scope.id,
            "kind": scope.kind.value,
            "name": scope.name,
            "line": scope.loc.line,
            "symbols": [
                {
                    "name": s.name,
                    "kind": s.kind.value,
                    "type": s.type_text,
                    "line": s.line,
                    "column": s.column,
                    "reads": s.reads,
                    "writes": s.writes,
                }
                for s in scope.symbols
            ],
            "children": [],
        }

    root_dict = convert(root)
    stack = [(root, root_dict)]
    while stack:
        scope, scope_dict = stack.pop()
        for child in scope.children:
            child_dict = convert(child)
            scope_dict["children"].append(child_dict)
            stack.append((child, child_dict))
    return root_dict


def _shorten(text: str) -> str:
    return text if len(text) <= MAX_LABEL_LENGTH else text[: MAX_LABEL_LENGTH - 1] + "…"


def node_label(node: ast.Node) -> str:
    """A short human-readable label for the AST view, e.g. 'BinaryOp +'."""
    match node:
        case ast.FunctionDef():
            return f"FunctionDef {node.name}"
        case ast.FunctionProto():
            return f"FunctionProto {node.name}"
        case ast.Param():
            return f"Param {node.type.text} {node.name}" if node.name else f"Param {node.type.text}"
        case ast.TypeSpec():
            return f"Type {node.text}"
        case ast.DeclStmt():
            return "Declaration"
        case ast.VarDecl():
            return f"VarDecl {node.name}"
        case ast.ExprStmt():
            return "ExpressionStatement"
        case ast.EmptyStmt():
            return "EmptyStatement"
        case ast.Identifier():
            return f"Identifier {node.name}"
        case ast.IntLiteral() | ast.FloatLiteral() | ast.CharLiteral() | ast.StringLiteral():
            return _shorten(f"{type(node).__name__} {node.text}")
        case ast.Binary():
            return f"BinaryOp {node.op}"
        case ast.Unary():
            return f"UnaryOp {node.op}"
        case ast.Assign():
            return f"Assign {node.op}"
        case ast.IncDec():
            return f"{'Prefix' if node.prefix else 'Postfix'} {node.op}"
        case ast.Call():
            return f"Call {node.callee.name}"
        case ast.Paren():
            return "Parenthesized"
    return type(node).__name__


def child_roles(node: ast.Node) -> list[str | None]:
    """Names for the children of nodes whose child order is not self-explanatory."""
    match node:
        case ast.If():
            return ["condition", "then", "else"]
        case ast.While():
            return ["condition", "body"]
        case ast.For():
            parts = [("init", node.init), ("condition", node.cond), ("update", node.update)]
            roles: list[str | None] = [role for role, part in parts if part is not None]
            return [*roles, "body"]
    return [None] * len(node.children())


def ast_to_json(root: ast.Node) -> str:
    """Serialize the AST to JSON text without recursion.

    Each node is {"type", "label", "role", "line", "column", "end_line",
    "end_column", "children": [...]}.
    """
    parts: list[str] = []
    stack: list[tuple[ast.Node, str | None] | str] = [(root, None)]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            parts.append(item)
            continue
        node, role = item
        loc = node.loc
        header = {
            "type": type(node).__name__,
            "label": node_label(node),
            "role": role,
            "line": loc.line,
            "column": loc.column,
            "end_line": loc.end_line,
            "end_column": loc.end_column,
        }
        parts.append(json.dumps(header, ensure_ascii=False)[:-1] + ',"children":[')
        children = node.children()
        roles = child_roles(node)
        stack.append("]}")
        for index in reversed(range(len(children))):
            stack.append((children[index], roles[index]))
            if index > 0:
                stack.append(",")
    return "".join(parts)
