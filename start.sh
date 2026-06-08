#!/usr/bin/env bash
# NeuraGraph — start plugin sandboxes + Flask UI (Linux/macOS).
# Usage: chmod +x start.sh && ./start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

if [[ -f "${ROOT}/venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT}/venv/bin/activate"
elif [[ -f "${ROOT}/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT}/.venv/bin/activate"
else
  echo "[WARN] No venv found at venv/ or .venv/ — using current python"
fi

export PYTHONPATH="${ROOT}"
export PLUGIN_SANDBOX=1

PYTHON="${PYTHON:-python3}"
if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  PYTHON=python
fi

echo "========================================"
echo "  NeuraGraph - AI Workflow Platform"
echo "========================================"
echo ""

echo "[1/3] Freeing ports 5001 / 5002 ..."
bash "${ROOT}/scripts/kill_ports.sh" || true
sleep 2

SANDBOX_WATCHER=""
cleanup() {
  if [[ -n "${SANDBOX_WATCHER}" ]]; then
    kill "${SANDBOX_WATCHER}" 2>/dev/null || true
    wait "${SANDBOX_WATCHER}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[2/3] Starting plugin sandboxes (meta/plugins_sandbox.json) ..."
export NEURAGRAPH_ROOT="${ROOT}"
"${PYTHON}" -u -c "
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(os.environ['NEURAGRAPH_ROOT']).resolve()
sys.path.insert(0, str(ROOT))
from plugin.sandbox_process import start_all_sandboxes, stop_processes

procs = start_all_sandboxes()
if not procs:
    print('[WARN] No sandboxes started — check sandbox/*/venv (see sandbox/setup_venv.sh or sandbox/setup_venv.ps1)')

def _stop(*_):
    stop_processes(procs)
    sys.exit(0)

signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)
while True:
    time.sleep(60)
" &
SANDBOX_WATCHER=$!
sleep 4

echo ""
echo "[3/3] Starting Flask http://127.0.0.1:5001"
echo "      Open http://localhost:5001 in your browser"
echo ""

exec "${PYTHON}" -m ui.app
