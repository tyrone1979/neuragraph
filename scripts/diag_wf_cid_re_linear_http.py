#!/usr/bin/env python3
"""HTTP SSE diagnostic for wf_cid_re_llm_linear (fixed query JSON encoding)."""
from __future__ import annotations

import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui_tests.utils.graph_workflow_json_utils import graph_run_params_for_query  # noqa: E402

BASE = "http://127.0.0.1:5001"
GID = "wf_cid_re_llm_linear"


def main() -> int:
    q = graph_run_params_for_query(GID)
    url = f"{BASE}/stream/test?{urllib.parse.urlencode({'graphId': GID, **q})}"
    print(f"GET {url[:120]}...", flush=True)
    t0 = time.perf_counter()
    buf = ""
    with urllib.request.urlopen(url) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace")
            if line.startswith("data: "):
                payload = line[6:].replace("\\n", "\n")
                buf += payload
                print(f"[{time.perf_counter() - t0:6.1f}s] {payload[:200]}", flush=True)
            if "[DONE]" in line:
                print(f"[{time.perf_counter() - t0:6.1f}s] [DONE]", flush=True)
                break
    print(f"total {time.perf_counter() - t0:.1f}s, buf len={len(buf)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
