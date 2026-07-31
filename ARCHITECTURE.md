# How subcheck works

A plain-language tour, for picking the project back up after time away.

## The one-sentence version

When a GitHub Actions job authenticates to a cloud, it gets a **token**. subcheck reads that
token's claims and compares them against a **policy file you wrote**. If they don't match, it exits
non-zero and your CI step fails.

## The problem it exists for

A GitHub Actions job that needs AWS credentials gets a short-lived token. Inside it is a claim
called `sub` — a single line of text:

```
repo:acme/payments-api:ref:refs/heads/main
```

Read it as: *"this job is running on the main branch of acme/payments-api."*

On the cloud side, an admin writes a **trust condition** — a rule saying which of those strings is
acceptable. That string-versus-rule comparison **is the entire security boundary**. Write the rule
too loosely (say `repo:acme/payments-api:*`) and every branch in the repo can reach your
production credentials.

subcheck sits on the **workflow side**. It doesn't know or care what the cloud rule says. It asks
one question: *"is the token this job received the one I expected?"* Answering that early turns a
later, cryptic `AccessDenied` into a readable diff — and catches the case where your token silently
changed shape (see the immutable-claims migration in the README).

## The flow, end to end

```
  --token <jwt>            --policy policy.yaml
        |                          |
        v                          v
   decoder.py                 policy.py          "what did I get?"  vs  "what did I expect?"
   decode_claims()            load_policy_file()
        |                          |
    {claims dict}            Policy(rules=[ClaimRule, ...])
        \                          /
         \                        /
          v                      v
              validator.py  validate()
                       |
              [Result, Result, ...]      one per rule: PASS / FAIL / MISSING
                       |
                       v
              report.py  build_report()  -> adds summary counts + advisory notes
                       |
                       v
              to_text() or to_json()
                       |
                       v
              cli.py prints, returns 0 / 1 / 2
```

## The files

All under `src/subcheck/`. Roughly 400 lines total — small enough to read in one sitting.

| File | What it does |
|---|---|
| **`cli.py`** | The entry point. Parses arguments, decides where claims come from, calls everything else in order, prints, and returns the exit code. Start here. |
| **`decoder.py`** | Turns a JWT string into a claims dictionary. A JWT is three base64 chunks joined by dots; this splits it, decodes the middle one, and parses the JSON. Also holds `parse_github_sub`, which breaks a `sub` string into its parts and detects the legacy vs immutable format. |
| **`policy.py`** | Reads your YAML/JSON policy file and turns it into a list of `ClaimRule` objects. Also holds `CLAIM_SEVERITY` — the table deciding which claims are "high" severity. |
| **`validator.py`** | The comparison engine. For each rule, look up the claim and check it (`equals` / `in` / `matches` / `glob`). Produces one `Result` per rule. ~60 lines; the real logic is `_matches()`. |
| **`report.py`** | Assembles results into a report dict, adds the summary counts and the advisory `notes`, and formats it as text or JSON. |

Tests mirror this one-to-one: `tests/test_decoder.py`, `test_validator.py`, `test_cli.py`,
`test_report.py`, plus `test_decoder_vectors.py` (see below).

## Two concepts worth knowing

**Exit codes are the product.** `0` = everything matched, `1` = a claim didn't match (this is what
fails your CI step), `2` = you gave it bad input. A CI gate is just a program with a meaningful
exit code.

**Notes are advisory, not gating.** `report.py` produces `notes` — hints about the immutable-claims
migration. They never change pass/fail. They exist because a silently-changed `sub` format is the
failure mode people don't see coming.

## The subvectors connection

`tests/fixtures/github_subjects.json` holds real GitHub subject strings copied from the
[subvectors](https://github.com/Dashtid/subvectors) vector suite (CC0, so copying is free).
`test_decoder_vectors.py` runs each one through `parse_github_sub` and asserts the result matches
what subvectors says it should be.

**This is test data only.** subcheck does not import subvectors at runtime and never will — the
dependency is one-way and exists so the two projects can't silently disagree about what a subject
string means.

## What it deliberately does NOT do

These are decisions, not gaps. See `BACKLOG.md` → Non-goals.

- **It does not verify the token's signature.** It decodes and inspects. Verifying that GitHub
  really issued the token is the cloud provider's job at role-assumption time. So subcheck is a
  *misconfiguration catcher, not an authentication control* — someone who controls the workflow can
  just skip the step.
- **It does not simulate cloud trust conditions.** Your policy's `glob` is not "what AWS would do."
  Grading real cloud rules is subvectors' job. Blurring that line risks being wrong in exactly the
  way subvectors exists to catch.
- **It is not released.** No PyPI package, no git tag, no `action.yml` — on purpose. The launch is
  parked until the flagship and the companion article are ready.

## Running it

```bash
pip install -e ".[dev]"

# decode a token and just look at it
subcheck --token-file token.txt

# check it against a policy (this is the CI gate)
subcheck --claims examples/claims-pull-request.json --policy examples/policy.json
echo $?     # 1 — the sub doesn't match

# see the immutable-migration advisory
subcheck --claims examples/claims-immutable.json --policy examples/policy.json

# the full check suite (what CI runs)
pytest -q --cov=subcheck && ruff check . && python -m mypy && bandit -q -r src
```

> On this machine use `python -m mypy` — a bare `mypy` resolves to a different Python install that
> lacks the type stubs.
