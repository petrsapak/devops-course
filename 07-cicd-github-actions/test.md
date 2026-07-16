# Chapter 07 — Test

15 questions. Passing: 12/15.

---

**Q1.** Why should lint run before unit tests, and unit tests before integration
tests, in a pipeline?

**Q2.** In GitHub Actions, what is the relationship between workflows, jobs, and
steps, and which of them run in parallel by default?

**Q3.** Why does nearly every job start with `uses: actions/checkout@v4`?

**Q4.** Job B consumes an image built by job A. What two things are required for
this to work reliably? (Think: ordering + how the image travels.)

**Q5.** What is the "build once, promote everywhere" principle, and name the
concrete GitHub Actions/registry mechanism this chapter used to implement it.

**Q6.** Why are secrets not available to workflows triggered by pull requests
from forks, and what would go wrong if they were?

**Q7.** What does this condition accomplish, and in which job did the chapter use it?
```yaml
if: github.event_name != 'pull_request'
```

**Q8.** Explain what each tag in this strategy is for: `sha-<commit>`, `1.2.3`
(from git tag `v1.2.3`), `latest` (default branch only).

**Q9.** What is a matrix build, and what does `fail-fast: false` change?

**Q10.** A pipeline caches pip packages with key
`pip-${{ hashFiles('requirements.txt') }}`. Why is hashing the requirements file
the right cache key design?

**Q11.** How do you implement a manual approval before production deployment in
GitHub Actions?

**Q12.** "Tests pass on my machine but fail in CI." Give three distinct likely
causes and the general principle CI is enforcing.

**Q13.** Your build job fails with `denied: permission_denied` when pushing to
ghcr.io, though login succeeded. Most likely fix?

**Q14.** Why should a *scheduled* (nightly) vulnerability scan exist even though
every build already scans the image at build time?

**Q15.** Translate concepts: for Jenkins and GitLab CI, name the equivalent of
(a) the workflow YAML file, (b) a runner, (c) `needs:` ordering.

---

<details>
<summary><b>Answer key</b></summary>

1. Fail fast, fail cheap: cheapest checks first give feedback in seconds and
   avoid wasting minutes of compute on code that can't pass; developers get the
   quickest possible loop.
2. A workflow contains jobs; jobs contain steps. **Jobs** run in parallel by
   default (unless `needs`); **steps** run sequentially within a job on the same
   filesystem.
3. Runners start as clean VMs with no code; checkout clones the repository at
   the triggering ref. Without it there's nothing to build or test.
4. (1) `needs: A` so B runs after A succeeds; (2) the image must travel through
   a registry (A pushes a uniquely tagged image, B pulls it) — jobs are separate
   VMs and share nothing implicitly.
5. Build the artifact exactly once, then deploy that same immutable artifact to
   every environment. Mechanism used: push the image tagged with the commit SHA
   to ghcr.io; staging and production both reference that exact tag/digest.
6. Anyone can open a PR from a fork; if fork PRs received secrets, a malicious
   PR could modify the workflow/tests to exfiltrate them. So GitHub withholds
   secrets from fork-triggered `pull_request` runs.
7. Skips the step on PR runs — used on the **push** step so PRs build and scan
   the image but never publish it.
8. `sha-` = traceability: exactly which commit produced the running image;
   semver = human-meaningful release version for consumers; `latest` = a
   convenience pointer for dev use that must never be the production reference.
9. One job definition expanded into N parallel runs over parameter combinations
   (versions, OSes). `fail-fast: false` lets remaining variants finish even
   after one fails — you see the *full* compatibility picture.
10. The cache is valid exactly as long as the dependency set is unchanged;
    hashing the manifest makes any dependency change automatically produce a new
    key (fresh install), while identical deps always hit the cache.
11. Define an environment (e.g., `production`) with required reviewers, and set
    `environment: production` on the deploy job — the run pauses until approval,
    and the approval is audited.
12. Undeclared dependency (tool/package installed locally but not in CI); missing
    env var/secret; reliance on uncommitted files or local state (paths, DB).
    Principle: the build must be fully reproducible from what's declared in the repo.
13. Grant the job `permissions: packages: write` (the default `GITHUB_TOKEN`
    permissions don't include package writes).
14. New CVEs are disclosed daily against *unchanged* images — an image that
    scanned clean at build time can be vulnerable a week later. Recurring scans
    catch that; build-time scans can't.
15. (a) `Jenkinsfile` / `.gitlab-ci.yml`; (b) agent (node) / runner;
    (c) stage ordering in the `stages {}` block (or `parallel`) / `stages:` +
    `needs:`.

</details>

**Scoring:** 12+ → [Chapter 08](../08-jenkins/lesson.md). Below → redo exercises
7.5 and 7.7 — the build-scan-push flow and gated deploys are the heart of the chapter.
