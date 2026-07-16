# Chapter 09 — Exercises

Two paths — pick one (or both):

- **Path A (recommended, closest to real use):** free account on gitlab.com,
  push the ch 07 app there, use shared runners.
- **Path B (fully local):** validate pipelines with `gitlab-ci-local`
  (github.com/firecow/gitlab-ci-local — `npm i -g gitlab-ci-local`), which
  executes `.gitlab-ci.yml` in Docker on your machine. Some features (registry,
  environments UI) won't exist; noted per exercise.

---

## Exercise 9.1 — Port your pipeline

Rewrite your ch 07 GitHub Actions workflow as `.gitlab-ci.yml`: stages
`[test, build]`; `lint` and `test` jobs in the test stage (parallel!), junit
report artifact from pytest.

- Path A: push and watch CI/CD → Pipelines. Open the MR view later to see the
  junit report rendered.
- Path B: `gitlab-ci-local` runs the jobs locally.

**Verify:** lint and test run *in parallel* (same stage) — compare with GHA where
you'd need two jobs, and Jenkins where stages are sequential by default. Pipeline
green.

## Exercise 9.2 — rules: the decision table

Add to your pipeline a job `debug-rules` that just echoes the key CI variables:

```yaml
debug-rules:
  stage: test
  image: alpine:3.20
  script:
    - echo "branch=$CI_COMMIT_BRANCH tag=$CI_COMMIT_TAG mr=$CI_MERGE_REQUEST_ID"
  rules:
    - if: $CI_COMMIT_TAG
      variables: { CONTEXT: "tag pipeline" }
    - if: $CI_MERGE_REQUEST_ID
      variables: { CONTEXT: "merge request pipeline" }
    - if: $CI_COMMIT_BRANCH == "main"
      variables: { CONTEXT: "main branch pipeline" }
    - when: never
```

Trigger all three contexts (push to main, open an MR, push a tag) and check
which rule matched each time.

**Verify:** you can state the two `rules:` laws: evaluated top-down, first match
wins; no match (or `when: never`) → job doesn't exist in that pipeline.

## Exercise 9.3 — Artifacts vs cache, experienced

1. Give `test` a pip `cache:` keyed on `requirements.txt` (lesson §1) and an
   `artifacts:` block for `report.xml`.
2. Run twice; compare the pip install time between runs (cache hit).
3. Add a `summary` job in the build stage that reads `report.xml`
   (`grep -c "<testcase" report.xml`) — it works because artifacts flow to later
   stages automatically.
4. Now change one letter in `requirements.txt` and run — cache miss, slow
   install, new cache stored.

**Verify:** you observed: cache = speed, silently rebuilt on miss; artifact =
data contract between jobs. State which one `report.xml` must be and why (the
summary job would be *wrong*, not slow, without it).

## Exercise 9.4 — Integration tests with a service container

1. Add the `integration-test` job from lesson §3 (postgres:16 service, alias
   `db`) and an integration test that actually hits the DB — reuse the `/visits`
   logic: a test that inserts and counts rows via `DATABASE_URL`.
2. Run it twice and prove test isolation: the second run's count must not be
   affected by the first run's inserts.

**Verify:** both runs pass identically — each got a **fresh** database. Write one
sentence on why a shared persistent "test DB" would eventually break this.
(Path B note: `gitlab-ci-local` supports services.)

## Exercise 9.5 — Build and push to the GitLab registry (Path A)

1. Add the `build-image` job (dind service, `$CI_REGISTRY_*` login, build,
   push `$CI_COMMIT_SHORT_SHA` tag), rules: main or tag.
2. Remove the lesson's `|| true` on the trivy step and make the scan a real gate.
   Write one sentence justifying it (what does `|| true` do to the exit code
   contract from ch 02?).
3. Push to main; find the image under Deploy → Container Registry.
4. Pull it locally: `docker login registry.gitlab.com` + pull.

**Verify:** image pull works; a HIGH/CRITICAL finding fails the pipeline
(test by temporarily scanning `python:3.8-slim`).

## Exercise 9.6 — Environments + manual production gate (Path A)

1. Add `deploy-staging` (auto on main) and `deploy-prod`
   (`when: manual`, `needs: [deploy-staging]`) with `environment:` blocks —
   fake deploys are fine (`echo` + `sleep`).
2. Run: staging deploys automatically, prod waits for the ▶ button.
3. Explore Operate → Environments: deployment history per environment, and
   re-deploy an *older* pipeline's job to staging — congratulations, that's a
   rollback.

**Verify:** the environments page shows the history and who triggered prod.
Reflect: same gate as GHA `environment:` reviewers and Jenkins `input` — third
spelling, same concept.

## Exercise 9.7 — Reuse with extends and include

1. Refactor your two deploy jobs with a hidden `.deploy-base` and `extends:`.
2. (Path A) Move `.deploy-base` into a second repo `ci-templates`, and `include:`
   it from the app repo. Change the template and watch the app pipeline pick it up.

**Verify:** app `.gitlab-ci.yml` shrank; template change propagated without an
app-repo commit — Jenkins shared library déjà vu, spelled in YAML.

## Exercise 9.8 — The three-way translation (paper, but the most valuable one)

Take the full reference pipeline (lint → test → build → scan → push → staging →
manual gate → prod) and produce a one-page, three-column cheat sheet:
GitHub Actions / Jenkins / GitLab CI, one row per concept (trigger, container
per step, secret injection, artifact passing, parallelism, manual gate,
conditional on branch/tag, reuse mechanism). Fill it from memory first, then
correct it against chapters 07–09.

**Verify:** fewer than 4 corrections needed → you own the concepts, not the
syntax. Keep this sheet; it's your interview crib and your first-day-at-a-new-job map.
