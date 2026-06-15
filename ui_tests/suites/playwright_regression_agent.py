"""Playwright regression: all agents — UI test screenshots + mock-LLM invoke.

Timeout root causes (historical 23/67 failures):
1. Blocking alert() — Run Test saves agent (PUT) first; failures showed alert() with no
   Playwright dialog handler → page stuck until navigation timeout.
2. Server saturation — each UI Run Test = PUT /agents/api/{id} + PGM invoke; Flask dev
   server slows; subsequent page.goto timed out. Mitigation: wait until server responds
   after each PGM test, use domcontentloaded + short sleep on goto.
3. UI test wait too short — ner_flair_* / dataset builders need sandbox HTTP (>90s).
4. (Fixed earlier) full_page screenshot on long PGM process editors hung 120s.
"""
from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

from service.meta.loader import MetaLoader
from ui_tests.suites.agent_invoke_mock_llm_suite import run_all_agents, write_report
from ui_tests.utils.agent_sample_row_fixtures import write_all_agent_sample_csvs
from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.regression_helpers import all_agent_ids, safe_name

SLOW_PGM_AGENTS = frozenset(
    {
        "ner_flair_doc",
        "ner_flair_sent",
        "relation_extract_pubtator",
        "dataset_cid_tuning_build",
        "dataset_chemdisgene_build",
    }
)


def _accept_dialogs(page: Page) -> None:
    page.context.on("dialog", lambda d: d.accept())


