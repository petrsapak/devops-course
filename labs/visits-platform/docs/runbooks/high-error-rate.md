# HighErrorRate runbook

1. Confirm the error ratio and affected paths on the Visits API dashboard.
2. Check for a deployment annotation immediately before the increase.
3. Query `{job="visits-api"} | json | level="error"` in Loki.
4. Check database readiness and saturation.
5. If a recent release caused the errors, revert the GitOps image-tag commit.
6. Record detection, mitigation, and recovery times in the incident timeline.

Escalate when user-visible errors continue for ten minutes after mitigation or
when data integrity may be affected.
