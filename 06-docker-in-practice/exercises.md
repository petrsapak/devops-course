# Chapter 06 — Exercises

Work in `~/devops/ch06`.

> **Starter files:** the
> [visits-platform lab](../labs/visits-platform/README.md) contains the complete
> Compose version. Build each exercise yourself first, then use the reference
> to compare networking, secrets, health checks, and hardening choices.

---

## Exercise 6.1 — Volume persistence proof

1. `docker volume create notesdata`, then run
   `docker run -d --name db1 -v notesdata:/var/lib/postgresql/data -e POSTGRES_PASSWORD=pw postgres:16`.
2. Create data:
   `docker exec -it db1 psql -U postgres -c "CREATE TABLE notes(t text); INSERT INTO notes VALUES ('survive!');"`
3. **Destroy the container**: `docker rm -f db1`.
4. Run a brand-new `db2` with the same volume mount and query the table.

**Verify:** `docker exec db2 psql -U postgres -c "SELECT * FROM notes;"` returns
`survive!`. Then clean up: `docker rm -f db2 && docker volume rm notesdata`.

## Exercise 6.2 — Bind-mount dev loop

1. `mkdir site && echo "<h1>v1</h1>" > site/index.html`
2. Serve it read-only:
   `docker run -d --name web -p 8085:80 -v $PWD/site:/usr/share/nginx/html:ro nginx:alpine`
3. Curl, then edit index.html on the host to `v2` and curl again — no restart needed.
4. Prove the `:ro` works: `docker exec web sh -c 'echo hacked > /usr/share/nginx/html/index.html'`
   — record the error.

**Verify:** step 3 shows v2 instantly; step 4 fails with "Read-only file system".

## Exercise 6.3 — Networks and name resolution

1. Create networks `frontend` and `backend`.
2. Run `db` (postgres, backend only), `api` (any image that can curl — use
   `alpine sleep 600` and `apk add curl` — on **both** networks... actually run
   nginx as a stand-in API on both: `docker run -d --name api --network backend nginx:alpine`
   then `docker network connect frontend api`), and `proxy` (nginx, frontend only).
3. From `proxy`, resolve and reach `api` (`docker exec proxy wget -qO- http://api`).
4. From `proxy`, try to reach `db` by name. What happens and why?
5. Inspect both networks and sketch which container sits where.

**Verify:** step 3 works; step 4 fails name resolution — `proxy` and `db` share
no network. This is network segmentation, the pattern real deployments use.

## Exercise 6.4 — Compose the full stack

Build the worked example from lesson §7 (api + db + adminer). Extend the ch05
Flask app to hit the DB — replace `app.py` with:

```python
from flask import Flask, jsonify
import os, psycopg

app = Flask(__name__)
DB = os.environ["DATABASE_URL"]

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/visits")
def visits():
    with psycopg.connect(DB) as conn, conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS visits(at timestamptz DEFAULT now())")
        cur.execute("INSERT INTO visits DEFAULT VALUES")
        cur.execute("SELECT count(*) FROM visits")
        return jsonify(visits=cur.fetchone()[0])

app.run(host="0.0.0.0", port=8000) if __name__ == "__main__" else None
```

(`requirements.txt`: `flask==3.1.3` and `psycopg[binary]==3.3.4`)

1. `docker compose up -d --build`, then curl `/visits` several times — counter grows.
2. `docker compose down` (no `-v`), up again — does the counter continue or reset?
3. Open Adminer at `localhost:8082` (system: PostgreSQL, server: `db`) and look
   at the table.
4. Now `docker compose down -v`, up again, curl — what happened to the counter and why?

**Verify:** counter survives step 2 (volume kept), resets in step 4 (volume removed).

## Exercise 6.5 — depends_on the hard way

1. In your compose file, remove the `condition: service_healthy` (leave plain
   `depends_on: [db]`) and remove the db healthcheck. `docker compose down -v && docker compose up -d`.
2. Immediately `curl localhost:8000/visits` a few times fast. Catch the error
   window (you may need `docker compose logs api` to see connection refused).
3. Restore the healthcheck + condition, recreate, and show the race is gone.

**Verify:** you witnessed the startup race and can explain why "started" ≠ "ready".

## Exercise 6.6 — Multi-stage build + size hunt

1. Take the Python multi-stage Dockerfile from lesson §4 and apply it to the
   visits app. Build as `visits:multi`.
2. Also build the naive single-stage version as `visits:fat`.
3. Compare `docker images` sizes and inspect with `docker history visits:multi`.
4. Bonus (dramatic version): build the Go example from the lesson if you have
   any Go code handy, or try `dive visits:multi`.

**Verify:** multi-stage image is measurably smaller and contains no pip cache/build
leftovers in its history.

## Exercise 6.7 — The layer-deletion trap

Build both of these and compare image sizes:

```dockerfile
# A: delete in a separate layer
FROM ubuntu:24.04
RUN dd if=/dev/zero of=/bigfile bs=1M count=200
RUN rm /bigfile
```

```dockerfile
# B: create and delete in one layer
FROM ubuntu:24.04
RUN dd if=/dev/zero of=/bigfile bs=1M count=200 && rm /bigfile
```

**Verify:** A is ~200 MB larger than B despite "deleting" the file. Explain in
one sentence why (hint: layers are additive; the file lives in layer 1 forever).

## Exercise 6.8 — Health checks and limits

1. Add to the visits app Dockerfile:
   `HEALTHCHECK --interval=5s --timeout=2s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`.
   Rebuild, run, and watch `docker ps` flip from `(health: starting)` to `(healthy)`.
2. Break it: stop the DB while api's healthcheck only tests `/health` (which
   doesn't touch the DB) — still healthy? What does that teach about *what* a
   health endpoint should check?
3. Run the api with `--memory=64m` and hammer it (`for i in {1..50}; do curl -s localhost:8000/visits > /dev/null; done`).
   If it survives, lower until you see an OOM kill; check `docker inspect --format '{{.State.OOMKilled}} {{.State.ExitCode}}' <c>`.

**Verify:** you saw a healthy→unhealthy transition (kill the app process inside:
`docker exec <c> pkill -f app.py` also works — though that kills PID1... use
judgment), and you recognize exit code 137.

## Exercise 6.9 — Scan and fix

1. Scan an old image: `trivy image python:3.8-slim` (or the dockerized trivy from
   the lesson). Count HIGH/CRITICAL findings.
2. Scan your `visits:multi`. Compare.
3. Run trivy with `--severity CRITICAL --exit-code 1` against both and check
   `echo $?` — this is exactly the gate you'll wire into CI in ch 07.

**Verify:** newer slim base shows dramatically fewer findings; exit codes differ
between the two scans (very likely 1 for the old image, 0 for yours).

---

**Cleanup:** `docker compose down -v`, `docker system prune`.
