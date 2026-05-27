"""Graph test suite: backup → delete → UI recreate → diff → run workflows."""
from pathlib import Path

from playwright.sync_api import Page

from ui_tests import graph_roundtrip_test, graph_run_test
from ui_tests.graph_utils import ensure_backup, restore_all_graphs


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    from ui_tests import common

    page.context.set_extra_http_headers({"Cache-Control": "no-cache", "Pragma": "no-cache"})
    ensure_backup()
    try:
        graph_roundtrip_test.run(page, base, screenshots_dir, tests_data_dir)
        graph_run_test.run(page, base, screenshots_dir, tests_data_dir)
    finally:
        restore_all_graphs()
