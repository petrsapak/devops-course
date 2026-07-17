# Chapter 10 — Artifacts, Versioning & Release Strategies

## Learning objectives

1. Apply semantic versioning correctly and automate it from commit history.
2. Explain artifact repositories (registry types, immutability, retention, promotion).
3. Choose and implement deployment strategies: rolling, blue-green, canary.
4. Use feature flags to decouple *deploy* from *release*.
5. Design rollback that actually works at 3 a.m.

---

## 1. Versioning

### 1.1 Semantic Versioning (SemVer)

`MAJOR.MINOR.PATCH` — e.g. `2.4.1`:

- **MAJOR** — breaking changes: consumers must act (`2.x` → `3.0.0`).
- **MINOR** — new functionality, backward compatible.
- **PATCH** — bug fixes only.

Extras: pre-releases `2.5.0-rc.1` (ordered before `2.5.0`), build metadata
`2.4.1+sha.f2a1c3d` (ignored for ordering).

SemVer is a **communication contract**, not decoration: a consumer pinning
`^2.4.0` (any 2.x ≥ 2.4) is trusting you never to break them in a MINOR. Breaking
someone in a PATCH is the cardinal sin of release engineering.

### 1.2 What gets a version, and from where

Two healthy patterns (often combined, as in ch 07):

- **Every main-branch build**: `sha-f2a1c3d` — unambiguous traceability.
- **Releases**: `v2.4.1` git tag → pipeline builds/promotes the artifact with
  that version. The tag is the *source of truth*; nobody types versions into
  build boxes.

**Automated versioning** via Conventional Commits (ch 03): tools
(semantic-release, release-please) scan commits since the last release —
`fix:` → patch bump, `feat:` → minor, `feat!:`/`BREAKING CHANGE:` → major — then
tag, generate the changelog, and publish. Version arithmetic stops being a
meeting.

### 1.3 The iron rule: released versions are immutable

Never republish different bytes under the same version ("mutable tag" sin, ch 05).
If `2.4.1` is broken, ship `2.4.2`. Registries can enforce this (tag immutability);
turn it on where offered.

## 2. Artifact repositories

The registry is the **handoff point**: CI writes, deployment reads, nothing else
crosses that boundary (no scp-ing binaries, no building on prod).

| Artifact type | Format examples | Repositories |
|---------------|----------------|--------------|
| Container images | OCI/Docker | Docker Hub, ghcr.io, GitLab Registry, Harbor, ECR/ACR/GAR |
| Language packages | npm, PyPI wheels, Maven JARs, NuGet | npmjs, PyPI, Maven Central + private mirrors |
| OS packages | deb, rpm | apt/yum repos |
| Universal/binary | zips, installers | Nexus, Artifactory, GitHub Releases |

**Nexus / Artifactory / Harbor** are the self-hosted, multi-format workhorses in
enterprises. Beyond storage they provide:

- **Proxy/mirror** of public registries — builds survive npm/PyPI outages, and
  you get a choke point to enforce policy (block known-bad packages: supply-chain
  defense, ch 16).
- **Retention rules** — `sha-*` dev tags cleaned after N days; releases kept forever.
- **Promotion model** — see below.

### Promotion, spelled out

"Build once, promote the artifact" mechanically:

```
build → push  registry/app:sha-f2a1c3d        (CI, automatic)
staging deploys sha-f2a1c3d                    (automatic)
tests pass, human approves prod                (gate)
retag: sha-f2a1c3d  →  also 2.4.1, prod-current   (promotion = adding a pointer)
prod deploys 2.4.1                             (same bytes staging ran)
```

