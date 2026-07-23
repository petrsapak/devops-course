# Chapter 13 — Exercises

The [visits-platform infrastructure lab](../labs/visits-platform/README.md)
contains a complete local Docker-provider configuration. Use it after the core
exercises to compare state, generated outputs, and module structure.

Install Terraform in WSL2 first:

```bash
wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install -y terraform
terraform -version
```

(Or use OpenTofu: `tofu` — identical commands.) Work in `~/devops/ch13`.

---

## Exercise 13.1 — First apply

1. Create `main.tf` with the lesson §2 example (network + image + container).
2. `terraform init` — inspect what appeared (`.terraform/`, lock file).
3. `terraform plan` — read every line of the plan. How many to add?
4. `terraform apply`, then confirm with `docker ps` and `curl localhost:8090`.
5. Look at `terraform.tfstate` (`less` — just look, never edit) and find your
   container's real ID inside.

**Verify:** nginx answers on 8090; state file maps `docker_container.web` to the
running container's ID.

## Exercise 13.2 — Idempotency and targeted change

1. Run `terraform apply` again with no changes. What does it say and do?
2. Change `external = 8090` to `8091`. Plan — is it `~` update or `-/+` replace?
   Apply and verify.
3. Change the container `name`. Plan — update or replace this time? Read the
   plan's annotation telling you *which attribute forces replacement*.

**Verify:** no-change apply = "No changes" (idempotency); you found the
`# forces replacement` marker and can articulate why the distinction matters
when the resource is a database, not an nginx.

## Exercise 13.3 — Drift

1. Outside Terraform: `docker rm -f tf-web` (simulate a 2 a.m. manual "fix").
2. `terraform plan` — what does it propose and why?
3. Apply to heal. Then create drift the other way: change something ABOUT the
   container out-of-band... (most attributes require recreation; simplest:
   `docker rename tf-web tf-web-manual`) and plan again.

**Verify:** Terraform detected both kinds of drift by refreshing reality against
state. One sentence: how is this like and unlike Kubernetes reconciliation?
(Like: converge to declared state. Unlike: on-demand when you run it, not a
continuous controller.)

## Exercise 13.4 — Variables, outputs, validation

1. Add variables `env` (string, required), `external_port` (number, default
   8090, validation >1024) and an output `web_url`. Name the container
   `"web-${var.env}"`.
2. Apply with `-var env=dev`. Then try `-var external_port=80` — watch the
   validation reject it.
3. Create `dev.tfvars` and `terraform.tfvars`; learn the precedence by
   experiment: which wins between tfvars file and `-var` flag?
4. `terraform output web_url` and `terraform output -json` (the machine-readable
   form other tools consume).

**Verify:** validation blocked port 80 with your message; `-var` beat the file.

## Exercise 13.5 — for_each: a fleet

1. Convert the single container to `for_each = toset(["blue", "green"])` —
   names `web-blue`/`web-green`, ports 8091/8092 (hint: use a map instead of a
   set: `for_each = { blue = 8091, green = 8092 }`, then `each.key`/`each.value`).
2. Apply; curl both.
3. Add `"canary" = 8093` to the map and apply — what does the plan touch?
   (Just the new one — the graph is per-instance.)
4. Remove `green` and apply.

**Verify:** step 3's plan showed `1 to add, 0 to change, 0 to destroy` — existing
resources untouched. This is why for_each beats copy-paste.

## Exercise 13.6 — State surgery (safe sandbox edition)

1. `terraform state list` — inventory.
2. `terraform state show 'docker_container.web["blue"]'`.
3. Simulate the classic mistake: create a container manually
   (`docker run -d --name manual-nginx -p 8094:80 nginx:1.27`) and adopt it:
   add a matching resource block, then
   `terraform import 'docker_container.adopted' $(docker inspect -f '{{.Id}}' manual-nginx)`.
   Plan until it's clean (you'll need to align attributes — this teaches you to
   read provider docs).
4. The reverse: `terraform state rm docker_container.adopted` — TF forgets it
   (container keeps running, unmanaged again). Clean it up with docker.

**Verify:** after import + attribute alignment, plan shows no changes for the
adopted resource; after `state rm`, plan wants to create it again (you removed
the *mapping*, not the resource).

## Exercise 13.7 — Modules + two environments

Restructure into the standard layout:

```
ch13/
├── modules/web-stack/{main.tf,variables.tf,outputs.tf}
└── environments/
    ├── dev/main.tf      # module source ../../modules/web-stack, 1 replica, port 8095
    └── prod/main.tf     # 2 replicas, port 8096
```

(Replicas via for_each over a count-derived set, or accept a list of names —
your design.) Init and apply **each environment from its own directory**.

1. Confirm both stacks run simultaneously.
2. Where are the two state files? What does that mean for blast radius?
3. Change the module (e.g., add a label to containers) and apply dev only —
   prod untouched until *its* apply. Reflect: this is staged rollout of infra.

**Verify:** `environments/dev/terraform.tfstate` and `.../prod/terraform.tfstate`
exist separately; module change reached dev before prod, by your choice.

## Exercise 13.8 — The CI shape (dry run)

Without a real pipeline, rehearse the CI contract locally:

1. `terraform fmt -check` (dirty the formatting first to see it fail),
   `terraform validate`.
2. `terraform plan -out=tf.plan`, then inspect it: `terraform show tf.plan`.
3. Apply **the file**: `terraform apply tf.plan` — no re-planning, no approval
   prompt.
4. The safety property: make a change between plan and apply (edit the config),
   try `terraform apply tf.plan` again — stale plan behavior? (Try it: plan
   files are single-use; and if reality changed, apply fails safe.)
5. Write the four pipeline steps (PR vs merge phases) as a comment block in your
   main.tf — the design from lesson §6, in your own words.

**Verify:** you applied exactly-what-was-planned and saw the mechanism that makes
"reviewed plan = executed change" trustworthy.

## Exercise 13.9 — Destroy discipline

1. `terraform destroy` in dev — read the plan (everything `-`), approve.
2. Prod stays up (separate state — the payoff again).
3. Destroy prod too. `docker ps` — clean.

**Verify:** all lab containers/networks gone *via Terraform* — you never once
needed `docker rm` for managed resources. That's lifecycle ownership.

---

**Stretch goal (cloud-curious, still free):** the same workflow with the
`github` provider — manage a repo, its labels, and branch protection as code
(`resource "github_repository"`, `github_branch_protection`). Everything
transfers; only the provider block changed. That's the multi-cloud promise
demonstrated on an API you already have.
