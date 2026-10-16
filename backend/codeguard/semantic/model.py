"""Name resolution: builds the scope tree, symbols and use counts (SRS addendum §5, §6).

The resolver is one iterative pass over the AST (explicit work stack, §4.1).
It records the facts the rules need: duplicate declarations, shadowing,
undeclared uses, which symbol each identifier refers to, read/write counts,
and the constant value of each const variable.

Reads and writes (SEM-UNUSED, §5.3): the left side of `=`, `&x` in a call, and
an increment or compound assignment whose value is not used (a standalone
statement or a for-loop clause) are writes only. Every other use is a read.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

from codeguard import ast
from codeguard.lexer import Define
from codeguard.semantic.folding import Const, fold
from codeguard.semantic.library import LibraryNames, load_library
from codeguard.semantic.symbols import (
    Scope,
    ScopeKind,
    Symbol,
    SymbolKind,
    function_type_text,
)


@dataclass(frozen=True, slots=True)
class Duplicate:
    decl: ast.Node  # the second declaration (VarDecl, Param, FunctionDef or FunctionProto)
    name: str
    name_loc: ast.Loc
    first: Symbol


@dataclass(frozen=True, slots=True)
class Shadow:
    symbol: Symbol
    outer: Symbol


@dataclass(frozen=True, slots=True)
class UndeclaredUse:
    identifier: ast.Identifier
    is_call: bool
    function: str | None  # enclosing function, None at file scope


@dataclass(slots=True)
class SemanticModel:
    unit: ast.TranslationUnit
    file_scope: Scope
    scopes: list[Scope]
    symbols: list[Symbol]  # every user symbol in declaration order (defines included)
    resolved: dict[ast.Identifier, Symbol]
    duplicates: list[Duplicate] = field(default_factory=list)
    shadows: list[Shadow] = field(default_factory=list)
    undeclared: list[UndeclaredUse] = field(default_factory=list)

    def const_lookup(self, identifier: ast.Identifier) -> Const | None:
        symbol = self.resolved.get(identifier)
        return None if symbol is None else symbol.const_value

    def fold(self, expr: ast.Node) -> Const | None:
        return fold(expr, self.const_lookup)


class _Library:
    """Marker for names resolved to the built-in library list."""


LIBRARY: Final = _Library()

# Work-stack items. ("node", node, value_used) visits a node; the others are
# markers that run after the nodes pushed above them have been processed.
_Item = (
    tuple[str, ast.Node, bool]  # ("node", node, value_used)
    | tuple[str]  # ("pop_scope",) / ("end_function",)
    | tuple[str, Symbol]  # ("const_value", symbol)
)


def build_model(
    unit: ast.TranslationUnit,
    defines: Iterable[Define] = (),
    library: LibraryNames | None = None,
) -> SemanticModel:
    return _Resolver(unit, list(defines), library or load_library()).run()


class _Resolver:
    def __init__(
        self, unit: ast.TranslationUnit, defines: list[Define], library: LibraryNames
    ) -> None:
        self.unit = unit
        self.library = library
        self.file_scope = Scope(0, ScopeKind.FILE, None, unit.loc, None)
        self.scopes = [self.file_scope]
        self.current = self.file_scope
        self.current_function: str | None = None
        self.symbols: list[Symbol] = []
        self.resolved: dict[ast.Identifier, Symbol] = {}
        self.duplicates: list[Duplicate] = []
        self.shadows: list[Shadow] = []
        self.undeclared: list[UndeclaredUse] = []

        # Functions resolve file-wide (§5.3), so collect each one's first declaration up front.
        self.functions: dict[str, Symbol] = {}
        for item in unit.items:
            if isinstance(item, ast.DeclStmt) or item.name in self.functions:
                continue
            self.functions[item.name] = Symbol(
                name=item.name,
                kind=SymbolKind.FUNCTION,
                type_text=function_type_text(item.return_type, item.params),
                name_loc=item.name_loc,
                decl=item,
                scope=self.file_scope,
            )

        # #define names are visible from their line onward.
        self.defines: dict[str, Symbol] = {}
        for define in defines:
            if define.name in self.defines:
                continue
            loc = ast.Loc(define.line, define.column, define.line, define.column + len(define.name))
            symbol = Symbol(
                name=define.name,
                kind=SymbolKind.DEFINE,
                type_text=f"#define {define.value}".rstrip(),
                name_loc=loc,
                decl=None,
                scope=self.file_scope,
            )
            self.defines[define.name] = symbol
            self.file_scope.symbols.append(symbol)  # listed, but resolved via self.defines
            self.symbols.append(symbol)

    # --- scopes -------------------------------------------------------------

    def open_scope(self, kind: ScopeKind, loc: ast.Loc, name: str | None = None) -> None:
        scope = Scope(len(self.scopes), kind, name, loc, self.current)
        self.current.children.append(scope)
        self.scopes.append(scope)
        self.current = scope

    def close_scope(self) -> None:
        assert self.current.parent is not None
        self.current = self.current.parent

    def lookup(self, name: str, line: int) -> Symbol | _Library | None:
        scope: Scope | None = self.current
        while scope is not None:
            symbol = scope.table.get(name)
            if symbol is not None:
                return symbol
            scope = scope.parent
        if name in self.functions:
            return self.functions[name]
        define = self.defines.get(name)
        if define is not None and define.line < line:
            return define
        if name in self.library:
            return LIBRARY
        return None

    def lookup_outer(self, name: str) -> Symbol | None:
        """A user variable, parameter or function visible from an enclosing scope."""
        if self.current is self.file_scope:
            return None
        scope = self.current.parent
        while scope is not None:
            symbol = scope.table.get(name)
            if symbol is not None and symbol.kind is not SymbolKind.DEFINE:
                return symbol
            scope = scope.parent
        return self.functions.get(name)

    # --- declarations -------------------------------------------------------

    def declare(
        self,
        decl: ast.VarDecl | ast.Param,
        name: str,
        name_loc: ast.Loc,
        kind: SymbolKind,
        type_spec: ast.TypeSpec,
    ) -> Symbol | None:
        existing = self.current.table.get(name)
        if existing is not None:
            self.duplicates.append(Duplicate(decl, name, name_loc, existing))
            return None
        symbol = Symbol(
            name=name,
            kind=kind,
            type_text=type_spec.text,
            name_loc=name_loc,
            decl=decl,
            scope=self.current,
            is_const=type_spec.const,
        )
        outer = self.lookup_outer(name)
        if outer is not None:
            self.shadows.append(Shadow(symbol, outer))
        self.current.add(symbol)
        self.symbols.append(symbol)
        return symbol

    def declare_function(self, item: ast.FunctionDef | ast.FunctionProto) -> None:
        symbol = self.functions[item.name]
        existing = self.file_scope.table.get(item.name)
        if existing is None:
            self.file_scope.add(symbol)
            self.symbols.append(symbol)
        elif existing is not symbol:  # a global variable of the same name came first
            self.duplicates.append(Duplicate(item, item.name, item.name_loc, existing))
            return
        if isinstance(item, ast.FunctionDef):
            if symbol.has_definition:
                self.duplicates.append(Duplicate(item, item.name, item.name_loc, symbol))
            symbol.has_definition = True

    # --- uses -----------------------------------------------------------------

    def use(
        self, identifier: ast.Identifier, *, read: bool, write: bool, call: bool = False
    ) -> None:
        symbol = self.lookup(identifier.name, identifier.loc.line)
        if symbol is LIBRARY:
            return
        if symbol is None:
            self.undeclared.append(UndeclaredUse(identifier, call, self.current_function))
            return
        assert isinstance(symbol, Symbol)
        self.resolved[identifier] = symbol
        if read:
            symbol.reads += 1
        if write:
            symbol.writes += 1

    # --- traversal --------------------------------------------------------------

    def run(self) -> SemanticModel:
        stack: list[_Item] = [("node", self.unit, False)]
        while stack:
            item = stack.pop()
            match item:
                case ("node", ast.Node() as node, bool(value_used)):
                    self.visit(node, value_used, stack)
                case ("pop_scope",):
                    self.close_scope()
                case ("end_function",):
                    self.current_function = None
                case ("const_value", Symbol() as symbol):
                    assert isinstance(symbol.decl, ast.VarDecl) and symbol.decl.init is not None
                    symbol.const_value = fold(symbol.decl.init, self.const_lookup)
        self.file_scope.symbols.sort(key=lambda s: (s.line, s.column))
        self.symbols.sort(key=lambda s: (s.line, s.column))
        return SemanticModel(
            unit=self.unit,
            file_scope=self.file_scope,
            scopes=self.scopes,
            symbols=self.symbols,
            resolved=self.resolved,
            duplicates=self.duplicates,
            shadows=self.shadows,
            undeclared=self.undeclared,
        )

    def const_lookup(self, identifier: ast.Identifier) -> Const | None:
        symbol = self.resolved.get(identifier)
        return None if symbol is None else symbol.const_value

    def visit(self, node: ast.Node, value_used: bool, stack: list[_Item]) -> None:
        def push(child: ast.Node | None, used: bool = True) -> None:
            if child is not None:
                stack.append(("node", child, used))

        match node:
            # --- top level and declarations ---
            case ast.TranslationUnit():
                for item in reversed(node.items):
                    push(item)
            case ast.FunctionProto():
                self.declare_function(node)
            case ast.FunctionDef():
                self.declare_function(node)
                self.open_scope(ScopeKind.FUNCTION, node.loc, node.name)
                self.current_function = node.name
                for param in node.params:
                    if param.name is not None and param.name_loc is not None:
                        self.declare(
                            param, param.name, param.name_loc, SymbolKind.PARAMETER, param.type
                        )
                stack.append(("end_function",))
                stack.append(("pop_scope",))
                # The body block shares the function scope with the parameters.
                for body_item in reversed(node.body.items):
                    push(body_item)
            case ast.DeclStmt():
                for decl in reversed(node.decls):
                    push(decl)
            case ast.VarDecl():
                symbol = self.declare(
                    node, node.name, node.name_loc, SymbolKind.VARIABLE, node.type
                )
                if node.init is not None:
                    if symbol is not None and symbol.is_const:
                        stack.append(("const_value", symbol))  # runs after the initializer
                    push(node.init)

            # --- statements ---
            case ast.Block():
                self.open_scope(ScopeKind.BLOCK, node.loc)
                stack.append(("pop_scope",))
                for block_item in reversed(node.items):
                    push(block_item)
            case ast.If():
                push(node.otherwise)
                push(node.then)
                push(node.cond)
            case ast.While():
                push(node.body)
                push(node.cond)
            case ast.For():
                if isinstance(node.init, ast.DeclStmt):
                    self.open_scope(ScopeKind.FOR, node.loc)
                    stack.append(("pop_scope",))
                push(node.body)
                push(node.update, used=False)
                push(node.cond)
                push(node.init, used=False)
            case ast.Return():
                push(node.value)
            case ast.ExprStmt():
                push(node.expr, used=False)
            case ast.Break() | ast.Continue() | ast.EmptyStmt():
                pass

            # --- expressions ---
            case ast.Identifier():
                self.use(node, read=True, write=False)
            case ast.Assign():
                compound_value_used = node.op != "=" and value_used
                self.use(node.target, read=compound_value_used, write=True)
                push(node.value)
            case ast.IncDec():
                self.use(node.target, read=value_used, write=True)
            case ast.Call():
                self.use(node.callee, read=True, write=False, call=True)
                for arg in reversed(node.args):
                    push(arg)
            case ast.AddressOf():
                self.use(node.target, read=False, write=True)
            case ast.Paren():
                push(node.inner, used=value_used)
            case ast.Unary():
                push(node.operand)
            case ast.Binary():
                push(node.right)
                push(node.left)
            case ast.IntLiteral() | ast.FloatLiteral() | ast.CharLiteral() | ast.StringLiteral():
                pass
            case _:
                raise AssertionError(f"unhandled node {type(node).__name__}")
