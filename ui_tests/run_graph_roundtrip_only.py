"""Run G1–G3 only (no G4 SSE)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from playwright.sync_api import sync_playwright

from ui_tests import common, graph_roundtrip_test
from ui_tests.graph_utils import ensure_backup, restore_all_graphs
from ui_tests.run_tests import SCREENSHOTS, start_plugin_servers, start_server, stop_server

BASE = "http://127.0.0.1:5001"


def main():
    os.environ.setdefault("PLUGIN_SANDBOX", "1")
    os.environ.setdefault("PLUGIN_SERVER_URL", "http://127.0.0.1:5002")
    plugin_procs = start_plugin_servers() or []
    server = start_server()
    code = 1
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
            ctx.set_extra_http_headers({"Cache-Control": "no-cache", "Pragma": "no-cache"})
            page = ctx.new_page()
            common.reset_results()
            ensure_backup()
            try:
                graph_roundtrip_test.run(page, BASE, str(SCREENSHOTS), ROOT / "tests")
            finally:
                restore_all_graphs()
            code = common.write_results(str(SCREENSHOTS))
            browser.close()
    finally:
        stop_server(server)
        from plugin.sandbox_process import stop_processes

        stop_processes(plugin_procs)
    sys.exit(code)


if __name__ == "__main__":
    main()
