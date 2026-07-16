# Chapter 16 — Exercises

Work in `~/devops/ch16` and your CI repo from ch 07. These wire the security
stack into the pipeline you already own, then drill the SRE practices.

---

## Exercise 16.1 — Secret scanning, both ends

1. **Local**: install gitleaks (`docker run` works:
   `docker run --rm -v $PWD:/repo zricethezav/gitleaks:latest detect --source /repo`).
   Plant a fake AWS key (`AKIA` + 16 uppercase/digits) in a file, commit to a
   scratch branch, scan — caught?
2. Wire it as a pre-commit hook via the `pre-commit` framework (ch 03 stretch
   goal, now mandatory): `.pre-commit-config.yaml` with the gitleaks hook.
3. **CI end**: add a gitleaks job to your GitHub Actions workflow (scans full
   history: `fetch-depth: 0`).
4. Drill the response: "the key was real and pushed." Write the ordered
   response steps (what's first?) — check yourself against ch 03's test Q14.

**Verify:** the planted key is blocked at commit time AND fails CI; your
response list starts with *rotate/revoke*, not with history rewriting.

## Exercise 16.2 — SCA + SAST in the pipeline

1. Add to CI: `pip-audit -r requirements.txt` (SCA) and Semgrep
   (`semgrep scan --config auto --error`) (SAST).
2. Test SCA: temporarily pin an old vulnerable dep (`flask==0.12`) — watch the
   audit fail with named CVEs. Restore.
3. Test SAST: add a deliberately awful endpoint —
   `@app.get("/run")` doing `subprocess.run(request.args["cmd"], shell=True)` —
   and watch Semgrep flag command injection. Remove it (obviously).
4. Policy tuning: configure one of the tools to fail only on HIGH+ severity,
   and write the one-line justification (the "gate on severity, baseline then
   ratchet" reality from the lesson).

**Verify:** both scanners have a demonstrated catch AND a tuned threshold —
you've seen signal and managed noise.

## Exercise 16.3 — IaC scanning

1. Run `trivy config .` (or Checkov) over your ch 13 Terraform and ch 11/12
   Kubernetes YAML.
2. Read every finding; classify: real issue / lab-acceptable / false positive.
3. Fix at least two real ones (typical catches: container without resource
   limits, missing securityContext, privileged flags).
4. Add `trivy config` to CI for the manifests directory.

**Verify:** before/after finding counts differ; your K8s deployment now carries
`runAsNonRoot: true` and `allowPrivilegeEscalation: false` if it didn't already.

## Exercise 16.4 — SBOM + the "are we affected?" drill

1. Generate an SBOM for your visits image:
   `trivy image --format cyclonedx --output sbom.json <image>` (or syft).
2. Explore it with jq: how many components? List the top-level Python packages.
3. The drill: pick any real CVE from your earlier trivy scans; using ONLY the
   SBOM, answer "do we ship the affected package, and which version?"
   (`jq '.components[] | select(.name=="<pkg>")' sbom.json`).
4. Attach SBOM generation to the CI build job (artifact, uploaded next to the
   image).

**Verify:** you answered an "are we affected" question in under a minute from a
file — that's the entire value proposition, experienced once so you remember it.

## Exercise 16.5 — Vault, hands on

1. Run dev-mode Vault:
   `docker run -d --name vault --cap-add=IPC_LOCK -p 8200:8200 -e VAULT_DEV_ROOT_TOKEN_ID=root hashicorp/vault`.
2. CLI basics (`export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root`,
   vault CLI via apt or `docker exec`):
   - `vault kv put secret/visits db_password=s3cret`
   - `vault kv get -field=db_password secret/visits`
3. App integration, simplest honest pattern: an entrypoint script that fetches
   the secret via `curl` to Vault's HTTP API
   (`curl -H "X-Vault-Token: $VAULT_TOKEN" .../v1/secret/data/visits | jq -r .data.data.db_password`)
   and exports it to the app env — run your visits container this way.
4. **Dynamic secrets** (the wow): enable the database secrets engine against
   your lab postgres (`vault secrets enable database`, configure connection +
   role per Vault's postgres docs), then `vault read database/creds/app-role`
   twice — two different live credentials. Check in psql (`\du`) that the users
   exist... then watch them expire after the TTL.

**Verify:** step 4 — you held two auto-created, auto-expiring DB credentials.
One sentence: why does this change the meaning of "leaked credential"?

## Exercise 16.6 — Sign an image

1. Install cosign; generate a keypair (`cosign generate-key-pair`).
2. Sign your registry image: `cosign sign --key cosign.key <image>@<digest>`
   (sign the digest, not the tag — you know why by now).
3. Verify: `cosign verify --key cosign.pub <image>@<digest>` — then verify a
   DIFFERENT image and watch it fail.

**Verify:** verification passes only for what you signed; you can articulate
where verification would run in production (cluster admission policy).

## Exercise 16.7 — Write an SLO + budget policy (paper, but binding)

For your visits service, write a one-page document:

1. Two SLIs (availability: non-5xx ratio; latency: % under 300ms) with exact
   PromQL (ch 15 skills).
2. SLO targets with a justification aimed at a product manager, including what
   one more nine would cost.
3. The error-budget policy table: budget >50% → ?, 10–50% → ?, exhausted → ?
   (deploy policy, work priority, who decides exceptions).

**Verify:** a teammate (or you, next week) can execute the policy without
interpretation — "exhausted" has a defined, pre-agreed consequence.

## Exercise 16.8 — Game day + blameless post-mortem (the finale)

Run a full-loop drill on your ch 15 stack:

1. Prepare: write a runbook for HighErrorRate (symptoms → 3 checks → 2
   mitigations) BEFORE the drill.
2. Inject: your 15.8 script (or a friend) breaks one thing while traffic runs.
3. Respond in roles (solo is fine — narrate the IC hat consciously): detect via
   alert, mitigate FIRST (restart/rollback/flag), then diagnose. Keep a
   timestamped log of every action.
4. Write the post-mortem using the lesson's structure: timeline, impact
   (estimate budget burned from the dashboard!), contributing causes (find at
   least two — "the injected fault" plus what made detection/mitigation slower
   than it could be), what went well/poorly, 2–3 action items with owners.
5. **Ship one action item** (improve the runbook, add a missing alert, fix a
   dashboard gap) — a post-mortem with rotting actions is theater; yours won't be.

**Verify:** the post-mortem names zero humans as causes, cites dashboard data,
and one action item is demonstrably done. You've now run the entire loop this
course exists to teach.

---

**Cleanup:** `docker rm -f vault`; keep everything else for the capstone.
