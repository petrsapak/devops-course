# Chapter 09 — Test

15 questions. Passing: 12/15.

---

**Q1.** In GitLab CI, jobs in the same stage run ______, and stages run ______.

**Q2.** What does `needs:` change about the default stage-based execution model?

**Q3.** State the artifact-vs-cache rule of thumb and classify: (a) junit
report.xml consumed by a later job, (b) `.cache/pip`, (c) the compiled release
binary, (d) node_modules.

**Q4.** What is a `services:` container in a GitLab job? Give the two canonical
examples from this chapter.

**Q5.** Why is an ephemeral per-run database preferable to a shared, long-lived
test database?

**Q6.** How do `rules:` decide whether a job runs? Include the two "laws".

**Q7.** Write the `rules:` entry for "runs on main, but only when a human clicks".

**Q8.** What do `$CI_COMMIT_SHORT_SHA`, `$CI_REGISTRY_IMAGE`, and
`$CI_MERGE_REQUEST_ID` contain?

**Q9.** What is a review app, what creates and destroys it, and what problem does
it solve for code review?

**Q10.** What is the difference between `extends:` and `include:`?

**Q11.** A pipeline's security scan step ends with `|| true`. What does this do
and why does it defeat the purpose of the step?

**Q12.** GitLab's `environment:` on a deploy job provides three operationally
useful things — name two.

**Q13.** Complete the three-way mapping table for the "manual production gate":
GitHub Actions: ______, Jenkins: ______, GitLab CI: ______.

**Q14.** An organization is air-gapped (no internet from the build network), has
strict audit requirements, and 15 years of build history in Jenkins — but new
teams complain about pipeline copy-paste. Recommend an approach in 2–3 sentences.

**Q15.** Across all three CI systems, list four *design principles* (not
features) that stayed identical.

---

<details>
<summary><b>Answer key</b></summary>

1. In parallel; sequentially.
2. It creates explicit DAG edges between jobs so a job can start as soon as its
   named dependencies finish, ignoring stage boundaries — faster pipelines than
   strict stage sequencing.
3. Artifact when correctness depends on it, cache when only speed does.
   (a) artifact, (b) cache, (c) artifact, (d) cache (rebuildable from lockfile).
4. A sidecar container started alongside the job and reachable by hostname/alias:
   `docker:dind` for image builds, `postgres:16` for integration tests.
5. Fresh state every run → deterministic, isolated, parallel-safe tests; a
   shared DB accumulates state, causing order-dependent and cross-pipeline
   flakiness (and it violates reproducibility).
6. Rules are evaluated top-down against the pipeline context; the first matching
   rule decides (`when: on_success/manual/never`, variables). No match → the job
   is excluded from the pipeline entirely.
7. ```yaml
   rules:
     - if: $CI_COMMIT_BRANCH == "main"
       when: manual
   ```
8. Short commit hash of the triggering commit; the project's container registry
   path (e.g. `registry.gitlab.com/group/project`); the merge request's ID when
   the pipeline runs in MR context (empty otherwise).
9. An ephemeral environment deployed per merge request at its own URL; created
   by a deploy job with `environment: review/$CI_COMMIT_REF_SLUG` on MR
   pipelines, destroyed by the `on_stop` job on merge/close. Reviewers interact
   with the running change instead of imagining it from the diff.
10. `extends:` reuses/overrides a (hidden) job definition within the reachable
    config; `include:` pulls in external YAML files (other repos, built-in
    templates) — cross-project reuse.
11. `|| true` forces exit code 0, so the job succeeds even when the scanner
    found blocking vulnerabilities — the gate becomes decoration. Ch 02's exit
    code contract is the entire enforcement mechanism.
12. Per-environment deployment history (what/when/who), protected environments
    (restrict who can deploy), stop actions/URL attachment (and easy re-deploy
    of older builds = rollback).
13. GHA: `environment:` with required reviewers. Jenkins: `input` step.
    GitLab: `rules: ... when: manual` (+ protected environment).
14. Keep Jenkins (air-gap and audit strengths, history) but fix the copy-paste
    with a shared library exposing a standard pipeline step, plus JCasC for
    config-as-code. Migrating CI systems isn't justified by a reuse problem the
    current system can solve.
15. Fail fast/cheapest first; build the artifact once and promote it; secrets
    injected by the platform and masked, never in code; gates enforced by exit
    codes + branch protection; ephemeral, reproducible build environments;
    manual approval only at the prod boundary. (Any four.)

</details>

**Scoring:** 12+ → [Chapter 10](../10-artifacts-releases/lesson.md). Below →
redo exercises 9.3 and 9.8 — the artifact/cache distinction and the three-way
mapping are what interviews and real migrations test.
