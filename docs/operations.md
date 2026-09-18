# Operations and troubleshooting

## Failure classes

| Symptom | Likely layer | First evidence |
|---|---|---|
| Python tests fail | application contract | Pytest failure and JUnit XML |
| Image will not build | dependency or Dockerfile | `docker_build` output in evidence JSON |
| Container starts but smoke fails | runtime configuration/service | container logs and endpoint assertion |
| Terraform init fails | network/provider resolution | Terraform init output |
| Terraform validate fails | provider/schema/configuration | exact validate diagnostic |
| Pod Pending | scheduler/resources/image | Pod describe and events |
| Pod restarts | liveness/process | restart count and previous logs |
| Rollout stalls, old Pods stay ready | readiness candidate failure | Deployment conditions and drill output |
| Service smoke fails with ready Pods | selector/port/routing | Endpoints, Service describe, port-forward log |

## Local service

```bash
RELEASE_VERSION=debug RELEASE_COMMIT_SHA=working-tree \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
scripts/smoke.sh http://127.0.0.1:8080
```

To inspect the intended readiness failure without Kubernetes:

```bash
RELEASE_FORCE_NOT_READY=true python -m uvicorn app.main:app --port 8080
curl -i http://127.0.0.1:8080/health/live
curl -i http://127.0.0.1:8080/health/ready
```

Expected: liveness is 200; readiness is 503 with a structured reason.

## Container diagnostics

```bash
docker image inspect cloud-release-reliability-lab:local --format '{{.Size}} {{.Config.User}}'
docker run --rm --entrypoint id cloud-release-reliability-lab:local -u
docker compose logs --no-color release-service
docker compose ps
```

## Kubernetes rollback

```bash
scripts/rollback.sh --context kind-release-lab
```

Rollback restores the previous ReplicaSet. It does not change Terraform state; always
review drift afterward. If no prior revision exists, rollback must fail rather than
pretend recovery.

## Cleanup

For a disposable local cluster:

```bash
terraform -chdir=infra/kubernetes destroy -auto-approve \
  -var kube_context=kind-release-lab
kind delete cluster --name release-lab
```

These commands are intentionally manual because destruction should name an exact target.
The Azure configuration must not be applied or destroyed without explicit subscription
authorization and a reviewed state file.

