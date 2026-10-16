"""Optimizer suggestions such as OPT-CONSTEXPR (owner: Member 3)."""

from codeguard.optimizer.constexpr import RULE_ID as OPT_CONSTEXPR
from codeguard.optimizer.constexpr import check as check_constexpr

TOGGLEABLE = frozenset({OPT_CONSTEXPR})

__all__ = ["OPT_CONSTEXPR", "TOGGLEABLE", "check_constexpr"]
