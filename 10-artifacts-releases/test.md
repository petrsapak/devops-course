# Chapter 10 — Test

15 questions. Passing: 12/15.

---

**Q1.** In SemVer, what does each of MAJOR, MINOR, PATCH promise to consumers?

**Q2.** A client pins your library as `^1.3.0`. You ship `1.4.0` which renames a
public function. What did you violate and what version should the rename have been?

**Q3.** Why must released versions be immutable, and what is the correct action
when `2.4.1` turns out to be broken?

**Q4.** With Conventional Commits, what release bump results from a history of:
three `fix:`, one `feat:`, one `chore:`? And if one commit had a
`BREAKING CHANGE:` footer?

**Q5.** Name three functions an enterprise artifact repository
(Nexus/Artifactory/Harbor) provides beyond "storing files".

**Q6.** Explain "promotion" of an artifact and why it never involves rebuilding.

**Q7.** Two images were built from the identical commit, one at 10:00 and one at
10:05. Are their digests equal? What does this imply for the "build once" rule?

**Q8.** During a rolling update, what compatibility constraint exists that a
recreate deployment doesn't have? Give a concrete example of violating it.

**Q9.** Compare blue-green and canary on: capacity cost, rollback speed, blast
radius, and what infrastructure each additionally requires.

**Q10.** "Deploy" vs "release" — define the distinction and name the mechanism
that separates them.

**Q11.** A newly launched feature is corrupting some users' data. Rank these
responses by expected MTTR and state your first action: (a) roll back the
deployment, (b) fix forward, (c) flip the feature's flag off.

**Q12.** Why can't you ship a column rename as one release in a zero-downtime
world? Name the pattern and its three phases.

**Q13.** In expand–migrate–contract, why must migrations run *before* the new
code deploys, and what property must every migration have relative to the
currently-running version?

**Q14.** List four properties of a rollback capability that "actually works at 3 a.m."

**Q15.** Design: 200 instances, high traffic, mature Prometheus monitoring,
leadership is deeply regression-averse, budget won't cover 2× capacity. Choose a
deployment strategy, justify it, and name the automation class that runs it.

---

<details>
<summary><b>Answer key</b></summary>

1. MAJOR: breaking changes — consumer action required. MINOR: new features,
   backward compatible. PATCH: bug fixes only, no interface change.
2. SemVer's core contract — breaking change in a MINOR. `^1.3.0` accepts any
   1.x ≥ 1.3, so clients auto-upgraded into breakage. It should have been `2.0.0`.
3. Reproducibility and trust: the same version must always mean the same bytes
   (debugging, audits, rollbacks depend on it). Broken release → ship `2.4.2`;
   never republish `2.4.1`.
4. `feat:` wins → MINOR bump. With a breaking footer → MAJOR.
5. Proxy/cache of public registries (availability + policy choke point);
   retention/cleanup rules; promotion/staging model; access control and audit;
   vulnerability scanning integration. (Any three.)
6. Adding a new label (tag) or copying to a prod repo for *already-built,
   already-tested* bytes. Rebuilding would produce a different artifact than the
   one validated — invalidating every test that gated the promotion.
7. Almost certainly not equal — timestamps and layer metadata differ. Hence
   equality of source ≠ equality of artifact, which is precisely why you promote
   the artifact instead of rebuilding "the same" code.
8. Old and new versions serve traffic simultaneously, so they must be mutually
   compatible: shared DB schema, API/message formats, session state. Example:
   new code writes a session format old code can't read → users bounce between
   versions and get logged out/errors.
9. Blue-green: 2× capacity, instant rollback (router switch back), blast radius
   = 100% at cutover (but validated first); needs a switchable router + duplicate
   environment. Canary: ~1.05× capacity, rollback = reroute the slice (fast),
   blast radius = the canary %; needs weighted routing + good metrics to judge.
10. Deploy: code is running on production infrastructure. Release: users
    experience it. Feature flags separate them (code deployed dark, released by
    flag flip).
11. (c) flag off — seconds, no deployment; then investigate. (a) minutes.
    (b) hours. First action: flip the flag (and (a) becomes fallback if the flag
    doesn't isolate it).
12. During any zero-downtime strategy, old code still runs while new code
    arrives; a rename instantly breaks the old version (and breaks rollback
    after). Pattern: expand–migrate–contract — add new alongside old, backfill
    and dual-write/read, then drop the old once nothing references it.
13. Code must never arrive before the schema it needs (new code + old schema =
    crash on startup or first query). Every migration must be backward
    compatible with the *currently running* code — because that code keeps
    serving during, and possibly after (rollback), the migration.
14. Previous artifacts retained and pullable; single automated command/click
    (same tooling as deploy); schema compatibility guaranteed by migration
    discipline; rehearsed regularly in lower environments; monitored so you know
    the rollback *worked*.
15. Canary. It avoids 2× capacity (rules out blue-green), minimizes blast radius
    for the regression-averse leadership, and the mature metrics enable
    automated judgment. Automation class: progressive delivery controllers
    (Argo Rollouts, Flagger) that shift weights and auto-abort on metric regression.

</details>

**Scoring:** 12+ → [Chapter 11](../11-kubernetes-fundamentals/lesson.md). Below →
redo exercises 10.4, 10.5, 10.8 — promotion, cutover mechanics, and schema
discipline are the load-bearing skills.
