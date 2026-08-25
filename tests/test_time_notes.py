"""exp/nbf/iat advisories: informative, never gating."""

from subcheck.policy import load_policy
from subcheck.report import build_report
from subcheck.validator import validate

NOW = 1_800_000_000  # fixed clock; these notes must never depend on wall time
POLICY = load_policy({"claims": {"repository": "acme/api"}})


def _report(claims: dict, now: float = NOW) -> dict:
    full = {"repository": "acme/api", **claims}
    return build_report(full, validate(full, POLICY), now=now)


def _notes(claims: dict, now: float = NOW) -> str:
    return " | ".join(_report(claims, now)["notes"])


def test_expired_token_is_flagged_but_does_not_fail_the_run():
    report = _report({"exp": NOW - 7200})
    assert "token expired" in " ".join(report["notes"])
    assert "2h ago" in " ".join(report["notes"])
    # Non-gating: lifetime is the cloud provider's job at assume-time.
    assert report["passed"] is True


def test_saved_fixture_hint_names_the_likely_cause():
    assert "--claims" in _notes({"exp": NOW - 86400})


def test_live_token_is_quiet():
    assert _notes({"exp": NOW + 600, "iat": NOW - 60, "nbf": NOW - 60}) == ""


def test_not_yet_valid_is_flagged():
    assert "not valid until" in _notes({"nbf": NOW + 600})


def test_small_iat_skew_is_tolerated_but_large_skew_is_not():
    assert _notes({"iat": NOW + 60}) == ""
    assert "in the future" in _notes({"iat": NOW + 3600})


def test_exp_before_iat_is_internally_inconsistent():
    assert "not internally consistent" in _notes({"iat": NOW, "exp": NOW - 1})


def test_non_numeric_time_claims_are_ignored():
    # A string or bool is not a NumericDate; never crash, never guess.
    assert _notes({"exp": "not-a-number", "nbf": True, "iat": None}) == ""


def test_absent_time_claims_produce_no_notes():
    assert _notes({}) == ""
