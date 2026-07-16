# DevOps Course — From Developer to DevOps Engineer

A hands-on curriculum that takes a software developer with basic engineering skills to
practical, job-ready fluency with the tools and practices used in modern DevOps.

## How this course works

- **16 chapters + a capstone project.** Each chapter lives in its own folder:
  - `lesson.md` — the theory, concepts, and worked examples
  - `exercises.md` — hands-on practice tasks with verification steps
  - `test.md` — a chapter test (multiple choice + practical) with an answer key
- **Everything runs locally** on Windows 11 + WSL2 + Docker Desktop. No cloud account
  or spending required. Cloud concepts are taught in a provider-agnostic way.
- **Do the exercises.** Reading alone will not make the skills stick. Every exercise
  has a "verify" step so you know you got it right.
- **Pass the tests.** Aim for 80%+ before moving to the next chapter. The tests are
  designed to catch the gaps the exercises might not.

## Estimated effort

Roughly 60–80 hours total. Suggested pace: 2 chapters per week ≈ 2 months.

## Curriculum

| # | Chapter | What you'll be able to do |
|---|---------|---------------------------|
| 01 | [DevOps Fundamentals & Culture](01-devops-fundamentals/lesson.md) | Explain what DevOps is (and isn't), CALMS, DORA metrics, the deployment pipeline mental model |
| 02 | [Environment Setup + Linux & Shell](02-linux-and-shell/lesson.md) | Set up WSL2 + Docker Desktop; navigate, script, and troubleshoot in bash like it's home |
| 03 | [Git & Collaboration Workflows](03-git-workflows/lesson.md) | Branching strategies, PR hygiene, rebasing, hooks, trunk-based development, release tagging |
| 04 | [Networking & Web Fundamentals](04-networking/lesson.md) | DNS, HTTP(S), TLS, ports, load balancing, reverse proxies — debug "it doesn't connect" issues |
| 05 | [Docker Fundamentals](05-docker-fundamentals/lesson.md) | Build images, run containers, write Dockerfiles, use registries |
| 06 | [Docker in Practice](06-docker-in-practice/lesson.md) | Multi-stage builds, Compose, networking, volumes, image slimming, vulnerability scanning |
| 07 | [CI/CD Concepts & GitHub Actions](07-cicd-github-actions/lesson.md) | Design pipelines; build, test, and publish automatically with GitHub Actions |
| 08 | [Jenkins](08-jenkins/lesson.md) | Run Jenkins, write declarative pipelines, agents, credentials, shared libraries |
| 09 | [GitLab CI & Pipeline Patterns](09-gitlab-ci-patterns/lesson.md) | GitLab CI syntax, caching, environments; compare CI systems and pick patterns that transfer |
| 10 | [Artifacts, Versioning & Release Strategies](10-artifacts-releases/lesson.md) | SemVer, artifact repositories, blue-green, canary, rolling deployments, feature flags |
| 11 | [Kubernetes Fundamentals](11-kubernetes-fundamentals/lesson.md) | Pods, Deployments, Services; run and debug workloads on a local cluster |
| 12 | [Kubernetes in Practice](12-kubernetes-in-practice/lesson.md) | ConfigMaps, Secrets, Ingress, probes, resource limits, autoscaling, Helm, GitOps/Argo CD |
| 13 | [Infrastructure as Code — Terraform](13-terraform/lesson.md) | Declare infrastructure in HCL, plan/apply, state, modules — practiced against local providers |
| 14 | [Configuration Management — Ansible](14-ansible/lesson.md) | Playbooks, inventory, roles, idempotency; configure fleets of machines (containers as targets) |
| 15 | [Monitoring & Observability](15-monitoring-observability/lesson.md) | Prometheus, Grafana, Loki logs, alerting, the three pillars, USE/RED methods |
| 16 | [DevSecOps & SRE Practices](16-devsecops-sre/lesson.md) | Secrets management, supply-chain security, scanning, SLOs/error budgets, incident response |
| — | [Capstone Project](capstone/README.md) | Build a complete pipeline: code → CI → registry → Kubernetes → monitored, with IaC |

## Prerequisites

- Comfortable in at least one programming language
- Basic Git (clone, commit, push)
- Windows 11 machine with admin rights (chapter 02 sets up everything else)

## Conventions used throughout

- `$` prefix means: run in a WSL2/bash shell. `PS>` means PowerShell.
- Long commands are broken with `\` line continuations — paste them whole.
- Example app used across chapters: a small HTTP service (provided in chapter folders
  when needed) so you're always deploying *something real*.
