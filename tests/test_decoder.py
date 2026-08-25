import pytest

from subcheck import decode_claims, parse_github_sub


def test_decode_roundtrip(make_jwt):
    claims = {"sub": "repo:acme/api:ref:refs/heads/main", "aud": "sts.amazonaws.com"}
    assert decode_claims(make_jwt(claims)) == claims


def test_decode_rejects_non_jwt():
    with pytest.raises(ValueError):
        decode_claims("not-a-jwt")


def test_decode_rejects_bad_payload():
    with pytest.raises(ValueError):
        decode_claims("aaa.@@@not-valid@@@.bbb")


def test_parse_github_sub_environment():
    parsed = parse_github_sub("repo:acme/api:environment:production")
    assert parsed["repository"] == "acme/api"
    assert parsed["context"] == "environment"
    assert parsed["environment"] == "production"


def test_parse_github_sub_pull_request():
    parsed = parse_github_sub("repo:acme/api:pull_request")
    assert parsed["repository"] == "acme/api"
    assert parsed["context"] == "pull_request"


def test_parse_github_sub_legacy_has_format():
    parsed = parse_github_sub("repo:acme/api:ref:refs/heads/main")
    assert parsed["format"] == "legacy"
    assert parsed["repository"] == "acme/api"
    assert parsed["repository_owner"] == "acme"
    assert "repository_id" not in parsed


def test_parse_github_sub_immutable():
    parsed = parse_github_sub("repo:octo-org@123456/octo-repo@456789:ref:refs/heads/main")
    assert parsed["format"] == "immutable"
    assert parsed["repository"] == "octo-org/octo-repo"  # names, IDs stripped out
    assert parsed["repository_owner"] == "octo-org"
    assert parsed["repository_owner_id"] == "123456"
    assert parsed["repository_id"] == "456789"
    assert parsed["context"] == "ref"
    assert parsed["ref"] == "refs/heads/main"


def test_parse_github_sub_non_repo_subject():
    parsed = parse_github_sub("not-a-repo-subject")
    assert parsed == {"raw": "not-a-repo-subject"}


def test_parse_github_sub_combined_customization_does_not_swallow_the_tail():
    # The documented include_claim_keys ['repo','context','job_workflow_ref'] shape.
    # Regression: the context value was read to end-of-string, so `environment`
    # decoded as "prod:job_workflow_ref:..." - a policy pinning environment=prod
    # then failed against a token whose environment really was prod.
    parsed = parse_github_sub(
        "repo:octo-org/octo-repo:environment:prod:job_workflow_ref:"
        "octo-org/octo-automation/.github/workflows/oidc.yml@refs/heads/main"
    )
    assert parsed["repository"] == "octo-org/octo-repo"
    assert parsed["context"] == "environment"
    assert parsed["environment"] == "prod"
    assert parsed["customized"] is True
    assert parsed["job_workflow_repository"] == "octo-org/octo-automation"
    assert parsed["job_workflow_path"] == ".github/workflows/oidc.yml"
    assert parsed["job_workflow_git_ref"] == "refs/heads/main"


def test_parse_github_sub_job_workflow_ref_only():
    # jwr-only customization: the sub no longer starts with 'repo:', so it
    # carries NO information about the calling repository. Reporting one would
    # be a mis-attribution - the reusable workflow usually lives elsewhere.
    parsed = parse_github_sub(
        "job_workflow_ref:octo-org/octo-automation/.github/workflows/oidc.yml@refs/heads/main"
    )
    assert parsed["customized"] is True
    assert parsed["job_workflow_repository"] == "octo-org/octo-automation"
    assert parsed["job_workflow_git_ref"] == "refs/heads/main"
    assert "repository" not in parsed
    assert "repository_owner" not in parsed
    assert "format" not in parsed


def test_parse_github_sub_job_workflow_ref_without_ref_claims_nothing_more():
    parsed = parse_github_sub("job_workflow_ref:octo-org/octo-automation/w.yml")
    assert parsed["job_workflow_ref"] == "octo-org/octo-automation/w.yml"
    assert "job_workflow_git_ref" not in parsed
    assert "job_workflow_repository" not in parsed


def test_parse_github_sub_customization_without_context():
    parsed = parse_github_sub(
        "repo:acme/api:job_workflow_ref:acme/auto/.github/workflows/w.yml@refs/tags/v1"
    )
    assert parsed["repository"] == "acme/api"
    assert parsed["format"] == "legacy"
    assert "context" not in parsed
    assert parsed["job_workflow_git_ref"] == "refs/tags/v1"


def test_parse_github_sub_default_format_is_not_flagged_customized():
    assert "customized" not in parse_github_sub("repo:acme/api:environment:production")


def test_parse_github_sub_half_immutable_is_malformed():
    # GitHub emits @id on both segments or neither; one-sided means hand-edited/half-migrated.
    only_repo = parse_github_sub("repo:acme/api@456:ref:refs/heads/main")
    assert only_repo["format"] == "malformed"
    assert only_repo["repository"] == "acme/api"
    assert only_repo["repository_id"] == "456"
    assert "repository_owner_id" not in only_repo

    only_owner = parse_github_sub("repo:acme@123/api:ref:refs/heads/main")
    assert only_owner["format"] == "malformed"
    assert only_owner["repository_owner_id"] == "123"
