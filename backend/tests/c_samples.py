"""C source generators shared by tests (nesting limits and worst cases)."""

from codeguard.parser.parser import MAX_CHAIN_LENGTH, MAX_PAREN_DEPTH, MAX_STATEMENT_DEPTH


def nested_blocks(levels: int, inner: str = "x = 1;") -> str:
    """A function whose body plus inner blocks make `levels` nested blocks."""
    inner_blocks = levels - 1  # the function body is level 1
    return (
        "int main(void) {\n  int x = 0;\n"
        + "{" * inner_blocks
        + f"\n{inner}\n"
        + "}" * inner_blocks
        + "\n  return x;\n}\n"
    )


def nested_parens(levels: int, inner: str = "1") -> str:
    return "(" * levels + inner + ")" * levels


def unary_chain(length: int, operand: str = "x") -> str:
    return "!" * length + operand


def else_if_chain(links: int) -> str:
    parts = ["if (x == 0) x = 1;"]
    parts += [f" else if (x == {i}) x = {i + 1};" for i in range(1, links + 1)]
    parts.append(" else x = 0;")
    return "".join(parts)


def assignment_chain(length: int) -> str:
    names = [f"v{i}" for i in range(length + 1)]
    return " = ".join(names) + ";"


def worst_case() -> str:
    """TC-38: every nesting limit at its maximum at the same time.

    The innermost of 64 nested blocks holds an expression with 64 nested
    parentheses around a 256-deep unary chain. One block level up (so its
    braceless bodies are the 64th level) sits a 256-link else-if chain whose
    first condition repeats the same deep expression.
    """
    deep_expr = nested_parens(MAX_PAREN_DEPTH, unary_chain(MAX_CHAIN_LENGTH))
    blocks_above_chain = MAX_STATEMENT_DEPTH - 2  # body + these = level 63
    chain = else_if_chain(MAX_CHAIN_LENGTH).replace("(x == 0)", f"({deep_expr})", 1)
    return (
        "int main(void) {\n  int x = 0;\n"
        + "{" * blocks_above_chain
        + "\n"
        + chain
        + "\n{ x = "
        + deep_expr
        + "; }\n"
        + "}" * blocks_above_chain
        + "\n  return x;\n}\n"
    )
