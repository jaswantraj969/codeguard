"""Parser: valid programs, AST shape, precedence and locations."""

import pytest

from codeguard import ast
from tests.parser_helpers import body_of, expr_of, parse_ok, sexpr


def test_srs_demo_program_parses() -> None:
    unit = parse_ok(
        "#include <stdio.h>\n"
        "int main(void) {\n"
        "    int x = 10;\n"
        "    int unused = 50;\n"
        "    if (10 > 5) {\n"
        '        printf("%d\\n", x);\n'
        "    }\n"
        "    return 0;\n"
        "}\n"
    )
    (main,) = unit.items
    assert isinstance(main, ast.FunctionDef)
    assert (main.name, main.return_type.text, main.params) == ("main", "int", ())
    kinds = [type(item).__name__ for item in main.body.items]
    assert kinds == ["DeclStmt", "DeclStmt", "If", "Return"]


def test_function_definition_with_parameters() -> None:
    (fn,) = parse_ok("double area(const float w, double h) { return w * h; }").items
    assert isinstance(fn, ast.FunctionDef)
    assert [(p.type.text, p.name) for p in fn.params] == [("const float", "w"), ("double", "h")]
    assert fn.name_loc == ast.Loc(1, 8, 1, 12)


@pytest.mark.parametrize(
    ("source", "params"),
    [
        ("int f(void);", []),
        ("int f();", []),
        ("int f(int);", [None]),
        ("int f(int a, char);", ["a", None]),
    ],
)
def test_prototypes(source: str, params: list[str | None]) -> None:
    (proto,) = parse_ok(source).items
    assert isinstance(proto, ast.FunctionProto)
    assert [p.name for p in proto.params] == params


def test_prototype_then_definition_then_call_before_definition() -> None:
    unit = parse_ok(
        "int add(int, int);\n"
        "int main(void) { return add(1, helper()); }\n"
        "int add(int a, int b) { return a + b; }\n"
        "int helper(void) { return 2; }\n"
    )
    assert [type(i).__name__ for i in unit.items] == [
        "FunctionProto",
        "FunctionDef",
        "FunctionDef",
        "FunctionDef",
    ]


def test_global_declarations_with_multiple_declarators() -> None:
    unit = parse_ok("int a = 1, b, c = a + 2;\nconst char nl = '\\n';")
    first, second = unit.items
    assert isinstance(first, ast.DeclStmt) and isinstance(second, ast.DeclStmt)
    assert [(d.name, d.init is not None) for d in first.decls] == [
        ("a", True),
        ("b", False),
        ("c", True),
    ]
    assert second.decls[0].type.text == "const char"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("1 + 2 * 3", "(+ 1 (* 2 3))"),
        ("(1 + 2) * 3", "(* (+ 1 2) 3)"),
        ("a - b - c", "(- (- a b) c)"),
        ("a / b % c * d", "(* (% (/ a b) c) d)"),
        ("a < b == c > d", "(== (< a b) (> c d))"),
        ("a || b && c", "(|| a (&& b c))"),
        ("a && b || c && d", "(|| (&& a b) (&& c d))"),
        ("a + b < c * d && e != f || g", "(|| (&& (< (+ a b) (* c d)) (!= e f)) g)"),
        ("-a * -b", "(* (- a) (- b))"),
        ("!a == b", "(== (! a) b)"),
        ("- - !x", "(- (- (! x)))"),
        ("+x", "(+ x)"),
        ("a = b = c + 1", "(= a (= b (+ c 1)))"),
        ("x += y -= 2", "(+= x (-= y 2))"),
        ("x *= 3", "(*= x 3)"),
        ("x /= 2", "(/= x 2)"),
        ("x %= 2", "(%= x 2)"),
        ("(x) = 1", "(= x 1)"),
        ("i++", "(post++ i)"),
        ("--i", "(pre-- i)"),
        ("-x++", "(- (post++ x))"),
        ("a+++b", "(+ (post++ a) b)"),
        ("f()", "(call f)"),
        ("f(1, g(2), x + 1)", "(call f 1 (call g 2) (+ x 1))"),
        ('printf("%d", x)', '(call printf "%d" x)'),
        ('scanf("%d %d", &a, &b)', '(call scanf "%d %d" (& a) (& b))'),
        ("y = f(x) * 2", "(= y (* (call f x) 2))"),
        ("'a' + 1.5e2", "(+ 'a' 1.5e2)"),
    ],
)
def test_expression_precedence_and_associativity(source: str, expected: str) -> None:
    assert sexpr(expr_of(source)) == expected


