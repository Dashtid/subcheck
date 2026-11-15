"""A key written twice in one mapping must be rejected, never silently replaced.

YAML and JSON parsers keep the LAST of two equal keys and drop the first without a
word. In a policy that turns one rule into another: `repository: {equals: acme/api}`
followed by `repository: {required: true}` left a presence check, and the gate passed
a token from any repository - PASS and rc=0 through the shipped CLI on 0.5.1. The same
held one level up, where a second `claims:` replaced every rule under the first, and
one level down, where a second `matches` replaced the pattern beside it instead of
adding to it.

A repeated key is now a bad policy at every level, rc=2, and the error names the key
(and, for YAML, both lines). YAML's merge key is not a repeat: a mapping that overrides
a key it merged in with `<<` is what a merge is for, and it still loads. `<<` is a key
itself, though, and a second one is not dropped but folded in after the first, so the
later merge replaced the earlier one's rules just as silently; it is rejected like any
other repeat, in every spelling YAML reads as the merge key.
"""

import json
import re

import pytest

from subcheck.cli import main
from subcheck.policy import load_policy_file

# A token from a repository the policies below were written to keep out.
OTHER_REPO = {
    "iss": "https://token.actions.githubusercontent.com",
    "aud": "sts.amazonaws.com",
    "sub": "repo:attacker/evil:ref:refs/heads/main",
    "repository": "attacker/evil",
    "ref": "refs/heads/main",
    "environment": "staging",
}

ISS_AUD_YAML = f"issuer: {OTHER_REPO['iss']}\naudience: {OTHER_REPO['aud']}\n"

# One repeat per level a key can repeat at: (policy text, the key the error must name).
YAML_REPEATS = {
    # Was: PASS (1 pass, 0 fail, 0 missing), rc=0 - the pin became a presence check.
    "claims-mapping": (
        "claims:\n  repository: {equals: acme/api}\n  repository: {required: true}\n",
        "repository",
    ),
    # Was: PASS (3 pass, 0 fail, 0 missing), rc=0 - the second 'claims' replaced every
    # rule under the first, so only the issuer, audience and environment were checked.
    "top-level": (
        ISS_AUD_YAML + "claims:\n  repository: {equals: acme/api}\n"
        "claims:\n  environment: {required: true}\n",
        "claims",
    ),
    # Was: PASS (1 pass, 0 fail, 0 missing), rc=0 - two patterns meant to hold together
    # read as the second alone, so the repository half of the check vanished.
    "operator-mapping": (
        "claims:\n  sub:\n    matches: '^repo:acme/api:'\n    matches: ':ref:refs/heads/main$'\n",
        "matches",
    ),
}

# The same three in JSON, which RFC 8259 leaves to the parser - and Python's keeps the last.
JSON_REPEATS = {
    "claims-mapping": (
        '{"claims": {"repository": {"equals": "acme/api"}, "repository": {"required": true}}}',
        "repository",
    ),
    "top-level": (
        f'{{"issuer": "{OTHER_REPO["iss"]}", "claims": {{"repository": {{"equals": "acme/api"}}}}, '
        '"claims": {"environment": {"required": true}}}',
        "claims",
    ),
    "operator-mapping": (
        '{"claims": {"sub": {"matches": "^repo:acme/api:", "matches": ":ref:refs/heads/main$"}}}',
        "matches",
    ),
}

