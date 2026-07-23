# Chapter 12 — Kubernetes in Practice

## Learning objectives

1. Externalize configuration with ConfigMaps and Secrets.
2. Keep workloads honest with probes, resource requests/limits, and autoscaling.
3. Route external HTTP traffic with Ingress.
4. Protect availability and lock down traffic: PodDisruptionBudgets, NetworkPolicies, pod placement.
5. Persist data with PersistentVolumeClaims; know when *not* to run state in K8s.
6. Package and deploy with Helm; understand GitOps and Argo CD.

This chapter turns ch 11's toy deployments into production-shaped ones. Each
section adds one layer to the same visits app.

---

## 1. ConfigMaps & Secrets — config out of the image

Ch 01's rule: same artifact, different config per environment. K8s objects for it:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: visits-config
data:
  LOG_LEVEL: "info"
  FEATURE_NEW_SEARCH: "off"
  app.properties: |            # whole files work too
    cache.ttl=300
---
apiVersion: v1
kind: Secret
metadata:
  name: visits-secrets
type: Opaque
stringData:                    # stringData = write plaintext, stored base64
  DATABASE_URL: postgresql://app:s3cret@db:5432/appdb
```

Consume as env vars or mounted files:

```yaml
    spec:
      containers:
        - name: app
          image: ghcr.io/you/visits:1.2.0
          envFrom:
            - configMapRef: { name: visits-config }
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef: { name: visits-secrets, key: DATABASE_URL }
          volumeMounts:
            - name: props
              mountPath: /etc/app
      volumes:
        - name: props
          configMap: { name: visits-config, items: [{ key: app.properties, path: app.properties }] }
```

Truths to internalize:

- **K8s Secrets are base64-encoded, NOT encrypted** — anyone with API read
  access reads them. Real protection: RBAC, etcd encryption at rest, or external
  managers (Vault, cloud secret stores via External Secrets Operator — ch 16).
- Env vars are read **at container start** — config changes need a pod restart
  (`kubectl rollout restart deploy/visits`). Mounted files *do* update live
  (eventually), if the app re-reads them — your ch 10 flag-file lesson again.
- Never commit real secret values to Git even in Secret YAML — templating/
  sealed-secrets/external stores exist for exactly this (ch 16).

## 2. Probes — telling K8s the truth about health

Ch 04's liveness/readiness distinction, in its native habitat:

```yaml
          livenessProbe:            # fail → RESTART the container
            httpGet: { path: /health, port: 8000 }
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:           # fail → remove from Service endpoints (no restart)
            httpGet: { path: /ready, port: 8000 }
            periodSeconds: 5
          startupProbe:             # for slow starters: until this passes, liveness is paused
            httpGet: { path: /health, port: 8000 }
            failureThreshold: 30
            periodSeconds: 2
```

Design rules (they carry incidents on their backs):

- Liveness = "process wedged, restart helps" — cheap, no dependency checks
  (DB down + DB-checking liveness = restart storm across the whole fleet).
- Readiness = "can serve *now*" — may check critical dependencies; failing
  readiness during overload sheds traffic gracefully.
- Rolling updates wait for readiness — that's how zero-downtime actually works:
  a new pod receives traffic only when ready; without a readiness probe, K8s
  routes to pods that are still booting. **No probes = lying to the platform.**

## 3. Resources — requests, limits, and QoS

```yaml
          resources:
            requests: { cpu: 100m, memory: 128Mi }   # scheduler reserves this
            limits:   { cpu: 500m, memory: 256Mi }   # hard caps
