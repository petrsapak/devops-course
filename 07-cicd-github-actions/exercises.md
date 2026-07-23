# Chapter 07 — Exercises

You need a GitHub account and a repo. Reuse `devops-playground` from ch 03 or
create `devops-ci-lab`. Put the ch 05/06 Flask "visits" app in it (app.py,
requirements.txt, Dockerfile, plus a tests folder below).

You may copy the runnable
[visits-platform lab](../labs/visits-platform/README.md); its
`.github/workflows` directory is a reference implementation. Create your own
workflow before comparing it with the reference.

Add a minimal test suite `test_app.py`:

```python
from app import app

def test_health():
    client = app.test_client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"
```

(Adjust the app so importing it doesn't start the server / require a DB — that
refactor is itself part of the exercise.)

---

## Exercise 7.1 — First green pipeline

1. Create `.github/workflows/ci.yml` that, on every push and PR: checks out,
   sets up Python 3.12 with pip cache, installs deps, runs `pytest`.
2. Push and watch the Actions tab. Make it green.
3. Now break a test on purpose, push, and observe the red X — then fix it.

**Verify:** you have one red run and green runs before/after it; total runtime
under ~1 minute (cache working from run 2 on).

## Exercise 7.2 — Fail fast with lint

1. Add `ruff` to the pipeline **before** pytest (separate step).
2. Introduce a lint violation (unused import), push, and check that the pipeline
   fails at the lint step *without* running the tests.

**Verify:** the failed run's log shows the pytest step as "skipped"/not reached.
Explain in one sentence why lint runs first.

## Exercise 7.3 — Enforce it with branch protection

1. Protect `main`: require a PR and require the CI check to pass before merging.
2. Open a PR with a failing test. Confirm the Merge button is blocked.
3. Fix the test in the PR branch and merge once green.

**Verify:** GitHub UI showed "Required check failed" blocking the merge. This is
ch 01's "automated gate" made real.

## Exercise 7.4 — Matrix

Convert the test job to a matrix over Python 3.11 / 3.12 / 3.13 with
`fail-fast: false`.

**Verify:** the Actions run shows three parallel test jobs; one failing version
(you can force one with a version-specific assert) doesn't cancel the others.

## Exercise 7.5 — Build, scan, and publish to ghcr.io

Implement the centerpiece workflow from lesson §3 (adapt image name to your repo):

1. `test` job (your matrix from 7.4 is fine).
2. `build` job with `needs: test`: buildx, login to ghcr with `GITHUB_TOKEN`,
   metadata-action tags (sha + latest-on-main), build with `load: true`,
   trivy scan gate, push only when not a PR.
3. Push to main. Then check: your repo → Packages → the image with `sha-…` and
   `latest` tags.
4. Open a PR and confirm the image is built and scanned but **not** pushed.
5. Pull and run your published image locally:
   `docker run --rm -p 8000:8000 ghcr.io/<you>/<repo>:latest` (make the package
   public, or `docker login ghcr.io` with a PAT).

**Verify:** all four behaviors: green main run pushes; PR run doesn't; trivy step
shows scan results; the pulled image serves `/health`.

## Exercise 7.6 — Release on tag

1. Extend the workflow triggers with `tags: ["v*"]` (already in the lesson
   version) and the semver pattern in metadata-action.
2. Locally: `git tag -a v1.0.0 -m "First release" && git push origin v1.0.0`.
3. Watch the run; confirm the package now has a `1.0.0` tag.
4. Bonus: add a job that creates a GitHub Release with
   `softprops/action-gh-release@v2` when a tag triggers the run.

**Verify:** `docker pull ghcr.io/<you>/<repo>:1.0.0` works. You've implemented
ch 03's table row: "tag push → release pipeline".

## Exercise 7.7 — Environments and a manual gate

1. Create environments `staging` and `production` in repo Settings; on
   `production`, add yourself as a **required reviewer**.
2. Add two deployment jobs (they can fake the deploy —
   `run: echo "deploying $IMAGE to staging" && sleep 5`):
   `deploy-staging` (needs: build, on main only) and `deploy-prod`
   (needs: deploy-staging, `environment: production`).
3. Push to main and watch the pipeline pause at production until you approve it
   in the UI.

**Verify:** the run sat in "Waiting" until your approval — Continuous Delivery
with a human button. Note who/when is recorded (audit trail).

## Exercise 7.8 — Nightly job + failure notification

1. Add a scheduled workflow (`cron: "0 3 * * *"`) that runs the full test suite
   and `trivy image` against your `latest` image (catching *newly disclosed*
   CVEs in an unchanged image — why scans must recur).
2. Add a final step with `if: failure()` that prints a loud message (in real
   life: Slack webhook).
3. Don't wait for 03:00 — add `workflow_dispatch:` and trigger it manually.

**Verify:** manual run succeeds; temporarily set trivy severity to `LOW` with
exit-code 1 to force a failure and see the `if: failure()` step fire.

## Exercise 7.9 — Debug drill

Deliberately commit each of these classic breakages (one at a time), read the
failing log, and write down the diagnosis *before* fixing:

1. Delete the `actions/checkout` step from the test job.
2. Remove `permissions: packages: write` from the build job.
3. Make a test depend on a file that exists locally but isn't committed.

**Verify:** your written diagnoses match the "common beginner failures" table in
the lesson — you recognized each from the log alone.

## Exercise 7.10 — Extract a reusable workflow

1. Move the Python setup, dependency installation, and test steps into
   `.github/workflows/reusable-python.yml` triggered by `workflow_call`.
2. Add a typed string input named `python-version` with default `3.12`.
3. Replace the original test job with a caller job using `uses:` and `with:`.
4. Add a matrix in the caller for Python 3.11, 3.12, and 3.13.
5. Call the reusable workflow from a second throwaway workflow to prove it is
   not coupled to one trigger.

**Verify:** both callers run the shared job, the three matrix versions are
visible, and changing one test step in the reusable file changes both callers.

---

**Stretch goal:** run your workflow locally with `act` and note where local
execution differs from real runners.
