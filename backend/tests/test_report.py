"""Report builder: stage status, statistics, sorting, serialization and view caps."""

import json
from typing import Any

import pytest

from codeguard import ast
from codeguard.report import (
    MAX_VIEW_AST_DEPTH,
    MAX_VIEW_AST_NODES,
    MAX_VIEW_TOKENS,
    TOGGLEABLE_RULES,
    Stage,
    StageState,
    build_report,
)
from codeguard.report.builder import count_lines
from codeguard.report.serialize import ast_to_json, node_label
from tests.c_samples import worst_case
from tests.parser_helpers import parse_ok
from tests.semantic_helpers import in_main
from tests.test_parser_limits import run_within_frame_budget

SRS_DEMO = (
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


def response(source: str, toggles: dict[str, bool] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(build_report(source, toggles).to_json("test-id"))
    return body


def statuses(source: str) -> dict[str, str]:
    return {s["stage"]: s["status"] for s in response(source)["status"]}


# --- stage status -----------------------------------------------------------


def test_valid_declaration_passes_lexical_and_syntax() -> None:
    # TC-01
    assert statuses("int x = 10;") == {
        "lexical": "passed",
        "syntax": "passed",
        "semantic": "passed",
        "optimizer": "passed",
    }


def test_lexical_error_skips_every_later_stage() -> None:
    body = response("int x = 1 @ 2;")
    assert {s["stage"]: s["status"] for s in body["status"]} == {
        "lexical": "failed",
        "syntax": "skipped",
        "semantic": "skipped",
        "optimizer": "skipped",
    }
    assert [d["rule_id"] for d in body["diagnostics"]] == ["LEX-INVALID-CHAR"]
    assert body["tokens"]  # tokens scanned so far are still returned
    assert body["ast"] is None and body["symbols"] is None


def test_syntax_error_skips_semantic_and_optimizer() -> None:
    body = response(in_main("int unused = 1 +;\nreturn 0;"))
    assert {s["stage"]: s["status"] for s in body["status"]} == {
        "lexical": "passed",
        "syntax": "failed",
        "semantic": "skipped",
        "optimizer": "skipped",
    }
    assert [d["rule_id"] for d in body["diagnostics"]] == ["SYN-MALFORMED-EXPR"]
    assert body["ast"] is None and body["symbols"] is None


def test_unsupported_construct_fails_the_syntax_stage() -> None:
    assert statuses(in_main("int a[3];\nreturn 0;"))["syntax"] == "failed"


def test_semantic_error_fails_semantic_but_optimizer_still_runs() -> None:
    body = response(in_main("int x = 1 + 2;\nreturn x + y;"))
    assert {s["stage"]: s["status"] for s in body["status"]}["semantic"] == "failed"
    assert {s["stage"]: s["status"] for s in body["status"]}["optimizer"] == "passed"
    assert [d["rule_id"] for d in body["diagnostics"]] == ["OPT-CONSTEXPR", "SEM-UNDECL"]


def test_warnings_alone_pass_the_semantic_stage() -> None:
    report = build_report(SRS_DEMO)
    assert report.stage(Stage.SEMANTIC).status is StageState.PASSED


def test_break_outside_loop_passes_syntax_and_fails_semantic() -> None:
    # TC-37
    report = build_report("void f(void) { break; }")
    assert report.stage(Stage.SYNTAX).status is StageState.PASSED
    assert report.stage(Stage.SEMANTIC).status is StageState.FAILED
    assert [d.rule_id for d in report.diagnostics] == ["SEM-BREAK-CONTEXT"]


def test_truncation_is_noted_in_the_stage_detail() -> None:
    lexical = build_report("@" * 30)
    assert lexical.stage(Stage.LEXICAL).detail == "Stopped reporting after 20 lexical errors."
    syntax = build_report(in_main("x = ;\n" * 30))
    assert syntax.stage(Stage.SYNTAX).detail == "Stopped after 20 syntax errors."


# --- diagnostics ------------------------------------------------------------


def test_srs_demonstration_result() -> None:
    # SRS §3.13: lexical and syntax pass, one unused-variable warning,
    # one constant-condition warning, and statistics.
    body = response(SRS_DEMO)
    assert [s["status"] for s in body["status"][:2]] == ["passed", "passed"]
    assert [(d["rule_id"], d["line"]) for d in body["diagnostics"]] == [
        ("SEM-UNUSED", 4),
        ("SEM-CONSTCOND", 5),
    ]
    stats = body["statistics"]
    assert (stats["variables"], stats["functions"]) == (2, 1)
    assert (stats["errors"], stats["warnings"], stats["suggestions"]) == (0, 2, 0)
    assert stats["lines"] == 9


def test_diagnostics_are_sorted_by_position_then_severity() -> None:
    source = in_main("int a = 1 + 2;\nint b = 3 / 0;\nreturn q;")
    rows = [(d["line"], d["rule_id"]) for d in response(source)["diagnostics"]]
    assert rows == [
        (2, "SEM-UNUSED"),
        (2, "OPT-CONSTEXPR"),
        (3, "SEM-UNUSED"),
        (3, "SEM-DIV0"),
        (4, "SEM-UNDECL"),
    ]


def test_diagnostics_carry_their_stage() -> None:
    stages = {
        "int x = 1 @ 2;": "lexical",
        in_main("x = ;"): "syntax",
        in_main("int a[2];"): "syntax",
        in_main("return y;"): "semantic",
        in_main("return 1 + 2;"): "optimizer",
    }
    for source, stage in stages.items():
        (d,) = response(source)["diagnostics"]
        assert d["stage"] == stage, source


def test_diagnostic_fields() -> None:
    (d,) = response(in_main("return y;"))["diagnostics"]
    assert set(d) == {
        "rule_id",
        "severity",
        "stage",
        "message",
        "line",
        "column",
        "end_line",
        "end_column",
        "explanation",
        "fix_hint",
    }


# --- statistics ---------------------------------------------------------------


def test_statistics() -> None:
    source = (
        "int g = 1;\n"
        "int add(int a, int b);\n"
        "int main(void) { int x = 2; return add(x, g); }\n"
        "int add(int a, int b) { return a + b; }\n"
    )
    stats = response(source)["statistics"]
    assert (stats["variables"], stats["functions"], stats["lines"]) == (2, 2, 4)
    assert stats["tokens"] == len(build_report(source).tokens)
    assert stats["duration_ms"] >= 0


def test_variable_and_function_counts_are_zero_when_semantics_are_skipped() -> None:
    stats = response(in_main("int x = ;"))["statistics"]
    assert (stats["variables"], stats["functions"], stats["errors"]) == (0, 0, 1)


@pytest.mark.parametrize(
    ("text", "lines"), [("", 0), ("a", 1), ("a\n", 1), ("a\nb", 2), ("\n\n", 2)]
)
def test_count_lines(text: str, lines: int) -> None:
    assert count_lines(text) == lines


# --- response shape and serialization ------------------------------------------


def test_response_shape() -> None:
    # TC-32
    body = response(SRS_DEMO)
    assert list(body) == [
        "analysis_id",
        "status",
        "diagnostics",
        "statistics",
        "tokens",
        "ast",
        "symbols",
        "truncated",
    ]
    assert body["analysis_id"] == "test-id"
    assert [s["stage"] for s in body["status"]] == ["lexical", "syntax", "semantic", "optimizer"]
    assert body["tokens"][0] == {"type": "KEYWORD", "lexeme": "int", "line": 2, "column": 1}
    assert body["ast"]["type"] == "TranslationUnit"
    main = body["ast"]["children"][0]
    assert (main["label"], main["line"], main["end_line"]) == ("FunctionDef main", 2, 9)
    assert body["symbols"]["kind"] == "file"
    assert body["symbols"]["symbols"][0] == {
        "name": "main",
        "kind": "function",
        "type": "int (void)",
        "line": 2,
        "column": 5,
        "reads": 0,
        "writes": 0,
    }
    (main_scope,) = body["symbols"]["children"]
    assert [s["name"] for s in main_scope["symbols"]] == ["x", "unused"]
    assert body["truncated"] == {"tokens": False, "ast": False}


def test_ast_json_matches_a_reference_serializer() -> None:
    def reference(node: ast.Node) -> dict[str, Any]:
        return {
            "type": type(node).__name__,
            "label": node_label(node),
            "line": node.loc.line,
            "column": node.loc.column,
            "end_line": node.loc.end_line,
            "end_column": node.loc.end_column,
            "children": [reference(c) for c in node.children()],
        }

    def without_roles(value: dict[str, Any]) -> dict[str, Any]:
        return {
            **{k: v for k, v in value.items() if k not in ("role", "children")},
            "children": [without_roles(c) for c in value["children"]],
        }

    unit = parse_ok(SRS_DEMO)
    assert without_roles(json.loads(ast_to_json(unit))) == reference(unit)


def test_ast_roles_name_the_parts_of_control_statements() -> None:
    body = response(in_main("int i;\nfor (i = 0; ; i++) { }\nif (i) i = 1; else i = 2;\nreturn i;"))
    main = body["ast"]["children"][0]
    for_node = next(c for c in main["children"] if c["type"] == "Block")["children"][1]
    assert [c["role"] for c in for_node["children"]] == ["init", "update", "body"]
    if_node = next(c for c in main["children"] if c["type"] == "Block")["children"][2]
    assert [c["role"] for c in if_node["children"]] == ["condition", "then", "else"]


@pytest.mark.parametrize(
    ("source", "label"),
    [
        ("x = a + b;", "BinaryOp +"),
        ("x = -a;", "UnaryOp -"),
        ("x += 1;", "Assign +="),
        ("x++;", "Postfix ++"),
        ("--x;", "Prefix --"),
        ("f(1);", "Call f"),
        ('puts("hi");', 'StringLiteral "hi"'),
    ],
)
def test_node_labels(source: str, label: str) -> None:
    unit = parse_ok(in_main(source))
    assert label in {node_label(n) for n in ast.walk(unit)}


def test_untrusted_text_is_returned_as_inert_json_data() -> None:
    # TC-34 (backend part): a script tag in the source comes back as plain string data.
    payload = '<script>alert("x")</script>'
    source = in_main(f'puts("{payload.replace(chr(34), chr(92) + chr(34))}");\nreturn 0;')
    body = response(source)
    lexemes = [t["lexeme"] for t in body["tokens"] if t["type"] == "STRING_LITERAL"]
    assert lexemes == ['"<script>alert(\\"x\\")</script>"']


# --- teaching-view caps (TC-39) and deep input (TC-38) -------------------------


def test_token_view_is_capped_but_statistics_count_everything() -> None:
    # TC-39
    source = in_main("int x = 0;\n" + "x = x + 1;\n" * 3000 + "return x;")
    report = build_report(source)
    assert len(report.tokens) > MAX_VIEW_TOKENS
    body = json.loads(report.to_json("id"))
    assert len(body["tokens"]) == MAX_VIEW_TOKENS
    assert body["truncated"]["tokens"] is True
    assert body["statistics"]["tokens"] == len(report.tokens)
    assert body["ast"] is not None or body["truncated"]["ast"]


def test_ast_view_is_dropped_above_the_node_cap() -> None:
    source = in_main("int x = 0;\n" + "x = x + 1;\n" * (MAX_VIEW_AST_NODES // 5) + "return x;")
    body = response(source)
    assert body["ast"] is None
    assert body["truncated"]["ast"] is True
    assert body["symbols"] is not None  # the symbol table is unaffected


def test_ast_view_is_dropped_above_the_depth_cap() -> None:
    source = in_main("int x = " + " + ".join(["1"] * (MAX_VIEW_AST_DEPTH + 10)) + ";\nreturn x;")
    body = run_within_frame_budget(lambda: response(source))
    assert body["ast"] is None and body["truncated"]["ast"] is True
    assert body["statistics"]["suggestions"] == 1


def test_worst_case_report_within_the_frame_budget() -> None:
    # TC-38 (in-process part): the whole pipeline plus JSON serialization.
    text = run_within_frame_budget(lambda: build_report(worst_case()).to_json("id"))
    body = json.loads(text)
    assert [s["status"] for s in body["status"]] == ["passed"] * 4
    assert not any(d["rule_id"] == "NESTING_TOO_DEEP" for d in body["diagnostics"])
    assert body["ast"] is not None


def test_toggleable_rules() -> None:
    assert sorted(TOGGLEABLE_RULES) == [
        "OPT-CONSTEXPR",
        "SEM-CONSTCOND",
        "SEM-DIV0",
        "SEM-DUP",
        "SEM-SHADOW",
        "SEM-UNDECL",
        "SEM-UNREACH",
        "SEM-UNUSED",
    ]
