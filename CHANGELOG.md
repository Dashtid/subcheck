# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.1] - 2026-11-11

### Security

- **A policy operator with no value passed any token that carried the claim.** In
  `repository: {equals: }` the operator is YAML for `null`, and a null operator read exactly like an
  absent one, so the rule was left as a bare presence check and stopped checking the value it was
  written to pin. Reproduced through the CLI against claims naming a different repository:
  `PASS (1 pass, 0 fail, 0 missing)` with "claim 'repository' satisfies present" and exit 0, while
  the same rule with a value failed them, exit 1. A deploy policy that also pinned the issuer and
  audience passed the same claims just as cleanly. `in:`, `matches:` and `glob:` with no value
  behaved the same way, and so did an empty `matches: ''`, because `re.search('', s)` matches
  every string. Each is now rejected as a bad policy, exit `2`, with a message that names the
  claim and the operator and shows how to ask for a presence check on purpose
  (`claim: {required: true}`); the README's policy section says the same. Same class as the two
  fail-opens 0.4.1 closed: the key was validated and its value never was. Every published release
  from 0.2.0 through 0.5.0 has it.
- **A `claims` key with no rules under it left only the issuer and audience checked.** `claims:`
  with nothing after it - or with every rule under it commented out - is YAML for `null`, and the
  loader read `null`, `[]`, `''`, `false` and `0` alike as "no claim rules" without asking whether
  the key was there at all. A policy that also set `issuer` and `audience` therefore passed a token
  from any repository: `PASS (2 pass, 0 fail, 0 missing)`, exit 0, through `--claims` and through
  the Action's `--token -` path alike. `claims: {}` did the same. Each is now rejected as a bad
  policy, exit `2`; a policy that means to check only the issuer and audience leaves `claims` out.
  Every published release from 0.2.0 through 0.5.0 has it.
- **A rule with no operator at all was still a bare presence check.** `repository: {}` printed
  "claim 'repository' satisfies present" and exited 0 for claims naming a different repository, and
  inside a deploy policy that also pinned the issuer and audience it reported
  `PASS (3 pass, 0 fail, 0 missing)`. `{}` is also what a serializer that drops null keys makes of
  `{"equals": null}`, the very input the first entry above rejects. A presence check now has to be
  asked for, as `{required: true}`, and a rule with neither an operator nor `required: true` is
  rejected, exit `2`. Two shapes that used to load no longer do: `{}`, a presence check nothing
  documented, and `{required: false}` with no operator, a rule that could not fail. Every published
  release from 0.2.0 through 0.5.0 has it.

  Deliberately unchanged: `equals: ''` and `glob: ''` each match only an empty claim value. That
  is a real constraint - GitHub's documented example token carries `head_ref: ""` on a
  `workflow_dispatch` run - so neither is rejected, and neither reads as "no constraint".
- **An empty `--policy` turned the gate into a decode that exited 0.** The CLI read `--policy ""`
  exactly like no `--policy` at all: it printed the claims, checked nothing, and exited 0. The
  Action reached that whenever its `policy` input was empty. `action.yml` passes
  `--policy "$SUBCHECK_POLICY"` on every run, the runner does not enforce the input's
  `required: true`, and an input that is left out, or whose expression evaluates to an empty
  string, arrives as `""`. So `uses: Dashtid/subcheck@v0.5.0` with no usable policy passed a token
  from any repository. Reproduced through `python -m subcheck --token - --policy ""`, the way the
  Action runs it, with a token from a different repository: the decoded claims, and exit 0.
  Decoding now runs only when `--policy` is absent. An empty or blank path exits `2`, and the
  Action itself exits `2` on an empty `policy` input, before it installs anything or requests a
  token. Every published release from 0.2.0 through 0.5.0 has it. Five tests in
  `tests/test_cli_inputs.py`, four of which fail against 0.5.0, and CI now runs the Action with an
  empty `policy` input and requires the step to fail; 207 -> 212 tests.

### Added

