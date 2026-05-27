"""Quick check: /stream/run/{exp_id} finishes and writes states.json."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PLUGIN_SANDBOX", "1")
os.environ.setdefault("PLUGIN_SERVER_URL", "http://127.0.0.1:5002")

from ui_tests.cid_experiment_ui_test import (  # noqa: E402
    NER_RUNNER,
    DATASET_FILE,
    api_create_experiment,
    api_post_json,
    wait_results_file,
    wait_stream_done,
)

BASE = "http://127.0.0.1:5001"


def main():
    exp_id = api_create_experiment(BASE, NER_RUNNER, "CID NER test stream")
    print("exp_id", exp_id)
    api_post_json(f"{BASE}/exp/api/update", {"exp_id": exp_id, "status": "running", "progress": 0})
    t0 = time.time()
    ok = wait_stream_done(BASE, exp_id, timeout=600)
    print("stream DONE", ok, "elapsed", round(time.time() - t0, 1))
    ready = wait_results_file(exp_id, min_samples=2, timeout=30)
    print("states.json ready", ready)
    path = ROOT / "result" / exp_id / "states.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        print("keys", list(data.keys()))


if __name__ == "__main__":
    main()
