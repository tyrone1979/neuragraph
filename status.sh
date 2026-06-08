#!/usr/bin/env bash
# Check NeuraGraph background process status.
# Usage: ./status.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${ROOT}/.pids"
LOG_DIR="${ROOT}/logs"

echo "========================================"
echo "  NeuraGraph Status"
echo "========================================"

_check() {
  local pidfile="$1"
  local label="$2"
  if [[ ! -f "${pidfile}" ]]; then
    printf "  %-25s  NOT RUNNING\n" "${label}"
    return
  fi
  local pid
  pid="$(cat "${pidfile}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    printf "  %-25s  STALE PID\n" "${label}"
    return
  fi
  if kill -0 "${pid}" 2>/dev/null; then
    printf "  %-25s  RUNNING  (PID %s)\n" "${label}" "${pid}"
  else
    printf "  %-25s  DEAD     (PID %s — stale file)\n" "${label}" "${pid}"
  fi
}

printf "\n"
_check "${PID_DIR}/flask.pid" "Flask (port 5001)"

for pidfile in "${PID_DIR}"/sandbox_*.pid; do
  if [[ -f "${pidfile}" ]]; then
    name="$(basename "${pidfile}" .pid)"
    _check "${pidfile}" "${name}"
  fi
done

printf "\n"
echo "  Logs: ${LOG_DIR}/"
echo "  Stop: ./stop.sh"
echo ""