- **A wholly customized `sub` now decodes**, not just the `job_workflow_ref` shapes.
  `include_claim_keys` can replace the subject grammar entirely, so a subject need not begin with
  `repo:` at all - GitHub's own reference prints one as a condition value to copy:
  `environment:production%3Aeastus:repository_owner:octo-org`. subcheck read that as raw text and
  said nothing about it. It now decodes into its claim keys, with two guards against reading some
  other issuer's subject the same way: every key must be a GitHub claim key (which is what keeps
  GitLab's `project_path:group/proj:ref_type:branch:ref:main` out, since it splits into pairs just
  as neatly), and a repeated key or an odd segment count is rejected.
- **The percent-encoded colon is decoded and explained.** GitHub replaces any `:` inside a metadata
  value with `%3A`, which is the only reason a colon-delimited subject stays unambiguous. Values now
  come back decoded, so an environment named `Production:V1` reads as itself rather than as
  `Production%3AV1`, and a new note names the failure mode: a trust condition has to pin the
  **encoded** form, because pinning the name as it appears in the GitHub UI matches nothing and
  fails **closed** - a broken deployment with no hint that the encoding is the cause.
- **A customized `sub` that names no repository is reported as org-wide.** The documented example
  above names an owner and an environment and never names the repository, so an exact, wildcard-free
  condition on it is satisfied by every repository in the organization - including ones created
  after the condition was written. This is the mirror of 0.5.0's repo-only advisory: one subject
  omits everything below the repository, the other omits the repository itself, and neither carries
  a `*` for a reviewer to catch.

- **Guards for the copy-paste material.** Two pieces of the repo are meant to be copied into a
  user's workflow, and neither was tied to anything that would notice it rotting:
  - The README's `uses: Dashtid/subcheck@vX.Y.Z` pin sat at `v0.4.0` across three releases -
    including both fail-open fixes - because nothing checked it. `tests/test_docs_pins.py` now
    asserts it equals `subcheck.__version__`.
  - Half of `examples/` had no test: the immutable pair (0.2.0) and the reusable-workflow pair
    (0.4.0) were never loaded by anything, so 0.4.1's stricter policy validation could have broken
    a shipped example silently. `tests/test_examples.py` loads **every** policy example and runs
    **every** claims example, discovered from the directory rather than listed, so a new example is
    covered the moment the file lands. It asserts its own globs are non-empty first - a
    parametrized test over an empty glob passes vacuously, which is the same shape of fail-open
    this project keeps turning up elsewhere.

  Tests only; no behaviour change. 122 -> 135 tests, coverage still 100%.

- `tests/test_policy_empty_operators.py` - 47 regression tests for the first three Security fixes
  above and the first two Fixed entries below, 40 of which fail against 0.5.0. The 7 that pass pin what must not
  change: the empty-string constraints, the explicit presence check, a policy of issuer and
  audience alone, and a control showing the same claims still fail a rule that has its value.
  `tests/test_docs_pins.py` now also loads every policy snippet in the README, because a stricter
  loader could start rejecting one with nothing to notice. 156 -> 204 tests.

### Fixed

- **`in: []` failed every token that carried the claim, on exit 1.** No value is a member of an
  empty list, so the rule could never pass, and the gate reported a mistake in the policy as a
  finding - the confusion exit `2` exists to prevent. It now exits `2` as a bad policy, and so does
  its shorthand, a claim given `[]`. One policy that used to run no longer loads:
  `{in: [], required: false}`, which passed only while the claim was absent. Nothing documented
  that as a way to forbid a claim, but it worked as one. An `in` item with no value - a bare `-`,
  or `~` - is YAML for `null` and asked for a JSON null, so alone in the list it made the same
  mistake. It is now rejected the same way, in `in:` and in the shorthand, and beside a real value
  too, where it was harmless but still a value the author meant to write.
- **`issuer:` or `audience:` with no value demanded the literal string `'None'`.** The shortcut
  went through `str()`, so every token failed, on exit 1. Rejected on the exit-`2` path, like the
  operators above.
