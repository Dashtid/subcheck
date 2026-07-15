"""Load an expected-claims policy and represent it as claim rules."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Trust-boundary anchors are high severity; contextual claims default to medium.
CLAIM_SEVERITY = {
    "iss": "high",
    "aud": "high",
    "sub": "high",
    "repository": "high",
    "repository_owner": "high",
    "ref": "medium",
    "environment": "medium",
    "runner_environment": "medium",
    "actor": "medium",
}
DEFAULT_SEVERITY = "medium"

_ALLOWED_KEYS = {"equals", "in", "matches", "glob", "required"}


@dataclass
class ClaimRule:
    name: str
    equals: str | None = None
    one_of: list | None = None
    matches: str | None = None  # regex, applied with re.search
    glob: str | None = None     # fnmatch-style pattern
    required: bool = True

    @property
    def severity(self) -> str:
        return CLAIM_SEVERITY.get(self.name, DEFAULT_SEVERITY)

    def describe(self) -> str:
        if self.equals is not None:
            return f"equals {self.equals!r}"
        if self.one_of is not None:
            return f"one of {self.one_of!r}"
        if self.matches is not None:
            return f"matches /{self.matches}/"
        if self.glob is not None:
            return f"glob {self.glob!r}"
        return "present"


@dataclass
class Policy:
    rules: list = field(default_factory=list)


def load_policy(data: dict) -> Policy:
    """Build a Policy from a parsed mapping (see the README for the schema)."""
    if not isinstance(data, dict):
        raise ValueError("policy must be a mapping/object")
    rules: list = []
    if "issuer" in data:
        rules.append(ClaimRule(name="iss", equals=str(data["issuer"])))
    if "audience" in data:
        rules.append(ClaimRule(name="aud", equals=str(data["audience"])))
    claims = data.get("claims") or {}
    if not isinstance(claims, dict):
        raise ValueError("policy 'claims' must be a mapping of claim -> rule")
    for name, spec in claims.items():
        rules.append(_rule_from_spec(name, spec))
    if not rules:
        raise ValueError("policy is empty: define 'issuer', 'audience', or 'claims'")
    return Policy(rules=rules)


def _rule_from_spec(name: str, spec) -> ClaimRule:
    if isinstance(spec, str):
        return ClaimRule(name=name, equals=spec)
    if isinstance(spec, list):
        return ClaimRule(name=name, one_of=list(spec))
    if isinstance(spec, dict):
        unknown = set(spec) - _ALLOWED_KEYS
        if unknown:
            raise ValueError(f"claim {name!r}: unknown rule keys {sorted(unknown)}")
        return ClaimRule(
            name=name,
            equals=spec.get("equals"),
            one_of=spec.get("in"),
            matches=spec.get("matches"),
            glob=spec.get("glob"),
            required=bool(spec.get("required", True)),
        )
    raise ValueError(f"claim {name!r}: rule must be a string, list, or mapping")


def load_policy_file(path: str | Path) -> Policy:
    """Load a policy from a .json, .yaml, or .yml file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "PyYAML is required to load YAML policies (pip install PyYAML), "
                "or use a .json policy instead"
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return load_policy(data)
