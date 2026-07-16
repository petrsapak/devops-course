# Chapter 08 — Jenkins

## Learning objectives

1. Run and administer a Jenkins instance: plugins, credentials, users, backup.
2. Write declarative `Jenkinsfile` pipelines: stages, agents, environment, post actions.
3. Use Multibranch Pipelines so every branch/PR gets built automatically.
4. Handle credentials safely and build/push Docker images from Jenkins.
5. Understand controller/agent architecture and shared libraries.

Why Jenkins still matters: it's ~20 years old, self-hosted, and infinitely
pluggable — which is exactly why enterprises with compliance requirements, air-gapped
networks, or a decade of build history still run it. You *will* encounter Jenkins.
The concepts are ch 07's; only the spelling changes.

---

## 1. Architecture

- **Controller** — the web UI + brain: stores job definitions, schedules builds,
  serves the UI. Should not run heavy builds itself.
- **Agents (nodes)** — machines that execute the builds. Connected via SSH or
  inbound (JNLP). Each offers **executors** (parallel build slots) and **labels**
  (`linux`, `docker`, `windows`) that pipelines target.
- **Jobs/Projects** — of which the only kind you should write today is the
  **Pipeline** (defined by a `Jenkinsfile` in the repo — pipeline-as-code, same
  philosophy as workflow YAML).
- **Plugins** — everything is a plugin (Git, Docker, credentials, UI). Power and
  Achilles' heel both: plugin upgrades are the main Jenkins maintenance burden.

```
┌────────────┐      ┌─────────────────┐
│ Controller │──────│ Agent: linux    │ 2 executors
│  (UI, cron,│      ├─────────────────┤
│  queue)    │──────│ Agent: docker   │ 4 executors
└────────────┘      └─────────────────┘
```

## 2. Lab setup — Jenkins in Docker

```bash
docker network create jenkins
docker volume create jenkins_home

docker run -d --name jenkins \
  --network jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts-jdk17
```

Notes:
- `jenkins_home` volume = ALL state (jobs, config, history). Backing up Jenkins =
  backing up this directory.
- Mounting `docker.sock` lets pipelines run `docker build` using the host daemon.
  **Remember ch 06: socket access = root on the host.** Acceptable in this lab;
  in production you'd use dedicated build agents, Docker-in-Docker with care, or
  rootless builders (kaniko/buildkit).
- You'll need the docker CLI inside: for the lab, install it in the container
  (`docker exec -u root jenkins bash -c "apt-get update && apt-get install -y docker.io"`)
  or build a small custom image — the exercises walk through it.

First-run wizard: `docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword`
→ paste at `http://localhost:8080` → **Install suggested plugins** → create admin user.

Also install (Manage Jenkins → Plugins): **Docker Pipeline**, **Blue Ocean** (nicer
pipeline UI, optional).

## 3. The Jenkinsfile — declarative pipeline

The complete reference example (mirrors ch 07's centerpiece):

```groovy
pipeline {
    agent any                        // run on any available node
    // agent { label 'docker' }      // or target a label
    // agent { docker { image 'python:3.12-slim' } }  // or run stages IN a container

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    environment {
        IMAGE = "ghcr.io/you/myapp"
        // credential binding: creates REGISTRY_CREDS_USR and REGISTRY_CREDS_PSW
        REGISTRY_CREDS = credentials('ghcr-token')
    }

    triggers {
        pollSCM('H/5 * * * *')       // fallback; prefer webhooks
    }

    stages {
        stage('Lint & Test') {
            agent { docker { image 'python:3.12-slim'; reuseNode true } }
            steps {
                sh 'pip install -r requirements.txt ruff pytest'
                sh 'ruff check .'
                sh 'pytest -v --junitxml=results.xml'
            }
            post {
                always { junit 'results.xml' }   // test report in the UI
            }
        }

        stage('Build image') {
            steps {
                sh "docker build -t ${IMAGE}:${GIT_COMMIT.take(7)} ."
            }
        }

        stage('Scan') {
            steps {
                sh "trivy image --severity HIGH,CRITICAL --exit-code 1 ${IMAGE}:${GIT_COMMIT.take(7)}"
            }
        }

        stage('Push') {
            when { branch 'main' }               // only on main
            steps {
                sh 'echo $REGISTRY_CREDS_PSW | docker login ghcr.io -u $REGISTRY_CREDS_USR --password-stdin'
                sh "docker push ${IMAGE}:${GIT_COMMIT.take(7)}"
            }
        }

        stage('Deploy to prod') {
            when { branch 'main' }
            steps {
                input message: 'Deploy to production?', ok: 'Ship it'   // manual gate
                sh './deploy.sh prod'
            }
        }
    }

    post {
        failure {
            echo "Build failed — notify here (Slack/mail plugins)"
        }
        always {
            cleanWs()                // wipe the workspace
        }
    }
}
```

### Structure decoded

| Block | Purpose | GitHub Actions equivalent |
|-------|---------|---------------------------|
| `pipeline {}` | root of declarative syntax | the workflow file |
| `agent` | where it runs (any / label / docker image) | `runs-on` |
| `stages/stage/steps` | the sequence of work | jobs/steps |
| `environment` | env vars + credential binding | `env:` + `secrets` |
| `when` | conditional stage execution | `if:` |
| `input` | manual gate mid-pipeline | environment required reviewers |
| `post` | always/success/failure hooks | `if: always()/failure()` |
| `options` | timeouts, log rotation, concurrency | various |

Details that matter:

- **`agent { docker { image ... } }`** runs the stage's steps inside a container —
  clean, pinned toolchains without polluting agents. `reuseNode true` keeps the
  workspace on the same node.
- **`when { branch 'main' }`** — declarative conditions; also `when { tag "v*" }`,
  `when { changeRequest() }` (PRs), `expression { ... }` for arbitrary Groovy.
- **`input`** pauses the build and records who clicked — Jenkins' manual gate.
  Put it in its own stage and consider a `timeout` around it.
- **`junit`** publishes test results — trend graphs, flaky-test history; a real
  Jenkins strength.
- Everything is Groovy underneath: `${GIT_COMMIT.take(7)}` is a method call.
  **Scripted pipeline** (`node { ... }`) is the older free-form dialect — read it
  when you meet it, write declarative.

## 4. Credentials — the right way

Manage Jenkins → Credentials → add:

- **Username/password** (e.g., registry login) — bind with
  `credentials('id')` → `_USR`/`_PSW` vars, or `withCredentials`:

```groovy
withCredentials([usernamePassword(credentialsId: 'ghcr-token',
                                  usernameVariable: 'U', passwordVariable: 'P')]) {
    sh 'echo $P | docker login ghcr.io -u $U --password-stdin'
}
```

- **Secret text** (API tokens), **SSH keys** (git/deploy), **files** (kubeconfig).

Rules: secrets are masked in logs (`****`) *only* when bound through the
credentials mechanisms — `echo`-ing a secret you assembled yourself is on you.
Never put secrets in job parameters or the Jenkinsfile. Scope credentials to
folders when teams share an instance.

## 5. Multibranch Pipelines & webhooks

A **Multibranch Pipeline** job points at a repo and auto-creates a sub-job for
every branch (and PR) containing a `Jenkinsfile`:

- New branch pushed → job appears, builds.
- Branch deleted → job cleaned up.
- With the GitHub Branch Source plugin, PRs get built and the result is reported
  back as a commit status — branch protection can require it (same law as ch 07).

**Triggering:** webhooks (GitHub → your Jenkins `/github-webhook/` endpoint) are
instant; `pollSCM` is the fallback where webhooks can't reach (lab machines,
firewalled Jenkins). In the lab you'll use polling; know that real installs use
webhooks.

