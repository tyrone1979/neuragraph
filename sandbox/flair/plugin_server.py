"""Flair sandbox sidecar. Set SANDBOX_ID=flair and PLUGIN_SERVER_PORT (default 5002)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("SANDBOX_ID", "flair")

from sandbox._common.server import main

if __name__ == "__main__":
    main("flair")
