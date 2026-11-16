"""A `matches` or `glob` that every value satisfies must be rejected, never read as a check.

`matches: ''` has been rejected since 0.5.1, because `re.search('', s)` succeeds on every
string. It was not the only such pattern: `^`, `(?i)`, `(?x) ` and `.*` match every value
too, and so does `glob: '*'`. Each loaded, and passed a token from any repository - PASS
and rc=0 through the shipped CLI on 0.5.1. They are not exotic: `(?i)${VAR}` with the
variable left empty is `(?i)`.

Whether a pattern constrains anything is asked the way the validator asks it - with
`re.search` and `fnmatch.fnmatchcase` - of values that have nothing in common: an empty
one, one letter, a long one shaped like a real `sub` and one shaped like a workflow name,
plus each run of plain text in the pattern itself. An escape that `re` reads as the
character escaped - punctuation, a space, an underscore - is read as that character, and
any other escape or a group opener as syntax that ends a run. A pattern that rules out any
of them constrains something and is kept, so the extra values can only keep a pattern,
never reject one. They are what keeps a negative lookahead such as `^(?!refs/pull/)`, or a
deny rule on a bot such as `dependabot[bot]` with its brackets escaped, or on a workflow
named `CI Build` with its space escaped, as `re.escape()` writes it, which matches every
unrelated value and rules out the text it names.

The empty value is not tried on a claim GitHub never sends empty - `sub`, `repository`
and the other trust-boundary anchors. A pattern that rules out only that value, such as
`.+` or `glob: '?*'`, passed a token from any repository there all the same - PASS and
rc=0 on 0.5.1 - one character away from the `.*` and `*` this release rejects. On
`head_ref`, which is empty outside a pull request, the same pattern rules something out,
and is kept.

Nothing this project ships stops loading. The README's snippets and the example policies
are held by test_docs_pins.py and test_examples.py; here, the vendored fixture's subjects
written as patterns, and every condition pattern in the pinned subvectors corpus but one -
its bare `*`, which the corpus itself grades dangerous.
"""

import fnmatch
import json
import re
from pathlib import Path

import pytest

from subcheck import load_policy, validate
from subcheck.cli import main
from subcheck.validator import FAIL, PASS

FIXTURE = Path(__file__).parent / "fixtures" / "github_subjects.json"

# A token from a repository the policies below were written to keep out.
OTHER_REPO = {
    "iss": "https://token.actions.githubusercontent.com",
    "aud": "sts.amazonaws.com",
    "sub": "repo:attacker/evil:ref:refs/heads/main",
    "repository": "attacker/evil",
    "ref": "refs/heads/main",
}

# Each passed every token on 0.5.1. The first five are the ones the review found.
MATCH_EVERYTHING = [
    ("matches", "^"),
    ("matches", "(?i)"),
    ("matches", "(?x) "),
    ("matches", ".*"),
    ("glob", "*"),
    ("matches", "$"),
    ("matches", "(?s).*"),
    ("matches", "|"),
    # Unanchored, a repeat that may match nothing succeeds at position 0 of anything.
    ("matches", "[0-9]*"),
    # A deny pattern that lost its anchor: it fails at 0 and matches one character on.
    ("matches", "(?!pull_request)"),
    ("glob", "**"),
    # Anchored at both ends, it still matches every value that holds no newline - and no
    # claim value does, so no value tried may hold one either.
    ("matches", "^.*$"),
]


def _message(op, pattern, name="repository"):
    return f"claim {name!r}: {op!r} {pattern!r} matches every value, so it would constrain nothing"


@pytest.mark.parametrize(
    ("op", "pattern"),
    MATCH_EVERYTHING,
    ids=[f"{op}:{pattern!r}" for op, pattern in MATCH_EVERYTHING],
)
def test_a_pattern_that_matches_every_value_is_rejected(op, pattern):
    # Was: loaded, and "claim 'repository' satisfies ..." for a different repository.
    with pytest.raises(ValueError) as excinfo:
        load_policy({"claims": {"repository": {op: pattern}}})
    message = str(excinfo.value)
    assert _message(op, pattern) in message
    # The way out, for an author who did mean "present, with any value".
    assert "repository: {required: true}" in message