```

- **Requests** drive scheduling: a pod goes only where requests fit (a node
  "full" by requests causes `Pending` — ch 11's zoo).
- **Limits**: exceed memory → OOMKill (exit 137, `kubectl describe` shows
  `OOMKilled`); CPU is throttled, not killed.
- Requests too low = overpacked nodes and noisy neighbors; too high = wasted
  capacity ("slack"). Right-size from real usage (`kubectl top pods`,
  Prometheus in ch 15).
- Namespace guardrails: `ResourceQuota` (total per namespace) and `LimitRange`
  (defaults per pod) keep teams honest.

### Autoscaling

**HPA** (Horizontal Pod Autoscaler) scales replicas on metrics:

```bash
kubectl autoscale deploy visits --min=2 --max=10 --cpu-percent=70
kubectl get hpa -w
```

> **What this creates:** an HPA object (yes, it's YAML-able too — the imperative form is for the lab) that watches the deployment's average CPU and adjusts `replicas` between 2 and 10, aiming at 70% of *requested* CPU.
> **Flags:** `--min`/`--max` the allowed replica range (min 2 = HA floor even at zero traffic) · `--cpu-percent=70` the target utilization · `-w` on the get = **w**atch: stream changes live instead of one snapshot (works on any `kubectl get`).
> **Expect:**
> ```
> NAME     REFERENCE           TARGETS    MINPODS  MAXPODS  REPLICAS
> visits   Deployment/visits   43%/70%    2        10       3
> ```
> `TARGETS <unknown>/70%` means the metrics-server isn't installed or requests aren't set — the two prerequisites, both named above. Generate load (exercises) and watch REPLICAS climb; scale-*down* happens minutes later by design (flap damping).

Requires the metrics-server (Docker Desktop: install via its manifest; kind:
same). CPU% is measured **against requests** — another reason requests must be
truthful. Beyond CPU: custom metrics (requests/sec via Prometheus adapter).
Also exist: VPA (right-sizes requests), Cluster Autoscaler (adds nodes — cloud).

## 4. Ingress — L7 routing in

Services are L4 (ch 04). **Ingress** is the L7 layer: host/path routing + TLS
termination, implemented by an **ingress controller** (nginx-ingress, Traefik)
that must be installed — Ingress objects are inert without one.

```bash
# lab install (kind/docker-desktop):
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
```

> **What this does:** `kubectl apply -f` accepts a URL as happily as a local file — this one is the ingress-nginx project's published manifest bundle, creating a namespace, the controller Deployment, its Service, RBAC, and admission webhooks in one shot. Watch it come up with `kubectl get pods -n ingress-nginx` until the controller pod is `Running`.
> **The trust question you should be asking:** you just applied YAML from the internet to your cluster. For a lab, fine; the diligent version is to download it first, read it, and pin a versioned URL instead of `main`. In production this arrives via Helm with a pinned chart version (§7) — same software, reviewable supply chain (ch 16).

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: visits-ing
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: visits.local          # add "127.0.0.1 visits.local" to /etc/hosts
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: visits-svc, port: { number: 80 } }
  tls:
    - hosts: [visits.local]
      secretName: visits-tls      # cert in a Secret; automated by cert-manager
```

The production pattern: **one LoadBalancer** (the controller) fronts *all* HTTP
services via Ingress rules — instead of one LB per service. TLS certs come from
**cert-manager** + Let's Encrypt (automated issuance/renewal — the ch 04 expiry
outage, engineered away). Note: Gateway API is Ingress' successor gradually
arriving; concepts transfer.

## 5. Production guardrails — PDBs, NetworkPolicies, and pod placement

Three objects that rarely appear in tutorials and always appear in production
cluster reviews (ch 16's audit checklist assumes all three).

### PodDisruptionBudget — surviving node maintenance

Nodes get drained: cluster upgrades, scale-downs, cloud spot reclaims.
`kubectl drain` evicts every pod on the node — and without guidance it will
happily evict *all* replicas of your service at the same moment. A
**PodDisruptionBudget (PDB)** sets the floor:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: visits-pdb
spec:
  minAvailable: 2                  # or: maxUnavailable: 1
  selector:
    matchLabels: { app: visits }
```

> **How it works:** *voluntary* disruptions (drain, the eviction API) must ask permission, and the PDB answers. With 3 replicas and `minAvailable: 2`, a drain evicts one pod, waits until its replacement is Ready on another node, then proceeds — the rolling-update choreography of ch 10, applied to infrastructure maintenance. It does **not** protect against involuntary disruptions (node crash, OOMKill) — replicas themselves are that protection. Classic footgun: `minAvailable` equal to `replicas` makes pods un-evictable and cluster upgrades hang forever; a PDB must leave headroom.

### NetworkPolicy — the in-cluster firewall

By default **every pod can talk to every pod**, across all namespaces — one
flat network. NetworkPolicies are the ch 04 firewall idea, expressed with
selectors:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-from-api-only
spec:
  podSelector:
    matchLabels: { app: db }       # the pods this policy protects
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels: { app: visits }
      ports:
        - protocol: TCP
          port: 5432
```

> **The semantics that surprise everyone:** policies are *additive whitelists*. The moment **any** policy selects a pod, that pod flips to default-deny for the covered direction, and only what policies explicitly allow gets through. This one says: the database accepts inbound TCP 5432 from `app: visits` pods — and nothing else, from anywhere. The ch 06 two-networks isolation idea, cluster-grade. Production baseline: one default-deny-all policy per namespace, then explicit allows per flow.
> **Lab caveat:** enforcement is the **CNI plugin's** job (Calico and Cilium enforce; Docker Desktop's default networking does *not*) — on a non-enforcing cluster the policy applies cleanly and silently does nothing. If you want to watch packets actually get dropped, kind + Calico is the lab route.

