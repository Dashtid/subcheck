# subcheck

[![PyPI](https://img.shields.io/pypi/v/subcheck)](https://pypi.org/project/subcheck/)
[![CI](https://github.com/Dashtid/subcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/Dashtid/subcheck/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/subcheck)](https://pypi.org/project/subcheck/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Decode a GitHub Actions **OIDC token's claims** and check them against an expected-claims
policy — so a workflow fails *before* an over-broad cloud trust policy lets the wrong branch,
workflow, or trigger assume your role.

*Named for the claim that decides everything — `sub`. A focused sibling of
[subvectors](https://github.com/Dashtid/subvectors), the conformance test-vector suite (an "answer
key") that grades whether those trust conditions are well-formed, matching, and safe.*

```text
$ subcheck --claims examples/claims-pull-request.json --policy examples/policy.json
OIDC claim inspection: FAIL  (5 pass, 1 fail, 1 missing)

  [+] iss                 high    claim 'iss' satisfies equals 'https://token.actions.githubusercontent.com'
  [+] aud                 high    claim 'aud' satisfies equals 'sts.amazonaws.com'
  [+] repository          high    claim 'repository' satisfies equals 'acme/payments-api'
  [+] repository_owner    high    claim 'repository_owner' satisfies equals 'acme'
  [-] sub                 high    claim 'sub'='repo:acme/payments-api:pull_request' does not satisfy matches /^repo:acme/payments-api:(ref:refs/heads/main|environment:production|ref:refs/tags/v[0-9].*)$/
  [!] environment         medium  claim 'environment' is required but absent
  [+] runner_environment  medium  claim 'runner_environment' satisfies equals 'github-hosted'
```

Exit code is non-zero on any finding, so the command drops straight into a CI step as a gate.

## Why

GitHub Actions can authenticate to AWS/Azure/GCP with a short-lived **OIDC token** instead of a
long-lived secret. The cloud side (e.g. an AWS IAM role's trust policy) decides *which* tokens
may assume the role by matching claims — above all `sub`
(`repo:org/repo:ref:refs/heads/main`, `...:environment:production`, `...:pull_request`, …).

The classic mistake is a trust condition that's too loose — a wildcard `sub`, a missing
condition, or `...:sub` allowed for `repo:org/*` — so a token minted by something you never
intended can assume a privileged role. This tool pins down exactly which claims you *expect* and
flags the moment a token doesn't match.

> **Who can actually mint such a token.** Not a fork's pull request: for `pull_request` runs from
> a fork GitHub downgrades `id-token: write` and never injects
> `ACTIONS_ID_TOKEN_REQUEST_TOKEN`, so a fork cannot obtain a token for the upstream repo. The
> real paths are anyone with push/branch-create access (a wildcard `sub` then covers their
> branch), `pull_request_target` or `workflow_run` jobs that check out untrusted code, and a
> compromised third-party action running inside an already-trusted job.

It's the small, focused sibling of **[subvectors](https://github.com/Dashtid/subvectors)** — the
conformance test-vector suite that grades whether a cloud trust *condition* is well-formed,
matches, and is safe. This one works the other end: it inspects a single *token* against a policy
you write — nothing to configure, no cloud account, no network.

## Install

```bash
pip install subcheck
# or from a clone:
pip install -e ".[dev]"
```

Or skip installing entirely and use the GitHub Action — see [In a workflow](#in-a-workflow).

## Usage

Decode a token (claims only):

```bash
subcheck --token "$TOKEN"      # or: --token -   (read the JWT from stdin)
```

Validate against a policy and gate on the result:

```bash
subcheck --token "$TOKEN" --policy .github/oidc-policy.yaml
echo $?     # 0 = all matched, 1 = a claim didn't match, 2 = usage/parse error
```

Inputs (choose one): `--token <jwt>` (`-` for stdin), `--token-file <path>`, or
`--claims <decoded-claims.json>`. Output: `--format text` (default) or `json`.

> Prefer `--token -` (stdin) or `--token-file` over passing the JWT as an argument — a token on the
> command line leaks into the process list and shell history.

> **Scope (and honesty):** this **decodes** the token payload for inspection — it does **not
> verify the signature**. Verifying the signature and issuer against GitHub's JWKS is the cloud
> provider's job at role-assumption time. Use this to catch misconfigured *expectations* early,
> not as an authentication control.

## Policy

YAML or JSON. `issuer`/`audience` are shortcuts for the `iss`/`aud` claims; everything else lives
under `claims`. Each claim takes one or more of `equals`, `in` (list), `matches` (regex), `glob`,
and `required` (default `true`).

```yaml
issuer: https://token.actions.githubusercontent.com
audience: sts.amazonaws.com
claims:
  repository:
    equals: acme/payments-api
  sub:
    matches: '^repo:acme/payments-api:(ref:refs/heads/main|environment:production)$'
  runner_environment:
    equals: github-hosted        # reject self-hosted runners (see note below)
  environment:
    equals: production
    required: true
```

Shorthand: a bare string means `equals`, a list means `in`:

```yaml
claims:
  repository_owner: acme
  ref: [refs/heads/main, refs/heads/release]
```

**Matching notes:** `matches` uses `re.search`, so it is *not* anchored — `matches: pull_request`
matches that substring anywhere in the value. Anchor with `^…$` when you mean the whole claim (the
examples do). `equals`/`in` compare against the value's real JSON type, so quote a number you expect
as a string; `matches`/`glob` always operate on the stringified value.

`glob` is `fnmatch`-based: case-sensitive, `*` spans any characters (including `/` and `:`), `?`
matches one. That lines up with AWS IAM `StringLike` on the properties that matter, with **one
divergence** — `fnmatch` also honours POSIX character classes, so `glob: 'repo:acme/[ap]*'` matches
here while IAM treats `[` and `]` as literals and matches nothing. Avoid character classes if the
pattern is meant to mirror a trust policy. This is an expectation language, not a cloud-semantics
simulator (see [subvectors](https://github.com/Dashtid/subvectors) for that).

Claims that anchor the trust boundary (`iss`, `aud`, `sub`, `repository`, `repository_owner`,
`repository_id`, `repository_owner_id`, and `job_workflow_ref`) are reported at **high** severity;
contextual claims default to **medium**.

**Why check claims the cloud already checks?** Because for several of them it can't.
`runner_environment` is the clearest case: "reject self-hosted runners" is **not expressible in an
AWS IAM trust policy at all** — nor are `event_name`, `head_ref`, `base_ref`, or `workflow_ref`. AWS
exposes only a fixed set of GitHub claims as condition keys, and note that `repository_owner` is not
among them (only `repository_owner_id` is), so a name-based owner pin here has no trust-policy
equivalent. Asserting those claims in the job is the only place they can be enforced.

## Immutable subject claims (2026-07-15)

GitHub is migrating the `sub` claim to an **immutable format** that embeds numeric owner/repo IDs —
`repo:acme@123456/payments-api@456789:ref:refs/heads/main`. Adoption is automatic for repositories
created, renamed, or transferred after **2026-07-15**, but any repository can be switched on sooner
through the org-level or repo-level immutable-subject setting — so you cannot infer the format from
a repo's age. A trust condition (or a `sub` pattern here) written for the legacy
`repo:owner/repo:...` names silently stops matching, and deploys break with no code change.

Immutable subject claims are **github.com only**; GitHub Enterprise Server keeps the mutable
name-based format under its own `https://HOSTNAME/_services/token` issuer, and subcheck suppresses
these migration hints for any non-github.com issuer.

subcheck decodes both formats, reports which one a token uses, and flags the mismatch. Run a
post-migration token against a name-based policy and it points straight at the cause (rows trimmed):

```text
$ subcheck --claims examples/claims-immutable.json --policy examples/policy.json
OIDC claim inspection: FAIL  (6 pass, 1 fail, 0 missing)
  ...
  [-] sub                 high    claim 'sub'='repo:acme@123456/payments-api@456789:ref:refs/heads/main' does not satisfy matches /^repo:acme/payments-api:(ref:refs/heads/main|environment:production|ref:refs/tags/v[0-9].*)$/
  ...

Notes:
  [i] sub uses the immutable format (repository_owner_id=123456, repository_id=456789); pin these numeric IDs in the cloud trust policy rather than mutable owner/repo names.
  [i] the sub check failed while the token is immutable-format and the expected pattern looks name-based; update the expected sub, or pin repository_id / repository_owner_id instead.
```

The durable fix is to pin the numeric IDs — stable across renames and transfers — as in
[`examples/policy-immutable.json`](examples/policy-immutable.json):

```yaml
claims:
  repository_owner_id: "123456"
  repository_id: "456789"
```

`repository_id` and `repository_owner_id` are **not new** — they have been separate claims in every
token since January 2023 and are present on legacy-format tokens too. You do not have to wait for
the migration to pin them; doing it now is what makes a policy survive the switch.

## Pinning the reusable workflow

`sub` says which *repository* minted the token; `job_workflow_ref` says which *workflow code* did.
For a repo whose deploys run through a shared reusable workflow, that second question is the
supply-chain one — and it is worth pinning to an immutable tag rather than a branch, because a
branch moves:

```yaml
claims:
  job_workflow_ref:
    matches: '^acme/shared-workflows/\.github/workflows/deploy\.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+$'
```

Try it with [`examples/claims-reusable-workflow.json`](examples/claims-reusable-workflow.json) and
[`examples/policy-reusable-workflow.json`](examples/policy-reusable-workflow.json); swapping the
token's `@refs/tags/v3.2.1` for `@refs/heads/main` fails the gate, which is the point.

> **`job_workflow_ref` vs `workflow_ref`.** `workflow_ref` is the *entry* workflow in your own repo;
> `job_workflow_ref` is the workflow the job actually ran, which for a reusable-workflow call is the
> shared one in another repo. Pin the latter to control what code held the token.

GitHub can also fold `job_workflow_ref` into `sub` itself via subject customization
(`include_claim_keys`). subcheck decodes both documented shapes and flags it, because a customized
`sub` **replaces** the default `repo:ORG/REPO:...` grammar rather than extending it — cloud trust
conditions written for the default format stop matching, wildcards included.

## Token lifetime notes

If the claims carry `exp`, `nbf`, or `iat`, subcheck comments on them — as **notes, never failures**.
Enforcing a token's lifetime is the cloud provider's job at assume-time, and gating on it here would
imply an authentication control this tool does not provide.

They earn their place on the common case instead: running against a **saved** `--claims` or
`--token-file` fixture. Real GitHub OIDC tokens live for minutes, so an expired one usually means the
fixture has drifted out of date and has quietly stopped testing anything:

```text
Notes:
  [i] token expired at 2027-01-15 09:12:03Z (6d ago). Real GitHub OIDC tokens live for minutes, so
      this usually means a saved --claims/--token-file fixture rather than a live token - check the
      fixture is still representative.
```

A future `nbf`, an `iat` more than five minutes ahead, and an `exp` at or before `iat` are reported
the same way.

## In a workflow

The one-line form — this repo ships an [`action.yml`](action.yml) that requests the job's OIDC
token and checks it against your policy:

```yaml
permissions:
  id-token: write
  contents: read
steps:
  - uses: actions/checkout@v7
  - name: Verify the OIDC token is scoped as expected
    uses: Dashtid/subcheck@v0.4.0        # or @main
    with:
      policy: .github/oidc-policy.yaml
      audience: sts.amazonaws.com        # default
```

Or by hand, if you'd rather see every moving part:

```yaml
permissions:
  id-token: write
  contents: read
steps:
  - uses: actions/checkout@v7
  - run: pip install subcheck
  - name: Verify the OIDC token is scoped as expected
    run: |
      TOKEN=$(curl -sH "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
        "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sts.amazonaws.com" | jq -r .value)
      echo "$TOKEN" | subcheck --token - --policy .github/oidc-policy.yaml
```

## Development

```bash
pip install -e ".[dev]"
pytest -q          # tests
ruff check .       # lint
bandit -r src      # security lint
```

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md); good first issues are labelled.

## Related tools

- **[subvectors](https://github.com/Dashtid/subvectors)** — the sibling project, working the other
  end of the same trust boundary. subcheck checks the token a job *received* against your expected
  claims; subvectors is the *cloud side* — a cited, versioned suite of conformance test vectors
  answering "does subject S satisfy trust condition C, and is C safe?" across AWS IAM, Azure FIC,
  and GCP WIF. subvectors grades the trust *rules*; subcheck asserts the *token*.

## License

MIT — see [LICENSE](LICENSE).
