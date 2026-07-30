from subcheck import build_report, load_policy, validate


def _report(claims: dict, policy_data: dict) -> dict:
    return build_report(claims, validate(claims, load_policy(policy_data)))


def test_immutable_token_notes_ids_and_migration_hint():
    claims = {"sub": "repo:acme@123456/payments-api@456789:ref:refs/heads/main"}
    # a name-based sub pattern the token no longer matches after migration
    policy = {"claims": {"sub": {"matches": r"^repo:acme/payments-api:ref:refs/heads/main$"}}}
    report = _report(claims, policy)
    assert not report["passed"]
    notes = report["notes"]
    assert any("immutable format" in n for n in notes)
    assert any("name-based" in n for n in notes)  # the migration-failure hint


def test_immutable_token_passes_with_id_pinning_but_still_notes():
    claims = {"sub": "repo:acme@123456/payments-api@456789:ref:refs/heads/main"}
    policy = {
        "claims": {
            "sub": {"matches": r"^repo:acme@123456/payments-api@456789:ref:refs/heads/main$"}
        }
    }
    report = _report(claims, policy)
    assert report["passed"]
    assert any("immutable format" in n for n in report["notes"])
    assert not any("name-based" in n for n in report["notes"])  # no failure hint on a pass


def test_legacy_name_pin_warns_about_migration():
    claims = {"sub": "repo:acme/payments-api:ref:refs/heads/main"}
    policy = {"claims": {"sub": {"matches": r"^repo:acme/payments-api:ref:refs/heads/main$"}}}
    report = _report(claims, policy)
    assert report["passed"]
    assert any("stops matching" in n for n in report["notes"])


def test_no_sub_yields_no_notes():
    report = _report({"aud": "sts.amazonaws.com"}, {"audience": "sts.amazonaws.com"})
    assert report["notes"] == []


def test_legacy_hint_mentions_opt_in_not_just_repo_age():
    claims = {"sub": "repo:acme/payments-api:ref:refs/heads/main"}
    policy = {"claims": {"sub": {"matches": r"^repo:acme/payments-api:ref:refs/heads/main$"}}}
    note = " ".join(_report(claims, policy)["notes"])
    assert "do not infer the format from the repo's age" in note


def test_ghes_issuer_suppresses_migration_hints():
    # Immutable subject claims are github.com only; GHES must not be told to migrate.
    claims = {
        "iss": "https://ghes.acme.example/_services/token",
        "sub": "repo:acme/payments-api:ref:refs/heads/main",
    }
    policy = {"claims": {"sub": {"matches": r"^repo:acme/payments-api:ref:refs/heads/main$"}}}
    assert _report(claims, policy)["notes"] == []


def test_malformed_half_immutable_sub_is_flagged():
    claims = {"sub": "repo:acme/payments-api@456789:ref:refs/heads/main"}
    policy = {"claims": {"sub": {"matches": r"^repo:.*$"}}}
    note = " ".join(_report(claims, policy)["notes"])
    assert "only one segment" in note
