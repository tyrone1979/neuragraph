"""
Playwright regression: all workflow graphs under meta/graphs/ (G2–G4).

  G2  Open each graph editor (/graph/{id}/edit) and screenshot (g2_editor_{id}.png)
  G3  Branch graphs with ≥3 conditions (JSON + optional UI snapshot)
  G4  Test modal — each graph × gold / no_gold, run workflow, screenshot (g4_test_{id}_{tag}.png)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.graph_workflow_json_utils import (
    branch_nodes_with_min_conditions,
    discover_graph_ids,
    graph_run_cost_hint,
    graph_run_timeout,
    list_graph_ids,
)


from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.regression_helpers import build_graph_test_params, safe_name
from ui_tests.utils.graph_workflow_json_utils import (
    branch_nodes_with_min_conditions,
    discover_graph_ids,
    graph_run_cost_hint,
    graph_run_params,
    graph_run_timeout,
    list_graph_ids,
)


def _run_graph_test_modal(
    page: Page,
    base: str,
    screenshots_dir: str,
    gid: str,
    *,
    with_gold: bool,
    shot_timeout: int,
    goto_timeout: int,
    test_timeout_ms: int,
) -> bool:
    """Open Test modal, run workflow, screenshot result. Returns True on completion."""
    tag = "gold" if with_gold else "no_gold"
    params = build_graph_test_params(gid, with_gold=with_gold)
    shot_name = f"g4_test_{safe_name(gid)}_{tag}"

    goto(
        page,
        base,
        f"/graph/{gid}/edit",
        2,
        wait_until="domcontentloaded",
        timeout=goto_timeout,
    )
    ready = _wait_editor_ready(page)
    if not ready:
        goto(
            page,
            base,
            f"/graph/{gid}/edit",
            2,
            wait_until="domcontentloaded",
            timeout=goto_timeout,
        )
        ready = _wait_editor_ready(page)
    if not ready:
        fail(f"G4-{gid}-{tag}", "editor not ready")
        return False

    page.evaluate(
        """(payload) => {
            const ta = document.getElementById('testInput');
            if (ta) ta.value = JSON.stringify(payload, null, 2);
            const el = document.getElementById('testModal');
            if (el && typeof bootstrap !== 'undefined') {
                bootstrap.Modal.getOrCreateInstance(el).show();
            }
        }""",
        params,
    )
    page.wait_for_selector("#testModal.show, #testModal.showing", timeout=30000)
    time.sleep(0.5)

    page.locator("#runTestBtn").click()
    try:
        page.wait_for_function(
            """() => {
                const out = document.getElementById('testOutput');
                if (!out) return false;
                const text = out.innerText || '';
                if (text.includes('Workflow completed.')) return true;
                if (out.querySelector('.fa-check-circle')) return true;
                if (out.querySelector('.text-danger')) return true;
                if (out.querySelector('.text-warning')) return true;
                return false;
            }""",
            timeout=test_timeout_ms,
        )
    except Exception as ex:
        fail(f"G4-{gid}-{tag}", f"timeout: {ex}")
        try:
            shot(page, screenshots_dir, shot_name, full_page=False, timeout=shot_timeout)
        except Exception:
            pass
        return False

    time.sleep(0.5)
    try:
        page.evaluate("() => Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 1500))])")
    except Exception:
        pass
    shot(page, screenshots_dir, shot_name, full_page=False, timeout=shot_timeout)

    output_text = page.evaluate(
        "() => (document.getElementById('testOutput') || {}).innerText || ''"
    )
    completed = "Workflow completed." in output_text
    if not completed:
        completed = bool(
            page.evaluate(
                "() => !!document.querySelector('#testOutput .fa-check-circle')"
            )
        )
    if completed:
        ok(f"G4-{gid}-{tag}", "completed")
        return True
    fail(f"G4-{gid}-{tag}", (output_text or "no output")[:200])
    return False


def _run_test_modal_suite(page: Page, base: str, screenshots_dir: str, graph_ids: list[str]) -> None:
    on_disk = set(list_graph_ids(from_backup=False))
    missing = [g for g in graph_ids if g not in on_disk]
    if missing:
        fail("G4-preflight", f"missing on disk: {missing[:5]}")
        return

    total = len(graph_ids) * 2
    print(f"\n=== G4. TEST MODAL — gold + no_gold ({len(graph_ids)} graphs, {total} runs) ===", flush=True)
    passed_n = 0
    failed_n = 0
    shot_timeout = int(os.environ.get("NG_GRAPH_SHOT_TIMEOUT", "120000"))
    goto_timeout = int(os.environ.get("NG_GRAPH_GOTO_TIMEOUT", "180000"))
    run_idx = 0

    for idx, gid in enumerate(graph_ids, start=1):
        if gid not in on_disk:
            failed_n += 2
            fail(f"G4-{gid}", "graph file missing")
            continue

        for with_gold in (True, False):
            run_idx += 1
            tag = "gold" if with_gold else "no_gold"
            params = build_graph_test_params(gid, with_gold=with_gold)
            hint = graph_run_cost_hint(gid, params)
            timeout_s = graph_run_timeout(gid)
            print(f"\n{'=' * 60}", flush=True)
            print(f"G4 [{run_idx}/{total}] {gid} variant={tag} timeout={timeout_s}s", flush=True)
            if hint:
                print(f"  cost: {hint}", flush=True)
            print(f"  input: {json.dumps(params, ensure_ascii=False)[:400]}", flush=True)

            t0 = time.perf_counter()
            done = _run_graph_test_modal(
                page,
                base,
                screenshots_dir,
                gid,
                with_gold=with_gold,
                shot_timeout=shot_timeout,
                goto_timeout=goto_timeout,
                test_timeout_ms=timeout_s * 1000,
            )
            elapsed = time.perf_counter() - t0
            print(f"  elapsed: {elapsed:.1f}s verdict: {'PASS' if done else 'FAIL'}", flush=True)
            if done:
                passed_n += 1
            else:
                failed_n += 1
            print(f"  progress: {passed_n} passed, {failed_n} failed, {run_idx}/{total} done", flush=True)
            sys.stdout.flush()

    print(f"\nG4 summary: {passed_n} passed, {failed_n} failed, {total} total", flush=True)

    try:
        goto(page, base, "/graph/", 1, wait_until="domcontentloaded", timeout=goto_timeout)
        shot(page, screenshots_dir, "g4_graph_list", full_page=False, timeout=shot_timeout)
    except Exception:
        pass


def _clear_screenshots(screenshots_dir: str) -> None:
    root = Path(screenshots_dir)
    if not root.is_dir():
        return
    removed = 0
    for path in root.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    print(f"[regression-graph] cleared {removed} file(s) from {root}")


def _wait_editor_ready(page: Page) -> bool:
    try:
        page.wait_for_function(
            """() => typeof renderWorkflow === 'function'
                && typeof graph !== 'undefined'
                && typeof currentGraph !== 'undefined'""",
            timeout=90000,
        )
        page.wait_for_function(
            """() => typeof allGraphs !== 'undefined'
                && typeof agentsData !== 'undefined'
                && (Object.keys(agentsData || {}).length > 0
                    || document.querySelectorAll('#agentList .component-item').length > 0)""",
            timeout=90000,
        )
        time.sleep(2)
        return True
    except Exception as ex:
        print(f"  [debug] editor not ready: {ex}")
        return False


def _run_editor_screenshots(
    page: Page,
    base: str,
    screenshots_dir: str,
    graph_ids: list[str],
) -> None:
    print(f"\n=== G2. EDITOR SCREENSHOTS ({len(graph_ids)} graphs) ===")
    goto_timeout = int(os.environ.get("NG_GRAPH_GOTO_TIMEOUT", "180000"))
    shot_timeout = int(os.environ.get("NG_GRAPH_SHOT_TIMEOUT", "120000"))

    for idx, gid in enumerate(graph_ids, start=1):
        print(f"  G2 [{idx}/{len(graph_ids)}] {gid}", flush=True)
        try:
            goto(
                page,
                base,
                f"/graph/{gid}/edit",
                2,
                wait_until="domcontentloaded",
                timeout=goto_timeout,
            )
            ready = _wait_editor_ready(page)
            if not ready:
                goto(
                    page,
                    base,
                    f"/graph/{gid}/edit",
                    2,
                    wait_until="domcontentloaded",
                    timeout=goto_timeout,
                )
                ready = _wait_editor_ready(page)
            if not ready:
                fail(f"G2-{gid}", "editor not ready")
                continue
            loaded = page.evaluate(
                """(id) => typeof current !== 'undefined' && current === id
                    && typeof currentGraph !== 'undefined' && !!currentGraph""",
                gid,
            )
            if not loaded:
                fail(f"G2-{gid}", "graph not loaded")
                continue
            page.evaluate(
                """() => {
                    if (typeof fitToContent === 'function') fitToContent();
                }"""
            )
            time.sleep(1.5)
            shot(
                page,
                screenshots_dir,
                f"g2_editor_{gid}",
                full_page=False,
                timeout=shot_timeout,
            )
            ok(f"G2-{gid}", "screenshot")
        except Exception as ex:
            fail(f"G2-{gid}", str(ex)[:200])


def _safe_accept_dialog(dialog) -> None:
    try:
        dialog.accept()
    except Exception:
        pass


def _ping_server(base: str, timeout: int = 10) -> bool:
    try:
        urllib.request.urlopen(f"{base}/", timeout=timeout)
        return True
    except Exception:
        return False


def _run_branch_checks(page: Page, base: str, screenshots_dir: str, graph_ids: list[str]) -> None:
    print("\n=== G3. BRANCH GRAPHS (≥3 CONDITIONS) ===")
    checked = 0
    for gid in graph_ids:
        branches = branch_nodes_with_min_conditions(gid, min_conditions=3)
        if not branches:
            continue
        checked += 1
        node_id, n_conds = branches[0]
        ok(f"G3-{gid}", f"{node_id} conditions={n_conds}")
        try:
            goto(page, base, f"/graph/{gid}/edit", 2, wait_until="domcontentloaded")
            loaded = page.evaluate(
                """(id) => typeof current !== 'undefined' && current === id
                    && typeof currentGraph !== 'undefined' && !!currentGraph""",
                gid,
            )
            if loaded:
                page.evaluate(
                    """(bid) => { const n = graph.getCell(bid); if (n) selectNode(n); }""",
                    node_id,
                )
                time.sleep(0.5)
                shot(page, screenshots_dir, f"g3_branch_{gid}")
        except Exception as ex:
            fail(f"G3-ui-{gid}", str(ex)[:80])
    if checked == 0:
        ok("G3-skip", "no branch graphs with ≥3 conditions in this run")


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    page.context.set_extra_http_headers({"Cache-Control": "no-cache", "Pragma": "no-cache"})
    page.context.on("dialog", _safe_accept_dialog)

    if os.environ.get("NG_GRAPH_NO_CLEAR", "").strip().lower() not in ("1", "true", "yes"):
        _clear_screenshots(screenshots_dir)

    all_ids = discover_graph_ids(from_backup=False)
    only = (os.environ.get("NG_REGRESSION_GRAPH_ONLY") or os.environ.get("NG_GRAPH_ONLY") or "").strip()
    graph_ids = sorted(all_ids)
    if only:
        graph_ids = [only] if only in set(all_ids) else []
        if not graph_ids:
            fail("G0-graph", f"NG_GRAPH_ONLY={only!r} not found under meta/graphs")
    print(
        f"[regression-graph] {len(graph_ids)} graph(s) "
        f"({len(all_ids)} on disk total)",
        flush=True,
    )

    skip_g2 = os.environ.get("NG_GRAPH_SKIP_G2", "").strip().lower() in ("1", "true", "yes")
    skip_ui = os.environ.get("NG_GRAPH_SKIP_UI", "").strip().lower() in ("1", "true", "yes")
    skip_g4 = os.environ.get("NG_GRAPH_SKIP_G4", "").strip().lower() in ("1", "true", "yes")

    try:
        if skip_g2:
            ok("G2-skip", "NG_GRAPH_SKIP_G2 set")
        else:
            if not _ping_server(base):
                fail("G2-preflight", "Flask not reachable")
            else:
                _run_editor_screenshots(page, base, screenshots_dir, graph_ids)
        if skip_ui:
            ok("G3-skip", "NG_GRAPH_SKIP_UI set")
        else:
            _run_branch_checks(page, base, screenshots_dir, graph_ids)
        if skip_g4:
            ok("G4-skip", "NG_GRAPH_SKIP_G4 set")
        else:
            if not _ping_server(base):
                fail("G4-preflight", "Flask not reachable")
            _run_test_modal_suite(page, base, screenshots_dir, graph_ids)
    finally:
        try:
            from ui_tests.utils.graph_suite_report import write_graph_suite_report

            report_path = write_graph_suite_report(screenshots_dir, suite_label="regression-graph")
            print(f"[regression-graph] report: {report_path}")
        except Exception as ex:
            print(f"[regression-graph] report write failed: {ex}")
