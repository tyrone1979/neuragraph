#!/usr/bin/env bash
# NeuraGraph — terminal chat (Linux/macOS). Mirrors chat.bat.
# Usage: chmod +x chat.sh && ./chat.sh
#        ./chat.sh --llm deepseek
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

if [[ -f "${ROOT}/venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT}/venv/bin/activate"
elif [[ -f "${ROOT}/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT}/.venv/bin/activate"
fi

export PYTHONPATH="${ROOT}"
export PLUGIN_SANDBOX=1

PYTHON="${PYTHON:-python3}"
if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  PYTHON=python
fi

FLAIR_PORT=5002
FLAIR_HEALTH="http://127.0.0.1:${FLAIR_PORT}/health"

check_health() {
  curl -sf "${FLAIR_HEALTH}" >/dev/null 2>&1
}

start_flair_sandbox() {
  local py="${ROOT}/sandbox/flair/venv/bin/python"
  local entry="${ROOT}/sandbox/flair/plugin_server.py"
  if [[ ! -x "${py}" ]]; then
    echo "[sandbox] flair venv not found at sandbox/flair/venv"
    echo "          Create it: python3 -m venv sandbox/flair/venv && pip install -r sandbox/flair/requirements.txt"
    return 1
  fi
  echo "[sandbox] Starting flair on port ${FLAIR_PORT} ..."
  (
    export PYTHONPATH="${ROOT}"
    export SANDBOX_ID=flair
    export PLUGIN_SERVER_PORT="${FLAIR_PORT}"
    cd "${ROOT}"
    exec "${py}" "${entry}"
  ) &
  local i
  for i in $(seq 1 20); do
    if check_health; then
      echo "[sandbox] flair is ready."
      return 0
    fi
    sleep 0.5
  done
  echo "[sandbox] flair did not respond on ${FLAIR_HEALTH}"
  return 1
}

echo "Checking flair sandbox (${FLAIR_HEALTH}) ..."
if check_health; then
  echo "[sandbox] flair already running."
else
  start_flair_sandbox || true
fi

ARGS=("$@")
if [[ ${#ARGS[@]} -eq 0 ]]; then
  ARGS=(--llm deepseek)
fi

echo "Starting NeuraGraph terminal chat ..."
echo "${PYTHON} chat.py ${ARGS[*]}"
exec "${PYTHON}" chat.py "${ARGS[@]}"
