# Chapter 11 — Kubernetes Fundamentals

## Learning objectives

1. Explain what Kubernetes is for and how its reconciliation model works.
2. Run a local cluster (Docker Desktop / kind) and drive it with `kubectl`.
3. Deploy applications with Pods, Deployments, and Services — and know what each adds.
4. Read cluster state fluently: `get`, `describe`, `logs`, `events`, `exec`.
5. Debug the classic failures: `ImagePullBackOff`, `CrashLoopBackOff`, `Pending`, unreachable Service.

---

## 1. Why Kubernetes exists

Docker (ch 05–06) runs containers on **one machine**. Production needs: many
machines, containers rescheduled when a machine dies, load-balanced traffic,
rolling updates (ch 10), autoscaling. You could script all that — many did — or
use the system that won: **Kubernetes (K8s)**, the cluster operating system.

### The core idea: declarative reconciliation

You don't tell K8s *what to do*; you declare *what should exist*:

> "There should be 3 replicas of `visits:1.2.0`, reachable as `visits-svc` on port 80."

Controllers run **reconciliation loops**: observe actual state → compare with
desired state → act to converge. Kill a pod — a new one appears, not because a
script reacted, but because "3 replicas" stopped being true and the controller
made it true again. This is IaC thinking (ch 13) applied continuously at runtime.

### Architecture in one diagram

```
CONTROL PLANE                          WORKER NODES
┌─────────────────────────┐            ┌──────────────────────┐
│ API server  ← kubectl,  │            │ kubelet (node agent) │
│   CI, controllers—      │  watches   │ container runtime    │
│   everything talks here │◄───────────│ kube-proxy (services)│
│ etcd (state store)      │            │   [pod] [pod] [pod]  │
│ scheduler (pods→nodes)  │            ├──────────────────────┤
│ controller manager      │            │ ... more nodes       │
└─────────────────────────┘            └──────────────────────┘
```

You need the shape, not the internals: **everything goes through the API server**;
state lives in etcd; the scheduler places pods; kubelets make them real on nodes.

## 2. Lab setup

Docker Desktop → Settings → Kubernetes → Enable (simplest, single node).
Alternative used by many pros: **kind** (Kubernetes-in-Docker) — multi-node
clusters as containers:

```bash
# kind route (also fine to skip if Docker Desktop K8s is on):
go install / brew install kind   # or: curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64
kind create cluster --name devops

# either way, verify:
kubectl cluster-info
kubectl get nodes
```

`kubectl` config lives in `~/.kube/config`; `kubectl config get-contexts` /
`use-context` switches clusters — one CLI, many clusters.

