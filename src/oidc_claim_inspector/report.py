"""Assemble and format the inspection report."""

from __future__ import annotations

import json
from dataclasses import asdict

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
        "results": [asdict(r) for r in results],
        "claims": claims,
    }


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
    return "\n".join(lines)
