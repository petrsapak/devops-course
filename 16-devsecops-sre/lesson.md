# Chapter 16 — DevSecOps & SRE Practices

## Learning objectives

1. Shift security left: the scanning toolchain (secrets, SCA, SAST, containers, IaC) wired into CI.
2. Manage secrets properly: injection patterns, rotation, Vault's model.
3. Understand supply-chain security: pinning, SBOMs, image signing, least-privilege CI.
4. Apply SRE practice: SLOs and error budgets (operationalized), toil reduction, incident response, blameless post-mortems.
5. Leave with a map of what "good" looks like — and a checklist to audit any team against.

Two disciplines share this chapter because they share a stance: **security and
reliability are engineering work inside the pipeline, not gates outside it.**

---

## Part A — DevSecOps

### A1. Shift left, concretely

The cost curve: a vulnerability caught at commit time costs a code review
comment; in production it costs an incident (or a breach). DevSecOps = moving
detection to the cheap end by automating it in the pipeline you've spent
chs 07–09 building.

The scanning stack, by pipeline stage:

| Stage | Check | Tools (open-source anchors) |
|-------|-------|------------------------------|
| pre-commit / PR | **Secret scanning** — keys, tokens in diffs | gitleaks, trufflehog (+ GitHub push protection) |
| PR | **SCA** — known CVEs in your *dependencies* | trivy fs, Grype, Dependabot/Renovate, `npm audit`/`pip-audit` |
| PR | **SAST** — dangerous patterns in *your code* (SQLi, path traversal) | Semgrep, CodeQL, Bandit |
| build | **Container scan** — CVEs in the image (ch 06) | trivy image |
| build | **IaC scan** — misconfig in TF/K8s YAML (public buckets, privileged pods) | tfsec/trivy config, Checkov, kube-score |
| runtime | **DAST** — probing the running app | OWASP ZAP |
| always | **Dependency updates** — the unglamorous #1 defense | Renovate/Dependabot auto-PRs |

Realities of running this without becoming hated:

- **Gate on severity + fixability** (fail on CRITICAL with a fix available),
  not on "any finding" — day-one walls of 400 findings get scanners deleted.
- **Baseline then ratchet:** on legacy code, block *new* findings first, burn
  the backlog gradually.
- **Triage is work**: false positives suppressed *with a comment and owner*, or
  the suppression file becomes where security goes to die.
