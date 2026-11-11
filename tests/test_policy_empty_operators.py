"""An operator with no value must be rejected, never read as no constraint.

`repository: {equals: }` is YAML for `equals: null`, and a null operator read
exactly like an absent one. A rule left with no operator is a bare presence check,
so the gate passed any token that carried the claim at all: PASS and rc=0 for
claims naming a different repository, through the shipped CLI on 0.5.0. Same class
as the two fail-opens 0.4.1 closed - the key was accepted and its value was never
checked.

`claims:` itself had the same hole one level up. Left with no rules under it - or
given `[]`, `''`, `false`, `0` or `{}` - it read as "no claim rules", so a policy
that also set `issuer` and `audience` checked only those two and passed a token
from any repository.

A rule with no operator at all was the same presence check by another road.
`repository: {}` - which is what a serializer that drops null keys makes of
`{"equals": null}` - passed any token carrying the claim, and `{required: false}`
alone could not fail. A presence check has to be asked for, as `{required: true}`.

The empty values are decided by what the matcher does with them, not by how they
look:

* `matches: ''` - `re.search('', s)` succeeds on every string, so it is the same
  presence check as a null operator, and it is rejected the same way;
* `in: []` - no value is a member of an empty list, so every token carrying the
  claim failed on rc=1: fail-closed, but a policy mistake reported as a finding,
  which is the confusion rc=2 exists to prevent;
* `equals: ''` and `glob: ''` stay valid - each matches only an empty claim value,
  so they constrain rather than skip. GitHub's documented example token carries
  `head_ref: ""` on a `workflow_dispatch` run, so pinning an empty value is a real
  rule.
"""

import json
import re

import pytest

from subcheck import load_policy, validate
from subcheck.cli import main
from subcheck.policy import load_policy_file
from subcheck.validator import FAIL, MISSING, PASS

OPERATORS = ["equals", "in", "matches", "glob"]

# A token from a repository the policies below were written to keep out.
OTHER_REPO = {
    "iss": "https://token.actions.githubusercontent.com",
    "aud": "sts.amazonaws.com",
    "sub": "repo:attacker/evil:ref:refs/heads/feature",
    "repository": "attacker/evil",
    "ref": "refs/heads/feature",
    "environment": "staging",
}

# The top-level shortcuts, which that token satisfies: on their own they cannot
# keep it out, so whatever stands under 'claims' is the whole gate.
ISS_AUD = {"issuer": OTHER_REPO["iss"], "audience": OTHER_REPO["aud"]}
ISS_AUD_YAML = f"issuer: {OTHER_REPO['iss']}\naudience: {OTHER_REPO['aud']}\n"

# --- an operator with no value -----------------------------------------------


@pytest.mark.parametrize("op", OPERATORS)
def test_an_operator_with_no_value_is_rejected(op):
    # Was: a presence check - "claim 'repository' satisfies present", PASS.
    with pytest.raises(ValueError) as excinfo:
        load_policy({"claims": {"repository": {op: None}}})
    message = str(excinfo.value)
    assert f"claim 'repository': '{op}' has no value" in message
    # The way out, for an author who did mean "present, with any value".
    assert "repository: {required: true}" in message


