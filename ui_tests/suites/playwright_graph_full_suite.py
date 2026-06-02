"""
Full graph suite for one workflow per family (highest version) under meta/graphs/:

  G1  Backup all graphs → clear meta/graphs
  G2  UI editor round-trip (inject, save, JSON + canvas diff) per graph
  G3  Branch graphs with ≥3 conditions (JSON + optional UI snapshot)
  G4  SSE /stream/test run per graph (payload from tests/<id>/*.csv when present)

Restores meta/graphs from backup when finished (see run()).
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.graph_workflow_json_utils import (
    ROOT,
    backup_graphs,
    branch_nodes_with_min_conditions,
    delete_all_graphs,
    discover_graph_ids,
    graph_ids_for_testing,
    ensure_backup,
    graph_diff,
    graph_diff_canvas,
    graph_run_params,
    graph_run_timeout,
    list_graph_ids,
    load_graph_json,
    restore_all_graphs,
)

# Representative graphs for post-run UI test-modal screenshots (not all 40+).
SNAPSHOT_GRAPH_IDS = frozenset(
    {
        "wf_doc_re_nested_branch",
        "wf_doc_ner_flair_eval",
        "wf_cid_re_branch",
        "wf_re_pubtator_eval",
        "sg_ner_flair_sent",
    }
)


def _safe_accept_dialog(dialog) -> None:
    """Auto-dismiss alerts; ignore races when the page is already closed."""
    try:
        dialog.accept()
    except Exception:
        pass


def _wait_editor_ready(page: Page) -> bool:
    try:
        page.wait_for_function(
            """() => typeof renderWorkflow === 'function'
                && typeof extractCanvasTopology === 'function'
                && typeof graph !== 'undefined'
                && typeof saveGraph === 'function'""",
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


def _seed_graphs_registry(page: Page, graph_ids: list[str]) -> None:
    payload = {gid: load_graph_json(gid, from_backup=True) for gid in graph_ids}
    page.evaluate(
        """(graphs) => {
            if (typeof graphsById !== 'object' || graphsById === null) graphsById = {};
            Object.keys(graphs).forEach(function(id) { graphsById[id] = graphs[id]; });
            if (!Array.isArray(allGraphs)) allGraphs = [];
            Object.keys(graphs).forEach(function(id) {
                if (!allGraphs.some(function(g) { return g && g.id === id; }))
                    allGraphs.push(graphs[id]);
            });
        }""",
        payload,
    )


def _inject_and_render(page: Page, gid: str, graph_data: dict) -> bool:
    return page.evaluate(
        """([id, data]) => {
            current = id;
            currentGraph = JSON.parse(JSON.stringify(data));
            graphBindings = JSON.parse(JSON.stringify(data.bindings || {}));
            const name = data.name || id;
            const title = document.getElementById('currentWorkflowName');
            if (title) title.textContent = name;
            else if (typeof $ !== 'undefined') $('#currentWorkflowName').text(name);
            renderWorkflow(currentGraph);
            return true;
        }""",
        [gid, graph_data],
    )


def _wait_stream_done(base: str, graph_id: str, params: dict, timeout: int) -> tuple[bool, str]:
    q = urllib.parse.urlencode({"graphId": graph_id, **params})
    url = f"{base}/stream/test?{q}"
    buf = ""
    saw_done = False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace")
                if line.startswith("data: "):
                    payload = line[6:].replace("\\n", "\n")
                    buf = (buf + payload)[-2000:]
                    low = payload.lower()
                    if "stream error" in low or '"status": "failed"' in low or '"status":"failed"' in low:
                        return False, payload[:200]
                if "[DONE]" in line:
                    saw_done = True
                    break
    except Exception as ex:
        return False, str(ex)[:200]
    if not saw_done:
        return False, buf[:200] or "no DONE"
    if "stream error" in buf.lower():
        return False, buf[:200]
    return True, "DONE"


def _run_backup_and_clear(page: Page, base: str, screenshots_dir: str, graph_ids: list[str]) -> None:
    print("\n=== G1. BACKUP (ALL GRAPHS) & CLEAR meta/graphs ===")
    ensure_backup()
    backup_graphs(force=True)
    backed = discover_graph_ids(from_backup=True)
    if backed:
        ok("G1a - Backup count", f"{len(backed)} graphs")
    else:
        fail("G1a", "empty backup")
    missing = [g for g in graph_ids if g not in backed]
    if missing:
        fail("G1a-missing", f"{len(missing)} ids not in backup: {missing[:5]}")
    removed = delete_all_graphs()
    live = list_graph_ids(from_backup=False)
    if len(live) == 0:
        ok("G1b - meta/graphs cleared", f"removed {removed}")
    else:
        fail("G1b", f"still {len(live)} files")
    try:
        shot(page, screenshots_dir, "g1_graphs_cleared")
    except Exception:
        pass


def _run_roundtrip(
    page: Page,
    base: str,
    screenshots_dir: str,
    graph_ids: list[str],
) -> None:
    print(f"\n=== G2. UI ROUND-TRIP ({len(graph_ids)} graphs) ===")
    goto(page, base, "/graph/new", 3, wait_until="domcontentloaded")
    if not _wait_editor_ready(page):
        fail("G2-setup", "visual editor not ready on /graph/new")
        return

    backed = discover_graph_ids(from_backup=True)
    try:
        _seed_graphs_registry(page, backed)
    except Exception as ex:
        fail("G2-setup", f"seed graphsById failed: {ex}")
        return

    for gid in graph_ids:
        if gid not in backed:
            fail(f"G2-{gid}", "missing backup")
            continue
        backup = load_graph_json(gid, from_backup=True)
        try:
            _inject_and_render(page, gid, backup)
        except Exception as ex:
            fail(f"G2a-{gid}", f"inject failed: {ex}")
            continue

        time.sleep(2)
        canvas = page.evaluate("() => extractCanvasTopology()")
        canvas_diff = graph_diff_canvas(backup, canvas)
        if canvas_diff:
            fail(f"G2d-{gid}", canvas_diff[:300])
        else:
            ok(f"G2d-{gid}", "canvas matches backup")

        try:
            shot(page, screenshots_dir, f"g2_editor_{gid}")
        except Exception:
            pass

        try:
            with page.expect_response(
                lambda r: "/graph/api/save" in r.url and r.request.method == "POST",
                timeout=60000,
            ) as resp:
                page.evaluate("() => saveGraph()")
            save_json = resp.value.json()
            if not save_json.get("success"):
                fail(f"G2b-{gid}", str(save_json)[:200])
                continue
        except Exception as ex:
            fail(f"G2b-{gid}", f"save failed: {ex}")
            continue

        time.sleep(0.5)
        graphs_path = ROOT / "meta" / "graphs" / f"{gid}.json"
        if not graphs_path.is_file():
            fail(f"G2b-{gid}", "file not written after save")
            continue

        saved = load_graph_json(gid, from_backup=False)
        diff = graph_diff(backup, saved)
        if diff:
            fail(f"G2c-{gid}", diff[:300])
        else:
            ok(f"G2c-{gid}", "saved JSON matches backup")

    try:
        shot(page, screenshots_dir, "g2_all_recreated")
    except Exception:
        pass


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


def _run_stream_tests(page: Page, base: str, screenshots_dir: str, graph_ids: list[str]) -> None:
    on_disk = set(list_graph_ids(from_backup=False))
    missing = [g for g in graph_ids if g not in on_disk]
    if missing:
        fail("G4-preflight", f"missing on disk: {missing[:5]}")
        return

    print(f"\n=== G4. RUN ALL GRAPHS /stream/test ({len(graph_ids)} graphs) ===")
    for gid in graph_ids:
        if gid not in on_disk:
            fail(f"G4-{gid}", "graph file missing")
            continue
        params = graph_run_params(gid)
        timeout = graph_run_timeout(gid)
        print(f"  Running {gid} (timeout={timeout}s)...")
        done, detail = _wait_stream_done(base, gid, params, timeout=timeout)
        if done:
            ok(f"G4-{gid}", "DONE")
        else:
            fail(f"G4-{gid}", detail)

    for gid in sorted(SNAPSHOT_GRAPH_IDS):
        if gid not in on_disk:
            continue
        params = graph_run_params(gid)
        try:
            goto(page, base, f"/graph/{gid}/edit", 2)
            page.evaluate(
                """(params) => {
                    if (typeof openTestModal === 'function') openTestModal();
                    const ta = document.getElementById('testInput');
                    if (ta) ta.value = JSON.stringify(params, null, 2);
                }""",
                params,
            )
            time.sleep(0.5)
            shot(page, screenshots_dir, f"g4_test_modal_{gid}")
        except Exception as ex:
            fail(f"G4-shot-{gid}", str(ex)[:100])

    try:
        goto(page, base, "/graph/", 2)
        shot(page, screenshots_dir, "g4_graph_list")
    except Exception:
        pass


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    page.context.set_extra_http_headers({"Cache-Control": "no-cache", "Pragma": "no-cache"})
    page.context.on("dialog", _safe_accept_dialog)

    all_ids = discover_graph_ids(from_backup=False)
    graph_ids = graph_ids_for_testing(from_backup=False)
    print(
        f"[graph full suite] {len(graph_ids)} workflows to test "
        f"({len(all_ids)} on disk, one per family)"
    )

    ensure_backup()
    backup_graphs(force=True)
    target_ids = graph_ids_for_testing(from_backup=True)
    if len(target_ids) < len(graph_ids):
        fail("G0-sync", f"backup {len(target_ids)} < live {len(graph_ids)}")
        target_ids = graph_ids

    try:
        _run_backup_and_clear(page, base, screenshots_dir, target_ids)
        _run_roundtrip(page, base, screenshots_dir, target_ids)
        _run_branch_checks(page, base, screenshots_dir, target_ids)
        run_ids = graph_ids_for_testing(from_backup=False)
        _run_stream_tests(page, base, screenshots_dir, run_ids or target_ids)
    finally:
        restore_all_graphs()
        print("[graph full suite] restored meta/graphs from backup")
        try:
            from ui_tests.utils.graph_suite_report import write_graph_suite_report

            report_path = write_graph_suite_report(screenshots_dir)
            print(f"[graph full suite] report: {report_path}")
        except Exception as ex:
            print(f"[graph full suite] report write failed: {ex}")
