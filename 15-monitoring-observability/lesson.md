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

> **Field by field:** `scrape_interval: 15s` — how often Prometheus pulls each target · `job_name` — becomes the `job` label on every series collected, your primary who-is-this dimension · `static_configs.targets` — host:port list to scrape (`http://api:8000/metrics` implied; the hostnames are Compose service names because the whole lab stack shares a network — ch 06). In Kubernetes this static list is replaced by *service discovery*, but the scrape model is identical. Verify targets under the Prometheus UI's **Status → Targets** page: every row should say `UP`, and a `DOWN` row shows the exact scrape error.

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

> **Query by query** (type these into Prometheus's web UI, the *Graph* tab — or later into Grafana panels; PromQL is the same everywhere):
> - `rate(app_requests_total[5m])` — `[5m]` selects each series' last 5 minutes of samples (a *range*); `rate()` computes the per-second increase over that window, automatically handling counter resets on restarts. Result: one req/s value **per label combination** — every path/status pair separately.
> - The error ratio — dissect it inside-out: `app_requests_total{status=~"5.."}` filters series by label, `=~` meaning regex-match (`5..` = 500–599); `rate(...[5m])` turns both numerator and denominator into per-second rates; `sum(...)` collapses the label combinations into single totals; the division yields a 0–1 fraction. Expect `0.021` = 2.1% of requests failing.
> - `histogram_quantile(0.99, sum(rate(app_request_seconds_bucket[5m])) by (le))` — histograms expose per-bucket counters (`_bucket` series, labeled `le=` "less than or equal"); `rate` + `sum by (le)` computes recent traffic per bucket while *keeping* the bucket label (that's what `by (le)` preserves — `histogram_quantile` needs it); the function then interpolates the 99th percentile. Read as: "the latency 99% of recent requests beat".
> - `sum(...) by (path)` — aggregate but keep one dimension: one req/s number per path. `by` is PromQL's GROUP BY.
> - The memory line — gauges need no `rate()`; dividing two gauges gives the available-memory fraction right now.

The pattern to internalize: **counters are always wrapped in `rate()`** — the
raw total is meaningless; the per-second rate is the signal. And prefer ratios
to absolutes (5 errors/s is terrible at 10 req/s, noise at 10k req/s).

### Recording rules — precompute the expensive queries

That `histogram_quantile` expression is too costly to re-evaluate on every
dashboard refresh and every alert-rule check. **Recording rules** run a query
on a schedule and save the result as a new, cheap series:

```yaml
# rules.yml (loaded via rule_files: in prometheus.yml)
groups:
  - name: visits-recording
    interval: 30s
    rules:
      - record: job:app_error_ratio:rate5m
        expr: |
          sum(rate(app_requests_total{status=~"5.."}[5m]))
            / sum(rate(app_requests_total[5m]))
      - record: job:app_latency_p99:rate5m
        expr: histogram_quantile(0.99, sum(rate(app_request_seconds_bucket[5m])) by (le))
```

> **How to read it:** each rule evaluates `expr` every `interval` and stores the result under the name in `record:`. The odd-looking name is the naming convention `level:metric:operations` — `job:app_error_ratio:rate5m` = "aggregated to job level, the error ratio, computed as a 5-minute rate". Dashboards and alert rules then query the *recorded* series (`job:app_error_ratio:rate5m > 0.02`): instant reads, and — at least as important — **one shared definition of "error ratio"** instead of five subtly different copies pasted across panels and alerts.

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

> **LogQL, line by line** (typed into Grafana's *Explore* view with Loki selected):
> - `{job="visits"}` — the *stream selector*: which labeled log streams to read. Always required, always first — this is the indexed part, so tight selectors = fast queries.
> - `|= "error"` — line filter: keep lines containing the substring (`!=` excludes; `|~` takes a regex). Exactly grep, running server-side over the selected streams.
> - `| json` — parse each line as JSON, turning its fields into queryable labels; `| level="error"` then filters on a parsed field. Substring-match vs field-match is the structured-logging payoff from §5 made tangible: no more matching the word "error" inside a URL by accident.
> - `sum(rate(... [5m]))` — PromQL-style functions over log streams: errors *per second*, graphable and alertable. You've turned logs into a metric without instrumenting anything — the trick for code you can't modify.

Collection: **Grafana Alloy** tails container stdout and ships it to Loki (in
K8s: a DaemonSet — one collector pod per node reads all pod logs). Older
examples use Promtail, but it reached end of life in March 2026 and was removed
from Loki; use Alloy for new work.
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

> **Field by field:** `alert:` the name that shows up in pages · `expr:` any PromQL returning a value — the alert *fires* while the expression is true (here: §2's error-ratio query against a 2% threshold) · `for: 5m` — the condition must hold continuously for 5 minutes before firing; this single line kills the flapping alerts that a momentary blip would cause · `labels:` routing metadata — Alertmanager's rules match on `severity: page` to decide pager-vs-Slack · `annotations:` human-facing text; `{{ $value | humanizePercentage }}` templates the current expression value into the message (`Error ratio 3.4% on visits`), and `runbook_url` is the 3 a.m. lifeline discussed below. The file loads via `rule_files:` in `prometheus.yml`; check status under the UI's *Alerts* tab (green inactive / yellow pending — inside the `for` window / red firing).

**Alertmanager** (routing layer): groups related alerts, routes by severity
(page → PagerDuty/phone; warn → Slack), silences during maintenance, inhibits
downstream noise ("node down" suppresses that node's 30 container alerts).
Its config makes those words concrete:

```yaml
# alertmanager.yml
route:
  receiver: slack-warnings            # default destination
  group_by: [alertname, service]      # bundle related firings into one notification
  routes:
    - matchers: [severity = "page"]
      receiver: pagerduty             # only severity=page reaches a phone

receivers:
  - name: slack-warnings
    slack_configs:
      - channel: "#alerts"
  - name: pagerduty
    pagerduty_configs:
      - routing_key: <secret-from-pagerduty>

inhibit_rules:
  - source_matchers: [alertname = "NodeDown"]
    target_matchers: [severity = "warning"]
    equal: [instance]                 # same instance → suppress the small alerts
```

> **Field by field:** `route` is a decision tree walked top-down — an alert's labels are tested against the child `routes:`, falling through to the default `receiver` when nothing matches. This is where the alert rule's `severity: page` label becomes pager-vs-Slack reality — the label was *routing metadata* all along · `group_by` batches alerts sharing those label values into one notification: 30 pods failing = one message listing 30, not 30 pages · `receivers` are named delivery endpoints (Slack, PagerDuty, email, generic webhook) · `inhibit_rules` encode "the big alert silences its consequences": while `NodeDown` fires for an instance, warnings from that same `instance` (the `equal:` join key) are suppressed — the responder sees the cause, not the 30 symptoms.

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
Alloy + node-exporter — a complete observability stack on your laptop,
the same architecture (minus scale) as production setups.

```
app /metrics ──scrape── Prometheus ──datasource── Grafana ──also── Loki
app stdout ───tail───── Alloy ─────push── Loki          Alertmanager ← rules
```

## Further reading

- prometheus.io/docs — concepts + PromQL basics.
- Google SRE book (sre.google/books, free): "Monitoring Distributed Systems",
  "Alerting on SLOs".
- grafana.com/docs — Loki "Getting started".

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| SLI | Service Level Indicator | The measured signal, e.g. "% of requests <300ms and non-5xx" |
| SLO | Service Level Objective | The target for that indicator, e.g. "99.9% over 30 days" |
| RED | Rate, Errors, Duration | Checklist for what to dashboard on a request-driven service |
| USE | Utilization, Saturation, Errors | Checklist for what to dashboard on a resource (CPU, disk, queue) |
| PII | Personally Identifiable Information | Data that must never be written to logs |
| ELK / EFK | Elasticsearch + Logstash/Fluentd + Kibana | The heavyweight full-text log stack, alternative to Loki |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 16: DevSecOps & SRE](../16-devsecops-sre/lesson.md)
