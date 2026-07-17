# Chapter 05 — Docker Fundamentals

## Learning objectives

1. Explain what containers are (and how they differ from VMs) in terms of kernel primitives.
2. Run, inspect, and manage containers fluently with the Docker CLI.
3. Write Dockerfiles and understand images as stacked, cached layers.
4. Push/pull images to registries; understand tags and digests.
5. Containerize a real application.

---

## 1. What a container actually is

A container is **not** a lightweight VM. It's a normal Linux process (or process
tree) that the kernel isolates and constrains:

- **Namespaces** — what the process can *see*: its own process tree (PID), network
  stack (net), filesystem mounts (mnt), hostname (uts), users (user). Inside the
  container, your app is PID 1 and sees only its own world.
- **cgroups** — what the process can *use*: caps on CPU, memory, IO.
- **Union/overlay filesystem** — the container's root FS is assembled from stacked
  read-only image layers plus one writable layer on top.

| | VM | Container |
|---|---|-----------|
| Isolation | hardware-virtualized, own kernel | kernel-enforced, **shared kernel** |
| Startup | minutes | milliseconds–seconds |
| Size | GBs | MBs |
| Density | ~10s per host | ~100s–1000s per host |

Consequences worth internalizing:
- Containers share the host kernel → a Linux container needs a Linux kernel
  (Docker Desktop on Windows runs one via WSL2 — that's why chapter 02 set it up).
- Weaker isolation than VMs → don't treat container boundaries as a hard security
  wall between mutually hostile tenants.
- **When the main process (PID 1) exits, the container stops.** A container isn't
  "a machine that runs things"; it *is* one running command.

Why containers took over DevOps: the image bundles app + runtime + libraries + OS
userland into one immutable, versioned artifact. "Works on my machine" becomes
"works in the image" — the same bytes run in dev, CI, staging, and prod. This is
the artifact the entire pipeline (ch 07–12) builds, scans, promotes, and deploys.

**Terminology:** *image* = the frozen template (like a class). *Container* = a
running (or stopped) instance of an image (like an object). *Registry* = where
images are stored and pulled from.

---

## 2. Running containers — the CLI core

```bash
docker run nginx:1.27                   # pull if absent + create + start (foreground)
docker run -d --name web nginx:1.27    # -d detached, named
docker run -d -p 8080:80 nginx:1.27    # publish: host 8080 → container 80
docker run --rm -it ubuntu:24.04 bash  # interactive shell; --rm auto-remove on exit
docker run -e LOG_LEVEL=debug myapp    # set environment variable
```

> **Tool:** `docker` — the CLI talking to the Docker *daemon* (the background service that actually builds and runs containers). Every `docker ...` command is an API call to that daemon.
> **`docker run` decoded** — it's three steps fused: pull the image if not local → create a container from it → start it.
> **Flags:** `-d` **d**etached: run in the background and print the container ID; without it the container's output owns your terminal · `--name web` a handle for later commands (otherwise you get a random name like `vigorous_hopper`) · `-p 8080:80` **p**ublish a port, always `HOST:CONTAINER` order — "host port 8080 forwards to container port 80" · `-it` **i**nteractive + **t**ty, the pair you need for a usable shell · `--rm` auto-delete the container when it exits (perfect for throwaway experiments) · `-e KEY=value` set an **e**nvironment variable inside — the standard way to configure containerized apps (ch 01's "same artifact, different config").
> **Expect:** detached mode prints a 64-char container ID and returns immediately; `curl localhost:8080` then reaches nginx. If the terminal seems to "hang", you forgot `-d` — the container is running in your foreground.

`-p HOST:CONTAINER` port mapping is NAT (ch 04): the container has its own network
namespace and private IP; publishing wires a host port to it.

### Lifecycle and inspection

```bash
docker ps                    # running containers
docker ps -a                 # including stopped ones
docker stop web              # SIGTERM, 10s grace, then SIGKILL
docker start web
docker rm web                # remove (stopped) container
docker rm -f web             # force: kill + remove

docker logs web              # stdout/stderr of PID 1 — containerized apps log to stdout!
docker logs -f --tail 50 web # follow
docker exec -it web sh       # shell INSIDE a running container (debugging)
docker inspect web           # full JSON: config, network, mounts...
docker inspect -f '{{.NetworkSettings.IPAddress}}' web
docker stats                 # live CPU/mem per container
docker cp web:/etc/nginx/nginx.conf .   # copy files in/out
```

> **Command by command:**
> - `docker ps` — running containers: ID, image, command, uptime, ports, name. `-a` adds stopped ones — essential when a container crashed and "disappeared" (it didn't; it's just not running).
> - `docker stop web` — sends SIGTERM to the container's main process, waits 10 s for a graceful shutdown, then SIGKILLs (the ch 02 signals story, now with a deadline). `docker rm` removes a *stopped* container's record; `-f` force-combines kill+remove.
> - `docker logs web` — everything PID 1 wrote to stdout/stderr, even after the container died. `-f` follows live, `--tail 50` starts from the last 50 lines. **This is always the first command on a misbehaving container.**
> - `docker exec -it web sh` — start an *additional* process (here a shell) inside a running container. Look around, check env vars, curl localhost — then leave. (Some minimal images have no `sh`; try `bash` or accept that distroless images are shell-less by design — ch 06.)
> - `docker inspect web` — the container's entire configuration and state as JSON; `-f` applies a Go template to pluck one field, or pipe to `jq` (ch 02) — both spellings are common.
> - `docker stats` — live per-container CPU/memory table; the quick answer to "which container is eating the box?"
> - `docker cp` — copy files between host and container, either direction (`web:/path` names the container side). Debugging convenience — anything permanent belongs in the image or a volume.

