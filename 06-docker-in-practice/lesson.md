# Chapter 06 — Docker in Practice

## Learning objectives

1. Persist data with volumes and bind mounts; know when to use which.
2. Wire containers together with user-defined networks and DNS.
3. Run multi-container stacks with Docker Compose (the daily-driver dev tool).
4. Write multi-stage Dockerfiles that produce small, secure production images.
5. Apply the container security baseline: scan, pin, minimize, drop privileges.
6. Set resource limits and health checks.

---

## 1. Persistent data: volumes and bind mounts

Chapter 05 ended on the cliffhanger: writable layers die with the container.
Two solutions:

### Named volumes — Docker-managed persistence

```bash
docker volume create pgdata
docker run -d --name db -v pgdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=secret postgres:16
docker volume ls
docker volume inspect pgdata
```

> **Command by command:**
> - `docker volume create pgdata` — makes a named, Docker-managed storage area (it lives under `/var/lib/docker/volumes/`, but you never touch that path directly). Optional — `-v pgdata:...` auto-creates it — but explicit creation reads better in scripts.
> - `-v pgdata:/var/lib/postgresql/data` — the mount syntax: `VOLUME_NAME:CONTAINER_PATH`. Postgres writes its entire database into that container path, so the mount redirects the data onto the volume. (The `-e POSTGRES_PASSWORD` is required by the postgres image on first run — it initializes the superuser.)
> - `docker volume ls` / `inspect` — list volumes / show one's details (driver, creation time, mountpoint). Note what's *missing*: there is no size column — `docker system df -v` answers that.
> **How to read the mount decision:** if the first character before `:` is a *path* (`~/site:/usr/...`), it's a bind mount; if it's a *name* (`pgdata:...`), it's a volume. Same flag, different behavior — the table below is the decision guide.

Kill the container, run a new one with the same `-v pgdata:...` → data intact.
Volumes live under Docker's control, survive container removal, and are the way
to run stateful services (databases, registries, Jenkins in ch 08).

### Bind mounts — a host directory mapped in

```bash
docker run -d -v ~/devops/site:/usr/share/nginx/html:ro nginx:alpine
```

Host path ↔ container path, live in both directions. Use for: source code during
development (edit on host, app in container sees changes instantly), and config
files. `:ro` = read-only — use it whenever the container shouldn't write.

| | Named volume | Bind mount |
|---|---|---|
| Managed by | Docker | you |
| Best for | databases, service state | dev source code, configs |
| Portable across hosts | contents live in Docker's area | depends on host layout |
| Performance in Docker Desktop | fast | slower across the Windows/WSL boundary — keep code on the Linux side |

**tmpfs mounts** (`--tmpfs /tmp`) exist too: RAM-only, gone at stop — for scratch
or secrets you never want on disk.

---

## 2. Container networking

Docker's default `bridge` network is legacy-ish: containers can talk by IP only.
**User-defined networks add DNS by container name** — always create your own:

```bash
docker network create appnet
docker run -d --name db --network appnet -e POSTGRES_PASSWORD=s3cret postgres:16
docker run -d --name api --network appnet -p 8000:8000 myapp:1.0.0
# inside 'api', the database is reachable as hostname "db":
docker exec api getent hosts db
```

> **Command by command:**
> - `docker network create appnet` — a new isolated network with Docker's DNS enabled. Containers attach via `--network appnet` at run time.
> - The two `docker run`s — note what's asymmetric: `db` gets **no `-p`** (nothing outside needs Postgres), `api` publishes `8000` (humans need it). Inside the network, `api` reaches Postgres at `db:5432` — container name as hostname, real container port.
> - `docker exec api getent hosts db` — proves the DNS claim: `getent hosts` performs a name lookup *inside* the `api` container. Expect `172.18.0.2  db`. When "api can't reach db", this is the first diagnostic: name resolves? then check same-network membership with `docker network inspect appnet`.

Key mental model:

- Same network → containers reach each other by **name**, on the **container's
  real port** (no `-p` needed for container-to-container traffic).
- `-p` is only for exposing to the **host/outside world**.
- Different networks → no connectivity (that's the isolation feature: put the DB
  and API on `backend`, only the proxy on both `backend` and `frontend`).

```bash
docker network ls
docker network inspect appnet      # who's on it, what IPs
docker network connect appnet other-container
```

This name-based service discovery is exactly the model Kubernetes Services
generalize in ch 11 — learn it here where it's simple.

---

## 3. Docker Compose — declarative multi-container apps

Typing `docker run` incantations doesn't scale past one container. Compose
declares the whole stack in `compose.yaml` (also accepted: `docker-compose.yml`):

```yaml
services:
  api:
    build: .                    # build from local Dockerfile
    image: myapp:dev
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://app:apppw@db:5432/appdb
      APP_VERSION: dev
    depends_on:
      db:
        condition: service_healthy   # wait for db's healthcheck, not just start
    develop:
      watch:                    # optional: live-reload workflows
        - action: sync
          path: .
          target: /app

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: apppw
      POSTGRES_DB: appdb
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d appdb"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

The daily commands:

```bash
docker compose up -d          # create network + volumes + containers
docker compose ps
docker compose logs -f api
docker compose exec api sh
docker compose up -d --build  # rebuild changed images
docker compose down           # stop + remove containers & network
docker compose down -v        # ...and volumes (data!) — deliberate act
```

> **Command by command** (all read `compose.yaml` from the current directory — run them where the file lives):
> - `docker compose up -d` — create everything the file declares (network, volumes, containers), in dependency order, detached. Re-running after edits is safe: Compose diffs desired vs actual and recreates only what changed — declarative thinking you'll meet again in Terraform (ch 13) and Kubernetes (ch 11).
> - `docker compose ps` / `logs -f api` / `exec api sh` — the ch 05 commands, scoped to this project's containers and addressed by *service* name instead of container name.
> - `--build` — rebuild images for services with a `build:` key before starting. Without it, Compose reuses the existing image even though you changed the code — the classic "why isn't my change showing up".
> - `down` — stop and remove containers and the network. Volumes survive (your data). `down -v` removes those too — the full factory reset; type it knowing that.
> **Expect from `up -d`:**
> ```
> ✔ Network myapp_default    Created
> ✔ Container myapp-db-1     Healthy
> ✔ Container myapp-api-1    Started
> ```
> Note `db` reaching `Healthy` (its healthcheck passed) *before* `api` starts — that's `condition: service_healthy` doing its job.

What Compose gives you for free: a dedicated network (services reach each other
by service name), ordered startup with health conditions, one-command lifecycle,
and a **committed, reviewable description of the dev environment** — "clone the
repo, run `docker compose up`" replaces a 3-page setup wiki.

Notes that save pain:

- `depends_on` without `condition: service_healthy` only orders *starting*, not
  *readiness* — the classic "API crashed because Postgres wasn't accepting
  connections yet."
- Environment-specific overrides: `compose.override.yaml` is merged automatically;
  `docker compose -f compose.yaml -f compose.prod.yaml up` for explicit stacking.
- Secrets don't belong in the YAML — for dev, `env_file: .env` (gitignored)
  works; one step better is Compose's native `secrets:` mechanism, which mounts
  each secret as a **file** instead of an env var (env vars leak into
  `docker inspect`, error reports, and child processes; files don't):

  ```yaml
  services:
    api:
      secrets: [db_password]            # appears at /run/secrets/db_password
  secrets:
    db_password:
      file: ./secrets/db_password.txt   # gitignored
  ```

  The app reads `/run/secrets/db_password` at startup (many images support a
  `*_FILE` env convention, e.g. `POSTGRES_PASSWORD_FILE`, for exactly this).
  Real secret management is ch 16.
- Compose is a **dev/single-host tool**. Production orchestration across many
  hosts is Kubernetes (ch 11) — same concepts, bigger machine.

---

## 4. Multi-stage builds — small, clean production images

Problem: building software needs compilers, dev headers, npm — none of which
should ship to production (size, attack surface). Solution: build in one stage,
copy only artifacts into a minimal final stage.

Go example (dramatic because Go compiles to a static binary):

```dockerfile
# ---- build stage ----
FROM golang:1.23 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/server .    # static binary (no C deps) → runs on distroless