@pytest.mark.parametrize("op", OPERATORS)
def test_yaml_reads_an_empty_operator_as_null_and_the_loader_rejects_it(tmp_path, op):
    p = tmp_path / "policy.yaml"
    p.write_text(f"claims:\n  repository:\n    {op}:\n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"'{op}' has no value"):
        load_policy_file(p)


def test_a_null_operator_is_rejected_beside_one_that_has_a_value():
    # The empty one is still a constraint the author meant to write.
    with pytest.raises(ValueError, match="'matches' has no value"):
        load_policy({"claims": {"ref": {"glob": "refs/heads/*", "matches": None}}})


def test_a_null_operator_is_rejected_on_an_optional_rule_too():
    # Was a rule that could not fail: absent passed as optional, present passed
    # as a presence check.
    with pytest.raises(ValueError, match="'equals' has no value"):
        load_policy({"claims": {"environment": {"equals": None, "required": False}}})


# --- a rule with no operator at all ------------------------------------------


@pytest.mark.parametrize("spec", [{}, {"required": False}], ids=["empty-mapping", "optional-only"])
def test_a_rule_with_no_operator_is_rejected(spec):
    # Was: `{}` a presence check, passing the same tokens a null operator did,
    # and `{required: false}` a rule that could not fail at all.
    with pytest.raises(ValueError) as excinfo:
        load_policy({"claims": {"repository": spec}})
    message = str(excinfo.value)
    assert "claim 'repository': the rule has no operator" in message
    assert "repository: {required: true}" in message


@pytest.mark.parametrize("key", ["issuer", "audience"])
def test_the_top_level_shortcuts_with_no_value_are_rejected(key):
    # Was: str(None), a rule demanding the literal string 'None', so every token
    # failed on rc=1 - fail-closed, but a broken policy wearing the finding code.
    with pytest.raises(ValueError, match=f"policy: '{key}' has no value"):
        load_policy({key: None, "claims": {"repository": "acme/api"}})


def test_issuer_and_audience_alone_are_still_a_policy():
    # What the error offers instead of an empty 'claims' is to remove the key. A
    # policy that checks only iss and aud is legitimate when it says so.
    assert [rule.name for rule in load_policy(dict(ISS_AUD)).rules] == ["iss", "aud"]


# --- empty values ------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        # Was: PASS for every value - re.search('', s) always matches.
        ({"matches": ""}, "'matches' is an empty pattern, which every value matches"),
        # Was: FAIL for every value, on rc=1 - nothing is in an empty list.
        ({"in": []}, "'in' is an empty list, which no value can match"),
        ([], "an empty list (the shorthand for 'in') matches no value"),
    ],
    ids=["matches-empty", "in-empty", "shorthand-empty"],
)
def test_empty_values_that_cannot_constrain_are_rejected(spec, expected):
    with pytest.raises(ValueError, match=re.escape(expected)):
        load_policy({"claims": {"environment": spec}})


@pytest.mark.parametrize(
    "spec",
    [{"equals": ""}, {"glob": ""}, "", {"in": [""]}],
    ids=["equals-empty", "glob-empty", "shorthand-empty-string", "in-holding-empty"],
)
def test_an_empty_string_is_a_real_constraint_not_a_presence_check(spec):
    # Each matches only an empty claim value, so none of them may be rejected or
    # read as "no constraint".
    policy = load_policy({"claims": {"head_ref": spec}})
    assert validate({"head_ref": ""}, policy)[0].status == PASS
    assert validate({"head_ref": "feature-branch"}, policy)[0].status == FAIL


def test_the_explicit_presence_check_still_works():
    # What the error message offers instead: `required` with no operator at all.
    policy = load_policy({"claims": {"environment": {"required": True}}})
    assert policy.rules[0].describe() == "present"
    assert validate({"environment": "anything"}, policy)[0].status == PASS
    assert validate({}, policy)[0].status == MISSING


# --- through the CLI ---------------------------------------------------------


def _run(tmp_path, policy_text, suffix=".yaml"):
    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps(OTHER_REPO), encoding="utf-8")
    policy = tmp_path / f"policy{suffix}"
    policy.write_text(policy_text, encoding="utf-8")
    return main(["--claims", str(claims), "--policy", str(policy)])


