# Chapter 03 — Git & Collaboration Workflows

## Learning objectives

1. Use Git beyond the basics: interactive staging, rebase, cherry-pick, bisect, reflog.
2. Choose and defend a branching strategy (trunk-based vs GitHub Flow vs Git Flow).
3. Run a professional pull-request workflow: small PRs, useful reviews, protected branches.
4. Tag and version releases; understand how Git events *drive* CI/CD.
5. Automate checks with Git hooks.

Why this matters for DevOps: **Git is the trigger for everything.** Every pipeline
in chapters 07–09 starts from a push, a PR, or a tag. Sloppy Git habits produce
sloppy pipelines.

---

## 1. The mental model (fast recap, then deeper)

Git is a graph of **commits**; each commit is an immutable snapshot pointing at
its parent(s). Branches are just movable pointers to commits; `HEAD` is a pointer
to your current branch.

```bash
git log --oneline --graph --all --decorate   # learn to read this view; alias it
git alias: git config --global alias.lg "log --oneline --graph --all --decorate"
```

Three zones your changes move through:

```
working directory --(git add)--> staging area --(git commit)--> repository
```

Inspection commands you should reach for constantly:

```bash
git status
git diff              # working dir vs staging
git diff --staged     # staging vs last commit
git show <commit>     # what a commit changed
git blame file.py     # who last touched each line (and in which commit)
```

---

## 2. Commits that don't embarrass you

- **Atomic:** one logical change per commit. Fixing a bug *and* renaming variables
  = two commits.
- **Message format** (widely adopted convention):

```
Add retry with backoff to payment client

Payment API returns 429 under load; without retries checkout fails
for ~2% of users during peaks. Retries 3x with exponential backoff.
```

Rules: imperative subject line ≤ ~50 chars ("Add", not "Added"), blank line,
body explains **why** (the diff already shows *what*).

