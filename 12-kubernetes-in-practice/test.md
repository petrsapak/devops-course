# Chapter 12 — Test

15 questions. Passing: 12/15.

---

**Q1.** Why do ConfigMaps/Secrets exist instead of baking config into images?
Which chapter-01 rule do they implement?

**Q2.** "Kubernetes Secrets are encrypted." Correct this statement precisely and
name two real mitigations.

**Q3.** You update a ConfigMap consumed via `envFrom`. Pods show old values. Why,
and what's the standard remedy?

**Q4.** Liveness vs readiness vs startup probes — one sentence each, including
what K8s does on failure.

**Q5.** Why must a liveness probe NOT check database connectivity?

**Q6.** Explain how readiness probes are what makes rolling updates zero-downtime.

**Q7.** Requests vs limits: which one does the scheduler use, what happens on
exceeding the memory limit, and what happens on exceeding the CPU limit?

**Q8.** An HPA is configured for 70% CPU but never scales. The deployment's
containers have no `resources` block. Explain the connection.

**Q9.** What is an ingress controller, and what happens if you apply Ingress
objects without one?

**Q10.** Draw (textually) the path of a request from a browser to a pod in a
cluster using ingress: name each layer it passes.

**Q11.** PV vs PVC vs StorageClass — one line each. What does a StatefulSet add
over a Deployment for stateful workloads?

**Q12.** What does `helm template` do and why should it be in your muscle memory
before every `helm install/upgrade` of a chart you changed?

**Q13.** One chart, three environments with different replica counts, hosts, and
resource sizes — what's the Helm mechanism, and what's the Kustomize equivalent
concept?

**Q14.** In GitOps (Argo CD): (a) who applies changes to the cluster, (b) what
happens when someone `kubectl edit`s a synced resource with self-heal on,
(c) how do you roll back, (d) why does CI never need cluster credentials?

**Q15.** Design: your visits app needs staging and prod isolation, external
secrets, zero-downtime deploys, Git rollback, protection during node drains,
default-deny networking, and replica spreading. Name the K8s/toolchain feature
answering each requirement.

---

<details>
<summary><b>Answer key</b></summary>

1. So the same immutable image runs everywhere with environment-supplied
   config — "environments differ only in configuration, never in the artifact."
2. They are base64-**encoded** (an encoding, not encryption) and readable by
   anyone with API access to the namespace. Mitigations: RBAC restricting secret
   reads, etcd encryption at rest, external secret managers (Vault/ESO),
   sealed-secrets for Git.
3. Env vars are captured at container start; running processes never see
   ConfigMap changes. Remedy: `kubectl rollout restart deploy/<name>` (or mount
   as files and have the app re-read).
4. Liveness: "is the process alive?" — failure restarts the container.
   Readiness: "can it serve now?" — failure removes it from Service endpoints.
   Startup: "has it finished booting?" — suspends liveness until it passes, for
   slow starters.
5. A DB outage would fail liveness on every replica simultaneously → mass
   restart storm that fixes nothing (the DB is the problem) and adds boot load.
   Dependency health belongs in readiness, which sheds traffic instead.
6. During a roll, K8s adds new-version pods and only sends traffic (and only
   continues the wave) when they report ready; old pods keep serving until
   replacements are genuinely serving. Without readiness, traffic hits
   still-booting pods → errors during every deploy.
7. Scheduler places pods by **requests**. Memory limit exceeded → OOMKill
   (exit 137). CPU limit exceeded → throttling, no kill.
8. HPA's "70%" is measured relative to the container's CPU **request**. With no
   request set, there's no denominator — the HPA can't compute utilization and
   does nothing (shows `<unknown>`).
9. The actual proxy workload (nginx-ingress/Traefik pods) that watches Ingress
   objects and implements them. Without one, Ingress objects are inert data —
   no routing occurs.
10. Browser → DNS → LoadBalancer/host port → ingress controller (L7: host/path
    match, TLS termination) → Service (ClusterIP, L4) → endpoints → pod
    (containerPort), gated by readiness.
11. PV: an actual piece of provisioned storage. PVC: a workload's claim/request
    for storage. StorageClass: the recipe that dynamically provisions PVs for
    claims. StatefulSet: stable identities (`db-0`), per-replica PVCs, ordered
    rollout — for workloads where instances aren't interchangeable.
12. Renders the templates to final YAML locally without touching the cluster —
    you review what will actually be applied, catching template/values mistakes
    before they become cluster mistakes.
13. Per-environment values files (`-f values-prod.yaml`) overriding chart
    defaults. Kustomize: base + per-env overlays applying patches.
14. (a) The in-cluster operator (Argo CD) pulls from Git and applies. (b) Drift
    is detected and reverted to Git's state. (c) `git revert` + push — the
    operator syncs the cluster backward. (d) Pull model: nothing outside the
    cluster ever holds apply-credentials; CI only pushes images and Git commits.
15. Isolation: namespaces plus per-environment Helm values. Secrets: an
    external secret manager/operator. Zero-downtime: Deployment rolling update
    plus readiness probes. Git rollback: Argo CD syncing a reverted commit.
    Node drains: PodDisruptionBudget. Default-deny and explicit flows:
    NetworkPolicy enforced by a supporting CNI. Replica spreading: pod
    anti-affinity or topology spread constraints.

</details>

**Scoring:** 12+ → [Chapter 13](../13-terraform/lesson.md). Below → redo
exercises 12.2, 12.4, 12.8, and 12.9 — probes, HPA mechanics, GitOps, and
production guardrails are the chapter's spine.