def test_it_is_rejected_beside_an_operator_that_constrains():
    # The rule as a whole still checks the glob, but the pattern beside it checks
    # nothing - the null operator's case, which 0.5.1 already rejects this way.
    with pytest.raises(ValueError, match=re.escape(_message("matches", ".*", "ref"))):
        load_policy({"claims": {"ref": {"glob": "refs/heads/*", "matches": ".*"}}})


def test_it_is_rejected_on_an_optional_rule_too():
    # Was a rule that could not fail: absent passed as optional, present matched.
    with pytest.raises(ValueError, match=re.escape(_message("glob", "*", "environment"))):
        load_policy({"claims": {"environment": {"glob": "*", "required": False}}})


# --- a claim that is never empty ---------------------------------------------

# Each rules out only the empty value, and passed every token on 0.5.1 on a claim that
# GitHub never sends empty.
MATCH_EVERY_NON_EMPTY = [
    ("matches", ".+"),
    ("matches", "."),
    ("matches", r"\S"),
    ("matches", r"[\s\S]"),
    ("glob", "?*"),
    ("glob", "*?"),
]

# The trust-boundary anchors: in every GitHub token, and never empty.
TRUST_ANCHORS = [
    "iss",
    "aud",
    "sub",
    "repository",
    "repository_owner",
    "repository_id",
    "repository_owner_id",
    "job_workflow_ref",
]


def _non_empty_message(op, pattern, name):
    return (
        f"claim {name!r}: {op!r} {pattern!r} matches every non-empty value, and {name!r} is "
        "never empty in a GitHub token, so it would constrain nothing"
    )


@pytest.mark.parametrize("name", ["repository", "sub"])
@pytest.mark.parametrize(
    ("op", "pattern"),
    MATCH_EVERY_NON_EMPTY,
    ids=[f"{op}:{pattern!r}" for op, pattern in MATCH_EVERY_NON_EMPTY],
)
def test_a_pattern_that_only_asks_for_a_value_is_rejected_on_a_never_empty_claim(name, op, pattern):
    # Was: loaded, and "claim 'repository' satisfies ..." for a different repository.
    with pytest.raises(ValueError) as excinfo:
        load_policy({"claims": {name: {op: pattern}}})
    message = str(excinfo.value)
    assert _non_empty_message(op, pattern, name) in message
    assert f"{name}: {{required: true}}" in message


def test_every_trust_anchor_is_treated_as_never_empty():
    # The set is read off the severity table; a claim moved out of it would quietly take
    # `.+` again.
    for name in TRUST_ANCHORS:
        with pytest.raises(ValueError, match=re.escape(_non_empty_message("matches", ".+", name))):
            load_policy({"claims": {name: {"matches": ".+"}}})


# --- patterns that rule something out are kept -------------------------------


@pytest.mark.parametrize(
    ("op", "pattern", "passes", "fails"),
    [
        # Each matches the empty value and still constrains: one of the others fails.
        ("matches", "^$", "", "feature-branch"),
        ("matches", "^[0-9]*$", "456789", "acme/payments-api"),
        ("matches", "^[^@]*$", "repo:acme/api:ref:refs/heads/main", "repo:acme@1/api@2:ref:x"),
        # Allowlists that a `sub` satisfies too: only a value with spaces and other
        # punctuation, shaped like a workflow name, shows that they rule something out.
        ("matches", "^[^#]*$", "refs/heads/main", "Deploy #2"),
        ("matches", r"^\S*$", "production", "Deploy to production"),
        ("matches", r"^[\w./:@%-]*$", "refs/heads/release/2.0", "Deploy #2 [prod] + docs"),
        # And these do not match it: a value has to be there - which rules something out
        # on head_ref, empty outside a pull request, though not on a never-empty claim.
        ("matches", ".+", "feature-branch", ""),
        ("glob", "?*", "feature-branch", ""),
    ],
    ids=[
        "empty-only",
        "digits-only",
        "legacy-subject-only",
        "no-hash",
        "no-whitespace",
        "allowlisted-characters",
        "non-empty",
        "glob-non-empty",
    ],
)
def test_a_pattern_that_rules_out_a_value_is_kept(op, pattern, passes, fails):
    policy = load_policy({"claims": {"head_ref": {op: pattern}}})
    assert validate({"head_ref": passes}, policy)[0].status == PASS
    assert validate({"head_ref": fails}, policy)[0].status == FAIL


