"""Load an expected-claims policy and represent it as claim rules."""

from __future__ import annotations

import fnmatch
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

# Values with nothing in common: an empty one, one letter, a long one shaped like a real
# `sub` - slashes, colons, dots, @ids, a percent-encoded colon - and one shaped like a
# workflow name, with the spaces and punctuation a `sub` never carries. None holds a
# newline, which no claim value does either, so `^.*$` still matches all of them. A
# `matches` or `glob` that every one of them satisfies constrains nothing (see
# _matches_every_value).
_UNRELATED_VALUES = (
    "",
    "x",
    "repo:Octo-Org@10001/octo_repo.v2@20002:ref:refs/heads/release/2.0%3Arc-1",
    "Deploy #2 [prod] + docs",
)


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
        # key=str: a YAML key need not be a string (`1:`), and sorting an int
        # against a str raised TypeError - a traceback on rc=1, not this rc=2.
        raise ValueError(
            f"policy: unknown top-level keys {sorted(unknown_top, key=str)} - claim rules "
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
    for key in ("issuer", "audience"):
        value = data.get(key)
        if key in data and not isinstance(value, str):
            # The shortcuts went through str(), so anything but a string became
            # text no token carries: `audience: [sts.amazonaws.com]` demanded
            # "['sts.amazonaws.com']" and `issuer: false` demanded 'False', so
            # every token failed on rc=1. A number fared little better - YAML
            # reads `0123` as 83 - so it has to be quoted, like an `equals` value
            # meant as a string.
            raise ValueError(
                f"policy: {key!r} must be a string, got {type(value).__name__} - write one "
                "value, in quotes if YAML would read it as a number or a boolean"
            )
    rules: list = []
    if "issuer" in data:
        rules.append(ClaimRule(name="iss", equals=data["issuer"]))
    if "audience" in data:
        rules.append(ClaimRule(name="aud", equals=data["audience"]))
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
        if not isinstance(name, str) or not name:
            # A YAML key need not be a string: `1:` is an int and `~:` is null, and
            # neither names a claim in a JSON token. The text report then crashed
            # on len(name) - a traceback on rc=1 - while --format json reported
            # normally, and an optional rule under a null name could never fail.
            # An empty name is a key left blank, not a claim.
            raise ValueError(f"policy: claim names must be non-empty strings, got {name!r}")
        rules.append(_rule_from_spec(name, spec))
    if not rules:
        raise ValueError("policy is empty: define 'issuer', 'audience', or 'claims'")
    return Policy(rules=rules)


def _rule_from_spec(name: str, spec) -> ClaimRule:
    if spec is None:
        # `repository:` with nothing under it - or with every line under it commented
        # out - is YAML for null. It was always rejected, but as a rule that was not "a
        # string, list, or mapping", which named neither the empty key nor the way to
        # ask for presence on purpose.
        raise ValueError(
            f"claim {name!r} has no value, so it would constrain nothing - give it a rule, "
            f"or write '{name}: {{required: true}}' if the claim only has to be present"
        )
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
            # key=str, for the same mixed-type keys as at the top level.
            raise ValueError(f"claim {name!r}: unknown rule keys {sorted(unknown, key=str)}")
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
            except (re.error, OverflowError, RecursionError) as exc:
                # re.error is not all re.compile raises: a repeat count past its
                # limit (`a{4294967296}`) is an OverflowError, which escaped as a
                # traceback on rc=1, and groups nested a few hundred deep are a
                # RecursionError, which reached rc=2 without naming the claim.
                raise ValueError(f"claim {name!r}: 'matches' is not a valid regex: {exc}") from exc
            if _matches_every_value(matches, lambda p, v: re.search(p, v) is not None):
                # `^`, `(?i)`, `(?x) ` and `.*` are not empty, so the check above let
                # them through, and each passed a token from any repository - `(?i)` is
                # what '(?i)${VAR}' becomes when the variable is empty.
                raise ValueError(_constrains_nothing(name, "matches", matches))
        glob = spec.get("glob")
        if glob is not None and not isinstance(glob, str):
            raise ValueError(
                f"claim {name!r}: 'glob' must be a pattern string, got {type(glob).__name__}"
            )
        if glob is not None and _matches_every_value(glob, lambda p, v: fnmatch.fnmatchcase(v, p)):
            # `*` spans every character, '/' and ':' included, so it passed every value.
            raise ValueError(_constrains_nothing(name, "glob", glob))
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


def _matches_every_value(pattern: str, match: Callable[[str, str], bool]) -> bool:
    """Whether every value tried matches `pattern`, asked with the validator's own call.

    The values are the unrelated ones above and each run of plain text in the pattern
    itself: a negative lookahead such as `^(?!refs/pull/)` matches all the unrelated
    ones, and rules out the text it names. Escaped punctuation stays in its run, read as
    the character it stands for, so a deny rule on the bot `dependabot[bot]` - its
    brackets escaped - is tried on that name, whole. A value the pattern rules out proves
    that it constrains something, so the extra values can only keep a pattern, never
    reject one.
    """
    runs = re.findall(r"(?:\\[^\w\s]|[\w/:@%. -])+", pattern)
    plain_text = [re.sub(r"\\([^\w\s])", r"\1", run) for run in runs]
    return all(match(pattern, value) for value in (*_UNRELATED_VALUES, *plain_text))


def _constrains_nothing(name: str, op: str, pattern: str) -> str:
    return (
        f"claim {name!r}: {op!r} {pattern!r} matches every value, so it would constrain "
        f"nothing - give it a pattern that rules something out, or write '{name}: "
        "{required: true}' if the claim only has to be present"
    )


# The tags YAML gives the merge key `<<` and the value key `=`. SafeConstructor folds a
# merge into its mapping and turns `=` into the string '=', so neither is read as written.
_YAML_MERGE_TAG = "tag:yaml.org,2002:merge"
_YAML_VALUE_TAG = "tag:yaml.org,2002:value"
_YAML_STR_TAG = "tag:yaml.org,2002:str"
# SafeConstructor merges at every key that carries the merge tag - `<<`, or anything written
# with `!!merge` - so all of them are the one key `<<`.
_YAML_MERGE_KEY = (_YAML_MERGE_TAG, "<<")


def _repeated_key(key: object, where: str = "") -> ValueError:
    # Both parsers keep the LAST of two equal keys and drop the first without a word:
    # `repository: {equals: acme/api}` followed by `repository: {required: true}` left a
    # presence check, and the gate passed a token from any repository.
    return ValueError(
        f"policy: the key {key!r} is repeated in one mapping{where} - only the last would be "
        "read, silently dropping the one before it; write each key once"
    )


def _repeated_merge_key(where: str) -> ValueError:
    # A second `<<` is not dropped like other keys: SafeConstructor folds both merges in, in
    # order, so wherever the two mappings share a key the later one's rule replaced the
    # earlier one's without a word - `<<: {repository: {equals: acme/api}}` followed by
    # `<<: {repository: {required: true}}` left a presence check.
    return ValueError(
        f"policy: the key '<<' is repeated in one mapping{where} - YAML would fold in both "
        "merges, and a key they share would silently take the later one's rule; merge "
        "several mappings with one '<<: [*a, *b]'"
    )


def _key_merged_twice(key: object, line: int) -> ValueError:
    # In `<<: [*a, *b]` YAML gives the EARLIER mapping precedence, so a key both supply took
    # a's rule and dropped b's without a word: `<<: [{repository: {required: true}},
    # {repository: {equals: acme/api}}]` left a presence check.
    return ValueError(
        f"policy: the key {key!r} comes from two of the mappings merged on line {line} - YAML "
        "would keep the first one's and silently drop the other; merge mappings that share "
        "no key"
    )


def _unique_json_keys(pairs: list) -> dict:
    """An object_pairs_hook for json.loads that rejects a key repeated in one object."""
    data: dict = {}
    for key, value in pairs:
        if key in data:
            raise _repeated_key(key)
        data[key] = value
    return data


def _load_yaml(text: str) -> Any:
    """yaml.safe_load, except that a key the parser would silently replace is rejected.

    That is a key repeated in one mapping, `<<` included, and a key that two of the mappings
    one `<<` merges both supply.
    """
    import yaml

    def key_of(key_node: yaml.Node) -> tuple | None:
        # A key is its tag and its text, so `repository` and "repository" are one key. A key
        # that is not a scalar is no dict key at all, and SafeConstructor rejects it - unless
        # it carries the merge tag, which makes it a merge whatever it is written as.
        if key_node.tag == _YAML_MERGE_TAG:
            return _YAML_MERGE_KEY
        if not isinstance(key_node, yaml.ScalarNode):
            return None
        return (_YAML_STR_TAG if key_node.tag == _YAML_VALUE_TAG else key_node.tag, key_node.value)

    def merged(value_node: yaml.Node) -> list:
        # The mappings a `<<` merges: one, or a list of them. Anything else is
        # SafeConstructor's to reject.
        nodes = value_node.value if isinstance(value_node, yaml.SequenceNode) else [value_node]
        return [node for node in nodes if isinstance(node, yaml.MappingNode)]

    def supplied(mapping: yaml.MappingNode, seen: set) -> dict:
        # The keys a mapping holds once its own merges are folded in, in the order written.
        # `seen` stops a mapping that merges itself through an alias.
        keys: dict = {}
        if id(mapping) not in seen:
            seen.add(id(mapping))
            for key_node, value_node in mapping.value:
                key = key_of(key_node)
                if key == _YAML_MERGE_KEY:
                    for source in merged(value_node):
                        keys.update(supplied(source, seen))
                elif key is not None:
                    keys[key] = key_node.value
        return keys

    class UniqueKeyLoader(yaml.SafeLoader):
        def __init__(self, stream: str) -> None:
            super().__init__(stream)
            # The line each key of a mapping is written on, by mapping, in order.
            self.key_lines: dict[int, list[int]] = {}

        def compose_node(self, parent: yaml.Node | None, index: Any) -> yaml.Node | None:
            # Read before the node is composed: an alias composes to the very node it names,
            # whose mark is the anchor's line, so `*k : ...` would be reported where `&k`
            # was written. A mapping composes each key with no index, and each value with
            # its key as the index.
            line = self.peek_event().start_mark.line + 1
            node = super().compose_node(parent, index)
            if isinstance(parent, yaml.MappingNode) and index is None:
                self.key_lines.setdefault(id(parent), []).append(line)
            return node

        def compose_mapping_node(self, anchor: Any) -> yaml.MappingNode:
            node = super().compose_mapping_node(anchor)
            # Checked as written, before SafeConstructor folds any `<<` merge into the
            # node: a merged key that the mapping overrides is what a merge is for, not a
            # repeat - but `<<` itself is a key like any other, and so is a key that two of
            # the mappings one `<<` merges both supply. (PyYAML's own composer has the
            # first check, commented out, here.)
            lines: dict = {}
            key_lines = self.key_lines.pop(id(node), [])
            for (key_node, value_node), line in zip(node.value, key_lines, strict=True):
                key = key_of(key_node)
                if key is None:
                    continue
                if key in lines:
                    where = f" (lines {lines[key]} and {line})"
                    if key == _YAML_MERGE_KEY:
                        raise _repeated_merge_key(where)
                    raise _repeated_key(key_node.value, where)
                lines[key] = line
                if key == _YAML_MERGE_KEY:
                    taken: dict = {}
                    for source in merged(value_node):
                        keys = supplied(source, set())
                        shared = [merged_key for merged_key in keys if merged_key in taken]
                        if shared:
                            raise _key_merged_twice(keys[shared[0]], line)
                        taken.update(keys)
            return node

    # A yaml.SafeLoader subclass - the linters accept only a Loader named SafeLoader.
    return yaml.load(text, Loader=UniqueKeyLoader)  # noqa: S506  # nosec B506


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
            data = _load_yaml(text)
        except yaml.YAMLError as exc:
            # YAMLError is not a ValueError (json.JSONDecodeError is), so an
            # unparseable YAML policy escaped the CLI's rc=2 handler and exited 1
            # - the "a claim did not match" code.
            raise ValueError(f"policy file {p} is not valid YAML: {exc}") from exc
    else:
        # The hook sees each object's keys before a dict can keep only the last.
        data = json.loads(text, object_pairs_hook=_unique_json_keys)
    return load_policy(data)
