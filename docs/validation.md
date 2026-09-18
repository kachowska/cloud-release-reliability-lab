# Validation matrix

| Claim | Command/evidence | Passing condition | What it does not prove |
|---|---|---|---|
| API contract | Pytest + `pytest.xml` | exact tests pass | deployed behavior |
| Bash entry points | `bash -n scripts/*.sh` + dry-run tests | parse and contracts pass | external tools work |
| PowerShell parity | `pwsh` parser + smoke on Windows | scripts parse/run | Linux deployment |
| Terraform configuration | `fmt -check`, `init`, `validate` | both roots pass | apply, quota, runtime health |
| Container delivery | evidence collector Docker checks | build, UID, four endpoints pass | production registry/security review |
| Kubernetes rollout | `deploy.sh` and cluster state | desired ready replicas | failure recovery |
| Controlled failure recovery | `failure-drill.sh` evidence | timeout, capacity retained, undo, smoke | arbitrary incident recovery |
| CI | completed workflow and uploaded artifacts | both jobs green | production release |
| Azure target | local Terraform validation only | schema/configuration valid | Azure login, plan/apply, AKS health, cost |

The evidence collector exits nonzero on executed failures. Optional unavailable runtimes
are `skipped` by default and can be promoted to hard requirements with command flags.

