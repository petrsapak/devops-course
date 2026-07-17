# Chapter 04 — Networking & Web Fundamentals for DevOps

## Learning objectives

1. Trace what happens between typing a URL and getting a page: DNS → TCP → TLS → HTTP.
2. Read and manipulate IPs, ports, CIDR ranges, and routing basics.
3. Debug connectivity systematically with `dig`, `curl`, `ss`, `ping`, `traceroute`, `tcpdump`.
4. Explain reverse proxies, load balancing, and TLS termination — and run one (nginx).
5. Know the HTTP details DevOps work needs: methods, status codes, headers, health checks.

Why this matters: half of production incidents surface as "can't connect", "timeout",
or "503". Kubernetes networking (ch 11–12) makes no sense without this layer.

---

## 1. The journey of a request

When a client opens `https://api.example.com/users`:

1. **DNS** — resolve `api.example.com` → an IP address.
2. **TCP** — three-way handshake (SYN → SYN/ACK → ACK) to that IP on port 443.
3. **TLS** — handshake: negotiate ciphers, server presents its certificate, client
   verifies it (CA chain + hostname + expiry), session keys established.
4. **HTTP** — the actual request/response inside the encrypted channel.

Each stage fails differently, which is why the debugging sequence in §5 works:
name resolution errors ≠ connection refused ≠ certificate errors ≠ HTTP 500.

---

## 2. IPs, ports, CIDR

### 2.1 Addresses and special ranges

Every interface has an IP. Ranges you must recognize on sight:

| Range | Meaning |
|-------|---------|
| `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` | Private (RFC 1918) — not routable on the internet |
| `127.0.0.1` (`localhost`) | Loopback — this machine only |
| `0.0.0.0` | As a *listen address*: "all interfaces" |
| `169.254.x.x` | Link-local — usually means "DHCP failed" |

### 2.2 CIDR notation

`10.0.1.0/24` = first 24 bits are the network → 256 addresses (`10.0.1.0`–`10.0.1.255`).
Quick table:

| CIDR | Addresses | Typical use |
|------|-----------|-------------|
| /32 | 1 | single host |
| /24 | 256 | a subnet |
| /16 | 65,536 | a VPC / large network |
| /8 | 16.7M | huge private space |

Rule of thumb: addresses = 2^(32 − prefix). You'll use CIDR constantly: cloud VPCs,
Kubernetes pod/service ranges, firewall rules.

### 2.3 Ports

A port identifies a *process* endpoint on a host. `IP:port` = one socket.
Well-known ports to know cold:

`22` SSH · `53` DNS · `80` HTTP · `443` HTTPS · `5432` PostgreSQL · `3306` MySQL ·
`6379` Redis · `8080` alt-HTTP (Jenkins!) · `9090` Prometheus · `3000` Grafana

Ports < 1024 need root to bind — one reason services sit behind a proxy.

```bash
sudo ss -tlnp        # what is LISTENING where
sudo ss -tnp         # established connections
```

> **Tool:** `ss` — **s**ocket **s**tatistics, part of the `iproute2` suite; the modern replacement for `netstat`. It answers the two questions ops asks daily: *what is listening on this machine?* and *who is connected to it?*
> **Flags:** `-t` TCP sockets only · `-l` **l**istening sockets (servers waiting for connections) — omit it to see established connections instead · `-n` **n**umeric: print `:8080`, don't try to resolve it to a service name (faster, unambiguous) · `-p` show the owning **p**rocess — this needs `sudo`, and it's the payoff column.
> **Expect:**
> ```
> State   Recv-Q  Send-Q  Local Address:Port   Peer Address:Port  Process
> LISTEN  0       4096    127.0.0.1:8080       0.0.0.0:*          users:(("jenkins",pid=812,fd=143))
> LISTEN  0       511     0.0.0.0:80           0.0.0.0:*          users:(("nginx",pid=601,fd=6))
> ```
> Read the *Local Address* column carefully: `127.0.0.1:8080` = loopback only, `0.0.0.0:80` = all interfaces — the exact distinction discussed below.

**Listen address matters:** a service bound to `127.0.0.1:8080` is reachable only
from the same machine; bound to `0.0.0.0:8080` it accepts external connections.
"Works with curl on the server but not from my laptop" is very often exactly this.

