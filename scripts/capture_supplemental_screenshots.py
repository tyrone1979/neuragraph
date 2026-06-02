"""Capture supplemental screenshots (versions modals, wizard tabs)."""

from __future__ import annotations

import glob
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5001"
OUT = Path("doc/images")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(f"{BASE}/graph/", wait_until="domcontentloaded")
        time.sleep(2)
        btn = page.locator(".wf-versions-badge").first
        if btn.count():
            btn.click()
            time.sleep(1)
            page.screenshot(path=str(OUT / "page_graph_versions_modal.png"))
            print("graph versions ok")

        for path, out_name, sel in [
            ("/tools/", "page_tool_versions_modal", ".entity-versions-badge, .wf-versions-badge"),
            ("/agents/", "page_agent_versions_modal", ".entity-versions-badge, .wf-versions-badge"),
        ]:
            page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
            time.sleep(2)
            badge = page.locator(sel).first
            if badge.count():
                badge.click()
                time.sleep(1)
                page.screenshot(path=str(OUT / f"{out_name}.png"))
                print(f"{out_name} ok")

        exp_id = None
        for f in sorted(glob.glob("meta/exps/*.json"), key=os.path.getmtime, reverse=True)[:30]:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("status") in ("completed", "running") or data.get("progress"):
                exp_id = data.get("exp_id") or Path(f).stem
                break

        if exp_id:
            page.goto(f"{BASE}/exp/{exp_id}", wait_until="domcontentloaded")
            time.sleep(2)
            for tab, name in [
                ("baseline", "page_exp_wizard_baseline"),
                ("tuning", "page_exp_wizard_tuning"),
                ("final", "page_exp_wizard_final"),
            ]:
                page.evaluate(
                    """(tabId) => {
                        const btn = document.getElementById('wizard-tab-btn-' + tabId);
                        if (btn) { btn.disabled = false; btn.click(); }
                    }""",
                    tab,
                )
                time.sleep(0.8)
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
                print(f"{name} ok")

        page.goto(f"{BASE}/tools/", wait_until="domcontentloaded")
        link = page.locator('a[href*="/tools/"][href*="/edit"]').first
        if link.count():
            link.click()
            time.sleep(1.5)
            page.screenshot(path=str(OUT / "page_tools_edit.png"), full_page=True)
            print("tools edit ok")

        browser.close()


if __name__ == "__main__":
    main()
