"""Assemble and format the inspection report."""

from __future__ import annotations

import json
from dataclasses import asdict

from .decoder import parse_github_sub
from .validator import FAIL, MISSING, PASS, Result


def build_report(claims: dict, results: list[Result]) -> dict:
    passed = all(r.status == PASS for r in results)
    return {
        "passed": passed,
        "summary": {
            "total": len(results),
            "pass": sum(r.status == PASS for r in results),
            "fail": sum(r.status == FAIL for r in results),
            "missing": sum(r.status == MISSING for r in results),
        },
        "notes": _advisories(claims, results),
        "results": [asdict(r) for r in results],
        "claims": claims,
    }


def _advisories(claims: dict, results: list[Result]) -> list[str]:
    """Non-gating hints, chiefly about the 2026 immutable subject-claims migration."""
    sub = claims.get("sub")
    if not isinstance(sub, str):
        return []
    parsed = parse_github_sub(sub)
    fmt = parsed.get("format")
    if fmt is None:
        return []
    sub_result = next((r for r in results if r.claim == "sub"), None)
    name_based_sub_pin = sub_result is not None and "@" not in str(sub_result.expected)
    notes: list[str] = []
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
    elif fmt == "legacy" and name_based_sub_pin:
        notes.append(
            "sub is pinned by name; when this repo adopts the immutable format (automatic for "
            "repos created, renamed, or transferred after 2026-07-15) the sub becomes "
            "'owner@id/repo@id:...' and this pattern stops matching - pin repository_id / "
            "repository_owner_id to stay durable."
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
