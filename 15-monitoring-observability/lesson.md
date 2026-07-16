# Chapter 15 — Monitoring & Observability

## Learning objectives

1. Distinguish monitoring from observability; know the three pillars (metrics, logs, traces).
2. Run Prometheus: scraping, PromQL, instrumenting an app with metrics.
3. Build Grafana dashboards that answer questions (RED/USE methods).
4. Centralize logs (Loki) and understand structured logging.
5. Design alerts that wake people only for real problems; know SLO-based alerting.

---

## 1. Monitoring vs observability, and the three pillars

- **Monitoring:** watching for *known* failure modes ("is CPU > 90%?", "is the
  health check failing?"). You decided in advance what to look at.
- **Observability:** can you answer *new* questions about the system from its
  outputs without shipping new code? "Why are checkouts from Austria slow since
  14:00?" was never a dashboard — an observable system lets you interrogate it.

The three pillars, and the question each answers:

| Pillar | Shape | Answers | This course's tool |
|--------|-------|---------|--------------------|
| **Metrics** | numbers over time, cheap, aggregated | *what* is happening, trends, alerting | Prometheus |
| **Logs** | timestamped events, rich detail | *why* — the specific error, the stack trace | Loki (+ the ELK alternative) |
| **Traces** | one request's journey across services, timed spans | *where* — which hop in a distributed path is slow/failing | OpenTelemetry (+ Jaeger/Tempo) |

The workflow they form: metric alerts you (*checkout error rate 5%*) → logs
explain it (*payment timeout to provider X*) → traces localize it in a
multi-service path (*the 8s is inside the fraud-check call*). In this chapter you
build the first two hands-on; traces are covered conceptually (they require
multi-service apps to mean much — a capstone stretch goal).

## 2. Prometheus — metrics

### The model

Prometheus **pulls** ("scrapes") `GET /metrics` from your services every N
seconds and stores time series. A series = metric name + **labels**:

```
http_requests_total{method="GET", path="/visits", status="200"}  1027
```

Labels are the superpower and the danger: every label combination = a new
series. Label by `status`, `path` (bounded sets) — never by user ID or request
ID (unbounded = "cardinality explosion", the classic way to kill a Prometheus).

Metric types:

- **Counter** — only goes up (requests served, errors). Query its *rate*.
- **Gauge** — goes up and down (memory in use, queue depth, in-flight requests).
- **Histogram** — observations in buckets (request duration) → enables
  percentiles ("p99 latency").

### Instrumenting the visits app

```python
# pip install prometheus-client
from prometheus_client import Counter, Histogram, generate_latest
import time

REQUESTS = Counter("app_requests_total", "Requests", ["path", "status"])
LATENCY = Histogram("app_request_seconds", "Request duration", ["path"])

@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": "text/plain"}

# wrap handlers (Flask: before/after_request):
@app.before_request
def _start():
    request._t0 = time.monotonic()

@app.after_request
def _observe(resp):
    LATENCY.labels(request.path).observe(time.monotonic() - request._t0)
    REQUESTS.labels(request.path, resp.status_code).inc()
    return resp
```

Beyond your app: **exporters** translate existing systems into /metrics —
`node_exporter` (host CPU/mem/disk), `postgres_exporter`, `cadvisor`
(containers), `blackbox_exporter` (probes URLs — your ch 04 cert-expiry check,
productized). In Kubernetes, the `kube-prometheus-stack` Helm chart deploys the
whole ecosystem with service discovery — pods get scraped automatically via
annotations.

### Scrape config (the lab compose version)

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: visits
    static_configs:
      - targets: ["api:8000"]
  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]
```

### PromQL — the queries that matter

```promql
# request rate per second, averaged over 5m (THE workhorse):
rate(app_requests_total[5m])

# error RATIO (not count — ratios survive traffic changes):
sum(rate(app_requests_total{status=~"5.."}[5m]))
  / sum(rate(app_requests_total[5m]))

# p99 latency from a histogram:
histogram_quantile(0.99, sum(rate(app_request_seconds_bucket[5m])) by (le))

# aggregate by label:
sum(rate(app_requests_total[5m])) by (path)

