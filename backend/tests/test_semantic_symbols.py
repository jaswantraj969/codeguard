"""Symbol table: scopes, symbols, resolution and read/write counts (addendum §6)."""

from codeguard.semantic import ScopeKind, SymbolKind
from codeguard.semantic.library import load_library
from tests.semantic_helpers import analyze_source


def symbols_by_name(source: str) -> dict[str, list[tuple[str, int, int]]]:
    """name -> [(kind, reads, writes), ...] in declaration order."""
    table: dict[str, list[tuple[str, int, int]]] = {}
    for s in analyze_source(source).model.symbols:
        table.setdefault(s.name, []).append((s.kind.value, s.reads, s.writes))
    return table


def test_scope_tree_shape() -> None:
    model = analyze_source(
        "int g;\n"
        "int main(void) {\n"
        "  int a = 1;\n"
        "  { int b = a; b++; }\n"
        "  for (int i = 0; i < a; i++) { int c = i; c++; }\n"
        "  return g;\n"
        "}\n"
    ).model
    root = model.file_scope
    assert root.kind is ScopeKind.FILE
    assert [s.name for s in root.symbols] == ["g", "main"]
    (main_scope,) = root.children
    assert (main_scope.kind, main_scope.name) == (ScopeKind.FUNCTION, "main")
    assert [s.name for s in main_scope.symbols] == ["a"]
    block, for_scope = main_scope.children
    assert (block.kind, [s.name for s in block.symbols]) == (ScopeKind.BLOCK, ["b"])
    assert (for_scope.kind, [s.name for s in for_scope.symbols]) == (ScopeKind.FOR, ["i"])
    (for_body,) = for_scope.children
    assert [s.name for s in for_body.symbols] == ["c"]


def test_parameters_share_the_function_scope_with_the_body() -> None:
    model = analyze_source("int f(int a, float b) { int c = a; return c; }").model
    (fn_scope,) = model.file_scope.children
    assert [(s.name, s.kind) for s in fn_scope.symbols] == [
        ("a", SymbolKind.PARAMETER),
        ("b", SymbolKind.PARAMETER),
        ("c", SymbolKind.VARIABLE),
    ]
    assert fn_scope.children == []


def test_symbol_types() -> None:
    model = analyze_source(
        "#define LIMIT 10\n"
        "const double PI = 3.14;\n"
        "int area(int w, float h);\n"
        "void tick(void) { }\n"
        "int area(int w, float h) { return w; }\n"
    ).model
    types = {s.name: (s.kind.value, s.type_text, s.line) for s in model.symbols}
    assert types["LIMIT"] == ("define", "#define 10", 1)
    assert types["PI"] == ("variable", "const double", 2)
    assert types["area"] == ("function", "int (int, float)", 3)
    assert types["tick"] == ("function", "void (void)", 4)


def test_reads_and_writes() -> None:
    table = symbols_by_name(
        "int main(void) {\n"
        "  int a = 1;\n"  # initializer: neither
        "  int b;\n"
        "  b = a;\n"  # b write, a read
        "  b += 1;\n"  # standalone compound: write only
        "  b++;\n"  # standalone increment: write only
        "  int c = b++;\n"  # value used: b read + write
        "  int d;\n"
        '  scanf("%d", &d);\n'  # &d: write
        "  for (c = 0; c < 3; c++) { }\n"  # init/update: writes; condition: read
        "  return c;\n"
        "}\n"
    )
    assert table["a"] == [("variable", 1, 0)]
    assert table["b"] == [("variable", 1, 4)]
    assert table["c"] == [("variable", 2, 2)]
    assert table["d"] == [("variable", 0, 1)]


def test_compound_assignment_used_as_a_value_is_a_read() -> None:
    table = symbols_by_name("int main(void) { int x = 0; int y = (x += 2); return y; }")
    assert table["x"] == [("variable", 1, 1)]


def test_function_reads_count_calls_including_before_definition() -> None:
    table = symbols_by_name(
        "int main(void) { return twice(1) + twice(2); }\nint twice(int n) { return n * 2; }\n"
    )
    assert table["twice"] == [("function", 2, 0)]


def test_identifiers_resolve_to_the_nearest_declaration() -> None:
    # TC-18: nested-scope resolution
    result = analyze_source(
        "int x = 1;\nint main(void) {\n  int x = 2;\n  { int x = 3; x++; }\n  return x;\n}\n"
    )
    xs = [s for s in result.model.symbols if s.name == "x"]
    global_x, main_x, inner_x = xs
    assert (global_x.reads, main_x.reads, inner_x.writes) == (0, 1, 1)
    assert [d.rule_id for d in result.diagnostics] == ["SEM-SHADOW", "SEM-SHADOW"]


def test_variable_is_visible_from_its_declarator() -> None:
    # `int a = 1, b = a;` - a is visible in b's initializer.
    result = analyze_source("int main(void) { int a = 1, b = a; return b; }")
    assert result.diagnostics == []


def test_library_names_are_never_symbols() -> None:
    model = analyze_source(
        '#include <stdio.h>\nint main(void) { printf("%d", EOF); return 0; }'
    ).model
    assert [s.name for s in model.symbols] == ["main"]


def test_library_list_is_loaded_from_the_data_file() -> None:
    library = load_library()
    for name in (
        "printf",
        "scanf",
        "puts",
        "putchar",
        "getchar",
        "abs",
        "sqrt",
        "pow",
        "strlen",
        "exit",
    ):
        assert name in library.functions
    for name in ("EOF", "NULL", "stdin", "RAND_MAX", "INT_MAX"):
        assert name in library.constants
    assert "main" not in library