@pytest.mark.parametrize(
    ("pattern", "excluded"),
    [
        ("^(?!refs/pull/)", "refs/pull/42/merge"),
        ("^(?!.*:pull_request$)", "repo:acme/api:pull_request"),
        ("^(?!pull_request_target$)", "pull_request_target"),
        ("(?<!:pull_request)$", "repo:acme/api:pull_request"),
        ("^(?!refs/heads/dev/|refs/heads/test/)", "refs/heads/test/x"),
        # Deny rules on `actor`, whose bot names need their brackets escaped. Each loaded on
        # 0.5.1, and was rejected while a run of plain text stopped at the backslash.
        (r"^(?!dependabot\[bot\]$)", "dependabot[bot]"),
        (r"^(?!github-actions\[bot\]$)", "github-actions[bot]"),
        (r"^(?!renovate\[bot\]$|dependabot\[bot\]$)", "renovate[bot]"),
        (r"^(?!.*\[bot\]$)", "dependabot[bot]"),
        (r"(?<!\[bot\])$", "github-actions[bot]"),
        (r"^(?!.*\+)", "refs/heads/a+b"),
        # Text beside a letter escape or a group opener. Each loaded on 0.5.1, and was
        # rejected while its runs were read one character at a time, which stuck the escape's
        # letter or the opener's colon to the text: 'bdebug', ':refs/pull/'.
        (r"^(?!.*\bdebug\b)", "refs/heads/debug"),
        (r"(?i)^(?!.*\bwip\b)", "refs/heads/WIP"),
        (r"^(?!\Adependabot)", "dependabot/pip/requests-2.32.0"),
        (r"^(?!(?:refs/pull/))", "refs/pull/42/merge"),
        (r"^(?!(?i:dependabot\[bot\])$)", "Dependabot[bot]"),
        # An escaped space or underscore, which re reads as that character - and re.escape()
        # writes every space as `\ `. Each loaded on 0.5.1, and was rejected on 0.5.2, which
        # kept only escaped punctuation in a run: `^(?!CI\ Build$)` was tried on 'CI' and
        # 'Build', and `^(?!.*\ prod$)` on 'prod'.
        (r"^(?!CI\ Build$)", "CI Build"),
        (r"^(?!.*Deploy\ to\ prod)", "Deploy to prod"),
        (r"(?<!my\-org/my\ repo)$", "my-org/my repo"),
        (r"^(?!.*\ prod$)", "Deploy to prod"),
        (r"^(?!release\_please$)", "release_please"),
        (r"^(?!.*\_wip$)", "refs/heads/feature_wip"),
    ],
)
def test_a_negative_lookahead_is_kept(pattern, excluded):
    # It matches the empty value and every unrelated one, and rules out the text it
    # names - which is why that text is among the values tried.
    policy = load_policy({"claims": {"ref": {"matches": pattern}}})
    assert validate({"ref": "refs/heads/main"}, policy)[0].status == PASS
    assert validate({"ref": excluded}, policy)[0].status == FAIL