- Secret scanning is the non-negotiable one to start **today** — it's cheap,
  low-noise, and the failure it prevents (ch 03: leaked key in Git history =
  rotate, forever-compromised) is brutal. Concretely:

  ```bash
  gitleaks detect --source . -v          # scan the repo INCLUDING full git history
  ```

  > **Tool:** `gitleaks` — pattern-matches known secret shapes (AWS keys, tokens,
  > private keys — a battle-tested version of your ch 03 hook's regex) across the
  > working tree *and every commit ever made*. `detect` is the scan mode, `-v`
  > lists each finding with file, commit, and rule. Expect `no leaks found` — or a
  > finding report that means: **rotate that credential now** (deleting the file in
  > a new commit removes nothing — ch 03). Runs identically as a pre-commit hook
  > and as a CI job.

### A2. Secrets management

Hierarchy of maturity (you've climbed the first steps already):

1. ❌ In code/repo — never (ch 03).
2. ⚠️ CI secret stores + K8s Secrets (chs 07/12) — fine to start; static,
   manual rotation, sprawl as you grow.
3. ✅ **Central secret manager** — Vault / cloud secret managers:
   - Single audited source; apps fetch at runtime (or via operator sync —
     External Secrets Operator pulls into K8s Secrets).
   - **Dynamic secrets** — Vault's signature move: an app asks for DB access,
     Vault *creates* short-lived credentials (TTL 1h) on the fly. Leaked cred
     is stale in minutes; every credential is per-consumer and audited.
   - **Rotation** without redeploys; revocation as an operation, not a crisis.

Whatever the store, the *injection pattern* is the same (12-factor): the app
reads config/secrets from its environment or mounted files; **the platform,
never the codebase, supplies them** — one image, any environment (ch 01's rule,
final form).

Also in this bucket: **mTLS between services** (both sides authenticate;
service meshes like Istio/Linkerd automate cert issuance/rotation) — mentioned
so you can name the mechanism securing the "unencrypted internal hop" tradeoff
from ch 04's TLS termination.

### A3. Supply-chain security

You ship your dependencies. Attacks increasingly enter through them:
typosquatted packages, hijacked maintainers, compromised build systems, mutable
tags swapped from under you.

The defense kit (most of it is discipline you already learned, now with teeth):

- **Pin everything**: base images by digest for prod builds (ch 05), lockfiles
  committed (`package-lock.json`, `poetry.lock`), CI actions pinned — for real
  rigor, to commit SHAs (`actions/checkout@<sha>` — ch 07's note, now justified:
  a hijacked `v4` tag can't reach you).
- **SBOM** (Software Bill of Materials) — a manifest of every component in your
  artifact. Generating one is a single command with tools you already run:

  ```bash
  trivy image --format cyclonedx --output sbom.json myapp:1.0.0
  # or with syft (Anchore's dedicated SBOM tool):
  syft myapp:1.0.0 -o cyclonedx-json > sbom.json
  ```

  > **What you get:** a JSON inventory — every OS package, language dependency, and
  > version inside the image, in **CycloneDX** format (SPDX is the other standard;
  > both are machine-readable). Attach it to the release, and when the next
  > Log4Shell drops, "are we affected, where?" is `jq`/`grep` over stored SBOMs
  > instead of a two-week archaeology dig. Increasingly demanded by regulation and
  > enterprise customers.
- **Sign and verify images**: cryptographic proof of provenance.

  ```bash
  cosign sign --key cosign.key registry/app:2.4.1      # CI signs after push
  cosign verify --key cosign.pub registry/app:2.4.1    # deploy side verifies
  ```

  > **Tool:** `cosign` (from the Sigstore project) — signs the image's *digest* and
  > stores the signature in the registry next to the image. `verify` fails loudly if
  > the image was re-pushed/tampered with or was never signed by your key. In real
  > setups CI uses "keyless" signing (an OIDC identity instead of a key file), and a
  > cluster admission policy rejects unsigned images — making "only images from our
  > pipeline run in prod" mechanical. (SLSA is the maturity framework for this area.)
- **Least-privilege CI**: per-job minimal tokens (ch 07's `permissions:`),
  no long-lived cloud keys in CI (OIDC federation instead), fork PRs get no
  secrets (ch 07 — now you know why it matters this much).
- **Registry hygiene**: private proxy/mirror with policy (ch 10's Nexus role).

### A4. Runtime and platform hardening (the checklist form)

Everything from earlier chapters, assembled as an audit list:

- Containers: non-root, read-only FS, no docker.sock mounts, minimal base,
  resource limits (chs 05–06).
- K8s: `securityContext` (runAsNonRoot, no privilege escalation), NetworkPolicies
  (default-deny east-west; the ch 06 two-networks idea, cluster-grade), RBAC
  least privilege, secrets encrypted at rest (ch 12).
- Network: TLS everywhere user-facing, cert automation + expiry monitoring
  (chs 04, 12, 15).
- Access: SSH keys not passwords (ch 02), MFA on the forges and clouds, humans
  don't share service accounts.

---

## Part B — SRE

SRE (Site Reliability Engineering, Google's school of ops) supplies the
*quantitative* layer DevOps culture lacks. Four pillars for practical use:

### B1. SLOs and error budgets, operationalized

Ch 15 defined SLI/SLO/budget. The operational contract that makes them real:

- SLOs are **chosen with product** (users' tolerance, not engineers' pride —
  99.9% vs 99.99% is a 10× cost difference).
- Budget healthy → ship fast, take risks, spend it deliberately.
- Budget exhausted → **the pre-agreed policy activates**: risky deploys pause,
  reliability work jumps the queue. Pre-agreed is the key word — you negotiate
  the policy in peacetime, not during the outage.
- 100% is not a target: the last nine costs more than users can perceive, and a
  zero-risk posture blocks all change (ch 01's inversion, quantified).

The alerting mechanics (ch 15's toolbox aimed at the budget): alert on **burn
rate** — the multiple of the budget-spend rate at which you're currently
consuming the month:

```promql
# page: error ratio is 14.4× the SLO budget rate
# (at 14.4×, a 30-day budget is gone in ~2 days — worth waking someone)
(
  sum(rate(app_requests_total{status=~"5.."}[1h]))
    / sum(rate(app_requests_total[1h]))
) > 14.4 * 0.001
```

> **The arithmetic:** an SLO of 99.9% means the budget is a 0.1% (= 0.001) error ratio sustained over the whole window. Burn rate = observed ratio ÷ budget ratio: burning at exactly 1× spends the budget in exactly 30 days (fine — that's what it's for); 14.4× spends it in 2 days (page now); a steady 1–2× measured over days is a slow leak — ticket, not page. Production setups pair two windows (a fast ~1h check for pages, a slow 6h/3d check for tickets) — the "multi-window, multi-burn-rate" pattern from Google's SRE Workbook, the canonical reference for this.

### B2. Toil — the budget for automation

**Toil** = manual, repetitive, automatable, scales-with-load operational work
(cert renewals by hand, deploy babysitting, account provisioning tickets).
SRE practice: measure it, cap it (Google: <50% of SRE time), and treat every
recurring toil item as an automation backlog entry. Your whole course has been
a toil-elimination toolkit: pipelines (deploys), IaC (environments), GitOps
(sync), auto-renewal (certs), auto-scaling (capacity).

### B3. Incident response — roles and mechanics

When the pager fires (ch 15's alert), the difference between 20-minute and
4-hour incidents is usually *process*, not skill:

- **Roles**: Incident Commander (coordinates, decides, communicates — does NOT
  debug), responders (debug), comms (stakeholder updates). Sized to the
  incident: a solo responder wears all hats knowingly.
- **Severity levels** (SEV1 = users down, all hands; SEV3 = degraded, business
  hours) with pre-defined response expectations.
- **Runbooks** per alert (ch 15's `runbook_url`): symptoms → checks → mitigations.
  Written in peacetime, tested in game days.
- **Mitigate first, diagnose later**: rollback / flag off / failover *now*
  (ch 10's decision tree); root cause is for tomorrow's daylight. Restore
  service, preserve evidence (grab logs/state before restarting things when you
  can afford to).
- Practice: **game days / chaos drills** — inject failures on purpose (you did
  a baby version in exercise 15.8). Netflix's Chaos Monkey is this
  institutionalized.

### B4. Blameless post-mortems — the learning loop

After every significant incident (ch 01 planted this; here's the full practice):

Structure: timeline (detection → mitigation → resolution) → impact
(users, duration, SLO budget burned) → contributing causes (plural! "root
cause" is usually several factors aligning) → what went well / what didn't →
**action items with owners and deadlines, tracked like real work**.

Blameless mechanics: name systems and gaps, not people ("the deploy pipeline
allowed an unreviewed config change" not "Petr skipped review"). The test of
sincerity: people volunteer their own mistakes in the doc. The test of value:
action items actually ship (a post-mortem whose actions rot is theater).

The full loop this course has built:
**alert (15) → mitigate via rollback/flag (10) → post-mortem (16) → action
items → pipeline/IaC fixes (07–14) → the same failure can't recur (01).**
That loop *is* DevOps.

---

## The "what good looks like" audit checklist

Score any team (or interview any employer) against this:

- [ ] Trunk-based-ish Git, protected main, PRs with CI gates (03, 07)
- [ ] CI: <10 min to green, tests + lint + secret scan + SCA + image scan (07–09, 16)
- [ ] Artifacts: immutable, versioned, built once, promoted (05, 10)
- [ ] Deploys: automated, zero-downtime, one-command rollback, flags for risk (10, 12)
- [ ] Infra: IaC in Git, plan-reviewed, no snowflakes; config management for the rest (13, 14)
- [ ] K8s (if used): probes, limits, GitOps sync (11, 12)
- [ ] Observability: RED dashboards, symptom-based SLO alerts, structured logs, runbooks (15)
- [ ] Secrets: central store, rotation, nothing in Git (16)
- [ ] Supply chain: pinned deps, auto-update PRs, SBOMs (16)
- [ ] Culture: blameless post-mortems with shipped actions; error budgets honored (01, 16)

## Further reading

- Google SRE book + SRE Workbook (sre.google/books — free, canonical).
- OWASP DevSecOps Guideline; SLSA.dev for supply-chain maturity.
- *Accelerate* (again — reread it now; it will land differently than in ch 01).

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| SCA | Software Composition Analysis | Scanning your dependencies for known vulnerabilities |
| SAST | Static Application Security Testing | Scanning your own source code for dangerous patterns |
| DAST | Dynamic Application Security Testing | Probing the *running* app for vulnerabilities |
| OWASP | Open Web Application Security Project | Nonprofit behind widely-used security guides and checklists |
| OIDC | OpenID Connect | Identity-federation protocol letting CI mint short-lived cloud credentials without stored keys |
| SLSA | Supply-chain Levels for Software Artifacts | Maturity framework for supply-chain security practices |
| SBOM | Software Bill of Materials | A manifest of every component inside a built artifact |
| SPDX | Software Package Data Exchange | One of the two standard machine-readable SBOM formats (with CycloneDX) |
| CVE | Common Vulnerabilities and Exposures | Public ID for a known security vulnerability |
| MFA | Multi-Factor Authentication | Requiring more than a password to log in |
| TTL | Time To Live | How long a dynamic secret (or cached value) stays valid before expiring |
| SEV1 / SEV3 | Severity 1 / Severity 3 | Incident severity levels — SEV1 = users down, all hands |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Capstone](../capstone/README.md)
