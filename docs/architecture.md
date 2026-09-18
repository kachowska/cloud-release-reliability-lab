# Architecture and release decisions

## Components and ownership

| Component | Responsibility | Failure signal |
|---|---|---|
| FastAPI service | Health, release identity, and scrapeable state | HTTP status/payload |
| Docker image | Reproducible non-root runtime | Build, health check, runtime UID |
| Terraform root | Namespace and application lifecycle | `fmt`, `init`, `validate`, `apply` |
| Kubernetes Deployment | Health-aware rolling replacement | Deployment conditions and ready replicas |
| ClusterIP Service | Routes only to ready Pods | Smoke failure or missing endpoints |
| Automation scripts | Repeatable validation, rollout, drill, rollback | Typed exit codes and evidence reports |
| GitHub Actions | Replays local gates and an ephemeral Kind drill | Required job conclusion and artifacts |
| Azure target | Documents an AKS/ACR migration shape | Configuration validation only |

## Health semantics

Liveness answers: “Is this process alive and able to serve HTTP?” It remains `200`
during the controlled failure so Kubernetes does not create a restart loop.

Readiness answers: “Should this instance receive traffic?” Setting
`RELEASE_FORCE_NOT_READY=true` returns `503`, preventing the candidate Pod from joining
Service endpoints. With two replicas, `maxUnavailable=0`, and `maxSurge=1`, the old
ReplicaSet should retain two ready Pods while one failed candidate remains unready.

## Configuration flow

Terraform writes non-secret release identity into a ConfigMap. The controlled failure
flag is a separate Deployment environment value so changing it creates a new Pod template
revision. The `/version` endpoint and response header make it possible to verify which
candidate is serving, rather than accepting HTTP 200 from an unknown release.

## Trust boundaries

- Client input is limited to GET requests; the failure switch is not an HTTP endpoint.
- The Pod does not mount a service-account token and cannot call the Kubernetes API.
- Kubernetes/provider credentials remain on the operator or CI runner.
- Azure credentials are neither requested nor stored by this repository.
- Evidence files contain command outputs but collectors avoid environment dumps.

## Production changes

A production design would use registry digests, signed images, admission policy, managed
identity, network policy, an ingress/gateway, secrets from a managed store, a Pod
Disruption Budget, autoscaling based on measured demand, remote state with locking, and
central logs/metrics/alerts. Those controls are intentionally not claimed by this lab.