- **A policy whose unknown keys were not all strings crashed instead of being rejected.** A YAML
  key need not be a string: `repository: {1: a, b: c}`, or a top-level `1:` beside a `foo:`, made
  the unknown-key error sort an int against a str, and the `TypeError` escaped as a traceback on
  exit 1 - the "a claim did not match" code - instead of the exit-`2` rejection that error exists
  to give. It now names the keys either way. Every published release has the rule-level form, and
  the top-level form since 0.4.1 started rejecting unknown top-level keys. Three tests in
  `tests/test_policy_shape.py`, all failing against 0.5.0; 204 -> 207 tests.
- **The customized-`sub` note blamed `job_workflow_ref` even when that was not the customization.**
  It was written when the only customized shapes subcheck decoded were the two `job_workflow_ref`
  ones, and it asserted that cause unconditionally. It now names what actually happened.
- **The org-wide note fired on three shapes where it was false**, one of them the most durable
  customized subject a user can mint. The gate asked only whether `repository` was absent, which is
  not the same question as whether the subject names a repository. Reproduced against the shipped
  code before the fix, all three with `iss` set to the github.com issuer:
  - `repository_id:1296269:environment:production` - a numeric id names exactly one repository and
    goes on naming it across renames and transfers. The note called it org-wide, and its remedy
    ("add `repo`") pushed the reader off the immutable identifier that the immutable-format advisory
    and the README's own migration section both tell them to prefer. The gate now accepts
    `repository_id` as naming the repository, and the remedy offers it first.
  - `repository_owner_id:12345:repository_id:1296269:environment:production` - same false fire, on
    a subject that is pinned about as tightly as the claim keys allow.
  - `job_workflow_ref:...@refs/heads/main` - the jwr-only form omits the CALLING repository by
    design; its control is the workflow file. That is the reusable-workflow pattern the README
    documents and `examples/policy-reusable-workflow.json` ships, so warning about it contradicted
    this tool's own advice. Excluded explicitly rather than by accident of the `repository` key.

  The wording was also wrong in the opposite direction for a subject with no owner at all
  (`environment:production:ref:refs/heads/main`): "every repository in the organization" is
  *narrower* than the truth, since the github.com issuer is shared and nothing in that subject
  scopes the condition to the reader's own org. It now says so.
- **The percent-encoded-colon note landed on subjects that are not GitHub's.** `%3A` is not a
  GitHub invention, and the note fires before anything has established the subject is a GitHub one.
  With no `iss` claim to screen on - the hand-written `--claims` case - a GitLab-shaped
  `project_path:acme/api:environment:prod%3Aeu` collected a lecture about `include_claim_keys`
  encoding rules that do not apply to it. The note now also requires the subject to have decoded as
  a GitHub subject (a `format`, or a recognised customization).

### Changed

