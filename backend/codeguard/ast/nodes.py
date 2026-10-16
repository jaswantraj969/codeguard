"""AST node definitions for the CodeGuard C subset (SRS addendum §3.2).

Every node is an immutable dataclass with a source location. Nodes compare by
identity, so later stages can use them as dictionary keys.

Traversal must never recurse (addendum §4.1): use `walk` / `walk_postorder`
from this module, which use an explicit stack.
"""

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Loc:
    line: int
    column: int
    end_line: int
    end_column: int  # exclusive


class Node:
    __slots__ = ()

    loc: Loc

    def children(self) -> tuple["Node", ...]:
        return ()


# --- types ------------------------------------------------------------------


@dataclass(frozen=True, slots=True, eq=False)
class TypeSpec(Node):
    loc: Loc
    base: str  # "int" | "char" | "float" | "double" | "void"
    const: bool

    @property
    def text(self) -> str:
        return f"const {self.base}" if self.const else self.base


# --- expressions ------------------------------------------------------------


@dataclass(frozen=True, slots=True, eq=False)
class IntLiteral(Node):
    loc: Loc
    value: int
    text: str


@dataclass(frozen=True, slots=True, eq=False)
class FloatLiteral(Node):
    loc: Loc
    value: float
    text: str


@dataclass(frozen=True, slots=True, eq=False)
class CharLiteral(Node):
    loc: Loc
    value: int
    text: str


@dataclass(frozen=True, slots=True, eq=False)
class StringLiteral(Node):
    """One or more juxtaposed string literals, already concatenated."""

    loc: Loc
    value: str
    text: str


@dataclass(frozen=True, slots=True, eq=False)
class Identifier(Node):
    loc: Loc
    name: str


@dataclass(frozen=True, slots=True, eq=False)
class Paren(Node):
    loc: Loc
    inner: "Expr"

    def children(self) -> tuple[Node, ...]:
        return (self.inner,)


@dataclass(frozen=True, slots=True, eq=False)
class Unary(Node):
    loc: Loc
    op: str  # "-" | "+" | "!"
    operand: "Expr"

    def children(self) -> tuple[Node, ...]:
        return (self.operand,)


@dataclass(frozen=True, slots=True, eq=False)
class IncDec(Node):
    loc: Loc
    op: str  # "++" | "--"
    prefix: bool
    target: Identifier

    def children(self) -> tuple[Node, ...]:
        return (self.target,)


@dataclass(frozen=True, slots=True, eq=False)
class Binary(Node):
    loc: Loc
    op: str
    left: "Expr"
    right: "Expr"

    def children(self) -> tuple[Node, ...]:
        return (self.left, self.right)


@dataclass(frozen=True, slots=True, eq=False)
class Assign(Node):
    loc: Loc
    op: str  # "=" | "+=" | "-=" | "*=" | "/=" | "%="
    target: Identifier
    value: "Expr"

    def children(self) -> tuple[Node, ...]:
        return (self.target, self.value)


@dataclass(frozen=True, slots=True, eq=False)
class AddressOf(Node):
    """`&name`, allowed only as a direct function-call argument (§2.1)."""

    loc: Loc
    target: Identifier

    def children(self) -> tuple[Node, ...]:
        return (self.target,)


@dataclass(frozen=True, slots=True, eq=False)
class Call(Node):
    loc: Loc
    callee: Identifier
    args: tuple["Expr | AddressOf", ...]

    def children(self) -> tuple[Node, ...]:
        return (self.callee, *self.args)


Expr = (
    IntLiteral
    | FloatLiteral
    | CharLiteral
    | StringLiteral
    | Identifier
    | Paren
    | Unary
    | IncDec
    | Binary
    | Assign
    | Call
)


# --- declarations and statements -------------------------------------------


@dataclass(frozen=True, slots=True, eq=False)
class VarDecl(Node):
    loc: Loc
    type: TypeSpec
    name: str
    name_loc: Loc
    init: Expr | None

    def children(self) -> tuple[Node, ...]:
        return (self.type,) if self.init is None else (self.type, self.init)


@dataclass(frozen=True, slots=True, eq=False)
class DeclStmt(Node):
    loc: Loc
    decls: tuple[VarDecl, ...]

    def children(self) -> tuple[Node, ...]:
        return self.decls