### 2.4 TCP vs UDP

- **TCP**: connection-oriented, ordered, reliable (retransmits). HTTP, SSH, DBs.
- **UDP**: fire-and-forget datagrams, no handshake. DNS queries, metrics
  (statsd), video. Cheaper, lossy.

---

## 3. DNS — the #1 "it's always DNS" system

DNS maps names to records. Resolution walks: stub resolver → recursive resolver
(ISP/corporate/8.8.8.8) → root servers → TLD servers (`.com`) → authoritative
server for the zone → answer, cached at every step per the record's **TTL**.

### Record types you must know

| Type | Maps | Example |
|------|------|---------|
| A | name → IPv4 | `api.example.com → 203.0.113.10` |
| AAAA | name → IPv6 | |
| CNAME | name → another name | `www → example.com` |
| MX | domain → mail servers | |
| TXT | name → arbitrary text | domain verification, SPF |
| NS | zone → authoritative name servers | |

### dig — the DNS debugging tool

```bash
dig example.com                 # full query (read the ANSWER section)
dig +short example.com          # just the answer
dig example.com CNAME           # specific record type
dig @8.8.8.8 example.com        # ask a SPECIFIC resolver (bypass local caches)
dig +trace example.com          # walk the whole delegation chain from the root
```

> **Tool:** `dig` — **d**omain **i**nformation **g**roper, from the `dnsutils` package (ch 02 installed it). It sends real DNS queries and shows you the raw answers — no caching layer of its own, no magic.
> **The variants decoded:**
> - `dig example.com` — full response. Skip to the `ANSWER SECTION`:
>   ```
>   ;; ANSWER SECTION:
>   example.com.   3600  IN  A  93.184.215.14
>   ```
>   Left to right: name, **TTL in seconds** (how long resolvers may cache this), class (`IN`ternet, always), record type, value. That TTL is the number that bites during migrations.
> - `+short` — just the value(s), perfect for scripts: `93.184.215.14`.
> - `dig example.com CNAME` — ask for a specific record type (A is the default).
> - `@8.8.8.8` — send the query to a *specific* resolver instead of your system's. This is the caching-debug tool: if `dig @8.8.8.8` shows the new IP but plain `dig` shows the old one, your local resolver is still caching.
> - `+trace` — resolve the way a recursive resolver does: from the root servers, through the TLD, to the authoritative server, printing every delegation. Slow and verbose; unbeatable when delegation itself is broken.

DevOps DNS gotchas:

- **TTL and deployments:** you changed an A record but users still hit the old
  server — caches hold the old answer until TTL expires. Lower TTL *before* a
  planned migration, not during it.
- `/etc/hosts` overrides DNS locally — great for testing
  (`203.0.113.10 api.example.com`), terrible when you forget an entry exists.
- Containers/K8s have their *own* DNS (service discovery) — same tooling applies.

---

## 4. HTTP — the protocol of everything

### 4.1 Request/response anatomy

```
GET /api/users?active=true HTTP/1.1
Host: api.example.com
Accept: application/json
Authorization: Bearer eyJhbGc...

HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: no-store

[{"id":1,"name":"Ada"}]
```

Methods: `GET` (read, no side effects), `POST` (create/act), `PUT` (replace),
`PATCH` (partial update), `DELETE`. GET/PUT/DELETE should be **idempotent** —
this matters for retries and load balancers replaying requests.

### 4.2 Status codes — the ops view

| Range | Meaning | The ones to know |
|-------|---------|------------------|
| 2xx | success | 200 OK, 201 Created, 204 No Content |
| 3xx | redirection | 301 permanent, 302 temporary, 304 not modified |
| 4xx | **client's** fault | 400 bad request, 401 unauthenticated, 403 forbidden, 404, 429 too many requests |
| 5xx | **server's** fault | 500 error, 502 bad gateway, 503 unavailable, 504 gateway timeout |

Ops interpretation cheat-sheet:
- Spike in **5xx** → your service is broken. Page someone.
- **502/504 specifically** → the proxy/LB can't reach or gets no timely answer
  from the *backend* — look behind the proxy, not at it.
- **503** → no healthy backends (all failed health checks?) or deliberate
  maintenance/overload shedding.
