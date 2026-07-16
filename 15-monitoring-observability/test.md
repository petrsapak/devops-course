# Chapter 15 — Test

15 questions. Passing: 12/15.

---

**Q1.** Monitoring vs observability — define the distinction in terms of known
vs unknown questions.

**Q2.** Name the three pillars and, for a live incident, the question each answers.

**Q3.** Counter vs gauge vs histogram — one example metric each, and which one
enables percentile latency.

**Q4.** Why is `app_requests_total` alone useless on a dashboard, and what do
you plot instead?

**Q5.** Your teammate adds a `user_id` label to the request counter. What
happens, why, and what's the rule they broke?

**Q6.** Write the PromQL for: 5xx error *ratio* over the last 5 minutes. Why is
a ratio preferred over an absolute error rate for alerting?

**Q7.** Expand RED and USE, and state which applies to a payment API vs a
database connection pool.

**Q8.** Average latency is 120ms and steady, yet users complain about
multi-second hangs. Explain how both can be true and what to plot instead.

**Q9.** What does structured (JSON) logging enable that plain-text logging
doesn't? Name two rules for good structured logs.

**Q10.** How does Loki's indexing model differ from Elasticsearch's, and what's
the operational consequence?

**Q11.** What is the purpose of the `for:` clause in an alert rule, and what
failure mode does omitting it cause?

**Q12.** "Page on symptoms, not causes." Explain, with "CPU > 80%" vs
"p99 > 2s for 5m" as the example. What belongs on each side?

**Q13.** Name three things Alertmanager does that Prometheus alert rules alone don't.

**Q14.** Define SLI, SLO, and error budget with one linked example. What does an
exhausted error budget change about the team's priorities?

**Q15.** Incident walkthrough: the HighErrorRate alert fires for the visits
service. Give your first four investigative moves, in order, naming the pillar
each uses.

---

<details>
<summary><b>Answer key</b></summary>

1. Monitoring watches for pre-defined, known failure modes (dashboards and
   alerts you set up in advance). Observability is the system property that
   lets you answer questions you *didn't* anticipate, from existing telemetry,
   without deploying new code.
2. Metrics — *what* is wrong (error ratio up, latency up). Logs — *why* (the
   actual error message/stack). Traces — *where* in a multi-service request
   path (which hop is slow/failing).
3. Counter: `http_requests_total` (only increases). Gauge: `queue_depth` /
   memory in use (up and down). Histogram: request duration in buckets — the
   one enabling percentiles (`histogram_quantile`).
4. It's a monotonically growing total — its value depends on process uptime.
   Plot `rate(app_requests_total[5m])` — the per-second rate is the signal.
5. Every distinct user creates a new time series per label combo — cardinality
   explosion: memory/storage blowup and possibly a dead Prometheus. Rule:
   labels only from small bounded sets (status, method, path), never unbounded
   IDs.
6. ```promql
   sum(rate(app_requests_total{status=~"5.."}[5m]))
     / sum(rate(app_requests_total[5m]))
   ```
   Ratios stay meaningful as traffic changes: 5 err/s is catastrophic at
   10 req/s and noise at 10k req/s — absolute thresholds can't be tuned for both.
7. RED: Rate, Errors, Duration — for request-serving services → the payment
   API. USE: Utilization, Saturation, Errors — for resources → the connection
   pool (busy %, waiters queued, connection errors).
8. Averages hide tail latency: 99 requests at 100ms + 1 at 5s barely moves the
   mean. The complainers live in the tail. Plot percentiles — p95/p99 — which
   represent the worst experiences directly.
9. Logs become queryable data: filter/aggregate by field (all errors for
   provider=stripe last hour) instead of regex archaeology; logs can even be
   turned into metrics. Rules: one JSON object per line to stdout; include
   correlation IDs (trace/request); consistent field names; never log
   secrets/PII. (Any two.)
10. Loki indexes only labels (job, container, level) and stores log bodies
    compressed-unindexed; Elasticsearch full-text-indexes everything.
    Consequence: Loki is far cheaper/simpler to run but body searches scan;
    ELK offers powerful search at significant infra and ops cost.
11. The condition must hold continuously for that duration before firing —
    it filters transient blips. Without it, a single flapping scrape or one bad
    request pages someone, breeding alert fatigue.
12. Symptoms = user-visible harm (error ratio, latency SLI breaches) — these
    page. Causes (CPU, memory, disk) may or may not hurt users — they belong on
    dashboards and maybe tickets. High CPU with normal p99 is a non-event;
    paging on it trains people to ignore pages.
13. Grouping (one notification for N related alerts), routing by
    labels/severity to different receivers (pager vs Slack), silences
    (maintenance windows), inhibition (suppress downstream alerts when the
    upstream cause already fired).
14. SLI: measured indicator — % of requests non-5xx under 300ms. SLO: target —
    99.9% over 30 days. Error budget: the complement — 0.1% (~43 min/month) of
    allowed failure. Exhausted budget → feature work yields to reliability work
    (freeze risky deploys, fix the sources of burn) by prior agreement, not
    negotiation-during-incident.
15. (1) Open the service dashboard: confirm the error ratio, check rate and
    duration for shape (metrics). (2) Check for a deploy annotation / recent
    release at the inflection point (metrics + change context — most incidents
    are deploys). (3) Query error logs for the window
    (`| json | level="error"`) to get the actual exception (logs). (4) Check
    the dependency implicated by the errors (DB up? — targets/USE panels or
    trace the failing path) and roll back / flag off if a deploy lines up
    (ch 10 decision).

</details>

**Scoring:** 12+ → [Chapter 16](../16-devsecops-sre/lesson.md). Below → redo
exercises 15.3, 15.5, 15.8 — dashboards, alert lifecycle, and the on-call drill
are the practice that makes this real.
