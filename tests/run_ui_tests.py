"""
graph.html UI tests — Playwright

Covers visual editor: Dify-style nodes, property panel, zoom toolbar, mouse-wheel zoom,
context menu, drag-drop branch/loop/subgraph, test modal, demo workflow.

Prerequisites (in project venv recommended):
  .\\venv\\Scripts\\pip install -r tests\\requirements-ui.txt
  .\\venv\\Scripts\\python.exe -m playwright install chromium

Usage:
  python tests/run_ui_tests.py
  # Auto-prefers .\\venv\\Scripts\\python.exe when present
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:5001"
SCREENSHOTS = ROOT / "tests" / "screenshots"


def resolve_python() -> Path:
    """Prefer project venv interpreter over whatever launched this script."""
    if sys.platform == "win32":
        candidates = [
            ROOT / "venv" / "Scripts" / "python.exe",
            ROOT / ".venv" / "Scripts" / "python.exe",
        ]
    else:
        candidates = [
            ROOT / "venv" / "bin" / "python",
            ROOT / ".venv" / "bin" / "python",
        ]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return Path(sys.executable).resolve()


PYTHON = resolve_python()


def ensure_playwright(python: Path) -> None:
    try:
        subprocess.run(
            [str(python), "-c", "import playwright"],
            check=True,
            capture_output=True,
            cwd=str(ROOT),
        )
    except subprocess.CalledProcessError:
        print("[ERROR] Playwright is not installed for:", python)
        print("  Run:")
        if sys.platform == "win32":
            print(r"    .\venv\Scripts\pip install -r tests\requirements-ui.txt")
            print(r"    .\venv\Scripts\python.exe -m playwright install chromium")
        else:
            print("    ./venv/bin/pip install -r tests/requirements-ui.txt")
            print("    ./venv/bin/python -m playwright install chromium")
        sys.exit(1)


def start_server(python: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.Popen(
        [str(python), "-m", "ui.app"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    import urllib.request

    for _ in range(40):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"{BASE}/", timeout=2)
            print("[OK] Server started")
            return proc
        except Exception:
            pass
    proc.terminate()
    raise RuntimeError("Server did not start")


def stop_server(proc):
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    os.chdir(str(ROOT))
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    using_venv = "venv" in PYTHON.parts or ".venv" in PYTHON.parts
    print(f"Python: {PYTHON}" + (" (project venv)" if using_venv else " (system)"))
    ensure_playwright(PYTHON)

    print("Starting server...")
    server = start_server(PYTHON)
    exit_code = 1
    try:
        test_path = ROOT / "tests" / "_test_runner_standalone.py"
        result = subprocess.run(
            [str(PYTHON), str(test_path), BASE, str(SCREENSHOTS.resolve())],
            cwd=str(ROOT),
            timeout=300,
        )
        exit_code = result.returncode
        print(f"\nTest runner exit code: {exit_code}")
    finally:
        stop_server(server)
        print("Server stopped.")
    sys.exit(exit_code)
