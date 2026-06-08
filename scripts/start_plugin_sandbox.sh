#!/usr/bin/env bash
# Start one named sandbox (see meta/plugins_sandbox.json).
# Usage: ./scripts/start_plugin_sandbox.sh [name] [-b|--background]
#   -b  run in background (survive terminal close)
set -euo pipefail

BACKGROUND=0
NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -b|--background) BACKGROUND=1; shift ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *)  NAME="$1"; shift ;;
  esac
done

NAME="${NAME:-flair}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MANIFEST="${ROOT}/meta/plugins_sandbox.json"
if ! read -r VENV_REL PORT ENTRY < <("${PYTHON:-python3}" -c "
import json, sys
from pathlib import Path
m = json.loads(Path('${MANIFEST}').read_text(encoding='utf-8'))
cfg = m.get('sandboxes', {}).get('${NAME}')
if not cfg:
    sys.exit(2)
print(cfg['venv'], cfg['port'], cfg['entry'])
" 2>/dev/null); then
  echo "Unknown sandbox: ${NAME}" >&2
  exit 1
fi

VENV_PY="${ROOT}/${VENV_REL}/bin/python"
ENTRY="${ROOT}/${ENTRY}"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "Run: ./sandbox/setup_venv.sh ${NAME}" >&2
  exit 1
fi

export PYTHONPATH="${ROOT}"
export SANDBOX_ID="${NAME}"
export PLUGIN_SERVER_PORT="${PORT}"

if [[ "${BACKGROUND}" -eq 1 ]]; then
  PID_DIR="${ROOT}/.pids"
  LOG_DIR="${ROOT}/logs"
  mkdir -p "${PID_DIR}" "${LOG_DIR}"

  nohup "${VENV_PY}" "${ENTRY}" > "${LOG_DIR}/sandbox_${NAME}.out" 2>&1 &
  PID=$!
  echo "${PID}" > "${PID_DIR}/sandbox_${NAME}.pid"
  echo "[OK] Sandbox '${NAME}' on port ${PORT} (PID ${PID})"
  echo "     Log: ${LOG_DIR}/sandbox_${NAME}.out"
else
  echo "Starting sandbox '${NAME}' on port ${PORT}..."
  exec "${VENV_PY}" "${ENTRY}"
fi
