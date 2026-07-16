# Chapter 01 — Test

15 questions. Passing score: 12/15. Answers at the bottom — no peeking until done.

---

**Q1.** Which statement best captures the core idea of DevOps?
- a) Developers take over all operations work
- b) A dedicated team handles the pipeline between dev and ops
- c) Shared ownership of the full lifecycle, enabled by automation and fast feedback
- d) Replacing manual testing with automated testing

**Q2.** In CALMS, the "L" stands for Lean. Which practice is the best example of it?
- a) Writing runbooks for every service
- b) Working in small batches and limiting work-in-progress
- c) Running a blameless post-mortem
- d) Measuring deployment frequency

**Q3.** Name the four DORA metrics. (Write them out.)

**Q4.** Which pair of DORA metrics measures *stability*?
- a) Deployment frequency & lead time
- b) Change failure rate & time to restore service
- c) Lead time & change failure rate
- d) Deployment frequency & time to restore

**Q5.** True or false: DORA research shows teams must trade deployment speed for stability.

**Q6.** A team deploys once a quarter in a weekend-long event that fails about half
the time. According to DevOps thinking, the *root cause* of the failures is most likely:
- a) Insufficiently skilled operations staff
- b) The enormous batch size and infrequency of the releases
- c) Lack of a change advisory board
- d) Developers not writing enough documentation

**Q7.** Define "lead time for changes" precisely.

**Q8.** What is the difference between Continuous Delivery and Continuous Deployment?

**Q9.** The "First Way" of DevOps is about:
- a) Feedback loops
- b) Flow of work from left to right across the whole value stream
- c) Experimentation and learning
- d) Automation of infrastructure

**Q10.** Why is "build the artifact once, promote the same artifact through
environments" considered a golden rule?

**Q11.** Which of these is an anti-pattern?
- a) A platform team building self-service deployment tooling
- b) A DevOps team that performs deployments on behalf of dev teams via tickets
- c) Developers being on call for their own services
- d) Automated rollback on failed health checks

**Q12.** What property must automation scripts have so that re-running them is safe? Name and define it.

**Q13.** "Shift left" means:
- a) Moving deployments to earlier in the week
- b) Moving testing and security checks earlier in the pipeline
- c) Prioritizing features over tech debt
- d) Migrating from cloud back to on-premises

**Q14.** In a blameless post-mortem, what replaces "who made the mistake?" as the central question?

**Q15.** A change made it to production and caused an outage. Fixing forward took
4 hours because the deploy process is manual. Which DORA metric does the 4 hours
directly measure, and name one investment that would improve it.

---

<details>
<summary><b>Answer key</b></summary>

1. **c**
2. **b**
3. Deployment frequency; lead time for changes; change failure rate; time to
   restore service (MTTR).
4. **b**
5. **False** — elite teams are better at both; the practices reinforce each other.
6. **b**
7. The time from a commit (change committed to version control) until that change
   is running in production.
8. Delivery: every change is *releasable*, a human decides when to release.
   Deployment: every passing change is released *automatically*, no human gate.
9. **b**
10. Because rebuilding per environment can produce a different binary (different
    dependencies, flags, timestamps), invalidating everything you tested. Promoting
    one immutable artifact guarantees what you tested is what runs in production.
11. **b** (a ticket-driven DevOps team is a new silo; the others are healthy practices)
12. **Idempotency** — running the operation multiple times yields the same result
    as running it once.
13. **b**
14. "What about our *system* allowed this to happen, and how do we change the
    system so it can't (or fails safely)?" — focus on systemic causes and fixes,
    not individuals.
15. **Time to restore service (MTTR).** Investments: automated deployment/rollback,
    one-click rollback to previous artifact, health-check-driven auto-rollback,
    better monitoring to detect and localize faster.

</details>

**Scoring:** 12+ correct → proceed to [Chapter 02](../02-linux-and-shell/lesson.md).
Below 12 → re-read the weak sections, redo exercises 1.2 and 1.4, retake in a day.
