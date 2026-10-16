"""One module per semantic rule (owner: Member 2).

Each module exposes RULE_ID and `check(model) -> list[Finding]`.
"""

from types import ModuleType

from codeguard.semantic.rules import (
    break_context,
    constant_condition,
    division_by_zero,
    duplicate,
    shadowing,
    undeclared,
    unreachable,
    unused,
)

# In report order. SEM-BREAK-CONTEXT is always on; the rest can be toggled.
ALL_RULES: tuple[ModuleType, ...] = (
    duplicate,
    undeclared,
    unused,
    division_by_zero,
    unreachable,
    constant_condition,
    shadowing,
    break_context,
)

ALWAYS_ON = frozenset({break_context.RULE_ID})
TOGGLEABLE = frozenset(rule.RULE_ID for rule in ALL_RULES) - ALWAYS_ON

__all__ = ["ALL_RULES", "ALWAYS_ON", "TOGGLEABLE"]
