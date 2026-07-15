import json

import pytest

from subcheck.cli import main


def test_inspect_only_prints_claims(examples_dir, capsys):
    rc = main(["--claims", str(examples_dir / "claims-main.json")])
    assert rc == 0
    assert "repository: acme/payments-api" in capsys.readouterr().out


def test_policy_pass_json(examples_dir):
    rc = main(
        [
            "--claims", str(examples_dir / "claims-main.json"),
            "--policy", str(examples_dir / "policy.json"),
            "--format", "json",
        ]
    )
    assert rc == 0


def test_policy_fail_pull_request(examples_dir, capsys):
    rc = main(
        [
            "--claims", str(examples_dir / "claims-pull-request.json"),
            "--policy", str(examples_dir / "policy.json"),
        ]
    )
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out


def test_policy_yaml_when_available(examples_dir):
    pytest.importorskip("yaml")
    rc = main(
        [
            "--claims", str(examples_dir / "claims-main.json"),
            "--policy", str(examples_dir / "policy.yaml"),
        ]
    )
    assert rc == 0


def test_token_input(make_jwt, capsys):
    token = make_jwt({"sub": "repo:acme/payments-api:environment:production"})
    rc = main(["--token", token, "--format", "json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["sub"].endswith("production")


def test_missing_input_errors(capsys):
    rc = main([])
    assert rc == 2
    assert "error" in capsys.readouterr().err
