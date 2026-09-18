#!/usr/bin/env bash
set -Eeuo pipefail

NAMESPACE="release-lab"
NAME="release-status"
KUBE_CONTEXT=""
TIMEOUT="120s"
DRY_RUN=false

while (($#)); do
  case "$1" in
    --namespace) NAMESPACE="${2:?missing value for --namespace}"; shift 2 ;;
    --name) NAME="${2:?missing value for --name}"; shift 2 ;;
    --context) KUBE_CONTEXT="${2:?missing value for --context}"; shift 2 ;;
    --timeout) TIMEOUT="${2:?missing value for --timeout}"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h)
      printf 'Usage: scripts/rollback.sh [--namespace NAME] [--name NAME] [--context CONTEXT] [--timeout DURATION] [--dry-run]\n'
      exit 0
      ;;
    *) printf 'error: unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

if [[ "${DRY_RUN}" == true ]]; then
  printf 'dry_run=passed action=kubectl_rollout_undo target=deployment/%s namespace=%s\n' "${NAME}" "${NAMESPACE}"
  exit 0
fi
if ! command -v kubectl >/dev/null 2>&1; then
  printf 'error: required command not found: kubectl\n' >&2
  exit 127
fi

context_args=()
if [[ -n "${KUBE_CONTEXT}" ]]; then
  context_args=(--context "${KUBE_CONTEXT}")
fi

kubectl "${context_args[@]}" --namespace "${NAMESPACE}" rollout undo "deployment/${NAME}"
kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  rollout status "deployment/${NAME}" --timeout="${TIMEOUT}"
revision="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.metadata.annotations.deployment\.kubernetes\.io/revision}')"
printf 'rollback_status=passed namespace=%s deployment=%s revision=%s\n' \
  "${NAMESPACE}" "${NAME}" "${revision:-unknown}"

