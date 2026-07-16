# Chapter 06 — Test

15 questions. Passing: 12/15.

---

**Q1.** Named volume vs bind mount — which do you choose for (a) a Postgres data
directory in a shared dev stack, (b) live-editing source code during development,
and why?

**Q2.** What does `docker compose down -v` do beyond `docker compose down`, and
when is that the wrong command?

**Q3.** Two containers are on the same user-defined network. Container `api`
listens on port 8000 and has no `-p` flag. Can `worker` (same network) reach it?
Can your browser on the host? Explain both.

**Q4.** Why is a user-defined network preferred over Docker's default bridge?

**Q5.** In Compose, plain `depends_on: [db]` still lets the app crash at startup
with "connection refused" to the database. Why, and what is the complete fix?

**Q6.** What problem do multi-stage builds solve? Name the two main benefits of
the resulting image.

**Q7.** This Dockerfile still produces a huge image. Why?
```dockerfile
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y build-essential
RUN make build
RUN apt-get remove -y build-essential && rm -rf /var/lib/apt/lists/*
```

**Q8.** A container was killed with exit code 137. What happened, and what are
the two most common triggers?

**Q9.** Where do orchestrators and `docker ps` get the `healthy`/`unhealthy`
status from, and what's the difference between `--start-period` and `--interval`?

**Q10.** Your `/health` endpoint returns 200 while the app can't reach its
database, so the LB keeps routing traffic into errors. Which check design
principle from ch 04/06 does this violate, and how do you fix it without causing
restart storms?

**Q11.** Why must secrets never be baked into image layers — even if the file is
deleted in a later Dockerfile instruction?

**Q12.** What does mounting `/var/run/docker.sock` into a container effectively
grant, and why?

**Q13.** Write the `docker run` flags to launch `myapp:1.2.0` with: max 256 MB
memory, max 0.5 CPU, read-only root filesystem, and a writable `/tmp`.

**Q14.** In CI you want the build to fail when the image has CRITICAL
vulnerabilities. Give the trivy command that does this.

**Q15.** Design task: sketch a `compose.yaml` (services + networks only, no full
syntax needed) for: nginx reverse proxy (public), API (internal), Postgres
(internal), where the proxy cannot reach Postgres directly.

---

<details>
<summary><b>Answer key</b></summary>

1. (a) Named volume — Docker-managed, survives container replacement, no host
   path coupling. (b) Bind mount — you edit files on the host and the container
   sees changes live.
2. Also removes the named volumes — i.e., **the data**. Wrong whenever you want
   state (DB contents) to survive, e.g., routine restarts of a dev stack.
3. `worker` → yes: same network gives DNS (`api`) and direct access to the
   container's real port 8000. Browser → no: without `-p`, nothing is published
   to the host.
4. User-defined networks provide name-based DNS between containers and clean
   isolation per stack; the default bridge only offers IP-to-IP connectivity
   (and legacy `--link`).
5. `depends_on` orders container *start*, not service *readiness* — Postgres
   accepts connections seconds after the process starts. Fix: a `healthcheck` on
   the db service plus `depends_on: { db: { condition: service_healthy } }`
   (and ideally retry logic in the app).
6. Shipping build toolchains in production images. Benefits: much smaller image
   (faster pulls/deploys) and reduced attack surface (no compilers, shells,
   package managers to abuse).
7. Layers are additive: `build-essential` still fully exists in the layer created
   by the second instruction; the later `remove` only masks it. Fix: install,
   build, and remove in a single `RUN`, or use a multi-stage build.
8. 137 = 128 + 9 → killed by SIGKILL. Triggers: cgroup OOM kill (exceeded memory
   limit) or `docker stop`'s grace period expiring (app ignored SIGTERM).
9. From the image's `HEALTHCHECK` command results (or probe config). `--interval`
   is the time between checks; `--start-period` is a grace window after start
   during which failures don't count — for apps with slow startup.
10. It conflates liveness and readiness. The traffic-gating (readiness) check
    should verify critical dependencies like the DB; the liveness/restart check
    should NOT (or a DB blip restarts every instance at once). Split them.
11. Every layer is preserved and inspectable (`docker history`, `dive`, registry
    pulls); deletion in a later layer hides nothing. Anyone with pull access owns
    the secret; it must be rotated.
12. Root on the host. The Docker daemon runs as root, and socket access allows
    starting a privileged container with the host FS mounted — equivalent to
    arbitrary root execution.
13. `docker run --memory=256m --cpus=0.5 --read-only --tmpfs /tmp myapp:1.2.0`
14. `trivy image --severity CRITICAL --exit-code 1 myapp:1.0.0`
15. Two networks: `frontend` and `backend`. proxy → frontend only... careful:
    proxy must reach the API: proxy on `frontend`, api on `frontend` **and**
    `backend`, db on `backend` only. Only proxy publishes a host port. Proxy and
    db share no network → unreachable, as required.

</details>

**Scoring:** 12+ → [Chapter 07](../07-cicd-github-actions/lesson.md). Below →
redo exercises 6.4, 6.5, 6.7 — Compose readiness and layer semantics are the
recurring interview traps.
