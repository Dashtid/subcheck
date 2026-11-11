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
was to keep subcheck parked until a subvectors v0.1 + article #1 launch burst. **That gate is gone
— retired 2026-08-29.** Every leg of it dissolved on its own: the pin fired ahead of schedule
(public slot #2, 2026-08-16), both packages shipped to PyPI regardless (subcheck v0.2.0 and
subvectors v0.2.0, both 2026-08-24), and the article programme was **closed
2026-08-29** — article #1 was never drafted and now never will be. Nothing in this repo is gated on anything: ship a slice
when it is ready. Phase 4 below is the shipping history, not a gate.

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
- `[x]` Open follow-up issues for the good-first-issue items below. **Done — the "returns empty"
  note was stale**: issues #2-#6 (forbidden rule, SARIF, GitLab sub, `--fail-on`, `--claim-map`)
  are open and labelled, verified 2026-08-25.

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
- `[x]` `job_workflow_ref` pinning example + severity — **DONE 2026-08-25 (v0.4.0)**. Severity was
  already high; added `examples/claims-reusable-workflow.json` + `policy-reusable-workflow.json`
  (tag-pinned shared workflow; swapping the tag for a branch fails the gate) and a README section
  covering `job_workflow_ref` vs `workflow_ref` and the sub-customization interaction.

## Phase 2 — first consumer of subvectors (done this cycle)

- `[x]` Vendored subvectors' CC0 GitHub `subject` strings as decoder fixtures
  (`tests/fixtures/github_subjects.json`, cited); `tests/test_decoder_vectors.py` asserts
  `parse_github_sub` agrees with the subvectors subject grammar on all 9 (legacy, both immutable ID
  forms, case-sensitivity, nested-branch ref, tag ref, customized multi-segment sub). One-way,
  test-time, self-contained (CI-safe) — subvectors is never a runtime dependency.
- `[x]` (upstream) subcheck recorded as the corpus's first consumer in subvectors' BACKLOG
  "Consumer-adoption" item — **done 2026-08-25**, together with the decoder bug that consumption
  caught (the combined-customization subject; fixed in 0.3.0).

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
- `[ ]` Coordinated burst *with subvectors* — **article leg dropped 2026-08-29** (the article
  programme is closed; the shipped artifact is the announcement). What remains, if it is ever worth
  the evening: Show HN -> one subreddit -> LinkedIn, all pointing at `pip install subcheck` and the
  subvectors corpus. Low priority by design — an installable package and a merged upstream PR are
  the durable proof; a launch post decays in a week.

> [x] **DECISION RESOLVED 2026-08-24 — de-gated and shipped.** v0.2.0 is live on PyPI via
> trusted publishing; both names reserved as pending publishers. The pin at slot #2 now points
> at an installable tool. Remaining Phase 4 items (demo GIF, coordinated burst with subvectors)
> are launch amplification, not gates.

## Phase 2.5 — technical-soundness pass (done this cycle)

Driven by a research fan-out (article-saturation + primary-source verification + adversarial
refutation) originally run ahead of an article that was never drafted — the article programme
closed 2026-08-29. [i] The pass keeps all of its value regardless: its output was never the article,
it was the corrections below, which landed in the code and the README. Findings that were *facts*,
fixed here:

- `[x]` **The fork claim was wrong.** A fork's `pull_request` cannot mint a token for the upstream
  repo — `id-token: write` is downgraded and `ACTIONS_ID_TOKEN_REQUEST_TOKEN` is never injected.
  README now lists the real paths. This error is endemic to the third-party literature; do not
  reintroduce it. **Kept as reference material, not as an article idea (2026-08-29).** The durable
  home for a correction this sharp is the README plus an upstream PR against a tool that encodes the
  wrong model — an artifact someone can cite, not a post that scrolls away.
- `[x]` Half-immutable subjects (`@id` on one segment) reported as `malformed`, not `immutable`.
- `[x]` Migration hints suppressed for non-github.com issuers (GHES keeps mutable names).
- `[x]` Legacy hint no longer implies format follows from repo age (org/repo opt-in exists).
- `[x]` `repository_id`/`repository_owner_id` provenance corrected (since Jan 2023, pin them now).
- `[x]` `glob` vs IAM `StringLike` divergence documented (POSIX character classes).
- `[x]` `job_workflow_ref` promoted to high severity.
- `[x]` Documented *why* subcheck exists: `runner_environment`, `event_name`, `head_ref`,
  `base_ref`, `workflow_ref` are **not expressible in an AWS trust policy at all**.

