"""
Playwright regression: all workflow graphs under meta/graphs/ (G1–G4).

  G1  Simple lifecycle + 3-level nested loops with inner branch (create → run → verify)
  G2  Open each graph editor (/graph/{id}/edit) and screenshot (g2_editor_{id}.png)
  G3  Branch graphs with ≥3 conditions (JSON + optional UI snapshot)
  G4  Test modal — each graph × 1 sample row (gold), run workflow, screenshot (g4_test_{id}_gold.png)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.utils.graph_workflow_json_utils import (
    GRAPHS,
    branch_nodes_with_min_conditions,
    discover_graph_ids,
    graph_run_cost_hint,
    graph_run_timeout,
    list_graph_ids,
)
from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.nested_loop_graph_fixtures import (
    NESTED_LOOP_TEST_INPUT,
    build_nested_loop_graphs,
    verify_nested_loop_result,
)
from ui_tests.utils.regression_helpers import (
    api_delete_json,
    api_get_json,
    api_post_json,
    build_graph_test_params,
    safe_name,
)

G1_AGENT_ID = "report_format_json"
G1_TEST_INPUT = {
    "text": "Aspirin may reduce the risk of heart disease.",
    "summary": "Aspirin may reduce heart disease risk.",
}
FAST_GRAPH_TIMEOUT = graph_run_timeout("sg_preprocess_inner")


def _g1_ids() -> tuple[str, str]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    orig = f"rg_lc_{stamp}"
    return orig, f"{orig}_copy"


def _graph_exists_on_disk(graph_id: str) -> bool:
    return (GRAPHS / f"{graph_id}.json").is_file()


def _wait_graph_on_disk(graph_id: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _graph_exists_on_disk(graph_id):
            return True
        time.sleep(0.5)
    return False


def _cleanup_g1_graphs(base: str, *graph_ids: str) -> None:
    for gid in graph_ids:
        if not gid:
            continue
        try:
            api_delete_json(f"{base.rstrip('/')}/graph/api/{gid}")
        except Exception:
            pass
        path = GRAPHS / f"{gid}.json"
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass


_g1_pending_copy_id: str | None = None


def _build_g1_workflow_in_editor(page: Page, graph_id: str, name: str) -> bool:
    payload = {
        "id": graph_id,
        "name": name,
        "agent_id": G1_AGENT_ID,
        "bindings": {
            G1_AGENT_ID: {
                "text": "{{ text }}",
                "summary": "{{ text }}",
            }
        },
    }
    return bool(
        page.evaluate(
            """(p) => {
                if (typeof renderWorkflow !== 'function') return false;
                const wf = {
                    id: p.id,
                    name: p.name,
                    description: 'Regression G1 lifecycle workflow',
                    nodes: ['START', p.agent_id, 'END'],
                    edges: [['START', p.agent_id], [p.agent_id, 'END']],
                    bindings: p.bindings,
                    flowNodes: {},
                    agentVersions: {},
                };
                renderWorkflow(wf);
                current = p.id;
                currentGraph = wf;
                const title = document.getElementById('currentWorkflowName');
                if (title) title.textContent = p.name;
                return typeof currentGraph !== 'undefined' && !!currentGraph;
            }""",
            payload,
        )
    )


def _run_workflow_test_modal(
    page: Page,
    screenshots_dir: str,
    gid: str,
    params: dict,
    *,
    shot_name: str,
    case_prefix: str,
    shot_timeout: int,
    test_timeout_ms: int,
) -> bool:
    """Run Test modal on the current editor page."""
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
        fail(case_prefix, f"timeout: {ex}")
        try:
            shot(page, screenshots_dir, shot_name, full_page=False, timeout=shot_timeout)
        except Exception:
            pass
        return False

    time.sleep(0.5)
    shot(page, screenshots_dir, shot_name, full_page=False, timeout=shot_timeout)
    output_text = page.evaluate(
        "() => (document.getElementById('testOutput') || {}).innerText || ''"
    )
    completed = "Workflow completed." in output_text or bool(
        page.evaluate("() => !!document.querySelector('#testOutput .fa-check-circle')")
    )
    if completed:
        ok(case_prefix, "completed")
        return True
    fail(case_prefix, (output_text or "no output")[:200])
    return False


def _run_g1_workflow_lifecycle(page: Page, base: str, screenshots_dir: str) -> None:
    """G1: create → save → run → copy → run copy → delete."""
    orig_id, copy_id = _g1_ids()
    name = "Regression G1 Lifecycle"
    goto_timeout = int(os.environ.get("NG_GRAPH_GOTO_TIMEOUT", "180000"))
    shot_timeout = int(os.environ.get("NG_GRAPH_SHOT_TIMEOUT", "120000"))
    test_timeout_ms = FAST_GRAPH_TIMEOUT * 1000

    global _g1_pending_copy_id
    print(f"\n=== G1. WORKFLOW LIFECYCLE ({orig_id} → {copy_id}) ===", flush=True)

    try:
        goto(page, base, "/graph/new", 2, wait_until="domcontentloaded", timeout=goto_timeout)
        if not _wait_editor_ready(page):
            fail("G1-editor", "editor not ready")
            return

        if not _build_g1_workflow_in_editor(page, orig_id, name):
            fail("G1-build", "renderWorkflow failed")
            return
        ok("G1-build", f"nodes=START,{G1_AGENT_ID},END")
        shot(page, screenshots_dir, "g1_new_editor", full_page=False, timeout=shot_timeout)

        page.locator("#saveGraphBtn").click()
        if not _wait_graph_on_disk(orig_id):
            fail("G1-save", f"{orig_id} not on disk")
            return
        ok("G1-save", orig_id)
        shot(page, screenshots_dir, "g1_saved", full_page=False, timeout=shot_timeout)

        goto(page, base, f"/graph/{orig_id}/edit", 2, wait_until="domcontentloaded", timeout=goto_timeout)
        if not _wait_editor_ready(page):
            fail("G1-run-orig", "editor not ready after save")
            return
        if not _run_workflow_test_modal(
            page,
            screenshots_dir,
            orig_id,
            dict(G1_TEST_INPUT),
            shot_name="g1_test_original",
            case_prefix=f"G1-run-{orig_id}",
            shot_timeout=shot_timeout,
            test_timeout_ms=test_timeout_ms,
        ):
            return

        goto(page, base, "/graph/", 2, wait_until="domcontentloaded", timeout=goto_timeout)
        page.wait_for_selector("#graphGrid .copy-btn", timeout=30000)
        page.locator("#searchInput").fill(orig_id)
        time.sleep(0.5)
        copy_btn = page.locator(f'.copy-btn[data-id="{orig_id}"]')
        if not copy_btn.count():
            fail("G1-copy", f"copy button missing for {orig_id}")
            return
        _g1_pending_copy_id = copy_id
        copy_btn.first.click()
        _g1_pending_copy_id = None
        if not _wait_graph_on_disk(copy_id):
            fail("G1-copy", f"{copy_id} not created")
            return
        ok("G1-copy", copy_id)
        shot(page, screenshots_dir, "g1_list_copied", full_page=False, timeout=shot_timeout)

        goto(page, base, f"/graph/{copy_id}/edit", 2, wait_until="domcontentloaded", timeout=goto_timeout)
        if not _wait_editor_ready(page):
            fail("G1-run-copy", "copy editor not ready")
            return
        if not _run_workflow_test_modal(
            page,
            screenshots_dir,
            copy_id,
            dict(G1_TEST_INPUT),
            shot_name="g1_test_copy",
            case_prefix=f"G1-run-{copy_id}",
            shot_timeout=shot_timeout,
            test_timeout_ms=test_timeout_ms,
        ):
            return

        goto(page, base, "/graph/", 2, wait_until="domcontentloaded", timeout=goto_timeout)
        page.wait_for_selector("#graphGrid .delete-btn", timeout=30000)
        for gid in (copy_id, orig_id):
            page.locator("#searchInput").fill(gid)
            time.sleep(0.5)
            del_btn = page.locator(f'.delete-btn[data-id="{gid}"]')
            if not del_btn.count():
                fail(f"G1-delete-{gid}", "delete button missing")
                continue
            del_btn.first.click()
            time.sleep(1.0)
            if _graph_exists_on_disk(gid):
                fail(f"G1-delete-{gid}", "still on disk after delete")
            else:
                ok(f"G1-delete-{gid}", "removed")

        shot(page, screenshots_dir, "g1_list_deleted", full_page=False, timeout=shot_timeout)
        try:
            data = api_get_json(f"{base.rstrip('/')}/graph/api/grouped", timeout=30)
            leftover = [
                gid
                for family in (data or [])
                for version in (family.get("versions") or [])
                if (version.get("id") or "") in (orig_id, copy_id)
            ]
            if leftover:
                fail("G1-cleanup", f"still listed: {leftover}")
            else:
                ok("G1-cleanup", "both workflows removed from list")
        except Exception as ex:
            fail("G1-cleanup", str(ex)[:120])
    finally:
        _cleanup_g1_graphs(base, copy_id, orig_id)


def _save_graph_via_api(base: str, graph_id: str, graph_def: dict) -> bool:
    payload = dict(graph_def)
    payload["id"] = graph_id
    try:
        resp = api_post_json(f"{base.rstrip('/')}/graph/api/save", payload, timeout=60)
        return bool(resp.get("success"))
    except Exception:
        return False


def _build_nested_workflow_in_editor(page: Page, graph_id: str, graph_def: dict) -> bool:
    payload = {"id": graph_id, "name": graph_def.get("name") or graph_id, "wf": graph_def}
    return bool(
        page.evaluate(
            """(p) => {
                if (typeof renderWorkflow !== 'function') return false;
                const wf = Object.assign({flowNodes: {}, bindings: {}, agentVersions: {}}, p.wf);
                wf.id = p.id;
                wf.name = p.name;
                renderWorkflow(wf);
                current = p.id;
                currentGraph = wf;
                const title = document.getElementById('currentWorkflowName');
                if (title) title.textContent = p.name;
                return true;
            }""",
            payload,
        )
    )


def _run_workflow_test_and_verify(
    page: Page,
    base: str,
    screenshots_dir: str,
    graph_id: str,
    test_input: dict,
    *,
    shot_name: str,
    case_prefix: str,
    shot_timeout: int,
    goto_timeout: int,
    test_timeout_ms: int,
) -> bool:
    goto(page, base, f"/graph/{graph_id}/edit", 2, wait_until="domcontentloaded", timeout=goto_timeout)
    if not _wait_editor_ready(page):
        fail(f"{case_prefix}-editor", "editor not ready")
        return False
    if not _run_workflow_test_modal(
        page,
        screenshots_dir,
        graph_id,
        test_input,
        shot_name=shot_name,
        case_prefix=case_prefix,
        shot_timeout=shot_timeout,
        test_timeout_ms=test_timeout_ms,
    ):
        return False

    try:
        from service.entity.graph import GraphLoader

        state = GraphLoader.load(graph_id).invoke(dict(test_input))
        good, detail = verify_nested_loop_result(state)
        if good:
            ok(f"{case_prefix}-verify", detail)
        else:
            fail(f"{case_prefix}-verify", detail)
            return False
    except Exception as ex:
        fail(f"{case_prefix}-verify", str(ex)[:200])
        return False

    ok(f"{case_prefix}-ui", "test modal completed")
    return True


def _run_g1_nested_loop_workflow(page: Page, base: str, screenshots_dir: str) -> None:
    """G1b: 3-level nested loops, innermost branch, run + verify merged state."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    graphs, ids = build_nested_loop_graphs(stamp)
    main_id = ids["main"]
    all_ids = list(ids.values())
    goto_timeout = int(os.environ.get("NG_GRAPH_GOTO_TIMEOUT", "180000"))
    shot_timeout = int(os.environ.get("NG_GRAPH_SHOT_TIMEOUT", "120000"))
    test_timeout_ms = max(FAST_GRAPH_TIMEOUT * 4, 180) * 1000

    print(f"\n=== G1b. NESTED LOOPS + BRANCH ({main_id}) ===", flush=True)

    try:
        for gid in (ids["l3_body"], ids["l2_body"], ids["l1_body"]):
            if not _save_graph_via_api(base, gid, graphs[gid]):
                fail(f"G1b-save-{gid}", "api save failed")
                return
            ok(f"G1b-save-{gid}", "subgraph saved")

        goto(page, base, "/graph/new", 2, wait_until="domcontentloaded", timeout=goto_timeout)
        if not _wait_editor_ready(page):
            fail("G1b-editor", "editor not ready")
            return

        if not _build_nested_workflow_in_editor(page, main_id, graphs[main_id]):
            fail("G1b-build", "renderWorkflow failed")
            return
        ok("G1b-build", "3-level loops + branch on canvas")
        shot(page, screenshots_dir, "g1_nested_editor", full_page=False, timeout=shot_timeout)

        page.locator("#saveGraphBtn").click()
        if not _wait_graph_on_disk(main_id):
            fail("G1b-save-main", f"{main_id} not on disk")
            return
        ok("G1b-save-main", main_id)

        if not _run_workflow_test_and_verify(
            page,
            base,
            screenshots_dir,
            main_id,
            dict(NESTED_LOOP_TEST_INPUT),
            shot_name="g1_nested_test",
            case_prefix="G1b-run",
            shot_timeout=shot_timeout,
            goto_timeout=goto_timeout,
            test_timeout_ms=test_timeout_ms,
        ):
            return

        shot(page, screenshots_dir, "g1_nested_done", full_page=False, timeout=shot_timeout)
    finally:
        _cleanup_g1_graphs(base, *all_ids)


