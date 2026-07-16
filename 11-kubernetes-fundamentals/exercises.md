# Chapter 11 — Exercises

Requires a running local cluster (Docker Desktop K8s or kind) and `kubectl`.
Work in `~/devops/ch11`. Use your published visits image from ch 07
(`ghcr.io/<you>/<repo>:latest` — make the package public for easy pulls) or any
public image (`nginx:1.27`, `traefik/whoami`) where noted.

---

## Exercise 11.1 — Cluster orientation

1. `kubectl cluster-info`, `kubectl get nodes -o wide` — how many nodes, what
   container runtime, what internal IPs?
2. `kubectl get pods -A` — inventory `kube-system`: identify the DNS pods and
   (if present) kube-proxy.
3. `kubectl api-resources | head -30` — find the SHORTNAMES column (po, deploy,
   svc, ns) — start using them.

**Verify:** you can answer: where does `kubectl` send every command? (One
component; everything else hangs off it.)

## Exercise 11.2 — Pods raw

1. Write `pod.yaml` for a single `traefik/whoami` pod labeled `app: whoami`,
   port 80. Apply it.
2. `kubectl port-forward pod/<name> 8080:80` and curl localhost:8080 — note the
   pod hostname/IP in the response.
3. `kubectl exec` in and look around (`env | grep KUBERNETES` — the injected
   service env).
4. Delete the pod. Does anything bring it back? Why not?

**Verify:** you stated the reason bare pods don't self-heal (no controller owns
them — nothing's desired-state says they should exist).

## Exercise 11.3 — Deployment + reconciliation theater

1. Write `deploy.yaml`: Deployment `whoami`, 3 replicas, same pod template.
   Apply; watch with `kubectl get pods -w` in a second terminal.
2. Kill a pod (`kubectl delete pod <one>`) and watch the replacement appear in
   the `-w` stream. Note the pod name changes — pods are cattle.
3. Scale to 6 via YAML edit + `kubectl apply` (not `kubectl scale`) — keep Git
   truthful. Then back to 3.
4. `kubectl get deploy,rs,pods` — map the three layers and their name prefixes.

**Verify:** replacement pod appeared within seconds; you can trace
deployment → replicaset hash → pod names.

## Exercise 11.4 — Service + endpoints

1. Add `svc.yaml`: ClusterIP service `whoami-svc`, port 80 → targetPort 80,
   selector `app: whoami`. Apply.
2. From a throwaway pod (`kubectl run tmp --rm -it --image=alpine -- sh`):
   `wget -qO- http://whoami-svc` several times — observe **different pod names**
   answering (load balancing in action).
3. Try the FQDN: `whoami-svc.default.svc.cluster.local`.
4. `kubectl get endpoints whoami-svc` — match the IPs against
   `kubectl get pods -o wide`.

**Verify:** responses rotate across ≥2 pods; endpoints list = ready pod IPs, exactly.

## Exercise 11.5 — Break the selector (the classic outage)

1. Edit the service selector to `app: whoami-typo`, apply.
2. From the debug pod, curl again — record the failure mode.
3. Check `kubectl get endpoints whoami-svc` — what does it show, and why is
   this the single most diagnostic command for "service doesn't work"?
4. Fix the selector.

**Verify:** empty endpoints ↔ selector matches no ready pod; connection to the
service name times out / refuses. Sentence to remember: *service problems are
almost always label problems.*

## Exercise 11.6 — Rolling update and rollback

Use your visits image with two real tags (e.g. `1.0.0` and `1.1.0` from ch 07;
or nginx `1.26`/`1.27` and check the `Server:` header).

1. Deploy 4 replicas of the old version, with the service in front.
2. In one terminal: a curl loop against a port-forward to the service.
   In another: `kubectl set image deploy/visits app=<new>` then
   `kubectl rollout status deploy/visits`.
3. Watch pods with `-w` during the roll: new ones appearing, old ones
   terminating, wave by wave.
4. `kubectl rollout history`, then `kubectl rollout undo` and confirm the old
   version answers again.

**Verify:** the curl loop never failed (zero-downtime roll), and rollback was one
command — ch 10's rolling strategy, delivered by a controller instead of your
nginx-and-hands.

## Exercise 11.7 — Failure zoo (the debugging drill)

Create each failure, diagnose it *using only the survival-table loop*
(get → describe/Events → logs), write the diagnosis, then fix:

1. **ImagePullBackOff:** deploy image `nginx:1.27-this-tag-does-not-exist`.
2. **CrashLoopBackOff:** deploy `busybox:1.36` with
   `command: ["sh", "-c", "echo starting; exit 1"]`. Use `logs --previous`.
3. **Pending:** deploy with an impossible resource request
   (`requests: {memory: "100Gi"}`).
4. **Service without endpoints:** you already did 11.5 — recreate it from
   memory in under a minute.

**Verify:** for each: which command revealed the cause, and what was the exact
Event/log line? (Write them down — these four cover ~80% of real K8s tickets.)

## Exercise 11.8 — Namespaces

1. Create namespaces `dev` and `staging`; deploy the whoami stack into both
   (same YAML, `-n` flag).
2. From a debug pod in `dev`: reach `whoami-svc` (short name) and then the
   staging one by FQDN (`whoami-svc.staging.svc.cluster.local`).
3. `kubectl get pods -A | grep whoami` — see the parallel worlds.
4. Delete the `dev` namespace and observe everything in it vanish.

**Verify:** short names resolve within a namespace; cross-namespace needs the
qualified name; namespace deletion is a mass-delete (respect it).

---

**Keep the cluster and the whoami/visits YAML** — chapter 12 builds directly on them.