- **Conventional Commits** (used to automate changelogs & versioning in ch 10):
  `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `feat!: ...` (breaking).

Partial staging — commit only some of your changes:

```bash
git add -p            # interactively pick hunks: y/n/s(plit)/q
```

---

## 3. Undoing things — the safety toolbox

| Situation | Command | Safe on shared branches? |
|-----------|---------|--------------------------|
| Unstage a file | `git restore --staged file` | ✅ |
| Discard working-dir changes | `git restore file` | ⚠️ destroys local edits |
| Fix the last commit (message or content) | `git commit --amend` | ❌ rewrites history |
| Undo a pushed commit | `git revert <commit>` | ✅ creates an inverse commit |
| Move branch pointer back, keep changes staged | `git reset --soft HEAD~1` | ❌ |
| Move branch pointer back, discard everything | `git reset --hard HEAD~1` | ❌ dangerous |
| "I lost a commit!" | `git reflog` then `git reset --hard <sha>` | recovery tool |

**The rule:** on shared/pushed history use `revert` (adds a new commit). `reset`,
`amend`, and rebase rewrite history — fine on your own unpushed branches, hostile
on shared ones.

`git reflog` records every position HEAD has had — commits are almost never truly
lost for ~90 days. This turns most "I destroyed the repo" panics into a 30-second fix.

---

## 4. Merging vs rebasing

Two ways to integrate `main` into your feature branch:

```bash
git merge main     # ties histories together with a merge commit; true history
git rebase main    # replays your commits on top of main; linear history
```

- **Merge**: preserves what actually happened; graph gets busy.
- **Rebase**: clean linear story; but it *rewrites your commits* (new SHAs).

Golden rule of rebase: **never rebase commits that others may have based work on**
(i.e., pushed shared branches). Rebasing your own unpushed/PR branch is normal.

Interactive rebase — clean up a messy branch before review:

```bash
git rebase -i main
# editor opens: pick / squash / reword / drop per commit
```

Typical use: squash five "wip" commits into one meaningful commit before the PR.

Conflicts happen with both. Resolving:

```bash
# after a conflicted merge/rebase:
git status                 # lists conflicted files
# edit files: pick between <<<<<<< ======= >>>>>>> sections
git add <resolved-files>
git merge --continue       # or: git rebase --continue
# bail out entirely:
git merge --abort          # or: git rebase --abort
```

---

## 5. Branching strategies

### 5.1 Git Flow (2010, legacy but you'll meet it)

Long-lived `develop` + `main`, plus `feature/*`, `release/*`, `hotfix/*` branches.
Designed for boxed releases (installed software, mobile apps with review delays).
**Downsides:** long-lived branches → big merges → slow lead time. Generally
considered over-heavy for web services today.

### 5.2 GitHub Flow

One long-lived branch: `main`, always deployable. Features branch off `main`,
merge back via PR, deploy after merge. Simple, PR-centric. The default choice
for most teams.

### 5.3 Trunk-Based Development (what DORA elite performers do)

Everyone integrates to `main` ("trunk") at least daily. Branches, if used at all,
live < a day or two. Incomplete features hide behind **feature flags** rather than
long-lived branches.

```python
if flags.enabled("new-checkout", user):
    return new_checkout(user)
return old_checkout(user)
```

Why it wins: integration pain grows super-linearly with branch age. Merging daily
keeps conflicts trivial and keeps CI meaningful (you're testing the *integrated*
system, not your private fork of reality).

**Decision guide:** default to GitHub Flow; move toward trunk-based as your test
automation matures; accept Git Flow only when versioned/boxed releases force it.

---

## 6. The pull request workflow

The PR is where code review, CI, and knowledge sharing meet.

A healthy PR loop:

1. Branch from fresh `main`: `git switch -c feat/retry-payments`
2. Commit in small steps; push early (`git push -u origin feat/retry-payments`).
3. Open the PR with a description: **what**, **why**, **how tested**. Link the issue.
4. CI runs automatically (chapters 07–09). Red CI = review doesn't start.
5. Review happens; you push fixes; re-review; approve.
6. Merge — pick a strategy:
   - **Merge commit** — keeps every commit + a merge node.
   - **Squash & merge** — the whole PR becomes one commit on `main` (most popular:
     `main` stays readable, PR noise disappears).
   - **Rebase & merge** — replays commits individually, no merge node.
7. Delete the branch.

Review etiquette that keeps teams healthy: keep PRs small (< ~400 changed lines
reviews far better), review promptly (a blocked PR blocks flow), comment on the
code not the person, distinguish "must fix" from "nit:".

**Branch protection** (server-side, GitHub/GitLab settings): require PR + passing
status checks + N approvals before merge to `main`; forbid force-push. This is
what makes "CI must pass" a law instead of a suggestion.

---

## 7. Tags and releases

Tags mark release points and **trigger release pipelines**:

```bash
git tag -a v1.4.0 -m "Release 1.4.0"    # annotated tag (has author/date/message)
git push origin v1.4.0                   # tags are NOT pushed by default
git tag -l "v1.*"                        # list
git describe --tags                      # nearest tag + distance, e.g. v1.4.0-3-gf2a1c3d
```

Use **annotated** tags for releases (lightweight tags are just pointers, no metadata).
In ch 07 you'll build a pipeline that fires on `v*` tags and publishes an artifact
whose version = the tag.

---

## 8. Git hooks — local automation

Scripts in `.git/hooks/` that run on events. Example pre-commit hook that blocks
committing obvious secrets:

```bash
#!/usr/bin/env bash
# .git/hooks/pre-commit  (chmod +x)
if git diff --cached | grep -eI "(AKIA[0-9A-Z]{16}|-----BEGIN.*PRIVATE KEY)"; then
  echo "Possible secret in staged changes — commit blocked." >&2
  exit 1
fi
```

Hook exits non-zero → the commit is aborted. Common uses: linting, formatting,
commit-message format checks (`commit-msg` hook).

Because `.git/hooks` isn't versioned, teams use the **pre-commit framework**
(`pip install pre-commit`) with a committed `.pre-commit-config.yaml` so everyone
runs the same hooks. Server-side enforcement still belongs in CI — local hooks can
be skipped with `--no-verify`, CI can't.

---

## 9. Power tools you'll be glad you know

### git bisect — binary-search for the commit that broke things

```bash
git bisect start
git bisect bad                 # current commit is broken
git bisect good v1.3.0         # this old tag was fine
# git checks out the midpoint; you test, then:
git bisect good   # or: git bisect bad
# repeat ~log2(N) times until: "<sha> is the first bad commit"
git bisect reset
# fully automatic if you have a test command:
git bisect run ./test.sh
```

### git stash — shelve work-in-progress

```bash
git stash             # park changes, clean working dir
git stash pop         # bring them back
git stash list
```

### cherry-pick — copy one commit to another branch (e.g., hotfix to release branch)

```bash
git switch release/1.4
git cherry-pick abc1234
```

### .gitignore essentials

Ignore build outputs, dependencies, local config, secrets: `node_modules/`,
`dist/`, `*.log`, `.env`. **Never commit secrets** — history is forever (ch 16
covers scanning and what to do after a leak: rotate the secret; deleting the file
in a new commit does NOT remove it from history).

---

## 10. How Git drives CI/CD (the bridge to chapters 07–09)

| Git event | Typical pipeline reaction |
|-----------|--------------------------|
| Push to feature branch / PR opened | build + unit tests + lint ("is this mergeable?") |
| Merge to `main` | full build + tests + publish snapshot artifact + deploy to staging |
| Tag `v*` pushed | release pipeline: build once, publish versioned artifact, deploy |
| Nightly schedule | slow suites: full integration, dependency/security scans |

Keep this table in mind — it's the skeleton every CI config in this course fleshes out.

## Further reading

- *Pro Git* (free online: git-scm.com/book) — chapters 2, 3, 7.
- trunkbaseddevelopment.com — the reference site for trunk-based development.
- conventionalcommits.org

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 04: Networking](../04-networking/lesson.md)
