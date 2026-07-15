import base64
import json
import sys
from pathlib import Path

import pytest

# Allow `import subcheck` without an install (src layout).
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

EXAMPLES = ROOT / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def make_jwt():
    """Return a helper that builds an unsigned JWT (header.payload.sig) from claims."""

    def _seg(obj) -> str:
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    def _make(claims: dict) -> str:
        header = _seg({"alg": "RS256", "typ": "JWT"})
        return f"{header}.{_seg(claims)}.{'x' * 8}"

    return _make
