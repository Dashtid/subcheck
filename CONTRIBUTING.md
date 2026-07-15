# Contributing

Thanks for looking. This is a small, focused tool — decode GitHub Actions OIDC claims and
validate them against a policy. It stays deliberately small; broader "map claims to reachable
cloud roles" work lives in [subvectors](https://github.com/Dashtid/subvectors).

## Setup

```bash
pip install -e ".[dev]"
pytest -q && ruff check . && bandit -r src
```

## Good first issues

Small, self-contained additions (labelled `good first issue`):

- Support the GitLab CI OIDC token `sub` format alongside GitHub's.
- Add a `forbidden` rule (assert a claim is NOT one of a set of values).
- Add `--claim-map` to normalise provider-specific claim names before validation.
- Emit [SARIF](https://sarifweb.azurewebsites.net/) so findings show up in the GitHub Security tab.

## Pull requests

Keep the change focused, add a test, and make sure `pytest`, `ruff check`, and `bandit` pass.
Not sure about scope? Open an issue first — open questions are welcome.
