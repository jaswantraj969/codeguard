"""Semantic stage entry point: build the model, run the rules, apply the policy."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from codeguard import ast
from codeguard.diagnostics import Diagnostic
from codeguard.lexer import Define
from codeguard.semantic.model import SemanticModel, build_model
from codeguard.semantic.rules import ALL_RULES, ALWAYS_ON, constant_condition
from codeguard.semantic.rules.base import Finding
from codeguard.semantic.rules.duplicate import RULE_ID as SEM_DUP
from codeguard.semantic.rules.shadowing import RULE_ID as SEM_SHADOW
from codeguard.semantic.rules.unused import RULE_ID as SEM_UNUSED

# One diagnostic per declaration: the first of these wins (addendum §5.1).
DECLARATION_PRIORITY = {SEM_DUP: 0, SEM_SHADOW: 1, SEM_UNUSED: 2}


@dataclass(frozen=True, slots=True)
class SemanticResult:
    model: SemanticModel
    diagnostics: list[Diagnostic]
    # Condition expressions reported by SEM-CONSTCOND; the optimizer skips them.
    constant_conditions: frozenset[ast.Node]


def is_enabled(rule_id: str, toggles: Mapping[str, bool]) -> bool:
    return rule_id in ALWAYS_ON or toggles.get(rule_id, True)


def analyze(
    unit: ast.TranslationUnit,
    defines: Iterable[Define] = (),
    toggles: Mapping[str, bool] | None = None,
) -> SemanticResult:
    toggles = toggles or {}
    model = build_model(unit, defines)
    findings: list[Finding] = []
    constant_conditions: set[ast.Node] = set()
    for rule in ALL_RULES:
        if not is_enabled(rule.RULE_ID, toggles):
            continue
        rule_findings: list[Finding] = rule.check(model)
        if rule is constant_condition:
            constant_conditions.update(f.anchor for f in rule_findings if f.anchor is not None)
        findings.extend(rule_findings)
    return SemanticResult(
        model=model,
        diagnostics=[f.diagnostic for f in apply_declaration_policy(findings)],
        constant_conditions=frozenset(constant_conditions),
    )


def apply_declaration_policy(findings: list[Finding]) -> list[Finding]:
    """Keep only the highest-priority SEM-DUP/SEM-SHADOW/SEM-UNUSED per declaration."""
    best: dict[ast.Node, int] = {}
    for finding in findings:
        priority = DECLARATION_PRIORITY.get(finding.diagnostic.rule_id)
        if priority is not None and finding.anchor is not None:
            best[finding.anchor] = min(priority, best.get(finding.anchor, priority))
    kept = []
    for finding in findings:
        priority = DECLARATION_PRIORITY.get(finding.diagnostic.rule_id)
        if priority is None or finding.anchor is None or best[finding.anchor] == priority:
            kept.append(finding)
    return kept
