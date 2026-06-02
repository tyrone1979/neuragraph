#!/usr/bin/env bash
# Stop processes listening on NeuraGraph ports (5001 Flask, 5002+ sandboxes).
set -euo pipefail

PORTS=(5001 5002 5003)

kill_port() {
  local port="$1"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti:"${port}" 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    return 0
  elif command -v ss >/dev/null 2>&1; then
    pids="$(ss -lptn "sport = :${port}" 2>/dev/null | grep -oP 'pid=\K[0-9]+' || true)"
  fi

  if [[ -n "${pids}" ]]; then
    echo "  Stopping port ${port}: PID(s) ${pids}"
    # shellcheck disable=SC2086
    kill -9 ${pids} 2>/dev/null || true
  fi
}

for port in "${PORTS[@]}"; do
  kill_port "${port}"
done
