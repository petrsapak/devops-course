# Chapter 10 — Exercises

Mix of hands-on (Docker/nginx from earlier chapters) and design drills. Work in
`~/devops/ch10`.

Use the [visits-platform lab](../labs/visits-platform/README.md) as the artifact
you version and promote. Its `APP_VERSION` response makes it possible to prove
which immutable build is running.

---

## Exercise 10.1 — SemVer judgment calls

For each change to a JSON HTTP API currently at `2.4.1`, decide the next version
and justify in one line:

1. Fix: `/users` returned 500 for empty result sets; now returns `[]`.
2. New optional query parameter `?sort=` on `/users`.
3. The `created_at` field changes format from unix epoch to ISO 8601.
4. Response times improved 40% via caching; no interface change.
5. A previously undocumented-but-public field `internal_score` is removed.
6. Security fix requiring all clients to re-authenticate once.

**Verify:** answers at the bottom. Rule to apply: version from the *consumer's*
perspective, not the effort involved.

## Exercise 10.2 — Automated versioning from commits

In a fresh repo, simulate a release flow with conventional commits:

1. Make commits: `feat: add export endpoint`, `fix: handle empty names`,
   `docs: update readme`, `feat!: drop XML support`.
2. Without tooling first: starting from `1.2.3`, what version do these commits
   produce collectively?
3. Now automate: `npx release-please` needs GitHub; simplest local alternative —
   write a 15-line `next_version.sh` that reads `git log --format=%s <last-tag>..HEAD`,
   greps for `feat!:`/`BREAKING`, `feat:`, `fix:`, and prints the bumped version.
   (This is a real script teams run; it's also great grep/bash practice.)

**Verify:** script prints `2.0.0` for the history above; for a history with only
`fix:` commits it prints a patch bump.

## Exercise 10.3 — Run your own registry + retention thinking

1. Run a local registry: `docker run -d -p 5000:5000 --name registry registry:2`.
2. Push your visits app: tag as `localhost:5000/visits:sha-abc1234`,
   `localhost:5000/visits:1.0.0`, push both.
3. List the repo's tags via the API:
   `curl -s localhost:5000/v2/visits/tags/list | jq .`
4. Get the image digest:
   `curl -sI -H "Accept: application/vnd.oci.image.manifest.v1+json" localhost:5000/v2/visits/manifests/1.0.0 | grep -i docker-content-digest`
5. Paper part: write a retention policy for a team producing ~20 `sha-*` images/day
   and ~2 releases/month (what to keep, how long, why releases differ).

**Verify:** both tags listed; you can explain why the digest, not the tag, is
the true identity. Keep the registry running for 10.4.

## Exercise 10.4 — Promotion without rebuilding

Simulate the promotion flow against your local registry:

1. "CI": push `visits:sha-1111111` (build once).
2. "Staging passed, promote": pull the SHA tag, retag as `visits:1.1.0` and
   `visits:prod-current`, push. **No docker build anywhere in this step.**
3. Prove all three tags are identical bytes: compare their digests via the API.
4. Anti-pattern for contrast: rebuild the image (change nothing, but rebuild)
   and push as `1.1.0-rebuilt`; compare digest with `1.1.0`. Same or different?
   Why does that matter?

**Verify:** step 3 digests identical; step 4's differs (timestamps/layer
metadata) — a rebuilt "same" image is not the artifact you tested.

## Exercise 10.5 — Blue-green with nginx (hands-on centerpiece)

Build a working blue-green setup on the ch 04 lab pattern:

1. Two versions of the visits app (or plain nginx with different index pages):
   `blue` container serving "v1", `green` serving "v2", both on network `bgnet`.
2. Router: nginx container publishing :8080, config
   `proxy_pass http://blue:8000;` (a file you bind-mount).
3. Verify traffic hits blue. Deploy day: green is already running — test it
   *directly* (`docker exec router curl green:8000`) while users still see blue.
4. **Cutover**: edit the config to `green`, then `docker exec router nginx -s reload`.
   Time the user-visible switch (run a `while true; do curl -s localhost:8080; sleep 0.2; done`
   loop in another terminal during the reload).
5. **Rollback drill**: switch back to blue the same way. Time it.

**Verify:** the curl loop shows zero failed requests during cutover (nginx reload
is graceful), and rollback took seconds. Write down: what did this cost you?
(Two environments running simultaneously — the blue-green tax.)

## Exercise 10.6 — Canary with weighted upstreams

Extend 10.5's router config to a weighted canary:

```nginx
upstream app {
    server blue:8000  weight=9;
    server green:8000 weight=1;   # 10% canary
}
```

1. Reload, then run 100 curls and count v1 vs v2 responses (`sort | uniq -c`).
2. Ramp: 50/50, then 0/100, reloading each time, re-measuring.
3. Simulate a failing canary: stop green mid-ramp and observe nginx routing
   around it (passive health behavior from ch 04).

**Verify:** measured splits ≈ configured weights; you can name the *missing*
piece that makes this a real canary system (automated metric comparison +
automatic abort — ch 15 provides the metrics half).

## Exercise 10.7 — Feature flag kill switch

Add a flag to the visits app:

```python
import os
@app.get("/search")
def search():
    if os.environ.get("FLAG_NEW_SEARCH", "off") == "on":
        return jsonify(engine="new", results=[])   # pretend it's risky
    return jsonify(engine="old", results=[])
```

1. Run two instances behind your router with `FLAG_NEW_SEARCH=on`.
2. "Incident": flip to off... realize env vars need a container restart —
   restart one instance at a time (mini rolling restart) and time
   feature-off-everywhere.
3. Now the better design: make the app re-read a bind-mounted `flags.json` on
   each request instead. Flip the file. Time it now.

**Verify:** file-based flag flips in ~0 seconds with no restarts — you've built
the fastest MTTR tool in the chapter and demonstrated why flag systems don't
use baked-in env vars.

## Exercise 10.8 — Expand–migrate–contract on paper

Your `orders` table has a `status` column holding free-text strings; you must
move to a strict `status_id` FK to a new `statuses` table, with a rolling
deployment and zero downtime. Write the full plan: what ships in release 1,
what runs as backfill, what ships in release N — and at each step, state what
happens if you must roll the code back.

**Verify:** your plan never has a release whose rollback would face a schema its
code can't use; the `DROP COLUMN status` appears only after a release that
provably never reads it.

---

<details>
<summary><b>Answers 10.1</b></summary>

1. `2.4.2` — pure fix.
2. `2.5.0` — new backward-compatible capability.
3. `3.0.0` — breaking: consumers parse that field.
4. `2.4.2` — no interface change (performance is patch-worthy unless documented guarantees change).
5. `3.0.0` — if consumers could see it, removing it is breaking; "undocumented" doesn't unbreak clients (Hyrum's Law).
6. Usually `2.4.2` (or `2.5.0` if new auth surface) — but ship with loud release notes; security trumps ceremony.

</details>

**Cleanup:** `docker rm -f registry blue green router` etc.
