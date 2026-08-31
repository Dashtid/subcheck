"""A malformed policy must be rejected, never silently weakened.

Every case here PASSED with rc=0 before the guards landed - the gate went green
while checking less than the author wrote. That is the one failure mode this
tool exists to prevent, so each case is pinned as a regression test.
"""

import json

import pytest

from subcheck import load_policy, validate
from subcheck.policy import load_policy_file
from subcheck.validator import FAIL, PASS

# --- claim rules written at the top level instead of under 'claims' ----------

def test_unknown_top_level_keys_are_rejected():
    # Was: silently ignored, so the policy checked only 'issuer' and passed a
    # token from an entirely different repository.
    with pytest.raises(ValueError, match="unknown top-level keys"):
        load_policy(
            {
                "issuer": "https://token.actions.githubusercontent.com",
                "repository": {"equals": "acme/payments-api"},
                "sub": {"matches": "^repo:acme/payments-api:"},
            }
        )


def test_the_documented_top_level_keys_are_still_accepted():
    policy = load_policy(
        {
            "issuer": "https://token.actions.githubusercontent.com",
            "audience": "sts.amazonaws.com",
            "claims": {"repository": {"equals": "acme/api"}},
        }
    )
    assert len(policy.rules) == 3


# --- rule value shapes -------------------------------------------------------

def test_in_must_be_a_list_not_a_string():
    # Was: `value not in "production"` - substring containment, so 'prod' and
    # even '' satisfied it. In YAML this is a one-item list missing its '- '.
    with pytest.raises(ValueError, match="'in' must be a list"):
        load_policy({"claims": {"environment": {"in": "production"}}})


def test_in_as_a_list_still_works():
    policy = load_policy({"claims": {"environment": {"in": ["production", "prod"]}}})
    assert validate({"environment": "prod"}, policy)[0].status == PASS
    assert validate({"environment": "staging"}, policy)[0].status == FAIL


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ({"matches": 123}, "'matches' must be a regex string"),
        ({"matches": "refs/heads/(main"}, "not a valid regex"),
        ({"glob": ["a", "b"]}, "'glob' must be a pattern string"),
        ({"required": "false"}, "'required' must be true or false"),
    ],
)
def test_malformed_rule_values_are_rejected(spec, expected):
    # Each of these previously escaped as a raw TypeError/re.error traceback
    # from validate(), exiting 1 - the "a claim did not match" code.
    with pytest.raises(ValueError, match=expected):
        load_policy({"claims": {"ref": spec}})


def test_equals_still_accepts_any_json_scalar():
    # equals compares with != against the claim's real JSON type, so a number
    # is a legitimate rule - the shape guards must not break it.
    policy = load_policy({"claims": {"run_attempt": {"equals": 1}}})
    assert validate({"run_attempt": 1}, policy)[0].status == PASS


# --- file-level parse failures ----------------------------------------------

def test_unparseable_yaml_policy_raises_valueerror(tmp_path):
    # yaml.YAMLError is not a ValueError (json.JSONDecodeError is), so this
    # escaped the CLI's rc=2 handler and exited 1.
    p = tmp_path / "policy.yaml"
    p.write_text("claims:\n  ref: {matches: '['\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid YAML"):
        load_policy_file(p)


def test_unparseable_json_policy_raises_valueerror(tmp_path):
    p = tmp_path / "policy.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy_file(p)


def test_every_shipped_example_policy_still_loads():
    from pathlib import Path

    examples = sorted(Path(__file__).resolve().parent.parent.glob("examples/policy*"))
    assert examples, "no example policies found"
    for path in examples:
        load_policy_file(path)


# --- describe() reports every constraint ------------------------------------

def test_describe_reports_all_constraints_not_just_the_first():
    # Was: only the first constraint was named, so a claim failing on the
    # regex was reported against the glob it actually satisfied.
    policy = load_policy({"claims": {"ref": {"glob": "refs/heads/*", "matches": "main$"}}})
    result = validate({"ref": "refs/tags/v1"}, policy)[0]
    assert result.status == FAIL
    assert "matches /main$/" in result.expected
    assert "glob 'refs/heads/*'" in result.expected


def test_json_policy_round_trips(tmp_path):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps({"claims": {"repository": {"equals": "acme/api"}}}), encoding="utf-8")
    assert len(load_policy_file(p).rules) == 1


# --- the glob matcher, previously untested anywhere ---------------------------

@pytest.mark.parametrize(
    ("pattern", "value", "expected"),
    [
        ("refs/heads/*", "refs/heads/main", PASS),
        ("refs/heads/*", "refs/tags/v1", FAIL),
        # fnmatch's '*' spans '/', exactly like AWS StringLike - a nested branch
        # still matches, which is the footgun the README documents.
        ("refs/heads/*", "refs/heads/feature/a", PASS),
        # fnmatchcase, so matching is case-sensitive.
        ("refs/heads/Main", "refs/heads/main", FAIL),
    ],
)
def test_glob_matching(pattern, value, expected):
    policy = load_policy({"claims": {"ref": {"glob": pattern}}})
    assert validate({"ref": value}, policy)[0].status == expected


# --- the equals FAIL path, previously never exercised -------------------------

def test_equals_mismatch_fails():
    # `equals` is the most common rule type and no test had ever made one FAIL:
    # every existing failure case went through `matches` or an absent claim.
    policy = load_policy({"claims": {"repository": {"equals": "acme/api"}}})
    ok, bad = (validate({"repository": v}, policy)[0] for v in ("acme/api", "attacker/evil"))
    assert ok.status == PASS
    assert bad.status == FAIL
    assert bad.severity == "high"
    assert "attacker/evil" in bad.message


def test_equals_shorthand_string_form_fails_too():
    # The bare-string shorthand builds the same rule as {"equals": ...}.
    policy = load_policy({"claims": {"repository": "acme/api"}})
    assert validate({"repository": "attacker/evil"}, policy)[0].status == FAIL