### Placement — nodeSelector, affinity, taints & tolerations

Left alone, the scheduler places pods wherever resource requests fit.
Production usually needs more say:

```yaml
      # in the pod template spec:
      nodeSelector:
        disktype: ssd              # only nodes labeled disktype=ssd
      tolerations:
        - key: dedicated
          operator: Equal
          value: build-agents
          effect: NoSchedule       # may run on nodes tainted for build agents
```

> **The two directions:** labels + `nodeSelector`/`affinity` *attract* — the pod names what nodes it wants (`affinity` is the expressive form: soft preferences, spread-across-zones rules). Taints *repel* — the **node** declares "nobody schedules here without explicitly tolerating this taint" (`kubectl taint nodes gpu-1 dedicated=build-agents:NoSchedule`). You need both to reserve special nodes (GPU, build agents): the taint keeps everyone else off, the toleration lets the right pods on.
> **The one everybody uses:** `podAntiAffinity` telling replicas to avoid *each other* — three replicas forced onto three different nodes, so one node failure can't take out all of your "redundant" copies. Without it, the scheduler is free to co-locate them.

## 6. Storage — PV, PVC, StatefulSet (and honest advice)

Pods' filesystems die with them. K8s storage stack:

- **PersistentVolume (PV)** — a piece of actual storage (cloud disk, NFS, local).
- **PersistentVolumeClaim (PVC)** — a pod's request for storage ("5Gi, RWO").
- **StorageClass** — provisions PVs on demand (local labs have one built in).

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pgdata
spec:
  accessModes: [ReadWriteOnce]
  resources: { requests: { storage: 5Gi } }
---
# in the pod template:
      volumes:
        - name: data
          persistentVolumeClaim: { claimName: pgdata }
      containers:
        - name: postgres
          volumeMounts: [{ name: data, mountPath: /var/lib/postgresql/data }]
```

**StatefulSets** manage stateful workloads: stable pod names (`db-0`, `db-1`),
one PVC per replica, ordered rollout — for databases, queues, anything with
identity.

Honest advice for this course's level: stateless services in K8s = great;
databases in K8s = a real discipline (operators like CloudNativePG help). Teams
commonly use managed databases and keep clusters stateless — a legitimate
architecture, not a cop-out. Know PVC mechanics; postpone "Postgres on K8s in
prod" until you have reasons and experience.

## 7. Helm — packaging and templating

The same YAML with 6 values changed per environment breeds copy-paste drift.
**Helm** = templates + values + lifecycle:

```
mychart/
├── Chart.yaml          # name, version
├── values.yaml         # defaults
└── templates/
    ├── deployment.yaml # YAML with {{ .Values.* }} holes
    └── service.yaml
```

`templates/deployment.yaml` (excerpt):

```yaml
spec:
  replicas: {{ .Values.replicas }}
  template:
    spec:
      containers:
        - name: app
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
```

`values.yaml`:

```yaml
replicas: 2
image:
  repository: ghcr.io/you/visits
  tag: 1.2.0
```

```bash
helm install visits ./mychart                          # deploy with defaults
helm upgrade visits ./mychart --set image.tag=1.3.0    # or -f values-prod.yaml
helm rollback visits 1
helm template ./mychart | less                         # render locally — review before applying!
helm list
```

> **Tool:** `helm` — the Kubernetes package manager. A deployed chart instance is a **release** with a name (`visits` here) and numbered revisions — that's the unit `upgrade`/`rollback`/`list` operate on.
> **Command by command:**
> - `install visits ./mychart` — render the templates with `values.yaml`, apply the result, record it as release `visits` revision 1. Expect a `STATUS: deployed` summary.
> - `upgrade visits ./mychart --set image.tag=1.3.0` — re-render with overrides and apply the diff; revision 2. `--set key=value` is a one-off override; `-f values-prod.yaml` layers a whole file (later sources win over `values.yaml` defaults). Prefer files in Git over `--set` for anything repeated — same reviewability argument as everywhere in this course.
> - `rollback visits 1` — re-apply revision 1's manifests. Deployment rollback, chart-scoped.
> - `template ./mychart` — render to stdout *without touching the cluster*: the plan-before-apply habit (ch 13 formalizes it). Pipe through `less` or diff against what's running.
> - `list` — releases in the current namespace with revision and chart version.

Two distinct uses:

1. **Consuming public charts** — the immediate superpower:
   `helm repo add prometheus-community https://prometheus-community.github.io/helm-charts`
   then `helm install monitoring prometheus-community/kube-prometheus-stack` —
   a full monitoring stack (ch 15) in one command.
