"""Command-line interface for oidc-claim-inspector."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .decoder import decode_claims
from .policy import load_policy_file
from .report import build_report, to_json, to_text
from .validator import validate


def _load_claims(args: argparse.Namespace) -> dict:
    if args.token:
        token = sys.stdin.read() if args.token == "-" else args.token  # noqa: S105  # nosec B105 - a JWT, not a secret to store
        return decode_claims(token)
    if args.token_file:
        return decode_claims(Path(args.token_file).read_text(encoding="utf-8"))
    if args.claims:
        return json.loads(Path(args.claims).read_text(encoding="utf-8"))
    raise ValueError("provide one of --token, --token-file, or --claims")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oidc-claim-inspector",
        description="Decode GitHub Actions OIDC token claims and validate them "
        "against an expected-claims policy.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    src = parser.add_argument_group("claims input (choose one)")
    src.add_argument("--token", help="the OIDC JWT ('-' reads from stdin)")
    src.add_argument("--token-file", help="path to a file containing the OIDC JWT")
    src.add_argument("--claims", help="path to a JSON file of already-decoded claims")
    parser.add_argument(
        "--policy", help="path to a policy file (.yaml/.yml/.json); omit to only decode"
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="output format (default: text)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        claims = _load_claims(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not args.policy:
        if args.format == "json":
            print(json.dumps(claims, indent=2))
        else:
            for key, value in claims.items():
                print(f"{key}: {value}")
        return 0

    try:
        policy = load_policy_file(args.policy)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_report(claims, validate(claims, policy))
    print(to_json(report) if args.format == "json" else to_text(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
