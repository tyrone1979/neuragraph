"""Playwright regression: all callable tools — UI + /tools/api/run_tool."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from service.meta.loader import MetaLoader
from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.regression_helpers import (
    all_tool_ids,
    api_post_json,
    default_tool_inputs,
    safe_name,
)


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    tool_ids = all_tool_ids()
    if not tool_ids:
        fail("RTOOL-setup", "no tools under meta/tools")
        return

    print(f"\n=== RTOOL: {len(tool_ids)} tool(s) ===")
    goto(page, base, "/tools/", 2)
    shot(page, screenshots_dir, "rtool_list")

    for idx, tool_id in enumerate(tool_ids, start=1):
        print(f"\n--- RTOOL [{idx}/{len(tool_ids)}] {tool_id} ---")
        tool_def = MetaLoader.load("tools", tool_id) or {}
        if not tool_def:
            fail(f"RTOOL-meta-{tool_id}", "missing meta")
            continue

        try:
            goto(page, base, f"/tools/{tool_id}", 2)
            shot(page, screenshots_dir, f"rtool_form_{safe_name(tool_id)}")
            ok(f"RTOOL-ui-{tool_id}", "form loaded")
        except Exception as ex:
            fail(f"RTOOL-ui-{tool_id}", str(ex)[:120])

        inputs = default_tool_inputs({**tool_def, "id": tool_id})
        try:
            resp = api_post_json(
                f"{base.rstrip('/')}/tools/api/run_tool",
                {"tool_id": tool_id, "inputs": inputs},
                timeout=180,
            )
            if resp.get("error"):
                fail(f"RTOOL-run-{tool_id}", str(resp.get("error"))[:200])
            elif resp.get("result") is not None:
                ok(f"RTOOL-run-{tool_id}", str(resp.get("result", ""))[:120])
            else:
                fail(f"RTOOL-run-{tool_id}", str(resp)[:200])
        except Exception as ex:
            fail(f"RTOOL-run-{tool_id}", str(ex)[:200])

    goto(page, base, "/tools/", 2)
    shot(page, screenshots_dir, "rtool_list_done")
    ok("RTOOL-summary", f"visited {len(tool_ids)} tools")