- Spike in **4xx** → usually a client/integration change; 401/403 spikes after a
  deploy → auth config regression; 429 → someone hit rate limits.

### 4.3 curl — your HTTP Swiss army knife

```bash
curl -v https://example.com                 # -v shows DNS, TCP, TLS, headers
curl -I https://example.com                 # headers only (HEAD)
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" https://example.com
curl -X POST -H "Content-Type: application/json" -d '{"name":"test"}' http://localhost:8080/api/items
curl -L http://example.com                  # follow redirects
curl --resolve api.example.com:443:127.0.0.1 https://api.example.com/health
                                            # test a name against a chosen IP (pre-DNS-cutover testing!)
curl -sf http://localhost:8080/health       # -f: exit non-zero on HTTP >= 400 (script/CI-friendly)
```

> **Tool:** `curl` — makes HTTP (and dozens of other protocols') requests from the command line. The single most-used debugging tool in this course.
> **Line by line:**
> - `-v` (**v**erbose) — prints the full conversation: DNS resolution, TCP connect, TLS handshake + certificate details, request headers (`>` lines), response headers (`<` lines). When *anything* HTTP misbehaves, `-v` first — it shows you which of the four §1 stages failed.
> - `-I` — send a `HEAD` request: response headers only, no body. Quick "is it up, what server, what cache headers".
> - `-s -o /dev/null -w "..."` — the timing/status one-liner: `-s` silences the progress meter, `-o /dev/null` throws away the body, and `-w` (**w**rite-out) prints just the variables you ask for after the transfer. Expect: `200 0.084s`. Loop it for a poor man's latency monitor.
> - `-X POST -H ... -d ...` — craft a real API call: `-X` sets the method, `-H` adds a request header (here declaring the body type), `-d` supplies the body (and implies POST, so `-X POST` is often redundant but explicit).
> - `-L` — follow 3xx redirects instead of just printing them.
> - `--resolve host:port:ip` — "pretend DNS said this": connects to the IP you chose while still sending the right hostname and validating TLS against it. *The* tool for testing a new server before cutting DNS over (compare: `/etc/hosts` hacks, which affect the whole machine and get forgotten).
> - `-f` (**f**ail) — makes curl's exit code non-zero on HTTP ≥ 400. Without it curl happily exits 0 after receiving a 500 page. Every scripted health check needs `-sf` (you met this in ch 02's script).

---

## 5. TLS/HTTPS