def _ping_server(base: str, timeout: int = 8) -> bool:
    try:
        with urllib.request.urlopen(f"{base.rstrip('/')}/", timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def _wait_server_ready(base: str, timeout_s: int = 90) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _ping_server(base, timeout=5):
            return True
        time.sleep(1)
    return False


def _agent_goto(page: Page, base: str, path: str) -> None:
    sleep_s = float(os.environ.get("NG_AGENT_GOTO_SLEEP", "0.5"))
    timeout_ms = int(os.environ.get("NG_AGENT_GOTO_TIMEOUT", "180000"))
    goto(page, base, path, sleep_s, wait_until="domcontentloaded", timeout=timeout_ms)


def _ui_test_timeout_ms(agent_id: str) -> int:
    if agent_id in SLOW_PGM_AGENTS:
        return int(os.environ.get("NG_AGENT_UI_TEST_TIMEOUT_SLOW", "420")) * 1000
    return int(os.environ.get("NG_AGENT_UI_TEST_TIMEOUT", "180")) * 1000


def _shot_test_result(page: Page, screenshots_dir: str, agent_id: str) -> None:
    path = f"{screenshots_dir}/ragent_test_{safe_name(agent_id)}.png"
    timeout = int(os.environ.get("NG_AGENT_SHOT_TIMEOUT", "30000"))
    page.locator("#testResult").screenshot(path=path, timeout=timeout)


def _wait_ui_test_finished(page: Page, timeout_ms: int) -> None:
    page.wait_for_function(
        """() => {
            const out = document.getElementById('testResult');
            const btn = document.getElementById('runTestBtn');
            if (!out) return false;
            const text = out.innerText || '';
            const btnText = btn ? (btn.innerText || '') : '';
            if (text.includes('Running test') || btnText.includes('Testing') || btnText.includes('Saving')) {
                return false;
            }
            if (out.querySelector('pre')) return true;
            if (out.querySelector('.text-danger')) return true;
            return text.trim().length > 15;
        }""",
        timeout=timeout_ms,
    )


def _run_pgm_test_via_ui(
    page: Page,
    base: str,
    screenshots_dir: str,
    agent_id: str,
) -> None:
    """Select sample.csv, click Run Test (save + invoke), screenshot #testResult."""
    form_timeout = int(os.environ.get("NG_AGENT_FORM_TIMEOUT", "60000"))
    page.wait_for_selector("#datasetSelect", timeout=form_timeout)
    page.wait_for_function(
        """() => {
            const sel = document.getElementById('datasetSelect');
            if (!sel || sel.disabled) return false;
            return Array.from(sel.options).some(o => o.value === 'sample');
        }""",
        timeout=form_timeout,
    )
    page.select_option("#datasetSelect", "sample")
    page.wait_for_function(
        """() => {
            const area = document.getElementById('testInputs');
            const btn = document.getElementById('runTestBtn');
            if (!area || !btn || btn.disabled) return false;
            return !!area.querySelector('input, textarea, select');
        }""",
        timeout=form_timeout,
    )

    test_timeout_ms = _ui_test_timeout_ms(agent_id)
    page.locator("#runTestBtn").click()
    try:
        _wait_ui_test_finished(page, test_timeout_ms)
    except Exception as ex:
        try:
            _shot_test_result(page, screenshots_dir, agent_id)
        except Exception:
            pass
        raise ex

    _shot_test_result(page, screenshots_dir, agent_id)
    has_error = page.evaluate(
        "() => !!document.querySelector('#testResult .text-danger')"
    )
    if has_error:
        err = page.evaluate(
            "() => (document.querySelector('#testResult .text-danger') || {}).innerText || 'UI test failed'"
        )
        fail(f"RAGENT-test-ui-{agent_id}", str(err)[:120])
    else:
        ok(f"RAGENT-test-ui-{agent_id}", "PGM UI test completed")

    if not _wait_server_ready(base, timeout_s=int(os.environ.get("NG_AGENT_SERVER_COOLDOWN", "30"))):
        fail(f"RAGENT-server-{agent_id}", "Flask slow after PGM UI test")


def _screenshot_agent_test_panel(
    page: Page,
    base: str,
    screenshots_dir: str,
    agent_id: str,
) -> None:
    meta = MetaLoader.load("agents", agent_id) or {}
    agent_type = str(meta.get("type") or "").upper()
    if agent_type != "PGM":
        ok(f"RAGENT-test-ui-{agent_id}", "LLM: no UI test screenshot")
        return
    try:
        _run_pgm_test_via_ui(page, base, screenshots_dir, agent_id)
    except Exception as ex:
        fail(f"RAGENT-test-ui-{agent_id}", str(ex)[:120])


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    _accept_dialogs(page)
    write_all_agent_sample_csvs()
    agent_ids = all_agent_ids()
    if not agent_ids:
        fail("RAGENT-setup", "no agents under meta/agents")
        return

    only = os.environ.get("NG_REGRESSION_AGENT_ONLY", "").strip()
    if only:
        agent_ids = [a for a in agent_ids if a == only]

    print(f"\n=== RAGENT: {len(agent_ids)} agent(s) — PGM via UI Run Test ===")
    _agent_goto(page, base, "/agents/")
    shot(page, screenshots_dir, "ragent_list", full_page=False)

    edit_shot = os.environ.get("NG_AGENT_EDIT_SHOT", "").strip().lower() in ("1", "true", "yes")
    ping_every = int(os.environ.get("NG_AGENT_PING_EVERY", "5"))

    for idx, agent_id in enumerate(agent_ids, start=1):
        print(f"\n--- RAGENT [{idx}/{len(agent_ids)}] {agent_id} ---")
        if ping_every > 0 and idx % ping_every == 1 and not _ping_server(base):
            fail(f"RAGENT-ping-{agent_id}", "Flask not reachable before agent step")

        try:
            _agent_goto(page, base, f"/agents/{agent_id}/edit")
            page.wait_for_selector("#agentForm", timeout=int(os.environ.get("NG_AGENT_FORM_TIMEOUT", "60000")))
            if edit_shot:
                shot(
                    page,
                    screenshots_dir,
                    f"ragent_edit_{safe_name(agent_id)}",
                    full_page=False,
                    timeout=int(os.environ.get("NG_AGENT_SHOT_TIMEOUT", "30000")),
                )
            _screenshot_agent_test_panel(page, base, screenshots_dir, agent_id)
            ok(f"RAGENT-ui-{agent_id}", "page ok")
        except Exception as ex:
            fail(f"RAGENT-ui-{agent_id}", str(ex)[:120])

    print("\n=== RAGENT: mock-LLM batch invoke ===")
    report = run_all_agents(mock_llm=True, write_datasets=False)
    _json_path, md_path = write_report(report)
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

    _agent_goto(page, base, "/agents/")
    shot(page, screenshots_dir, "ragent_list_done", full_page=False)
