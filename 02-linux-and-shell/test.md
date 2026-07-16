# Chapter 02 — Test

15 questions. Passing: 12/15. Questions marked **[practical]** should be answered
by actually running commands.

---

**Q1.** What does the permission string `-rwxr-x---` mean, and what is it in octal?

**Q2.** Which command shows what process is listening on port 8080?
- a) `ps aux | grep 8080`
- b) `sudo ss -tlnp | grep 8080`
- c) `df -8080`
- d) `top -p 8080`

**Q3.** What is the difference between `>` and `>>`?

**Q4.** What does `2>&1` do, and why does the order in `cmd > file 2>&1` matter?

**Q5.** Write a pipeline that prints the 5 most common values in the first column
of a space-separated file `data.txt`.

**Q6.** What is the exit code convention on Linux, and why is it fundamental to CI systems?

**Q7.** In a bash script, what do `set -e`, `set -u`, and `set -o pipefail` each do?

**Q8.** What's wrong with this script line, and what could go wrong at runtime?
```bash
rm -rf $BUILD_DIR/output
```

**Q9.** `kill 1234` vs `kill -9 1234` — what signal does each send, and why should
`-9` be the last resort?

**Q10.** Which command shows the last 50 log lines of the systemd unit `nginx` and
keeps following new ones?
- a) `journalctl -u nginx -n 50 -f`
- b) `systemctl logs nginx --follow`
- c) `tail -f /var/log/nginx`
- d) `cat /proc/nginx/log`

**Q11.** After editing `/etc/systemd/system/myapp.service`, what must you run
before `systemctl restart myapp` picks up the changes?

**Q12.** **[practical]** Using `jq`, extract the value `"1.2.3"` from:
```json
{"app": {"name": "api", "release": {"version": "1.2.3"}}}
```
Write the exact command assuming the JSON is in `app.json`.

**Q13.** A disk-full incident: which two commands, in what order, do you run to
(a) confirm which filesystem is full and (b) find what's consuming it?

**Q14.** Why must `~/.ssh/id_ed25519` have mode `600`?

**Q15.** **[practical]** A colleague's script:
```bash
#!/bin/bash
cd /opt/app
git pull
systemctl restart app
echo "deployed!"
```
Name three distinct robustness problems and how to fix them.

---

<details>
<summary><b>Answer key</b></summary>

1. Regular file; owner: read+write+execute; group: read+execute; others: nothing. Octal **750**.
2. **b**
3. `>` truncates (overwrites) the file; `>>` appends.
4. Redirects stderr (fd 2) to wherever stdout (fd 1) currently points. Order
   matters because redirections apply left to right: `cmd > file 2>&1` sends both
   to the file; `cmd 2>&1 > file` points stderr at the *terminal* (stdout's old
   target) and only stdout at the file.
5. `awk '{print $1}' data.txt | sort | uniq -c | sort -rn | head -5`
6. Exit code 0 = success, non-zero = failure. CI steps are commands; a pipeline
   stage fails exactly when its command exits non-zero — that's the whole contract.
7. `-e`: exit the script when any command fails. `-u`: treat use of undefined
   variables as an error. `-o pipefail`: a pipeline's exit code is the first
   failing stage's, not just the last stage's.
8. Unquoted variable. If `BUILD_DIR` is unset (and `set -u` is absent) it expands
   to empty → `rm -rf /output`; if it contains spaces the arguments split.
   Fix: `set -u` plus quotes — `rm -rf "${BUILD_DIR:?}/output"`.
9. `kill` sends SIGTERM (graceful — process may clean up: flush, close
   connections). `kill -9` sends SIGKILL, which cannot be caught — no cleanup,
   possible corrupted state/lost data. Try TERM first.
10. **a**
11. `sudo systemctl daemon-reload`
12. `jq -r '.app.release.version' app.json`
13. `df -h` (which filesystem is full) then `du -sh <mount>/*` (or
    `du -ah <dir> | sort -rh | head`) to find the consumer.
14. SSH refuses private keys readable by group/others (and a readable key means
    anyone on the machine can steal your identity). 600 = owner read/write only.
15. Any three of: no `set -euo pipefail` — failures don't stop it, so "deployed!"
    prints even when `git pull` failed; `cd /opt/app` can fail and subsequent
    commands run in the wrong directory (use `cd /opt/app || exit 1`);
    `systemctl restart` needs root — no privilege check/sudo; no verification
    after restart (health check) before declaring success; `git pull` on a dirty
    tree can conflict and leave a half-updated app.

</details>

**Scoring:** 12+ → [Chapter 03](../03-git-workflows/lesson.md). Below → redo
exercises 2.4, 2.6, 2.8 — they cover the most-tested ground.
