# Chapter 05 — Exercises

Work in `~/devops/ch05`. Docker Desktop must be running.

---

## Exercise 5.1 — Container lifecycle drill

1. Run nginx detached, named `web1`, publishing host port 8081 → container 80.
2. Curl it. Check its logs — find your request's access-log line.
3. Open a shell inside with `docker exec` and `cat /etc/nginx/conf.d/default.conf`.
4. Stop it; confirm it's absent from `docker ps` but present in `docker ps -a`.
5. Start it again (same container), then remove it fully.

**Verify:** after step 5, `docker ps -a` no longer lists `web1`.

## Exercise 5.2 — Understand "the container IS the process"

1. `docker run -d --name sleeper ubuntu:24.04 sleep 300` — why does this stay
   running while `docker run -d ubuntu:24.04` exits instantly? Check with
   `docker ps -a` and explain.
2. `docker exec sleeper ps aux` — what is PID 1?
3. `docker stop sleeper` and time it (`time docker stop sleeper`). Why did it
   take ~10 seconds? (Hint: what does `sleep` do with SIGTERM? Nothing — it
   ignores nothing but also doesn't exit... actually it dies on SIGTERM. Compare
   with `docker run -d --name ignorer ubuntu:24.04 sh -c 'trap "" TERM; sleep 300'`
   and `time docker stop ignorer`.)

**Verify:** `sleeper` stops fast; `ignorer` takes ~10s (SIGTERM trapped/ignored →
Docker escalates to SIGKILL after the grace period). Clean up both.

## Exercise 5.3 — Ephemeral writable layer

1. Run `docker run -it --name scratch ubuntu:24.04 bash`, create
   `/root/important.txt` with some text, exit.
2. `docker start scratch && docker exec scratch cat /root/important.txt` — still there?
3. Now `docker rm -f scratch` and run a **new** container from the same image.
   Is the file there?

**Verify:** file survives stop/start of the *same* container, but not a new
container — state lives in the container's writable layer, not the image. Say in
one sentence where durable data must go instead (ch 06 answers it: volumes).

## Exercise 5.4 — Build the course app image

Create the Flask app from lesson §4 (app.py, requirements.txt, Dockerfile,
.dockerignore) in `~/devops/ch05/myapp` and:

1. Build as `myapp:1.0.0` and run it on host port 8000.
2. `curl localhost:8000` — confirm JSON with hostname + version.
3. Run a **second** container from the same image on port 8001 with
   `-e APP_VERSION=2.0.0-test`. Curl both and compare the `version` and `host` fields.
4. Confirm with `docker exec myapp ps aux` that python runs as `appuser`, not root.

**Verify:** two containers, one image, different env/behavior; process runs non-root.

## Exercise 5.5 — Layer caching experiment

Using your `myapp` build:

1. Build once (warm). Then rebuild without changes — note every step says CACHED
   and total time.
2. Edit `app.py` (change the message). Rebuild. Which steps were cached and which
   re-ran?
3. Add a package to `requirements.txt` (e.g. `requests==2.32.3`). Rebuild. Now
   which steps re-ran?
4. Deliberately break the ordering: move `COPY app.py .` ABOVE the requirements
   lines, rebuild twice with a code edit in between, and compare times.

**Verify:** you observed: code change → only `COPY app.py` onward rebuilt;
deps change → pip reinstall re-ran; wrong ordering → pip reinstall on every code
edit. Restore the good ordering.

## Exercise 5.6 — CMD vs ENTRYPOINT

Build this 4-line image:

```dockerfile
FROM ubuntu:24.04
ENTRYPOINT ["echo", "prefix:"]
CMD ["default-arg"]
```

1. `docker run --rm cmdlab` → what prints?
2. `docker run --rm cmdlab hello world` → what prints? Which instruction did your
   arguments replace?
3. Change ENTRYPOINT to CMD (two CMDs? no — replace so the file has only
   `CMD ["echo", "prefix:", "default-arg"]`), rebuild, and repeat run (2).
   What's different?

**Verify:** with ENTRYPOINT: args append (`prefix: hello world`). With CMD only:
args replace everything (`hello world` runs as the command → prints nothing
via echo? It becomes `hello world` which fails — exactly the point: observe the error).

## Exercise 5.7 — Tags are pointers

1. Tag your app image three ways: `myapp:1.0.0`, `myapp:1.0`, `myapp:latest`.
   (`docker tag` twice.) Check `docker images | grep myapp` — compare IMAGE IDs.
2. Change the app message, build as `myapp:1.1.0`, and also retag `myapp:latest`
   to it.
3. Now `docker run --rm -p 8002:8000 -d myapp:latest` and curl — which code runs?
4. Explain in one sentence why "we deploy latest" makes rollbacks and audits hard.

**Verify:** step 1 — all three tags share one image ID (aliases). Step 3 — the
new message; `latest` moved.

## Exercise 5.8 — Push to a registry

Using Docker Hub (free account) or ghcr.io:

1. Tag and push `myapp:1.0.0` and `:1.1.0` under your namespace.
2. Remove the local images AND local containers, then run straight from the
   registry reference.
3. Find your image on hub.docker.com and locate its digest. Run the image **by
   digest** (`docker run <you>/myapp@sha256:...`).

**Verify:** step 2 shows a pull happening before the run; step 3 works without
any tag — you've referenced immutable bytes.

## Exercise 5.9 — Containerize something of your own

Pick a small app you've written (any language) and containerize it:
pinned base image, sensible layer ordering, `.dockerignore`, non-root user,
exec-form CMD, port published, logs to stdout.

**Verify:** it builds, runs, answers requests; a second `docker build` with no
changes is fully cached; `docker exec <c> ps aux` shows a non-root user.

---

**Cleanup:** `docker system prune` and remove lab containers/images you don't need.
