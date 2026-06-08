#!/usr/bin/env bash
# NeuraGraph — start plugin sandboxes + Flask UI in background.
# Close the terminal safely; all processes keep running.
# Usage: ./start.sh          start all
#        ./stop.sh           stop all
#        ./status.sh         check running status
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

PID_DIR="${ROOT}/.pids"
LOG_DIR="${ROOT}/logs"
mkdir -p "${PID_DIR}" "${LOG_DIR}"

# ---------- venv ----------
if [[ -f "${ROOT}/.venv/bin/activate" ]]; then
  source "${ROOT}/.venv/bin/activate"
elif [[ -f "${ROOT}/venv/bin/activate" ]]; then
  source "${ROOT}/venv/bin/activate"
else
  echo "[WARN] No venv at venv/ or .venv/ — using system python"
fi

export PYTHONPATH="${ROOT}"
export PLUGIN_SANDBOX=1

PYTHON="${PYTHON:-python3}"
if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  PYTHON=python
fi

echo "========================================"
echo "  NeuraGraph  (background mode)"
echo "========================================"
echo ""

# ---------- stop old instances ----------
echo "[1/3] Stopping old instances ..."

bash "${ROOT}/scripts/kill_ports.sh" 2>/dev/null || true

for pidfile in "${PID_DIR}"/flask.pid "${PID_DIR}"/sandbox_*.pid; do
  if [[ -f "${pidfile}" ]]; then
    pid="$(cat "${pidfile}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]]; then
      kill "${pid}" 2>/dev/null || true
    fi
    rm -f "${pidfile}"
  fi
done

sleep 1

# ---------- sandboxes ----------
echo "[2/3] Starting plugin sandboxes ..."

"${PYTHON}" -u -c "
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(os.environ.get('NEURAGRAPH_ROOT', '${ROOT}')).resolve()
sys.path.insert(0, str(ROOT))
from plugin.sandbox_manifest import list_sandboxes

PID_DIR = ROOT / '.pids'
LOG_DIR = ROOT / 'logs'
PID_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

started = []

for spec in list_sandboxes():
    py = spec.venv_python()
    if not py.is_file():
        print(f'[WARN] Sandbox {spec.id}: venv missing — run ./sandbox/setup_venv.sh {spec.id}')
        continue
    if not spec.entry.is_file():
        print(f'[WARN] Sandbox {spec.id}: entry missing {spec.entry}')
        continue

    log_file = LOG_DIR / f'sandbox_{spec.id}.out'
    pid_file = PID_DIR / f'sandbox_{spec.id}.pid'

    env = os.environ.copy()
    env['SANDBOX_ID'] = spec.id
    env['PLUGIN_SERVER_PORT'] = str(spec.port)

    with open(log_file, 'w') as f_out, open(pid_file, 'w') as f_pid:
        proc = subprocess.Popen(
            [str(py), str(spec.entry)],
            env=env, cwd=str(ROOT),
            stdout=f_out, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        f_pid.write(str(proc.pid))

    # Wait for health check
    import urllib.request
    url = f'{spec.url}/health'
    ok = False
    for _ in range(40):
        time.sleep(0.5)
        if proc.poll() is not None:
            print(f'[FAIL] Sandbox {spec.id} exited early (PID {proc.pid})')
            break
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    ok = True
                    break
        except Exception:
            pass
    if ok:
        print(f'[OK] Sandbox {spec.id} on port {spec.port} (PID {proc.pid})')
        started.append(proc.pid)
    else:
        print(f'[WARN] Sandbox {spec.id} health check timeout — check logs/sandbox_{spec.id}.out')

if not started:
    print('[WARN] No sandboxes started')
else:
    print(f'       Started {len(started)} sandbox(es), PID(s): {\" \".join(str(p) for p in started)}')
" &
SANDBOX_PID=$!

# Wait for sandbox startup to finish (not forever — the Python script handles health checks)
wait "${SANDBOX_PID}" 2>/dev/null || true

sleep 1

# ---------- Flask ----------
echo ""
echo "[3/3] Starting Flask on http://127.0.0.1:5001"

nohup "${PYTHON}" -m ui.app > "${LOG_DIR}/flask.out" 2>&1 &
FLASK_PID=$!
echo "${FLASK_PID}" > "${PID_DIR}/flask.pid"

sleep 2

# Verify Flask started
if kill -0 "${FLASK_PID}" 2>/dev/null; then
  echo "       PID: ${FLASK_PID}"
  echo "       Log: ${LOG_DIR}/flask.out"
  echo ""
  echo "========================================"
  echo "  All processes running in background"
  echo "  Open:  http://localhost:5001"
  echo "  Stop:  ./stop.sh"
  echo "  Check: ./status.sh"
  echo "========================================"
else
  echo "[FAIL] Flask failed to start — check logs/flask.out"
  exit 1
fi
