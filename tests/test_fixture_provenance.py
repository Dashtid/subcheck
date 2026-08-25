"""The vendored fixture must stay derivable from the PINNED subvectors corpus.

The full differential check (including the coverage direction and the weekly
canary against subvectors main) lives in scripts/check_fixture_drift.py; this
test wires the provenance direction into every plain pytest run so a fixture
edit that orphans a subject fails locally, not a workflow later.
"""

import json
from pathlib import Path

import pytest

corpus = pytest.importorskip(
    "subvectors.corpus", reason='pinned corpus is a dev extra - pip install -e ".[dev]"'
)

FIXTURE = Path(__file__).parent / "fixtures" / "github_subjects.json"


def test_every_fixture_subject_exists_in_the_pinned_corpus() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pinned = {
        vec["subject"]
        for name in corpus.suite_names()
        for vec in corpus.load_suite(name)["vectors"]
        if vec.get("issuer") == "github"
    }
    missing = {s["subject"] for s in fixture["subjects"]} - pinned
    assert not missing, (
        f"fixture subjects absent from pinned subvectors corpus: {sorted(missing)} - "
        "either the pin was bumped without re-deriving the fixture, or the fixture "
        "gained a subject the cited source never contained"
    )