def _run_g1_suite(page: Page, base: str, screenshots_dir: str) -> None:
    skip_simple = os.environ.get("NG_GRAPH_SKIP_G1_SIMPLE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    skip_nested = os.environ.get("NG_GRAPH_SKIP_G1_NESTED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not skip_simple:
        _run_g1_workflow_lifecycle(page, base, screenshots_dir)
    else:
        ok("G1-skip-simple", "NG_GRAPH_SKIP_G1_SIMPLE set")
    if not skip_nested:
        _run_g1_nested_loop_workflow(page, base, screenshots_dir)
    else:
        ok("G1b-skip", "NG_GRAPH_SKIP_G1_NESTED set")


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


def _g4_variants() -> list[bool]:
    """Default: one row with gold labels. Set NG_GRAPH_G4_BOTH=1 for gold + no_gold."""
    if os.environ.get("NG_GRAPH_G4_BOTH", "").strip().lower() in ("1", "true", "yes"):
        return [True, False]
    return [True]


def _run_test_modal_suite(page: Page, base: str, screenshots_dir: str, graph_ids: list[str]) -> None:
    on_disk = set(list_graph_ids(from_backup=False))
    missing = [g for g in graph_ids if g not in on_disk]
    if missing:
        fail("G4-preflight", f"missing on disk: {missing[:5]}")
        return

    variants = _g4_variants()
    total = len(graph_ids) * len(variants)
    variant_label = "gold+no_gold" if len(variants) > 1 else "1-row gold"
    print(
        f"\n=== G4. TEST MODAL — {variant_label} ({len(graph_ids)} graphs, {total} runs) ===",
        flush=True,
    )
    passed_n = 0
    failed_n = 0
    shot_timeout = int(os.environ.get("NG_GRAPH_SHOT_TIMEOUT", "120000"))
    goto_timeout = int(os.environ.get("NG_GRAPH_GOTO_TIMEOUT", "180000"))
    run_idx = 0

    for idx, gid in enumerate(graph_ids, start=1):
        if gid not in on_disk:
            failed_n += len(variants)
            fail(f"G4-{gid}", "graph file missing")
            continue

        for with_gold in variants:
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
        if (
            dialog.type == "prompt"
            and _g1_pending_copy_id
            and "Copy workflow" in (dialog.message or "")
        ):
            dialog.accept(_g1_pending_copy_id)
        else:
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

    skip_g1 = os.environ.get("NG_GRAPH_SKIP_G1", "").strip().lower() in ("1", "true", "yes")
    skip_g2 = os.environ.get("NG_GRAPH_SKIP_G2", "").strip().lower() in ("1", "true", "yes")
    skip_ui = os.environ.get("NG_GRAPH_SKIP_UI", "").strip().lower() in ("1", "true", "yes")
    skip_g4 = os.environ.get("NG_GRAPH_SKIP_G4", "").strip().lower() in ("1", "true", "yes")

    try:
        if skip_g1:
            ok("G1-skip", "NG_GRAPH_SKIP_G1 set")
        elif not _ping_server(base):
            fail("G1-preflight", "Flask not reachable")
        else:
            _run_g1_suite(page, base, screenshots_dir)
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
