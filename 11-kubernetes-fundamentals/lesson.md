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

> **Tools:** `kind` — runs a whole Kubernetes cluster where each "node" is a Docker container; `create cluster --name devops` boots one and writes its connection details into your kubeconfig. `kubectl` — *the* Kubernetes CLI; every command is an HTTPS call to the cluster's API server.
> **The verification pair:** `kubectl cluster-info` prints the API server's URL — proving your kubeconfig points somewhere alive. `kubectl get nodes` asks the cluster for its member machines; expect:
> ```
> NAME                   STATUS   ROLES           AGE   VERSION
> devops-control-plane   Ready    control-plane   2m    v1.30.0
> ```
> `STATUS Ready` is the health signal. Anything else (or a connection error) means stop and fix the cluster before continuing — every later command depends on this working.

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

> **The kubectl grammar** — almost every command is `kubectl VERB RESOURCE-TYPE NAME [flags]`. Learn the verbs once, they apply to every object type:
> - `apply -f pod.yaml` — "make reality match this file". Create or update, same command, safe to repeat (idempotent — ch 01's word, and the declarative discipline of §8).
> - `get pods` — the list view. Expect: `NAME  READY  STATUS  RESTARTS  AGE` / `visits  1/1  Running  0  30s`. `-o wide` adds the pod's IP and node; `-o yaml` dumps the full object (including the `status:` the system added).
> - `describe pod visits` — the detail view: config, conditions, and at the bottom **Events** — the scheduler's and kubelet's diary ("pulled image", "failed to pull", "OOMKilled"). Events answer most "why is my pod broken" questions; read them bottom-up (newest last).
> - `logs visits` — the container's stdout (the ch 05 habit pays off here). `-f` follows; `--previous` shows the *last crashed* instance's output — the only place a boot-crash's error message survives.
> - `exec -it visits -- sh` — a shell inside, exactly like `docker exec`; the `--` separates kubectl's flags from the command to run.
> - `delete pod visits` — asks the API to remove it (SIGTERM → grace period → SIGKILL, same contract as `docker stop`).

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

> **What to watch:** `get deploy,rs,pods` (comma = multiple types in one call) shows the ownership chain — expect:
> ```
> NAME                          READY   UP-TO-DATE   AVAILABLE
> deployment.apps/visits        3/3     3            3
>
> NAME                                    DESIRED   CURRENT   READY
> replicaset.apps/visits-7d4b9c8f6d       3         3         3
>
> NAME                              READY   STATUS    RESTARTS
> pod/visits-7d4b9c8f6d-x2m4p       1/1     Running   0
> ```
> The hash in the ReplicaSet name (`7d4b9c8f6d`) identifies one pod-template version; pod names append a random suffix to it. After `delete pod`, a replacement with a *new suffix* appears within seconds — you deleted a pod, but the ReplicaSet's job is "3 replicas exist", so it made another. That's reconciliation, observed.

### Rolling updates and rollback — ch 10, implemented

```bash
# change the image (or edit YAML and re-apply — preferred, keeps Git truthful):
kubectl set image deploy/visits app=ghcr.io/you/visits:1.1.0
kubectl rollout status deploy/visits      # watch the roll
kubectl rollout history deploy/visits
kubectl rollout undo deploy/visits        # rollback in one command
```

> **Command by command:**
> - `set image deploy/visits app=...:1.1.0` — changes the image of container `app` in the pod template. Any template change (image, env, resources) triggers a rolling update: a new ReplicaSet is created and scaled up while the old scales down, wave by wave.
> - `rollout status` — blocks until the roll completes (or fails), printing progress: `Waiting for deployment "visits" rollout to finish: 2 out of 3 new replicas have been updated...` Exit code reflects success — which makes this line the natural last step of a CI deploy job.
> - `rollout history` — numbered revisions of the pod template (each old ReplicaSet is kept, scaled to 0, as the revision record).
> - `rollout undo` — scales the previous revision's ReplicaSet back up — rollback as *another rolling update, backwards*, ch 10's rolling strategy both directions. `--to-revision=N` picks a specific one.

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

> **Command by command:**
> - `get svc` — expect `visits-svc  ClusterIP  10.96.142.7  <none>  80/TCP` — that `CLUSTER-IP` is the stable virtual IP; it never changes for the service's lifetime.
> - `get endpoints visits-svc` — the pod IPs currently behind the service: `ENDPOINTS: 10.244.1.5:8000,10.244.1.6:8000,10.244.2.3:8000`. **The single most diagnostic command for service problems:** a healthy service lists ready pod IPs; `<none>` means the selector matches nothing (typo) or no matching pod is ready (failing readiness). Service debugging starts here, always.
> - `port-forward svc/visits-svc 8080:80` — opens a tunnel: your laptop's `localhost:8080` → the service's port 80, through the API server. No Ingress, no NodePort, no exposure — it lives only while the command runs (foreground; Ctrl-C ends it). `curl localhost:8080` in another terminal to test.

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

> **The flags:** `-n staging` scopes any command to one namespace; without a flag you're in `default`. `-A` (`--all-namespaces`) sees everything. The `config set-context` line changes what "no flag" means for your current cluster connection — handy when working in one namespace all day, and worth double-checking (`kubectl config get-contexts` shows the active default) before any `delete`.

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

> **Command by command:**
> - `get events --sort-by=.lastTimestamp` — every recent event cluster-wide, oldest first (`--sort-by` orders by any field; unsorted event output is confusingly shuffled). The "what just happened here?" view when you don't yet know *which* object is sick.
> - `kubectl run tmp --rm -it --image=alpine -- sh` — the debug pod: `run` creates a single pod imperatively (one of the few legit uses), flags exactly like `docker run` (`--rm -it`), dropping you into a shell *inside the cluster's network*. From there, service DNS and pod IPs are testable directly: `wget -qO- http://visits-svc` (wget because alpine has no curl; `-qO-` = quiet, output to stdout). Exit the shell and the pod cleans itself up.
> - `api-resources` — every object type this cluster knows, with short names (`po`, `deploy`, `svc`) and API groups. Also how you discover types added by extensions.
> - `explain deployment.spec.strategy` — official docs for any field, drilled by dot-path, straight from the API server's schema. No browser, no version mismatch — the docs *are* the cluster's.

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

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| K8s | Kubernetes | The container-orchestration platform ("8" replaces the 8 letters between K and s) |
| RBAC | Role-Based Access Control | Permission model governing who/what can act on cluster objects |
| DNS | Domain Name System | How Services get stable, name-based addresses inside the cluster |
| API | Application Programming Interface | Everything — `kubectl` included — talks to the cluster through the API server |
| CLI | Command-Line Interface | `kubectl`, the cluster's command-line tool |
| IP | Internet Protocol (address) | What each Pod and Service gets — Pods' IPs are ephemeral, Services' aren't |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 12: Kubernetes in Practice](../12-kubernetes-in-practice/lesson.md)
