# Chapter 05 — Test

15 questions. Passing: 12/15.

---

**Q1.** The fundamental difference between a container and a VM is:
- a) Containers are smaller VMs
- b) Containers are isolated processes sharing the host kernel; VMs virtualize hardware and run their own kernel
- c) VMs can run Linux, containers cannot
- d) Containers cannot access the network

**Q2.** Which two kernel features provide, respectively, *what a container can
see* and *what it can use*?

**Q3.** `docker run -d ubuntu:24.04` exits immediately while
`docker run -d nginx:1.27` keeps running. Why?

**Q4.** `docker run -p 8080:80 nginx` — which is the host port and which is the
container port?

**Q5.** What is the difference between `docker stop` and `docker rm -f`, including
the signals involved?

**Q6.** Why should containerized applications write logs to stdout/stderr instead
of files?

**Q7.** Explain why this Dockerfile ordering is bad and rewrite it:
```dockerfile
FROM node:22-slim
WORKDIR /app
COPY . .
RUN npm ci
CMD ["node", "server.js"]
```

**Q8.** `EXPOSE 8000` in a Dockerfile — what does it actually do?
- a) Publishes port 8000 on the host
- b) Opens the firewall for port 8000
- c) Documents the port; publishing still requires `-p` at run time
- d) Makes the app listen on 8000

**Q9.** `CMD ["python", "app.py"]` vs `CMD python app.py` — name the practical
difference involving signals.

**Q10.** What is the difference between an image tag and a digest, and why is
deploying `myapp:latest` to production an anti-pattern?

**Q11.** A developer fixes a config problem with `docker exec -it prod-app vi
/app/config.yml`. The fix works. What's wrong with this, and what happens on the
next deployment?

**Q12.** You edit one line of application code. Your CI rebuild takes 4 minutes,
almost all in `pip install`. The Dockerfile copies all sources before installing
dependencies. What one-line reordering fixes it and why?

**Q13.** Decompose the reference `ghcr.io/acme/api:2.3.1` into its parts, and
write the equivalent full form of the bare reference `redis`.

**Q14.** Why does the course insist on `USER appuser` (non-root) in Dockerfiles?

**Q15.** A container "loses" data every deployment: users upload files into
`/app/uploads`, and after each release they're gone. Explain the mechanism (which
layer held the files and what deployment does) — the fix is chapter 06's topic,
but name it.

---

<details>
<summary><b>Answer key</b></summary>

1. **b**
2. Namespaces (visibility) and cgroups (resource limits).
3. A container runs exactly one main process and lives as long as it does. Bare
   `ubuntu`'s default command (`bash`) exits instantly with no TTY; nginx's
   default command runs a server in the foreground.
4. `8080` host, `80` container (`-p HOST:CONTAINER`).
5. `stop`: SIGTERM, 10 s grace for cleanup, then SIGKILL; container remains (stopped).
   `rm -f`: SIGKILL immediately and the container is deleted.
6. `docker logs` and all standard log collectors consume the stdout/stderr
   stream; files inside the container are invisible to tooling and die with the
   container.
7. Any code change invalidates the `COPY . .` layer and forces full `npm ci`.
   Fix:
   ```dockerfile
   COPY package.json package-lock.json ./
   RUN npm ci
   COPY . .
   ```
8. **c**
9. Exec form runs python as PID 1, which receives SIGTERM on stop → graceful
   shutdown. Shell form wraps it in `/bin/sh -c`; the shell gets the signal and
   doesn't forward it → app is SIGKILLed after the 10 s timeout.
10. Tag = movable pointer (can point to different bytes over time); digest =
    immutable content hash. With `latest` you can't tell what's running, can't
    roll back to "the previous latest", and two pulls may yield different images.
11. Changes live only in that container's writable layer — undocumented,
    unreviewed, unreproducible. Next deployment replaces the container and the
    fix silently vanishes. The fix belongs in the image/config in version control.
12. Copy the dependency manifest first, install, then copy sources — dependency
    layer stays cached across code-only changes (see Q7 answer).
13. Registry `ghcr.io`, namespace `acme`, repository `api`, tag `2.3.1`.
    `redis` = `docker.io/library/redis:latest`.
14. If the app is compromised, the attacker holds root *inside* the container —
    combined with any container-escape or misconfigured mount, that's root-level
    damage. Non-root is the cheapest blast-radius reduction there is.
15. Uploads were written to the container's writable copy-on-write layer.
    Deployment replaces the container (new one from the image) → the writable
    layer with the uploads is discarded. Fix: mount a **volume** for
    `/app/uploads` (chapter 06).

</details>

**Scoring:** 12+ → [Chapter 06](../06-docker-in-practice/lesson.md). Below →
redo exercises 5.3, 5.5, 5.6 — layers, cache, and PID 1 are the concepts that stick
only through repetition.
