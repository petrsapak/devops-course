# TargetDown runbook

1. Identify whether `visits-api` or `visits-worker` is down in Prometheus.
2. Check the target's container or pod state and recent events.
3. Inspect the last logs before termination.
4. Check readiness dependencies, especially PostgreSQL.
5. Restart only after capturing evidence; roll back if a release caused it.

This warning becomes page-worthy when both API replicas are unavailable or the
worker outage breaches its reporting freshness objective.
