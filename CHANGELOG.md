# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project follows
[Semantic Versioning](https://semver.org/).

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
