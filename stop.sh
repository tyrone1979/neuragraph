#!/usr/bin/env bash
# Stop all NeuraGraph background processes (flask + sandboxes).
# Usage: ./stop.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${ROOT}/.pids"

stopped=0

_stop_pidfile() {
  local pidfile="$1"
  local name="$2"
  if [[ ! -f "${pidfile}" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "${pidfile}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    rm -f "${pidfile}"
    return 0
  fi
  if kill -0 "${pid}" 2>/dev/null; then
    echo "  Stopping ${name} (PID ${pid}) ..."
    kill "${pid}" 2>/dev/null || true
    sleep 1
    if kill -0 "${pid}" 2>/dev/null; then
      echo "  Force-killing ${name} (PID ${pid}) ..."
      kill -9 "${pid}" 2>/dev/null || true
    fi
    stopped=$((stopped + 1))
  fi
  rm -f "${pidfile}"
}

echo "========================================"
echo "  Stopping NeuraGraph"
echo "========================================"

# Kill ports as fallback
bash "${ROOT}/scripts/kill_ports.sh" 2>/dev/null || true

# Stop by PID files
_stop_pidfile "${PID_DIR}/flask.pid" "Flask"

for pidfile in "${PID_DIR}"/sandbox_*.pid; do
  if [[ -f "${pidfile}" ]]; then
    _stop_pidfile "${pidfile}" "$(basename "${pidfile}" .pid)"
  fi
done

if [[ "${stopped}" -eq 0 ]]; then
  echo "  No running processes found."
else
  echo "  Stopped ${stopped} process(es)."
fi
