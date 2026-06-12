"""Playwright regression: all agents — UI screenshots + mock-LLM invoke."""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.suites.agent_invoke_mock_llm_suite import run_all_agents, write_report
from ui_tests.utils.agent_sample_row_fixtures import write_all_agent_sample_csvs
from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.regression_helpers import all_agent_ids, safe_name


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    write_all_agent_sample_csvs()
    agent_ids = all_agent_ids()
    if not agent_ids:
        fail("RAGENT-setup", "no agents under meta/agents")
        return

    print(f"\n=== RAGENT: {len(agent_ids)} agent(s) ===")
    goto(page, base, "/agents/", 2)
    shot(page, screenshots_dir, "ragent_list")

    only = os.environ.get("NG_REGRESSION_AGENT_ONLY", "").strip()
    if only:
        agent_ids = [a for a in agent_ids if a == only]

    for idx, agent_id in enumerate(agent_ids, start=1):
        print(f"\n--- RAGENT UI [{idx}/{len(agent_ids)}] {agent_id} ---")
        try:
            goto(page, base, f"/agents/{agent_id}/edit", 2)
            shot(page, screenshots_dir, f"ragent_edit_{safe_name(agent_id)}")
            ok(f"RAGENT-ui-{agent_id}", "edit page loaded")
        except Exception as ex:
            fail(f"RAGENT-ui-{agent_id}", str(ex)[:120])

    print("\n=== RAGENT: mock-LLM batch invoke ===")
    report = run_all_agents(mock_llm=True, write_datasets=False)
    json_path, md_path = write_report(report)
    ok("RAGENT-invoke-summary", f"{report.passed}/{report.total} pass")
    print(f"  report: {md_path}")

    for item in report.results:
        test = f"RAGENT-invoke-{item.agent_id}"
        if item.status == "pass":
            ok(test, item.message[:120])
        elif item.status == "skip":
            ok(test, f"skip: {item.message[:80]}")
        else:
            fail(test, item.message[:200])

    goto(page, base, "/agents/", 2)
    shot(page, screenshots_dir, "ragent_list_done")
