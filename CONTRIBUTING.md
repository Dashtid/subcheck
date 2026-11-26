# Contributing

Thanks for looking. This is a small, focused tool — decode GitHub Actions OIDC claims and
validate them against a policy. It stays deliberately small: it asserts a token against an
expectation *you* write, and deliberately does **not** simulate a cloud's trust-condition
semantics — grading whether a trust condition is well-formed, matching, and safe lives in the
sibling [subvectors](https://github.com/Dashtid/subvectors) vector suite.

## Archived

subcheck was archived on 2026-11-26: the repository is read-only, so it takes no issues or pull
requests, and 0.5.3 is the final release. The code is MIT-licensed, so a fork can take it further.
[`BACKLOG.md`](BACKLOG.md) keeps the open items: two known bugs, both fail-closed, and the feature
ideas filed as issues #2-#6, closed as not planned.

## Setup

```bash
pip install -e ".[dev]"
pytest -q && ruff check . && mypy && bandit -r src
```
