"""Lexer: preprocessor lines are skipped; object-like #define is recorded (§2.2)."""

from codeguard.lexer import Define, tokenize


def lexemes(source: str) -> list[str]:
    result = tokenize(source)
    assert result.diagnostics == [], result.diagnostics
    return [t.lexeme for t in result.tokens[:-1]]


def test_include_lines_are_skipped_without_errors() -> None:
    source = '#include <stdio.h>\n#include "my.h"\nint main(void) { printf("hi"); }'
    assert lexemes(source)[:4] == ["int", "main", "(", "void"]


def test_indented_directive_and_space_after_hash() -> None:
    assert lexemes("   # include <stdio.h>\n\t#pragma once\nx") == ["x"]


def test_tokens_after_directives_keep_correct_lines() -> None:
    tokens = tokenize("#include <stdio.h>\n\nint x;").tokens
    assert (tokens[0].lexeme, tokens[0].line) == ("int", 3)


def test_continuation_lines_are_skipped() -> None:
    source = "#define LONG 1 + \\\n   2 + \\\n   3\nint y;"
    tokens = tokenize(source).tokens
    assert [t.lexeme for t in tokens[:-1]] == ["int", "y", ";"]
    assert tokens[0].line == 4


def test_conditional_compilation_lines_are_skipped_but_both_branches_lexed() -> None:
    source = "#ifdef DEBUG\nint a;\n#else\nint b;\n#endif\n"
    assert lexemes(source) == ["int", "a", ";", "int", "b", ";"]


def test_object_like_define_is_recorded() -> None:
    result = tokenize("#define MAX 100\n  #  define  PI 3.14 // circle\n#define EMPTY\n")
    assert result.defines == [
        Define(name="MAX", value="100", line=1, column=9),
        Define(name="PI", value="3.14", line=2, column=14),
        Define(name="EMPTY", value="", line=3, column=9),
    ]
    assert result.tokens[-1].type == "EOF" and len(result.tokens) == 1


def test_function_like_macro_is_ignored() -> None:
    result = tokenize("#define SQ(x) ((x) * (x))\n")
    assert result.defines == []
    assert result.diagnostics == []


def test_object_like_define_whose_value_starts_with_paren() -> None:
    # A space before "(" makes it object-like.
    (define,) = tokenize("#define N (10)\n").defines
    assert (define.name, define.value) == ("N", "(10)")


def test_malformed_define_is_ignored_without_error() -> None:
    result = tokenize("#define\n#define 9X\n#defineX 1\n")
    assert result.defines == []
    assert result.diagnostics == []


def test_hash_after_code_on_the_same_line_is_invalid() -> None:
    result = tokenize("int x; #define N 1\n")
    assert [d.rule_id for d in result.diagnostics] == ["LEX-INVALID-CHAR"]
    assert result.defines == []


def test_directive_at_end_of_file_without_newline() -> None:
    result = tokenize("int x;\n#define LAST 1")
    assert [d.name for d in result.defines] == ["LAST"]
    assert result.ok
