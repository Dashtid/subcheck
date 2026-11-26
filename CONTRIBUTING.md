# Contributing

Thanks for looking. This is a small, focused tool — decode GitHub Actions OIDC claims and
validate them against a policy. It stays deliberately small: it asserts a token against an
expectation *you* write, and deliberately does **not** simulate a cloud's trust-condition
semantics — grading whether a trust condition is well-formed, matching, and safe lives in the
sibling [subvectors](https://github.com/Dashtid/subvectors) vector suite.

## Setup

```bash
pip install -e ".[dev]"
pytest -q && ruff check . && mypy && bandit -r src
```

## Maintenance only

subcheck is finished: bug fixes still ship, and new features are not planned. A bug report, or a
fix with a test, is welcome. The feature ideas filed as issues #2-#6 (the GitLab `sub` format, a
`forbidden` rule, SARIF output, `--fail-on`, `--claim-map`) are not planned.

## Pull requests

Keep the change focused, add a test, and make sure `pytest`, `ruff check`, `mypy`, and `bandit` pass - CI runs all four.
Not sure about scope? Open an issue first — open questions are welcome.