def test_adjacent_strings_are_concatenated() -> None:
    expr = expr_of('puts("ab" "cd")')
    assert isinstance(expr, ast.Call)
    (arg,) = expr.args
    assert isinstance(arg, ast.StringLiteral)
    assert (arg.value, arg.text) == ("abcd", '"ab" "cd"')


def test_literal_values() -> None:
    expr = expr_of("x = 0x10 + 017 + 'A' + 2.5")
    values = [
        (type(n).__name__, n.value)
        for n in ast.walk(expr)
        if isinstance(n, ast.IntLiteral | ast.CharLiteral | ast.FloatLiteral)
    ]
    assert values == [
        ("IntLiteral", 16),
        ("IntLiteral", 15),
        ("CharLiteral", 65),
        ("FloatLiteral", 2.5),
    ]


def test_if_else_if_chain_is_nested_in_the_else_branch() -> None:
    (stmt,) = body_of("if (a) x = 1; else if (b) x = 2; else if (c) x = 3; else x = 4;")
    assert isinstance(stmt, ast.If)
    conditions = []
    node: ast.Stmt | None = stmt
    while isinstance(node, ast.If):
        conditions.append(sexpr(node.cond))
        node = node.otherwise
    assert conditions == ["a", "b", "c"]
    assert isinstance(node, ast.ExprStmt)


def test_dangling_else_binds_to_nearest_if() -> None:
    (outer,) = body_of("if (a) if (b) x = 1; else x = 2;")
    assert isinstance(outer, ast.If) and outer.otherwise is None
    inner = outer.then
    assert isinstance(inner, ast.If) and inner.otherwise is not None


def test_loops() -> None:
    stmts = body_of(
        "while (i < 10) i++;\n"
        "for (int i = 0, j = 1; i < j; i++) { continue; }\n"
        "for (i = 0; ; ) break;\n"
        "for (;;) { break; }\n"
    )
    while_stmt, for_decl, for_expr, for_empty = stmts
    assert isinstance(while_stmt, ast.While)
    assert isinstance(for_decl, ast.For) and isinstance(for_decl.init, ast.DeclStmt)
    assert [d.name for d in for_decl.init.decls] == ["i", "j"]
    assert isinstance(for_expr, ast.For) and isinstance(for_expr.init, ast.Assign)
    assert for_expr.cond is None and for_expr.update is None
    assert isinstance(for_empty, ast.For)
    assert (for_empty.init, for_empty.cond, for_empty.update) == (None, None, None)


def test_jumps_empty_statements_and_nested_blocks() -> None:
    stmts = body_of("; { ; { return; } } return 1 + 2;")
    assert [type(s).__name__ for s in stmts] == ["EmptyStmt", "Block", "Return"]
    final = stmts[-1]
    assert isinstance(final, ast.Return) and final.value is not None


def test_break_outside_loop_is_not_a_syntax_error() -> None:
    # SEM-BREAK-CONTEXT is a semantic check (addendum §5.3).
    (stmt,) = body_of("break;")
    assert isinstance(stmt, ast.Break)


def test_declarations_mixed_with_statements() -> None:
    stmts = body_of("int a = 1; a++; float b; b = a;")
    assert [type(s).__name__ for s in stmts] == ["DeclStmt", "ExprStmt", "DeclStmt", "ExprStmt"]


def test_node_locations_span_their_source() -> None:
    (stmt,) = body_of("x = (a + b) * 2;")
    assert isinstance(stmt, ast.ExprStmt)
    assert stmt.loc == ast.Loc(2, 1, 2, 17)
    expr = stmt.expr
    assert isinstance(expr, ast.Assign)
    assert expr.value.loc == ast.Loc(2, 5, 2, 16)  # "(a + b) * 2"


def test_if_location_covers_the_whole_chain() -> None:
    (stmt,) = body_of("if (a) {\n x = 1;\n} else {\n x = 2;\n}")
    assert isinstance(stmt, ast.If)
    assert (stmt.loc.line, stmt.loc.end_line) == (2, 6)


def test_walk_orders() -> None:
    expr = expr_of("a + b * c")
    pre = [sexpr(n) for n in ast.walk(expr)]
    post = [sexpr(n) for n in ast.walk_postorder(expr)]
    assert pre == ["(+ a (* b c))", "a", "(* b c)", "b", "c"]
    assert post == ["a", "b", "c", "(* b c)", "(+ a (* b c))"]
    assert ast.depth(expr) == 3


def test_empty_file_is_an_empty_translation_unit() -> None:
    assert parse_ok("").items == ()
    assert parse_ok("// just a comment\n#include <stdio.h>\n").items == ()
