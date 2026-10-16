"""Parser: nesting limits and recursion safety (addendum §4.1, §7; TC-28, TC-38)."""

import sys
from collections.abc import Callable

import pytest

from codeguard import ast
from codeguard.parser.parser import (
    MAX_CHAIN_LENGTH,
    MAX_PAREN_DEPTH,
    MAX_STATEMENT_DEPTH,
    NESTING_TOO_DEEP,
)
from tests.c_samples import (
    assignment_chain,
    else_if_chain,
    nested_blocks,
    nested_parens,
    unary_chain,
    worst_case,
)
from tests.parser_helpers import parse_ok, parse_source

# The parser must handle the worst case in well under Python's default limit of
# 1000 frames. Measured: about 460 frames, so this leaves room for the API and
# worker frames below it, and catches regressions that add recursion.
FRAME_BUDGET = 500


def _stack_depth() -> int:
    frame, depth = sys._getframe(), 0
    while frame is not None:
        depth += 1
        frame = frame.f_back
    return depth


def run_within_frame_budget[T](fn: Callable[[], T], budget: int = FRAME_BUDGET) -> T:
    """Run fn with the recursion limit lowered to `budget` frames above the caller.

    This lowers the limit (never raises it), to prove fn's stack use is bounded.
    """
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(_stack_depth() + budget)
    try:
        return fn()
    finally:
        sys.setrecursionlimit(old_limit)


def in_main(statement: str) -> str:
    return "int main(void) {\n  int x = 0;\n" + statement + "\n  return x;\n}\n"


def nesting_errors(source: str) -> list[str]:
    return [d.rule_id for d in parse_source(source).diagnostics]


# --- statement nesting (blocks and braceless bodies): 64 allowed --------------


def test_64_nested_blocks_are_accepted() -> None:
    parse_ok(nested_blocks(MAX_STATEMENT_DEPTH))


def test_65_nested_blocks_give_nesting_too_deep() -> None:
    # TC-28
    result = parse_source(nested_blocks(MAX_STATEMENT_DEPTH + 1))
    (d,) = result.diagnostics
    assert d.rule_id == NESTING_TOO_DEEP
    assert d.explanation


def test_braceless_bodies_count_as_levels() -> None:
    allowed = "if (x) " * (MAX_STATEMENT_DEPTH - 1) + "x = 1;"
    parse_ok(in_main(allowed))
    too_deep = "if (x) " * MAX_STATEMENT_DEPTH + "x = 1;"
    assert nesting_errors(in_main(too_deep)) == [NESTING_TOO_DEEP]


def test_nesting_too_deep_stops_parsing() -> None:
    source = nested_blocks(MAX_STATEMENT_DEPTH + 1) + "int g(void) { return 1 + ; }\n"
    assert nesting_errors(source) == [NESTING_TOO_DEEP]


# --- parentheses: 64 allowed, counted separately ----------------------------


def test_64_nested_parens_are_accepted() -> None:
    parse_ok(in_main("x = " + nested_parens(MAX_PAREN_DEPTH) + ";"))


def test_65_nested_parens_give_nesting_too_deep() -> None:
    source = in_main("x = " + nested_parens(MAX_PAREN_DEPTH + 1) + ";")
    assert nesting_errors(source) == [NESTING_TOO_DEEP]


def test_call_parens_count_towards_the_paren_limit() -> None:
    calls = "f(" * MAX_PAREN_DEPTH + "1" + ")" * MAX_PAREN_DEPTH
    parse_ok(in_main(f"x = {calls};"))
    too_many = "f(" * (MAX_PAREN_DEPTH + 1) + "1" + ")" * (MAX_PAREN_DEPTH + 1)
    assert nesting_errors(in_main(f"x = {too_many};")) == [NESTING_TOO_DEEP]


def test_parens_and_blocks_are_counted_separately() -> None:
    parse_ok(nested_blocks(MAX_STATEMENT_DEPTH, "x = " + nested_parens(MAX_PAREN_DEPTH) + ";"))


# --- chains: 256 links allowed, parsed iteratively -----------------------------


@pytest.mark.parametrize(
    ("make", "name"),
    [
        (lambda n: else_if_chain(n), "else-if"),
        (lambda n: "x = " + unary_chain(n) + ";", "unary"),
        (
            lambda n: (
                "int " + ", ".join(f"v{i}" for i in range(n + 1)) + ";\n" + assignment_chain(n)
            ),
            "assignment",
        ),
    ],
)
def test_chain_limits(make: Callable[[int], str], name: str) -> None:
    parse_ok(in_main(make(MAX_CHAIN_LENGTH)))
    assert nesting_errors(in_main(make(MAX_CHAIN_LENGTH + 1))) == [NESTING_TOO_DEEP], name


def test_else_if_chain_does_not_count_as_statement_nesting() -> None:
    # 256 links at block level 64 (bodies at the limit) are fine.
    chain = else_if_chain(MAX_CHAIN_LENGTH).replace("x = ", "{ x = ").replace(";", "; }")
    parse_ok(nested_blocks(MAX_STATEMENT_DEPTH - 1, chain))


def test_long_binary_chains_have_no_limit() -> None:
    # Binary operators are parsed iteratively, so a 5,000-term sum is fine.
    unit = run_within_frame_budget(
        lambda: parse_ok(in_main("x = " + " + ".join(["1"] * 5000) + ";"))
    )
    assert ast.depth(unit) > 5000


# --- TC-38: worst case within a fixed stack budget -----------------------------


def test_worst_case_parses_within_the_frame_budget() -> None:
    # TC-38 (parser part). The full pipeline in the worker process is tested
    # once the worker pool exists (Phase 6).
    unit = run_within_frame_budget(lambda: parse_ok(worst_case()))
    assert ast.depth(unit) > MAX_CHAIN_LENGTH


def test_frame_budget_helper_detects_unbounded_recursion() -> None:
    def recurse(n: int) -> int:
        return 0 if n == 0 else 1 + recurse(n - 1)

    with pytest.raises(RecursionError):
        run_within_frame_budget(lambda: recurse(FRAME_BUDGET + 50))
