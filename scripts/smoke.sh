#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${1:-${RELEASE_BASE_URL:-http://127.0.0.1:8080}}"
EXPECTED_VERSION="${EXPECTED_VERSION:-}"
EXPECTED_COMMIT_SHA="${EXPECTED_COMMIT_SHA:-}"
CURL_BIN="${CURL_BIN:-curl}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TIMEOUT_SECONDS="${SMOKE_TIMEOUT_SECONDS:-30}"

for command_name in "${CURL_BIN}" "${PYTHON_BIN}"; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    printf 'error: required command not found: %s\n' "${command_name}" >&2
    exit 127
  fi
done

TMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "${TMP_DIR}"' EXIT

deadline=$((SECONDS + TIMEOUT_SECONDS))
until "${CURL_BIN}" --silent --show-error --fail --max-time 3 \
  "${BASE_URL}/health/live" --output "${TMP_DIR}/live.json"; do
  if (( SECONDS >= deadline )); then
    printf 'error: service did not become live within %ss at %s\n' "${TIMEOUT_SECONDS}" "${BASE_URL}" >&2
    exit 1
  fi
  sleep 1
done

"${CURL_BIN}" --silent --show-error --fail --max-time 3 \
  "${BASE_URL}/health/ready" --output "${TMP_DIR}/ready.json"
"${CURL_BIN}" --silent --show-error --fail --max-time 3 \
  "${BASE_URL}/version" --output "${TMP_DIR}/version.json"
"${CURL_BIN}" --silent --show-error --fail --max-time 3 \
  "${BASE_URL}/metrics" --output "${TMP_DIR}/metrics.txt"

"${PYTHON_BIN}" - "${TMP_DIR}" "${EXPECTED_VERSION}" "${EXPECTED_COMMIT_SHA}" <<'PY'
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
expected_version = sys.argv[2]
expected_commit = sys.argv[3]

live = json.loads((directory / "live.json").read_text(encoding="utf-8"))
ready = json.loads((directory / "ready.json").read_text(encoding="utf-8"))
version = json.loads((directory / "version.json").read_text(encoding="utf-8"))
metrics = (directory / "metrics.txt").read_text(encoding="utf-8")

assert live == {"status": "live"}, live
assert ready == {"status": "ready"}, ready
assert {"service", "version", "commit_sha", "environment"} <= version.keys(), version
if expected_version:
    assert version["version"] == expected_version, version
if expected_commit:
    assert version["commit_sha"] == expected_commit, version
assert "# TYPE release_service_info gauge" in metrics
assert "release_service_ready 1" in metrics
PY

printf 'smoke_status=passed endpoints_checked=4 base_url=%s\n' "${BASE_URL}"