In Docker commands (ch 05's tools, doing release engineering), the promotion step is just:

```bash
docker pull registry/app:sha-f2a1c3d          # the exact bytes staging validated
docker tag  registry/app:sha-f2a1c3d registry/app:2.4.1
docker push registry/app:2.4.1                # instant: layers already exist, only the new tag uploads
```

> **Why this is the whole trick:** `docker tag` creates a new *name* for the same image ID — no rebuild, no new bytes. Registries with a retag API (Harbor, most cloud ones) do it server-side without even the pull. Compare the anti-pattern: `docker build -t app:2.4.1 .` at release time rebuilds from source — different timestamp, possibly different dependency versions — and ships bytes nothing ever tested.

Promotion adds *labels* to existing bytes — never rebuilds. Some shops use
separate repos (`dev-images/` → `prod-images/`) with a copy step; same principle.

## 3. Deployment strategies

The problem: replace version A with version B on N instances without dropping
traffic — and with an escape hatch. All strategies assume the LB/health-check
machinery of ch 04.

### 3.1 Recreate (the baseline to avoid)

Stop A everywhere → start B. Simple; guaranteed downtime. Acceptable only for
dev environments and apps whose users tolerate windows.

### 3.2 Rolling update

Replace instances one (or a few) at a time; the LB routes only to healthy ones.

```
[A][A][A][A] → [B][A][A][A] → [B][B][A][A] → ... → [B][B][B][B]
```

- ✅ No downtime, no extra capacity needed, the default (and Kubernetes' default, ch 12).
- ⚠️ A and B **coexist** during the roll — B must be compatible with A's world:
  same DB schema expectations, compatible APIs, sessions survivable. This
  constraint surprises every team once.
- Rollback = roll the other way (minutes, not instant).

### 3.3 Blue-green

Two identical environments. Blue serves prod; deploy B to green; test green
*in production conditions*; then **switch the router** — one atomic cutover.

- ✅ Instant cutover, instant rollback (switch back), full pre-switch validation.
- ⚠️ 2× capacity cost; databases are shared — schema still must serve both
  (see §5); long-lived connections need draining at switch.

### 3.4 Canary

Route a small slice (1–5%) of real traffic to B; compare error rates/latency
against A (the "control"); ramp 5→25→50→100% while metrics stay clean; abort and
route back at the first regression.

- ✅ Smallest possible blast radius; verdicts from *real* traffic; pairs
  perfectly with monitoring (ch 15) — and can be fully automated
  ("progressive delivery": Argo Rollouts, Flagger).
- ⚠️ Needs solid metrics to judge; needs enough traffic for statistics; same
  coexistence constraint as rolling.

### Choosing

| Constraint | Choice |
|-----------|--------|
| Default web service, cost-sensitive | rolling |
| Compliance demands pre-prod validation of the exact prod deployment + instant rollback | blue-green |
| High traffic, mature monitoring, fear of regressions | canary |
| Batch/cron worker, brief downtime harmless | recreate is honest |

## 4. Feature flags — deploy ≠ release

**Deploy** = the code is on the servers. **Release** = users experience it.
Feature flags split these:

```python
if flags.is_enabled("new-search", user):
    return new_search(query, user)
return old_search(query)
```

What this buys, operationally:

- **Trunk-based development** (ch 03): merge incomplete features *dark*.
- **Instant kill switch**: feature misbehaves in prod → flip off in seconds — no
  deployment, no rollback. Often the fastest MTTR tool in the box.
- **Percentage rollouts / targeting**: 5% of users, employees only, region by
  region — a canary at the *feature* level instead of the instance level.
- **A/B experiments**: same mechanism, product-analytics purpose.

Tooling: LaunchDarkly/Unleash/Flagsmith (managed/self-hosted), or a config-table
DIY for small needs. The costs to manage: every flag doubles the state space —
test both paths; flags are **temporary** — removing them after full rollout is
real work that must be scheduled (flag debt); a flag *service* outage needs safe
defaults in code.

## 5. The database problem (why "just roll back" is naive)

Code rolls back in seconds; **schemas don't**. During rolling/blue-green/canary,
old and new code hit the same DB simultaneously — and a code rollback after a
destructive migration is catastrophic.

The discipline: **expand–migrate–contract** — every schema change split into
backward-compatible steps:

Renaming column `username` → `handle`:

1. **Expand** (release 1): add `handle` column; code writes both, reads `handle`
   with fallback to `username`. Old code still works — rollback safe.
2. **Migrate**: backfill data; verify.
3. **Contract** (release N, later): once no deployed code touches `username`,
   drop it.

Rules that follow: never `DROP`/`RENAME`/`NOT NULL`-ify in the same release as
the code that needs it; migrations run *before* code deploys and must be
backward compatible with the still-running version; test rollback against the
migrated schema. Slower? Yes. It's the price of zero-downtime deployment, paid
by every team that has one.

## 6. Rollback engineering

Rollback is a **capability you build and rehearse**, not a hope:

1. **Previous artifact always available** — versioned, in the registry
   (retention rules must keep the last N releases!).
2. **One command / one click** — `deploy 2.4.0` must be exactly as automated as
   `deploy 2.4.1`. If rollback needs a wiki page, MTTR is measured in wiki-reading.
3. **Schema-compatible** — guaranteed by §5's discipline.
4. **Rehearsed** — roll back in staging routinely; an unpracticed rollback fails
   precisely when you're panicking.
5. **Know the alternatives**: fix-forward (when rollback is unsafe), feature-flag
   kill switch (when the regression is flag-scoped — fastest of all).

Decision heuristic at incident time: flag off if flagged → roll back if the last
deploy is suspect and schema-safe → fix forward otherwise.

## 7. Release notes & changelogs

Consumers (users, other teams, future-you-at-an-incident) need to know what
changed. Automate it: Conventional Commits → generated changelog per release
(semantic-release/release-please), attached to the git tag / GitHub Release.
Hand-curate only the headline ("what should a human care about").

## Further reading

- semver.org — the spec, short and worth reading verbatim.
- *Release It!* (Nygard) — deployment patterns and production failure modes.
- martinfowler.com: "BlueGreenDeployment", "CanaryRelease", "Feature Toggles".

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 11: Kubernetes Fundamentals](../11-kubernetes-fundamentals/lesson.md)
