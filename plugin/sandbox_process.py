"""Start/stop plugin sandbox sidecars from manifest."""
from __future__ import annotations

import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from plugin.sandbox_manifest import SandboxSpec, list_sandboxes

ROOT = Path(__file__).resolve().parent.parent


def start_sandbox(spec: SandboxSpec) -> subprocess.Popen | None:
    py = spec.venv_python()
    if not py.is_file():
        print(f"[WARN] Sandbox '{spec.id}': venv missing at {spec.venv}")
        print(f"       Windows: .\\sandbox\\setup_venv.ps1 -Name {spec.id}")
        print(f"       Linux:   python3 -m venv {spec.venv} && pip install deps for {spec.id}")
        return None
    if not spec.entry.is_file():
        print(f"[WARN] Sandbox '{spec.id}': entry missing {spec.entry}")
        return None

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["SANDBOX_ID"] = spec.id
    env["PLUGIN_SERVER_PORT"] = str(spec.port)

    proc = subprocess.Popen(
        [str(py), str(spec.entry)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"{spec.url}/health"
    for _ in range(40):
        time.sleep(0.5)
        if proc.poll() is not None:
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            print(f"[WARN] Sandbox '{spec.id}' exited: {err[-400:]}")
            return None
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print(f"[OK] Sandbox '{spec.id}' at {spec.url}")
                    return proc
        except Exception:
            pass
    print(f"[WARN] Sandbox '{spec.id}' did not respond at {url}")
    return proc


def start_all_sandboxes() -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    for spec in list_sandboxes():
        proc = start_sandbox(spec)
        if proc:
            procs.append(proc)
    return procs


def stop_processes(procs: list[Any]) -> None:
    for proc in procs or []:
        if not proc:
            continue
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
