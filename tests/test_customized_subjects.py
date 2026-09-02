"""Wholly customized subjects, and the colon GitHub percent-encodes.

`include_claim_keys` can replace the subject grammar entirely, so a subject need
not start with `repo:` at all. GitHub's own reference gives one as a condition
value to copy:

    "sub": "environment:production%3Aeastus:repository_owner:octo-org"

It names an owner and an environment and never names the repository, and it is
wildcard-free, so a condition on it looks tight and is org-wide.

The `%3A` is the other half: "Any `:` within the metadata values will be replaced
with `%3A` in the subject claim." That encoding is what keeps a colon-delimited
subject unambiguous - and it is also a trap, because an environment named
`Production:V1` reads that way everywhere in the UI while the token carries
`Production%3AV1`.
"""

import pytest

from subcheck import build_report, load_policy, parse_github_sub, validate

DOCS_EXAMPLE = "environment:production%3Aeastus:repository_owner:octo-org"
GITHUB_ISSUER = "https://token.actions.githubusercontent.com"


def _notes(sub: str) -> str:
    claims = {"iss": GITHUB_ISSUER, "sub": sub}
    policy = load_policy({"claims": {"sub": {"equals": sub}}})
    return " ".join(build_report(claims, validate(claims, policy))["notes"])


# --- decoding ----------------------------------------------------------------

def test_the_documented_customized_subject_decodes():
    parsed = parse_github_sub(DOCS_EXAMPLE)
    assert parsed["customized"] is True
    assert parsed["repository_owner"] == "octo-org"
    # Percent-decoded, so the value matches the environment name a human reads.
    assert parsed["environment"] == "production:eastus"
    # The whole point of the shape: no repository anywhere in it.
    assert "repository" not in parsed


def test_a_colon_in_a_value_is_decoded_in_the_default_grammar_too():
    parsed = parse_github_sub("repo:octo-org/octo-repo:environment:Production%3AV1")
    assert parsed["environment"] == "Production:V1"
    assert parsed["percent_encoded"] is True
    assert parsed["repository"] == "octo-org/octo-repo"


def test_a_subject_without_an_encoded_colon_is_not_flagged():
    assert "percent_encoded" not in parse_github_sub("repo:octo-org/octo-repo:ref:refs/heads/main")


@pytest.mark.parametrize(
    "sub",
    [
        # GitLab's subject splits into pairs just as neatly; 'project_path' is not a
        # GitHub claim key, which is the only thing separating the two grammars.
        "project_path:acme/api:ref_type:branch:ref:main",
        # Odd number of segments - not key/value pairs at all.
        "environment:production:repository_owner",
        # A repeated key is not a shape GitHub mints.
        "environment:a:environment:b",
        # Free text.
        "not a subject at all",
    ],
)
def test_subjects_that_must_not_be_read_as_customized(sub):
    parsed = parse_github_sub(sub)
    assert parsed == {"raw": sub}, f"decoded {sub!r} as {parsed!r}"


# --- advisories --------------------------------------------------------------

def test_percent_encoded_colon_is_reported_with_the_failure_mode():
    note = _notes("repo:octo-org/octo-repo:environment:Production%3AV1")
    assert "percent-encoded colon" in note
    assert "fails closed" in note


def test_a_customized_subject_without_a_repository_is_reported_as_org_wide():
    note = _notes(DOCS_EXAMPLE)
    assert "does not name a repository" in note
    assert "every repository in the organization" in note


def test_the_customized_note_does_not_blame_job_workflow_ref_when_absent():
    # The note used to assert job_workflow_ref was the customization, which is wrong
    # for a subject customized with any other set of claim keys.
    note = _notes(DOCS_EXAMPLE)
    assert "job_workflow_ref" not in note
    assert "include_claim_keys" in note


def test_a_customized_subject_that_does_name_a_repository_gets_no_org_wide_note():
    sub = (
        "repo:acme/payments-api:environment:production"
        ":job_workflow_ref:acme/shared/.github/workflows/deploy.yml@refs/tags/v1.2.3"
    )
    note = _notes(sub)
    assert "does not name a repository" not in note
    assert "job_workflow_ref is included" in note


def test_a_customized_subject_can_still_name_the_repository():
    # include_claim_keys sets the ORDER too, so 'repo' need not come first. When it is
    # present the repository is reported, and the org-wide note must not fire.
    sub = "environment:production:repo:octo-org/octo-repo"
    parsed = parse_github_sub(sub)
    assert parsed["customized"] is True
    assert parsed["repository"] == "octo-org/octo-repo"
    assert parsed["environment"] == "production"
    assert "does not name a repository" not in _notes(sub)
