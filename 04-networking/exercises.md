# Chapter 04 — Exercises

Work in `~/devops/ch04`. Exercises use only your WSL2 shell plus Docker for the
proxy lab.

```bash
mkdir -p ~/devops/ch04 && cd ~/devops/ch04
```

---

## Exercise 4.1 — DNS spelunking with dig

1. Resolve `github.com` — note the A record(s) and the TTL. Run it again — did
   the TTL change? Why?
2. Find what `www.github.com` is a CNAME for.
3. Query `github.com` against Google's resolver (`8.8.8.8`) and your default one.
   Compare answers.
4. Run `dig +trace github.com` and identify the four delegation levels in the
   output (root → TLD → authoritative → answer).
5. Look up the TXT records of `github.com` — what kinds of things live there?

**Verify:** for (1) you can explain the second TTL being lower (cached answer
counting down). For (4) you can point at the `.` servers, `com.` servers, and
github's NS in the trace.

## Exercise 4.2 — CIDR arithmetic

Without tools first, then check with `ipcalc` (`sudo apt install -y ipcalc`):

1. How many usable addresses in `10.20.0.0/22`?
2. Is `192.168.1.130` inside `192.168.1.128/26`?
3. Your VPC is `10.0.0.0/16`. Split it into four equal subnets — write their CIDRs.
4. What's the smallest CIDR block that contains both `10.0.4.7` and `10.0.5.9`?

**Verify:** `ipcalc 10.20.0.0/22` etc. confirm your manual answers.

## Exercise 4.3 — Ports and listen addresses

1. Start `python3 -m http.server 8001 --bind 127.0.0.1 &` and
   `python3 -m http.server 8002 --bind 0.0.0.0 &`.
2. Show both with `ss -tlnp` and note the difference in the Local Address column.
3. From **Windows PowerShell** (a different network vantage point), run
   `curl.exe http://localhost:8001` and `curl.exe http://localhost:8002`.
   (WSL2 forwards localhost — both may work. Now find your WSL IP with
   `ip addr show eth0` and from PowerShell curl `http://<wsl-ip>:8001` and `:8002`.)
4. Explain the results in terms of listen addresses.
5. Kill both servers.

**Verify:** `<wsl-ip>:8002` answers, `<wsl-ip>:8001` is refused — 8001 only
accepts loopback connections.

## Exercise 4.4 — curl as a diagnostic instrument

1. Run `curl -v https://example.com 2>&1 | less` and identify these phases in
   the output: DNS resolution, TCP connect, TLS handshake (note the TLS version
   and certificate subject), request headers, response headers.
2. Time it: `curl -s -o /dev/null -w "dns=%{time_namelookup} tcp=%{time_connect} tls=%{time_appconnect} total=%{time_total}\n" https://example.com`
   — run 3 times; which phase dominates? Why is run 2+ faster?
3. Get just the HTTP status of `https://httpbin.org/status/503`.
4. Follow the redirect chain of `http://github.com` with `-L -v` and list every
   status code on the way.

**Verify:** (3) prints `503`; (4) shows a `301` to https then a `200`.

## Exercise 4.5 — Break it and read the error

Trigger each failure mode and record the *exact* client error message:

1. DNS failure: `curl https://this-domain-definitely-does-not-exist-12345.com`
2. Connection refused: `curl http://localhost:9999`
3. Timeout (filtered): `curl --connect-timeout 3 http://10.255.255.1`
4. TLS error: `curl https://expired.badssl.com/` and `curl https://wrong.host.badssl.com/`
5. Backend down behind a proxy: you'll build this in 4.6.

**Verify:** you can now match each message to a row of the interpretation table
in lesson §7 without looking.

## Exercise 4.6 — Build a load balancer (nginx + two backends)

Create two trivially different backends and an nginx proxy in front:

```bash
mkdir -p lb && cd lb
echo "backend ONE" > one.html && echo "backend TWO" > two.html
docker network create lbnet
docker run -d --name be1 --network lbnet -v $PWD/one.html:/usr/share/nginx/html/index.html:ro nginx:alpine
docker run -d --name be2 --network lbnet -v $PWD/two.html:/usr/share/nginx/html/index.html:ro nginx:alpine
```

Create `lb.conf`:

```nginx
upstream backends {
    server be1:80;
    server be2:80;
}
server {
    listen 80;
    location / {
        proxy_pass http://backends;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
docker run -d --name lb --network lbnet -p 8080:80 \
  -v $PWD/lb.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine
```

1. `for i in {1..6}; do curl -s localhost:8080; done` — observe the alternation.
2. Stop one backend (`docker stop be1`) and immediately curl 6 more times. What
   do you get? (Expect some `502`s at first, then nginx marks the peer failed and
   routes around it.)
3. Start `be1` again and confirm it re-enters rotation.
4. Bonus: check nginx's view — `docker logs lb` shows the upstream errors.

**Verify:** step 1 alternates ONE/TWO; step 2 produces at least one 502 followed
by consistent TWO. Clean up: `docker rm -f lb be1 be2 && docker network rm lbnet`.

## Exercise 4.7 — Inspect a TLS certificate

1. Using `openssl s_client` (lesson §5), print subject, issuer, and validity dates
   for `github.com`.
2. Compute how many days until it expires (manually is fine).
3. Write `cert_expiry.sh <host>` that prints the days remaining and exits 1 if
   fewer than 14 — a real monitoring probe shape. Hints: `openssl x509 -enddate`,
   `date -d <str> +%s`.

**Verify:** `./cert_expiry.sh github.com; echo $?` → prints days, exit 0.
`./cert_expiry.sh expired.badssl.com` → exit 1 (negative days).

## Exercise 4.8 — The full debug drill (capstone for this chapter)

Have a colleague — or your future self, tomorrow — set up ONE of these faults
while you're not looking, using the lb lab from 4.6:

- stop both backends
- stop just nginx
- change `lb.conf` to point at a wrong port and restart nginx
- add a bogus entry for some hostname in `/etc/hosts` and have you curl that name

Then diagnose from the outside in, **writing down each step**: dig → nc →
curl -v → docker logs. No peeking at what was changed until you've named the layer.

**Verify:** your written trail identifies the failing layer before you look —
that's the skill this whole chapter exists to build.
