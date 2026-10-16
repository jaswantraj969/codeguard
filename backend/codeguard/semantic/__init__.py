"""Symbol table, constant folding and semantic rules (owner: Member 2)."""

from codeguard.semantic.analyzer import SemanticResult, analyze
from codeguard.semantic.folding import Const, fold
from codeguard.semantic.model import SemanticModel, build_model
from codeguard.semantic.rules import ALWAYS_ON, TOGGLEABLE
from codeguard.semantic.symbols import Scope, ScopeKind, Symbol, SymbolKind

__all__ = [
    "ALWAYS_ON",
    "TOGGLEABLE",
    "Const",
    "Scope",
    "ScopeKind",
    "SemanticModel",
    "SemanticResult",
    "Symbol",
    "SymbolKind",
    "analyze",
    "build_model",
    "fold",
]
