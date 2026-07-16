# Chapter 04 — Test

15 questions. Passing: 12/15.

---

**Q1.** Put in order the phases of loading `https://example.com` for the first time:
TLS handshake, DNS resolution, HTTP request/response, TCP handshake.

**Q2.** How many addresses are in `10.0.0.0/20`?
- a) 256
- b) 1,024
- c) 4,096
- d) 65,536

**Q3.** Which of these is a private (RFC 1918) address?
- a) 172.20.5.1
- b) 8.8.8.8
- c) 203.0.113.7
- d) 169.254.10.1

**Q4.** A service is bound to `127.0.0.1:8080` on a server. Curl from the server
works; curl from your laptop gets "connection refused". Explain and give the fix.

**Q5.** What is a DNS TTL, and why does it matter when you're migrating a service
to a new IP?

**Q6.** `curl http://api.internal:8080` hangs for 30 seconds then reports a
timeout. `nc -vz api.internal 8080` also hangs. `ping api.internal` works.
What's the most likely cause?
- a) DNS misconfiguration
- b) Nothing listening on port 8080
- c) A firewall silently dropping packets to port 8080
- d) TLS certificate expired

**Q7.** What is the difference between "connection refused" and a connection
timeout, in terms of what's happening on the wire?

**Q8.** Your load balancer returns 502 for some requests. What does 502
specifically tell you, and what are the first two things to check?

**Q9.** Why do reverse proxies add the `X-Forwarded-For` header, and what does an
app that ignores it get wrong?

**Q10.** Liveness vs readiness checks: define each and give one situation where a
service should fail readiness but NOT liveness.

**Q11.** Name the three guarantees TLS provides.

**Q12.** `curl https://internal.corp` fails with a certificate error; the cert is
signed by the company's own CA. A teammate suggests scripting it with `curl -k`.
What's the risk, and what's the correct fix?

**Q13.** A monitoring dashboard shows a sudden spike of 4xx (specifically 401)
right after a deployment. What class of problem do you suspect, and why does the
4xx-vs-5xx distinction point you there?

**Q14.** What is the difference between an L4 and an L7 load balancer? Give one
capability only L7 can provide.

**Q15.** Design question: sketch the debug sequence (4 commands, in order, with a
one-line purpose each) you'd run when a user reports "https://shop.example.com is down"
and you know nothing else yet.

---

<details>
<summary><b>Answer key</b></summary>

1. DNS resolution → TCP handshake → TLS handshake → HTTP request/response.
2. **c** — 2^(32−20) = 4,096.
3. **a** (172.16.0.0/12 covers 172.16–172.31). 169.254.x is link-local, not RFC 1918.
4. The service listens only on loopback, so only local connections are accepted.
   Fix: bind to `0.0.0.0` (or the specific external interface) — and then make
   sure a firewall rule permits the port.
5. TTL = how long resolvers may cache a record. During a migration, cached old
   answers keep sending users to the old IP until TTL expires; lower the TTL well
   in advance so the cutover propagates quickly.
6. **c** — DNS works (ping resolved it), host is up, but the port probe hangs
   rather than being refused → packets are being dropped (filtered), the firewall
   signature.
7. Refused: the host is reachable and actively answers with a TCP RST — nothing
   is listening on that port. Timeout: no answer at all — packets are dropped en
   route (firewall) or the host is unreachable.
8. 502 = the proxy itself is fine but got an invalid/no response from a backend.
   Check: (1) are backend processes up/healthy (health checks, `docker ps`,
   `systemctl status`); (2) can the proxy reach the backend address:port it's
   configured with (config drift, wrong port).
9. Because the backend otherwise sees the proxy's IP as the client. An app
   ignoring it logs the proxy IP for every request, breaking analytics, rate
   limiting, geo-features, and abuse investigation.
10. Liveness: "process is alive" — failure triggers restart. Readiness: "can
    serve traffic now" — failure removes it from load balancing. Example: the app
    lost its DB connection or is warming a cache — restarting won't help
    (liveness OK), but it shouldn't receive traffic (readiness fail).
11. Encryption (confidentiality), integrity, server authentication.
12. `-k` disables ALL certificate verification — the script would happily talk to
    any man-in-the-middle. Correct fix: install/trust the company CA certificate
    (e.g., `--cacert corp-ca.pem` or add it to the system trust store).
13. 4xx = requests judged invalid by the server; 401 = failing authentication.
    Right after a deploy, that points at an auth configuration regression (wrong
    key/secret/issuer/audience config shipped) rather than a server crash (which
    would be 5xx).
14. L4 balances at TCP level — content-blind, very fast. L7 parses HTTP and can
    e.g. route by path/host (`/api` → service A), inject headers, or retry
    idempotent requests.
15. Example sequence:
    1. `dig +short shop.example.com` — does the name resolve, and to what?
    2. `nc -vz <ip> 443` — is the port reachable/open?
    3. `curl -v https://shop.example.com/health` — TLS OK? What HTTP status?
    4. Depending on status: 5xx → check backends/logs behind the LB
       (`docker logs` / `journalctl -u app`); cert error → check expiry;
       timeout → firewall/routing.

</details>

**Scoring:** 12+ → [Chapter 05](../05-docker-fundamentals/lesson.md). Below →
redo exercises 4.5, 4.6, 4.8 — failure-mode recognition is the core skill here.
