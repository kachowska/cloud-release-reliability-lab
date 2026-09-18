# Cloud Release Reliability Lab

A small release-engineering system that turns health-aware delivery, infrastructure
automation, smoke testing, and rollback into inspectable evidence. The workload is a
typed FastAPI operational service, not a business CRUD demo.

The repository deliberately separates three proof levels:

1. **Executed local proof** — tests and commands recorded under `evidence/`.
2. **Executable configuration** — Docker, Terraform, Kubernetes, Bash, PowerShell,
   and GitHub Actions definitions that can be validated without claiming a rollout.
3. **Unexecuted target design** — the Azure module is configuration-only until an
   authorized subscription run proves otherwise.

## What is implemented

- `/health/live`, `/health/ready`, `/version`, and Prometheus-compatible `/metrics`.
- Environment-driven release metadata and a controlled readiness-only failure mode.
- One-line structured JSON request logs with request and release correlation.
- Multi-stage, non-root, read-only-capable Docker image with a health check.
- Terraform-managed namespace, ConfigMap, Deployment, and ClusterIP Service.
- Zero-unavailable rolling update settings, resource controls, security context,
  liveness/readiness probes, and immutable release annotations.
- Bash deployment, smoke, rollback, failure-drill, and evidence commands.
- PowerShell validation and smoke-test parity.
- GitHub Actions quality/container gates and an ephemeral Kind rollout/rollback job.
- A configuration-only AKS/ACR migration target, isolated from local runtime claims.

## Architecture

```text
source change
  -> Pytest + Ruff + script checks
  -> Docker image (non-root, health-aware)
  -> Terraform Kubernetes resources
  -> rolling rollout + four-endpoint smoke
  -> controlled not-ready candidate
  -> rollout timeout observed + old capacity retained
  -> rollout undo + post-recovery smoke
  -> JSON / Markdown evidence
```

See [docs/architecture.md](docs/architecture.md) for ownership and trust boundaries.

## Fast local path

Python 3.12 or 3.13:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --editable '.[dev]'
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

In another terminal:

```bash
scripts/smoke.sh http://127.0.0.1:8080
```

Docker Compose fallback:

```bash
RELEASE_VERSION=local-001 RELEASE_COMMIT_SHA=abc1234 docker compose up --build --wait
EXPECTED_VERSION=local-001 EXPECTED_COMMIT_SHA=abc1234 scripts/smoke.sh
docker compose down
```

## Command-backed validation

```bash
scripts/validate.sh
```

The collector runs tests, compilation, Ruff when installed, Bash parsing,
PowerShell parsing when `pwsh` exists, Terraform formatting/validation when the CLI
exists, and a Docker build plus four-endpoint container smoke when the daemon is
reachable. Missing optional runtimes are recorded as **skipped**, never as passed.

CI can enforce the major prerequisites:

```bash
scripts/validate.sh --require-docker --require-terraform
```

Outputs:

- `evidence/local-validation.json` — command results, output tails, durations, counts.
- `evidence/local-validation.md` — recruiter-friendly proof summary and boundaries.
- `evidence/pytest.xml` — machine-readable test results.

## Local Kubernetes release drill

Create a Kind cluster, build and load the image, then deploy:

```bash
kind create cluster --name release-lab
docker build -t cloud-release-reliability-lab:local .
kind load docker-image cloud-release-reliability-lab:local --name release-lab
scripts/deploy.sh \
  --context kind-release-lab \
  --image cloud-release-reliability-lab:local \
  --image-pull-policy Never \
  --release-id local-001 \
  --commit-sha abc1234
```

Expose the ClusterIP Service and run the drill:

```bash
kubectl --context kind-release-lab -n release-lab \
  port-forward service/release-status 8080:80
scripts/smoke.sh http://127.0.0.1:8080
scripts/failure-drill.sh \
  --context kind-release-lab \
  --base-url http://127.0.0.1:8080
```

The drill patches a new candidate to fail readiness, expects its rollout to time out,
asserts that the old ready replicas still meet desired capacity, performs
`kubectl rollout undo`, waits for recovery, and writes measured evidence. Full details
are in [docs/failure-drill.md](docs/failure-drill.md).

## Configuration and security decisions

- No secrets are placed in a ConfigMap or source. A production implementation should
  use workload identity plus a managed secret store.
- Terraform state is local only for the disposable lab. Team use requires encrypted
  remote state, locking, access control, and state backup.
- The container drops all Linux capabilities, disallows privilege escalation, uses a
  read-only root filesystem in Kubernetes/Compose, and runs as UID/GID 10001.
- The Kubernetes Service is ClusterIP-only; exposure is an environment-specific concern.
- Failure injection affects readiness while preserving liveness, so the scenario models
  an instance that should stop receiving traffic but does not need a restart loop.

## Honest limitations

- A YAML workflow is not a passed CI run. Only a completed GitHub Actions run can prove CI.
- `terraform validate` proves configuration consistency, not a deployed cluster.
- A reachable Kubernetes cluster and executed drill are required before claiming rollout
  or rollback results.
- No Azure authentication, plan, apply, AKS rollout, quota check, or cost validation is
  implied by `infra/azure/`.
- Local measurements are evidence for that specific machine and timestamp, not uptime or
  production performance claims.

See [docs/operations.md](docs/operations.md) for troubleshooting and recovery commands.

