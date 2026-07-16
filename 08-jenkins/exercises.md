# Chapter 08 — Exercises

These run entirely on your machine: Jenkins in Docker + your local Git repos.
Budget a full evening — Jenkins rewards patience.

---

## Exercise 8.1 — Install and tour

1. Start Jenkins exactly as in lesson §2 (network, volume, socket mount).
2. Complete the setup wizard (suggested plugins + admin user).
3. Give the container a docker CLI:
   `docker exec -u root jenkins bash -c "apt-get update && apt-get install -y docker.io && usermod -aG docker jenkins"`
   then `docker restart jenkins`.
4. Sanity check: `docker exec jenkins docker ps` — Jenkins can see the host daemon.
5. Tour: Manage Jenkins → note where Plugins, Credentials, Nodes, and System live.

**Verify:** step 4 lists containers (including jenkins itself — think about why).

## Exercise 8.2 — Freestyle job (once, to know what you're NOT going to use)

1. New Item → Freestyle project `hello-freestyle`. Build step: shell
   `echo "Hello from build $BUILD_NUMBER on $(hostname)"`.
2. Build it twice; open the console output of each.
3. Note where this configuration lives (clicked together in the UI — not in Git).

**Verify:** you can articulate why UI-configured jobs lose to pipeline-as-code
(no review, no history, no reproducibility — then delete the job).

## Exercise 8.3 — First Jenkinsfile

1. Create a local git repo `~/devops/ch08/pipeline-lab` with the Flask app +
   tests from ch 07 and this Jenkinsfile skeleton:

```groovy
pipeline {
    agent any
    stages {
        stage('Test') {
            agent { docker { image 'python:3.12-slim'; reuseNode true } }
            steps {
                sh 'pip install -r requirements.txt pytest'
                sh 'pytest -v --junitxml=results.xml'
            }
            post { always { junit 'results.xml' } }
        }
    }
}
```

2. Jenkins can't reach `~/devops` directly — but it can reach a bind-mounted path.
   Easiest lab route: restart jenkins with an extra
   `-v ~/devops/ch08:/repos` mount (rm + rerun the container — the volume keeps
   all config, notice that!). Then: New Item → Pipeline → Definition: "Pipeline
   script from SCM", SCM: Git, URL `file:///repos/pipeline-lab`.
3. Build. Fix whatever breaks (this is the exercise). Check the test report page.

**Verify:** blue/green ball; Test Result page shows your pytest cases; and you
observed that recreating the container lost nothing (jenkins_home volume).

## Exercise 8.4 — Full build-scan-push pipeline

Extend the Jenkinsfile to mirror ch 07's centerpiece:

1. Stages: Lint & Test → Build image (`myapp:${GIT_COMMIT.take(7)}`) → Scan
   (trivy via `docker run aquasec/trivy` since it's not installed natively) →
   Push (to your ghcr.io or Docker Hub).
2. Add credentials: Manage Jenkins → Credentials → username/password with your
   registry token, id `registry-creds`. Bind via `credentials()` in `environment`.
3. Gate the Push stage with `when { branch 'main' }`.
4. Run it. Then check the console log: is your token masked?

**Verify:** image appears in the registry; grep the console output for your
token — it must show `****`. Try `sh 'echo $REGISTRY_CREDS_PSW'` and observe
masking as well; then remove that line (don't tempt fate).

## Exercise 8.5 — Manual gate with input

1. Add a `Deploy` stage: `when { branch 'main' }`, an
   `input message: 'Deploy?', ok: 'Go'` step, then a fake deploy echo.
2. Wrap the input in `timeout(time: 10, unit: 'MINUTES') { ... }` — what happens
   if nobody clicks within the window?
3. Build; find the paused stage in the UI (classic view and, if installed, Blue
   Ocean); approve it.

**Verify:** the build paused, recorded who approved, and proceeded. Abort one run
via the input's Abort to see that path too.

## Exercise 8.6 — Multibranch Pipeline

1. In your repo, create branches `main` and `feature/x` (tiny difference in each).
2. New Item → **Multibranch Pipeline** → Git source `file:///repos/pipeline-lab`.
3. Scan the repository; watch Jenkins create one job per branch and build both.
4. Confirm the `when { branch 'main' }` stages were skipped on `feature/x`.
5. Delete the feature branch, rescan, observe cleanup.

**Verify:** the branch view shows main (full pipeline) and feature/x (Push/Deploy
skipped) — one Jenkinsfile, branch-aware behavior.

## Exercise 8.7 — Shared library

1. Create repo `~/devops/ch08/jenkins-lib` with
   `vars/buildAndScanImage.groovy` from lesson §6 (commit it).
2. Register it: Manage Jenkins → System → Global Trusted Pipeline Libraries —
   name `devops-lib`, default version `main`, SCM Git `file:///repos/jenkins-lib`.
3. Refactor your Jenkinsfile's Build+Scan stages to a single
   `buildAndScanImage(image: ..., tag: ...)` call with `@Library('devops-lib') _`.
4. Change the library (e.g., add an echo of the scan policy), commit, rebuild the
   app job — the change applies without touching the app repo.

**Verify:** step 4 — that's the point of libraries: one commit updates every
consumer pipeline.

## Exercise 8.8 — Break/fix admin drill

1. **Backup:** `docker run --rm -v jenkins_home:/data -v $PWD:/backup ubuntu tar czf /backup/jenkins-backup.tgz /data`.
2. **Disaster:** `docker rm -f jenkins && docker volume rm jenkins_home`.
   Confirm Jenkins is gone (fresh wizard would greet you).
3. **Restore:** recreate the volume, untar the backup into it, start the
   container, log in with your old admin user.

**Verify:** jobs, build history, and credentials are back. You have now done the
thing most Jenkins admins only hope works.

## Exercise 8.9 — Concept mapping (paper)

Fill the table from memory, then check against lesson §3:

| Need | GitHub Actions | Jenkins |
|------|----------------|---------|
| Run only on main | | |
| Manual approval | | |
| Secret injection | | |
| Run step in a container | | |
| Publish test results | | |
| Reusable pipeline code | | |

**Verify:** ≥5 of 6 rows correct → the concepts transferred; you'd be productive
in either tool.

---

**Cleanup (optional — you may want Jenkins for the capstone):**
`docker rm -f jenkins` (keep `jenkins_home` volume to resume later).