## 6. Shared libraries — don't copy-paste Jenkinsfiles

When 30 repos each carry a 200-line Jenkinsfile, maintenance dies. A **shared
library** is a Git repo of Groovy steps every pipeline can import:

```
jenkins-library/
└── vars/
    ├── buildAndScanImage.groovy     // becomes a step: buildAndScanImage(...)
    └── notifySlack.groovy
```

`vars/buildAndScanImage.groovy`:

```groovy
def call(Map cfg) {
    sh "docker build -t ${cfg.image}:${cfg.tag} ."
    sh "trivy image --severity HIGH,CRITICAL --exit-code 1 ${cfg.image}:${cfg.tag}"
}
```

Consumer Jenkinsfile shrinks to:

```groovy
@Library('devops-lib') _
pipeline {
    agent any
    stages {
        stage('Build') {
            steps { buildAndScanImage(image: 'ghcr.io/you/myapp', tag: GIT_COMMIT.take(7)) }
        }
    }
}
```

Register under Manage Jenkins → System → Global Trusted Pipeline Libraries.
This is Jenkins' answer to reusable actions/templates — and how platform teams
standardize pipelines org-wide.

## 7. Administration survival kit

- **Backup** = the `jenkins_home` volume (config, jobs, history, secrets).
  Practice restoring it — a backup you've never restored is a hope, not a backup.
- **Plugin discipline:** fewer plugins = fewer CVEs and fewer broken upgrades.
  Update Jenkins LTS + plugins on a schedule, in a test instance first.
- **Configuration as Code (JCasC plugin):** the whole system config in YAML in
  Git — the cure for "nobody knows why this checkbox is set."
- **Executors on the controller: set to 0** in production — builds belong on agents.
- **Security:** enable authentication, use matrix/role-based authorization,
  keep Jenkins off the public internet (or behind SSO/VPN). An open Jenkins with
  script console = remote root for everyone (the script console executes
  arbitrary Groovy on the controller).
- Common failures: builds queue forever → no agent matches the label / no free
  executors; "workspace is locked" → concurrent builds colliding
  (`disableConcurrentBuilds()`); mysterious failures after upgrade → plugin
  compatibility.

## 8. Jenkins vs. modern SaaS CI — honest comparison

| | Jenkins | GitHub Actions / GitLab SaaS |
|---|---------|------------------------------|
| Hosting | yours (control, and burden) | theirs |
| Cost model | infra + admin time | per-minute (free tiers) |
| Air-gapped/compliance | excellent | limited |
| Plugin/customization depth | unmatched | growing |
| Maintenance | significant (upgrades, plugins, agents) | near-zero |
| Pipeline-as-code | Jenkinsfile (Groovy) | YAML |

The pattern in industry: new projects default to SaaS CI; Jenkins persists where
control, compliance, or legacy demand it — often both coexist.

## Further reading

- jenkins.io/doc — Pipeline syntax reference and "Pipeline: Getting Started".
- jenkins.io/doc/book/managing/casc/ — Configuration as Code.

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 09: GitLab CI](../09-gitlab-ci-patterns/lesson.md)
