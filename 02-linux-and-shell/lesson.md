# Chapter 02 — Environment Setup + Linux & Shell Essentials

## Learning objectives

1. Set up the course environment: WSL2 (Ubuntu) + Docker Desktop + core CLI tools.
2. Navigate and manipulate a Linux system confidently: files, permissions, processes, services.
3. Compose commands with pipes and redirection; use the classic text tools (`grep`, `sed`, `awk`, `jq`).
4. Write robust bash scripts with error handling — the language of DevOps glue.
5. Troubleshoot with `systemctl`, `journalctl`, `ps`, `top`, `df`, and friends.

Why this chapter matters: **every** tool later in the course (Docker, Jenkins,
Kubernetes, Ansible) assumes Linux and shell fluency. Weakness here compounds.

---

## 1. Environment setup (do this now)

### 1.1 WSL2 + Ubuntu

In **PowerShell as Administrator**:

```powershell
wsl --install -d Ubuntu-24.04
```

Reboot if asked. On first launch, create a Linux username/password. Then update:

```bash
sudo apt update && sudo apt upgrade -y
```

Useful facts about WSL2:
- Your Windows drives are mounted at `/mnt/c`, `/mnt/d`.
- Keep course work in the *Linux* filesystem (`~/devops`) — it's much faster than `/mnt/*`.
- `wsl --shutdown` (PowerShell) restarts the whole WSL VM if things get weird.

### 1.2 Docker Desktop

1. Install Docker Desktop for Windows (docker.com), enable the **WSL2 backend**
   (Settings → General → "Use the WSL 2 based engine").
2. Settings → Resources → WSL Integration → enable for Ubuntu-24.04.
3. Verify inside Ubuntu:

```bash
docker run --rm hello-world
```

### 1.3 Core tools

```bash
sudo apt install -y git curl wget jq unzip tree htop net-tools dnsutils \
    make python3 python3-pip python3-venv
```

Create the course workspace:

```bash
mkdir -p ~/devops && cd ~/devops
```

You're set. Everything below happens in the Ubuntu shell.

---

## 2. The filesystem and navigation

Linux has one tree rooted at `/`. The directories that matter for DevOps:

| Path | What lives there |
|------|-----------------|
| `/etc` | System & service configuration (`/etc/nginx/`, `/etc/ssh/`) |
| `/var/log` | Logs (`syslog`, service logs) |
| `/var/lib` | Service state/data (`/var/lib/docker`, databases) |
| `/usr/local/bin` | Locally installed executables |
| `/opt` | Optional third-party software |
| `/tmp` | Scratch space, cleared on reboot |
| `/proc`, `/sys` | Kernel's live view of processes & hardware (virtual) |
| `/home/<user>` (`~`) | Your stuff |

Navigation and inspection:

```bash
pwd                     # where am I
ls -la                  # list all, long format (note: permissions column)
cd /var/log && cd -     # cd - returns to previous dir
tree -L 2 /etc/ssh      # directory as a tree, 2 levels
file /usr/bin/python3   # what kind of file is this
which docker            # where does this command resolve from
find / -name "*.conf" -path "*nginx*" 2>/dev/null   # find files by name/path
stat /etc/passwd        # size, permissions, timestamps in detail
```

---

## 3. Permissions and users

`ls -l` shows `-rwxr-xr--  1 alice devs  4096 …`:

```
-        rwx      r-x      r--
type    owner    group    others
```

`r`=read(4), `w`=write(2), `x`=execute(1). So `rwxr-xr--` = `754`.

```bash
chmod 644 file          # rw-r--r--  (typical config file)
chmod +x deploy.sh      # add execute for everyone
chown alice:devs file   # change owner and group
sudo -i                 # root shell (careful)
id                      # my uid, gid, groups
```

DevOps-relevant subtleties:

- **Directories need `x` to be entered.** A directory with `r--` can be listed but
  not entered — a classic confusing failure.
- **SSH is picky:** `~/.ssh` must be `700`, private keys `600`, or ssh refuses them.
- The `docker` group is effectively root (members control the Docker daemon) —
  that's why `sudo usermod -aG docker $USER` is convenient *and* a security decision.
- Services should run as dedicated non-root users; you'll see `User=` in systemd
  units and `USER` in Dockerfiles for the same reason.

