"""The claim-input paths and the failure exits, which had no coverage.

`--token-file` and `--token -` are how the shipped GitHub Action feeds subcheck
(action.yml pipes the token into `--token -`), so the tool's own advertised entry
point ran on code no test executed.
"""

import json
import subprocess
import sys

import pytest

from subcheck.cli import main


def test_token_file(make_jwt, tmp_path, capsys):
    jwt = make_jwt({"iss": "https://token.actions.githubusercontent.com", "repository": "acme/api"})
    f = tmp_path / "token.jwt"
    f.write_text(jwt, encoding="utf-8")
    assert main(["--token-file", str(f)]) == 0
    assert "repository: acme/api" in capsys.readouterr().out


def test_token_stdin(make_jwt, monkeypatch, capsys):
    # The action.yml path: `... | python3 -m subcheck --token - ...`
    jwt = make_jwt({"iss": "https://token.actions.githubusercontent.com", "repository": "acme/api"})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(jwt + "\n"))
    assert main(["--token", "-"]) == 0
    assert "repository: acme/api" in capsys.readouterr().out


def test_token_stdin_then_policy(make_jwt, monkeypatch, tmp_path, capsys):
    jwt = make_jwt({"iss": "https://x", "repository": "acme/api"})
    policy = tmp_path / "p.json"
    policy.write_text(
        json.dumps({"claims": {"repository": {"equals": "acme/api"}}}), encoding="utf-8"
    )
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(jwt))
    assert main(["--token", "-", "--policy", str(policy)]) == 0


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b", "a.!!!!.c"])
def test_malformed_token_exits_2(token, capsys):
    assert main(["--token", token]) == 2
    assert "error:" in capsys.readouterr().err


def test_token_payload_that_is_not_an_object_exits_2(capsys):
    import base64

    def seg(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    jwt = f"{seg({'alg': 'none'})}.{seg(['not', 'an', 'object'])}.xxxxxxxx"
    assert main(["--token", jwt]) == 2


def test_missing_claims_file_exits_2(capsys):
    assert main(["--claims", "no-such-file.json"]) == 2
    assert "error:" in capsys.readouterr().err


def test_policy_file_with_unknown_suffix_is_read_as_json(tmp_path, make_jwt, monkeypatch):
    # load_policy_file only special-cases .yaml/.yml; everything else is JSON.
    policy = tmp_path / "policy.txt"
    policy.write_text(
        json.dumps({"claims": {"repository": {"equals": "acme/api"}}}), encoding="utf-8"
    )
    claims = tmp_path / "c.json"
    claims.write_text(json.dumps({"repository": "acme/api"}), encoding="utf-8")
    assert main(["--claims", str(claims), "--policy", str(policy)]) == 0


def test_json_format_report_shape(examples_dir, capsys):
    rc = main(["--claims", str(examples_dir / "claims-pull-request.json"),
               "--policy", str(examples_dir / "policy.json"), "--format", "json"])
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is False
    assert report["summary"]["fail"] >= 1
    counted = sum(report["summary"][k] for k in ("pass", "fail", "missing"))
    assert counted == len(report["results"])
    assert isinstance(report["notes"], list)


def test_python_dash_m_entry_point():
    # `python -m subcheck` is what action.yml invokes; __main__.py had 0% coverage.
    # Run out-of-process against this checkout, so it works whether or not the
    # package happens to be installed in the environment running the tests.
    import os
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src"
    env = {**os.environ, "PYTHONPATH": str(src)}
    r = subprocess.run([sys.executable, "-m", "subcheck", "--version"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "subcheck" in r.stdout


def test_python_dash_m_subcheck_cli_entry_point():
    # cli.py carries its own `if __name__ == "__main__"` guard, reachable as
    # `python -m subcheck.cli`. Both entry points are real; exercise both.
    import os
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src"
    env = {**os.environ, "PYTHONPATH": str(src)}
    r = subprocess.run([sys.executable, "-m", "subcheck.cli", "--version"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "subcheck" in r.stdout
