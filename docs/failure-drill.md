# Controlled readiness failure and rollback drill

## Purpose

Prove the difference between an alive process and a release candidate that must not take
traffic. The drill is deliberately reversible and changes no persistent application data.

## Preconditions

- A reachable Kubernetes context explicitly selected by the operator.
- The Terraform-managed Deployment is fully rolled out with at least one ready replica.
- `kubectl rollout history deployment/release-status -n release-lab` shows a prior revision.
- For HTTP proof, a port-forward to the ClusterIP Service is running.

Run the contract without touching a cluster:

```bash
scripts/failure-drill.sh --dry-run
```

Run the real drill:

```bash
scripts/failure-drill.sh \
  --context kind-release-lab \
  --namespace release-lab \
  --name release-status \
  --base-url http://127.0.0.1:8080
```

## Assertions made by the script

1. The baseline Deployment reports a completed rollout.
2. A new template revision sets `RELEASE_FORCE_NOT_READY=true`.
3. `kubectl rollout status` fails within the bounded failure timeout.
4. Ready replicas during the failure remain at least the desired replica count.
5. `kubectl rollout undo` completes and restores ready capacity.
6. If a base URL is supplied, all four HTTP smoke checks pass after recovery.
7. Measured values and the failed rollout output are written to JSON and Markdown.

If the script is interrupted after injection, its exit trap attempts an emergency undo.
This is a guardrail, not a substitute for watching Deployment conditions and events.

## Diagnostics

```bash
kubectl -n release-lab describe deployment/release-status
kubectl -n release-lab get pods -l app.kubernetes.io/name=release-status -o wide
kubectl -n release-lab get events --sort-by=.lastTimestamp
kubectl -n release-lab logs -l app.kubernetes.io/name=release-status --tail=100
kubectl -n release-lab rollout history deployment/release-status
```

The expected failed candidate is `Running` but not `Ready`; its readiness endpoint
returns 503 while liveness remains 200. Image pull, crash-loop, scheduling, or probe
connection failures are different incidents and should not be described as this drill.

## Terraform reconciliation

The emergency `kubectl set env` and `rollout undo` actions model operational rollback.
They are temporary imperative changes. Run `terraform plan` afterward; a healthy undo
should match the Terraform-managed baseline. Review any remaining drift before apply.