2. **Authoring charts** for your own apps — one chart, per-env values files
   (`values-staging.yaml`, `values-prod.yaml`). Alternative worth knowing:
   **Kustomize** (built into kubectl, `kubectl apply -k`) — overlay patches
   instead of templates; simpler, less powerful; many teams run both.

## 8. GitOps — closing the loop (Argo CD)

You now have: manifests/charts in Git (ch 03 discipline) + a cluster that
converges on declared state. **GitOps** connects them: an in-cluster operator
(Argo CD, Flux) continuously syncs Git → cluster.

```
CI (ch 07-09): build image, push registry, bump tag in the GITOPS REPO
                                                    │ (a PR — reviewed!)
Argo CD: watches the repo ── detects drift ── applies ── reports health
```

What this buys over `kubectl apply` from CI:

- **Git is the single source of truth** — the cluster matches the repo, always;
  manual `kubectl edit` drift is detected (and optionally auto-reverted).
- **Rollback = `git revert`** — with full audit history for free.
- **No cluster credentials in CI** — the pull model: CI never touches the
  cluster; Argo CD (inside) pulls from Git. Smaller attack surface.
- Deploy = merge a PR. Same review gate as code.

Lab-able: Argo CD installs via one manifest, has a clean UI, and the exercises
walk you through app-of-repo setup. This pattern — CI builds artifacts, GitOps
deploys them — is the current best-practice endpoint of everything since ch 07.

## The complete production-shaped deployment

All layers assembled (abbreviated):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: visits }
spec:
  replicas: 3
  selector: { matchLabels: { app: visits } }
  template:
    metadata: { labels: { app: visits } }
    spec:
      containers:
        - name: app
          image: ghcr.io/you/visits:1.2.0        # pinned (ch 05)
          ports: [{ containerPort: 8000 }]
          envFrom: [{ configMapRef: { name: visits-config } }]
          env:
            - name: DATABASE_URL
              valueFrom: { secretKeyRef: { name: visits-secrets, key: DATABASE_URL } }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { memory: 256Mi }
          livenessProbe: { httpGet: { path: /health, port: 8000 }, periodSeconds: 10 }
          readinessProbe: { httpGet: { path: /ready, port: 8000 }, periodSeconds: 5 }
          securityContext: { runAsNonRoot: true, allowPrivilegeEscalation: false }
```

Every line answers a question from an earlier chapter. That's the design of this
course working as intended.

## Further reading

- kubernetes.io/docs: Configuration, Probes, Ingress, Storage concepts.
- helm.sh/docs — "Getting Started" + chart template guide.
- argo-cd.readthedocs.io — "Getting Started".

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| HPA | Horizontal Pod Autoscaler | Adjusts a Deployment's replica count based on live metrics |
| VPA | Vertical Pod Autoscaler | Adjusts a pod's requested CPU/memory instead of replica count |
| PDB | PodDisruptionBudget | Floor on how many replicas voluntary evictions (node drains) must leave running |
| CNI | Container Network Interface | The pluggable pod-network layer; NetworkPolicy enforcement depends on which one runs |
| GPU | Graphics Processing Unit | Specialized compute hardware — the classic reason to taint and reserve nodes |
| PV | PersistentVolume | An actual piece of storage available to the cluster |
| PVC | PersistentVolumeClaim | A pod's request for a chunk of that storage |
| RWO | ReadWriteOnce | Access mode allowing the volume to be mounted by only one node at a time |
| QoS | Quality of Service | The pod priority class Kubernetes derives from its resource requests/limits |
| TLS | Transport Layer Security | What Ingress terminates before traffic reaches backend Services |
| CI/CD | Continuous Integration / Continuous Delivery-Deployment | The pipeline that builds images which GitOps then deploys |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 13: Terraform](../13-terraform/lesson.md)
