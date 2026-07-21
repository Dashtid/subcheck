# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
