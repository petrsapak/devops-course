# Chapter 13 — Test

15 questions. Passing: 12/15.

---

**Q1.** Declarative IaC vs an imperative provisioning script: name three concrete
advantages the declarative model provides.

**Q2.** What are the three "inputs" Terraform reconciles when computing a plan?

**Q3.** What does each plan symbol mean: `+`, `-`, `~`, `-/+`? Which one demands
the most scrutiny before approving, and why?

**Q4.** How does Terraform know to create a network before the container that
uses it, without you writing any ordering?

**Q5.** What exactly does `terraform init` do (two main jobs)?

**Q6.** What is the state file, and what breaks if it's lost?

**Q7.** Why must `terraform.tfstate` never be committed to Git? (Two independent
reasons.)

**Q8.** What is drift, how does Terraform detect it, and what does `apply` do to it?

**Q9.** What two problems do remote backends solve for teams, and what disaster
does state *locking* specifically prevent?

**Q10.** You have 30 hand-created cloud resources predating Terraform. Which
command brings one under management, and what must you write first?

**Q11.** `terraform state rm docker_container.web` — what does this do to (a) the
state, (b) the actual container, (c) the next plan?

**Q12.** What is a module? Explain the inputs/outputs analogy and one benefit of
per-environment root directories with separate state.

**Q13.** In the CI pattern, why is `terraform plan -out=tf.plan` +
`terraform apply tf.plan` used instead of a plain `apply` after merge?

**Q14.** A teammate's plan for a "small change" to a production database resource
shows `1 to destroy, 1 to add`. What happened, why is it dangerous, and name two
ways to proceed safely.

**Q15.** Position the tools: when would you pick Terraform vs Ansible vs Pulumi
vs CloudFormation? One line each.

---

<details>
<summary><b>Answer key</b></summary>

1. Idempotency for free (re-run = no-op); the tool computes minimal diffs
   (scripts re-run everything or need hand-written checks); dependency ordering
   from the reference graph; drift detection; uniform workflow across providers;
   plans as reviewable previews. (Any three.)
2. Configuration (desired state), state file (what Terraform believes it
   manages), and refreshed reality (actual resource attributes from provider APIs).
3. `+` create, `-` destroy, `~` in-place update, `-/+` destroy-and-recreate
   (replacement). `-/+` deserves scrutiny: for stateful/production resources,
   recreation means downtime and possible data loss hidden behind an innocent
   attribute change.
4. Attribute references (`docker_network.app.name` inside the container
   resource) form a dependency graph; Terraform orders operations by that graph
   (and reverses it for destroy).
5. Downloads/installs the required provider plugins (per version constraints,
   recording them in the lock file) and configures the backend where state lives.
6. The mapping from config resource names to real-world resource IDs plus their
   last-known attributes. Lost state → Terraform no longer knows it owns the
   resources: plans propose creating everything anew while the originals still
   run — duplicates, conflicts, manual import/cleanup.
7. It can contain secrets in plaintext (resource attributes like DB passwords),
   and Git is the wrong concurrency/consistency mechanism for it (merge
   conflicts on state are unresolvable; teams need locking, not merging).
8. Reality changed outside Terraform (console/CLI edits). Detected during
   plan's refresh: state/config vs actual attributes differ. Apply converges
   reality back to the configuration (reverting the manual change).
9. Shared access to one authoritative state (collaboration) and durability/
   access control (not on someone's laptop). Locking prevents two concurrent
   applies from interleaving writes and corrupting state.
10. `terraform import <address> <real-id>` — and you must first write the
    matching `resource` block in config (import populates state, not config).
11. (a) Removes the resource's entry from state. (b) Nothing — it keeps running,
    now unmanaged. (c) Plan proposes creating it (config says it should exist,
    state no longer knows it does).
12. A reusable directory of Terraform config with declared input variables and
    outputs — a function for infrastructure. Per-env roots with separate state
    isolate blast radius: an apply (or a mistake) in dev physically cannot
    modify prod's resources.
13. The saved plan guarantees you execute exactly the reviewed change set; if
    reality moved between plan and apply, applying the stale plan fails safely
    instead of silently doing something different from what was approved.
14. The attribute change forces replacement (`-/+`) — the DB would be destroyed
    and recreated: outage + data loss. Options: don't apply — find an
    in-place path (some changes have provider-supported migration),
    use `lifecycle { prevent_destroy = true }` as a guardrail, perform a
    blue-green data migration, or explicitly accept and schedule the recreation
    with backups. (Any two.)
15. Terraform: default for multi-cloud declarative provisioning. Ansible:
    configuring what's *inside* machines (packages, files, services) and
    procedural ops. Pulumi: Terraform's model with general-purpose languages —
    teams that want real code. CloudFormation: AWS-only shops committed to
    native tooling.

</details>

**Scoring:** 12+ → [Chapter 14](../14-ansible/lesson.md). Below → redo exercises
13.2, 13.3, 13.6 — plan-reading, drift, and state surgery are the skills that
separate "used Terraform" from "trusted with prod Terraform".
