# Chapter 03 — Test

15 questions. Passing: 12/15.

---

**Q1.** A branch in Git is:
- a) A copy of all the files in the repository
- b) A movable pointer to a commit
- c) A diff against main
- d) A separate clone of the repository

**Q2.** You committed and pushed a bad change to the shared `main`. Which command
undoes it safely, and why is it the right choice over `git reset`?

**Q3.** What is the difference between `git diff` and `git diff --staged`?

**Q4.** When is it acceptable to rebase a branch? State the golden rule.

**Q5.** Match the merge strategy to the description:
1. Squash & merge   2. Merge commit   3. Rebase & merge
- a) Every PR commit lands individually on main, history stays linear
- b) The whole PR becomes exactly one commit on main
- c) All PR commits land plus a commit with two parents tying histories together

**Q6.** Your teammate says "I did `git reset --hard` and lost a day's commits."
What do you tell them to run, and why does it usually work?

**Q7.** Explain trunk-based development in two sentences, and name the technique
that makes it possible to merge *incomplete* features to main.

**Q8.** Why are long-lived feature branches considered harmful from a DORA-metrics
point of view?

**Q9.** What is the difference between an annotated and a lightweight tag, and
which should you use for releases?

**Q10.** `git push origin v2.0.0` — why is this command necessary even after
`git push`?

**Q11.** A pre-commit hook blocks secrets from being committed. A developer runs
`git commit --no-verify`. What does this demonstrate about client-side hooks, and
where must the authoritative check live?

**Q12.** You have 500 commits between a known-good release and a broken HEAD, and
a script `test.sh` that exits 0/1. Give the exact commands to find the breaking
commit with minimal effort, and roughly how many test runs it takes.

**Q13.** Which Git events typically trigger: (a) a PR-validation pipeline,
(b) a staging deployment, (c) a versioned release pipeline?

**Q14.** A secret API key was committed and pushed three commits ago. A colleague
proposes committing a deletion of the file. Is the incident resolved? What is the
mandatory first response?

**Q15.** Write a well-formed commit message (subject + body) for this change:
"we increased the HTTP client timeout from 2s to 10s because the reporting service
sometimes takes 8s and users were seeing errors."

---

<details>
<summary><b>Answer key</b></summary>

1. **b**
2. `git revert <commit>` — it creates a new inverse commit instead of rewriting
   published history, so collaborators' clones stay consistent.
3. `git diff`: working directory vs staging area. `--staged`: staging area vs
   last commit (what would be committed right now).
4. Rebase only commits that haven't been shared — your own local/PR branch.
   Golden rule: never rebase commits others may have based work on.
5. 1→b, 2→c, 3→a
6. `git reflog` — it logs every previous HEAD position; find the pre-reset SHA
   and `git reset --hard <sha>`. Works because Git keeps unreachable commits for
   ~90 days before garbage collection.
7. Everyone merges small changes into `main` at least daily and `main` is kept
   releasable at all times. Feature flags let incomplete code ship dark
   (merged but disabled).
8. They increase batch size and delay integration → longer lead time, bigger
   riskier merges → higher change failure rate. They also make CI less meaningful
   because it tests unintegrated code.
9. Annotated tags are full objects with tagger, date, and message; lightweight
   tags are bare pointers. Use annotated for releases (auditable metadata,
   `git describe` prefers them).
10. Tags are not pushed by regular `git push`; they must be pushed explicitly
    (or with `--tags`).
11. Client-side hooks are advisory — trivially bypassed. The authoritative check
    belongs on the server side: CI status checks + branch protection (and/or
    server-side hooks).
12. `git bisect start; git bisect bad; git bisect good <good-sha>; git bisect run ./test.sh`
    — about log₂ 500 ≈ 9 runs.
13. (a) push to a feature branch / PR opened or updated; (b) merge/push to `main`;
    (c) pushing a version tag (`v*`).
14. Not resolved — the key lives in history forever and must be treated as
    compromised. Mandatory first step: **rotate/revoke the key immediately**;
    then optionally scrub history (filter-repo) and add secret scanning.
15. Example:
    ```
    Increase reporting client timeout to 10s

    The reporting service takes up to 8s under load; the previous 2s
    timeout caused user-facing errors on report pages. 10s covers the
    observed p99 with margin.
    ```
    (Imperative subject ≤ ~50 chars, blank line, body explains why.)

</details>

**Scoring:** 12+ → [Chapter 04](../04-networking/lesson.md). Below → redo
exercises 3.2, 3.3, 3.8; they train the mechanics the test probes.
