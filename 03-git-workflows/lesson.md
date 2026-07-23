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
git log --oneline --graph --all --decorate            # learn to read this view
git config --global alias.lg "log --oneline --graph --all --decorate"   # alias it: git lg
```

> **Flags:** `--oneline` one commit per line (short SHA + subject) · `--graph` draws the branch/merge structure as ASCII art in the left margin · `--all` show every branch, not just the current one · `--decorate` label commits that branches/tags point at.
> **Why:** this is the view that makes "branches are just pointers" visible — you *see* `main` and `feature/x` as labels hanging off commits.
> **Expect:**
> ```
> * f2a1c3d (HEAD -> feat/retry, origin/feat/retry) Add retry to payment client
> * 9b7e2aa (main) Fix health endpoint
> | * 3c9d0ef (origin/main) Bump deps
> |/
> * 88a71b2 (tag: v1.3.0) Release 1.3.0
> ```
> The second line defines a git **alias**: `git config --global` writes to your `~/.gitconfig`, and afterwards `git lg` expands to the whole incantation.

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

> **Command by command:**
> - `git status` — which files are modified/staged/untracked, plus what git suggests doing next. Cheap; run it constantly.
> - `git diff` vs `git diff --staged` — two different questions: "what have I edited but not yet staged?" vs "what exactly will the next commit contain?" Review `--staged` before every commit — it's the last look before history.
> - `git show <commit>` — a commit's metadata (author, date, message) followed by its full diff. `git show HEAD~2` = two commits back; `git show v1.3.0` works on tags too.
> - `git blame file.py` — prefixes every line with the commit and author that last changed it. Not for assigning guilt: it's how you find *the commit* (and its why-explaining message and PR) behind a puzzling line. Expect: `9b7e2aa (alice 2026-03-02 14:11) timeout = 30`.

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

> **Flag:** `-p` = **p**atch mode. Git walks you through your changes one *hunk* (contiguous block of diff) at a time and asks about each: `y` stage it, `n` skip it, `s` split into smaller hunks, `q` quit.
> **Why:** you fixed the bug *and* tweaked an unrelated log line in the same file — patch mode lets you commit them separately, keeping commits atomic. Verify what you picked with `git diff --staged` before committing.

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

> **How the recovery actually goes:** `git reflog` prints HEAD's movement history, newest first:
> ```
> 3c9d0ef HEAD@{0}: reset: moving to HEAD~1
> f2a1c3d HEAD@{1}: commit: Add retry to payment client
> ```
> There's your "lost" commit at `HEAD@{1}`. `git reset --hard f2a1c3d` moves the branch pointer (and your files) right back to it. The commit was never deleted — only the *pointer* to it was.

---

## 4. Merging vs rebasing

Two ways to integrate `main` into your feature branch:

```bash
git merge main     # ties histories together with a merge commit; true history
git rebase main    # replays your commits on top of main; linear history
```

> **What each actually does** (run from your feature branch):
> - `git merge main` — creates a single new *merge commit* with two parents (your branch's tip and main's tip). Your existing commits are untouched.
> - `git rebase main` — takes each of your branch's commits, re-applies them one by one on top of main's current tip, and moves your branch pointer to the result. Same content, **new commits with new SHAs** — the old ones are abandoned. That's why rebasing anything already pushed and shared rewrites history under your teammates' feet.
> **Expect after rebase:** `Successfully rebased and updated refs/heads/feat/retry.` — and `git lg` now shows your commits sitting linearly on top of main.

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

Conflicts happen with both. A conflict is not an error — it's Git saying "both
sides changed the same lines; a human must choose." Inside a conflicted file:

```
def get_timeout():
 <<<<<<< HEAD
    return config.timeout or 30      # your branch's version
 =======
    return settings.TIMEOUT          # main's version
 >>>>>>> main
```

Between `<<<<<<<` and `=======` is **your side** (`HEAD`); between `=======` and
`>>>>>>>` is **the side being merged in**. Resolving = editing the block into the
code you actually want — one side, the other, or a hand-written blend — and
deleting all three marker lines. There is no magic: the markers are plain text
in the file, and the resolution is an edit like any other.

```bash
# after a conflicted merge/rebase:
git status                 # conflicted files listed under "Unmerged paths"
git diff                   # shows the conflicted hunks with both sides
# edit files, resolve each <<<<<<< block, then:
git add <resolved-files>   # marks them resolved
git merge --continue       # or: git rebase --continue
# bail out entirely, back to the pre-merge state:
git merge --abort          # or: git rebase --abort
```

> **The flow decoded:** `git add` on a conflicted file means "I declare this resolved" — staging doubles as the resolution ledger. `--continue` then finishes the merge commit (or moves the rebase on to the next commit — a rebase can conflict repeatedly, once per replayed commit). `--abort` is the no-shame escape hatch: everything back exactly as it was before you started.
> **Shortcuts:** `git checkout --ours <file>` / `--theirs <file>` takes one side wholesale — right for lockfiles and generated files you'd regenerate anyway. **Rebase trap:** during a rebase the meanings invert — `--ours` is the branch you're rebasing *onto*, `--theirs` is your own commits (rebase replays *your* commits onto the other branch, so from Git's seat the base is "ours"). Run `git diff` before trusting either.

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

> **Command by command:**
> - `git tag -a v1.4.0 -m "..."` — `-a` makes an **a**nnotated tag: a real object with author, date, and message (`-m`), attached to the current commit. Without `-a` you get a lightweight tag — a bare pointer, fine for private bookmarks, wrong for releases.
> - `git push origin v1.4.0` — pushes the tag explicitly. **A plain `git push` does not push tags** — forgetting this is why "I tagged the release but CI never fired" happens to everyone once.
> - `git tag -l "v1.*"` — `-l` lists tags matching a pattern.
> - `git describe --tags` — "where am I relative to the last release?" Output `v1.4.0-3-gf2a1c3d` reads as: nearest tag `v1.4.0`, `3` commits ahead of it, currently at commit `f2a1c3d` (the `g` just means "git"). Build systems love this string as an automatic version number.

Use **annotated** tags for releases (lightweight tags are just pointers, no metadata).
In ch 07 you'll build a pipeline that fires on `v*` tags and publishes an artifact
whose version = the tag.

### Signed commits and tags — proving who made them

A commit's author field is just text: `git config user.name "Linus Torvalds"`
and you're "Linus" in every log. Signatures fix that with cryptography — and
modern Git can sign with the SSH key you already have (ch 02), no GPG setup:

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git commit -S -m "Add retry to payment client"
git tag -s v1.4.0 -m "Release 1.4.0"
git log --show-signature -1
```

