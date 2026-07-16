# Chapter 15 — Exercises

Work in `~/devops/ch15`. You'll assemble the full observability stack around the
visits app, then use it like an on-call engineer.

## Lab scaffold

`compose.yaml` services (build it up through the exercises):

- `api` — your visits app, now instrumented (15.1)
- `db` — postgres (as in ch 06)
- `prometheus` — `prom/prometheus`, config bind-mounted
- `grafana` — `grafana/grafana`, port 3000
- `loki` — `grafana/loki`
- `promtail` — `grafana/promtail`, with the Docker socket/log path mounted
- `node-exporter` — `prom/node-exporter`

(Official images all have compose examples in their docs — assembling this IS
exercise 15.2.)

---

## Exercise 15.1 — Instrument the app

1. Add `prometheus-client` metrics to the visits app per lesson §2: request
   counter (path, status labels) + latency histogram, exposed at `/metrics`.
2. Run locally, generate a few requests, and read `/metrics` raw. Find your
   counter, the histogram buckets (`_bucket`, `_sum`, `_count`), and Python's
   free process metrics.
3. Sanity-check cardinality: hit a nonexistent path 5 times — does a new label
   value appear per 404 path? If your before/after hooks label by raw
   `request.path`, what's the risk? Cap it (label 404s as path="other").

**Verify:** `/metrics` shows your series; you found and fixed a real cardinality
trap (unbounded 404 paths) before it found you.

## Exercise 15.2 — Assemble the stack

1. Write the compose file with api+db+prometheus+grafana+node-exporter.
   Prometheus scrapes `api:8000` and `node-exporter:9100` (config from lesson §2).
2. Up. Open Prometheus at `localhost:9090`: Status → Targets — both UP?
3. Generate traffic (`while true; do curl -s localhost:8000/visits >/dev/null; sleep 0.2; done`)
   and try the four workhorse queries from lesson §2 in the Prometheus UI
   (rate, error ratio, p99, sum by path).

**Verify:** both targets UP; `rate(app_requests_total[5m])` shows ~5 req/s from
your loop. Leave the traffic running for the rest.

## Exercise 15.3 — RED dashboard in Grafana

1. Add Grafana to compose (admin/admin), datasource: Prometheus
   (provisioning YAML or clicked — try provisioning, it's the IaC way).
2. Build a "Visits — Service" dashboard, top row RED:
   - Rate: `sum(rate(app_requests_total[5m]))`
   - Errors: the 5xx ratio (as a percentage, with thresholds green<1%<yellow<5%<red)
   - Duration: p50 + p95 + p99 from the histogram, one panel
3. Second row USE-ish: node CPU (from node-exporter — crib the query from
   dashboard 1860 if needed), memory available, and the api container's
   restart-relevant signal if you have cadvisor (optional).
4. Import dashboard **1860** (Node Exporter Full) by ID and skim how pros lay
   out panels; open any panel's query and read it.

**Verify:** with your traffic loop running, Rate shows the load; kill the DB
container (`docker compose stop db`) — watch Errors climb within a minute.
Restart it. You just watched an incident on your own dashboard.

## Exercise 15.4 — Structured logs + Loki

1. Convert the app's logging to JSON-per-line on stdout (Python: `json.dumps`
   in a logging formatter, or structlog) — include level, msg, path, status,
   and duration_ms.
2. Add loki + promtail to compose (promtail scraping Docker container logs —
   the grafana/promtail docs compose snippet does this).
3. Grafana → add Loki datasource → Explore:
   - `{container=~".*api.*"}` — raw stream
   - `| json | level="error"` — errors only (make some: stop the db again)
   - `sum(rate({container=~".*api.*"} | json | level="error" [5m]))` — logs as metrics
4. Add a "recent errors" logs panel to your dashboard, under the RED row.

**Verify:** the DB-stop incident now shows BOTH the error-ratio spike (metric)
and the actual psycopg connection error (log) on one screen — the
metrics-tell-you-what, logs-tell-you-why loop, closed.

## Exercise 15.5 — Alert rules + Alertmanager

1. Add `alertmanager` to compose; wire prometheus to it; give Alertmanager a
   trivial receiver (webhook to `httpbin` container or just the UI at :9093).
2. Rules file with two alerts:
   - `HighErrorRate`: 5xx ratio > 2% `for: 2m`, severity=page, with a
     runbook_url annotation.
   - `TargetDown`: `up == 0` for 2m, severity=warn.
3. Trigger #1 (stop the db, keep traffic flowing). Watch it: Prometheus →
   Alerts (pending → firing) → Alertmanager UI.
4. Silence it in Alertmanager for 1 hour (the maintenance-window move), then
   resolve the incident and watch it clear.
5. Answer in writing: why the `for: 2m`? What page would a 0-second `for`
   produce on a single flaky request?

**Verify:** you saw the full lifecycle: pending → firing → silenced → resolved,
and can defend duration windows against flappy paging.

## Exercise 15.6 — Percentiles vs averages (the lying-average demo)

1. Add an endpoint `/slow` that sleeps 3s, and hit it once every ~20 normal
   requests (adjust your traffic loop).
2. On the dashboard, panel with BOTH `avg` latency
   (`rate(app_request_seconds_sum[5m]) / rate(app_request_seconds_count[5m])`)
   and p99.
3. Compare: where does the 3s outlier show up clearly, and where does it almost
   vanish?

**Verify:** average barely moves; p99 screams. One sentence: which one is your
users' experience of "the site sometimes hangs"?

## Exercise 15.7 — SLO arithmetic (paper + one query)

Your SLO: 99.5% of requests succeed (non-5xx), 30-day window.

1. Compute the monthly error budget in request terms at 1M requests/month, and
   in downtime terms if failures come as full outages (minutes/month).
2. Write the PromQL for the SLI (success ratio over 30d):
   `1 - (sum(rate(app_requests_total{status=~"5.."}[30d])) / sum(rate(app_requests_total[30d])))`.
3. Burn-rate thinking: with 0.5% budget, an incident erring at 25% of requests
   burns how fast? How long until the month's budget is gone? Should the
   burn-rate alert page at once — or is this a slow-burn ticket?

**Verify:** 5,000 errors or ~216 min/month; at 25% error rate the budget dies
in ~7 hours — decidedly a page. You just did SLO math most teams hand-wave.

## Exercise 15.8 — On-call simulation (capstone drill)

Have tomorrow-you (or a script you write blind today) inject ONE of these,
then diagnose using ONLY Grafana (no docker CLI until you've named the culprit):

- stop the db
- `docker compose pause api` (hangs, doesn't die)
- add `&& sleep 2` inside the visits handler (latency, not errors)
- kill promtail (logs go dark — meta-incident!)

Write the incident timeline as you go: alert seen → dashboard observation →
hypothesis → log query → root cause.

**Verify:** you named the culprit from telemetry alone, and your timeline reads
like the post-mortems you'll write in ch 16.

---

**Keep the stack** — the capstone plugs the pipeline into it. `docker compose stop`
is enough.