@pytest.mark.parametrize("op", ["glob", "matches"])
def test_every_vendored_subject_written_as_a_pattern_loads(op):
    # The fixture's subjects are the shapes real tokens carry, so a pattern pinning any
    # of them - whole, or by its leading segment - is the kind a policy is made of.
    subjects = [s["subject"] for s in json.loads(FIXTURE.read_text(encoding="utf-8"))["subjects"]]
    assert len(subjects) >= 10, "the vendored fixture changed shape"
    for subject in subjects:
        first_segment = re.escape(subject.split(":")[0])
        patterns = [subject] if op == "glob" else [f"^{re.escape(subject)}$", f"^{first_segment}:"]
        for pattern in patterns:
            load_policy({"claims": {"sub": {op: pattern}}})


def test_every_pinned_corpus_pattern_loads_but_its_dangerous_wildcard():
    # Every trust-condition pattern in the pinned subvectors corpus - AWS StringLike and
    # StringEquals, Azure, GCP - as a glob and as the regex fnmatch makes of it.
    corpus = pytest.importorskip(
        "subvectors.corpus", reason='pinned corpus is a dev extra - pip install -e ".[dev]"'
    )

    def patterns(condition):
        # A condition nests: {"consumer": "aws-all", "of": [...]}, and a pattern may be
        # a list of values, as an IAM condition's value list is.
        if isinstance(condition, list):
            for item in condition:
                yield from patterns(item)
        elif isinstance(condition, dict):
            value = condition.get("pattern")
            if isinstance(value, list):
                yield from value
            elif value is not None:
                yield value
            for key, item in condition.items():
                if key != "pattern":
                    yield from patterns(item)

    rejected, checked = set(), 0
    for name in corpus.suite_names():
        for vector in corpus.load_suite(name)["vectors"]:
            grade = (vector.get("judgment") or {}).get("grade")
            for pattern in patterns(vector.get("condition")):
                for op, value in (("glob", pattern), ("matches", fnmatch.translate(pattern))):
                    checked += 1
                    try:
                        load_policy({"claims": {"sub": {op: value}}})
                    except ValueError:
                        rejected.add((vector["id"], grade, op, pattern))
    assert checked > 300, f"the pinned corpus changed shape: {checked} patterns"
    assert rejected == {
        ("bitbucket-aws-aud-only-workspace-wide", "dangerous", "glob", "*"),
        ("bitbucket-aws-aud-only-workspace-wide", "dangerous", "matches", "*"),
    }


# --- through the CLI ---------------------------------------------------------


def _run(tmp_path, policy_text, claims=None):
    # OTHER_REPO, with any claims given set over it.
    claims_file = tmp_path / "claims.json"
    claims_file.write_text(json.dumps({**OTHER_REPO, **(claims or {})}), encoding="utf-8")
    policy = tmp_path / "policy.yaml"
    policy.write_text(policy_text, encoding="utf-8")
    return main(["--claims", str(claims_file), "--policy", str(policy)])


@pytest.mark.parametrize(
    "policy_text",
    [
        "claims:\n  repository: {matches: '^'}\n",
        "claims:\n  repository: {matches: '(?i)'}\n",
        "claims:\n  repository: {matches: '(?x) '}\n",
        "claims:\n  repository: {matches: '.*'}\n",
        "claims:\n  repository: {glob: '*'}\n",
        # Was: PASS (3 pass, 0 fail, 0 missing), rc=0 - a deploy policy whose pattern
        # came from '(?i)${REPO}' with REPO unset.
        "issuer: https://token.actions.githubusercontent.com\n"
        "audience: sts.amazonaws.com\n"
        "claims:\n  repository: {matches: '(?i)'}\n",
    ],
    ids=["caret", "flag-i", "flag-x-space", "dot-star", "glob-star", "templated-deploy-policy"],
)
def test_cli_exits_2_on_a_pattern_that_matches_every_value(tmp_path, capsys, policy_text):
    # Was: PASS and rc=0 for every one of these, against a different repository.
    assert _run(tmp_path, policy_text) == 2
    out, err = capsys.readouterr()
    assert "matches every value, so it would constrain nothing" in err
    assert out == "", "a policy that was rejected must not print a verdict"


