# Chapter 13 — Infrastructure as Code: Terraform

## Learning objectives

1. Explain IaC and why declarative + stateful beats scripts for infrastructure.
2. Write HCL: providers, resources, variables, outputs, data sources.
3. Master the core loop: `init` → `plan` → `apply` → `destroy`, and read plans critically.
4. Understand state: what it is, why it's sacred, remote backends, locking.
5. Structure real projects: modules, environments, CI integration.

Local-first note: we practice against the **Docker provider** (real
infrastructure on your machine — containers, networks, volumes) so every concept
is hands-on without a cloud bill. Swap the provider and the *identical* workflow
manages AWS/Azure/GCP.

---

## 1. Why IaC, and why Terraform's model

Ch 01 named the villain: **snowflake servers** — hand-built, unreproducible,
undocumented. IaC's answer: infrastructure defined in files, in Git, applied by
tools. What files-in-Git buys: review (a VPC change gets a PR review like code),
reproducibility (rebuild an environment from scratch), audit (git log = who
changed what, when, why), disaster recovery that isn't archaeology.

Two philosophies:

- **Imperative** (scripts, CLI): *how* — "create VM, then network, then attach."
  You own ordering, error recovery, and idempotency yourself.
- **Declarative** (Terraform): *what* — "these 3 resources should exist with
  these properties." The tool computes the difference between declared and
  actual, and executes only that difference.

Terraform in one sentence: **declarative descriptions + a state file recording
what it manages + providers that translate to real APIs** (AWS, Azure, GCP,
Kubernetes, GitHub, Docker, ~4000 more). Same tool, same workflow, any API.
(Note: OpenTofu is the open-source fork with identical basics — everything here
applies to both.)

