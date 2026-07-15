# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project follows
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-07-15

### Added
- Decode a GitHub Actions OIDC JWT's claims (`--token` / `--token-file` / `--claims`),
  without signature verification (inspection only).
- Expected-claims policy in YAML or JSON: `equals`, `in`, `matches`, `glob`, `required`,
  plus `issuer`/`audience` shortcuts.
- Validation with per-claim severity and `PASS` / `FAIL` / `MISSING` results.
- Text and JSON reports; non-zero exit on any finding for use as a CI gate.
- `parse_github_sub` helper for the GitHub `sub` claim.
