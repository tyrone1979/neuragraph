import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env = os.environ.copy()
env["PYTHONPATH"] = str(ROOT)
env["PLUGIN_SANDBOX"] = "1"
env["PLUGIN_SERVER_URL"] = "http://127.0.0.1:5002"

proc = subprocess.Popen(
    [
        str(ROOT / "venv" / "Scripts" / "python.exe"),
        "-c",
        "from ui.app import create_app; create_app().run("
        "host='0.0.0.0', port=5001, debug=False, threaded=True, use_reloader=False)",
    ],
    cwd=str(ROOT),
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.PIPE,
)
try:
    for _ in range(40):
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://127.0.0.1:5001/", timeout=2)
            break
        except Exception:
            pass
    else:
        err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        print("server failed", err[-500:])
        sys.exit(1)

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from plugin.sandbox_process import start_all_sandboxes

    start_all_sandboxes()
    r = subprocess.run(
        [str(ROOT / "venv" / "Scripts" / "python.exe"), str(ROOT / "scripts" / "_test_stream_batch.py")],
        cwd=str(ROOT),
        env=env,
    )
    sys.exit(r.returncode)
finally:
    proc.terminate()
