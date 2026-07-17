# Chapter 07 — CI/CD Concepts & GitHub Actions

## Learning objectives

1. Design a pipeline: stages, fail-fast ordering, triggers, artifacts.
2. Write GitHub Actions workflows: jobs, steps, matrices, caching, secrets.
3. Build → test → scan → publish a Docker image automatically on every push.
4. Cut releases from tags; understand environments and deployment gates.
5. Recognize the CI concepts that transfer to Jenkins (ch 08) and GitLab (ch 09).

---

## 1. Pipeline design principles (tool-agnostic)

Before any YAML, the ideas every CI system implements:

- **A pipeline is a directed graph of jobs** triggered by a Git event. Jobs run
  commands; a non-zero exit fails the job; a failed job (usually) stops the pipeline.
- **Fail fast, fail cheap:** order stages by cost — lint (seconds) → unit tests
  (minutes) → build → integration tests → deploy. Feedback in 5 min beats 45.
- **Reproducibility:** each run starts in a clean, ephemeral environment. "It
  passes locally but not in CI" almost always means an undeclared dependency —
  CI is *telling you* your build isn't reproducible.
- **Build once:** produce the artifact (Docker image) in one job; every later
  stage *uses* that artifact — never rebuilds it.
- **Secrets stay out of code:** injected by the CI system at runtime, masked in logs.

Canonical stage sequence you'll implement in three different tools (ch 07–09):

```
lint → unit test → build image → scan → push image → deploy staging → smoke test → [gate] → deploy prod
```

## 2. GitHub Actions — the model

Actions terminology:

| Term | Meaning |
|------|---------|
| **Workflow** | a YAML file in `.github/workflows/`, triggered by events |
| **Event** | `push`, `pull_request`, `schedule`, `workflow_dispatch` (manual), tag push… |
| **Job** | a set of steps on one fresh **runner** VM; jobs run in parallel unless `needs` says otherwise |
| **Step** | a shell command (`run:`) or a reusable **action** (`uses:`) |
| **Runner** | the machine: GitHub-hosted (`ubuntu-latest`) or self-hosted |
| **Action** | packaged reusable step from the marketplace (`actions/checkout@v4`) |

### Minimal real workflow

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4          # you must check out your own code!
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip                        # built-in dependency caching
      - run: pip install -r requirements.txt
      - run: ruff check .                   # lint
      - run: pytest -v                      # tests
```

> **Line by line:**
> - `on:` — the trigger block: run on pushes to `main` and on every pull request (a bare `pull_request:` means "any PR event"). These two triggers together = "validate everything before and after merge".
> - `runs-on: ubuntu-latest` — GitHub boots a fresh Ubuntu VM for this job. Fresh = empty: no code, no Python packages, nothing from previous runs.
> - `uses: actions/checkout@v4` — an *action* (prepackaged step from the marketplace; `actions/` is GitHub's own namespace, `@v4` pins the major version). Checkout clones your repo into the workspace — the fresh VM doesn't even have your code until this runs.
> - `uses: actions/setup-python@v5` + `with:` — installs the Python version you declare (`with:` passes parameters to an action); `cache: pip` transparently caches downloaded packages between runs, keyed on your requirements file.
> - `run: ...` — plain shell commands (bash on Linux runners): install dependencies, run `ruff` (a fast Python linter), run `pytest` (the test runner; `-v` lists each test by name). Each step's exit code decides pass/fail — ch 02's exit-code convention is the entire foundation of CI.
> **Expect:** in the repo's *Actions* tab, a run per push with each step's live log; any non-zero exit turns the step red, fails the job, and marks the commit/PR with an ✗. That X, combined with
branch protection (ch 03), is CI as a *law*.

Anatomy notes:

- Each job gets a **fresh VM** — nothing survives between jobs except what you
  explicitly pass (artifacts) or cache.
- `uses: actions/checkout@v4` — pin actions to at least a major version; for
  hard supply-chain rigor, pin to a commit SHA (ch 16).
- Steps share the job's filesystem and run sequentially; the first failing step
  fails the job.

## 3. The core workflow: build, scan, push a Docker image

This is the chapter's centerpiece — the pattern that powers everything later:

```yaml
name: build-and-publish

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:

env:
  IMAGE: ghcr.io/${{ github.repository }}    # ghcr.io/<owner>/<repo>

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -r requirements.txt
      - run: pytest -v

  build:
    needs: test                     # ← the dependency edge
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write               # allow pushing to ghcr.io
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}   # automatic per-run token

      - name: Compute tags
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE }}
          tags: |
            type=ref,event=pr
            type=sha,prefix=sha-
            type=semver,pattern={{version}}      # v1.2.3 tag → 1.2.3
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build image (don't push yet)
        uses: docker/build-push-action@v6
        with:
          context: .
          load: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Scan for vulnerabilities
        uses: aquasecurity/trivy-action@0.24.0
        with:
          image-ref: ${{ env.IMAGE }}:sha-${{ github.sha }}
          severity: HIGH,CRITICAL
          exit-code: "1"            # fail the build on findings

      - name: Push
        if: github.event_name != 'pull_request'   # PRs build+scan but don't publish
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
```

> **The actions used, one by one:**
> - `docker/setup-buildx-action` — enables BuildKit's advanced builder (`buildx`), needed for the cache options below and multi-platform builds. The `docker/*` namespace is Docker Inc.'s official set.
> - `docker/login-action` — `docker login` as an action. `github.actor` = whoever triggered the run; `secrets.GITHUB_TOKEN` = an automatic, per-run token GitHub mints with exactly the `permissions:` declared above — which is why `packages: write` is there and why no personal token is stored anywhere.
> - `docker/metadata-action` — computes image tags from the Git event so nobody hand-writes tagging logic: a PR builds `pr-42`, a main-branch push builds `sha-<commit>` + `latest`, a `v1.2.3` tag builds `1.2.3`. `id: meta` names the step so later steps can reference its output as `steps.meta.outputs.tags`.
> - `docker/build-push-action` — `docker build`/`push` with cache wiring: `cache-from`/`cache-to: type=gha` stores image layers in GitHub's cache between runs (`mode=max` caches all layers, not just the final ones), so unchanged layers don't rebuild — ch 05's layer-cache lesson, ported to ephemeral CI machines where the local cache would otherwise be empty every time. `load: true` keeps the built image on the runner's local daemon so the *next* step can scan it.
> - `aquasecurity/trivy-action` — ch 06's scanner as a gate. Pinned to an exact version (`@0.24.0`) rather than a floating major — third-party actions deserve tighter pinning than GitHub's own (ch 16 goes further: SHA-pinning).
> - The `${{ ... }}` syntax is the *expression context* — variables GitHub substitutes before running the step: `github.repository`, `github.sha`, `secrets.*`, `steps.<id>.outputs.*`.

Read the design decisions, they matter more than the syntax:

- **`needs: test`** — the graph. No artifact without green tests.
- **PRs build and scan but don't push** — validation without publication.
- **Tags:** every main-branch image is tagged with the commit SHA
  (traceability: *which code is this?*), releases get the semver tag from the
  git tag, `latest` moves only on the default branch.
- **`GITHUB_TOKEN`** is minted per run with the `permissions:` you declare —
  no long-lived registry password to leak.
- **Trivy gate** — ch 06's scan, now enforced.

## 4. Secrets, variables, environments

```yaml
      - run: ./deploy.sh
        env:
          API_TOKEN: ${{ secrets.PROD_API_TOKEN }}     # Settings → Secrets
          REGION: ${{ vars.DEPLOY_REGION }}            # Settings → Variables (non-secret)
```

- Secrets are write-only in the UI, masked (`***`) in logs, and *not* exposed to
  workflows triggered from forks (`pull_request` from a fork gets no secrets —
  that's why the push step is gated).
- **Environments** (Settings → Environments: `staging`, `production`) attach
  protection rules to deployment jobs — required reviewers (a manual gate),
  wait timers, environment-scoped secrets:

```yaml
  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production        # ← pauses for the required reviewer
    steps:
      - run: ./deploy.sh prod
```

This is how "Continuous Delivery with a human button" is spelled in Actions.

## 5. Matrices, artifacts, and other daily tools

### Matrix builds — one job definition, N variants

```yaml
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python }}" }
      - run: pip install -r requirements.txt && pytest
```

### Passing files between jobs

Jobs are separate VMs; use artifacts:

```yaml
      - uses: actions/upload-artifact@v4
        with: { name: coverage-report, path: htmlcov/ }
# ...in a later job:
      - uses: actions/download-artifact@v4
        with: { name: coverage-report }
```

(For Docker images, the registry itself is the artifact store — push by SHA tag,
pull downstream.)

### Caching

`actions/setup-python`/`setup-node` have built-in dependency caches; generic:

```yaml
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('requirements.txt') }}
```

> **How `actions/cache` works:** at job start it restores `path` from storage if a cache entry matching `key` exists; at job end it saves `path` under that key. `hashFiles('requirements.txt')` bakes the lockfile's hash into the key, so editing dependencies produces a new key = a clean cache — you can never be poisoned by stale packages. Cache ≠ artifact: a miss must be survivable (the job just runs slower) — the ch 09 comparison table formalizes this.

Key design: cache key = hash of the lockfile → dependency change = new cache.

### Conditionals and expressions

```yaml
    if: github.ref == 'refs/heads/main'
    if: startsWith(github.ref, 'refs/tags/v')
    if: failure()          # run only when something failed (notifications)
    if: always()           # run even after failures (cleanup)
```

### Manual and scheduled triggers

```yaml
on:
  workflow_dispatch:        # "Run workflow" button (with optional inputs)
  schedule:
    - cron: "0 3 * * *"     # nightly: long tests, dependency scans
```

## 6. Debugging failing workflows — the practical skill

1. **Read the log of the first failing step** — not the last message; scroll to
   the first error. Exit codes rule everything (ch 02).
2. Re-run with debug: repo secret `ACTIONS_STEP_DEBUG=true`, or the "Re-run with
   debug logging" button.
3. Reproduce locally: the runner is just Ubuntu — run the same commands in a
   `ubuntu:24.04` container. If it passes locally and fails in CI: undeclared
   dependency, missing env var, or an assumption about the machine.
4. Print context when confused:
   `- run: echo '${{ toJSON(github) }}'` shows the whole event payload.
5. `act` (github.com/nektos/act) runs workflows locally in Docker — imperfect
   but fast iteration.

Common beginner failures:

| Symptom | Cause |
|---------|-------|
| `fatal: not a git repository` | forgot `actions/checkout` |
| works on PR, fails on main | secrets/permissions differ between contexts |
| `permission denied` pushing to ghcr | missing `permissions: packages: write` |
| artifact not found | consumer ran before producer — missing `needs:` |
| tests pass locally, fail in CI | undeclared dep / env var / relies on local files |

## 7. What transfers to other CI systems

You will meet Jenkins and GitLab CI next. The mapping to remember:

| Concept | GitHub Actions | Jenkins | GitLab CI |
|---------|----------------|---------|-----------|
| Definition file | `.github/workflows/*.yml` | `Jenkinsfile` | `.gitlab-ci.yml` |
| Unit of parallelism | job | stage/parallel | job |
| Ordering | `needs:` | `stages { }` order | `stages:` + `needs:` |
| Executor | runner | agent/node | runner |
| Reusable pieces | actions | shared libraries | includes/templates |
| Manual gate | environment reviewers | `input` step | `when: manual` |

Learn the concepts once; the rest is syntax.

## Further reading

- docs.github.com/actions — "Understanding GitHub Actions", workflow syntax reference.
- docker/build-push-action and docker/metadata-action READMEs.

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 08: Jenkins](../08-jenkins/lesson.md)
