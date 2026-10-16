"""Constant folding with C semantics (SRS addendum §5.2).

Shared by SEM-DIV0, SEM-CONSTCOND and the optimizer (OPT-CONSTEXPR). The
evaluation is iterative (post-order with an explicit stack), so arbitrarily
deep expressions such as long `1 + 1 + ...` chains are safe (§4.1).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from codeguard import ast

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1


@dataclass(frozen=True, slots=True)
class Const:
    value: int | float
    is_float: bool

    @property
    def is_zero(self) -> bool:
        return self.value == 0

    @property
    def truthy(self) -> bool:
        return self.value != 0

    def text(self) -> str:
        """The value as C source text, e.g. 30, 2.5, -1.0, 1e+20."""
        if not self.is_float:
            return str(self.value)
        text = repr(float(self.value))
        return text if any(c in text for c in ".e") else text + ".0"


# Look up the constant value of an identifier (a const variable), or None.
ConstLookup = Callable[[ast.Identifier], Const | None]


def no_constants(_: ast.Identifier) -> Const | None:
    return None


def _int(value: int) -> Const | None:
    return Const(value, False) if INT_MIN <= value <= INT_MAX else None


def _float(value: float) -> Const | None:
    return Const(value, True) if math.isfinite(value) else None


def _bool(value: bool) -> Const:
    return Const(1 if value else 0, False)


def _c_div(a: int, b: int) -> int:
    quotient = abs(a) // abs(b)
    return quotient if (a < 0) == (b < 0) else -quotient


def apply_binary(op: str, left: Const, right: Const) -> Const | None:
    """Evaluate `left op right` (both constant) with C semantics, or None."""
    if op in ("/", "%") and right.is_zero:
        return None
    is_float = left.is_float or right.is_float
    a, b = left.value, right.value
    match op:
        case "+" | "-" | "*" | "/":
            if is_float:
                fa, fb = float(a), float(b)
                result = {"+": fa + fb, "-": fa - fb, "*": fa * fb}.get(op)
                return _float(fa / fb if result is None else result)
            assert isinstance(a, int) and isinstance(b, int)
            if op == "/":
                return _int(_c_div(a, b))
            return _int({"+": a + b, "-": a - b, "*": a * b}[op])
        case "%":
            if is_float:
                return None  # % needs integer operands in C
            assert isinstance(a, int) and isinstance(b, int)
            return _int(a - b * _c_div(a, b))
        case "<":
            return _bool(a < b)
        case ">":
            return _bool(a > b)
        case "<=":
            return _bool(a <= b)
        case ">=":
            return _bool(a >= b)
        case "==":
            return _bool(a == b)
        case "!=":
            return _bool(a != b)
        case "&&":
            return _bool(left.truthy and right.truthy)
        case "||":
            return _bool(left.truthy or right.truthy)
    return None


def apply_unary(op: str, operand: Const) -> Const | None:
    match op:
        case "-":
            return Const(-operand.value, True) if operand.is_float else _int(-int(operand.value))
        case "+":
            return operand
        case "!":
            return _bool(not operand.truthy)
    return None


def fold(expr: ast.Node, lookup: ConstLookup = no_constants) -> Const | None:
    """The constant value of `expr`, or None if it is not a constant."""
    values: dict[ast.Node, Const | None] = {}
    for node in ast.walk_postorder(expr):
        values[node] = _fold_one(node, values, lookup)
    return values[expr]


def _fold_one(
    node: ast.Node, values: dict[ast.Node, Const | None], lookup: ConstLookup
) -> Const | None:
    match node:
        case ast.IntLiteral():
            return _int(node.value)
        case ast.CharLiteral():
            return Const(node.value, False)
        case ast.FloatLiteral():
            return _float(node.value)
        case ast.Identifier():
            return lookup(node)
        case ast.Paren():
            return values[node.inner]
        case ast.Unary():
            operand = values[node.operand]
            return None if operand is None else apply_unary(node.op, operand)
        case ast.Binary():
            left, right = values[node.left], values[node.right]
            # Short-circuit: `0 && e` is 0 and `1 || e` is 1 whatever e is.
            if node.op == "&&" and left is not None and not left.truthy:
                return _bool(False)
            if node.op == "||" and left is not None and left.truthy:
                return _bool(True)
            if left is None or right is None:
                return None
            return apply_binary(node.op, left, right)
    return None  # strings, calls, assignments, ++/--: never constant
