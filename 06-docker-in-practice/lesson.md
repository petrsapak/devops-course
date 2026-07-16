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
- Secrets don't belong in the YAML — use `env_file: .env` (gitignored) for dev;
  real secret management is ch 16.
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
RUN CGO_ENABLED=0 go build -o /out/server .

# ---- final stage ----
FROM gcr.io/distroless/static-debian12
COPY --from=build /out/server /server
USER nonroot
ENTRYPOINT ["/server"]
```

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

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 07: CI/CD & GitHub Actions](../07-cicd-github-actions/lesson.md)