# `<<` written twice in one mapping: (policy text, the lines the error names). SafeConstructor
# folds both merges in, the later one last, so on 0.5.1 every one of these passed the token
# above - PASS (1 pass, 0 fail, 0 missing), rc=0.
MERGE_REPEATS = {
    # The pin became a presence check.
    "claims-mapping": (
        "claims:\n  <<: {repository: {equals: acme/api}}\n  <<: {repository: {required: true}}\n",
        "2 and 3",
    ),
    # Two patterns meant to hold together read as the second alone.
    "operator-mapping": (
        "claims:\n  sub:\n    <<: {matches: '^repo:acme/api:'}\n"
        "    <<: {matches: ':ref:refs/heads/main$'}\n",
        "3 and 4",
    ),
    # The second merge's 'claims' replaced the first's.
    "top-level": (
        "<<: {claims: {repository: {equals: acme/api}}}\n"
        "<<: {claims: {repository: {required: true}}}\n",
        "1 and 2",
    ),
    # `!!merge` is the merge key's tag written out, and it makes a merge of any key it is
    # on - `<<`, other text, or not even a scalar.
    "tagged-merge-key": (
        "claims:\n  !!merge <<: {repository: {equals: acme/api}}\n"
        "  <<: {repository: {required: true}}\n",
        "2 and 3",
    ),
    "tagged-other-text": (
        "claims:\n  !!merge a: {repository: {equals: acme/api}}\n"
        "  !!merge b: {repository: {required: true}}\n",
        "2 and 3",
    ),
    "tagged-sequence": (
        "claims:\n  ? !!merge [x]\n  : {repository: {equals: acme/api}}\n"
        "  <<: {repository: {required: true}}\n",
        "2 and 4",
    ),
}


def _policy(tmp_path, text, suffix=".yaml"):
    path = tmp_path / f"policy{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


# --- the loader --------------------------------------------------------------


@pytest.mark.parametrize(("text", "key"), YAML_REPEATS.values(), ids=YAML_REPEATS.keys())
def test_a_repeated_yaml_key_is_rejected_at_every_level(tmp_path, text, key):
    with pytest.raises(ValueError) as excinfo:
        load_policy_file(_policy(tmp_path, text))
    message = str(excinfo.value)
    assert f"policy: the key {key!r} is repeated in one mapping (lines " in message
    assert "write each key once" in message


@pytest.mark.parametrize(("text", "key"), JSON_REPEATS.values(), ids=JSON_REPEATS.keys())
def test_a_repeated_json_key_is_rejected_at_every_level(tmp_path, text, key):
    expected = f"policy: the key {key!r} is repeated in one mapping - only the last would be read"
    with pytest.raises(ValueError, match=re.escape(expected)):
        load_policy_file(_policy(tmp_path, text, ".json"))


def test_the_yaml_error_names_both_lines(tmp_path):
    text = YAML_REPEATS["claims-mapping"][0]
    expected = "the key 'repository' is repeated in one mapping (lines 2 and 3)"
    with pytest.raises(ValueError, match=re.escape(expected)):
        load_policy_file(_policy(tmp_path, text))


def test_a_quoted_key_repeats_its_plain_spelling(tmp_path):
    # Both are the string 'repository', and YAML kept the second.
    text = 'claims:\n  repository: {equals: acme/api}\n  "repository": {required: true}\n'
    with pytest.raises(ValueError, match="the key 'repository' is repeated"):
        load_policy_file(_policy(tmp_path, text))


def test_a_repeat_inside_a_mapping_that_is_merged_in_is_rejected(tmp_path):
    # The merged mapping is never built on its own, so it is checked as it is written.
    text = "claims:\n  repository:\n    <<: {equals: acme/api, equals: attacker/evil}\n"
    with pytest.raises(ValueError, match="the key 'equals' is repeated"):
        load_policy_file(_policy(tmp_path, text))


@pytest.mark.parametrize(("text", "lines"), MERGE_REPEATS.values(), ids=MERGE_REPEATS.keys())
def test_a_repeated_merge_key_is_rejected_at_every_level(tmp_path, text, lines):
    with pytest.raises(ValueError) as excinfo:
        load_policy_file(_policy(tmp_path, text))
    message = str(excinfo.value)
    assert f"policy: the key '<<' is repeated in one mapping (lines {lines})" in message
    # Both merges would be read, so "only the last" would not be true. It points at the
    # form that merges several mappings instead.
    assert "merge several mappings with one '<<: [*a, *b]'" in message