# gauge, right now:
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
```

The pattern to internalize: **counters are always wrapped in `rate()`** — the
raw total is meaningless; the per-second rate is the signal. And prefer ratios
to absolutes (5 errors/s is terrible at 10 req/s, noise at 10k req/s).

## 3. What to measure: RED and USE

Two checklists that turn "what should the dashboard show?" from art to procedure:

- **RED — for services** (request-driven things):
  **R**ate (req/s), **E**rrors (failed/s, as a ratio), **D**uration (latency
  percentiles — p50, p95, p99; averages lie, one 30s outlier hides in them).
- **USE — for resources** (CPUs, disks, queues, pools):
  **U**tilization (% busy), **S**aturation (queued work — load average, queue
  depth, connection-pool waiters), **E**rrors.

A service dashboard = RED for the service + USE for its critical resources +
current deploy version annotated. That's it; everything else is supporting cast.

**The four golden signals** (Google SRE) = RED + saturation — same idea, four words:
latency, traffic, errors, saturation.

## 4. Grafana — dashboards

Grafana visualizes data sources (Prometheus, Loki, many more). Practice beats
prose here (the exercises build one), so just the principles:

- **A dashboard answers a question**, top-left first: "is the service healthy?"
  → RED row on top, resources below, details at the bottom.
- Percentiles over averages; ratios over counts; rate() over raw counters.
- **Variables** (`$env`, `$service`) make one dashboard serve all environments.
- Import community dashboards by ID (e.g., Node Exporter Full = 1860) — then
  learn by reading their queries.
- Annotate deploys (CI can POST an annotation) — half of all incidents line up
  with a deploy marker, and seeing it saves the first 15 minutes of confusion.

## 5. Logs — centralized and structured

### Structured logging (the app-side half)

```
BAD:  "Payment failed for order 12345 after 3 retries"
GOOD: {"level":"error", "msg":"payment failed", "order_id":"12345",
       "retries":3, "provider":"stripe", "trace_id":"abc..."}
```

JSON logs turn grep into queries: *all payment errors, by provider, last hour*.
Rules: log to **stdout** (ch 05 — the collector's contract), one JSON object per
line, include correlation IDs (trace_id/request_id) so logs join with traces,
never log secrets/PII (ch 16 will insist).

### Loki — the lab log stack

Loki = "Prometheus for logs": indexes only labels (job, container, level), not
full text — cheap to run, queried with **LogQL** in the same Grafana:

```logql
{job="visits"} |= "error"                        # grep-like
{job="visits"} | json | level="error"            # parse JSON, filter fields
sum(rate({job="visits"} | json | level="error" [5m]))   # logs → metrics!
```

Collection: **Promtail**/**Alloy** agent tails container stdout and ships to
Loki (in K8s: a DaemonSet — one collector pod per node reads all pod logs).
The heavyweight alternative you'll meet in enterprises: **ELK/EFK**
(Elasticsearch + Logstash/Fluentd + Kibana) — full-text indexing, more power,
much more cost/ops.

## 6. Alerting — the discipline

The iron law: **every page must be actionable and urgent.** Alerts nobody acts
on train responders to ignore alerts ("alert fatigue") — then the real one
scrolls by unread. Symptoms over causes: page on "error ratio > 2% for 5m"
(users are hurting) — not on "CPU > 80%" (maybe fine, maybe not; it's a
dashboard line, not a page).

Prometheus alert rule:

```yaml
groups:
  - name: visits
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(app_requests_total{status=~"5.."}[5m]))
            / sum(rate(app_requests_total[5m])) > 0.02
        for: 5m                    # must be true 5 minutes — kills flappy pages
        labels:
          severity: page
        annotations:
          summary: "Error ratio {{ $value | humanizePercentage }} on visits"
          runbook_url: "https://wiki/runbooks/visits-errors"
```

**Alertmanager** (routing layer): groups related alerts, routes by severity
(page → PagerDuty/phone; warn → Slack), silences during maintenance, inhibits
downstream noise ("node down" suppresses that node's 30 container alerts).

Every alert carries a **runbook link** — 3 a.m. responders execute checklists,
not epiphanies.

### SLO-based alerting (the modern standard, brief but load-bearing)

- **SLI** — a measured indicator: "% of requests < 300ms and non-5xx".
- **SLO** — the target: "99.9% over 30 days".
- **Error budget** — the allowed failure: 0.1% ≈ 43 min/month. Spend it on
  releases and experiments; when it's exhausted, stability work takes priority
  over features. This turns "is it reliable enough?" from opinion war to arithmetic.
- Alert on **burn rate**: "at this error rate, the month's budget is gone in
  6 hours" → page. Slow burn → ticket, not page. (Ch 16 picks SLOs back up.)

## 7. The lab stack (exercises build this)

One compose file: visits app (instrumented) + Prometheus + Grafana + Loki +
Promtail + node-exporter — a complete observability stack on your laptop,
the same architecture (minus scale) as production setups.

```
app /metrics ──scrape── Prometheus ──datasource── Grafana ──also── Loki
app stdout ───tail───── Promtail ──push── Loki          Alertmanager ← rules
```

## Further reading

- prometheus.io/docs — concepts + PromQL basics.
- Google SRE book (sre.google/books, free): "Monitoring Distributed Systems",
  "Alerting on SLOs".
- grafana.com/docs — Loki "Getting started".

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 16: DevSecOps & SRE](../16-devsecops-sre/lesson.md)
