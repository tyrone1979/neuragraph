#!/usr/bin/env bash
# Create / refresh a named plugin sandbox venv.
# Usage: ./sandbox/setup_venv.sh [name]
#        ./sandbox/setup_venv.sh flair
#        ./sandbox/setup_venv.sh custom
set -euo pipefail

NAME="${1:-flair}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MANIFEST="${ROOT}/meta/plugins_sandbox.json"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "[sandbox] manifest not found: ${MANIFEST}" >&2
  exit 1
fi

if ! read -r VENV_REL PORT ENTRY < <(python3 -c "
import json, sys
from pathlib import Path
m = json.loads(Path('${MANIFEST}').read_text(encoding='utf-8'))
cfg = m.get('sandboxes', {}).get('${NAME}')
if not cfg:
    sys.exit(2)
print(cfg['venv'], cfg['port'], cfg['entry'])
" 2>/dev/null); then
  echo "[sandbox] Unknown sandbox '${NAME}' in meta/plugins_sandbox.json" >&2
  exit 1
fi

SANDBOX_DIR="${ROOT}/sandbox/${NAME}"
VENV_DIR="${ROOT}/${VENV_REL}"
REQ_FILE="${SANDBOX_DIR}/requirements.txt"
SANDBOX_PY="${VENV_DIR}/bin/python"

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "[sandbox] Missing ${REQ_FILE}" >&2
  exit 1
fi

# Migrate legacy sandbox/venv -> sandbox/flair/venv
if [[ "${NAME}" == "flair" ]]; then
  LEGACY_VENV="${ROOT}/sandbox/venv"
  if [[ -d "${LEGACY_VENV}" && ! -d "${VENV_DIR}" ]]; then
    echo "[sandbox:flair] Moving legacy sandbox/venv -> sandbox/flair/venv ..."
    mv "${LEGACY_VENV}" "${VENV_DIR}"
  fi
fi

pick_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    echo python3.12
  elif command -v python3.11 >/dev/null 2>&1; then
    echo python3.11
  elif command -v python3 >/dev/null 2>&1; then
    echo python3
  else
    echo python3
  fi
}

if [[ ! -x "${SANDBOX_PY}" ]]; then
  PY_BOOT="$(pick_python)"
  echo "[sandbox:${NAME}] Creating venv at ${VENV_DIR} ..."
  "${PY_BOOT}" -m venv "${VENV_DIR}"
fi

echo "[sandbox:${NAME}] pip install ..."
"${SANDBOX_PY}" -m pip install -U pip
"${SANDBOX_PY}" -m pip install -r "${REQ_FILE}"

if [[ "${NAME}" == "flair" ]]; then
  echo "[sandbox:flair] Installing torch CPU ..."
  "${SANDBOX_PY}" -m pip install "torch==2.6.0+cpu" --index-url https://download.pytorch.org/whl/cpu
fi

echo "[sandbox:${NAME}] Verify imports ..."
if [[ "${NAME}" == "flair" ]]; then
  "${SANDBOX_PY}" -c "import torch; import flair; print('torch', torch.__version__)"
else
  "${SANDBOX_PY}" -c "print('venv ok')"
fi

echo "[sandbox:${NAME}] Done. Port ${PORT}, entry ${ENTRY}"
