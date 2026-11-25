import pytest

from subcheck import load_policy, validate
from subcheck.cli import main
from subcheck.validator import FAIL, MISSING, PASS


def _policy():
    return load_policy(
        {
            "issuer": "https://token.actions.githubusercontent.com",
            "audience": "sts.amazonaws.com",
            "claims": {
                "repository": {"equals": "acme/api"},
                "sub": {"matches": r"^repo:acme/api:(ref:refs/heads/main|environment:production)$"},
                "runner_environment": {"equals": "github-hosted"},
                "environment": {"equals": "production", "required": True},
            },
        }
    )


def _good_claims():
    return {
        "iss": "https://token.actions.githubusercontent.com",
        "aud": "sts.amazonaws.com",
        "sub": "repo:acme/api:environment:production",
        "repository": "acme/api",
        "runner_environment": "github-hosted",
        "environment": "production",
    }


def test_all_pass():
    results = validate(_good_claims(), _policy())
    assert all(r.status == PASS for r in results)


def test_sub_mismatch_fails_high_and_env_missing():
    claims = _good_claims()
    claims["sub"] = "repo:acme/api:pull_request"
    claims.pop("environment")  # a pull_request token has no environment
    by_claim = {r.claim: r for r in validate(claims, _policy())}
    assert by_claim["sub"].status == FAIL
    assert by_claim["sub"].severity == "high"
    assert by_claim["environment"].status == MISSING


def test_optional_claim_absent_passes():
    policy = load_policy({"claims": {"actor": {"equals": "bot", "required": False}}})
    assert validate({}, policy)[0].status == PASS


def test_one_of_list():
    policy = load_policy({"claims": {"ref": ["refs/heads/main", "refs/heads/release"]}})
    assert validate({"ref": "refs/heads/main"}, policy)[0].status == PASS
    assert validate({"ref": "refs/heads/dev"}, policy)[0].status == FAIL


def test_unknown_rule_key_rejected():
    with pytest.raises(ValueError):
        load_policy({"claims": {"sub": {"eq": "x"}}})


# --- equals and in compare JSON values, and a boolean is not a number --------


def _status(spec, value):
    policy = load_policy({"claims": {"run_attempt": spec}})
    return validate({"run_attempt": value}, policy)[0].status


@pytest.mark.parametrize(
    ("spec", "value"),
    [
        ({"equals": True}, 1),
        ({"equals": 1}, True),
        ({"equals": 1.0}, True),
        ({"equals": False}, 0),
        ({"in": [1]}, True),
        ({"in": [True]}, 1),
        ([0, "x"], False),
        # Inside an array or an object the same holds, item by item.
        ({"equals": [1]}, [True]),
        ({"equals": {"a": 1}}, {"a": True}),
        ({"in": [[True]]}, [1]),
    ],
    ids=[
        "equals-true-vs-1",
        "equals-1-vs-true",
        "equals-1.0-vs-true",
        "equals-false-vs-0",
        "in-1-vs-true",
        "in-true-vs-1",
        "shorthand-0-vs-false",
        "equals-array",
        "equals-object",
        "in-array",
    ],
)
def test_a_boolean_never_equals_a_number(spec, value):
    # Was: PASS for every one. bool is an int subclass in Python, so True == 1 and
    # True in [1]: a JSON boolean satisfied a rule written as a number, and the reverse.
    assert _status(spec, value) == FAIL


@pytest.mark.parametrize(
    ("spec", "value"),
    [
        ({"equals": "1"}, 1),
        ({"equals": 1}, "1"),
        ({"in": ["1"]}, 1),
        ({"equals": "true"}, True),
        ({"equals": True}, "true"),
    ],
    ids=[
        "equals-string-vs-number",
        "equals-number-vs-string",
        "in-string-vs-number",
        "equals-string-vs-true",
        "equals-true-vs-string",
    ],
)
def test_a_string_never_equals_a_number_or_a_boolean(spec, value):
    # Unchanged, and documented: quote a number you expect as a string.
    assert _status(spec, value) == FAIL


@pytest.mark.parametrize(
    ("spec", "value"),
    [
        ({"equals": [1]}, [1, 1]),
        ({"equals": [1, 1]}, [1]),
        ({"equals": {"a": 1}}, {"a": 1, "b": 1}),
        ({"equals": {"a": 1, "b": 1}}, {"a": 1}),
    ],
    ids=["longer-array", "shorter-array", "extra-key", "missing-key"],
)
def test_an_array_or_object_must_match_in_full(spec, value):
    # Items are compared pair by pair, so a value with more or fewer items or keys
    # than the rule must fail, not pass on the ones the two share.
    assert _status(spec, value) == FAIL


@pytest.mark.parametrize(
    ("spec", "value"),
    [
        ({"equals": True}, True),
        ({"equals": False}, False),
        ({"in": [1, True]}, True),
        ({"in": [1, True]}, 1),
        # One JSON number type: 1 and 1.0 are equal, as they always were.
        ({"equals": 1}, 1.0),
        ({"equals": 1.0}, 1),
        ({"in": [1.0]}, 1),
        ({"equals": [True, 1]}, [True, 1.0]),
        ({"equals": {"a": [True]}}, {"a": [True]}),
    ],
    ids=[
        "equals-true",
        "equals-false",
        "in-true",
        "in-1",
        "equals-1-vs-1.0",
        "equals-1.0-vs-1",
        "in-1.0-vs-1",
        "equals-array",
        "equals-object",
    ],
)
def test_equal_json_values_still_pass(spec, value):
    assert _status(spec, value) == PASS


@pytest.mark.parametrize(
    ("suffix", "policy_text"),
    [
        (".yaml", "claims:\n  run_attempt:\n    equals: 1\n"),
        (".json", '{"claims": {"run_attempt": {"in": [1]}}}'),
    ],
    ids=["yaml-equals", "json-in"],
)
def test_cli_fails_a_boolean_claim_against_a_number(tmp_path, capsys, suffix, policy_text):
    # Was: PASS (1 pass, 0 fail, 0 missing) and exit 0.
    claims = tmp_path / "claims.json"
    claims.write_text('{"run_attempt": true}', encoding="utf-8")
    policy = tmp_path / f"policy{suffix}"
    policy.write_text(policy_text, encoding="utf-8")
    assert main(["--claims", str(claims), "--policy", str(policy)]) == 1
    assert "claim 'run_attempt'=True does not satisfy" in capsys.readouterr().out
