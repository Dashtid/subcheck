"""A malformed policy must be rejected, never silently weakened.

Every case here PASSED with rc=0 before the guards landed - the gate went green
while checking less than the author wrote. That is the one failure mode this
tool exists to prevent, so each case is pinned as a regression test.
"""

import json
import re
import sys

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


@pytest.mark.parametrize(
    "pattern",
    [
        "a{4294967296}",
        # One level per frame of the limit is deeper than re's recursive parser can go.
        "(" * sys.getrecursionlimit() + ")" * sys.getrecursionlimit(),
    ],
    ids=["repeat-count-overflow", "groups-nested-too-deep"],
)
def test_a_regex_re_cannot_compile_is_rejected_whatever_re_raises(pattern):
    # re.compile raises more than re.error. The OverflowError for a repeat count
    # past its limit escaped as a traceback on rc=1; the RecursionError for deep
    # nesting reached rc=2 only as a RuntimeError, naming neither claim nor regex.
    with pytest.raises(ValueError, match="claim 'sub': 'matches' is not a valid regex"):
        load_policy({"claims": {"sub": {"matches": pattern}}})


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


# --- the remaining rejection paths -------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (["not", "a", "mapping"], "policy must be a mapping"),
        ({"claims": ["not", "a", "mapping"]}, "'claims' must be a mapping"),
        ({}, "policy is empty"),
        ({"claims": {"ref": 42}}, "rule must be a string, list, or mapping"),
    ],
)
def test_structurally_invalid_policies_are_rejected(data, expected):
    with pytest.raises(ValueError, match=expected):
        load_policy(data)


def test_bad_policy_file_exits_2_through_the_cli(tmp_path, capsys):
    from subcheck.cli import main

    claims = tmp_path / "c.json"
    claims.write_text('{"repository": "acme/api"}', encoding="utf-8")
    policy = tmp_path / "p.json"
    policy.write_text('{"claims": {"environment": {"in": "production"}}}', encoding="utf-8")
    assert main(["--claims", str(claims), "--policy", str(policy)]) == 2
    assert "must be a list" in capsys.readouterr().err


def test_missing_policy_file_exits_2_through_the_cli(tmp_path, capsys):
    from subcheck.cli import main

    claims = tmp_path / "c.json"
    claims.write_text('{"repository": "acme/api"}', encoding="utf-8")
    assert main(["--claims", str(claims), "--policy", str(tmp_path / "nope.json")]) == 2
    assert "error:" in capsys.readouterr().err


# --- unknown keys that are not all strings -----------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({1: "x", "foo": "y"}, "policy: unknown top-level keys [1, 'foo']"),
        ({"claims": {"repository": {1: "a", "b": "c"}}}, "unknown rule keys [1, 'b']"),
    ],
    ids=["top-level", "rule"],
)
def test_unknown_keys_of_mixed_types_are_named_not_crashed_on(data, expected):
    # Was: sorting the unknown keys compared an int with a str and raised
    # TypeError, which the CLI does not catch - a traceback on rc=1.
    with pytest.raises(ValueError, match=re.escape(expected)):
        load_policy(data)


def test_unknown_keys_of_mixed_types_exit_2_through_the_cli(tmp_path, capsys):
    from subcheck.cli import main

    claims = tmp_path / "c.json"
    claims.write_text('{"repository": "acme/api"}', encoding="utf-8")
    policy = tmp_path / "p.yaml"
    # YAML reads the bare 1 as an int key.
    policy.write_text("claims:\n  repository: {1: a, b: c}\n", encoding="utf-8")
    assert main(["--claims", str(claims), "--policy", str(policy)]) == 2
    assert "claim 'repository': unknown rule keys [1, 'b']" in capsys.readouterr().err


# --- claim names that are not strings ----------------------------------------


@pytest.mark.parametrize("name", [1, None, True, ""], ids=["int", "null", "bool", "empty"])
def test_a_claim_name_must_be_a_non_empty_string(name):
    # Was: loaded. The text report crashed on len(name), --format json reported
    # normally, and an optional rule under a null name could never fail.
    expected = f"policy: claim names must be non-empty strings, got {name!r}"
    with pytest.raises(ValueError, match=re.escape(expected)):
        load_policy({"claims": {name: {"equals": "x"}}})


def test_a_claim_name_that_is_not_a_string_exits_2_through_the_cli(tmp_path, capsys):
    from subcheck.cli import main

    claims = tmp_path / "c.json"
    claims.write_text('{"repository": "acme/api"}', encoding="utf-8")
    policy = tmp_path / "p.yaml"
    # Was: TypeError from len(1) in the text report - a traceback on rc=1.
    policy.write_text("claims:\n  1: {equals: x}\n", encoding="utf-8")
    assert main(["--claims", str(claims), "--policy", str(policy)]) == 2
    out, err = capsys.readouterr()
    assert out == "", "a policy that was rejected must not print a verdict"
    assert "policy: claim names must be non-empty strings, got 1" in err


# --- the issuer and audience shortcuts take a string ---------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        # A JWT `aud` may be an array, so a list is the natural slip.
        ({"audience": ["sts.amazonaws.com"]}, "policy: 'audience' must be a string, got list"),
        ({"issuer": False}, "policy: 'issuer' must be a string, got bool"),
        ({"audience": {"value": "x"}}, "policy: 'audience' must be a string, got dict"),
        # YAML reads an unquoted 12345 as an int, and `0123` as 83.
        ({"audience": 12345}, "policy: 'audience' must be a string, got int"),
    ],
    ids=["audience-list", "issuer-false", "audience-mapping", "audience-number"],
)
def test_the_issuer_and_audience_shortcuts_must_be_strings(data, expected):
    # Was: str() of the value, a rule no token could satisfy - every token
    # failed on rc=1, a broken policy wearing the finding code.
    with pytest.raises(ValueError, match=re.escape(expected)):
        load_policy({**data, "claims": {"repository": "acme/api"}})


def test_a_quoted_numeric_audience_still_works():
    # What the error asks for instead: quoted, it is the string a token carries.
    policy = load_policy({"audience": "12345"})
    assert validate({"aud": "12345"}, policy)[0].status == PASS


def test_a_non_string_audience_exits_2_through_the_cli(tmp_path, capsys):
    from subcheck.cli import main

    claims = tmp_path / "c.json"
    claims.write_text('{"aud": "sts.amazonaws.com"}', encoding="utf-8")
    policy = tmp_path / "p.yaml"
    # Was: FAIL (0 pass, 1 fail, 0 missing) and rc=1, against the very audience it lists.
    policy.write_text("audience: [sts.amazonaws.com]\n", encoding="utf-8")
    assert main(["--claims", str(claims), "--policy", str(policy)]) == 2
    out, err = capsys.readouterr()
    assert out == "", "a policy that was rejected must not print a verdict"
    assert "policy: 'audience' must be a string, got list" in err
