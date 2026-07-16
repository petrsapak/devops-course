# Chapter 11 — Test

15 questions. Passing: 12/15.

---

**Q1.** Explain Kubernetes' declarative reconciliation model and contrast it with
an imperative deploy script.

**Q2.** Which component does every `kubectl` command (and every controller) talk
to, and where does cluster state persist?

**Q3.** What is a Pod, precisely — and why is "container" the wrong answer?

**Q4.** Why should you (almost) never create bare Pods in production?

**Q5.** Name the three-object chain a Deployment manages and what each layer adds.

**Q6.** In a Deployment spec, what is the relationship between
`spec.selector.matchLabels` and `spec.template.metadata.labels`, and what happens
if they don't match?

**Q7.** Pods are recreated with new IPs constantly. What two stable things does a
Service provide, and how does it decide which pods receive traffic?

**Q8.** `port` vs `targetPort` in a Service spec — which is which?

**Q9.** ClusterIP vs NodePort vs LoadBalancer — one sentence each.

**Q10.** A pod shows `CrashLoopBackOff`. What is happening, and what is the
single most useful command (be exact) to see *why*?

**Q11.** A pod is `Pending` for 10 minutes. Where do you look and what are the
two most common causes?

**Q12.** `curl http://orders-svc` from inside the cluster times out. Pods with
`app: orders` are Running. Give the one command that most quickly distinguishes
"selector mismatch" from other causes, and the two states it disambiguates.

**Q13.** What does `kubectl rollout undo deploy/visits` do, and which chapter-10
strategy does a Deployment implement by default?

**Q14.** What do namespaces provide, and what's the DNS difference between
reaching a service in your own vs. another namespace?

**Q15.** Practical: write the complete YAML for a Deployment `web` (2 replicas,
image `nginx:1.27`, container port 80) plus a ClusterIP Service `web-svc`
exposing it on port 80. (From memory — this is the muscle-memory check.)

---

<details>
<summary><b>Answer key</b></summary>

1. You declare desired state (objects in the API); controllers continuously
   observe actual state and act to converge it. A script runs once and stops —
   nothing re-runs it when a node dies at 3 a.m.; reconciliation reacts to any
   divergence, whenever it occurs.
2. The API server; state lives in etcd.
3. The smallest deployable unit: one or more containers sharing network
   namespace (one IP, localhost between them) and lifecycle. "Container" is
   wrong because sidecars share the pod and the pod, not the container, is what
   gets scheduled.
4. No controller owns them: a bare pod isn't rescheduled when its node fails,
   can't scale, and has no rolling-update mechanism.
5. Deployment → ReplicaSet → Pods. ReplicaSet: keeps N replicas alive.
   Deployment: manages ReplicaSets across versions — rolling updates, history,
   rollback.
6. The selector must match the template's labels — that's how the Deployment
   finds its pods. Mismatch is rejected at apply time (for apps/v1) precisely
   because it would orphan the pods.
7. A stable virtual IP and a stable DNS name. Traffic goes to pods whose labels
   match the Service's selector *and* that are ready.
8. `port` = the Service's own port (what clients dial); `targetPort` = the
   container's port the traffic is forwarded to.
9. ClusterIP: internal-only virtual IP (default, service-to-service).
   NodePort: opens a high port on every node — crude external access.
   LoadBalancer: provisions an external cloud load balancer with a public IP.
10. The container starts, exits (crash), and kubelet restarts it with
    exponential backoff, repeatedly. Command: `kubectl logs <pod> --previous` —
    the output of the *crashed* instance, which contains the actual error.
11. `kubectl describe pod <pod>` → Events. Causes: unschedulable resources
    (requests exceed any node's free capacity) or unsatisfiable placement
    constraints (nodeSelector/affinity/taints).
12. `kubectl get endpoints orders-svc`. Empty endpoints = the Service's selector
    matches no ready pod (label typo or readiness failing); populated endpoints =
    routing/port/app problem instead.
13. Reverts the Deployment to the previous ReplicaSet revision (rolling back the
    pod template, e.g. the image). Default strategy: rolling update.
14. Isolation scopes for names, RBAC, and quotas (dev/staging/prod, per team).
    Same namespace: short name (`svc`) resolves. Other namespace: qualify —
    `svc.<namespace>` or the full `svc.<namespace>.svc.cluster.local`.
15. ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: web
    spec:
      replicas: 2
      selector:
        matchLabels:
          app: web
      template:
        metadata:
          labels:
            app: web
        spec:
          containers:
            - name: web
              image: nginx:1.27
              ports:
                - containerPort: 80
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: web-svc
    spec:
      selector:
        app: web
      ports:
        - port: 80
          targetPort: 80
    ```

</details>

**Scoring:** 12+ → [Chapter 12](../12-kubernetes-in-practice/lesson.md). Below →
redo exercises 11.5, 11.6, 11.7 until the get→describe→logs loop is reflexive.
