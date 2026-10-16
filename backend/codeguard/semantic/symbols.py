"""Scopes and symbols (SRS addendum §6)."""

from dataclasses import dataclass, field
from enum import StrEnum

from codeguard import ast
from codeguard.semantic.folding import Const


class ScopeKind(StrEnum):
    FILE = "file"
    FUNCTION = "function"  # parameters and the function's outermost block
    BLOCK = "block"
    FOR = "for"  # a for statement with a declaration in its first clause


class SymbolKind(StrEnum):
    VARIABLE = "variable"
    PARAMETER = "parameter"
    FUNCTION = "function"
    DEFINE = "define"


@dataclass(eq=False, slots=True)
class Symbol:
    name: str
    kind: SymbolKind
    type_text: str
    name_loc: ast.Loc
    decl: ast.Node | None  # VarDecl, Param, FunctionDef/FunctionProto; None for #define
    scope: "Scope"
    is_const: bool = False
    reads: int = 0  # for functions: number of calls
    writes: int = 0
    const_value: Const | None = None  # set only for const variables with a constant initializer
    has_definition: bool = False  # functions only

    @property
    def line(self) -> int:
        return self.name_loc.line

    @property
    def column(self) -> int:
        return self.name_loc.column

    @property
    def is_local_variable(self) -> bool:
        return self.kind is SymbolKind.VARIABLE and self.scope.kind is not ScopeKind.FILE


@dataclass(eq=False, slots=True)
class Scope:
    id: int
    kind: ScopeKind
    name: str | None  # the function name for FUNCTION scopes
    loc: ast.Loc
    parent: "Scope | None"
    children: list["Scope"] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    table: dict[str, Symbol] = field(default_factory=dict)

    def add(self, symbol: Symbol) -> None:
        self.symbols.append(symbol)
        self.table[symbol.name] = symbol


def function_type_text(return_type: ast.TypeSpec, params: tuple[ast.Param, ...]) -> str:
    inner = ", ".join(param.type.text for param in params) if params else "void"
    return f"{return_type.text} ({inner})"
