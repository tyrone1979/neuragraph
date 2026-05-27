"""Template sandbox entry — copy to sandbox/<id>/plugin_server.py and set SANDBOX_ID."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("SANDBOX_ID", "custom")

from sandbox._common.server import main

if __name__ == "__main__":
    main(os.environ["SANDBOX_ID"])
