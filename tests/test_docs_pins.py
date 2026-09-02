"""The README must keep telling the truth about the tool it documents.

Two of its claims are copy-paste material, and neither was tied to anything that
would notice it rotting:

* the `uses: Dashtid/subcheck@vX.Y.Z` pin, which sat at `v0.4.0` across three
  releases - including both fail-open fixes - because nothing checked it;
* the quickstart transcript, the first thing a reader sees, which had already
  been wrong once and was corrected by hand with nothing added to stop it
  happening again. Every advisory this project adds is another chance for it to
  drift, since a new note appears in that block without anyone editing it.
"""

import io
import re
from pathlib import Path

import pytest

import subcheck
from subcheck.cli import main

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# `uses: Dashtid/subcheck@v1.2.3`, whatever the whitespace or trailing comment.
_PIN = re.compile(r"uses:\s*Dashtid/subcheck@v(\d+\.\d+\.\d+)")

# The quickstart transcript: a ```text block opening with `$ subcheck <args>`.
_TRANSCRIPT = re.compile(r"```text\n\$ subcheck ([^\n]*)\n(.*?)```", re.S)


def test_readme_advertises_the_current_version():
    pins = _PIN.findall(README.read_text(encoding="utf-8"))
    assert pins, "no `uses: Dashtid/subcheck@vX.Y.Z` found - did the quickstart change shape?"
    stale = sorted({p for p in pins if p != subcheck.__version__})
    assert not stale, (
        f"README pins subcheck@v{', v'.join(stale)} but this tree is "
        f"{subcheck.__version__}; bump the README with the version."
    )


def test_readme_quickstart_transcript_is_real_output():
    match = _TRANSCRIPT.search(README.read_text(encoding="utf-8"))
    assert match, "no `$ subcheck ...` transcript found - did the quickstart change shape?"
    argv, documented = match.group(1).split(), match.group(2)

    buf = io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(ROOT)  # the transcript uses paths relative to the repo root
        mp.setattr("sys.stdout", buf)
        rc = main(argv)

    # The documented run ends in a finding; showing a failing gate is the point of it.
    assert rc == 1, f"the quickstart is documented as FAIL but exited {rc}"

    expected = [line.rstrip() for line in documented.strip("\n").splitlines()]
    got = [line.rstrip() for line in buf.getvalue().strip("\n").splitlines()]
    assert got == expected, "README quickstart no longer matches real output"
