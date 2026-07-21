"""Differential test: subcheck's decoder must agree with the subvectors subject grammar.

The fixtures in ``fixtures/github_subjects.json`` are real GitHub OIDC subjects vendored
from the subvectors CC0 vector suite. This makes subcheck the first *consumer* of that
corpus and proves ``parse_github_sub`` decodes the same components subvectors defines.
"""

import json
from pathlib import Path

import pytest

from subcheck import parse_github_sub

FIXTURES = Path(__file__).parent / "fixtures" / "github_subjects.json"
_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))["subjects"]


@pytest.mark.parametrize("case", _CASES, ids=[c["subject"] for c in _CASES])
def test_parse_agrees_with_subvectors_subject_grammar(case):
    parsed = parse_github_sub(case["subject"])
    for key, expected in case.items():
        if key == "subject":
            continue
        assert parsed.get(key) == expected, f"{key}: {parsed.get(key)!r} != {expected!r}"
