#!/usr/bin/env python3
"""Capture cid_* 04_results / 05_report screenshots for latest or new NER experiment."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PLUGIN_SANDBOX", "1")
os.environ.setdefault("PLUGIN_SERVER_URL", "http://127.0.0.1:5002")

from playwright.sync_api import sync_playwright

from ui_tests import cid_experiment_ui_test as cid
from ui_tests.common import goto

SCREENSHOTS = ROOT / "ui_tests" / "screenshots"
BASE = "http://127.0.0.1:5001"


def main():
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    cid.ensure_cid_dataset(ROOT / "tests")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        exp_id = cid._run_experiment_ui(
            page,
            BASE,
            str(SCREENSHOTS),
            ROOT / "tests",
            cid.NER_RUNNER,
            "CID NER Eval (LLM) (wf_cid_ner_llm_eval) - Workflow",
            "cid_ner_",
        )
        print("NER exp_id:", exp_id)
        browser.close()


if __name__ == "__main__":
    main()
