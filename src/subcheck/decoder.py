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


def parse_github_sub(sub: str) -> dict:
    """Best-effort parse of the GitHub Actions ``sub`` claim into its components.

    Handles both the classic name-based format and the immutable format that appends
    numeric owner/repo IDs (``repo:owner@123/repo@456:...``) — mandatory for repositories
    created, renamed, or transferred after 2026-07-15. ``format`` is ``"immutable"`` when
    an ID is present, else ``"legacy"``. ``repository`` is always the ``owner/repo`` names.

    Examples::

        repo:acme/api:ref:refs/heads/main       -> repository, context=ref, ref, format=legacy
        repo:acme/api:environment:production    -> repository, context=environment, environment
        repo:acme@1/api@2:ref:refs/heads/main   -> repository, repository_id, ..., format=immutable
        repo:acme/api:pull_request              -> repository, context=pull_request
    """
    out: dict = {"raw": sub}
    m = _SUB_RE.match(sub)
    if m is None:
        return out
    owner, repo = m.group("owner"), m.group("repo")
    owner_id, repo_id = m.group("owner_id"), m.group("repo_id")
    out["repository_owner"] = owner
    out["repository"] = f"{owner}/{repo}"
    if owner_id is not None:
        out["repository_owner_id"] = owner_id
    if repo_id is not None:
        out["repository_id"] = repo_id
    out["format"] = "immutable" if (owner_id or repo_id) else "legacy"
    context = m.group("context")
    if not context:
        return out
    kind, _, value = context.partition(":")
    out["context"] = kind
    if value:
        out[kind] = value
    return out