@dataclass(frozen=True, slots=True, eq=False)
class ExprStmt(Node):
    loc: Loc
    expr: Expr

    def children(self) -> tuple[Node, ...]:
        return (self.expr,)


@dataclass(frozen=True, slots=True, eq=False)
class EmptyStmt(Node):
    loc: Loc


@dataclass(frozen=True, slots=True, eq=False)
class Block(Node):
    loc: Loc
    items: tuple["BlockItem", ...]

    def children(self) -> tuple[Node, ...]:
        return self.items


@dataclass(frozen=True, slots=True, eq=False)
class If(Node):
    loc: Loc
    cond: Expr
    then: "Stmt"
    otherwise: "Stmt | None"

    def children(self) -> tuple[Node, ...]:
        if self.otherwise is None:
            return (self.cond, self.then)
        return (self.cond, self.then, self.otherwise)


@dataclass(frozen=True, slots=True, eq=False)
class While(Node):
    loc: Loc
    cond: Expr
    body: "Stmt"

    def children(self) -> tuple[Node, ...]:
        return (self.cond, self.body)


@dataclass(frozen=True, slots=True, eq=False)
class For(Node):
    loc: Loc
    init: DeclStmt | Expr | None
    cond: Expr | None
    update: Expr | None
    body: "Stmt"

    def children(self) -> tuple[Node, ...]:
        parts = (self.init, self.cond, self.update, self.body)
        return tuple(part for part in parts if part is not None)


@dataclass(frozen=True, slots=True, eq=False)
class Return(Node):
    loc: Loc
    value: Expr | None

    def children(self) -> tuple[Node, ...]:
        return () if self.value is None else (self.value,)


@dataclass(frozen=True, slots=True, eq=False)
class Break(Node):
    loc: Loc


@dataclass(frozen=True, slots=True, eq=False)
class Continue(Node):
    loc: Loc


Stmt = Block | If | While | For | Return | Break | Continue | ExprStmt | EmptyStmt
BlockItem = DeclStmt | Stmt


# --- top level ----------------------------------------------------------------


@dataclass(frozen=True, slots=True, eq=False)
class Param(Node):
    loc: Loc
    type: TypeSpec
    name: str | None  # may be omitted in a prototype
    name_loc: Loc | None

    def children(self) -> tuple[Node, ...]:
        return (self.type,)


@dataclass(frozen=True, slots=True, eq=False)
class FunctionDef(Node):
    loc: Loc
    return_type: TypeSpec
    name: str
    name_loc: Loc
    params: tuple[Param, ...]
    body: Block

    def children(self) -> tuple[Node, ...]:
        return (self.return_type, *self.params, self.body)


@dataclass(frozen=True, slots=True, eq=False)
class FunctionProto(Node):
    loc: Loc
    return_type: TypeSpec
    name: str
    name_loc: Loc
    params: tuple[Param, ...]

    def children(self) -> tuple[Node, ...]:
        return (self.return_type, *self.params)


TopLevel = FunctionDef | FunctionProto | DeclStmt


@dataclass(frozen=True, slots=True, eq=False)
class TranslationUnit(Node):
    loc: Loc
    items: tuple[TopLevel, ...]

    def children(self) -> tuple[Node, ...]:
        return self.items


# --- iterative traversal -----------------------------------------------------


def walk(root: Node) -> Iterator[Node]:
    """Yield every node in pre-order (parent before children, left to right)."""
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children()))


def walk_postorder(root: Node) -> Iterator[Node]:
    """Yield every node in post-order (children before parent, left to right)."""
    stack: list[tuple[Node, bool]] = [(root, False)]
    while stack:
        node, expanded = stack.pop()
        if expanded:
            yield node
        else:
            stack.append((node, True))
            stack.extend((child, False) for child in reversed(node.children()))


def depth(root: Node) -> int:
    """Height of the tree rooted at `root` (a lone node has depth 1)."""
    deepest = 0
    stack = [(root, 1)]
    while stack:
        node, level = stack.pop()
        deepest = max(deepest, level)
        stack.extend((child, level + 1) for child in node.children())
    return deepest
