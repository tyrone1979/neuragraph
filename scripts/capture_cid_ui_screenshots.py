#!/usr/bin/env python3
"""Capture CID NER experiment screenshots via regression-exp helper."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PLUGIN_SANDBOX", "1")
os.environ.setdefault("PLUGIN_SERVER_URL", "http://127.0.0.1:5002")

from playwright.sync_api import sync_playwright

from ui_tests.utils.regression_helpers import run_graph_experiment

SCREENSHOTS = ROOT / "ui_tests" / "screenshots"
BASE = "http://127.0.0.1:5001"
NER_RUNNER = "wf_cid_ner_llm_eval"


def main():
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        exp_id = run_graph_experiment(
            page,
            BASE,
            str(SCREENSHOTS),
            NER_RUNNER,
            with_gold=True,
        )
        print("NER exp_id:", exp_id)
        browser.close()


if __name__ == "__main__":
    main()
