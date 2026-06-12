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


def open_wizard_tab(page, tab_id: str, name: str, *, wait: float = 1.0) -> bool:
    tab = page.locator(f"#{tab_id}")
    if not tab.count():
        return False
    try:
        page.wait_for_function(
            f"() => {{ const b = document.getElementById('{tab_id}'); return b && !b.disabled; }}",
            timeout=8000,
        )
    except Exception:
        return False
    tab.click()
    time.sleep(wait)
    shot(page, name, full_page=False)
    return True


def find_exp_with_final_tab() -> str | None:
    root = Path(__file__).resolve().parents[1]
    for ctx_path in sorted((root / "result").glob("*/optimization_context.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            import json

            ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
            if ctx.get("optimized_test_exp_id") or ctx.get("optimized_test_report_path"):
                return ctx_path.parent.name
        except Exception:
            continue
    return None


def find_completed_exp_id() -> str | None:
    root = Path(__file__).resolve().parents[1]
    for exp_path in sorted((root / "meta" / "exps").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        exp_id = exp_path.stem
        if not (root / "result" / exp_id / "report_baseline_test.md").is_file():
            continue
        try:
            import json

            cfg = json.loads(exp_path.read_text(encoding="utf-8"))
            if str(cfg.get("status") or "").lower() == "completed":
                return exp_id
        except Exception:
            continue
    return None


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
        page.wait_for_selector("#agentGrid, .entity-card", timeout=15000)
        shot(page, "page_agent_list")
        ver_agent = page.locator(".wf-versions-badge").first
        if ver_agent.count():
            ver_agent.click()
            time.sleep(1)
            shot(page, "page_agent_versions_modal", full_page=False)
            page.keyboard.press("Escape")
            time.sleep(0.3)
        agents = page.locator("a[href*='/agents/'][href*='/edit']").first
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
        ver_btn = page.locator(".wf-versions-badge").first
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
            test_wf = page.locator("#testWorkflow, button:has-text('Test Workflow')")
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
                test_agent = page.locator("button:has-text('Test'), button:has-text('Run Test')")
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

        exp_id = find_completed_exp_id()
        if exp_id:
            click_nav(page, f"/exp/{exp_id}")
            time.sleep(2)
            shot(page, "page_exp_running")
            open_wizard_tab(page, "wizard-tab-btn-baseline", "page_exp_wizard_baseline")
            page.wait_for_function(
                """() => {
                    const el = document.getElementById('baselineReportMarkdown');
                    return el && (el.innerText || '').trim().length > 20;
                }""",
                timeout=30000,
            )
            shot(page, "page_exp_report", full_page=False)
            open_wizard_tab(page, "wizard-tab-btn-tuning", "page_exp_wizard_tuning", wait=0.8)
            if not open_wizard_tab(page, "wizard-tab-btn-final", "page_exp_wizard_final", wait=0.8):
                final_exp = find_exp_with_final_tab()
                if final_exp:
                    click_nav(page, f"/exp/{final_exp}")
                    time.sleep(2)
                    open_wizard_tab(page, "wizard-tab-btn-final", "page_exp_wizard_final", wait=0.8)
            shot(page, "page_exp_completed", full_page=False)
        else:
            exp_link = page.locator("a[href*='/exp/']").filter(has_not=page.locator("[href='/exp/new']")).first
            if exp_link.count():
                click_nav(page, "/exp")
                exp_link.click()
                time.sleep(2)
                shot(page, "page_exp_running")
                shot(page, "page_exp_completed")
                open_wizard_tab(page, "wizard-tab-btn-baseline", "page_exp_wizard_baseline")
                shot(page, "page_exp_report", full_page=False)

        # ── Datasets ──
        click_nav(page, "/testset")
        shot(page, "page_dataset_list")

        # ── Tools ──
        click_nav(page, "/tools")
        page.wait_for_selector("#toolGrid, .entity-card", timeout=15000)
        shot(page, "page_tools_list")
        tool_link = page.locator("a[href*='/tools/']:not([href='/tools/new']):not([href^='/tools/api'])").first
        if tool_link.count():
            tool_link.click()
            time.sleep(1.5)
            shot(page, "page_tools_edit")
        click_nav(page, "/tools")
        ver_tool = page.locator(".wf-versions-badge").first
        if ver_tool.count():
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
