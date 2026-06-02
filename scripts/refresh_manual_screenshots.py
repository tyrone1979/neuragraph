"""Capture UI screenshots for doc/MANUAL.md.

Usage (from repo root, server running on :5001):
    py -3 scripts/refresh_manual_screenshots.py
    py -3 scripts/refresh_manual_screenshots.py http://127.0.0.1:5001 doc/images
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "doc/images")
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1440, "height": 900}


def shot(page, name: str, *, full_page: bool = True, wait: float = 1.5) -> None:
    time.sleep(wait)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=full_page)
    print(f"  saved {path}")


def click_nav(page, href: str) -> None:
    page.goto(f"{BASE}{href}", timeout=60000, wait_until="domcontentloaded")


def open_chat(page) -> None:
    fab = page.locator("#floatingChatFab")
    if fab.is_visible():
        fab.click()
        time.sleep(0.5)


def main() -> None:
    print(f"Capturing screenshots from {BASE} -> {OUT.resolve()}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT)
        page = ctx.new_page()

        # ── Home & navigation ──
        click_nav(page, "/")
        shot(page, "homepage")
        shot(page, "menu")

        # ── LLMs ──
        click_nav(page, "/llms/new")
        shot(page, "page_new_llm")
        btn = page.locator("button:has-text('Test Connection'), #testConnectionBtn")
        if btn.count():
            shot(page, "btn_test_connection", full_page=False, wait=0.3)
        click_nav(page, "/")
        create_llm = page.locator("a[href='/llms/new']").first
        if create_llm.count():
            create_llm.screenshot(path=str(OUT / "btn_create_LLM.png"))

        # ── Agents ──
        click_nav(page, "/agents")
        shot(page, "page_agent_list")
        agents = page.locator("a[href*='/agents/'][href*='/edit'], .entity-card a").first
        if agents.count():
            agents.click()
            time.sleep(1.5)
            shot(page, "page_agent_left")
            # Try to detect agent type from page
            if page.locator("text=PGM").count():
                shot(page, "page_agent_pgm_left")
            if page.locator("text=SUB").count():
                shot(page, "page_agent_sub_left")
            test_btn = page.locator("button:has-text('Run Test'), #runTestBtn, #btnRunTest")
            if test_btn.count():
                test_btn.first.click()
                time.sleep(2)
                shot(page, "page_agent_test_right")
                shot(page, "page_agent_test_output_right")

        # ── Workflows ──
        click_nav(page, "/graph")
        shot(page, "page_graph_list")
        # Open versions modal if a badge exists
        ver_btn = page.locator(".version-badge, .badge-version, [data-versions]").first
        if ver_btn.count():
            ver_btn.click()
            time.sleep(0.8)
            shot(page, "page_graph_versions_modal", full_page=False)
            page.keyboard.press("Escape")
            time.sleep(0.3)
        wf_link = page.locator("a[href*='/graph/'][href*='/edit']").first
        if wf_link.count():
            wf_link.click()
            time.sleep(3)
            shot(page, "page_graph_edit_panel")
            shot(page, "page_graph_graph_panel")
            shot(page, "page_graph_subgraph")
            shot(page, "page_graph_right_panel")
            test_wf = page.locator("button:has-text('Test Workflow'), #btnTestWorkflow")
            if test_wf.count():
                test_wf.first.click()
                time.sleep(1)
                shot(page, "page_graph_graph_test", full_page=False)
                page.keyboard.press("Escape")
            node = page.evaluate("""() => {
                if (typeof graph === 'undefined' || !graph) return null;
                for (const el of graph.getElements()) {
                    const c = el.get('config');
                    if (c && c.id && c.id !== 'START' && c.id !== 'END') return el.id;
                }
                return null;
            }""")
            if node:
                page.evaluate(
                    """(nid) => { const el = graph.getCell(nid); if (el && typeof selectNode === 'function') selectNode(el); }""",
                    node,
                )
                time.sleep(0.8)
                test_agent = page.locator("button:has-text('Test Agent'), #btnTestAgent")
                if test_agent.count():
                    test_agent.first.click()
                    time.sleep(1)
                    shot(page, "page_graph_agent_test", full_page=False)
                    page.keyboard.press("Escape")

        # ── Experiments ──
        click_nav(page, "/exp")
        shot(page, "page_exp_list")
        click_nav(page, "/exp/new")
        shot(page, "page_exp_new")
        # Wizard tabs if present
        for tab_id, name in [
            ("wizard-tab-btn-baseline", "page_exp_wizard_baseline"),
            ("wizard-tab-btn-tuning", "page_exp_wizard_tuning"),
            ("wizard-tab-btn-final", "page_exp_wizard_final"),
        ]:
            tab = page.locator(f"#{tab_id}")
            if tab.count() and not tab.is_disabled():
                tab.click()
                time.sleep(0.5)
                shot(page, name, full_page=False)
        page.locator("#wizard-tab-btn-config").click()
        time.sleep(0.3)

        # Open an existing experiment if any
        click_nav(page, "/exp")
        exp_link = page.locator("a[href*='/exp/']").filter(has_not=page.locator("[href='/exp/new']")).first
        if exp_link.count():
            exp_link.click()
            time.sleep(2)
            shot(page, "page_exp_running")
            shot(page, "page_exp_completed")
            baseline_tab = page.locator("#wizard-tab-btn-baseline")
            if baseline_tab.count():
                if not baseline_tab.is_disabled():
                    baseline_tab.click()
                    time.sleep(0.5)
                    shot(page, "page_exp_report")

        # ── Datasets ──
        click_nav(page, "/testset")
        shot(page, "page_dataset_list")

        # ── Tools ──
        click_nav(page, "/tools")
        shot(page, "page_tools_list")
        tool_link = page.locator("a[href*='/tools/'][href*='/edit']").first
        if tool_link.count():
            tool_link.click()
            time.sleep(1.5)
            shot(page, "page_tools_edit")
        ver_tool = page.locator(".version-badge, [data-versions]").first
        if ver_tool.count():
            click_nav(page, "/tools")
            ver_tool.click()
            time.sleep(0.8)
            shot(page, "page_tool_versions_modal", full_page=False)
            page.keyboard.press("Escape")

        # ── Chat assistant ──
        click_nav(page, "/")
        open_chat(page)
        shot(page, "page_chat_widget", full_page=False)
        inp = page.locator("#floatingChatInput")
        if inp.count():
            inp.fill("/help")
            page.locator("#floatingChatSend").click()
            time.sleep(1.5)
            shot(page, "page_chat_help", full_page=False)

        browser.close()
    print("Done.")


if __name__ == "__main__":
    main()
