# Chapter 01 — Exercises

These are analysis exercises (the hands-on tooling starts in chapter 02). Write your
answers down — the act of writing exposes gaps that reading hides.

---

## Exercise 1.1 — Map your current project

Take a project you work on (or worked on last).

1. Draw its path from "developer commits code" to "users run it" — every step,
   including manual ones (email to release manager? someone copies files?).
2. Mark each step **A** (automated) or **M** (manual).
3. Estimate the total lead time (commit → production).

**Verify:** you should have at least 5 steps. If you drew fewer, you're missing
steps (code review? testing? approval? the actual deploy? smoke check after?).

## Exercise 1.2 — Score it with DORA

For the same project, estimate all four DORA metrics:

- Deployment frequency: ______
- Lead time for changes: ______
- Change failure rate: ______
- Time to restore: ______

Then classify the team (elite / high / medium / low) using the table in the lesson.

**Verify:** sanity-check the pairing — if you wrote "deploys daily" but "lead time
3 weeks", one of the two numbers is wrong (daily deployment with 3-week lead time
means a huge queue of undeployed commits, which contradicts daily deploys of fresh work).

## Exercise 1.3 — Find the constraint

From your Exercise 1.1 diagram, identify the *single* step that most limits flow
(longest wait, most failures, or most manual effort). Propose one concrete
automation for it and predict which DORA metric(s) it would improve.

**Verify:** your proposal should name a specific mechanism ("add a CI job that runs
the test suite on every PR"), not a wish ("testing should be faster").

## Exercise 1.4 — CI vs CD vs CD

For each scenario, label it as CI only, Continuous Delivery, or Continuous Deployment:

1. Every merge to `main` triggers build + tests. Releases are cut manually every
   two weeks from whatever `main` contains.
2. Every merge to `main` produces a deployable artifact and updates staging; a
   product manager clicks "promote" to ship to production.
3. Every merge to `main` reaches production within 30 minutes with no human action.
4. Developers merge to `main` weekly after long-lived feature branches; a nightly
   job runs the tests.

**Verify:** answers at the bottom of this file.

## Exercise 1.5 — Anti-pattern spotting

A company creates a new "DevOps department." Developers file tickets to the DevOps
department to get things deployed. Deploys happen Tuesdays and Thursdays. The
department is very busy and proud of its 200-page deployment runbook.

List every anti-pattern you can find (there are at least four) and, for each, what
the healthier alternative looks like.

## Exercise 1.6 — Blameless post-mortem rewrite

Rewrite this incident summary in blameless form, focusing on systems instead of
individuals:

> "The outage happened because Marek deployed on Friday without running the tests.
> Marek has been reminded to always run tests."

**Verify:** your version should (a) not depend on any person "being more careful,"
(b) propose at least one systemic change that makes the failure impossible or
much less likely, e.g. a pipeline gate.

---

<details>
<summary><b>Answers for 1.4</b></summary>

1. **CI only** — integration is continuous, release is periodic and manual.
2. **Continuous Delivery** — always releasable, human pushes the button.
3. **Continuous Deployment** — no button.
4. **None / not even CI** — weekly merges from long-lived branches with nightly
   tests is the anti-pattern CI was invented to fix. Integration isn't continuous.

</details>
