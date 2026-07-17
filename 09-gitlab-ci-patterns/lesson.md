# Chapter 09 — GitLab CI & Pipeline Patterns

## Learning objectives

1. Write `.gitlab-ci.yml` pipelines: stages, jobs, rules, artifacts, cache.
2. Use GitLab-specific strengths: built-in registry, environments, review apps, templates.
3. Recognize the *patterns* shared by all CI systems — and cement them by seeing
   the third spelling of the same pipeline.
4. Make an informed CI system recommendation for a given organization.

This chapter is deliberately lighter on setup: you've built the same pipeline
twice; the third time is about pattern recognition. (Exercises offer both a
gitlab.com path and a fully local one.)

---

## 1. The GitLab model

GitLab is a single application covering repo + CI + registry + issues + more.
CI specifics:

| Term | Meaning | GHA / Jenkins equivalent |
|------|---------|--------------------------|
| `.gitlab-ci.yml` | pipeline definition at repo root | workflow YAML / Jenkinsfile |
| **Stage** | ordering bucket; all jobs in a stage run in parallel, stages run sequentially | — / `stage` |
| **Job** | named unit with a script, runs on a runner | job / stage |
| **Runner** | executor (shared on gitlab.com, or self-hosted) | runner / agent |
| `rules:` | when a job runs | `if:` / `when {}` |
| `needs:` | DAG edges that *bypass* stage ordering | `needs:` / — |
| **Artifacts** | files passed between jobs & downloadable | upload-artifact |
| **Environments** | named deploy targets with history & protection | environments |

### The reference pipeline, third spelling

```yaml
stages: [test, build, deploy]

variables:
  IMAGE: $CI_REGISTRY_IMAGE          # built-in: this project's registry path

default:
  interruptible: true                # newer pipeline on same branch cancels this one

lint:
  stage: test
  image: python:3.12-slim            # every job runs IN a container by default
  script:
    - pip install ruff
    - ruff check .

test:
  stage: test
  image: python:3.12-slim
  script:
    - pip install -r requirements.txt pytest
    - pytest -v --junitxml=report.xml
  artifacts:
    when: always
    reports:
      junit: report.xml              # test results in MR UI
  cache:
    key:
      files: [requirements.txt]      # cache key from lockfile hash — same design as ch 07
    paths: [.cache/pip]

build-image:
  stage: build
  image: docker:27
  services:
    - docker:27-dind                 # Docker-in-Docker sidecar for docker builds
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $IMAGE:$CI_COMMIT_SHORT_SHA .
    - docker run --rm aquasec/trivy image --severity HIGH,CRITICAL --exit-code 1 $IMAGE:$CI_COMMIT_SHORT_SHA || true   # see note below
    - docker push $IMAGE:$CI_COMMIT_SHORT_SHA
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_TAG

deploy-staging:
  stage: deploy
  environment:
    name: staging
    url: https://staging.example.com
  script: [ "./deploy.sh staging $IMAGE:$CI_COMMIT_SHORT_SHA" ]
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy-prod:
  stage: deploy
  environment:
    name: production
    url: https://example.com
  script: [ "./deploy.sh prod $IMAGE:$CI_COMMIT_SHORT_SHA" ]
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual                   # ← the manual gate, GitLab spelling
  needs: [deploy-staging]
```

(Note: in real configs don't `|| true` a security gate — shown only to keep the
lab pipeline moving; the exercises make you remove it and justify why.)

