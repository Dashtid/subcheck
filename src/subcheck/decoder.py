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


def parse_github_sub(sub: str) -> dict:
    """Best-effort parse of the GitHub Actions ``sub`` claim into its components.

    Examples::

        repo:acme/api:ref:refs/heads/main     -> repository, context=ref, ref
        repo:acme/api:environment:production  -> repository, context=environment, environment
        repo:acme/api:pull_request            -> repository, context=pull_request
    """
    out: dict = {"raw": sub}
    if not sub.startswith("repo:"):
        return out
    repo, _, context = sub[len("repo:"):].partition(":")
    out["repository"] = repo
    if not context:
        return out
    kind, _, value = context.partition(":")
    out["context"] = kind
    if value:
        out[kind] = value
    return out