# ---- final stage ----
FROM gcr.io/distroless/static-debian12
COPY --from=build /out/server /server
USER nonroot
ENTRYPOINT ["/server"]
```

> **The mechanics:** `FROM ... AS build` names a stage; a later `COPY --from=build src dst` reaches back into it. **Only the final stage becomes the shipped image** — everything in earlier stages (compiler, source code, caches) is simply left behind. `gcr.io/distroless/static-debian12` is a Google-maintained base containing only libc-level essentials: no shell, no `apt`, no busybox — which is why `docker exec ... sh` won't work on it, and why its attack surface is so small.

Result: ~1 GB build environment → ~10 MB final image with *no shell, no package
manager, nothing to exploit*.

Python/Node equivalent idea:

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY app.py .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["python", "app.py"]
```

Image-size levers, in order of impact:

1. **Smaller base**: `-slim` → `-alpine` (musl caveats) → distroless → `scratch`.
2. **Multi-stage** — leave the toolchain behind.
3. **Layer hygiene**: combine `RUN apt-get update && apt-get install -y x && rm -rf /var/lib/apt/lists/*`
   in ONE instruction (deleting in a later layer does NOT shrink the image — the
   file still exists in the earlier layer).
4. `.dockerignore` — don't send `.git`/`node_modules` into the context.

Check your work: `docker images`, `docker history <img>`, and the excellent
`dive <img>` tool (wagoodman/dive) for layer-by-layer inspection.

---

## 5. Health checks and resource limits

### HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -sf http://localhost:8000/health || exit 1
```

> **How it works:** Docker runs the `CMD` *inside* the container on a schedule; exit 0 = healthy, non-zero = one strike. The knobs: `--interval` how often · `--timeout` how long the command may take · `--start-period` grace time after start during which failures don't count (app still booting) · `--retries` consecutive failures before the status flips to `unhealthy`. The `curl -sf` is ch 04's script-friendly health probe — `-f` turns an HTTP 500 into a non-zero exit; `|| exit 1` normalizes any failure to exit code 1 (Docker treats other codes as reserved). Requires curl to exist in the image — slim images often use `wget -q --spider` or a tiny built-in healthcheck binary instead.

`docker ps` then shows `healthy`/`unhealthy`; Compose `depends_on` conditions and
orchestrators key off it. (In Kubernetes you'll define probes in the pod spec
instead — same idea, different location.)

### Resource limits

An unconstrained container can eat the whole host — one memory leak takes down
every neighbor.

```bash
docker run -d --memory=512m --cpus=1.5 myapp:1.0.0
```

Compose:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.5"
```

Behavior to know: exceed the memory limit → the kernel **OOM-kills** the process
(exit code 137 = 128 + SIGKILL(9); you'll see it in `docker inspect` and in K8s
events forever). CPU limits throttle rather than kill.

---

## 6. Container security baseline

The checklist to apply to every image you ship (ch 16 goes deeper):

1. **Pin base images** to specific tags; rebuild regularly to pick up patches.
2. **Minimal base** — every package is attack surface. Distroless/slim > full.
3. **Non-root `USER`** — mandatory.
4. **No secrets in images** — not in ENV in the Dockerfile, not in COPY'd files;
   layers are readable by anyone with the image (`docker history`, `dive`).
   Inject at runtime (env/secret stores).
5. **Scan images** and fail builds on critical findings:

