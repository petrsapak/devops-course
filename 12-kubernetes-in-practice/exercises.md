# Chapter 12 — Exercises

Continues from ch 11's cluster and visits/whoami deployments. Work in
`~/devops/ch12`. These exercises stack — do them in order; by 12.8 you'll have
the full production-shaped app.

---

## Exercise 12.1 — ConfigMap + Secret wiring

1. Create `visits-config` (LOG_LEVEL, FEATURE_NEW_SEARCH) and `visits-secrets`
   (DATABASE_URL) as in lesson §1. Wire them into the visits Deployment via
   `envFrom` and `secretKeyRef`.
2. Verify from inside: `kubectl exec deploy/visits -- env | grep -E "LOG_LEVEL|DATABASE"`.
3. Change LOG_LEVEL in the ConfigMap, apply, and check the pod's env again —
   changed or not? Do what's needed to make it take effect.
4. Read the secret back: `kubectl get secret visits-secrets -o jsonpath='{.data.DATABASE_URL}' | base64 -d`.

**Verify:** step 3 required a `rollout restart` (env vars bind at container
start); step 4 proved to you that base64 ≠ encryption.

## Exercise 12.2 — Probes, honest and dishonest

1. Add `/ready` to the visits app (return 200; plus a testing backdoor:
   `POST /ready/toggle` flips it to 503). Rebuild/push, or simulate with an
   nginx pod if you'd rather not rebuild.
2. Add liveness (`/health`) and readiness (`/ready`) probes to the Deployment.
3. With 3 replicas and a curl loop against the service: toggle ONE pod's
   readiness off (`kubectl exec` + curl the backdoor). Watch
   `kubectl get endpoints` — the pod leaves the endpoints, traffic continues
   unharmed, **no restart happens**.
4. Toggle it back — it rejoins.
5. Contrast: `kubectl exec` into a pod and kill the main process — liveness
   territory. RESTARTS increments.

**Verify:** you demonstrated the core distinction live: readiness gates traffic,
liveness triggers restarts, and neither substitutes for the other.

## Exercise 12.3 — Resources, OOMKill, and Pending revisited

1. Set requests `cpu: 100m, memory: 64Mi`, limits `memory: 96Mi` on visits. Apply.
2. `kubectl top pods` (install metrics-server if missing) — headroom?
3. Force an OOMKill: exec in and eat memory
   (`python3 -c "x = bytearray(200*1024*1024); import time; time.sleep(60)"`).
   Then `kubectl describe pod <it>` — find `OOMKilled` and exit code 137.
4. Set requests `memory: 100Gi`, apply, and explain the resulting pod state
   from ch 11's zoo. Revert.

**Verify:** you located `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`
— you will meet this exact block again in real life.

## Exercise 12.4 — HPA under load

1. `kubectl autoscale deploy visits --min=2 --max=8 --cpu-percent=50`.
2. Generate load from a pod:
   `kubectl run load --rm -it --image=busybox -- sh -c "while true; do wget -qO- http://visits-svc > /dev/null; done"`
   (run 2–3 of these for real pressure).
3. Watch `kubectl get hpa -w` and `get pods -w` — scale-out as CPU% crosses the
   target; kill the load pods and watch scale-in (note: slower — why might
   scale-down be deliberately conservative?).

**Verify:** replicas rose and later fell; you can explain why HPA is useless if
requests are unset (the percentage has no denominator).

## Exercise 12.5 — Ingress

1. Install ingress-nginx (lesson §4 manifest). Wait for the controller pod.
2. Create Ingress rules on ONE host with TWO paths: `visits.local/` →
   visits-svc, `visits.local/who` → whoami-svc.
3. Add `127.0.0.1 visits.local` to the **Windows** hosts file
   (`C:\Windows\System32\drivers\etc\hosts`, admin) — Docker Desktop exposes the
   controller on localhost.
4. Curl/browse both paths.
5. Bonus TLS: create a self-signed cert
   (`openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 30 -nodes -subj "/CN=visits.local"`),
   make a TLS secret (`kubectl create secret tls visits-tls --cert=tls.crt --key=tls.key`),
   add the `tls:` block, and hit `https://visits.local` (accept the warning —
   and recall which real component automates this away: cert-manager).

**Verify:** two services, one entry point, path-routed — the L7 pattern. State
what an Ingress object does with no controller installed (nothing — inert).

## Exercise 12.6 — PVC + a database pod

1. Create a PVC `pgdata` (1Gi, RWO) and a postgres Deployment (1 replica!)
   mounting it at `/var/lib/postgresql/data`, plus a ClusterIP service `db`.
2. Create a table + row (`kubectl exec` + psql, like ch 06's exercise).
3. Delete the postgres **pod** — reconciliation rebuilds it; is the data there?
4. Delete the Deployment AND recreate it — same PVC — data?
5. Point the visits app's DATABASE_URL secret at `postgresql://...@db:5432/...`
   and confirm `/visits` works end-to-end in-cluster.

**Verify:** data survived both pod death and deployment recreation (the PVC is
the durable thing); the full app now runs in-cluster. Note why `replicas: 1`
(RWO volume + Postgres isn't multi-writer — the StatefulSet/operator discussion).

## Exercise 12.7 — Helm-ify it

1. `helm create visits-chart` — study the generated skeleton, then simplify:
   deployment + service + ingress templates for your app with values for
   `image.tag`, `replicas`, `ingress.host`, resources.
2. `helm template ./visits-chart` — read the rendered output BEFORE installing.
3. `helm install visits-r ./visits-chart` alongside... conflict with your
   existing raw-YAML deployment? Clean up the old one first (`kubectl delete -f`),
   then install.
4. Create `values-staging.yaml` (1 replica, staging host) and deploy a second
   release into the `staging` namespace:
   `helm install visits-stg ./visits-chart -n staging -f values-staging.yaml`.
5. Upgrade prod's tag (`--set image.tag=...`), then `helm rollback visits-r 1`.

**Verify:** two environments from one chart + two values files; rollback works;
`helm list -A` shows both releases with revision history.

## Exercise 12.8 — GitOps with Argo CD (capstone of the K8s block)

1. Install: `kubectl create namespace argocd && kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml`.
2. UI: `kubectl port-forward svc/argocd-server -n argocd 8443:443`; password:
   `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d`.
3. Push your `visits-chart` (or raw manifests) to a GitHub repo `visits-gitops`.
4. In Argo CD: create an Application pointing at that repo/path, destination:
   your cluster, namespace `default`, enable auto-sync + self-heal.
5. **The GitOps moment:** change `replicas` in Git (commit/push) — watch Argo
   sync it. Then cause drift: `kubectl scale deploy visits --replicas=1`
   manually — watch self-heal put it back.
6. Roll back a change with `git revert` + push. Watch the cluster follow.

**Verify:** the cluster obeyed Git twice (sync + revert) and *overrode your
manual kubectl* — you experienced "Git as the single source of truth" rather
than reading about it.

---

**Keep everything running if you can** — the capstone reuses this cluster, chart,
and Argo CD.