Open follow-ups from the same pass:

- `[x]` **subvectors half-immutable tolerance — FIXED upstream 2026-08-18.**
  `src/subvectors/github.py:62` now reads `owner_id is not None and repo_id is not None`, so the
  two grammars agree again. Nothing left to do here.
- `[ ]` Re-vendor the subject fixtures if subvectors adds a malformed/asymmetric subject vector.
  (Still not triggered for THIS form: subvectors added no one-sided-`@id` vector; its grammar test
  covers the branch directly.) **A different form did fire it, 2026-09-02**: the 0.5.2 pin brought
  `repo:octo-org/octo-repo` - a subject with no `ref`, `environment` or event segment - and every
  one of the nine vendored subjects carried a context, so the optional-context branch had no
  fixture reaching it. Re-derived from `vectors/` (9 -> 10), and the entry pins `context` as
  **absent**, because the omission is the whole point of the vector upstream. Worth noting the
  mechanism: the drift check's COVERAGE direction asks whether upstream subjects *decode*, and this
  one always did - what caught it was reading the delta on a deliberate pin bump. Coverage of the
  corpus is not the same question as coverage of the grammar.

## Correctness / quality parking lot

- `[x]` **Policy-shape validation — DONE 2026-08-31 (v0.4.1), and it found two silent fail-opens.**
  A 22-agent audit sweep (5 lenses, each finding then adversarially verified; roughly half the raw
  findings were refuted) turned up two ways a malformed policy passed every token it was written to
  reject, both reproduced through the shipped CLI: claim rules written at the **top level** were
  dropped without a word (only `issuer`/`audience` were read, so the gate went green having checked
  the issuer alone), and **`in:` given a string** became Python substring containment, so `prod`
  satisfied `in: production` and so did the empty string. Rule *keys* had been validated since the
  start; rule *values* never were. Both now raise on the documented rc=2 path, along with a
  non-compiling `matches`, a non-string `glob`, and a quoted `required`.
  **The lesson worth keeping:** green CI, 93% coverage and a tidy backlog all held while these
  shipped, because no test had ever written a *malformed policy*. Coverage measures the lines you
  execute, not the inputs you never thought to send. A gate whose own config can silently weaken it
  is the failure this tool exists to prevent, so policy-shape tests belong next to claim tests.

- `[x]` **Claims-shape validation — DONE 2026-09-01 (v0.4.2), found by asking 0.4.1's question of
  the other input.** The tool takes two things: a policy and a set of claims. v0.4.1 hardened the
  policy and never asked the same question of the claims, and that gap *was* the bug — `--claims`
  went straight to `json.loads` while `decode_claims` had always required a JSON object, so the two
  claim-input paths disagreed about what claims are. A list-shaped claims file made `validate()`
  return **all PASS** (`rule.name not in claims` is legal on any container, so every rule read as
  absent, which is PASS when optional); the only thing preventing a green gate was an unrelated
  crash a few lines later in `build_report`. `--claims <non-object> --format json` exited **0** and
  echoed the garbage back. Everything else exited **1** on a traceback — bad input wearing the
  gate-failure exit code, the same confusion 0.4.1 fixed one input over.
  **The generalisable move:** when a fix hardens one input, check the others *for the same defect*
  before closing it out. Symmetry between inputs is cheap to check and, here, was the whole finding.

- `[x]` **Customized subjects that do not start with `repo:` - DONE 2026-09-02.** Found by the pin
  bump to subvectors 0.6.0: the corpus's `%3A` tranche carries GitHub's own documented condition
  value, `environment:production%3Aeastus:repository_owner:octo-org`, and `parse_github_sub`
  returned raw text for it. `include_claim_keys` REPLACES the subject grammar, so a subject need
  not begin with `repo:` at all - subcheck had only ever handled the two `job_workflow_ref` shapes.
  Now decoded, with the percent-encoded colon undone (GitHub encodes any `:` inside a metadata
  value, which is the only thing keeping a colon-delimited subject unambiguous). Two advisories
  came with it: the encoding trap, where pinning the environment name as the UI shows it fails
  **closed** and reads as a broken pipeline; and a customized subject that names no repository,
  which is org-wide and wildcard-free.
  **Non-goals check, so a later session does not re-litigate it:** this is subject *decoding*, the
  tool's core job, not trust-condition simulation. The advisories describe what the token's subject
  omits; they do not evaluate a condition against it.