Terraform (provisioning: creating infra) vs Ansible (configuration: setting up
what's inside) — ch 14 completes the pair.

## 2. HCL — the language

A complete working example (`main.tf`):

```hcl
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}          # talks to your local Docker daemon

resource "docker_network" "app" {
  name = "tf-appnet"
}

resource "docker_image" "nginx" {
  name = "nginx:1.27"
}

resource "docker_container" "web" {
  name  = "tf-web"
  image = docker_image.nginx.image_id     # ← reference = dependency
  networks_advanced {
    name = docker_network.app.name
  }
  ports {
    internal = 80
    external = 8090
  }
}
```

Anatomy:

- `resource "<type>" "<local-name>"` — the unit of infrastructure. The local
  name is *your* handle, not the real-world name.
- **References** (`docker_image.nginx.image_id`) do double duty: they wire
  values AND declare dependencies — Terraform builds a dependency graph and
  creates/destroys in the right order (network before container; reverse on
  destroy). You almost never write explicit ordering.
- Providers are plugins downloaded by `terraform init`, pinned with version
  constraints (`~> 3.0` = any 3.x).

### Variables, outputs, locals

```hcl
# variables.tf
variable "external_port" {
  type        = number
  default     = 8090
  description = "Host port for the web container"
  validation {
    condition     = var.external_port > 1024
    error_message = "Use an unprivileged port."
  }
}

variable "env" {
  type = string          # no default = required
}

# outputs.tf
output "web_url" {
  value = "http://localhost:${docker_container.web.ports[0].external}"
}
```

Usage: `var.external_port` in resources; supply values via `-var env=dev`,
`terraform.tfvars`, `dev.tfvars` (`-var-file=dev.tfvars`), or `TF_VAR_env`
env vars. **Outputs** surface computed values (IPs, URLs, IDs) — for humans and
for other tooling.

```hcl
# data sources: READ existing things you don't manage
data "docker_network" "bridge" {
  name = "bridge"
}
# then: data.docker_network.bridge.id
```

`count` and `for_each` create resource sets:

```hcl
resource "docker_container" "web" {
  for_each = toset(["blue", "green"])
  name     = "web-${each.key}"
  image    = docker_image.nginx.image_id
}
```

## 3. The core loop

```bash
terraform init      # download providers, set up backend — once per checkout
terraform fmt       # canonical formatting
terraform validate  # syntax/type check
terraform plan      # THE step: computed diff, changes nothing
terraform apply     # execute (shows plan again, asks approval)
terraform destroy   # delete everything this config manages
```

> **Command by command** (all read the `.tf` files in the current directory):
> - `init` — downloads the providers your config requires into `.terraform/` and writes `.terraform.lock.hcl` (pinning exact provider versions — commit it, it's a lockfile like any other). Run once per fresh checkout, and again whenever providers/backend change. Expect: `Terraform has been successfully initialized!`
> - `fmt` — rewrites files into canonical formatting (prints the names of changed files). Run it in CI as `fmt -check` — formatting debates end here, same as any code formatter.
> - `validate` — syntax and internal consistency (bad references, type errors), no cloud/API calls.
> - `plan` — the heart: refresh reality from the provider, diff against config, print what *would* change, change nothing. Details in the reading-a-plan section below.
> - `apply` — plan again, show it, prompt `Do you want to perform these actions?` — type `yes` — then execute in dependency order, updating the state file. `-auto-approve` skips the prompt (labs and CI with a reviewed saved plan; nowhere else).
> - `destroy` — a plan whose goal is "nothing this config manages exists", same confirmation flow. Precise scope: only resources in this config's *state* — it never touches things Terraform doesn't manage.
> **Expect from `apply`:**
> ```
> docker_network.app: Creating...
> docker_network.app: Creation complete after 1s [id=b1f4...]
> docker_container.web: Creating...
> Apply complete! Resources: 3 added, 0 changed, 0 destroyed.
> ```
> Note the order — network before container, derived from the reference graph, nobody wrote it down.

### Reading a plan — the professional skill

```
Plan: 2 to add, 1 to change, 1 to destroy.

  # docker_container.web must be replaced
-/+ resource "docker_container" "web" {
      ~ name  = "tf-web" -> "tf-web-v2"   # forces replacement
      ...
```

The symbols: `+` create · `-` destroy · `~` update in place ·
`-/+` **destroy and recreate** ("replace").

The critical discipline: **hunt for replaces before approving.** Some attribute
changes can't be done in place (renaming a container, changing an AWS RDS
availability zone…) and Terraform will *delete and recreate* — which for a
database is an outage-slash-catastrophe hiding behind a one-line diff. A plan
that says "1 to destroy" when you expected "1 to change" is a stop-and-think
moment. In CI, plans are posted into PRs for exactly this review.

## 4. State — the sacred file

After `apply`, `terraform.tfstate` maps your config names to real-world IDs:
"`docker_container.web` **is** container `f2a1c3d…`". Plan = a three-way diff:
**config** (desired) vs **state** (what TF believes) vs **reality** (refreshed
from the provider).

Consequences:

- **Lose the state → Terraform forgets it owns anything.** Plan shows "create
  everything" while the old resources still run — duplicates or manual cleanup
  hell. State is precious.
- **Never edit state by hand.** Surgical tools exist:
  `terraform state list` (every address in state) / `state show docker_container.web`
  (one resource's recorded attributes) / `state mv` (rename a resource in state after
  refactoring config — avoids a destroy/recreate) / `state rm` (forget a resource
  *without destroying it* — it keeps running, unmanaged) and `terraform import`
  (the inverse: adopt an existing real resource into state so Terraform manages it
  from now on).
- State may contain **secrets in plaintext** (DB passwords in resource
  attributes) → state storage must be access-controlled; never commit
  `terraform.tfstate` to Git.
- **Drift**: someone changes reality outside Terraform (console click, docker
  CLI). Next plan flags the difference; apply reverts it (reconciliation, ch 11
  cousin — but on-demand, not continuous).

### Remote backends — mandatory for teams

Local state on one laptop = single point of failure + no collaboration.
Remote backends (S3+DynamoDB, Azure Blob, GCS, Terraform Cloud) store state
centrally with **locking** — two simultaneous applies corrupt state; the lock
serializes them.

```hcl
terraform {
  backend "s3" {
    bucket         = "acme-tfstate"
    key            = "app/prod/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "tf-locks"
    encrypt        = true
  }
}
```

(Lab: we stay with local state; know that team #1 rule is "remote backend first".)

## 5. Modules and project structure

A **module** = a directory of `.tf` files with variables (inputs) and outputs —
a function for infrastructure:

```
modules/web-stack/
├── main.tf         # network + image + container(s)
├── variables.tf    # env, port, replicas...
└── outputs.tf      # url
```

```hcl
# environments/dev/main.tf
module "web" {
  source        = "../../modules/web-stack"
  env           = "dev"
  external_port = 8090
  replicas      = 1
}

# environments/prod/main.tf
module "web" {
  source        = "../../modules/web-stack"
  env           = "prod"
  external_port = 8080
  replicas      = 3
}
```

Each environment directory has its **own state** — a prod apply cannot touch
dev, and blast radii stay separated. This layout (modules + per-env roots +
per-env state) is the industry-standard shape; the alternative spelling is
**workspaces** (one config, `terraform workspace select prod`) — simpler,
weaker isolation; fine for small setups.

Public registry modules (registry.terraform.io) are the Helm-charts of infra:
`terraform-aws-modules/vpc/aws` instead of hand-rolling 40 VPC resources.

## 6. Terraform in CI — the pipeline pattern

The mature flow (mirrors everything since ch 07):

```
PR opened:    terraform fmt -check → validate → plan  → post plan as PR comment
              (humans review the DIFF OF REALITY, not just the code diff)
PR merged:    terraform apply (the reviewed plan, via -out=planfile)
```

Key details: `plan -out=tf.plan` + `apply tf.plan` guarantees you apply
*exactly* what was reviewed (reality may have moved between plan and apply —
the saved plan fails safe). Credentials come from CI secrets (ch 07); state
lives in the remote backend; nobody applies from laptops. Tools in the space:
Atlantis (PR-driven applies), Terraform Cloud, Spacelift.

## 7. Terraform vs friends (know the map)

| Tool | Niche |
|------|-------|
| Terraform / OpenTofu | multi-cloud declarative provisioning — the default |
| Pulumi | same model, real languages (TS/Python/Go) instead of HCL |
| CloudFormation / Bicep | AWS-only / Azure-only equivalents |
| Ansible | configuration *inside* machines; light provisioning (ch 14) |
| Crossplane | infra as Kubernetes objects (GitOps-native provisioning) |

## Further reading

- developer.hashicorp.com/terraform — "Get Started" + the Docker provider docs
  (registry.terraform.io/providers/kreuzwerker/docker).
- *Terraform: Up & Running* (Brikman) — the book, especially state & modules chapters.

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 14: Ansible](../14-ansible/lesson.md)