> **Command by command:** the two `config` lines switch signing from GPG (the historical default) to your **SSH key** and point at the public half · `-S` on commit / `-s` on tag attaches a signature made with the private key · `--show-signature` verifies and displays it in the log. GitHub/GitLab verify signatures server-side and show the **Verified** badge; branch protection can *require* signed commits.
> **Why it matters here:** this is the provenance chain's first link — ch 16 signs *images* (cosign) for the same reason. Signed commit → reviewed PR → signed image = "everything in prod traces to a person and a pipeline."

---

## 8. Git hooks — local automation

Scripts in `.git/hooks/` that run on events. Example pre-commit hook that blocks
committing obvious secrets:

```bash
#!/usr/bin/env bash
# .git/hooks/pre-commit  (chmod +x)
if git diff --cached | grep -qE "(AKIA[0-9A-Z]{16}|-----BEGIN.*PRIVATE KEY)"; then
  echo "Possible secret in staged changes — commit blocked." >&2
  exit 1
fi
```

> **How the hook works:** `git diff --cached` prints what's staged for this commit (same as `--staged`); `grep -qE` scans it — `-E` extended regex, `-q` **q**uiet (we only want the exit code, not the matched secret echoed into the terminal) — for two secret shapes — `AKIA` + 16 chars (the fixed prefix of AWS access key IDs) and the `-----BEGIN ... PRIVATE KEY` header of PEM key files. grep exits 0 when it *finds* something, making the `if` true → print a warning to stderr (`>&2`) and `exit 1`.

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

> **How bisect works:** you give it one known-bad commit (usually the current one) and one known-good point in the past; git checks out the *middle* commit between them. You test and report `good` or `bad`; each answer halves the search space. 1000 commits = ~10 rounds to the exact culprit. `git bisect reset` returns you to where you started.
> **The killer variant:** `git bisect run ./test.sh` automates the loop — git runs your script at every step and interprets its exit code (0 = good, non-zero = bad). Come back in a minute to:
> ```
> f2a1c3d is the first bad commit
> ```
> Combine with everything from ch 02: the "test script" can be *any* command — `curl -sf localhost:8000/health`, a pytest invocation, a grep.

### git stash — shelve work-in-progress

```bash
git stash             # park changes, clean working dir
git stash pop         # bring them back
git stash list
```

> **Why it exists:** you're mid-change and suddenly need a clean working directory (urgent fix on another branch, a pull that refuses to run over dirty files). `stash` shelves your uncommitted changes onto a stack; `pop` reapplies the most recent shelf and drops it; `list` shows what's parked (`stash@{0}: WIP on main: ...`). Untracked files aren't stashed unless you add `-u`.

### cherry-pick — copy one commit to another branch (e.g., hotfix to release branch)

```bash
git switch release/1.4
git cherry-pick abc1234
```

> **What it does:** `git switch` moves you onto the target branch (the modern, clearer replacement for `git checkout` when changing branches); `cherry-pick` then *copies* commit `abc1234`'s changes as a brand-new commit here. New SHA, same diff and message. The original stays where it was — you've duplicated the change, not moved it. The canonical use: a bug fixed on `main` must also land on a maintenance branch.

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

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| PR | Pull Request | Proposed change submitted for review before merging into a shared branch |
| CI/CD | Continuous Integration / Continuous Delivery-Deployment | The automated build-test-release pipeline a Git event triggers |
| SHA | Secure Hash Algorithm (digest) | The hex ID that uniquely identifies a Git commit's content |
| WIP | Work In Progress | Marks an unfinished commit or PR not meant for merging yet |
| PEM | Privacy-Enhanced Mail (format) | The base64 text format used for private keys and certificates |
| AWS | Amazon Web Services | Cloud provider whose access-key prefix (`AKIA`) the secret-scanning regex looks for |
| GPG | GNU Privacy Guard | The OpenPGP toolset historically used for signing commits/tags (SSH keys now work too) |
| SSH | Secure Shell | Encrypted remote access; its key pairs can also sign Git commits |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 04: Networking](../04-networking/lesson.md)
