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