Two habits that mark experienced users:
1. **Logs to stdout/stderr**, never to files inside the container — `docker logs`
   (and every log collector in ch 15) reads the stream.
2. `docker exec` is for *inspecting*, not fixing. Changes inside a running
   container die with it. Fix the image instead.

### Cleaning up

```bash
docker system df             # what's eating disk
docker container prune       # remove stopped containers
docker image prune -a        # remove unused images
docker system prune          # all of the above (careful)
```

> **Why this section exists:** Docker never deletes anything on its own; stopped containers, superseded image versions, and build cache accumulate until the disk fills (ch 02: full disk = classic outage). `docker system df` shows the damage per category. The `prune` commands delete what nothing references — `image prune -a` removes **a**ll images not used by at least one container, not just untagged ones. Each prompts for confirmation and prints what it reclaimed.

---

## 3. Images and layers

An image = ordered stack of read-only layers + metadata (env, default command,
exposed ports). Each Dockerfile instruction that changes the filesystem creates a
layer. Layers are content-addressed and **shared**: ten images based on
`ubuntu:24.04` store Ubuntu's layers once.

```bash
docker pull python:3.12-slim
docker images                          # local images with sizes
docker history python:3.12-slim       # the layer stack and what created each
```

> **Command by command:**
> - `docker pull` — download an image (all its layers) without running anything. Watch the output: `Already exists` per layer is layer-sharing working for you — only missing layers download.
> - `docker images` — local images with tags and sizes. When this list is huge, see "Cleaning up" above.
> - `docker history` — one line per layer, newest first: the Dockerfile instruction that created it and its size. Expect rows like `RUN pip install -r requirements.txt   58MB`. **This is how you find what bloats an image** — and a first hint that anything COPY'd into a layer (secrets included) stays visible in it forever (ch 06 security section).

When a container runs, Docker adds a thin writable layer on top (copy-on-write).
Delete the container → that layer is gone. **Persistent data therefore needs
volumes** (ch 06).

### Tags and digests

`python:3.12-slim` = repository `python`, tag `3.12-slim`. Crucial facts:

- A tag is a **movable pointer**, not a version guarantee. `latest` today ≠
  `latest` tomorrow. Even `3.12-slim` gets patched in place.
- A **digest** (`python@sha256:ab12...`) is immutable — the exact bytes.
- `latest` is just the default tag name — it is NOT automatically the newest, and
  depending on it in production is an anti-pattern (which version is even running?).

Rule for the course and for life: **deploy by specific tag (or digest), never
`latest`.**

---

## 4. Dockerfile — building images

The example app for this chapter (`app.py`, Flask):

```python
from flask import Flask, jsonify
import os, socket

app = Flask(__name__)

@app.get("/")
def index():
    return jsonify(message="Hello from DevOps course",
                   host=socket.gethostname(),
                   version=os.environ.get("APP_VERSION", "dev"))

@app.get("/health")
def health():
    return jsonify(status="ok")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

`requirements.txt`:

```
flask==3.0.3
```

The Dockerfile:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy dependency manifest FIRST — see caching section for why
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV APP_VERSION=1.0.0
EXPOSE 8000

# Run as non-root (security baseline)
RUN useradd --create-home appuser
USER appuser

CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t myapp:1.0.0 .
docker run -d --name myapp -p 8000:8000 myapp:1.0.0
curl localhost:8000/health
```

> **`docker build` decoded:** `-t myapp:1.0.0` **t**ags the result (name:version — untagged images are unusable `<none>` orphans); the final `.` is the **build context** — the directory sent to the daemon, which `COPY` instructions read from (and which `.dockerignore` filters). Forgetting the dot is the #1 build-command typo.
> **Expect:** one `[N/6]` step per Dockerfile instruction, `CACHED` markers on layers reused from previous builds (the caching section below explains when), and finally:
> ```
> => => naming to docker.io/library/myapp:1.0.0
> ```
> Then `docker run` starts it exactly like any pulled image — locally built and registry images are the same thing — and the `curl` should return `{"status":"ok"}`. If it doesn't: `docker logs myapp`.

### Instruction reference

| Instruction | Purpose | Notes |
|-------------|---------|-------|
| `FROM` | base image | always pin a tag |
| `WORKDIR` | set working dir | creates it if needed |
| `COPY` | files from build context → image | prefer over `ADD` (ADD also unpacks/URLs — surprising) |
| `RUN` | execute command at **build** time | each RUN = a layer |
| `ENV` | environment variable (build + runtime) | |
| `ARG` | build-time-only variable | `docker build --build-arg` |
| `EXPOSE` | documents the port | metadata only — does NOT publish |
| `USER` | user for subsequent instructions + runtime | non-root! |
| `CMD` | default command at **run** time | exec form `["a","b"]` preferred |
| `ENTRYPOINT` | fixed executable; CMD becomes its args | for CLI-style images |

