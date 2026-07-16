# Chapter 03 — Exercises

Work in `~/devops/ch03`. These exercises build a local playground repo — no GitHub
account needed until 3.7 (recommended: create a free one, you'll need it for ch 07 anyway).

```bash
mkdir -p ~/devops/ch03 && cd ~/devops/ch03
git init playground && cd playground
git config user.name "Your Name" && git config user.email "you@example.com"
```

---

## Exercise 3.1 — Atomic commits with `add -p`

1. Create `app.py`:
   ```python
   def greet(name):
       return "Hello " + name

   def farewell(name):
       return "Bye " + name
   ```
   Commit it as `Add greet and farewell`.
2. Now edit **both** functions in one go: make `greet` return `f"Hello, {name}!"`
   and `farewell` return `f"Goodbye, {name}."`.
3. Using `git add -p` (the `s` split option may help), create **two separate
   commits**, one per function change, with proper messages.

**Verify:** `git log --oneline` shows 3 commits; `git show HEAD` and
`git show HEAD~1` each touch only one function.

## Exercise 3.2 — Undo safari

Starting from your 3-commit repo:

1. Make a bad commit: add `debug.log` with junk, commit as `wip`.
2. Undo it but keep the file staged (`reset --soft`). Confirm with `git status`.
3. Commit again as `Add debug log`, then remove it properly with `git revert`.
   Inspect the history — what did revert add?
4. Now the recovery drill: `git reset --hard HEAD~2` (you just "lost" two commits).
   Use `git reflog` to find and restore them with `git reset --hard <sha>`.

**Verify:** after step 4, `git log --oneline` shows the same history as after
step 3. If reflog confused you, run it again and read the entries top-down — each
line is "where HEAD was".

## Exercise 3.3 — Merge conflict, both ways

1. `git switch -c feature/shout` — change `greet` to return the greeting uppercased. Commit.
2. `git switch main` (or `master`) — change the *same line* to add an exclamation
   mark. Commit.
3. `git merge feature/shout` → conflict. Resolve it so both behaviors combine
   (uppercase + exclamation), complete the merge.
4. Look at `git lg` (the graph alias). Note the merge commit.
5. Now repeat the scenario with **rebase**: make two new conflicting branches,
   but on the feature branch run `git rebase main`, resolve, `--continue`, then
   merge (it will fast-forward). Compare the resulting graph with step 4's.

**Verify:** you can articulate the difference the graph shows: merge → diamond
shape with merge commit; rebase → straight line.

## Exercise 3.4 — Interactive rebase cleanup

1. On a new branch, make 4 sloppy commits touching `README.md`: `wip`, `more wip`,
   `fix typo`, `actually works now`.
2. `git rebase -i main` and squash all four into a single commit with the message
   `Add project README`.

**Verify:** `git log --oneline` on the branch shows exactly one commit ahead of
main. `git show` displays the combined change.

## Exercise 3.5 — Tags and describe

1. Tag the current main as `v1.0.0` (annotated, with a message).
2. Make two more commits, then run `git describe --tags` and interpret the output.
3. Create `v1.1.0`, then list all tags matching `v1.*`.

**Verify:** `git show v1.0.0` displays tag metadata (tagger, date, message) *and*
the commit — that's how you know it's annotated, not lightweight.

## Exercise 3.6 — Pre-commit hook

1. Write `.git/hooks/pre-commit` (executable) that rejects any commit whose staged
   changes contain the string `password=`.
2. Test: try to commit a file containing `password=hunter2` → blocked. Remove the
   string → commit passes.
3. Prove the loophole: commit the bad file with `--no-verify`, then revert it.

**Verify:** step 3 is the lesson — local hooks are a convenience, not a control.
State where the *enforcing* version of this check must live.

## Exercise 3.7 — Full PR workflow on GitHub

Create a free GitHub account if needed, then:

1. Create a repo `devops-playground`, push your local playground to it.
2. Protect `main`: Settings → Branches → require a pull request before merging.
3. Branch `feat/status-endpoint`, add any small change, push, and open a PR with
   a proper description (what / why / how tested).
4. Try pushing directly to `main` — observe the rejection.
5. Merge the PR using **Squash and merge** and delete the branch.
6. Pull main locally and inspect the squashed commit.

**Verify:** `git log --oneline origin/main` shows one commit for the whole PR;
direct push in step 4 was rejected by the server.

## Exercise 3.8 — git bisect hunt

Build a repo with a hidden bug and find it by bisecting:

```bash
cd ~/devops/ch03 && git init bisect-lab && cd bisect-lab
for i in $(seq 1 20); do
  if [ "$i" -eq 13 ]; then echo "echo broken; exit 1" > check.sh
  else echo "echo ok; exit 0" > check.sh; fi
  git add check.sh && git commit -qm "commit $i"
done
```

Commit 13 introduced the "bug" (`check.sh` exits 1 from then on). Pretend you
don't know that:

1. Confirm HEAD is bad (`bash check.sh`), confirm the first commit is good
   (`git log --oneline | tail -1`).
2. Bisect manually (`git bisect start/bad/good`, testing each checkout with
   `bash check.sh`).
3. Reset, then do it again fully automated with `git bisect run bash check.sh`.

**Verify:** both approaches identify "commit 13" as the first bad commit, and the
manual hunt took you ~4–5 test steps (log₂ 20), not 20.

---

**Stretch goal:** install the `pre-commit` framework, configure
`.pre-commit-config.yaml` with `shellcheck` for shell scripts, and make it run on
your playground repo.