@pytest.mark.parametrize(
    "policy_text",
    [
        "claims:\n  repository: {matches: '.+'}\n",
        "claims:\n  repository: {glob: '?*'}\n",
        "claims:\n  repository: {matches: '\\S'}\n",
        "claims:\n  sub: {matches: '.+'}\n",
        "claims:\n  sub: {glob: '?*'}\n",
    ],
    ids=["dot-plus", "glob-non-empty", "non-space", "sub-dot-plus", "sub-glob-non-empty"],
)
def test_cli_exits_2_on_a_pattern_that_matches_every_non_empty_value(tmp_path, capsys, policy_text):
    # Was: PASS (1 pass, 0 fail, 0 missing) and rc=0 for every one of these, against a
    # different repository.
    assert _run(tmp_path, policy_text) == 2
    out, err = capsys.readouterr()
    assert "is never empty in a GitHub token, so it would constrain nothing" in err
    assert out == "", "a policy that was rejected must not print a verdict"


def test_cli_control_a_pattern_with_something_in_it_still_fails_these_claims(tmp_path, capsys):
    # The claims above really are ones the policies should catch.
    assert _run(tmp_path, "claims:\n  repository: {matches: '(?i)^acme/'}\n") == 1
    assert "does not satisfy matches /(?i)^acme//" in capsys.readouterr().out


# A name a deny rule is written for, the claim it names, and another value of that claim.
# The rules are built with re.escape(), as a script that writes a policy builds them: it
# writes a space as `\ `, a hyphen as `\-` and a bracket as `\[`, and leaves `_` and `/`.
ESCAPED_NAMES = [
    ("workflow", "CI Build", "Nightly"),
    ("environment", "Deploy to prod", "staging"),
    ("workflow", "release_please", "release-please"),
    ("actor", "dependabot[bot]", "octocat"),
    ("actor", "github-actions[bot]", "octocat"),
    ("repository", "my-org/my repo", "my-org/my-repo"),
]


def _matches(claim, pattern):
    # A YAML policy, as a policy file holds one; no pattern here holds a single quote.
    return f"claims:\n  {claim}: {{matches: '{pattern}'}}\n"


@pytest.mark.parametrize(
    ("claim", "name", "other"), ESCAPED_NAMES, ids=[name for _, name, _ in ESCAPED_NAMES]
)
def test_cli_runs_a_deny_rule_built_with_re_escape(tmp_path, capsys, claim, name, other):
    # Was: rc=2 on 0.5.2 for each name with a space, "matches every value", though each
    # rule rules out the name it is built from; rc=0 and rc=1 on 0.5.1, as now.
    for shape in ("^(?!{}$)", "^(?!.*{})", "(?<!{})$"):
        policy_text = _matches(claim, shape.format(re.escape(name)))
        assert _run(tmp_path, policy_text, {claim: other}) == 0
        assert _run(tmp_path, policy_text, {claim: name}) == 1
        out, err = capsys.readouterr()
        assert err == ""
        assert f"[-] {claim}" in out


@pytest.mark.parametrize(
    ("claim", "name", "other"), ESCAPED_NAMES, ids=[name for _, name, _ in ESCAPED_NAMES]
)
def test_cli_exits_2_on_those_names_in_a_pattern_that_matches_every_value(
    tmp_path, capsys, claim, name, other
):
    # Reading `\ ` as a space lets none of these through: the deny rule without its `^`,
    # which fails where the name starts and matches one character on; the name made
    # optional; and the name beside an empty alternative.
    for shape in ("(?!{}$)", "(?:{})?", "{}|"):
        assert _run(tmp_path, _matches(claim, shape.format(re.escape(name))), {claim: other}) == 2
        out, err = capsys.readouterr()
        assert "matches every value, so it would constrain nothing" in err
        assert out == "", "a policy that was rejected must not print a verdict"
