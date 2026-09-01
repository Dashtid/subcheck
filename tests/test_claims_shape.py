"""A claims file that is not a JSON object must be rejected, not half-processed.

`decode_claims` has always rejected a JWT payload that is not an object. `--claims`
went straight to `json.loads` with no such check, so the two claim-input paths
disagreed about what "claims" means. Three things followed from that asymmetry,
all reproduced on 0.4.1 and all pinned below:

* `validate()` returned **all PASS** for list-shaped claims - `rule.name not in
  claims` is legal on any container, so every rule read as absent, which is PASS
  for an optional rule. Only an unrelated crash further down stopped a green report.
* `--claims <non-object> --format json` with no policy printed the garbage and
  **exited 0**.
* Every other combination raised an AttributeError traceback and exited **1** - the
  "a claim did not match" code, so bad input was indistinguishable from a real
  gate failure.
"""

import json

import pytest

from subcheck import build_report, load_policy, validate
from subcheck.cli import main
from subcheck.validator import MISSING, PASS

NOT_OBJECTS = [[], [1, 2, 3], "hello", 42, None, True]

OPTIONAL_POLICY = {
    "claims": {
        "repository": {"equals": "acme/api", "required": False},
        "sub": {"matches": "^repo:acme/api:", "required": False},
    }
}


# --- the library API ---------------------------------------------------------

@pytest.mark.parametrize("claims", NOT_OBJECTS + [()])
def test_validate_rejects_claims_that_are_not_a_mapping(claims):
    # Was: [] and (1,2,3) returned one PASS per rule, so an all-optional policy
    # reported a clean pass over claims holding nothing at all.
    with pytest.raises(ValueError, match="mapping/object"):
        validate(claims, load_policy(OPTIONAL_POLICY))


@pytest.mark.parametrize("claims", NOT_OBJECTS)
def test_build_report_rejects_claims_that_are_not_a_mapping(claims):
    with pytest.raises(ValueError, match="mapping/object"):
        build_report(claims, [])


def test_an_empty_claims_object_is_still_accepted():
    # The guard must reject the wrong SHAPE, not an empty token: {} is a legitimate
    # (if useless) claim set, and a required rule should report MISSING as before.
    policy = load_policy({"claims": {"repository": {"equals": "acme/api"}}})
    assert [r.status for r in validate({}, policy)] == [MISSING]
    assert [r.status for r in validate({}, load_policy(OPTIONAL_POLICY))] == [PASS, PASS]


# --- through the CLI ---------------------------------------------------------

def _claims_file(tmp_path, value):
    f = tmp_path / "claims.json"
    f.write_text(json.dumps(value), encoding="utf-8")
    return str(f)


@pytest.mark.parametrize("claims", NOT_OBJECTS)
def test_cli_rejects_a_non_object_claims_file_on_rc2(tmp_path, capsys, claims):
    # Was: rc=1 with an AttributeError traceback - the gate-failure exit code.
    assert main(["--claims", _claims_file(tmp_path, claims)]) == 2
    assert "did not decode to a JSON object" in capsys.readouterr().err


@pytest.mark.parametrize("claims", NOT_OBJECTS)
def test_cli_json_format_no_longer_exits_zero_on_a_non_object(tmp_path, capsys, claims):
    # Was: rc=0, echoing the garbage back as if it were a decoded token. This is
    # the worst of the three - a silent success on input that is not claims.
    assert main(["--claims", _claims_file(tmp_path, claims), "--format", "json"]) == 2
    assert "did not decode to a JSON object" in capsys.readouterr().err


def test_cli_rejects_a_non_object_claims_file_with_a_policy(tmp_path, capsys):
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps(OPTIONAL_POLICY), encoding="utf-8")
    rc = main(["--claims", _claims_file(tmp_path, []), "--policy", str(policy)])
    assert rc == 2
    assert "did not decode to a JSON object" in capsys.readouterr().err


def test_both_claim_input_paths_agree_on_what_claims_are(tmp_path, capsys, make_jwt):
    # Parity: the token path has always rejected a non-object payload. The point of
    # the fix is that --claims now gives the same verdict and the same exit code.
    token = tmp_path / "token.jwt"
    token.write_text(make_jwt(["not", "an", "object"]), encoding="utf-8")
    assert main(["--token-file", str(token)]) == 2
    assert "did not decode to a JSON object" in capsys.readouterr().err

    assert main(["--claims", _claims_file(tmp_path, ["not", "an", "object"])]) == 2
    assert "did not decode to a JSON object" in capsys.readouterr().err
