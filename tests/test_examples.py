"""Every shipped example must still load and run.

`examples/` is copy-paste material exactly like the README quickstart, and half of
it had no test: the immutable pair (0.2.0) and the reusable-workflow pair (0.4.0)
were never loaded by anything. A policy tightening could therefore break a shipped
example silently - 0.4.1 started rejecting unknown top-level keys, which is
precisely the kind of change that would.

The discovery-based tests below matter more than the explicit pairs: a new example
is covered the moment the file lands, without anyone remembering to add a case.
Each one asserts its own glob is non-empty first, because a parametrized test over
an empty glob passes vacuously - the same shape of fail-open this project keeps
finding elsewhere.
"""

import json
from pathlib import Path

import pytest

from subcheck import build_report, load_policy_file, validate
from subcheck.cli import main

# Mirrors conftest's EXAMPLES; needed at import time for parametrization, and
# `tests` is not an importable package.
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

POLICIES = sorted(p for p in EXAMPLES.glob("policy*") if p.suffix in {".json", ".yaml", ".yml"})
CLAIMS = sorted(EXAMPLES.glob("claims-*.json"))


def test_the_globs_actually_found_the_examples():
    # Without this, renaming the directory turns every test below into a no-op
    # that still reports green.
    assert len(POLICIES) >= 4, f"expected the shipped policy examples, found {POLICIES}"
    assert len(CLAIMS) >= 4, f"expected the shipped claims examples, found {CLAIMS}"


@pytest.mark.parametrize("path", POLICIES, ids=lambda p: p.name)
def test_every_example_policy_loads(path):
    policy = load_policy_file(path)
    assert policy.rules, f"{path.name} loaded but defines no rules"


@pytest.mark.parametrize("path", CLAIMS, ids=lambda p: p.name)
def test_every_example_claims_file_is_a_usable_claims_object(path):
    claims = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(claims, dict), f"{path.name} is not a JSON object"
    # Runs the advisory and time-note paths over real example data.
    assert "notes" in build_report(claims, [])


@pytest.mark.parametrize(
    ("claims_file", "policy_file"),
    [
        ("claims-immutable.json", "policy-immutable.json"),
        ("claims-reusable-workflow.json", "policy-reusable-workflow.json"),
    ],
)
def test_the_documented_pairs_pass_their_own_policy(claims_file, policy_file):
    # These two pairs exist to be copied into a real workflow. If a pair ever
    # stops passing, the README is teaching a policy that fails.
    rc = main(["--claims", str(EXAMPLES / claims_file), "--policy", str(EXAMPLES / policy_file)])
    assert rc == 0


def test_the_immutable_example_really_is_immutable_format():
    # The pair is the worked example for the 2026-07-15 migration, so the claims
    # must actually carry the immutable subject - otherwise it demonstrates nothing.
    claims = json.loads((EXAMPLES / "claims-immutable.json").read_text(encoding="utf-8"))
    policy = load_policy_file(EXAMPLES / "policy-immutable.json")
    notes = build_report(claims, validate(claims, policy))["notes"]
    assert any("immutable format" in n for n in notes)
