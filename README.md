# subcheck

Decode a GitHub Actions **OIDC token's claims** and check them against an expected-claims
policy — so a workflow fails *before* an over-broad cloud trust policy lets the wrong branch,
pull request, or fork assume your role.

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
condition, or `...:sub` allowed for `repo:org/*` — so a pull request from a fork, or any branch,
can mint a token that assumes a privileged role. This tool pins down exactly which claims you
*expect* and flags the moment a token doesn't match.

It's the small, focused sibling of **[subvectors](https://github.com/Dashtid/subvectors)** — the
conformance test-vector suite that grades whether a cloud trust *condition* is well-formed,
matches, and is safe. This one works the other end: it inspects a single *token* against a policy
you write — nothing to configure, no cloud account, no network.

## Install

```bash
pip install subcheck        # once published
# or from a clone:
pip install -e ".[dev]"
```

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
    equals: github-hosted        # reject self-hosted runners
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

Claims that anchor the trust boundary (`iss`, `aud`, `sub`, `repository`, `repository_owner`)
are reported at **high** severity; contextual claims default to **medium**.

## In a workflow

```yaml
permissions:
  id-token: write
  contents: read
steps:
  - uses: actions/checkout@v4
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