TLS gives **encryption** (nobody reads it), **integrity** (nobody alters it), and
**authentication** (you're talking to the real server, proven by certificate).

Certificate trust chain: server cert ← intermediate CA ← root CA (pre-installed in
OS/browser trust stores). Verification checks the chain signature, the hostname
(must match CN/SAN), and validity dates.

```bash
# inspect a live server's certificate:
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
# what curl thinks:
curl -vI https://example.com 2>&1 | grep -E "subject|issuer|expire"
```

> **Tools:** two subcommands of `openssl`, the swiss-army TLS toolkit. `openssl s_client` opens a raw TLS connection and dumps the whole handshake — certificate included; `openssl x509` parses a certificate and prints chosen fields. The pipe feeds the first one's output (which contains the PEM-encoded cert) into the second.
> **Flags:** `-connect example.com:443` where to connect · `-servername example.com` sends **SNI** (Server Name Indication) — one IP often hosts many sites, and this tells the server *which* certificate to present; omit it and you may be handed the wrong cert and chase a ghost · `</dev/null` closes stdin so s_client exits after the handshake instead of sitting there waiting for you to type · `2>/dev/null` hides handshake chatter from stderr · `-noout` don't re-print the raw certificate · `-subject -issuer -dates` print exactly these three fields.
> **Expect:**
> ```
> subject=CN=example.com
> issuer=C=US, O=Let's Encrypt, CN=R11
> notBefore=Jun 16 08:21:11 2026 GMT
> notAfter=Sep 14 08:21:10 2026 GMT
> ```
> `notAfter` in the past = the classic expired-cert outage. The `curl -vI` variant gets similar facts with less typing — `2>&1` merges the verbose output (which goes to stderr) into stdout so grep can see it (ch 02 §4.1).

Ops realities:

- **Expired certificates are a classic self-inflicted outage.** Automate renewal
  (Let's Encrypt + cert-manager in K8s) and *monitor expiry* (alert at 14 days).
- **TLS termination:** commonly the load balancer/reverse proxy holds the
  certificate and speaks plain HTTP to backends inside the private network.
  Simple, centralized cert management; the tradeoff is unencrypted internal hops
  (mTLS/service mesh addresses that — ch 16 mentions it).
- Self-signed certs fail verification by design; `curl -k` skips verification —
  acceptable in a lab, never in automation against production.

---

## 6. Reverse proxies and load balancing

A **reverse proxy** sits in front of backends and forwards client requests to them
(nginx, HAProxy, Traefik, Envoy). It provides: TLS termination, load balancing,
routing by host/path, caching, compression, and a single controlled entry point.

Minimal nginx reverse proxy + load balancer:

```nginx
upstream app_servers {
    server 10.0.1.11:8080;
    server 10.0.1.12:8080;
    # least_conn;            # alternative to default round-robin
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://app_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> **Directive by directive** (this lands in `/etc/nginx/conf.d/` or `sites-available/`; `sudo nginx -t` validates syntax, `sudo systemctl reload nginx` applies without dropping connections — ch 02):
> - `upstream app_servers { ... }` — names a *pool* of backend addresses. nginx balances across them; commented `least_conn` switches the algorithm.
> - `server { listen 80; server_name api.example.com; }` — a *virtual host*: this block handles plain-HTTP requests whose `Host` header says `api.example.com`. (TLS would be `listen 443 ssl;` + certificate paths.)
> - `location / { proxy_pass http://app_servers; }` — for every path under `/`, forward the request to the upstream pool. This one line is what makes it a reverse proxy.
> - The three `proxy_set_header` lines rewrite what the backend sees — without them it sees the proxy's IP and hostname instead of the client's. That's not cosmetic: rate limiting, geo-blocking, audit logs, and "redirect to https" logic in the app all depend on these headers being set.

Key concepts:

- **Algorithms:** round-robin (default), least-connections, IP-hash (sticky by
  client IP).
- **Health checks:** the LB stops sending traffic to backends that fail checks.
  This + rolling replacement is the mechanism behind zero-downtime deploys (ch 10).
- **`X-Forwarded-For` / `X-Forwarded-Proto`:** the backend otherwise sees the
  proxy's IP and plain HTTP; these headers preserve the original client context.
  When your app logs "all traffic comes from 10.0.0.5" — it's logging the proxy.
- **L4 vs L7:** L4 balances TCP connections (fast, content-blind); L7 understands
  HTTP (can route `/api` vs `/static`, retry idempotent requests, inspect headers).
  nginx above is L7. Kubernetes Services are L4; Ingress is L7 (ch 12).

---

## 7. Firewalls, NAT, and the path debugging toolkit

- **Firewalls** allow/deny by (source, destination, port, protocol). On Linux:
  `ufw`/`iptables`/`nftables`; in clouds: security groups. Default-deny inbound
  is the norm — "connection timed out" to a new service is very often just a
  missing firewall rule.
- **NAT**: private-ranged machines share a public IP through address translation;
  inbound connections to them require explicit port-forwarding. (Docker's port
  publishing `-p 8080:80` is exactly this idea — ch 05.)

### The systematic connectivity debug sequence

Work up the stack; each step isolates a layer:

```bash
# 1. Name resolution
dig +short api.example.com          # no answer → DNS problem

# 2. Reachability / route
ping <ip>                           # (ICMP may be blocked — a non-answer isn't proof)
traceroute <ip>                     # where does the path die?

# 3. Is the PORT open?
nc -vz <ip> 443                     # "succeeded" / "refused" / hangs (filtered)

# 4. Is the service answering correctly?
curl -v https://api.example.com/health
```

> **The tools in the sequence:**
> - `ping <ip>` — sends ICMP echo packets; replies prove the host is reachable at the IP layer. Expect `64 bytes from 203.0.113.10: icmp_seq=1 ttl=57 time=12.4 ms`. Interpret silence cautiously: many firewalls drop ICMP while TCP works fine — *no ping ≠ host down*.
> - `traceroute <ip>` — maps the route hop by hop (it sends packets with increasing TTLs; each router that decrements TTL to zero reveals itself). Where the output turns into `* * *` forever is where packets die — inside your network vs at the provider vs at the destination is exactly the fact you need for the "whose problem is this" call.
> - `nc -vz <ip> 443` — `nc` (netcat) is a raw TCP/UDP swiss-army knife; `-z` = **z**ero-I/O, just try to connect, `-v` = say what happened. This tests *the specific port* — one layer more precise than ping. The three outcomes map to causes: `succeeded!` (something listens) / `Connection refused` (host reached, port closed — service down or wrong port) / silent hang (a firewall is eating packets).
> - `curl -v ...` — finally, the application layer: TLS OK? What status code? Only at this step are you debugging *software* rather than *network*.
> **Why the order matters:** each step assumes the previous one passed. Running them in order turns "it doesn't work" into "DNS fine, route fine, port open, but the app returns 503" — a sentence that names the guilty layer.

Interpretation table — memorize this:

| Symptom | Most likely layer |
|---------|------------------|
| `could not resolve host` | DNS |
| `connection refused` | Host reached, **nothing listening** on that port (or wrong port/listen address) |
| Timeout / hangs | Firewall dropping packets, wrong route, or host down |
| TLS certificate error | Cert expired / wrong hostname / self-signed |
| HTTP 502/504 | Proxy up, **backend** down or too slow |
| Works locally, not remotely | Service bound to `127.0.0.1`, or firewall |

### tcpdump — when you need ground truth

```bash
sudo tcpdump -i any port 8080 -n        # watch traffic live
sudo tcpdump -i any host 10.0.1.5 -w cap.pcap    # capture to file (open in Wireshark)
```

> **Tool:** `tcpdump` — a packet sniffer: it puts a network interface into promiscuous mode (hence `sudo`) and prints every packet matching your filter. Everything above tcpdump *interprets*; tcpdump shows what's actually on the wire.
> **Flags & filter syntax:** `-i any` capture on all **i**nterfaces (or name one: `-i eth0`) · `-n` numeric addresses/ports, no DNS lookups (lookups are slow and generate their own traffic) · `-w cap.pcap` **w**rite raw packets to a file instead of printing · the rest is the *filter expression*: `port 8080`, `host 10.0.1.5`, combinable as `host 10.0.1.5 and port 443`. Filter aggressively — an unfiltered tcpdump on a busy box is a firehose.
> **Expect (live mode):**
> ```
> 14:11:02.410551 IP 10.0.0.8.52814 > 10.0.1.5.8080: Flags [S], seq 3401...
> 14:11:02.410890 IP 10.0.1.5.8080 > 10.0.0.8.52814: Flags [S.], seq 918..., ack 3402...
> ```
> `Flags [S]` = SYN (connection attempt), `[S.]` = SYN-ACK (reply), `[R]` = reset (refused). SYN out, nothing back = the interpretation rules that follow.

If tcpdump shows SYN packets going out and nothing coming back → network/firewall.
SYN in, nothing out → local service/host problem. No packets at all → wrong
interface/route or the traffic never leaves the app.

---

## 8. Health checks — the contract between your app and the platform

Every LB, container orchestrator, and monitor needs a way to ask "are you OK?".
Convention: an unauthenticated `GET /health` (or `/healthz`, `/ready`) endpoint.

- **Liveness** — "is the process alive?" Fail → restart it.
- **Readiness** — "can it serve traffic *right now*?" Fail → take out of rotation
  (don't restart). E.g., still warming caches, or DB connection lost.

Design rules: fast (<1s), no cascading dependency checks in liveness (a DB blip
shouldn't cause a restart storm), readiness *may* check critical dependencies.
Kubernetes turns these into `livenessProbe`/`readinessProbe` in ch 12 — the
concept is identical.

## Further reading

- *High Performance Browser Networking* (free online) — chs. on TCP, TLS, HTTP.
- nginx docs: "NGINX Reverse Proxy" and "HTTP Load Balancing" guides.
- Julia Evans' networking zines (wizardzines.com) — excellent mental models.

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 05: Docker Fundamentals](../05-docker-fundamentals/lesson.md)
