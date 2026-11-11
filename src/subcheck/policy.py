"""Load an expected-claims policy and represent it as claim rules."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Trust-boundary anchors are high severity; contextual claims default to medium.
CLAIM_SEVERITY = {
    "iss": "high",
    "aud": "high",
    "sub": "high",
    "repository": "high",
    "repository_owner": "high",
    "repository_id": "high",  # immutable trust anchors (survive rename/transfer)
    "repository_owner_id": "high",
    # the only claim constraining WHICH workflow code minted the token; AWS accepts it as an
    # alternative identity-provider control to sub.
    "job_workflow_ref": "high",
    "ref": "medium",
    "environment": "medium",
    "runner_environment": "medium",
    "actor": "medium",
}
DEFAULT_SEVERITY = "medium"

_OPERATORS = ("equals", "in", "matches", "glob")
_ALLOWED_KEYS = {*_OPERATORS, "required"}
_ALLOWED_TOP_KEYS = {"issuer", "audience", "claims"}


@dataclass
class ClaimRule:
    name: str
    equals: str | None = None
    one_of: list | None = None
    matches: str | None = None  # regex, applied with re.search
    glob: str | None = None  # fnmatch-style pattern
    required: bool = True

    @property
    def severity(self) -> str:
        return CLAIM_SEVERITY.get(self.name, DEFAULT_SEVERITY)

    def describe(self) -> str:
        # Every constraint set on a rule must hold (validator._matches ANDs them),
        # so describe them all - reporting only the first produced a failure line
        # that contradicted itself when a claim carried two constraints.
        parts = []
        if self.equals is not None:
            parts.append(f"equals {self.equals!r}")
        if self.one_of is not None:
            parts.append(f"one of {self.one_of!r}")
        if self.matches is not None:
            parts.append(f"matches /{self.matches}/")
        if self.glob is not None:
            parts.append(f"glob {self.glob!r}")
        return " and ".join(parts) if parts else "present"


@dataclass
class Policy:
    rules: list = field(default_factory=list)


def load_policy(data: dict) -> Policy:
    """Build a Policy from a parsed mapping (see the README for the schema)."""
    if not isinstance(data, dict):
        raise ValueError("policy must be a mapping/object")
    # Claim rules belong under 'claims'. Silently ignoring anything else let a
    # policy that put its rules at the top level pass every token it was written
    # to reject, green and rc=0, because only 'issuer'/'audience' were read.
    unknown_top = set(data) - _ALLOWED_TOP_KEYS
    if unknown_top:
        raise ValueError(
            f"policy: unknown top-level keys {sorted(unknown_top)} - claim rules "
            "belong under 'claims'; only 'issuer', 'audience' and 'claims' are read"
        )
    for key in ("issuer", "audience", "claims"):
        if key in data and data[key] is None:
            # A key with nothing after it loads as null. `issuer:` went through
            # str(None) and demanded 'None', so every token failed on rc=1 - a
            # broken policy wearing the gate-failure code. `claims:` - left empty,
            # or with every rule under it commented out - read as "no claim
            # rules", so the gate checked only iss and aud and passed the rest.
            raise ValueError(f"policy: {key!r} has no value - give it one, or remove the key")
    rules: list = []
    if "issuer" in data:
        rules.append(ClaimRule(name="iss", equals=str(data["issuer"])))
    if "audience" in data:
        rules.append(ClaimRule(name="aud", equals=str(data["audience"])))
    # A default, not `or {}`: `or` turned [], '', false and 0 into "no claim
    # rules" too, so none of them ever reached the mapping check below.
    claims = data.get("claims", {})
    if not isinstance(claims, dict):
        raise ValueError(
            f"policy 'claims' must be a mapping of claim -> rule, got {type(claims).__name__}"
        )
    if "claims" in data and not claims:
        # The same nothing, spelled {}; rejected like `in: []`.
        raise ValueError("policy: 'claims' is empty - list the claim rules, or remove the key")
    for name, spec in claims.items():
        rules.append(_rule_from_spec(name, spec))
    if not rules:
        raise ValueError("policy is empty: define 'issuer', 'audience', or 'claims'")
    return Policy(rules=rules)


def _rule_from_spec(name: str, spec) -> ClaimRule:
    if isinstance(spec, str):
        return ClaimRule(name=name, equals=spec)
    if isinstance(spec, list):
        if not spec:
            # The shorthand reaches the same empty-`in` rule checked below.
            raise ValueError(
                f"claim {name!r}: an empty list (the shorthand for 'in') matches no value - "
                "list the allowed values"
            )
        if any(item is None for item in spec):
            # And the same item with no value, checked below too.
            raise ValueError(
                f"claim {name!r}: the list (the shorthand for 'in') has an item with no value - "
                "a bare '-' or '~' is YAML for null; give the item a value, or remove it"
            )
        return ClaimRule(name=name, one_of=list(spec))
    if isinstance(spec, dict):
        unknown = set(spec) - _ALLOWED_KEYS
        if unknown:
            raise ValueError(f"claim {name!r}: unknown rule keys {sorted(unknown)}")
        for op in _OPERATORS:
            if op in spec and spec[op] is None:
                # `equals:` with nothing after it loads as null, which reads the
                # same as an absent operator: a rule left with no operator is a
                # bare presence check, and passed any token carrying the claim.
                raise ValueError(
                    f"claim {name!r}: {op!r} has no value, so it would constrain nothing - "
                    f"give it one, or write '{name}: {{required: true}}' if the claim "
                    "only has to be present"
                )
        one_of = spec.get("in")
        if one_of is not None and not isinstance(one_of, list):
            # `in: production` (a one-item YAML list missing its '- ') became
            # Python containment: substring matching, so 'prod' and even '' passed.
            raise ValueError(
                f"claim {name!r}: 'in' must be a list of values, got {type(one_of).__name__}"
            )
        if one_of == []:
            # No value is a member of an empty list, so every token carrying the
            # claim failed, on rc=1: a policy error reported as a finding.
            raise ValueError(
                f"claim {name!r}: 'in' is an empty list, which no value can match - "
                "list the allowed values"
            )
        if one_of is not None and any(item is None for item in one_of):
            # An item left as a bare '-' is null, the same "no value" as an empty
            # operator. It asked for a JSON null, so alone in the list it failed
            # every token carrying the claim, on rc=1 - the `in: []` mistake again.
            raise ValueError(
                f"claim {name!r}: 'in' has an item with no value - a bare '-' or '~' is YAML "
                "for null; give the item a value, or remove it"
            )
        matches = spec.get("matches")
        if matches is not None:
            if not isinstance(matches, str):
                raise ValueError(
                    f"claim {name!r}: 'matches' must be a regex string, got "
                    f"{type(matches).__name__}"
                )
            if not matches:
                # re.search('', s) succeeds on every string: the same presence
                # check as a null operator, and the same fail-open.
                raise ValueError(
                    f"claim {name!r}: 'matches' is an empty pattern, which every value "
                    f"matches - give it a regex, or write '{name}: {{required: true}}' if "
                    "the claim only has to be present"
                )
            try:
                re.compile(matches)
            except re.error as exc:
                raise ValueError(f"claim {name!r}: 'matches' is not a valid regex: {exc}") from exc
        glob = spec.get("glob")
        if glob is not None and not isinstance(glob, str):
            raise ValueError(
                f"claim {name!r}: 'glob' must be a pattern string, got {type(glob).__name__}"
            )
        required = spec.get("required", True)
        if not isinstance(required, bool):
            # bool("false") is True, so a quoted boolean silently made an
            # optional claim mandatory.
            raise ValueError(f"claim {name!r}: 'required' must be true or false, got {required!r}")
        if spec.get("required") is not True and not any(op in spec for op in _OPERATORS):
            # A rule with no operator at all is the same bare presence check a null
            # operator was: `repository: {}` passed any token carrying the claim,
            # and `{}` is what a serializer that drops null keys makes of
            # `{equals: null}`. With `required: false` it could not fail at all.
            # A presence check has to be asked for, as `required: true`.
            raise ValueError(
                f"claim {name!r}: the rule has no operator, so it would constrain nothing - "
                f"give it one of equals, in, matches or glob, or write '{name}: "
                "{required: true}' if the claim only has to be present"
            )
        return ClaimRule(
            name=name,
            equals=spec.get("equals"),
            one_of=one_of,
            matches=matches,
            glob=glob,
            required=required,
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
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            # YAMLError is not a ValueError (json.JSONDecodeError is), so an
            # unparseable YAML policy escaped the CLI's rc=2 handler and exited 1
            # - the "a claim did not match" code.
            raise ValueError(f"policy file {p} is not valid YAML: {exc}") from exc
    else:
        data = json.loads(text)
    return load_policy(data)
