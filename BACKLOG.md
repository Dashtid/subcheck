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

**Sequencing.** subvectors is the flagship; subcheck is the finished companion. The original plan
was to keep subcheck parked until a subvectors v0.1 + article #1 launch burst — but as of
2026-08-16 that gate has partly fired on its own (subcheck is pinned at public slot #2) while both
gate conditions remain outside your control. See the DECISION in Phase 4 before doing more here.

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
- `[x]` Commit + push the above (done; tree clean and in sync).
- `[ ]` Open follow-up issues for the good-first-issue items below (`gh issue list` returns empty).

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

## Phase 3 — ship it properly (DE-GATED 2026-08-22 — decision taken, executed)

- `[x]` `release.yml` — PyPI **trusted publishing (OIDC)**, fires on a published GitHub Release
  (build job + publish job, `environment: pypi`, `id-token: write`). Version bumped **0.2.0**
  (immutable-claims support is a feature); CHANGELOG rolled; tag `v0.2.0` pushed (inert until the
  Release is created).
- `[x]` `action.yml` composite wrapper — `uses: Dashtid/subcheck@v0.2.0` (or `@main`, which works
  already: it installs from the action path, no PyPI needed). Inputs passed via `env`, never
  interpolated into `run:` (the template-injection footgun).
- `[x]` Topics: added `aws-iam`, `cicd-security`, `supply-chain-security`, `least-privilege`
  (11 total). Seeded 5 `good first issue` tickets (#2-#6: forbidden rule, SARIF, GitLab sub,
  `--fail-on`, `--claim-map`).
- `[x]` **[HUMAN — the two remaining clicks] DONE 2026-08-24.** Pending publishers added for
  BOTH `subcheck` and `subvectors` (name reserved; subvectors' release.yml exists but stays
  inert behind its vectors-packaging gate, see subvectors ROADMAP item 4). Release v0.2.0
  published, trusted-publishing run green, `pypi.org/pypi/subcheck/json` returns 200 —
  **`pip install subcheck` works.** The "featured but not installable" state is over.

## Phase 4 — launch (the gate has partly fired on its own)

- `[x]` **Set the GitHub pin** — done, and at slot **#2** (verified 2026-08-16), ahead of its gate.
- `[ ]` Record the demo GIF/asciinema (a PR failing on `sub=...:pull_request`).
- `[ ]` Coordinated burst *with subvectors*: article -> Show HN -> one subreddit -> LinkedIn.

> [x] **DECISION RESOLVED 2026-08-24 — de-gated and shipped.** v0.2.0 is live on PyPI via
> trusted publishing; both names reserved as pending publishers. The pin at slot #2 now points
> at an installable tool. Remaining Phase 4 items (demo GIF, coordinated burst with subvectors)
> are launch amplification, not gates.

## Phase 2.5 — technical-soundness pass (done this cycle)

Driven by a research fan-out (article-saturation + primary-source verification + adversarial
refutation) before any article gets published. Findings that were *facts*, fixed here:

- `[x]` **The fork claim was wrong.** A fork's `pull_request` cannot mint a token for the upstream
  repo — `id-token: write` is downgraded and `ACTIONS_ID_TOKEN_REQUEST_TOKEN` is never injected.
  README now lists the real paths. This error is endemic to the published literature; do not
  reintroduce it, and it is worth an article of its own (see below).
- `[x]` Half-immutable subjects (`@id` on one segment) reported as `malformed`, not `immutable`.
- `[x]` Migration hints suppressed for non-github.com issuers (GHES keeps mutable names).
- `[x]` Legacy hint no longer implies format follows from repo age (org/repo opt-in exists).
- `[x]` `repository_id`/`repository_owner_id` provenance corrected (since Jan 2023, pin them now).
- `[x]` `glob` vs IAM `StringLike` divergence documented (POSIX character classes).
- `[x]` `job_workflow_ref` promoted to high severity.
- `[x]` Documented *why* subcheck exists: `runner_environment`, `event_name`, `head_ref`,
  `base_ref`, `workflow_ref` are **not expressible in an AWS trust policy at all**.

Open follow-ups from the same pass:

- `[ ]` **subvectors carries the same half-immutable tolerance** — `src/subvectors/github.py:56`
  `RepoSegment.immutable` uses `owner_id is not None or repo_id is not None`. Fix in a subvectors
  session so the two grammars genuinely agree (subcheck's decoder docstring claims they do).
- `[ ]` Re-vendor the subject fixtures if subvectors adds a malformed/asymmetric subject vector.

## Correctness / quality parking lot

- `[ ]` `--fail-on <severity>` threshold gating — today any single required-but-missing medium claim
  fails the whole gate (`report.py` `passed = all(PASS)`); no way to gate on high only.
- `[ ]` Optional `exp`/`iat`/`nbf` time checks — flag an expired or not-yet-valid token.
- `[ ]` `forbidden` rule (assert a claim is NOT one of a set). *(good first issue)*
- `[ ]` SARIF output so findings land in the GitHub Security tab. *(good first issue)*
- `[ ]` GitLab CI `sub` format support. *(good first issue)*
- `[x]` **Decode `job_workflow_ref:` subjects — DONE 2026-08-25 (v0.3.0), and it turned up a
  real bug.** The drift check flagged the bare
  `job_workflow_ref:owner/repo/.github/workflows/x.yml@ref` form as undecoded (2026-08-24).
  Implementing it surfaced the worse defect next door: the DOCUMENTED combined form
  `repo:O/R:environment:prod:job_workflow_ref:...` decoded "successfully" while `environment`
  swallowed the entire tail (`prod:job_workflow_ref:...`), so a policy pinning
  `environment: prod` failed against a token whose environment really was prod. Both fixed;
  `customized` is now reported, with a report note that a customized sub invalidates
  default-format trust conditions entirely. The drift check gained a third direction
  (MIS-PARSE) because coverage alone could never have caught this — it only asks whether a
  subject parses, not whether it parses *correctly*.
- `[ ]` Decide `equals`/`in` type handling: coerce, or keep type-strict + documented (currently the
  latter).
- `[ ]` Close test-coverage holes (92% now): `glob` branch, `--token-file`, `--token -` stdin,
  `load_policy_file` suffix logic, `to_json`/summary counts, and the `rc=2` bad-policy/bad-JSON paths.
- `[ ]` Cosmetic: rephrase the `# nosec B105` comments so bandit stops emitting "Test in comment"
  warnings (prose after `# nosec` is parsed as test IDs).

## Non-goals (hold the line)

- No cloud-trust-condition *simulation* (AWS StringLike / Azure FIC exact / GCP CEL matching) — that
  collides with subvectors and risks being wrong, the exact bug class subvectors exists to grade.
- No JWT signature/issuer verification — keep the honest "misconfiguration catcher, not auth control"
  boundary explicit as the tool grows.
- No scanner / posture / reachability-graph scope creep.
