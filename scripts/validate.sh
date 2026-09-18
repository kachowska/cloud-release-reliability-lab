#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  printf 'error: Python executable not found: %s\n' "${PYTHON_BIN}" >&2
  exit 127
fi

cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" scripts/collect_evidence.py "$@"