def test_one_merge_of_several_mappings_still_loads(tmp_path):
    # The form that error points at: one `<<`, with a list. A rule takes every key the
    # mappings supply, and a key the rule writes itself still wins.
    text = (
        "claims:\n"
        "  sub:\n    <<: [{matches: '^repo:acme/api:'}, &optional {required: false}]\n"
        "  ref:\n    <<: [*optional, {glob: 'refs/heads/*'}]\n    required: true\n"
    )
    rules = load_policy_file(_policy(tmp_path, text)).rules
    assert [(rule.name, rule.matches, rule.glob, rule.required) for rule in rules] == [
        ("sub", "^repo:acme/api:", None, False),
        ("ref", None, "refs/heads/*", True),
    ]


def test_a_key_overridden_after_a_merge_is_not_a_repeat(tmp_path):
    # YAML's merge key exists to be overridden: the rule takes the anchored one and
    # replaces its value. That is the author's stated intent, not a silent drop.
    text = (
        "claims:\n"
        "  repository: &pinned {equals: acme/api, required: true}\n"
        "  repository_owner:\n    <<: *pinned\n    equals: acme\n"
    )
    rules = load_policy_file(_policy(tmp_path, text)).rules
    assert [(rule.name, rule.equals, rule.required) for rule in rules] == [
        ("repository", "acme/api", True),
        ("repository_owner", "acme", True),
    ]


def test_the_same_key_in_two_mappings_is_not_a_repeat(tmp_path):
    # Every rule has its own 'equals'; a repeat is two equal keys in ONE mapping.
    text = "claims:\n  repository: {equals: acme/api}\n  repository_owner: {equals: acme}\n"
    assert len(load_policy_file(_policy(tmp_path, text)).rules) == 2
    rules = {"repository": {"equals": "acme/api"}, "repository_owner": {"equals": "acme"}}
    path = _policy(tmp_path, json.dumps({"claims": rules}), ".json")
    assert len(load_policy_file(path).rules) == 2


# --- through the CLI ---------------------------------------------------------


def _run(tmp_path, policy_text, suffix=".yaml"):
    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps(OTHER_REPO), encoding="utf-8")
    return main(["--claims", str(claims), "--policy", str(_policy(tmp_path, policy_text, suffix))])


@pytest.mark.parametrize(
    ("suffix", "text", "key"),
    [(".yaml", *case) for case in YAML_REPEATS.values()]
    + [(".json", *case) for case in JSON_REPEATS.values()]
    + [(".yaml", text, "<<") for text, _ in MERGE_REPEATS.values()],
    ids=[f"yaml-{level}" for level in YAML_REPEATS]
    + [f"json-{level}" for level in JSON_REPEATS]
    + [f"yaml-merge-{level}" for level in MERGE_REPEATS],
)
def test_cli_exits_2_on_a_repeated_key(tmp_path, capsys, suffix, text, key):
    # Was: rc=0 for every one of these, against a token from a different repository.
    assert _run(tmp_path, text, suffix) == 2
    out, err = capsys.readouterr()
    assert f"the key {key!r} is repeated in one mapping" in err
    assert out == "", "a policy that was rejected must not print a verdict"


@pytest.mark.parametrize(
    "text",
    [
        "claims:\n  repository: {equals: acme/api}\n",
        "claims:\n  sub: {matches: '^repo:acme/api:'}\n",
    ],
    ids=["first-rule", "first-pattern"],
)
def test_cli_control_the_first_rule_alone_still_fails_these_claims(tmp_path, capsys, text):
    # The claims above really are ones the policies should catch: the rule each repeat
    # silently dropped fails them on rc=1, exactly as its author meant it to.
    assert _run(tmp_path, text) == 1
    assert "does not satisfy" in capsys.readouterr().out