- Pinned corpus bumped `subvectors==0.5.2` -> `0.6.0`, **with a re-derivation**. Measured across the
  span rather than assumed: no `issuer: github` subject was removed or changed, and three were
  added by the `%3A` tranche. Two of them earn a fixture entry and one does not:
  - `repo:octo-org/octo-repo:environment:Production-sandbox` - a new **value** of the
    `environment:` form already covered. Everything interesting about it lives in the IAM condition
    (`environment:Production*`, which IAM's non-delimiter-aware `*` widens to a name prefix), and
    the fixture holds subjects, not conditions. No entry, on the same reasoning that left
    `environment:Sandbox` out at the 0.5.2 pin.
  - `repo:octo-org/octo-repo:environment:Production%3AV1` - the grammar is not new, but this is the
    only vendored subject whose decoded value differs from its raw text, so it is the sole fixture
    guard on the percent-decoding. Included deliberately, and the fixture now carries a
    `_selection` note saying why, so a later reader does not mistake it for a stray duplicate.
  - `environment:production%3Aeastus:repository_owner:octo-org` - a new **form**, unambiguously:
    the first vendored subject that neither starts with `repo:` nor is jwr-only. It pins
    `repository` and `format` as **absent**, the way 0.5.0's entry pinned `context` absent, because
    the omission is the whole point of it upstream. It is also the subject that forced the
    customized-subject decoding under Added: the decoder could not read it at all, and the drift
    check's COVERAGE direction went red on the first CI run after the pin moved - a bump that lands
    a new grammar reddening at once rather than quietly.

  Also vendored, and overdue: `job_workflow_ref:octo-org/octo-automation/.github/workflows/oidc.yml@refs/heads/main`.
  It has been in the corpus since subvectors 0.2.0 and takes a completely different decoder branch
  from the combined form the fixture already carried, so the fixture read as though it pinned the
  `job_workflow_ref` grammar while pinning only half of it. The 0.5.0 re-derivation missed it.

  Fixture 10 -> 13 subjects, upstream 23 -> 26. All three drift directions green against the new
  pin via both paths (`--installed` and a checkout). 135 -> 156 tests.

## [0.5.0] - 2026-09-02

### Added

- **Advisory for a `sub` that identifies the repository and nothing else.** `include_claim_keys:
  ["repo"]` mints a subject of exactly `repo:ORG/REPO`, with no `ref`, `environment` or event
  segment. An IAM `StringEquals` condition on that value is an exact match holding no wildcard, and
  it still admits every branch, tag, environment and `pull_request` run of the repository -
  including a `pull_request` run on an unmerged branch. The over-permission is in what the subject
  **omits**, so a review that scans conditions for `*` finds nothing to object to. subcheck now
  notes the shape whenever it decodes one, and says what actually narrows it: adding claim keys
  back to the subject, not tightening the condition's pattern. Advisory only, like every other
  note - it never changes the verdict. Documented in the README's subject-customization section.
  Found by consuming the corpus: this is upstream's
  `gh-aws-repo-only-customized-sub-admits-everything`, which arrived with the 0.5.2 pin below.

### Changed

- Pinned corpus bumped `subvectors==0.3.0` -> `0.5.2`, **and this one did carry a re-derivation**,
  unlike the two bumps before it. Measured rather than assumed - comparing every `issuer: github`
  subject string across the span shows **none removed and none changed**, and two added:
  - `repo:octo-org/octo-repo:environment:Sandbox` (0.5.0) is a new *value* of the `environment:`
    form the fixture already covers, so it needed nothing.
  - `repo:octo-org/octo-repo` (0.5.2) is a new **form**: a subject with no `ref`, `environment` or
    event segment at all. It exercises the optional-context branch of the subject grammar, which no
    vendored subject reached before, so the fixture's own `_source` promise - "refresh from upstream
    when subvectors adds subject forms" - is what fires here. Re-derived from `vectors/` rather than
    copied: the fixture is now 10 subjects, and the new entry pins `context` as **absent**, since
    what this subject omits is the whole point of it upstream.

  All three drift directions green against the new pin (10 vendored, 23 upstream; provenance,
  coverage and mis-parse clean), 120 tests pass.

  What the releases in the span carry, since the pin now covers them: 0.4.x put the whole AWS
  tranche on committed transcripts (11 `observed` vectors, each linking the raw request and
  response) and recorded that AWS's `iam:CreateRole` guardrail validates only the FIRST value of a
  `sub` condition's value list. 0.5.0 adds the `ForAllValues:`/`ForAnyValue:` set-operator tranche
  and a `condition.qualifier` schema property. 0.5.1 corrected and commit-pinned the corpus's
  Checkov citations - worth having under the pin, because the upstream PR this project's findings
  fed into invites a maintainer to follow those links.

## [0.4.2] - 2026-09-01

### Fixed

- **A claims file that is not a JSON object was half-processed instead of rejected.**
  `decode_claims` has always required the JWT payload to decode to an object; `--claims` went
  straight to `json.loads` with no such check, so the tool's two claim-input paths disagreed about
  what "claims" means. Three consequences, all reproduced through the shipped CLI on 0.4.1:
  - **`validate()` returned *all PASS* for list-shaped claims.** `rule.name not in claims` is legal
    on any container, so every rule read as absent - MISSING for a required rule, but **PASS** for
    an optional one. An all-optional policy therefore reported a clean pass over claims holding
    nothing at all. Nothing downstream caught that on purpose: the report merely happened to crash
    a few lines later on `claims.get()`, and that accident was the only thing standing between
    `--claims '[]'` and a green gate. `validate()` and `build_report()` now reject the shape, so
    the guard does not depend on a crash that a refactor could remove.
  - **`--claims <non-object> --format json` exited 0**, echoing the input back as though it were a
    decoded token. That branch consults no policy and calls no `.items()`, so it had no crash to
    hide behind - a silent success on input that was never claims.
  - **Every other combination exited 1** - the "a claim did not match" code - with a raw
    `AttributeError` traceback. That is the same bad-input-indistinguishable-from-a-finding
    confusion 0.4.1 fixed on the policy side; it now lands on the documented rc=2 path.

  An empty object `{}` is still accepted, and a required rule still reports MISSING against it: the
  guard rejects the wrong *shape*, not an empty token.

### Added

- `tests/test_claims_shape.py` - 28 regression tests, 27 of which fail against 0.4.1. One of them
  is a parity test asserting that `--token-file` and `--claims` now return the same verdict and the
  same exit code for the same non-object payload, since that asymmetry is what caused this.
- Tests for the claim-input paths that had none: `--token-file`, `--token -` (stdin), and both
  `python -m` entry points - the three the shipped `action.yml` actually uses, so the Action's only
  invocation path had been running on untested code. Plus malformed-JWT rejection, the
  unknown-policy-suffix branch, the JSON summary counts, the structurally-invalid-policy rejections
  through the CLI, and the customized-sub and days-duration report branches.
  Coverage 95% -> **100%**, every module (still 100% after this release's guards).

### Changed

- README documents the exit codes explicitly (`0` / `1` / `2`) instead of "non-zero on any
  finding". Both 0.4.1 and 0.4.2 turn on the 1-vs-2 distinction, and someone wiring this into a CI
  gate has to know which code means "fix your config" and which means "the gate caught something".

## [0.4.1] - 2026-08-31

### Fixed

- **A malformed policy could pass every token it was written to reject.** Two silent fail-open
  paths, both found by an audit sweep and both reproduced through the shipped CLI before fixing:
  - **Claim rules written at the top level were ignored entirely.** `issuer` and `audience`
    legitimately live at the top level, so putting the rest of the rules there too is the natural
    slip - and unknown top-level keys were dropped without a word. A policy pinning `repository`
    and `sub` that way returned `PASS (1 pass, 0 fail, 0 missing)` and exit 0 against a token from
    an entirely different repository, having checked only the issuer. Unknown top-level keys are
    now rejected, matching the unknown-rule-key check that already existed one level down.
  - **`in:` given a string did substring matching.** `{"in": "production"}` - a one-item YAML list
    missing its `- ` - became Python containment, so `prod` passed, and so did the empty string.
    `in` must now be a list.
- **Rule values are validated, not just rule key names.** `matches` must be a string and must
  compile; `glob` must be a string; `required` must be a real boolean (`"false"` is a non-empty
  string, so it silently made an optional claim mandatory). Each of these previously escaped
  `validate()` as a raw `TypeError`/`re.error` traceback and exited **1** - the "a claim did not
  match" code - making a broken policy indistinguishable from a real gate failure. They now raise
  a readable error on the documented rc=2 path. `equals` is deliberately unrestricted: it compares
  against the claim's real JSON type, so a number is a legitimate rule.
- **An unparseable YAML policy exited 1 instead of 2.** `yaml.YAMLError` is not a `ValueError`
  (`json.JSONDecodeError` is), so it slipped past the CLI's bad-input handler.
- **A claim carrying two constraints reported the wrong one on failure.** `describe()` named only
  the first constraint, so a `ref` failing its regex was reported against the glob it satisfied.
  All constraints are now listed, which is also what the validator actually requires.

### Added

- CI now **executes the composite action** (`uses: ./`) against a policy pinning this repository's
  own OIDC token, in both text and JSON formats. `action.yml` is the entry point the README
  advertises and nothing had ever run it, so a break would have surfaced in a user's pipeline
  rather than here. Skipped on fork PRs, which get no token by design.
- `tests/test_policy_shape.py` - 20 regression tests; 8 of them fail against the previous release.
  Also closes three long-standing coverage holes: the `glob` matcher (which had no assertion
  anywhere despite being a documented rule), the `equals` FAIL path (every prior failure case went
  through `matches` or an absent claim), and the rc=2 bad-policy paths. Coverage 93% -> 95%, with
  `validator.py` at 100%.

### Changed

- The two `# nosec B105` comments no longer carry trailing prose, which bandit was parsing as a
  comma-separated list of test IDs and warning about on every run.

- Pinned corpus bumped `subvectors==0.2.1` -> `0.3.0`, the release carrying the first six
  `observed` vectors. **No fixture re-derivation was needed and that is a verified fact, not an
  assumption**: `git diff v0.2.1..v0.3.0 -- vectors/` changes no `"subject"` line at all — 0.3.0
  adds `observation` blocks and the schema that enforces them, so the subject grammar this
  project consumes is byte-identical. All three drift directions stay green against the new pin
  (9 vendored subjects, 21 upstream). Bumping still means re-deriving whenever a subject string
  *does* move.

## [0.4.0] - 2026-08-25

### Added

- **Token-lifetime notes** for `exp` / `nbf` / `iat`, as advisories and never failures: enforcing a
  token's lifetime is the cloud provider's job at assume-time, and gating on it here would imply an
  authentication control this tool explicitly does not provide. They pay for themselves on the
  saved-fixture case — a stale `--claims` file that expired days ago otherwise passes forever and
  has quietly stopped testing anything. A future `nbf`, an `iat` more than five minutes ahead, and
  an `exp` at or before `iat` are reported the same way. Non-numeric or absent time claims are
  ignored rather than guessed at, and `build_report(..., now=)` is injectable so tests are
  clock-free.
- **Reusable-workflow pinning example**: `examples/claims-reusable-workflow.json` +
  `examples/policy-reusable-workflow.json`, pinning `job_workflow_ref` to an immutable version tag
  (swap the tag for a branch and the gate fails, which is the point). The README section covers the
  `job_workflow_ref` vs `workflow_ref` distinction — the entry workflow in your repo versus the
  shared workflow that actually held the token — and how subject customization interacts with it.

## [0.3.0] - 2026-08-25

Sub-customization support, and the correctness fix that came with it. Both were found by
differential-testing the decoder against the [subvectors](https://github.com/Dashtid/subvectors)
conformance corpus, now pinned as a dev dependency (`subvectors==0.2.0`) so the check moves only
when the pin is bumped deliberately.

### Fixed

- **A customized `sub` mis-decoded, and it could fail a correct policy.** For the documented
  combined form `repo:ORG/REPO:environment:ENV:job_workflow_ref:...`, the context value was read
  to end-of-string, so `environment` decoded as `"ENV:job_workflow_ref:ORG/AUTO/..."` instead of
  `"ENV"` — a policy pinning `environment: prod` then failed against a token whose environment
  really was `prod`. The `job_workflow_ref` portion is now split off before the context is parsed.

### Added

- `job_workflow_ref` subject decoding, both documented shapes: appended to the default grammar,
  and the jwr-only form that replaces it. Decomposed into `job_workflow_repository`,
  `job_workflow_path` and `job_workflow_git_ref`. The workflow's repository is deliberately *not*
  reported as `repository` — a reusable workflow usually lives in a different repo than the caller,
  so attributing it to the caller would be the same class of mis-parse.
- `customized` flag plus a report note: a customized `sub` does not vary the default format, it
  **replaces** it, so trust conditions written for `repo:ORG/REPO:...` stop matching — wildcards
  included. That fails closed and reads like a broken deployment rather than a claims change.
- Differential drift check (`scripts/check_fixture_drift.py`, workflow `fixture-drift.yml`) with
  three directions — provenance, coverage, and mis-parse — run against the pinned corpus on every
  relevant change, and weekly as a canary against subvectors `main`.

## [0.2.0] - 2026-08-22

First published release (PyPI, via OIDC trusted publishing — fittingly, the same mechanism the
tool inspects). Also ships `action.yml`, so a workflow can gate with
`uses: Dashtid/subcheck@v0.2.0` instead of a curl+pip snippet.

### Added

- Immutable subject-claims support: `parse_github_sub` decodes both the legacy and the immutable
  `repo:owner@id/repo@id:...` `sub` formats, exposing owner/repo IDs and a `format` field.
- Report `notes`: advisory hints about the 2026-07-15 immutable-format migration (a name-based
  `sub` pin that will break; a hint when an immutable token fails a name-based pattern).
- `repository_id` / `repository_owner_id` ranked as high-severity (immutable) trust anchors.
- `examples/claims-immutable.json` + `examples/policy-immutable.json` (an id-pinned durable policy).

### Changed

- CI also runs on Python 3.13, type-checks with `mypy`, and reports coverage; the package now
  ships a `py.typed` marker.

### Fixed

- **Corrected a factually wrong threat description.** A fork's pull request cannot mint an OIDC
  token for the upstream repo (GitHub downgrades `id-token: write` and never injects
  `ACTIONS_ID_TOKEN_REQUEST_TOKEN` for fork `pull_request` runs). The README now names the real
  paths: push/branch-create access, `pull_request_target` / `workflow_run` with untrusted checkout,
  and compromised third-party actions in a trusted job.
- `parse_github_sub` no longer reports a subject carrying an ID on only one segment as
  `immutable`; that shape is `malformed` (GitHub emits `@id` on both segments or neither) and is
  surfaced as an advisory note.
- Migration advisories are suppressed for non-github.com issuers — immutable subject claims are a
  github.com-only feature, so GitHub Enterprise Server must not be told to migrate.
- The legacy-format advisory no longer implies the format follows from a repo's age; any repo can
  opt in early via the org-level or repo-level immutable-subject setting.
- Corrected `repository_id` / `repository_owner_id` provenance: they have existed since January
  2023 and work on legacy-format tokens, so they can be pinned today rather than after migrating.
- Documented that `glob` honours POSIX character classes while IAM `StringLike` treats `[`/`]` as
  literals, and that `repository_owner` is not an AWS condition key (only `repository_owner_id`).
- `job_workflow_ref` promoted to high severity — the only claim constraining which workflow code
  minted the token, and an AWS-accepted alternative identity-provider control to `sub`.
- README quickstart output now matches the tool's real output (7 rows, `5 pass, 1 fail, 1 missing`).
- The sibling **subvectors** is described accurately across README/CONTRIBUTING (a conformance
  test-vector suite, not a reachability PR gate).
- Documented that `matches` is unanchored (`re.search`) and that `equals`/`in` are JSON-type-sensitive.

## [0.1.0] - 2026-07-15

### Added

- Decode a GitHub Actions OIDC JWT's claims (`--token` / `--token-file` / `--claims`),
  without signature verification (inspection only).
- Expected-claims policy in YAML or JSON: `equals`, `in`, `matches`, `glob`, `required`,
  plus `issuer`/`audience` shortcuts.
- Validation with per-claim severity and `PASS` / `FAIL` / `MISSING` results.
- Text and JSON reports; non-zero exit on any finding for use as a CI gate.
- `parse_github_sub` helper for the GitHub `sub` claim.
