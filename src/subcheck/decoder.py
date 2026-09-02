"""Decode a GitHub Actions OIDC JSON Web Token into its claims.

This decodes the token payload for INSPECTION only. It does NOT verify the token
signature - verifying the signature against GitHub's JWKS is the cloud provider's
job at role-assumption time. Never trust these claims as an authentication control;
use them to catch a misconfigured trust policy before it ships.
"""

from __future__ import annotations

import base64
import binascii
import json
import re


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_claims(token: str) -> dict:
    """Decode the claims (payload) of a JWT without verifying its signature."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError(
            f"not a JWT: expected 3 dot-separated segments, got {len(parts)}"
        )
    try:
        payload = _b64url_decode(parts[1])
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"could not base64url-decode the JWT payload: {exc}") from exc
    try:
        claims = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JWT payload is not valid JSON: {exc}") from exc
    if not isinstance(claims, dict):
        raise ValueError("JWT payload did not decode to a JSON object")
    return claims


# repo:OWNER[@owner_id]/REPO[@repo_id]: ... -- the immutable format appends a numeric
# owner/repo ID (mandatory for repos created, renamed, or transferred after 2026-07-15).
# Owner/repo names exclude the '/', '@', ':' delimiters. Mirrors the subvectors subject
# grammar so the two agree on what a concrete subject decodes to.
_SUB_RE = re.compile(
    r"^repo:"
    r"(?P<owner>[^/@:]+)(?:@(?P<owner_id>\d+))?"
    r"/"
    r"(?P<repo>[^/@:]+)(?:@(?P<repo_id>\d+))?"
    r"(?::(?P<context>.*))?$"
)

# GitHub's OIDC sub-CUSTOMIZATION (include_claim_keys) can append job_workflow_ref
# to the default grammar, or replace the grammar with it entirely:
#
#   repo:ORG/REPO:environment:ENV:job_workflow_ref:ORG/AUTOMATION/.github/workflows/w.yml@REF
#   job_workflow_ref:ORG/AUTOMATION/.github/workflows/w.yml@REF
#
# The appended form must be split off BEFORE the context is parsed: the context
# value is otherwise read to end-of-string and swallows the whole tail, so
# `environment` decodes as "ENV:job_workflow_ref:..." instead of "ENV".
# Source: https://docs.github.com/en/actions/reference/security/oidc
_JWR_KEY = "job_workflow_ref"
_JWR_PREFIX = f"{_JWR_KEY}:"
_JWR_SEP = f":{_JWR_KEY}:"

# GitHub OIDC claim keys that may appear in a customized subject. include_claim_keys
# can only name claims GitHub actually mints, so requiring EVERY key of a candidate
# subject to be in this set is what stops another issuer's colon-delimited subject
# (GitLab's 'project_path:group/proj:ref_type:branch:ref:main', say) from being read
# as a customized GitHub one. 'repo' is the customization spelling of the repository
# key, from GitHub's own include_claim_keys: ["repo"] example.
_GITHUB_CLAIM_KEYS = frozenset(
    {
        "actor", "actor_id", "base_ref", "enterprise", "enterprise_id", "environment",
        "event_name", "head_ref", "job_workflow_ref", "job_workflow_sha", "ref",
        "ref_protected", "ref_type", "repo", "repository", "repository_id",
        "repository_owner", "repository_owner_id", "repository_visibility", "run_attempt",
        "run_id", "run_number", "runner_environment", "sha", "workflow", "workflow_ref",
        "workflow_sha",
    }
)

# "Any `:` within the metadata values will be replaced with %3A in the subject claim."
# - GitHub Actions OIDC reference. That encoding is the only reason a colon-delimited
# subject stays unambiguous, so a value's colon is ALWAYS encoded and every literal
# colon in the subject is structural.
_ENCODED_COLON = "%3A"


def _decode_value(value: str) -> str:
    """Undo GitHub's percent-encoding of a colon inside a subject metadata value."""
    return value.replace(_ENCODED_COLON, ":").replace(_ENCODED_COLON.lower(), ":")


def _parse_customized_pairs(sub: str) -> dict | None:
    """Decode a wholly customized subject: ``key:value:key:value``.

    Returns ``None`` unless the subject splits evenly into pairs whose keys are ALL
    GitHub claim keys - the check that keeps another issuer's subject out. Values are
    percent-decoded, so the caller sees the environment name a human would recognise
    rather than the wire form.
    """
    parts = sub.split(":")
    if len(parts) < 2 or len(parts) % 2:
        return None
    keys, values = parts[0::2], parts[1::2]
    if not all(key in _GITHUB_CLAIM_KEYS for key in keys):
        return None
    if len(set(keys)) != len(keys):
        return None  # a repeated key is not a shape GitHub mints
    return {key: _decode_value(value) for key, value in zip(keys, values, strict=True)}


