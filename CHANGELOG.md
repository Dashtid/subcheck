# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

### Changed
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
