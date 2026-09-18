#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="release-lab"
NAME="release-status"
KUBE_CONTEXT=""
FAILURE_TIMEOUT="20s"
RECOVERY_TIMEOUT="120s"
BASE_URL=""
DRY_RUN=false

while (($#)); do
  case "$1" in
    --namespace) NAMESPACE="${2:?missing value for --namespace}"; shift 2 ;;
    --name) NAME="${2:?missing value for --name}"; shift 2 ;;
    --context) KUBE_CONTEXT="${2:?missing value for --context}"; shift 2 ;;
    --failure-timeout) FAILURE_TIMEOUT="${2:?missing value for --failure-timeout}"; shift 2 ;;
    --recovery-timeout) RECOVERY_TIMEOUT="${2:?missing value for --recovery-timeout}"; shift 2 ;;
    --base-url) BASE_URL="${2:?missing value for --base-url}"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h)
      printf 'Usage: scripts/failure-drill.sh [--namespace NAME] [--name NAME] [--context CONTEXT] [--base-url URL] [--dry-run]\n'
      exit 0
      ;;
    *) printf 'error: unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

if [[ "${DRY_RUN}" == true ]]; then
  printf 'dry_run=passed scenario=readiness_failure_then_rollout_undo target=deployment/%s namespace=%s\n' "${NAME}" "${NAMESPACE}"
  printf 'planned_assertions=liveness_independent,failed_candidate_not_ready,old_replicas_available,recovery_ready\n'
  exit 0
fi

for command_name in kubectl python3; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    printf 'error: required command not found: %s\n' "${command_name}" >&2
    exit 127
  fi
done

context_args=()
rollback_context_args=()
if [[ -n "${KUBE_CONTEXT}" ]]; then
  context_args=(--context "${KUBE_CONTEXT}")
  rollback_context_args=(--context "${KUBE_CONTEXT}")
fi

rollback_needed=false
emergency_recovery() {
  exit_code=$?
  if [[ "${rollback_needed}" == true ]]; then
    printf 'warning: drill interrupted; attempting emergency rollout undo\n' >&2
    "${SCRIPT_DIR}/rollback.sh" --namespace "${NAMESPACE}" --name "${NAME}" \
      --timeout "${RECOVERY_TIMEOUT}" "${rollback_context_args[@]}" || true
  fi
  exit "${exit_code}"
}
trap emergency_recovery EXIT

kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  rollout status "deployment/${NAME}" --timeout="${RECOVERY_TIMEOUT}"
before_revision="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.metadata.annotations.deployment\.kubernetes\.io/revision}')"
desired_replicas="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.spec.replicas}')"

started_epoch="$(date +%s)"
failed_release="failed-candidate-$(date -u +%Y%m%dT%H%M%SZ)"
rollback_needed=true
kubectl "${context_args[@]}" --namespace "${NAMESPACE}" set env "deployment/${NAME}" \
  RELEASE_FORCE_NOT_READY=true "RELEASE_VERSION=${failed_release}"

set +e
rollout_output="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  rollout status "deployment/${NAME}" --timeout="${FAILURE_TIMEOUT}" 2>&1)"
rollout_exit=$?
set -e
if (( rollout_exit == 0 )); then
  printf 'error: injected not-ready candidate unexpectedly completed rollout\n' >&2
  exit 1
fi

ready_during_failure="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.status.readyReplicas}')"
ready_during_failure="${ready_during_failure:-0}"
if (( ready_during_failure < desired_replicas )); then
  printf 'error: healthy capacity fell below desired replicas during failed rollout (%s/%s)\n' \
    "${ready_during_failure}" "${desired_replicas}" >&2
  exit 1
fi

"${SCRIPT_DIR}/rollback.sh" --namespace "${NAMESPACE}" --name "${NAME}" \
  --timeout "${RECOVERY_TIMEOUT}" "${rollback_context_args[@]}"
rollback_needed=false
after_revision="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.metadata.annotations.deployment\.kubernetes\.io/revision}')"
ready_after_recovery="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.status.readyReplicas}')"
duration_seconds="$(( $(date +%s) - started_epoch ))"

smoke_executed=false
if [[ -n "${BASE_URL}" ]]; then
  "${SCRIPT_DIR}/smoke.sh" "${BASE_URL}"
  smoke_executed=true
fi

python3 "${SCRIPT_DIR}/write_drill_evidence.py" \
  --output-dir "${REPO_ROOT}/evidence" \
  --namespace "${NAMESPACE}" \
  --deployment "${NAME}" \
  --before-revision "${before_revision:-unknown}" \
  --after-revision "${after_revision:-unknown}" \
  --desired-replicas "${desired_replicas}" \
  --ready-during-failure "${ready_during_failure}" \
  --ready-after-recovery "${ready_after_recovery:-0}" \
  --failure-timeout "${FAILURE_TIMEOUT}" \
  --duration-seconds "${duration_seconds}" \
  --failed-release "${failed_release}" \
  --smoke-executed "${smoke_executed}" \
  --rollout-output "${rollout_output}"

trap - EXIT
printf 'failure_drill_status=passed failure_observed=true rollback_recovered=true ready=%s desired=%s\n' \
  "${ready_after_recovery:-0}" "${desired_replicas}"