def _parse_job_workflow_ref(value: str) -> dict:
    """Decompose a ``job_workflow_ref`` value: ``OWNER/REPO/PATH@REF``.

    Split on the LAST ``@``: a workflow path may legally contain one, and the
    documented shape always ends with ``@REF``.

    The workflow's repository is deliberately NOT reported as ``repository`` -
    a reusable workflow usually lives in a DIFFERENT repo from the caller, so
    attributing it to the calling repository would be a mis-parse of the same
    kind this function exists to avoid.
    """
    out: dict = {_JWR_KEY: value}
    location, sep, ref = value.rpartition("@")
    if not sep:
        return out  # no @REF: not the documented shape, so claim nothing more
    out["job_workflow_git_ref"] = ref
    owner, _, rest = location.partition("/")
    repo, _, path = rest.partition("/")
    if owner and repo and path:
        out["job_workflow_repository"] = f"{owner}/{repo}"
        out["job_workflow_path"] = path
    return out


def parse_github_sub(sub: str) -> dict:
    """Best-effort parse of the GitHub Actions ``sub`` claim into its components.

    Handles both the classic name-based format and the immutable format that appends
    numeric owner/repo IDs (``repo:owner@123/repo@456:...``). ``format`` is ``"immutable"``
    only when BOTH IDs are present (the documented grammar always carries ``@ID`` on both
    segments), ``"legacy"`` when neither is, and ``"malformed"`` when exactly one is —
    a shape GitHub never mints, so it signals a hand-edited or half-migrated value.
    ``repository`` is always the ``owner/repo`` names.

    Examples::

        repo:acme/api:ref:refs/heads/main       -> repository, context=ref, ref, format=legacy
        repo:acme/api:environment:production    -> repository, context=environment, environment
        repo:acme@1/api@2:ref:refs/heads/main   -> repository, repository_id, ..., format=immutable
        repo:acme/api@2:ref:refs/heads/main     -> format=malformed (only one ID present)
        repo:acme/api:pull_request              -> repository, context=pull_request

    Customized subjects (``include_claim_keys``) set ``customized`` and decode the
    ``job_workflow_ref`` portion; the jwr-only form carries no repository at all::

        repo:acme/api:environment:prod:job_workflow_ref:acme/auto/.github/workflows/w.yml@refs/heads/main
        job_workflow_ref:acme/auto/.github/workflows/w.yml@refs/heads/main
    """
    out: dict = {"raw": sub}
    if _ENCODED_COLON in sub or _ENCODED_COLON.lower() in sub:
        out["percent_encoded"] = True

    if sub.startswith(_JWR_PREFIX):
        # jwr-only customization: the sub no longer starts with 'repo:', so it
        # says nothing about the calling repository - report only what it holds.
        out["customized"] = True
        out.update(_parse_job_workflow_ref(sub[len(_JWR_PREFIX) :]))
        return out

    head, jwr_sep, jwr_value = sub.partition(_JWR_SEP)

    m = _SUB_RE.match(head)
    if m is None:
        # Not the default grammar. A subject may still be a wholly customized one
        # that omits 'repo' altogether - GitHub's own documented example is
        # 'environment:production%3Aeastus:repository_owner:octo-org'. Decoding it
        # matters because such a subject can name an owner and an environment while
        # never naming the repository.
        pairs = _parse_customized_pairs(sub)
        if pairs is not None:
            out["customized"] = True
            out.update(pairs)
            if "repo" in pairs:
                out["repository"] = pairs["repo"]
        return out
    owner, repo = m.group("owner"), m.group("repo")
    owner_id, repo_id = m.group("owner_id"), m.group("repo_id")
    out["repository_owner"] = owner
    out["repository"] = f"{owner}/{repo}"
    if owner_id is not None:
        out["repository_owner_id"] = owner_id
    if repo_id is not None:
        out["repository_id"] = repo_id
    if owner_id and repo_id:
        out["format"] = "immutable"
    elif owner_id or repo_id:
        out["format"] = "malformed"  # GitHub always emits @ID on both segments, or neither
    else:
        out["format"] = "legacy"
    context = m.group("context")
    if context:
        kind, _, value = context.partition(":")
        out["context"] = kind
        if value:
            out[kind] = _decode_value(value)
    if jwr_sep:
        out["customized"] = True
        out.update(_parse_job_workflow_ref(jwr_value))
    return out
