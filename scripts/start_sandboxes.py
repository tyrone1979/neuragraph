"""CLI: start all enabled plugin sandboxes (used by start.ps1 / tests)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugin.sandbox_process import start_all_sandboxes

if __name__ == "__main__":
    procs = start_all_sandboxes()
    if not procs:
        sys.exit(1)
    print(f"Started {len(procs)} sandbox(es). Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        from plugin.sandbox_process import stop_processes

        stop_processes(procs)
