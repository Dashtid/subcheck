"""Differential drift check between subcheck and its upstream vector source.

The fixture ``tests/fixtures/github_subjects.json`` is hand-derived from the
subvectors conformance suite (github.com/Dashtid/subvectors, vectors/ under
CC0-1.0). Two things can rot silently, and this script fails loudly on both:

1. PROVENANCE - every fixture subject must still exist verbatim as a
   ``subject`` of an ``issuer: github`` vector upstream. If one disappears,
   the fixture cites a source that no longer says what we claim it says.

2. COVERAGE - every upstream GitHub subject must decode through
   ``parse_github_sub`` (a decoded result carries a ``format`` key). A subject
   that comes back raw-only means subvectors now exercises a subject grammar
   subcheck cannot parse - exactly the "refresh from upstream when subvectors
   adds subject forms" trigger the fixture's ``_source`` note promises.

Known-undecoded forms are allowlisted below rather than left to redden the
scheduled run forever: a check that is always red carries no information.
Removing an allowlist entry is part of implementing that form's decoder
(tracked in BACKLOG.md).

Usage: python scripts/check_fixture_drift.py [--subvectors PATH]
Exit 0 clean, 1 on drift, 2 on setup errors (missing checkout, bad JSON).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from subcheck.decoder import parse_github_sub  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "github_subjects.json"

# Subject grammars subvectors exercises that subcheck deliberately does not
# decode YET. Each entry must have a matching BACKLOG.md item; delete the
# entry when the decoder learns the form so coverage enforcement resumes.
KNOWN_UNDECODED_PREFIXES = (
    # Bare job_workflow_ref subjects (customized sub claim, reusable-workflow
    # pinning). BACKLOG: "Decode job_workflow_ref subjects".
    "job_workflow_ref:",
)


def upstream_github_subjects(subvectors: Path) -> set[str]:
    subjects: set[str] = set()
    vector_files = sorted(subvectors.glob("vectors/github-*.json"))
    if not vector_files:
        print(f"[-] no vectors/github-*.json under {subvectors} - wrong path?")
        raise SystemExit(2)
    for path in vector_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for vec in data.get("vectors", []):
            if vec.get("issuer") == "github" and isinstance(vec.get("subject"), str):
                subjects.add(vec["subject"])
    return subjects


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--subvectors",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "subvectors",
        help="path to a subvectors checkout (default: ../subvectors)",
    )
    args = ap.parse_args()

    if not args.subvectors.is_dir():
        print(f"[-] subvectors checkout not found at {args.subvectors}")
        return 2

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture_subjects = {s["subject"] for s in fixture["subjects"]}
    upstream = upstream_github_subjects(args.subvectors)
    print(f"[i] fixture subjects: {len(fixture_subjects)}, upstream: {len(upstream)}")

    failed = False

    orphaned = sorted(fixture_subjects - upstream)
    if orphaned:
        failed = True
        print(f"[-] PROVENANCE: {len(orphaned)} fixture subject(s) no longer exist upstream:")
        for s in orphaned:
            print(f"      {s}")
        print("    The fixture cites vectors that are gone - re-derive it from vectors/.")
    else:
        print("[+] provenance: every fixture subject still exists upstream verbatim")

    undecoded = sorted(
        s
        for s in upstream
        if "format" not in parse_github_sub(s)
        and not s.startswith(KNOWN_UNDECODED_PREFIXES)
    )
    if undecoded:
        failed = True
        print(f"[-] COVERAGE: {len(undecoded)} upstream subject(s) do not decode:")
        for s in undecoded:
            print(f"      {s}")
        print("    subvectors added a subject form parse_github_sub cannot parse.")
        print("    Either implement the form or allowlist it WITH a BACKLOG item.")
    else:
        skipped = sum(1 for s in upstream if s.startswith(KNOWN_UNDECODED_PREFIXES))
        note = f" ({skipped} known-undecoded allowlisted)" if skipped else ""
        print(f"[+] coverage: every upstream github subject decodes{note}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
