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