> **The build-image job, line by line** (the rest of the file is ch 07's pipeline in new spelling — the table above maps it):
> - `image: docker:27` — the job runs inside the official Docker *CLI* image…
> - `services: [docker:27-dind]` — …and gets a **D**ocker-**in**-**D**ocker sidecar: a second container running an actual Docker daemon, reachable from the job. The CLI in the job talks to the daemon in the sidecar. This is GitLab's stock answer to "how do I `docker build` inside a container without touching the host's docker.sock" — more isolation than the ch 08 socket mount, at the cost of no shared layer cache between runs.
> - `docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY` — all three variables are **predefined**: GitLab injects per-job credentials for the project's own built-in registry. Zero secret configuration for the most common CI task — genuinely a GitLab selling point.
> - `docker run --rm aquasec/trivy image ...` — ch 06's scanner, run as a container since the `docker:27` image doesn't include trivy.
> - `rules:` — evaluated top-down, first match wins: this job runs on main-branch pushes or tag pushes, and (no matching rule) simply doesn't exist on other branches — GitLab's equivalent of ch 07's `if:` gating.

Reading notes:

- **Everything runs in containers by default** (`image:`) — GitLab was
  container-native early; there's no "install python on the runner" step.
- **`services:`** — sidecar containers for the job: `docker:dind` for builds,
  or `postgres:16` for integration tests (the killer feature — see §3).
- **Predefined variables** do heavy lifting: `$CI_COMMIT_SHORT_SHA`,
  `$CI_COMMIT_TAG`, `$CI_REGISTRY_*` (auto-credentials for the built-in
  registry — no secret setup needed at all).
- **`rules:`** evaluate top-down, first match wins; `when: manual` inside a rule
  = manual gate; `when: never` excludes.
- **`environment:`** gives a deployment history per target, "stop" actions, and
  protected environments (only maintainers can trigger — approval semantics).

## 2. Artifacts vs cache — a distinction all CI shares

| | Artifacts | Cache |
|---|---|---|
| Purpose | pass **results** between jobs/stages; keep outputs | speed up repeats of **derivable** work |
| Guaranteed? | yes — downstream jobs get them | no — a cache miss must be survivable |
| Examples | test reports, binaries, coverage | pip/npm caches, compiled deps |
| Lifetime | `expire_in`, downloadable from UI | evicted whenever |

Rule: if the pipeline would be *wrong* without it → artifact. If merely
*slower* → cache. Teams that cache build outputs (instead of artifacting them)
get heisenbuilds; teams that artifact node_modules get 2 GB uploads.

## 3. Integration testing with services — the pattern to steal

Real integration tests need a real database. GitLab's spelling:

```yaml
integration-test:
  stage: test
  image: python:3.12-slim
  services:
    - name: postgres:16
      alias: db
  variables:
    POSTGRES_USER: app
    POSTGRES_PASSWORD: test
    POSTGRES_DB: appdb
    DATABASE_URL: "postgresql://app:test@db:5432/appdb"
  script:
    - pip install -r requirements.txt pytest
    - pytest tests/integration -v
```

> **How this works at runtime:** GitLab starts the `postgres:16` service container *first*, on a private network shared with the job container, reachable at hostname `db` (the `alias`; without an alias the image name doubles as hostname). The `POSTGRES_*` variables configure the service (that image reads them at init — ch 06); `DATABASE_URL` points the tests at it. Every run gets a **brand-new, empty database that vanishes with the job** — no state can bleed between runs, no cleanup step can be forgotten. If tests fail with "connection refused" immediately, the service was still booting: real setups add a wait-for-it loop or rely on the app's retry logic.

The same pattern exists everywhere — learn it as a concept:
- GitHub Actions: `services:` block on the job (same idea, same name).
- Jenkins: start a container in a stage or use `docker compose up` in the build.
- Everywhere: an ephemeral, per-run database at a known hostname — never a
  shared long-lived "test database" (state bleeds between runs; ch 01's
  reproducibility principle).

## 4. Templates and includes — GitLab's reuse story

```yaml
include:
  - project: 'platform/ci-templates'      # org-wide templates repo
    file: '/python-service.yml'
  - template: Security/SAST.gitlab-ci.yml # GitLab's built-in scanners

# extend/override what the template defined:
deploy-prod:
  variables:
    REGION: eu-central
```

Plus `extends:` for intra-file reuse:

```yaml
.deploy-base:                 # leading dot = hidden/abstract job
  image: alpine:3.20
  script: [ "./deploy.sh $TARGET" ]

deploy-staging:
  extends: .deploy-base
  variables: { TARGET: staging }
```

Same role as GHA reusable workflows and Jenkins shared libraries. Every mature CI
setup converges on: **a platform team owns templates; product repos stay thin.**

## 5. Review apps — ephemeral environment per merge request

A GitLab pattern worth knowing everywhere: deploy every MR to its own throwaway
environment, URL posted in the MR, destroyed on merge/close.

```yaml
review-app:
  stage: deploy
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    url: https://$CI_COMMIT_REF_SLUG.review.example.com
    on_stop: stop-review
  script: [ "./deploy-review.sh" ]
  rules: [ { if: $CI_MERGE_REQUEST_ID } ]

stop-review:
  stage: deploy
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    action: stop
  script: [ "./destroy-review.sh" ]
  rules: [ { if: $CI_MERGE_REQUEST_ID, when: manual } ]
```

Reviewers click a URL instead of imagining the change. Requires cheap, automated
environments — which is exactly what containers + IaC (ch 11–13) make possible.
This idea (preview deployments) now exists on every platform (Vercel/Netlify
previews, Argo CD ApplicationSets, Heroku review apps).

## 6. Choosing a CI system — the decision framework

Having now used three, the honest summary:

| Situation | Sensible default |
|-----------|-----------------|
| Code already on GitHub | GitHub Actions |
| Code already on GitLab (or want repo+CI+registry in one self-hostable app) | GitLab CI |
| Air-gapped / heavy compliance / deep legacy & plugin needs | Jenkins (self-hosted GitLab also viable) |
| Enterprise .NET/Azure shop | Azure DevOps Pipelines (same concepts, YAML) |
| Monorepo at scale, hermetic builds | Bazel + any of the above (different problem) |

What actually matters more than the tool: pipeline design (fail fast, build once,
gate on scans, deploy from artifacts). Those transferred unchanged across all
three chapters — that's the real lesson.

## Further reading

- docs.gitlab.com/ee/ci/ — `.gitlab-ci.yml` reference and "CI/CD examples".
- docs.gitlab.com/ee/ci/environments/ — environments & review apps.

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 10: Artifacts & Releases](../10-artifacts-releases/lesson.md)
