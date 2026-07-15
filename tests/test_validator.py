from subcheck import load_policy, validate
from subcheck.validator import FAIL, MISSING, PASS


def _policy():
    return load_policy(
        {
            "issuer": "https://token.actions.githubusercontent.com",
            "audience": "sts.amazonaws.com",
            "claims": {
                "repository": {"equals": "acme/api"},
                "sub": {
                    "matches": r"^repo:acme/api:(ref:refs/heads/main|environment:production)$"
                },
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
    import pytest

    with pytest.raises(ValueError):
        load_policy({"claims": {"sub": {"eq": "x"}}})
