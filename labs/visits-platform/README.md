# Visits Platform Lab

This directory is the runnable reference project used from chapter 05 through
the capstone. It prevents the course examples from drifting into unrelated
snippets: each chapter adds one production concern to the same two-service
application.

## What is included

| Course area | Runnable asset |
|---|---|
| Docker | `Dockerfile`, `.dockerignore`, `compose.yaml` |
| Application testing | `tests/` and `requirements-dev.txt` |
| GitHub Actions | `.github/workflows/` |
| Jenkins | `Jenkinsfile` |
| GitLab CI | `.gitlab-ci.yml` |
| Kubernetes | `k8s/platform.yaml` |
| Helm | `helm/visits/` |
| Terraform and Ansible | `infra/` |
| Prometheus, Grafana, Loki | `compose.observability.yaml`, `observability/` |

The files are intentionally small enough to read. They are a starting point for
the exercises, not a hidden solution to every exercise.

## Quick start

Requirements: Docker Desktop with Compose v2.

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/visits
curl http://localhost:8000/metrics
```

Expected endpoints:

- API: <http://localhost:8000>
- worker metrics: <http://localhost:8001/metrics>
- Adminer, when the `tools` profile is enabled:
  <http://localhost:8082>

Run Adminer with:

```bash
docker compose --profile tools up --build
```

Stop the stack without deleting data:

```bash
docker compose down
```

Add `--volumes` only when you deliberately want to delete the database.

## Tests

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest
```

On PowerShell, activate with `.venv\Scripts\Activate.ps1`.
Tests that do not require PostgreSQL run everywhere. The CI workflows also set
`TEST_DATABASE_URL` and run the integration test against a disposable
PostgreSQL service.

## Using the CI examples

The GitHub Actions workflows in this directory are standalone-project assets.
GitHub only discovers `.github/workflows` at the repository root, so they do
not execute while `visits-platform` is nested inside the course repository.
Copy this directory into its own repository to activate them:

```bash
cp -R labs/visits-platform visits-platform-project
cd visits-platform-project
git init
git add .
git commit -m "chore: bootstrap visits platform"
```

The course's root quality workflow validates these nested workflow examples
with `actionlint` so they cannot drift unnoticed.

## Observability profile

Start the app and the local monitoring stack together:

```bash
docker compose -f compose.yaml -f compose.observability.yaml up --build
```

Then open Grafana at <http://localhost:3000> and Prometheus at
<http://localhost:9090>. The development-only Grafana login is
`admin` / `admin`; change it before exposing the service beyond localhost.

## Kubernetes

For a quick raw-manifest deployment:

```bash
kubectl apply -f k8s/platform.yaml
kubectl -n visits create secret generic visits-db \
  --from-literal=password='choose-a-local-lab-password'
kubectl -n visits get pods,svc,hpa,pdb,networkpolicy
```

The image names in the raw manifest and Helm values are placeholders. Build and
load the images into your local cluster, then replace `ghcr.io/example/...`
with your image coordinates. The database Secret is deliberately created at
runtime and never stored in Git.

For Helm:

```bash
kubectl create namespace visits
kubectl -n visits create secret generic visits-db \
  --from-literal=password='choose-a-local-lab-password'
helm lint helm/visits
helm template visits helm/visits --namespace visits
helm upgrade --install visits helm/visits --namespace visits \
  --set image.apiRepository=your-registry/visits-api \
  --set image.workerRepository=your-registry/visits-worker \
  --set image.tag=your-tag
```

The default Helm values deploy a single-node PostgreSQL StatefulSet for the
local lab. The password is never stored in chart values: both PostgreSQL and
the application read the existing `visits-db` Secret.

For an externally managed database, set `database.internal.enabled=false`, set
`database.host`, and supply at least one Kubernetes NetworkPolicy peer under
`database.externalEgress`. For example:

```yaml
database:
  host: postgres.database.svc.cluster.local
  internal:
    enabled: false
  externalEgress:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: database
      podSelector:
        matchLabels:
          app.kubernetes.io/name: postgres
```

The chart's `values.schema.json` rejects external-database configurations that
would leave database egress blocked.

## Infrastructure handoff

The Terraform lab creates three SSH-enabled containers and writes an Ansible
inventory. Ansible then configures those containers:

```bash
cd infra/terraform
terraform init
terraform apply
ANSIBLE_CONFIG=../ansible/ansible.cfg \
  ansible-playbook -i inventory.ini ../ansible/site.yml
terraform destroy
```

This is local lab infrastructure. Do not expose its SSH ports to untrusted
networks.