---

## 4. Pipes, redirection, and the text-processing toolkit

The Unix philosophy: small tools composed with pipes. This is 80% of daily DevOps work.

### 4.1 Redirection

```bash
command > out.txt        # stdout to file (overwrite)
command >> out.txt       # append
command 2> err.txt       # stderr to file
command > all.txt 2>&1   # both to one file
command 2>/dev/null      # discard errors
command < input.txt      # file as stdin
cmd1 | cmd2              # stdout of cmd1 → stdin of cmd2
cmd1 && cmd2             # run cmd2 only if cmd1 succeeded
cmd1 || cmd2             # run cmd2 only if cmd1 FAILED
tee file.txt             # write to file AND pass through (great in pipelines)
```

Every command exits with a status code: `0` = success, anything else = failure.
Check with `echo $?`. **All CI systems are built on this convention** — a pipeline
step fails when its command exits non-zero.

### 4.2 grep — find lines

```bash
grep -i error /var/log/syslog        # case-insensitive
grep -r "TODO" ~/devops              # recursive through a tree
grep -v "^#" config.conf             # -v inverts: lines NOT matching (strip comments)
grep -E "5[0-9]{2}" access.log       # extended regex: HTTP 5xx
grep -c "GET" access.log             # count matches
grep -A3 -B1 "panic" app.log         # 3 lines After, 1 Before for context
```

### 4.3 sed — edit streams

```bash
sed 's/old/new/' file            # replace first occurrence per line
sed 's/old/new/g' file           # all occurrences
sed -i 's/DEBUG/INFO/g' app.conf # -i edits the file in place
sed -n '10,20p' file             # print only lines 10–20
sed '/^$/d' file                 # delete empty lines
```

### 4.4 awk — column-oriented processing

```bash
awk '{print $1}' access.log                  # first column (e.g. client IP)
awk '{print $NF}' file                       # last column
awk -F: '{print $1}' /etc/passwd             # -F sets delimiter → usernames
awk '$9 == 500 {print $7}' access.log        # URLs that returned 500
awk '{sum+=$10} END {print sum/NR}' log      # average of column 10
```

### 4.5 jq — JSON (modern APIs speak JSON; jq is grep/awk for it)

```bash
curl -s https://api.github.com/repos/torvalds/linux | jq '.stargazers_count'
echo '{"items":[{"name":"a","ok":true},{"name":"b","ok":false}]}' \
  | jq '.items[] | select(.ok) | .name'
docker inspect mycontainer | jq '.[0].NetworkSettings.IPAddress'
```

### 4.6 A realistic composition

Top 5 IPs hitting your server, from an nginx access log:

```bash
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -5
```

Read pipelines left to right, and build them incrementally — run each stage,
inspect output, add the next. That's how professionals actually write them.

---

## 5. Processes and services

### 5.1 Processes

```bash
ps aux                        # all processes (USER, PID, %CPU, %MEM, COMMAND)
ps aux | grep nginx           # find a specific one
top          # live view; press M to sort by memory, P by CPU, q to quit
htop         # nicer top (we installed it)
kill 1234              # polite termination (SIGTERM) — allows cleanup
kill -9 1234           # forced (SIGKILL) — last resort, no cleanup
pkill -f "python3 app.py"     # kill by command-line match
nohup ./server &              # run in background, survive logout; also: tmux
```

Signals matter later: Docker sends SIGTERM on `docker stop`, waits 10 s, then
SIGKILL. Kubernetes does the same on pod shutdown. Apps that ignore SIGTERM get
killed mid-request — that's why "graceful shutdown" is a code concern too.

### 5.2 systemd — the service manager

On real Linux servers (and important for Ansible/Jenkins chapters):

```bash
systemctl status nginx        # is it running? recent log lines included
sudo systemctl start nginx
sudo systemctl stop nginx
sudo systemctl restart nginx
sudo systemctl reload nginx   # re-read config without dropping connections
sudo systemctl enable nginx   # start automatically at boot
journalctl -u nginx           # full logs for a unit
journalctl -u nginx -f        # follow (like tail -f)
journalctl --since "10 min ago"
```

A minimal unit file (`/etc/systemd/system/myapp.service`) — you'll write one in
the exercises:

```ini
[Unit]
Description=My App
After=network.target

[Service]
User=appuser
ExecStart=/opt/myapp/server
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

After editing units: `sudo systemctl daemon-reload`.

### 5.3 Disk, memory, and "why is the server sick"

```bash
df -h            # disk usage per filesystem — full disk = most classic outage
du -sh /var/*    # what's eating the space
free -h          # memory (watch 'available', not 'free')
uptime           # load average: 1, 5, 15 min (rough rule: worry when > CPU count)
```

The 60-second triage habit, in order: `uptime` → `df -h` → `free -h` →
`top` → `journalctl -e`. Practice it until it's reflexive.

---

## 6. Bash scripting — the glue language

### 6.1 The safe template

Start every script like this:

```bash
#!/usr/bin/env bash
set -euo pipefail

# -e          exit on any command failure
# -u          error on undefined variables (catches typos)
# -o pipefail a pipeline fails if ANY stage fails, not just the last
```

Without `set -euo pipefail`, scripts happily continue after failures and cause
the "deploy script said OK but nothing deployed" class of incident.

### 6.2 Variables, arguments, quoting

```bash
name="world"                 # NO spaces around =
echo "Hello, ${name}"        # quote variables — always
readonly ENV="${1:?usage: $0 <environment>}"   # required arg with error message
count=$(ls | wc -l)          # command substitution
```

**Always quote expansions** (`"$var"`, `"$@"`): unquoted variables split on spaces
and glob — the #1 source of bash bugs.

### 6.3 Conditionals and loops

```bash
if [[ -f "/etc/myapp.conf" ]]; then     # -f file exists; -d dir; -z string empty
  echo "config found"
elif [[ "$ENV" == "prod" ]]; then
  echo "no config in prod!" >&2
  exit 1
fi

for f in /var/log/*.log; do
  echo "=== $f ==="
  tail -3 "$f"
done

while read -r line; do          # canonical line-by-line file processing
  echo "got: $line"
done < servers.txt
```

### 6.4 Functions and a realistic example

```bash
#!/usr/bin/env bash
set -euo pipefail

log() { echo "[$(date +%H:%M:%S)] $*"; }

check_service() {
  local url="$1"
  if curl -sf --max-time 5 "$url" > /dev/null; then
    log "OK   $url"
  else
    log "FAIL $url"
    return 1
  fi
}

failures=0
for svc in "http://localhost:8080/health" "http://localhost:9090/health"; do
  check_service "$svc" || failures=$((failures+1))
done

if (( failures > 0 )); then
  log "$failures service(s) unhealthy"
  exit 1
fi
log "all healthy"
```

This shape — loop over targets, check, count failures, exit non-zero — is the
skeleton of half the operational scripts ever written.

### 6.5 Debugging scripts

```bash
bash -x script.sh        # trace every command as it runs
shellcheck script.sh     # static analysis (sudo apt install shellcheck) — use it always
```

---

## 7. Remote machines: SSH essentials

```bash
ssh user@host                        # log in
ssh-keygen -t ed25519                # generate a key pair (~/.ssh/id_ed25519[.pub])
ssh-copy-id user@host                # install your public key on the server
scp file.txt user@host:/tmp/         # copy file over ssh
ssh user@host 'df -h; uptime'        # run remote commands non-interactively
```

`~/.ssh/config` saves typing and is used by Ansible later:

```
Host web1
    HostName 203.0.113.10
    User deploy
    IdentityFile ~/.ssh/id_ed25519
```

Then just `ssh web1`. Key-based auth (never passwords) is the standard; the
private key never leaves your machine.

---

## Command reference card

| Task | Command |
|------|---------|
| What's using port 8080 | `sudo ss -tlnp \| grep 8080` |
| Follow a log | `tail -f /var/log/syslog` or `journalctl -f` |
| Find big files | `du -ah /var \| sort -rh \| head -20` |
| Replace text in many files | `grep -rl "old" . \| xargs sed -i 's/old/new/g'` |
| Download | `curl -LO <url>` or `wget <url>` |
| Archive / extract | `tar czf a.tgz dir/` / `tar xzf a.tgz` |
| Line/word count | `wc -l file` |
| Diff two files | `diff -u a b` |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 03: Git Workflows](../03-git-workflows/lesson.md)
