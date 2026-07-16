# Chapter 16 — Test

15 questions. Passing: 12/15.

---

**Q1.** "Shift left" in security terms: what moves, where, and why does the cost
argument work?

**Q2.** Match each scanner class to what it examines: SAST, SCA, secret
scanning, container scanning, IaC scanning, DAST.

**Q3.** Why does "fail the build on ANY finding" backfire on a legacy codebase,
and what's the workable policy?

**Q4.** A real API key was committed and pushed 20 minutes ago. Order these and
strike the wrong one: (a) rewrite history, (b) rotate the key, (c) add the file
to .gitignore, (d) audit usage logs for abuse.

**Q5.** What are dynamic secrets (Vault), and why do they change the severity of
a credential leak?

**Q6.** Name the injection pattern: where do secrets enter the application, and
who supplies them? Which chapter-01 rule is this the final form of?

**Q7.** Why pin a CI action to a commit SHA rather than a version tag, and what
attack does it neutralize?

**Q8.** What is an SBOM, and what question does it turn from a two-week hunt
into a query? When is it generated?

**Q9.** What does image signing (cosign) prove, and where is the verification
enforced in a Kubernetes shop?

**Q10.** Define toil (three qualifying properties) and give the SRE stance on it.

**Q11.** Why is 100% availability the wrong target? Use the error-budget frame.

**Q12.** During a SEV1, what is the Incident Commander explicitly NOT supposed
to do, and why does the role exist?

**Q13.** "Mitigate first, diagnose later" — what are the three standard
mitigations (ch 10) and what should you try to preserve while mitigating?

**Q14.** Give three properties of a *blameless* post-mortem, and the two tests
(from the lesson) of whether the practice is real or theater.

**Q15.** Synthesis: a deploy at 14:02 causes checkout errors; paged at 14:09;
rolled back at 14:15; all clear 14:18. Walk the full course loop: name what
detected it (ch), what mitigated it (ch), what documents it (ch), and TWO
pipeline-level action items with the chapter whose tooling implements each.

---

<details>
<summary><b>Answer key</b></summary>

1. Security checks move from a pre-release audit (or post-breach discovery) into
   the developer's inner loop — pre-commit hooks, PR checks, build gates.
   Defects cost roughly orders of magnitude less at each earlier stage: a code
   review comment vs a production incident vs a breach.
2. SAST → your source code's patterns. SCA → known CVEs in your dependencies.
   Secret scanning → credentials in code/diffs/history. Container scanning →
   CVEs in image packages/layers. IaC scanning → misconfigurations in
   Terraform/K8s manifests. DAST → the running application's behavior.
3. Day one produces hundreds of findings; blocking everything halts delivery,
   so teams disable the scanner — net security negative. Policy: gate on
   severity + fixability (e.g., CRITICAL with fix available), baseline existing
   findings, block only *new* ones, ratchet the baseline down over time.
4. **b** (rotate immediately) → **d** (audit for abuse during exposure) → then
   optionally (a) history rewrite + prevention (hooks/push protection).
   Strike **(c)** — gitignore does nothing about a secret already in history;
   the key is compromised regardless.
5. Credentials created on demand, per consumer, with short TTLs, by the secret
   manager (e.g., Vault creating a 1-hour Postgres user). A leak is
   self-expiring and per-consumer auditable — "leaked credential" degrades from
   crisis to inconvenience.
6. Via environment variables or mounted files at runtime, supplied by the
   platform (CI secret store, K8s + external secrets, Vault) — never by the
   codebase or image. Final form of "same artifact everywhere; environments
   differ only in configuration."
7. Tags are mutable pointers: a compromised action repo can re-point `v4` at
   malicious code and every consumer runs it on the next build. A SHA is
   immutable content — the hijacked-tag supply-chain attack can't reach you.
8. A machine-readable inventory of every component (with versions) inside an
   artifact. Turns "are we affected by CVE-X in package Y?" into a query across
   stored SBOMs. Generated at build time in CI and stored alongside the artifact.
9. Provenance and integrity: this exact image (digest) was produced and signed
   by our pipeline's key and hasn't been altered. Enforced by cluster admission
   control (policy engine rejecting unsigned/unverified images).
10. Manual, repetitive, automatable work that scales with service growth and
    carries no enduring value (deploy babysitting, hand cert renewals, ticket
    provisioning). Stance: measure it, cap it (<50%), continuously convert it
    into automation — toil is the automation backlog.
11. The marginal nine costs exponentially more while users can't perceive it
    past their own noise floor (their wifi fails more than your 99.99%). And a
    100% target means zero error budget — no releases, no experiments, no
    change. Reliability is a feature with a cost curve; budget the failure
    deliberately.
12. Debug. The IC coordinates: assigns responders, makes the
    mitigate-vs-investigate calls, owns communication. The role exists because
    incidents fail on coordination — five engineers debugging in parallel with
    nobody deciding is how 20-minute incidents become 4-hour ones.
13. Rollback to previous artifact; feature-flag kill switch; failover to
    healthy capacity/region. Preserve evidence where affordable: logs, metrics
    snapshots, a sick instance kept out of rotation for autopsy instead of
    restarted.
14. Names systems/process gaps, not people; assumes people acted reasonably on
    the information they had; contributing causes (plural) over a single "root
    cause" + human error. Tests: people volunteer their own mistakes in the
    doc; action items actually ship (tracked with owners/deadlines).
15. Detected by symptom-based alerting on error ratio (ch 15). Mitigated by
    one-command rollback of the immutable previous artifact (ch 10, executed by
    ch 11–12's platform). Documented by a blameless post-mortem with SLO budget
    burn quantified (ch 16 + 15). Action items, e.g.: canary/progressive
    delivery so the next bad deploy hits 5% of traffic (ch 10 tooling);
    a pipeline gate — smoke test or checkout-flow integration test — that
    catches this failure class pre-prod (chs 07–09); deploy annotations on
    dashboards if the 14:02↔14:09 correlation was slow to spot (ch 15). (Any two.)

</details>

**Scoring:** 12+ → you've completed all 16 chapters. Go build the
[Capstone](../capstone/README.md) — it's where the course becomes a portfolio.