```bash
# Trivy — the standard open-source scanner
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image myapp:1.0.0
# or install natively: sudo apt install trivy (via aquasecurity repo)
trivy image --severity HIGH,CRITICAL --exit-code 1 myapp:1.0.0
```

> **Tool:** `trivy` (by Aqua Security) — scans an image's packages against CVE (known-vulnerability) databases. The first form runs Trivy itself as a container; mounting `docker.sock` lets it inspect your local images (with the security caveat that mounting the socket grants daemon control — fine for a scan on your own machine).
> **Flags:** `image` scan an image (also: `fs` a directory, `config` IaC files — ch 16) · `--severity HIGH,CRITICAL` report only these levels — an unfiltered scan of any real base image yields hundreds of LOW findings and trains you to ignore the report · `--exit-code 1` exit non-zero when findings remain.
> **Expect:**
> ```
> myapp:1.0.0 (debian 12.6)
> Total: 2 (HIGH: 2, CRITICAL: 0)
> ┌────────────┬────────────────┬──────────┬────────────┬───────────────┐
> │  Library   │ Vulnerability  │ Severity │ Installed  │ Fixed Version │
> ├────────────┼────────────────┼──────────┼────────────┼───────────────┤
> │ libssl3    │ CVE-2026-xxxx  │ HIGH     │ 3.0.11-1   │ 3.0.13-1      │
> ```
> The *Fixed Version* column is the actionable part — usually the fix is just rebuilding on a newer base image.

That `--exit-code 1` is the CI hook: scan fails → pipeline fails (ch 07).

6. **Read-only where possible**: `docker run --read-only --tmpfs /tmp ...` makes
   the root FS immutable at runtime.
7. **Don't run privileged / don't mount the Docker socket** into app containers —
   `-v /var/run/docker.sock` = root on the host, full stop. (Jenkins in ch 08
   will force us to discuss this tradeoff honestly.)

---

## 7. Worked example — the full dev stack

The pattern you'll reuse in ch 07's CI and ch 15's monitoring stack:

```
myapp/
├── app.py               # Flask app from ch05, now reading DATABASE_URL
├── requirements.txt     # flask + psycopg
├── Dockerfile           # multi-stage, non-root, HEALTHCHECK
├── .dockerignore
└── compose.yaml         # api + db + adminer (DB UI)
```

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://app:apppw@db:5432/appdb
    depends_on:
      db: { condition: service_healthy }
  db:
    image: postgres:16
    environment: { POSTGRES_USER: app, POSTGRES_PASSWORD: apppw, POSTGRES_DB: appdb }
    volumes: [ "pgdata:/var/lib/postgresql/data" ]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      retries: 10
  adminer:
    image: adminer:4
    ports: ["8082:8080"]
volumes:
  pgdata: {}
```

`docker compose up -d` → full environment. `docker compose down -v` → gone
without a trace. That reproducibility is the point.

## Further reading

- Docker docs: "Storage", "Networking", "Compose", "Multi-stage builds".
- `dive` (github.com/wagoodman/dive), Trivy docs (aquasecurity.github.io/trivy).
- OWASP Docker Security Cheat Sheet.

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| DNS | Domain Name System | How containers on a user-defined network resolve each other by name |
| RAM | Random-Access Memory | Working memory; what `--memory` limits and OOM-killer watches |
| MB / GB | Megabyte / Gigabyte | Units of image size shrunk by multi-stage builds |
| CVE | Common Vulnerabilities and Exposures | Public ID for a known security vulnerability, what Trivy scans for |
| OWASP | Open Web Application Security Project | Nonprofit behind the security cheat sheets referenced throughout |
| OOM | Out Of Memory | Kernel condition that kills a container exceeding its memory limit |
| YAML | YAML Ain't Markup Language | The indentation-based format `compose.yaml` is written in |
| DB | Database | Shorthand for the stateful service (e.g. Postgres) in the stack |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 07: CI/CD & GitHub Actions](../07-cicd-github-actions/lesson.md)