- `[x]` **An operator key with no value was read as no constraint - DONE 2026-11-11 (v0.5.1),
  rejected on the rc=2 path.** In a rule such as `repository: {equals: }` (YAML `equals:` with
  nothing after it) the operator loaded as `null`, and `_rule_from_spec` (`src/subcheck/policy.py`,
  the `ClaimRule(...)` it returns) passed a `None` `equals`/`matches`/`glob`/`in` straight through.
  A rule whose operators are all `None` is a presence check, so the gate passed any token that
  carried the claim at all: claims naming a different repository reported
  `PASS (1 pass, 0 fail, 0 missing)` with "claim 'repository' satisfies present" and exit 0, while
  the same rule with `equals: Dashtid/subcheck` failed them and exited 1. Same class as the two
  fail-opens v0.4.1 closed: the key was accepted, and its empty value never checked. Every
  published release from 0.2.0 through 0.5.0 has it. Found in a review on 2026-09-14, reproduced
  2026-10-21, 2026-11-06 and 2026-11-11, the last time just before the fix.
  **Decision: reject it, rather than keep it as a documented presence check.** A presence check is
  still there for anyone who means one, written on purpose as `{required: true}`, and the error
  message says so. The empty values were settled by what the matcher does with them, not by how
  they look: `matches: ''` matches every value (rejected - the same fail-open), `in: []` and its
  `[]` shorthand match none (rejected - they failed every token on rc=1, a policy mistake reported
  as a finding), and `equals: ''` and `glob: ''` match only an empty value, a real rule on a claim
  like `head_ref`, so they stay valid. Asking the same question of the top-level shortcuts found
  `issuer:`/`audience:` with no value turning into the string `'None'`; rejected too.
  A review of the fix then asked it of `claims` itself, one line further down, and found the same
  fail-open: `data.get("claims") or {}` read `claims:` with no rules under it - and `[]`, `''`,
  `false`, `0` and `{}` - as "no claim rules", so a policy that set an issuer and audience checked
  those two and passed every repository's token. Rejected on rc=2 as well. The same review found
  a rule with no operator at all still a bare presence check: `repository: {}` - what a serializer
  that drops null keys makes of `{"equals": null}` - passed a different repository, and
  `{required: false}` alone could not fail. The decision above already said a presence check is
  written on purpose as `{required: true}`; now the loader enforces it, on rc=2. For consistency
  it also rejects an `in` item left as a bare `-` (or `~`): null again, asking for a JSON null, so
  alone in the list it failed every token on rc=1 - the `in: []` mistake.
  **The lesson worth keeping:** 0.4.1 validated every operator value *that was not `None`*, and
  `spec.get(op)` returns `None` for "absent" and for "present but empty" alike - so the one value
  every check skipped was the one that switched the rule off. A guard written as
  `if x is not None` has to ask what `None` means before it trusts it, and `x or default` answers
  that question for every falsy value at once, without asking. Ask it of every key the loader
  reads, not only of the one in the bug report - and ask what a rule means when none of its keys
  is there at all.
