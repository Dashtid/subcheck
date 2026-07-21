# Backlog

Granular, current task list for subcheck. Complements [`README.md`](README.md) (what it is) and
[`CHANGELOG.md`](CHANGELOG.md) (what shipped).

**What subcheck is — and is not.** subcheck decodes the OIDC token a GitHub Actions job actually
received and asserts its claims against an expectation *you* write. It is the token-author's
expectation language and a fail-fast CI gate. It is **not** a cloud-trust-condition simulator and
**not** an authentication control — grading whether a trust *condition* (AWS StringLike / Azure FIC
/ GCP CEL) is well-formed, matching, and safe lives in the sibling
[subvectors](https://github.com/Dashtid/subvectors); verifying the JWT signature is the cloud
provider's job at assume-time. Keep that line sharp (see Non-goals).

**Sequencing.** subvectors is the flagship and the priority; subcheck is the finished, ship-fast
companion. Keep subcheck launch-ready and *parked* — the public launch burst rides the subvectors
v0.1 + writing article #1 release, not a solo push.

Status keys: `[ ]` todo · `[~]` in progress · `[x]` done this cycle.

## Phase 0 — correctness & honesty (done this cycle)

- `[x]` Fix the stale sibling description: subvectors is a conformance test-vector suite, not a
  "PR gate that maps claims to reachable IAM roles" (the killed `oidc-reach` scanner). Corrected in
  README tagline + Why section + CONTRIBUTING.
- `[x]` Fix the README quickstart output to match real output (7 rows, `5 pass, 1 fail, 1 missing`).
- `[x]` Document that `matches` is unanchored (`re.search`) and that `equals`/`in` are
  JSON-type-sensitive while `matches`/`glob` stringify.
- `[x]` Note the `--token <jwt>` argv-leak footgun; steer to `--token -` / `--token-file`.
- `[x]` Add a "Related tools" cross-link to subvectors (the ecosystem-link half of the family).
- `[x]` CI: add Python 3.13, add `mypy` (green), add coverage report; ship `py.typed` + add
  `types-PyYAML` to dev deps.
- `[ ]` Commit + push the above; open follow-up issues for the good-first-issue items below.

## Phase 1 — immutable subject-claims awareness (done this cycle)

The immutable `sub` format (`repo:owner@<owner_id>/repo@<repo_id>:...`) became automatic for
new/renamed/transferred repos on **2026-07-15**; name-based policies silently stop matching.

- `[x]` Immutable-aware decoder: `parse_github_sub` parses both formats, exposes
  `repository_id`/`repository_owner_id` and a `format` field. Mirrors the subvectors subject grammar.
- `[x]` Wire `parse_github_sub` into the engine — used for report **advisories** (format detection +
  migration hints), *not* a `sub.<component>` DSL. `repository`/`repository_owner`/`ref`/`environment`
  are already top-level claims, so a parsed-sub DSL would be redundant; revisit only on concrete need.
- `[x]` Migration advisories (`report["notes"]`): flag a name-based `sub` pin that will break, and
  hint when an immutable token fails a name-based pattern.
- `[x]` `repository_id`/`repository_owner_id` ranked high severity (the durable trust anchors).
- `[x]` Example pair: `examples/claims-immutable.json` + `examples/policy-immutable.json`.
- `[ ]` (optional) `job_workflow_ref` pinning example + severity — the reusable-workflow supply-chain
  anchor AWS now exposes as a first-class condition key.

## Phase 2 — first consumer of subvectors (done this cycle)

- `[x]` Vendored subvectors' CC0 GitHub `subject` strings as decoder fixtures
  (`tests/fixtures/github_subjects.json`, cited); `tests/test_decoder_vectors.py` asserts
  `parse_github_sub` agrees with the subvectors subject grammar on all 9 (legacy, both immutable ID
  forms, case-sensitivity, nested-branch ref, tag ref, customized multi-segment sub). One-way,
  test-time, self-contained (CI-safe) — subvectors is never a runtime dependency.
- `[ ]` (upstream, separate subvectors session) record subcheck as the corpus's first consumer in
  subvectors' BACKLOG "Consumer-adoption" item — the adoption datapoint its success metric tracks.

## Phase 3 — ship it properly

- `[ ]` `release.yml` with PyPI **trusted publishing (OIDC)**; cut `v0.1.0` (git tag + GitHub
  Release). Flip README "once published" to a real `pip install subcheck`.
- `[ ]` `action.yml` wrapper so adoption is `uses: Dashtid/subcheck@v1` instead of the curl+jq+pip
  snippet — the biggest adoption-friction fix for a tool pitched as a CI gate.
- `[ ]` ~20 specific GitHub Topics (`oidc`, `github-actions`, `aws-iam`, `cicd-security`,
  `supply-chain-security`, `least-privilege`, ...); seed 3-5 `good first issue` tickets.

## Phase 4 — launch (GATED: do not fire until subvectors v0.1 + article #1 are ready)

- `[ ]` Record the demo GIF/asciinema (a PR failing on `sub=...:pull_request`).
- `[ ]` Set the GitHub pin (portfolio slot #3; surfaces on dashti.se Featured Projects).
- `[ ]` Coordinated burst *with subvectors*: article -> Show HN -> one subreddit -> LinkedIn.

## Correctness / quality parking lot

- `[ ]` `--fail-on <severity>` threshold gating — today any single required-but-missing medium claim
  fails the whole gate (`report.py` `passed = all(PASS)`); no way to gate on high only.
- `[ ]` Optional `exp`/`iat`/`nbf` time checks — flag an expired or not-yet-valid token.
- `[ ]` `forbidden` rule (assert a claim is NOT one of a set). *(good first issue)*
- `[ ]` SARIF output so findings land in the GitHub Security tab. *(good first issue)*
- `[ ]` GitLab CI `sub` format support. *(good first issue)*
- `[ ]` Decide `equals`/`in` type handling: coerce, or keep type-strict + documented (currently the
  latter).
- `[ ]` Close test-coverage holes (90% now): `glob` branch, `--token-file`, `--token -` stdin,
  `load_policy_file` suffix logic, `to_json`/summary counts, and the `rc=2` bad-policy/bad-JSON paths.
- `[ ]` Cosmetic: rephrase the `# nosec B105` comments so bandit stops emitting "Test in comment"
  warnings (prose after `# nosec` is parsed as test IDs).

## Non-goals (hold the line)

- No cloud-trust-condition *simulation* (AWS StringLike / Azure FIC exact / GCP CEL matching) — that
  collides with subvectors and risks being wrong, the exact bug class subvectors exists to grade.
- No JWT signature/issuer verification — keep the honest "misconfiguration catcher, not auth control"
  boundary explicit as the tool grows.
- No scanner / posture / reachability-graph scope creep.
