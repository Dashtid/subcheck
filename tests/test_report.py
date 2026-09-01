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


def test_customized_sub_warns_that_default_format_conditions_stop_matching():
    # A customized sub REPLACES the default format rather than varying it, so a
    # trust condition written for 'repo:ORG/REPO:...' stops matching entirely -
    # wildcards included. That advisory had no test.
    claims = {
        "sub": "repo:acme/payments-api:environment:production"
        ":job_workflow_ref:acme/shared/.github/workflows/deploy.yml@refs/tags/v1.2.3"
    }
    note = " ".join(_report(claims, {"claims": {"sub": {"matches": "^repo:acme/"}}})["notes"])
    assert "CUSTOMIZED" in note
    assert "wildcards included" in note


def test_repo_only_sub_warns_that_it_guards_nothing_below_the_repository():
    # 'repo:ORG/REPO' with no ref, environment or event segment - the
    # include_claim_keys: ["repo"] shape. The over-permission is in what the
    # subject OMITS, so an exact-match condition on it carries no wildcard for a
    # reviewer to spot while admitting every branch, tag and pull_request run.
    claims = {"sub": "repo:acme/payments-api"}
    policy = {"claims": {"sub": {"equals": "repo:acme/payments-api"}}}
    note = " ".join(_report(claims, policy)["notes"])
    assert "no ref, environment or event segment" in note
    assert "pull_request run on an unmerged branch" in note


def test_repo_only_warning_does_not_fire_on_a_normal_subject():
    # The note must key on an ABSENT context, not merely on a short subject: a
    # ref-pinned sub is the ordinary case and deserves no scary advisory.
    claims = {"sub": "repo:acme/payments-api:ref:refs/heads/main"}
    note = " ".join(_report(claims, {"claims": {"sub": {"matches": "^repo:acme/"}}})["notes"])
    assert "no ref, environment or event segment" not in note


def test_unparseable_sub_yields_no_format_notes():
    # A sub that is not a GitHub subject at all (another issuer's format) must
    # not produce migration advice about a format it does not have.
    claims = {"sub": "project_path:acme/api:ref_type:branch:ref:main"}
    report = _report(claims, {"claims": {"sub": {"matches": "^project_path:"}}})
    assert report["passed"]
    assert not any("immutable" in n for n in report["notes"])