Set up autocomplete now (it's not optional at K8s verbosity levels):

```bash
echo 'source <(kubectl completion bash)' >> ~/.bashrc
echo 'alias k=kubectl && complete -o default -F __start_kubectl k' >> ~/.bashrc
```

## 3. Pods — the atom

A **Pod** = one or more containers sharing a network namespace (one IP, can talk
via localhost) and lifecycle. Usually one main container; sidecars (log shippers,
proxies) share the pod.

```yaml
# pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: visits
  labels:
    app: visits
spec:
  containers:
    - name: app
      image: ghcr.io/you/visits:1.0.0
      ports:
        - containerPort: 8000
```

```bash
kubectl apply -f pod.yaml       # declarative: make it so
kubectl get pods                # STATUS, RESTARTS, AGE
kubectl get pods -o wide        # + pod IP, node
kubectl describe pod visits    # full detail + EVENTS (the debugging goldmine)
kubectl logs visits            # stdout (ch 05 habit pays off)
kubectl logs visits -f --previous   # follow / previous crashed instance
kubectl exec -it visits -- sh  # shell inside
kubectl delete pod visits
```

Every K8s object follows the same YAML skeleton: `apiVersion`, `kind`,
`metadata` (name, labels), `spec` (desired state). The system adds `status`
(actual state). Reconciliation = making status match spec.

**You almost never create bare Pods.** They don't restart when a node dies and
don't scale — that's the next layer's job. But every higher layer *produces*
pods, so pod debugging skills are universal.

## 4. Deployments — replicas + rollouts

A **Deployment** declares "N replicas of this pod template" and manages rolling
updates (it creates ReplicaSets under the hood — you'll see them in `get all`):

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: visits
spec:
  replicas: 3
  selector:
    matchLabels:
      app: visits
  template:                      # ← a full pod template
    metadata:
      labels:
        app: visits              # must match the selector!
    spec:
      containers:
        - name: app
          image: ghcr.io/you/visits:1.0.0
          ports:
            - containerPort: 8000
```

```bash
kubectl apply -f deployment.yaml
kubectl get deploy,rs,pods                # see all three layers
kubectl delete pod <one-of-them>          # watch reconciliation replace it
kubectl scale deploy visits --replicas=5  # imperative scale (or edit YAML + apply)
```

### Rolling updates and rollback — ch 10, implemented

```bash
# change the image (or edit YAML and re-apply — preferred, keeps Git truthful):
kubectl set image deploy/visits app=ghcr.io/you/visits:1.1.0
kubectl rollout status deploy/visits      # watch the roll
kubectl rollout history deploy/visits
kubectl rollout undo deploy/visits        # rollback in one command
```

The Deployment performs a **rolling update** by default (`maxSurge`/
`maxUnavailable` tune the wave). Version coexistence during the roll — the ch 10
compatibility constraint — applies in full.

**Labels and selectors** are the glue everywhere: the Deployment finds its pods
by label match; Services (next) route by label match; you query by them:
`kubectl get pods -l app=visits`. Labels are the relational join of K8s.

## 5. Services — stable networking over ephemeral pods

Pods get new IPs every restart; you need a stable address. A **Service** =
fixed virtual IP + DNS name, load-balancing to all pods matching its selector
(the ch 04 load balancer, cluster-native):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: visits-svc
spec:
  selector:
    app: visits          # routes to ready pods with this label
  ports:
    - port: 80           # the service's port
      targetPort: 8000   # the container's port
```

Types:

| Type | Reachable from | Use |
|------|----------------|-----|
| `ClusterIP` (default) | inside the cluster only | service-to-service traffic |
| `NodePort` | `<any-node-ip>:30000-32767` | crude external access, labs |
| `LoadBalancer` | cloud LB with external IP | real external exposure (cloud) |

In-cluster DNS: `visits-svc` resolves within the namespace,
`visits-svc.<namespace>.svc.cluster.local` from anywhere — Docker network DNS
(ch 06) scaled up. HTTP routing by host/path (the L7 story) is **Ingress** — ch 12.

```bash
kubectl get svc
kubectl get endpoints visits-svc     # the actual pod IPs behind it — THE debugging view
kubectl port-forward svc/visits-svc 8080:80   # tunnel to your laptop for testing
```

`kubectl port-forward` is the lab/debug workhorse — no exposure needed.

## 6. Namespaces

Virtual sub-clusters for isolation: `dev`/`staging`/`prod`, or per team.

```bash
kubectl create namespace staging
kubectl apply -f deployment.yaml -n staging
kubectl get pods -n staging
kubectl get pods -A                  # all namespaces
kubectl config set-context --current --namespace=staging   # switch default
```

Names are unique per namespace; RBAC and quotas attach to namespaces. System
components live in `kube-system` — look, don't touch (yet).

## 7. Debugging the classic failures — the survival table

The universal loop: `kubectl get pods` → **STATUS column** → `describe` (read
**Events** bottom-up) → `logs` → `exec`.

| STATUS | Meaning | Usual causes | First command |
|--------|---------|--------------|---------------|
| `ImagePullBackOff` / `ErrImagePull` | can't fetch image | typo in tag, private registry without pull secret, image doesn't exist | `describe` → Events show the pull error verbatim |
| `CrashLoopBackOff` | container starts and dies, repeatedly, with growing backoff | app crashes on boot: bad config, missing env/dependency, wrong command | `logs --previous` (the crashed instance's output!) |
| `Pending` | no node can host it | insufficient CPU/memory, unsatisfiable node selector | `describe` → Events: "0/3 nodes available: insufficient memory" |
| `Running` but not working | app-level problem | readiness failing, wrong port, app bug | `logs`, `port-forward` and curl it directly |
| Service returns nothing | selector/label mismatch or no ready pods | typo'd labels, readiness probe failing | `kubectl get endpoints <svc>` — empty = selector matches no ready pod |

Also in the toolbox:

```bash
kubectl get events --sort-by=.lastTimestamp     # cluster-wide recent events
kubectl run tmp --rm -it --image=alpine -- sh   # throwaway debug pod inside the cluster
#   (then: wget -qO- http://visits-svc — test service DNS/routing from inside)
kubectl api-resources                           # what object kinds exist
kubectl explain deployment.spec.strategy        # built-in field documentation!
```

`kubectl explain` deserves fame: full schema docs for any field, offline.

## 8. Imperative vs declarative — the discipline

Everything has an imperative shortcut (`kubectl run`, `scale`, `set image`,
`create deployment`). Fine for labs and incident surgery. **The durable practice:
YAML in Git, `kubectl apply`** — because ch 01's principles (reviewable,
reproducible, auditable) apply to runtime config too. `kubectl diff -f f.yaml`
previews changes. GitOps (ch 12) turns this discipline into machinery.

## Mental model recap

```
Deployment ─manages→ ReplicaSet ─maintains→ Pods (label: app=visits)
                                              ▲
Service (selector: app=visits) ──routes to───┘
        + stable DNS name + virtual IP
```

## Further reading

- kubernetes.io/docs/tutorials/kubernetes-basics/ — official interactive basics.
- kubernetes.io/docs/concepts/ — Workloads and Services sections.
- `kubectl explain` — genuinely a primary doc source.

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 12: Kubernetes in Practice](../12-kubernetes-in-practice/lesson.md)
