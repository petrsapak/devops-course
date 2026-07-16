# Capstone Project — The Full Loop

Everything from chapters 01–16, integrated into one system you build, break,
and operate. Budget 15–25 hours. This is the portfolio piece: a public repo
demonstrating this capstone is a stronger interview asset than any certificate.

## The mission

Build, deploy, and operate a small two-service application with a complete
DevOps platform around it — entirely on your machine (plus free GitHub).

### The application (kept deliberately simple — the app is not the point)

- **api** — the visits service you've evolved since ch 05 (Flask + Postgres),
  with `/health`, `/ready`, `/metrics`, structured JSON logs, and one feature
  behind a flag (`FEATURE_STATS` → a `/stats` endpoint).
- **worker** — a tiny second service (e.g., increments a "reports generated"
  counter every 30 s, exposing its own `/metrics`) — exists so you have
  service-to-service networking and two deployables.

## Requirements — the checklist

### 1. Repositories & Git (ch 03)
- [ ] `capstone-app` repo: source, Dockerfiles, CI. Protected `main`, PRs only,
      conventional commits.
- [ ] `capstone-gitops` repo: Helm chart(s) / manifests, per-env values
      (`staging`, `prod` = two namespaces).

### 2. CI pipeline (chs 07, 16) — GitHub Actions
- [ ] PR: lint + unit tests + secret scan (gitleaks) + SCA (pip-audit) — all
      required checks.
- [ ] Main: build both images (multi-stage, non-root, pinned bases) → trivy
      image scan (gate: HIGH+) → push to ghcr.io tagged `sha-<commit>` →
      generate & upload SBOMs.
- [ ] Tag `v*`: same + semver image tags.
- [ ] CI updates the **gitops repo** (bumps the staging image tag via PR or
      direct commit — your call, justify it in the README).

### 3. Deployment (chs 11, 12) — local cluster
- [ ] Helm chart per service (or one umbrella chart): Deployment (probes,
      resources, securityContext), Service, Ingress (`visits.local`),
      ConfigMap, Secret.
- [ ] Argo CD watching the gitops repo: staging auto-sync + self-heal; prod
      syncs only on manual approval (or from a `prod` values change via PR —
      document your promotion flow).
- [ ] Postgres via PVC (or documented decision to run it in compose alongside —
      defend whichever you choose).
- [ ] HPA on the api (works under your load test).

### 4. Infrastructure as code (chs 13, 14)
- [ ] Terraform manages the *platform*: at minimum the local registry mirror or
      lab containers/networks that live outside the cluster, AND the GitHub
      side — both repos, branch protection, required checks — via the github
      provider. (`terraform plan` clean at submission.)
- [ ] One Ansible playbook with a real job: e.g., configure a "build agent"
      container (docker + tooling) or the lab-node fleet health check —
      idempotent, `--check` clean, one role, vault-encrypted var somewhere.

### 5. Observability (ch 15)
- [ ] Prometheus scraping both services + the cluster (kube-prometheus-stack
      is the sanctioned shortcut — installing it via Helm *is* the exercise).
- [ ] One Grafana dashboard per service: RED top row, resources below, deploy
      annotations (bonus: CI posts them).
- [ ] Loki + promtail; JSON logs queryable.
- [ ] Alerts: HighErrorRate (page) + TargetDown (warn) routed through
      Alertmanager; every alert has a runbook in the repo (`runbooks/`).
- [ ] A written SLO (availability + latency) with PromQL SLIs and a budget
      policy (ch 16 ex 16.7 — reuse and refine it).

### 6. The operational proof (the part that makes it real)
Run and document, with screenshots/logs in `docs/`:

- [ ] **A feature release**: branch → PR (CI green) → merge → image → gitops
      bump → Argo syncs staging → promote to prod. Trace one commit SHA
      end-to-end and show it in `docs/release-walkthrough.md`.
- [ ] **A rollback**: break something on purpose (bad image that fails
      readiness, or an error-throwing route) → deploy to staging → detect on
      the dashboard → roll back via `git revert` in the gitops repo. Timeline
      in docs.
- [ ] **A flag kill-switch**: enable `FEATURE_STATS` in prod values, then kill
      it via config-only change. Measure the time from decision to effect.
- [ ] **A game day**: one injected failure (DB down / pod OOM / dead promtail),
      full incident response, and a blameless post-mortem in
      `docs/postmortem-001.md` with at least one shipped action item.

### 7. The README (ch 01, full circle)
- [ ] Architecture diagram (mermaid), the pipeline flow, how to run everything
      from zero (`terraform apply` → `helm`/Argo bootstrap → done), and a
      **decisions section**: 5+ deliberate tradeoffs you made and why (e.g.,
      "compose Postgres over StatefulSet because...", "direct commit vs PR for
      staging bumps because..."). The decisions section is what interviewers read.

## Suggested build order

1. App + Dockerfiles + compose dev environment (½ day — mostly reuse).
2. CI to green with all gates (1 day).
3. Helm + cluster + Argo staging loop (1–2 days).
4. Observability stack + dashboards + alerts (1 day).
5. Terraform + Ansible pieces (1 day).
6. Prod promotion flow + SLO doc (½ day).
7. The four operational proofs (1 day — the fun one).
8. README + docs polish (½ day; don't skip — this is the deliverable).

## Grading yourself

| Level | Bar |
|-------|-----|
| **Pass** | Sections 1–3 + 5 work; release walkthrough documented |
| **Strong** | Everything above + 4 + rollback & flag proofs + SLO doc |
| **Portfolio** | All checkboxes; post-mortem reads like you've done this for years; README decisions section would survive a senior engineer's questioning |

## After the capstone

- Put the repo public; write a short post walking through your architecture.
- Gaps this course deliberately left for your next steps: a real cloud
  (take the AWS/Azure/GCP flavor of chs 11–13 — concepts transfer 1:1),
  service mesh & mTLS, distributed tracing hands-on (add OpenTelemetry to the
  two services — you already have the trace_id fields waiting), Kubernetes
  operators, platform engineering (Backstage), and the CKA/CKAD certification
  if credentials matter in your market.

Good luck — and remember ch 01: small batches. Ship the capstone incrementally,
on a pipeline, like you now know how.
