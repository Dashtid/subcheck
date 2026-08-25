"""Assemble and format the inspection report."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone

from .decoder import parse_github_sub
from .validator import FAIL, MISSING, PASS, Result


def build_report(claims: dict, results: list[Result], now: float | None = None) -> dict:
    """Assemble the report. ``now`` (unix seconds) is injectable for tests."""
    passed = all(r.status == PASS for r in results)
    return {
        "passed": passed,
        "summary": {
            "total": len(results),
            "pass": sum(r.status == PASS for r in results),
            "fail": sum(r.status == FAIL for r in results),
            "missing": sum(r.status == MISSING for r in results),
        },
        "notes": _advisories(claims, results) + _time_notes(claims, now),
        "results": [asdict(r) for r in results],
        "claims": claims,
    }


# Beyond this much clock disagreement, an iat in the future is worth mentioning.
# GitHub's OIDC tokens are short-lived (minutes), so a few minutes of skew is
# ordinary and a large gap is not.
_SKEW_TOLERANCE_SECONDS = 300


def _as_epoch(value: object) -> int | None:
    """A JWT time claim is a NumericDate: seconds since the epoch, as a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _duration(seconds: int) -> str:
    seconds = abs(int(seconds))
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    if seconds < 172800:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _time_notes(claims: dict, now: float | None = None) -> list[str]:
    """Advisory notes on exp/nbf/iat. Deliberately NON-GATING.

    subcheck inspects a token the job already received; enforcing lifetime is the
    cloud provider's job at assume-time, so an expired token is not a policy
    failure here. It IS worth saying out loud, because the common cause is not a
    real expiry at all: running against a SAVED --claims file, where a stale
    fixture would otherwise pass forever and quietly stop testing anything.
    """
    ts = time.time() if now is None else now
    notes: list[str] = []

    exp = _as_epoch(claims.get("exp"))
    if exp is not None and ts > exp:
        notes.append(
            f"token expired at {_iso(exp)} ({_duration(ts - exp)} ago). Real GitHub OIDC "
            "tokens live for minutes, so this usually means a saved --claims/--token-file "
            "fixture rather than a live token - check the fixture is still representative."
        )

    nbf = _as_epoch(claims.get("nbf"))
    if nbf is not None and ts < nbf:
        notes.append(
            f"token is not valid until {_iso(nbf)} ({_duration(nbf - ts)} from now); "
            "the nbf claim is in the future, which points at clock skew."
        )

    iat = _as_epoch(claims.get("iat"))
    if iat is not None and iat - ts > _SKEW_TOLERANCE_SECONDS:
        notes.append(
            f"token reports being issued at {_iso(iat)}, {_duration(iat - ts)} in the future - "
            "the clock here and the issuer's disagree by more than the 5-minute tolerance."
        )
    if iat is not None and exp is not None and exp <= iat:
        notes.append(
            f"token claims to expire at or before it was issued "
            f"(iat {_iso(iat)}, exp {_iso(exp)}); these claims are not internally consistent."
        )

    return notes


GITHUB_ISSUER = "https://token.actions.githubusercontent.com"


def _advisories(claims: dict, results: list[Result]) -> list[str]:
    """Non-gating hints, chiefly about the 2026 immutable subject-claims migration.

    Immutable subject claims are a github.com-only feature, so the migration hints are
    suppressed for any other issuer (notably GitHub Enterprise Server, which keeps the
    mutable name-based format and uses an https://HOSTNAME/_services/token issuer).
    """
    sub = claims.get("sub")
    if not isinstance(sub, str):
        return []
    iss = claims.get("iss")
    if isinstance(iss, str) and iss != GITHUB_ISSUER:
        return []
    parsed = parse_github_sub(sub)
    notes: list[str] = []
    if parsed.get("customized"):
        # A customized sub is not a variant of the default format - it REPLACES
        # it. Conditions written for 'repo:ORG/REPO:...' stop matching, and a
        # repo-wide wildcard stops matching too, so this fails closed and looks
        # like a broken deployment rather than a claims change.
        notes.append(
            "sub uses a CUSTOMIZED format (job_workflow_ref is included via "
            "include_claim_keys); trust conditions written for the default "
            "'repo:ORG/REPO:...' format no longer match this token, wildcards included."
        )
    fmt = parsed.get("format")
    if fmt is None:
        return notes
    sub_result = next((r for r in results if r.claim == "sub"), None)
    name_based_sub_pin = sub_result is not None and "@" not in str(sub_result.expected)
    if fmt == "immutable":
        oid, rid = parsed.get("repository_owner_id"), parsed.get("repository_id")
        notes.append(
            f"sub uses the immutable format (repository_owner_id={oid}, repository_id={rid}); "
            "pin these numeric IDs in the cloud trust policy rather than mutable owner/repo names."
        )
        if sub_result is not None and sub_result.status == FAIL and name_based_sub_pin:
            notes.append(
                "the sub check failed while the token is immutable-format and the expected "
                "pattern looks name-based; update the expected sub, or pin repository_id / "
                "repository_owner_id instead."
            )
    elif fmt == "malformed":
        notes.append(
            "sub carries an owner/repo ID on only one segment; GitHub always emits '@id' on "
            "both or neither, so this value looks hand-edited or half-migrated."
        )
    elif fmt == "legacy" and name_based_sub_pin:
        notes.append(
            "sub is pinned by name; when this repo adopts the immutable format the sub becomes "
            "'owner@id/repo@id:...' and this pattern stops matching - pin repository_id / "
            "repository_owner_id to stay durable. Adoption is automatic for repos created, "
            "renamed, or transferred after 2026-07-15, but any repo can be switched on sooner "
            "via the org-level or repo-level immutable-subject setting, so do not infer the "
            "format from the repo's age."
        )
    return notes


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2)


_ICON = {PASS: "[+]", FAIL: "[-]", MISSING: "[!]"}


def to_text(report: dict) -> str:
    summary = report["summary"]
    verdict = "PASS" if report["passed"] else "FAIL"
    lines = [
        f"OIDC claim inspection: {verdict}  "
        f"({summary['pass']} pass, {summary['fail']} fail, {summary['missing']} missing)",
        "",
    ]
    width = max((len(r["claim"]) for r in report["results"]), default=5)
    for r in report["results"]:
        icon = _ICON.get(r["status"], "[?]")
        lines.append(
            f"  {icon} {r['claim']:<{width}}  {r['severity']:<6}  {r['message']}"
        )
    notes = report.get("notes") or []
    if notes:
        lines.append("")
        lines.append("Notes:")
        lines.extend(f"  [i] {note}" for note in notes)
    return "\n".join(lines)
