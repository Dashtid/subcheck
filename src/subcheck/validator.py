"""Validate decoded claims against a policy."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass

from .policy import ClaimRule, Policy

PASS = "PASS"  # noqa: S105  # nosec B105 - a status constant, not a secret
FAIL = "FAIL"
MISSING = "MISSING"


@dataclass
class Result:
    claim: str
    status: str
    severity: str
    expected: str
    actual: object
    message: str


def _matches(rule: ClaimRule, value) -> bool:
    text = str(value)
    if rule.equals is not None and value != rule.equals:
        return False
    if rule.one_of is not None and value not in rule.one_of:
        return False
    if rule.matches is not None and re.search(rule.matches, text) is None:
        return False
    if rule.glob is not None and not fnmatch.fnmatchcase(text, rule.glob):
        return False
    return True


def validate(claims: dict, policy: Policy) -> list[Result]:
    """Check each policy rule against the claims and return one Result per rule."""
    results: list[Result] = []
    for rule in policy.rules:
        expected = rule.describe()
        if rule.name not in claims:
            status = MISSING if rule.required else PASS
            note = (
                f"claim {rule.name!r} is required but absent"
                if rule.required
                else f"claim {rule.name!r} absent (optional)"
            )
            results.append(Result(rule.name, status, rule.severity, expected, None, note))
            continue
        actual = claims[rule.name]
        if _matches(rule, actual):
            results.append(
                Result(rule.name, PASS, rule.severity, expected, actual,
                       f"claim {rule.name!r} satisfies {expected}")
            )
        else:
            results.append(
                Result(rule.name, FAIL, rule.severity, expected, actual,
                       f"claim {rule.name!r}={actual!r} does not satisfy {expected}")
            )
    return results
