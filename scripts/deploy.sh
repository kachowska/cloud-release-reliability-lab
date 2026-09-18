#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
TF_DIR="${REPO_ROOT}/infra/kubernetes"

IMAGE="cloud-release-reliability-lab:local"
RELEASE_ID="local"
COMMIT_SHA="unknown"
NAMESPACE="release-lab"
NAME="release-status"
KUBE_CONTEXT=""
IMAGE_PULL_POLICY="IfNotPresent"
TIMEOUT="180s"
DRY_RUN=false

usage() {
  printf '%s\n' \
    'Usage: scripts/deploy.sh [options]' \
    '  --image IMAGE              container image reference' \
    '  --release-id ID            release identifier exposed by /version' \
    '  --commit-sha SHA           source revision exposed by /version' \
    '  --namespace NAME           Kubernetes namespace (default: release-lab)' \
    '  --name NAME                Deployment/Service name (default: release-status)' \
    '  --context CONTEXT          explicit kubeconfig context' \
    '  --image-pull-policy POLICY Always, IfNotPresent, or Never' \
    '  --timeout DURATION         kubectl rollout timeout (default: 180s)' \
    '  --dry-run                  validate inputs and print the execution contract'
}

while (($#)); do
  case "$1" in
    --image) IMAGE="${2:?missing value for --image}"; shift 2 ;;
    --release-id) RELEASE_ID="${2:?missing value for --release-id}"; shift 2 ;;
    --commit-sha) COMMIT_SHA="${2:?missing value for --commit-sha}"; shift 2 ;;
    --namespace) NAMESPACE="${2:?missing value for --namespace}"; shift 2 ;;
    --name) NAME="${2:?missing value for --name}"; shift 2 ;;
    --context) KUBE_CONTEXT="${2:?missing value for --context}"; shift 2 ;;
    --image-pull-policy) IMAGE_PULL_POLICY="${2:?missing value for --image-pull-policy}"; shift 2 ;;
    --timeout) TIMEOUT="${2:?missing value for --timeout}"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'error: unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! "${NAMESPACE}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
  printf 'error: invalid Kubernetes namespace: %s\n' "${NAMESPACE}" >&2
  exit 2
fi
if [[ ! "${IMAGE_PULL_POLICY}" =~ ^(Always|IfNotPresent|Never)$ ]]; then
  printf 'error: invalid image pull policy: %s\n' "${IMAGE_PULL_POLICY}" >&2
  exit 2
fi
if [[ -z "${IMAGE}" || -z "${RELEASE_ID}" || -z "${COMMIT_SHA}" ]]; then
  printf 'error: image, release ID, and commit SHA must not be blank\n' >&2
  exit 2
fi

context_args=()
terraform_context_args=()
if [[ -n "${KUBE_CONTEXT}" ]]; then
  context_args=(--context "${KUBE_CONTEXT}")
  terraform_context_args=(-var "kube_context=${KUBE_CONTEXT}")
fi

if [[ "${DRY_RUN}" == true ]]; then
  printf 'dry_run=passed\n'
  printf 'terraform_root=%s\n' "${TF_DIR}"
  printf 'target=deployment/%s namespace=%s image=%s release=%s commit=%s pull_policy=%s\n' \
    "${NAME}" "${NAMESPACE}" "${IMAGE}" "${RELEASE_ID}" "${COMMIT_SHA}" "${IMAGE_PULL_POLICY}"
  printf 'planned_steps=terraform_init,terraform_apply,kubectl_rollout_status\n'
  exit 0
fi

for command_name in terraform kubectl; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    printf 'error: required command not found: %s\n' "${command_name}" >&2
    exit 127
  fi
done

kubectl "${context_args[@]}" cluster-info >/dev/null
terraform -chdir="${TF_DIR}" init -backend=false -input=false -no-color
terraform -chdir="${TF_DIR}" apply -input=false -auto-approve -no-color \
  -var "namespace=${NAMESPACE}" \
  -var "name=${NAME}" \
  -var "image=${IMAGE}" \
  -var "image_pull_policy=${IMAGE_PULL_POLICY}" \
  -var "release_version=${RELEASE_ID}" \
  -var "commit_sha=${COMMIT_SHA}" \
  "${terraform_context_args[@]}"
kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  rollout status "deployment/${NAME}" --timeout="${TIMEOUT}"

ready_replicas="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.status.readyReplicas}')"
desired_replicas="$(kubectl "${context_args[@]}" --namespace "${NAMESPACE}" \
  get "deployment/${NAME}" -o 'jsonpath={.spec.replicas}')"
printf 'deploy_status=passed namespace=%s deployment=%s ready=%s desired=%s\n' \
  "${NAMESPACE}" "${NAME}" "${ready_replicas:-0}" "${desired_replicas:-0}"