@pytest.mark.parametrize(
    ("policy_text", "expected"),
    [
        # Was: PASS (3 pass, 0 fail, 0 missing), rc=0 - a deploy policy whose one
        # repository pin was left empty waved through a different repository.
        (
            "issuer: https://token.actions.githubusercontent.com\n"
            "audience: sts.amazonaws.com\n"
            "claims:\n  repository:\n    equals:\n",
            "claim 'repository': 'equals' has no value",
        ),
        ("claims:\n  repository: {equals: }\n", "claim 'repository': 'equals' has no value"),
        ("claims:\n  sub:\n    matches:\n", "claim 'sub': 'matches' has no value"),
        ("claims:\n  ref:\n    glob:\n", "claim 'ref': 'glob' has no value"),
        ("claims:\n  environment:\n    in:\n", "claim 'environment': 'in' has no value"),
        ("claims:\n  sub:\n    matches: ''\n", "claim 'sub': 'matches' is an empty pattern"),
        # These two exited 1, reporting a policy mistake as a finding.
        ("claims:\n  environment:\n    in: []\n", "claim 'environment': 'in' is an empty list"),
        ("claims:\n  environment: []\n", "the shorthand for 'in'"),
        ("issuer:\naudience: sts.amazonaws.com\n", "policy: 'issuer' has no value"),
    ],
    ids=[
        "deploy-policy",
        "equals-flow",
        "matches",
        "glob",
        "in",
        "matches-empty",
        "in-empty",
        "shorthand-empty",
        "issuer",
    ],
)
def test_cli_exits_2_on_a_rule_that_cannot_constrain(tmp_path, capsys, policy_text, expected):
    assert _run(tmp_path, policy_text) == 2
    out, err = capsys.readouterr()
    assert expected in err
    assert out == "", "a policy that was rejected must not print a verdict"


_NOT_A_MAPPING = "policy 'claims' must be a mapping of claim -> rule, got"


@pytest.mark.parametrize(
    ("suffix", "policy_text", "expected"),
    [
        # YAML reads `claims:` as null whether nothing follows it or only comments
        # do - the shape a policy takes when its last rule is commented out.
        (
            ".yaml",
            ISS_AUD_YAML + "claims:\n  # repository: acme/payments-api\n",
            "policy: 'claims' has no value",
        ),
        (".json", json.dumps({**ISS_AUD, "claims": None}), "policy: 'claims' has no value"),
        (".yaml", ISS_AUD_YAML + "claims: []\n", f"{_NOT_A_MAPPING} list"),
        (".yaml", ISS_AUD_YAML + "claims: ''\n", f"{_NOT_A_MAPPING} str"),
        (".yaml", ISS_AUD_YAML + "claims: false\n", f"{_NOT_A_MAPPING} bool"),
        (".yaml", ISS_AUD_YAML + "claims: 0\n", f"{_NOT_A_MAPPING} int"),
        (".yaml", ISS_AUD_YAML + "claims: {}\n", "policy: 'claims' is empty"),
    ],
    ids=["no-value", "json-null", "empty-list", "empty-string", "false", "zero", "empty-mapping"],
)
def test_cli_exits_2_on_claims_with_no_rules(tmp_path, capsys, suffix, policy_text, expected):
    # Was: PASS (2 pass, 0 fail, 0 missing), rc=0, for every one of these. The
    # loader read each as "no claim rules", so the gate checked only iss and aud
    # and passed a token from any repository.
    assert _run(tmp_path, policy_text, suffix) == 2
    out, err = capsys.readouterr()
    assert expected in err
    assert out == "", "a policy that was rejected must not print a verdict"


@pytest.mark.parametrize(
    ("suffix", "policy_text"),
    [
        (".yaml", "claims:\n  repository: {}\n"),
        # What a serializer that drops null keys makes of {"equals": null}.
        (".json", json.dumps({"claims": {"repository": {}}})),
        # Was: PASS (3 pass, 0 fail, 0 missing), rc=0 - the deploy policy again.
        (".yaml", ISS_AUD_YAML + "claims:\n  repository: {}\n"),
    ],
    ids=["yaml", "json", "deploy-policy"],
)
def test_cli_exits_2_on_a_rule_with_no_operator(tmp_path, capsys, suffix, policy_text):
    # Was: "claim 'repository' satisfies present" and rc=0 for a different repository.
    assert _run(tmp_path, policy_text, suffix) == 2
    out, err = capsys.readouterr()
    assert "claim 'repository': the rule has no operator" in err
    assert out == "", "a policy that was rejected must not print a verdict"


def test_cli_control_the_same_rule_with_a_value_still_fails_these_claims(tmp_path, capsys):
    # The claims above really are ones the policy should catch: with the value
    # filled in, the gate fails them on rc=1 exactly as before.
    assert _run(tmp_path, "claims:\n  repository:\n    equals: acme/payments-api\n") == 1
    assert "does not satisfy equals 'acme/payments-api'" in capsys.readouterr().out
