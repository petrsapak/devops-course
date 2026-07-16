# Chapter 08 — Test

15 questions. Passing: 12/15.

---

**Q1.** Describe the controller/agent architecture and why production controllers
should have zero executors.

**Q2.** Where does ALL Jenkins state live in our Docker setup, and what does that
imply for backup?

**Q3.** What is the difference between a Freestyle job and a Pipeline job, and
why is pipeline-as-code strongly preferred?

**Q4.** In a declarative Jenkinsfile, what do these blocks do: `agent`,
`environment`, `when`, `post`?

**Q5.** What does `agent { docker { image 'python:3.12-slim' } }` on a stage
accomplish, and what problem does it solve compared to installing Python on agents?

**Q6.** Write the `when` conditions for: (a) run only on branch main,
(b) run only for version tags, (c) run only for pull requests.

**Q7.** `REGISTRY = credentials('ghcr-token')` in the environment block — what
variables does it create, and what does Jenkins do if they appear in the log?

**Q8.** What is a Multibranch Pipeline and what does it do when (a) a new branch
with a Jenkinsfile is pushed, (b) a branch is deleted?

**Q9.** Webhook vs `pollSCM` triggering — how does each work and which is
preferred, when possible, and why?

**Q10.** What is the `input` step, where should it NOT be placed (hint:
executor), and what should usually wrap it?

**Q11.** What problem do shared libraries solve, and what does the
`@Library('devops-lib') _` line do?

**Q12.** Mounting `/var/run/docker.sock` into the Jenkins container let us run
`docker build`. Restate the security cost, and name one production alternative.

**Q13.** A build sits in the queue forever with "Waiting for next available
executor". Name two distinct causes and their checks.

**Q14.** Why is an unsecured Jenkins instance (no auth, reachable network) a
critical vulnerability? Name the specific feature that makes it remote code
execution.

**Q15.** Your company has 40 microservice repos with nearly identical
Jenkinsfiles; every pipeline change means 40 PRs. Design the fix in 2–3
sentences using this chapter's tools.

---

<details>
<summary><b>Answer key</b></summary>

1. The controller schedules builds, stores config/history, and serves the UI;
   agents execute builds and are targeted by labels. Controller executors = 0 so
   heavy/hostile build workloads can't starve or compromise the brain.
2. In `/var/jenkins_home` — the `jenkins_home` named volume. Backing up Jenkins
   = archiving that volume; restoring it resurrects jobs, history, credentials,
   config.
3. Freestyle: configured by clicking in the UI — unversioned, unreviewable,
   unreproducible. Pipeline: defined by a Jenkinsfile in the repo — reviewed,
   versioned, branch-aware, recoverable.
4. `agent`: where the pipeline/stage executes. `environment`: env vars and
   credential bindings. `when`: conditional stage execution. `post`:
   always/success/failure hooks after stages or the pipeline.
5. Runs the stage's steps inside a pinned container image — every build gets a
   clean, exact toolchain, and agents stay generic instead of accumulating
   hand-installed tool versions.
6. (a) `when { branch 'main' }` (b) `when { tag "v*" }`
   (c) `when { changeRequest() }`
7. `REGISTRY_USR` and `REGISTRY_PSW`. Jenkins masks bound credential values in
   console output (`****`).
8. A job that scans a repo and materializes one pipeline job per branch/PR
   containing a Jenkinsfile. (a) new job appears and builds automatically;
   (b) the corresponding job is removed on the next scan.
9. Webhook: the Git host calls Jenkins on push — instant, no wasted work.
   Polling: Jenkins asks the repo on a schedule — delayed and wasteful, but works
   when the Git host can't reach Jenkins (firewalls, local labs). Prefer webhooks.
10. A pause for human approval that records the approver. It should not hold a
    heavyweight executor/agent while waiting (structure so the wait doesn't
    block an agent, e.g., `agent none` at top level with per-stage agents).
    Wrap it in a `timeout` so an unanswered gate eventually aborts.
11. Copy-pasted pipeline code across many repos. The annotation imports a
    registered Groovy library repo, exposing its `vars/*.groovy` files as
    pipeline steps; one library commit updates all consumers.
12. Socket access ≈ root on the host (can start privileged containers with host
    mounts). Alternatives: dedicated build agents, kaniko/buildkit rootless
    builds, or isolated DinD with strict controls.
13. No online agent has the label the pipeline demands (check Manage Nodes,
    label spelling); all matching executors are busy/offline (check executor
    counts, agent connectivity). Also possible: `disableConcurrentBuilds` with a
    stuck earlier run.
14. Anyone can reach the **Script Console** (or create a pipeline), which
    executes arbitrary Groovy *on the controller* — i.e., remote code execution
    with access to all stored credentials.
15. Create a shared library encapsulating the standard stages (build, scan,
    push, deploy) behind one step like `standardPipeline(image: ...)`; register
    it globally; each repo's Jenkinsfile shrinks to a few lines calling it.
    Pipeline changes become one PR in the library repo.

</details>

**Scoring:** 12+ → [Chapter 09](../09-gitlab-ci-patterns/lesson.md). Below →
redo exercises 8.4, 8.6, 8.7 — credentials, multibranch, and libraries carry the
most weight in real Jenkins work.