- `[x]` **Malformed policies that crashed the loader or failed every token on rc=1 - DONE
  2026-11-11 (v0.5.1).** Each of these fails closed, and each reported a broken policy on the
  "a claim did not match" code, the confusion rc=2 exists to prevent. All now exit 2 with a
  message that names what is wrong.
  - Unknown policy keys that were not all strings. Found by the same review, as a separate item.
    Both unknown-key errors sorted the keys they named, and a YAML key need not be a string:
    `repository: {1: a, b: c}`, or a top-level `1:` beside `foo:`, made `sorted()` compare an int
    with a str, so the `TypeError` exited 1 with a traceback instead of 2. Sorted with `key=str`
    now. Every published release has the rule-level form; the top-level one arrived with 0.4.1's
    unknown-top-level-key check.
  - A `matches` pattern that fails to compile with something other than `re.error`: a repeat count
    past `re`'s limit (`OverflowError`, a traceback on rc=1 in every release), or groups nested a
    few hundred deep (`RecursionError`, which has reached rc=2 since 0.4.1 only because it is a
    `RuntimeError`, without naming the claim). Found by the next review of the release.
  - A claim name that is not a non-empty string. `1:` or `~:` under `claims` loaded, and the text
    report crashed on `len()` of the name - a traceback on rc=1 - while `--format json` reported
    normally. Every published release has it. Found by the same review.
  - An `issuer` or `audience` that is not a string. The shortcuts went through `str()`, which the
    null fix above had closed for `None` only: `audience: [sts.amazonaws.com]` demanded
    `"['sts.amazonaws.com']"` and failed every token. Both now take a string and nothing else, so
    an unquoted numeric audience has to be quoted - a deliberate change, since YAML reads `0123`
    as 83 and `str()` never saw what the author wrote. Found by the same review.
- `[x]` **An empty `--policy` turned the gate into a decode - DONE 2026-11-11 (v0.5.1), rejected
  on rc=2 in the CLI and in `action.yml`.** `if not args.policy` in `cli.py` read `--policy ""`
  the way it read no `--policy` at all, so the CLI printed the claims and exited 0. `action.yml`
  passes `--policy "$SUBCHECK_POLICY"` on every run and the runner does not enforce an input's
  `required: true`, so an Action step whose `policy` input was missing, or came out of its
  expression empty, went green for a token from any repository. Every published release from
  0.2.0 through 0.5.0 has it. Found by a review of the 0.5.1 fix that asked this release's
  question of the CLI's own flags, where every other flag left empty already exited 2. The CLI
  now decodes only when `--policy` is absent, and the Action checks its input before it installs
  anything; CI runs the Action with an empty `policy` and requires the step to fail.
  **The lesson is the empty-operator item's, one layer out:** `if not x` cannot tell "absent"
  from "empty", and an entry point that reads empty as absent hands the absent behaviour - here a
  decode that always exits 0 - to whoever controls the empty value.
- `[ ]` `--fail-on <severity>` threshold gating — today any single required-but-missing medium claim
  fails the whole gate (`report.py` `passed = all(PASS)`); no way to gate on high only.
- `[x]` `exp`/`iat`/`nbf` time checks — **DONE 2026-08-25 (v0.4.0)**, as advisory NOTES, never
  failures: enforcing lifetime is the cloud provider's job at assume-time, and gating would imply
  an authentication control this tool does not provide. The value is the saved-fixture case (an
  expired `--claims` file that quietly stopped testing anything); future `nbf`, `iat` >5min ahead,
  and `exp` <= `iat` are reported the same way. `now` is injectable so the tests are clock-free.
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
- `[x]` Close test-coverage holes — **DONE 2026-08-31: 92% -> 100%, every module.** The v0.4.1 pass
  took the `glob` branch, the `equals` FAIL path and the `rc=2` bad-policy paths
  (`tests/test_policy_shape.py`); the follow-up took the rest (`tests/test_cli_inputs.py`):
  `--token-file`, `--token -` stdin, both `python -m` entry points, the unknown-policy-suffix
  branch, the JSON summary counts, malformed-JWT rejection, and the customized-sub and
  days-duration report branches. **Worth noting which ones mattered**: `--token-file` and
  `--token -` are how `action.yml` feeds the tool, so the shipped Action's only invocation path had
  been running on untested code. 100% is not the point and is not a target to defend — it just
  happens to be where the risk-driven list ran out.
- `[x]` Cosmetic: rephrase the `# nosec B105` comments — **DONE 2026-08-31**. The prose moved to
  its own line above; `# nosec B105` is now bare, so bandit stops parsing "a status constant, not
  a secret" as a list of test IDs and runs silent.

## Non-goals (hold the line)

- No cloud-trust-condition *simulation* (AWS StringLike / Azure FIC exact / GCP CEL matching) — that
  collides with subvectors and risks being wrong, the exact bug class subvectors exists to grade.
- No JWT signature/issuer verification — keep the honest "misconfiguration catcher, not auth control"
  boundary explicit as the tool grows.
- No scanner / posture / reachability-graph scope creep.
