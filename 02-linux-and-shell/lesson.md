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

> **Tools:** `wsl` — the Windows Subsystem for Linux management CLI, built into Windows 11. It manages the lightweight VM that runs real Linux kernels alongside Windows.
> **Flags:** `--install` enables the WSL feature and installs a distribution · `-d Ubuntu-24.04` picks *which* distribution (run `wsl --list --online` to see all available ones).
> **Why:** all DevOps tooling assumes Linux; WSL2 gives you a genuine Ubuntu without dual-booting or a heavyweight VM.
> **Expect:** download progress, then either a new Ubuntu window asking for a username, or a prompt to reboot first.

Reboot if asked. On first launch, create a Linux username/password. Then update:

```bash
sudo apt update && sudo apt upgrade -y
```

> **Tools:** `sudo` — run a command as root (the admin user); `apt` — Debian/Ubuntu's package manager, which installs and updates software from online repositories.
> **Flags & pieces:** `apt update` refreshes the *catalog* of available package versions (downloads nothing else) · `&&` runs the second command only if the first succeeded (ch 02 §4.1) · `apt upgrade -y` installs the newer versions, `-y` answering "yes" to the confirmation prompt automatically.
> **Why:** a fresh distro image ships with months-old packages; patching first is the standard opening move on any new Linux system.
> **Expect:** a list of repositories being fetched, then a package list and progress bars. Second run: `All packages are up to date.`

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