`CMD` vs `ENTRYPOINT` in one line: `docker run image X` **replaces** CMD but is
**appended** to ENTRYPOINT. Exec form (`["python","app.py"]`) matters because
shell form (`python app.py`) wraps in `/bin/sh -c`, and then your app isn't PID 1
and **doesn't receive SIGTERM** → every stop takes the full 10s kill timeout.

### The build cache — the key to fast builds

Docker reuses a cached layer if the instruction AND its inputs are unchanged —
but a cache miss invalidates **every subsequent layer**. Hence the golden
ordering: least-changing first.

```dockerfile
# GOOD: deps reinstalled only when requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .                      # code changes only bust cache from here

# BAD: any code edit reinstalls all dependencies
COPY . .
RUN pip install -r requirements.txt
```

This single idiom often cuts CI build times from minutes to seconds.

### .dockerignore

The build context (everything in `.`) is sent to the daemon. Exclude junk:

```
.git
__pycache__/
*.log
.env
node_modules/
```

Also a security matter: without it, `.env` files and `.git` history can end up
inside images.

---

## 5. Registries — shipping images

A registry stores images; Docker Hub is the default public one. Others: GitHub
Container Registry (ghcr.io), GitLab Registry, cloud registries (ECR/ACR/GAR),
self-hosted (Harbor, Nexus — ch 10).

Image references decompose as `[registry/][namespace/]name[:tag]`:
`nginx` → `docker.io/library/nginx:latest`.

```bash
docker login                          # Docker Hub (or: docker login ghcr.io)
docker tag myapp:1.0.0 yourname/myapp:1.0.0     # a tag is just an alias/pointer
docker push yourname/myapp:1.0.0
docker pull yourname/myapp:1.0.0      # from any other machine
```

> **Command by command:**
> - `docker login` — authenticates against a registry (Docker Hub by default; pass a hostname like `ghcr.io` for others) and caches the credential locally. In CI this happens with `--password-stdin` and an injected token — never a typed password (ch 07–08).
> - `docker tag SOURCE TARGET` — adds another name to the *same* image (no copying — both names point to identical layers). Needed because the push destination is encoded in the name: `myapp:1.0.0` has no registry/namespace, so it can't be pushed anywhere; `yourname/myapp:1.0.0` can.
> - `docker push` — uploads the layers the registry doesn't already have (`Layer already exists` = dedup at work), then the image manifest.
> - `docker pull` — the reverse. Expect a digest line at the end of both: `sha256:ab12...` — the immutable identity of what you just shipped.

Typical CI flow you'll automate in ch 07: build → tag with the version (and the
git SHA) → push. Then deployment (ch 11–12) is just "pull tag X and run it" —
the registry is the hand-off point between CI and the runtime platform.

Docker Hub rate-limits anonymous pulls — one practical reason real teams run
authenticated pulls or their own registry/proxy.

---

## 6. Worked example — containerize, ship, run

End-to-end, assuming a Docker Hub account (`<you>`):

```bash
mkdir -p ~/devops/ch05/myapp && cd ~/devops/ch05/myapp
# create app.py, requirements.txt, Dockerfile, .dockerignore from §4
docker build -t <you>/devops-myapp:1.0.0 .
docker run -d --name myapp -p 8000:8000 <you>/devops-myapp:1.0.0
curl -s localhost:8000 | jq .
docker push <you>/devops-myapp:1.0.0

# simulate "another machine":
docker rm -f myapp && docker rmi <you>/devops-myapp:1.0.0
docker run -d --name myapp -p 8000:8000 <you>/devops-myapp:1.0.0   # pulls from Hub
curl -s localhost:8000/health
```

> **The one new command:** `docker rmi` — **r**e**m**ove **i**mage (locally; the registry copy is untouched). The `rm -f` + `rmi` pair wipes every local trace, so the final `docker run` *must* pull from the registry — proving the image truly round-tripped. Watch its output for the `Pulling from yourname/myapp` lines: that's your artifact coming back from the outside world.

That loop — build, push, pull elsewhere, run — is the beating heart of every
container pipeline you'll build for the rest of the course.

## Common beginner errors decoded

| Error | Meaning |
|-------|---------|
| `port is already allocated` | host port taken — pick another `-p` |
| `Conflict. The container name ... is already in use` | `docker rm` the old one or rename |
| container exits immediately | PID 1 finished (e.g. daemonizing web server, or a one-shot command) — check `docker logs` |
| `pull access denied / not found` | typo, private image without login, or wrong registry |
| changes vanished after restart | you edited the writable layer, then removed the container — fix the image or use volumes |

## Further reading

- Docker docs: "Docker overview" and Dockerfile reference.
- `docker run --help` — genuinely, skim it once.

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 06: Docker in Practice](../06-docker-in-practice/lesson.md)
