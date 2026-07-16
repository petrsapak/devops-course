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
sudo ss -tlnp        # what is LISTENING where (t=tcp, l=listen, n=numeric, p=process)
sudo ss -tnp         # established connections
```

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