> **Tools:** `docker` — the container CLI (ch 05 teaches it fully; here it's just a smoke test).
> **Flags:** `run` pulls and starts a container from the image `hello-world` · `--rm` deletes the container again once it exits, so the test leaves no litter.
> **Why:** proves the whole chain works: your Ubuntu shell → Docker Desktop's daemon → registry pull → container execution.
> **Expect:**
> ```
> Hello from Docker!
> This message shows that your installation appears to be working correctly.
> ```
> If instead you get `cannot connect to the Docker daemon`, Docker Desktop isn't running or WSL integration (step 2) isn't enabled.

### 1.3 Core tools

```bash
sudo apt install -y git curl wget jq unzip tree htop net-tools dnsutils \
    make python3 python3-pip python3-venv
```

> **What you're installing:** `git` version control · `curl`/`wget` HTTP clients for downloading and testing APIs · `jq` JSON processor (§4.5) · `unzip` archive extraction · `tree` directory visualizer · `htop` interactive process viewer (§5.1) · `net-tools` legacy network commands · `dnsutils` provides `dig` for DNS debugging (ch 04) · `make` the classic build runner · `python3` + `pip` + `venv` because the course's example app is Python.
> **Note:** the trailing `\` continues the command on the next line — paste both lines together.

Create the course workspace:

```bash
mkdir -p ~/devops && cd ~/devops
```

> **Tools:** `mkdir` — make directory; `cd` — change directory.
> **Flags:** `-p` creates parent directories as needed and, crucially, doesn't error if the directory already exists — which makes the command safe to re-run (your first taste of *idempotency*, ch 01's key term).
> **Why:** `~` is your home directory (`/home/<user>`); keeping work here, on the Linux filesystem, is much faster than under `/mnt/c`.

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

> **Command by command:**
> - `pwd` — *print working directory*: the absolute path you're standing in.
> - `ls -la` — *list*: `-l` long format (one file per line with permissions, owner, size, date), `-a` include hidden files (names starting with `.` — where configs like `.bashrc` hide). Expect lines like `-rw-r--r-- 1 you you 220 Jul 17 10:00 .bashrc`.
> - `cd /var/log && cd -` — `cd -` jumps back to wherever you were before; great for bouncing between two directories.
> - `tree -L 2 /etc/ssh` — draws the directory as an ASCII tree; `-L 2` limits depth to 2 levels so big trees stay readable.
> - `file /usr/bin/python3` — inspects content (not the name) to say what a file *is*: `ELF 64-bit executable`, `ASCII text`, `symbolic link to…`. Useful when a "script" turns out to be a binary.
> - `which docker` — prints the full path the shell would execute for that command name (`/usr/bin/docker`). First question when "the wrong version" of a tool runs.
> - `find / -name "*.conf" -path "*nginx*"` — `find` walks a directory tree applying tests: `-name` matches the filename (glob), `-path` matches the whole path. The `2>/dev/null` discards the flood of *permission denied* errors from directories you can't read (explained properly in §4.1).
> - `stat /etc/passwd` — everything the filesystem knows about one file: exact size, octal permissions, owner, and the three timestamps (last access/modify/change).

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

> **Command by command:**
> - `chmod` — *change mode* (permissions). Takes either octal (`644` = owner `rw-`, group `r--`, others `r--` — do the 4+2+1 math per digit) or symbolic form (`+x` = add execute, `u+w` = add write for the owner only). Symbolic is safer when you only want to flip one bit.
> - `chown alice:devs file` — *change owner*: sets owning user to `alice` and group to `devs` in one go. Needs `sudo` unless you already own the file.
> - `sudo -i` — opens a full interactive root shell (prompt changes to `#`). Prefer one-off `sudo <command>` — a lingering root shell is how "oops, wrong directory" becomes an outage.
> - `id` — shows your numeric user ID, group ID, and all group memberships. Expect: `uid=1000(you) gid=1000(you) groups=1000(you),999(docker)` — that `docker` entry is what `usermod -aG docker` added.

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

> **What's actually happening:** every process gets three streams — stdin (fd 0, input), stdout (fd 1, normal output), stderr (fd 2, errors). `>` redirects stdout; the `2` in `2>` names the stderr stream. So `> all.txt 2>&1` means "stdout to the file, then point stderr at wherever stdout goes" — **order matters**: `2>&1 > all.txt` sends stderr to the *old* stdout (your terminal) and only stdout to the file, a classic gotcha.
> **Why `2>/dev/null` keeps appearing:** `/dev/null` is a kernel-provided black hole; sending stderr there silences noise (like `find`'s permission errors) while keeping the real output.
> **`tee`** (as in a T-shaped pipe fitting) duplicates its stdin: one copy to a file, one copy onward. `./deploy.sh | tee deploy.log` shows output live *and* keeps a record — exactly what you want in CI scripts.

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

> **Tool:** `grep` — searches text line by line for a pattern (regular expression) and prints matching lines. *The* log-searching tool; the name is a verb now ("grep the logs").
> **Flags used above:** `-i` ignore case (`Error`, `ERROR`, `error` all match) · `-r` recurse into directories, searching every file · `-v` in**v**ert — print lines that *don't* match (stripping `^#` comment lines from configs is the classic use) · `-E` extended regex so `[0-9]{2}` repetition works: `5[0-9]{2}` = "5 then two digits" = HTTP 500–599 · `-c` count matching lines instead of printing them · `-A3 -B1` include 3 lines **A**fter and 1 **B**efore each match — context is everything when reading a stack trace.
> **Expect:** matching lines, prefixed with the filename when searching multiple files (`app.log:panic: nil pointer`). Exit code 0 if anything matched, 1 if nothing did — which is why `grep -q pattern file && ...` works as an if-condition in scripts.

### 4.3 sed — edit streams

```bash
sed 's/old/new/' file            # replace first occurrence per line
sed 's/old/new/g' file           # all occurrences
sed -i 's/DEBUG/INFO/g' app.conf # -i edits the file in place
sed -n '10,20p' file             # print only lines 10–20
sed '/^$/d' file                 # delete empty lines
```

> **Tool:** `sed` — *stream editor*: reads lines, applies editing commands, prints the result. In DevOps it's overwhelmingly used for one thing: search-and-replace in config files from scripts and pipelines.
> **The syntax decoded:** `s/old/new/` means **s**ubstitute; the trailing `g` (**g**lobal) replaces every occurrence on a line instead of just the first. The address forms select *which* lines a command touches: `10,20p` = lines 10–20, `p`rint them (with `-n` suppressing everything else); `/^$/d` = lines matching the regex "empty line", **d**elete them.
> **Flags:** `-i` edits the file **i**n place instead of printing to stdout — the flag that turns sed from a viewer into automation. No `-i`? Nothing on disk changes; run it without `-i` first as a preview.
> **Expect:** the transformed text on stdout (or a silently modified file with `-i`). sed exits 0 even when nothing matched — don't use its exit code to check "did the replacement happen"; grep afterwards instead.

### 4.4 awk — column-oriented processing

```bash
awk '{print $1}' access.log                  # first column (e.g. client IP)
awk '{print $NF}' file                       # last column
awk -F: '{print $1}' /etc/passwd             # -F sets delimiter → usernames
awk '$9 == 500 {print $7}' access.log        # URLs that returned 500
awk '{sum+=$10} END {print sum/NR}' log      # average of column 10
```

> **Tool:** `awk` — a tiny programming language for line-and-column data. It splits every input line into fields (`$1`, `$2`, … by whitespace; `$0` = whole line) and runs your program against each line. Where grep answers "which lines?", awk answers "which *columns*, computed how?".
> **The syntax decoded:** a program is `condition { action }`. No condition = run on every line (`{print $1}`). `$9 == 500 {print $7}` = "when field 9 equals 500, print field 7" — in an nginx access log those are the status code and URL. `-F:` changes the **F**ield separator (here `:` for `/etc/passwd`'s colon-delimited format). Built-ins: `$NF` = last field (**N**umber of **F**ields), `NR` = current line number, and the `END { }` block runs once after all input — perfect for totals and averages, like `sum/NR`.
> **Expect:** one output line per matching input line (or one summary line from `END`). When a column comes out wrong, the field numbering is off — run `awk '{print NR, $1, $2, $3}' file | head` to see how awk split things.

### 4.5 jq — JSON (modern APIs speak JSON; jq is grep/awk for it)

```bash
curl -s https://api.github.com/repos/torvalds/linux | jq '.stargazers_count'
echo '{"items":[{"name":"a","ok":true},{"name":"b","ok":false}]}' \
  | jq '.items[] | select(.ok) | .name'
docker inspect mycontainer | jq '.[0].NetworkSettings.IPAddress'
```

> **Tool:** `jq` — a query language for JSON, used as a filter in pipelines. Modern infrastructure speaks JSON (`docker inspect`, `kubectl -o json`, every REST API); jq is how you extract the one field you need without writing a Python script.
> **The syntax decoded:** a jq program is a *filter* the JSON flows through. `.stargazers_count` = "the `stargazers_count` key of the top-level object". `.[0]` = first element of an array (docker inspect always returns an array — hence `.[0]` before drilling in). `.items[]` = *each* element of the `items` array, one at a time; `select(.ok)` keeps only elements where `.ok` is true; `| .name` then extracts one field from the survivors. Filters chain with `|` exactly like shell pipes — same mental model, inside JSON.
> **Flags worth knowing:** `-r` outputs **r**aw strings (no quotes — needed when feeding results to other commands); `.` alone pretty-prints, so `curl -s api | jq .` is the standard "let me look at this response" move.
> **Expect (line 2 above):** `"a"` — the only item whose `ok` was true.

### 4.6 A realistic composition

Top 5 IPs hitting your server, from an nginx access log:

```bash
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -5
```

> **Stage by stage** — run each prefix of the pipeline yourself and watch the data transform:
> 1. `awk '{print $1}' access.log` — extract column 1 (the client IP) from every log line. Output: one IP per line, in log order, full of repeats.
> 2. `| sort` — sort those IPs alphabetically. Why? Because the next tool requires it:
> 3. `| uniq -c` — collapse *adjacent* duplicate lines into one, prefixed with a **c**ount. `uniq` only sees neighbors — **without the `sort` before it, repeats scattered through the log would never collapse.** This sort-then-uniq pairing is a fixed idiom; learn it as one unit. Output now: `  57 10.0.1.4` style lines.
> 4. `| sort -rn` — sort again, this time by the count: `-n` compares **n**umerically (so 100 > 20; text sort would put "100" before "20"), `-r` **r**everses to biggest-first.
> 5. `| head -5` — keep only the first 5 lines. (`head`/`tail` show the start/end of any stream.)
>
> **Expect:**
> ```
>    1042 203.0.113.7
>     388 198.51.100.23
>     201 10.0.0.5
>      77 192.0.2.146
>      63 203.0.113.9
> ```
> That top IP hammering you 3× harder than anyone else? That's the answer you were asked for.

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

> **Command by command:**
> - `ps aux` — snapshot of every process. The odd flag cluster is historical: `a` = all users' processes, `u` = user-oriented columns, `x` = include processes without a terminal (i.e., daemons — the ones you care about). Expect columns: `USER PID %CPU %MEM ... COMMAND`. The PID is what `kill` needs.
> - `ps aux | grep nginx` — the standard "is it running?" combo. (You'll see the grep match itself in the output — `pgrep nginx`, which just prints matching PIDs, avoids that wrinkle.)
> - `top` / `htop` — live, self-refreshing process view, sorted by CPU. `htop` is the friendlier rewrite: colors, scrolling, tree view, kill from a menu (F9).
> - `kill 1234` — despite the name, kill *sends a signal*; the default SIGTERM means "please shut down" and lets the app clean up (close connections, flush buffers). `kill -9` sends SIGKILL, which the process never sees — the kernel just erases it. Escalate to `-9` only when TERM was ignored.
> - `pkill -f "python3 app.py"` — kill by name instead of PID; `-f` matches against the **f**ull command line, not just the binary name (there may be many `python3`s; only one runs `app.py`).
> - `nohup ./server &` — `&` runs the command in the background; `nohup` (*no hangup*) detaches it from your terminal so it survives your logout. Output lands in `nohup.out`. For anything serious use a systemd unit (§5.2) or `tmux` — nohup is the duct-tape version.

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

> **Tools:** `systemctl` — the control CLI for **systemd**, the init system that starts and supervises services on virtually every modern Linux server. `journalctl` — reads systemd's central log (the *journal*), where stdout/stderr of every unit lands automatically.
> **The systemctl verbs:** `status` = running? since when? recent log lines? (your first command on any misbehaving service — expect a green `active (running)` or red `failed`) · `start`/`stop` act now · `restart` = stop+start (drops connections) vs `reload` = re-read config without dropping (nginx supports it; not every service does) · `enable` doesn't start anything *now* — it registers the unit to start **at boot**. Freshly installed service that vanished after a reboot = someone forgot `enable`.
> **The journalctl flags:** `-u nginx` filter to one **u**nit · `-f` **f**ollow live, like `tail -f` · `--since` takes human-friendly times (`"10 min ago"`, `"2026-07-17 09:00"`) · add `-e` to jump to the end of the log.
> **Why sudo on some:** reading state is free; changing state (`start`/`stop`/`enable`) touches the system → root.

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

> **Command by command:**
> - `df -h` — **d**isk **f**ree per mounted filesystem; `-h` = human-readable sizes (GB, not blocks). Read the `Use%` column; expect a line like `/dev/sdb  251G  180G  58G  76% /`. Anything at 100% explains almost any weird symptom (services failing to write logs, databases refusing writes).
> - `du -sh /var/*` — **d**isk **u**sage of actual directories: `-s` summarize (one total per argument instead of every subdirectory), `-h` human-readable. `df` says "the disk is full"; `du` says *what filled it*. Pair them.
> - `free -h` — memory. The column that matters is `available` — memory the kernel could hand to applications right now. `free` looks alarmingly low on healthy systems because Linux uses spare RAM as disk cache (that's a feature); `available` accounts for that.
> - `uptime` — expect `10:03:11 up 42 days, 2 users, load average: 0.82, 1.10, 0.45`. Load average = how many processes are running or waiting (for CPU, or stuck on disk I/O), averaged over 1/5/15 minutes. Compare against CPU count (`nproc`): load 4 on a 4-core box = fully busy; load 40 = drowning. The 1-vs-15-minute comparison tells you whether things are getting worse or recovering.

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

> **Line by line:**
> - `name="world"` — assignment. The no-spaces rule is real syntax: `name = "world"` runs a command called `name` with arguments `=` and `"world"`.
> - `${name}` — the braces delimit the variable name explicitly; `"Hello, ${name}fish"` works where `"$namefish"` would look up a variable called `namefish`.
> - `${1:?message}` — parameter expansion with teeth: `$1` is the first script argument; `:?` means "if it's missing or empty, print this message to stderr and exit". One line buys you argument validation. `readonly` additionally protects it from being reassigned later.
> - `$(command)` — *command substitution*: run the command, capture its stdout as a string. Here `ls | wc -l` (list files, count lines) yields a file count.

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

> **How the script works, piece by piece:**
> - `log() { ...; }` — a function. `$*` = all arguments joined; `$(date +%H:%M:%S)` stamps each line with the current time (`date` formats via `+` patterns). Result: `[14:02:31] OK http://...`.
> - `local url="$1"` — inside a function, `$1` is the function's first argument (not the script's), and `local` keeps the variable from leaking out.
> - `curl -sf --max-time 5 "$url" > /dev/null` — the actual check. `curl` fetches the URL; `-s` silent (no progress bar), `-f` **fail**: exit non-zero when the server answers with HTTP 400+ (without it, curl exits 0 on a 500 error — the flag that makes curl usable in scripts), `--max-time 5` gives up after 5 s so one hung service can't hang the whole check. We throw away the response body (`> /dev/null`) — only the exit code matters here.
> - `check_service "$svc" || failures=$((failures+1))` — the `||` branch runs on failure; `$(( ))` is shell arithmetic. Note this also stops `set -e` from killing the script on the first bad service — a *handled* failure doesn't trigger exit-on-error.
> - `(( failures > 0 ))` — arithmetic condition; then `exit 1` makes the whole script's exit code non-zero, which is what a CI step or a systemd timer will actually look at.
>
> **Expect:**
> ```
> [14:02:31] OK   http://localhost:8080/health
> [14:02:36] FAIL http://localhost:9090/health
> [14:02:36] 1 service(s) unhealthy
> ```
> …and `echo $?` afterwards prints `1`.

This shape — loop over targets, check, count failures, exit non-zero — is the
skeleton of half the operational scripts ever written.

### 6.5 Debugging scripts

```bash
bash -x script.sh        # trace every command as it runs
shellcheck script.sh     # static analysis (sudo apt install shellcheck) — use it always
```

> **`bash -x`** prints every command *after* expansion, prefixed with `+`, as it executes — so you see what the variables actually contained, which is usually the whole mystery:
> ```
> + url=http://localhost:8080/health
> + curl -sf --max-time 5 http://localhost:8080/health
> ```
> (Toggle it mid-script with `set -x` / `set +x` to trace just one section.)
> **`shellcheck`** is a linter that knows every classic bash trap — unquoted variables, useless `cat`s, `$?` misuse — and explains each finding with a wiki link. Expect output like `SC2086: Double quote to prevent globbing and word splitting.` Running it in CI on every script is a cheap, high-value habit (you'll wire that up in ch 07).

---

## 7. Remote machines: SSH essentials

```bash
ssh user@host                        # log in
ssh-keygen -t ed25519                # generate a key pair (~/.ssh/id_ed25519[.pub])
ssh-copy-id user@host                # install your public key on the server
scp file.txt user@host:/tmp/         # copy file over ssh
ssh user@host 'df -h; uptime'        # run remote commands non-interactively
```

> **Tools:** `ssh` — encrypted remote login and command execution, the transport under nearly all server administration (and under Ansible, ch 14). `ssh-keygen` / `ssh-copy-id` / `scp` are its companions from the same OpenSSH suite.
> **Command by command:**
> - `ssh user@host` — open an interactive shell on `host` as `user`. First connection asks you to confirm the host's fingerprint (then remembers it in `~/.ssh/known_hosts`; a later *fingerprint changed!* warning means the server was reinstalled — or something is impersonating it).
> - `ssh-keygen -t ed25519` — generate a key pair; `-t` picks the algorithm (ed25519 = modern, fast, short keys — the current default choice). Private key `~/.ssh/id_ed25519` stays with you *forever*; `.pub` is shareable freely.
> - `ssh-copy-id user@host` — appends your public key to the server's `~/.ssh/authorized_keys` (asks for your password one last time to do it). After this, key auth works and passwords can be disabled.
> - `scp file.txt user@host:/tmp/` — **s**ecure **c**o**p**y over SSH; the `host:path` syntax marks the remote side, either direction works.
> - `ssh user@host 'df -h; uptime'` — run commands remotely and get their output back on your stdout, no interactive session. This composes with everything in this chapter: loop over a server list, ssh a check to each — congratulations, you've rediscovered what Ansible industrializes in ch 14.

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

Decoding the non-obvious rows:

- `sudo ss -tlnp | grep 8080` — `ss` = **s**ocket **s**tatistics (the modern `netstat`): `-t` TCP, `-l` listening sockets only, `-n` numeric ports (skip slow name lookups), `-p` show the owning process (needs sudo). Expect `LISTEN 0 4096 *:8080 users:(("jenkins",pid=812))` — now you know *what* is squatting on the port. Full treatment in ch 04.
- `du -ah /var | sort -rh | head -20` — `du -a` lists **a**ll files (not just dirs), then sort `-h` compares human-readable sizes (knows 2G > 900M — plain `-n` doesn't), `-r` biggest first, head takes the top 20. The find-the-disk-eater pipeline.
- `grep -rl "old" . | xargs sed -i 's/old/new/g'` — two-stage: `grep -l` prints only file*names* containing the pattern (`-r` recursively); `xargs` takes those names from stdin and hands them to `sed -i` as arguments for in-place replacement. **Bulk edit across a tree — preview the file list (run just the grep) before pulling the trigger.**
- `tar czf a.tgz dir/` / `tar xzf a.tgz` — the archive tool; memorize as **c**reate / e**x**tract, **z** gzip-compress, **f** file name follows. Add `-v` to watch the file list scroll by.
- `curl -LO <url>` — `-L` follow redirects (GitHub releases redirect to a CDN — without `-L` you download an HTML stub), `-O` save under the remote filename.
- `diff -u a b` — compare files; `-u` unified format (the `+++`/`---`/`@@` style you know from `git diff` — this is where that format comes from).

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| WSL2 | Windows Subsystem for Linux (version 2) | Runs a real Linux kernel alongside Windows — the course's dev environment |
| CLI | Command-Line Interface | A text-based way to control a program, as opposed to a GUI |
| VM | Virtual Machine | A fully emulated computer with its own kernel — heavier than a container |
| PID | Process ID | The unique number the kernel assigns to each running process |
| CPU | Central Processing Unit | The processor; `%CPU` columns show how busy it is |
| RAM | Random-Access Memory | Working memory; `free -h` reports how much is available |
| ENV | Environment (variable) | A key/value pair passed into a process's runtime context |
| API | Application Programming Interface | A system's callable interface — what `curl`/`jq` usually talk to |
| JSON | JavaScript Object Notation | The data format modern APIs speak; `jq` is its query tool |
| HTTP | HyperText Transfer Protocol | The protocol behind web requests and most APIs |
| DNS | Domain Name System | Resolves human-readable names to IP addresses |
| IP | Internet Protocol (address) | A device's network address |
| TCP | Transmission Control Protocol | Reliable, ordered network transport (what SSH/HTTP ride on) |
| URL | Uniform Resource Locator | A web address |
| SSH | Secure Shell | Encrypted remote login and command execution |
| ASCII | American Standard Code for Information Interchange | Plain-text encoding; what `file` reports for text files |
| ELF | Executable and Linkable Format | Linux's binary executable file format |
| CDN | Content Delivery Network | Distributed cache serving static content close to users |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 03: Git Workflows](../03-git-workflows/lesson.md)
