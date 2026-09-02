"""The README's advertised action pin must not lag the released version.

The quickstart's `uses: Dashtid/subcheck@vX.Y.Z` is copy-paste material, so a
stale pin silently hands users an older tool. It sat at `v0.4.0` through three
releases - including the two that fixed policies and claims files passing tokens
they were written to reject - because nothing tied it to the version.
"""

import re
from pathlib import Path

import subcheck

README = Path(__file__).resolve().parent.parent / "README.md"

# `uses: Dashtid/subcheck@v1.2.3`, however much whitespace or trailing comment.
_PIN = re.compile(r"uses:\s*Dashtid/subcheck@v(\d+\.\d+\.\d+)")


def test_readme_advertises_the_current_version():
    pins = _PIN.findall(README.read_text(encoding="utf-8"))
    assert pins, "no `uses: Dashtid/subcheck@vX.Y.Z` found - did the quickstart change shape?"
    stale = sorted({p for p in pins if p != subcheck.__version__})
    assert not stale, (
        f"README pins subcheck@v{', v'.join(stale)} but this tree is "
        f"{subcheck.__version__}; bump the README with the version."
    )
