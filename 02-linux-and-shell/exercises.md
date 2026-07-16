# Chapter 02 — Exercises

All exercises run in your Ubuntu (WSL2) shell. Work in `~/devops/ch02`.

```bash
mkdir -p ~/devops/ch02 && cd ~/devops/ch02
```

---

## Exercise 2.1 — Environment verification

Run each and confirm sensible output:

```bash
lsb_release -a          # Ubuntu 24.04
docker run --rm hello-world
git --version && jq --version && curl --version | head -1
```

**Verify:** all commands succeed; `hello-world` prints "Hello from Docker!".

## Exercise 2.2 — Filesystem scavenger hunt

Using only the shell (no file manager), answer:

1. How many `.conf` files exist under `/etc` (top level only)?
2. What is the largest file in `/var/log`?
3. What shell does the `root` user have configured? (Look in `/etc/passwd`.)
4. Where does the `python3` command live, and is it a real file or a symlink?

**Verify:** each answer should come from a single command or short pipeline. If
you used more than ~2 commands per question, look for the more direct tool
(`ls /etc/*.conf | wc -l`, `du`/`sort`, `grep`+`awk`, `which`+`file`).

## Exercise 2.3 — Permissions lab

```bash
mkdir -p perms && cd perms
touch secret.txt script.sh
```

1. Make `secret.txt` readable and writable by you only. Confirm with `ls -l`
   (should show `-rw-------`).
2. Put `echo "it runs"` into `script.sh` and make it executable. Run it with `./script.sh`.
3. Remove the execute bit and run it again. Note the exact error message.
4. Create a directory `vault`, put a file inside, then `chmod 600 vault`. Try
   `ls vault` and `cat vault/<file>`. Explain what each error tells you about
   the difference between `r` and `x` on directories.

**Verify:** step 4 — `ls` partially works (names but permission-denied details)
while entering/reading fails; restoring with `chmod 700 vault` fixes it.

## Exercise 2.4 — Log analysis pipeline

Generate a fake access log:

```bash
cd ~/devops/ch02
for i in $(seq 1 500); do
  ip="10.0.0.$((RANDOM % 20))"
  code=$(shuf -e 200 200 200 200 301 404 500 -n1)
  path=$(shuf -e /home /api/users /api/orders /login /health -n1)
  echo "$ip - - [16/Jul/2026:10:00:$((RANDOM%60))] \"GET $path HTTP/1.1\" $code $((RANDOM%5000))"
done > access.log
```

Build pipelines to answer:

1. How many requests returned 500?
2. Top 3 client IPs by request count.
3. Which paths ever returned 500, and how many times each?
4. Total bytes transferred (last column), using `awk`.

**Verify:** `grep -c " 500 " access.log` for (1); the others should each be one
pipeline. Cross-check (3): the per-path counts must sum to the answer of (1).

## Exercise 2.5 — jq practice

```bash
curl -s https://api.github.com/repos/kubernetes/kubernetes > k8s.json
```

Using `jq` only:

1. Extract the repo's description.
2. Extract stars, forks, and open issues as one line: `stars=X forks=Y issues=Z`.
3. From `curl -s https://api.github.com/repos/kubernetes/kubernetes/tags`, print
   just the tag names.

**Verify:** (2) hint — string interpolation: `jq -r '"stars=\(.stargazers_count) forks=\(.forks_count) issues=\(.open_issues_count)"'`.

## Exercise 2.6 — Write a health-check script

Write `healthcheck.sh` that:

1. Takes one argument: a URL. Missing argument → usage message on **stderr**, exit code 2.
2. Curls the URL with a 5-second timeout.
3. Prints `OK <url>` and exits 0 on success; `FAIL <url>` and exits 1 on failure.
4. Uses the safe template (`set -euo pipefail`) and passes `shellcheck` cleanly.

Test it:

```bash
./healthcheck.sh https://example.com; echo "exit=$?"
./healthcheck.sh http://localhost:1; echo "exit=$?"
./healthcheck.sh; echo "exit=$?"
```

**Verify:** exit codes are 0, 1, 2 respectively, and `shellcheck healthcheck.sh`
reports nothing.

## Exercise 2.7 — Processes and signals

1. Run `sleep 600 &`. Find its PID two different ways (`ps aux | grep`, `pgrep sleep`).
2. Send it SIGTERM. Confirm it's gone.
3. Run `python3 -c "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(600)" &`
   — a process that *ignores* SIGTERM. Try `kill <pid>`, observe it survives, then
   `kill -9 <pid>`.

**Verify:** you can explain in one sentence why `docker stop` on such an app takes
10 seconds instead of being instant.

## Exercise 2.8 — Create a systemd service

Create a tiny web server and run it as a service. In WSL2 Ubuntu 24.04 systemd is
enabled by default (check with `systemctl is-system-running`; if it prints
`offline`, add `[boot]\nsystemd=true` to `/etc/wsl.conf` and run `wsl --shutdown`
from PowerShell).

1. `mkdir -p ~/devops/ch02/www && cd ~/devops/ch02/www && echo "hello from systemd" > index.html`
2. Create `/etc/systemd/system/hellowww.service` running
   `/usr/bin/python3 -m http.server 8099 --directory /home/<you>/devops/ch02/www`
   as your user, with `Restart=on-failure`.
3. `daemon-reload`, `start`, then check `systemctl status hellowww` and
   `curl localhost:8099`.
4. Kill the python process with `kill -9` and watch systemd resurrect it
   (`systemctl status` shows a new PID).
5. Read its logs with `journalctl -u hellowww`.

**Verify:** step 4 is the point — the service comes back without your help. Clean
up with `sudo systemctl disable --now hellowww`.

## Exercise 2.9 — SSH keys (local loopback)

Even without a remote server you can practice against localhost:

```bash
sudo apt install -y openssh-server && sudo systemctl start ssh
ssh-keygen -t ed25519        # accept defaults, empty passphrase is fine for this lab
ssh-copy-id localhost
ssh localhost 'hostname; uptime'
```

**Verify:** the final command runs without a password prompt. Then check
`~/.ssh` is `700` and `id_ed25519` is `600` (`ls -la ~/.ssh`).

---

**Stretch goal:** combine 2.4 and 2.6 — a script `top_errors.sh <logfile>` that
prints the top 3 paths by 500-count and exits 1 if there were any 500s at all
(useful shape for CI smoke checks later).
