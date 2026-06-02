"""
Full graph suite for one workflow per family (highest version) under meta/graphs/:

  G1  Backup all graphs → clear meta/graphs
  G2  UI editor round-trip (inject, save, JSON + canvas diff) per graph
  G3  Branch graphs with ≥3 conditions (JSON + optional UI snapshot)
  G4  SSE /stream/test — one graph at a time, no socket timeout; judge output then next

Restores meta/graphs from backup when finished (see run()).
"""
from __future__ import annotations

import json
import os
import sys
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
    graph_run_cost_hint,
    graph_run_params,
    graph_run_params_for_query,
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


def _ping_server(base: str, timeout: int = 10) -> bool:
    try:
        urllib.request.urlopen(f"{base}/", timeout=timeout)
        return True
    except Exception:
        return False


def _judge_stream_output(saw_done: bool, buf: str) -> tuple[bool, str]:
    """Decide pass/fail from full SSE text after the stream closes."""
    if not saw_done:
        return False, "stream ended without [DONE]"
    low = buf.lower()
    if "stream error" in low:
        idx = low.index("stream error")
        return False, buf[idx : idx + 400].strip()
    if '"status": "failed"' in low or '"status":"failed"' in low:
        return False, "workflow reported status failed in stream"
    if not buf.strip():
        return False, "empty stream output"
    return True, "ok"


def _wait_stream_done(base: str, graph_id: str, query_params: dict[str, str]) -> tuple[bool, str, str]:
    """Block until [DONE] or connection error. No per-graph socket timeout. Prints each SSE chunk."""
    if not _ping_server(base):
        return False, "server not reachable before stream", ""
    q = urllib.parse.urlencode({"graphId": graph_id, **query_params})
    url = f"{base}/stream/test?{q}"
    buf = ""
    saw_done = False
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace")
                if line.startswith("data: "):
                    payload = line[6:].replace("\\n", "\n")
                    buf += payload
                    preview = payload.replace("\n", " ")[:240]
                    print(
                        f"  [{time.perf_counter() - t0:6.1f}s] sse: {preview}",
                        flush=True,
                    )
                if "[DONE]" in line:
                    saw_done = True
                    print(f"  [{time.perf_counter() - t0:6.1f}s] sse: [DONE]", flush=True)
                    break
    except Exception as ex:
        return False, str(ex)[:500], buf[-1500:]
    passed, msg = _judge_stream_output(saw_done, buf)
    return passed, msg, buf[-1500:]


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
                timeout=120000,
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

    total = len(graph_ids)
    print(f"\n=== G4. /stream/test — sequential, no timeout ({total} graphs) ===", flush=True)
    passed_n = 0
    failed_n = 0

    for idx, gid in enumerate(graph_ids, start=1):
        print(f"\n{'=' * 60}", flush=True)
        print(f"G4 [{idx}/{total}] graphId={gid}", flush=True)
        if gid not in on_disk:
            failed_n += 1
            fail(f"G4-{gid}", "graph file missing")
            print("  verdict: FAIL (missing JSON on disk)\n", flush=True)
            continue

        params = graph_run_params(gid)
        query = graph_run_params_for_query(gid)
        hint = graph_run_cost_hint(gid, params)
        print(f"  input: {json.dumps(params, ensure_ascii=False)}", flush=True)
        if hint:
            print(f"  cost: {hint}", flush=True)
        print("  running (wait until [DONE], no socket timeout)...", flush=True)

        t0 = time.perf_counter()
        done, detail, output_tail = _wait_stream_done(base, gid, query)
        elapsed = time.perf_counter() - t0

        print(f"  elapsed: {elapsed:.1f}s", flush=True)
        print(f"  verdict: {'PASS' if done else 'FAIL'} — {detail}", flush=True)
        if output_tail.strip():
            print("  output (tail):", flush=True)
            print(output_tail, flush=True)
        else:
            print("  output (tail): (empty)", flush=True)

        if done:
            passed_n += 1
            ok(f"G4-{gid}", f"ok ({elapsed:.0f}s)")
        else:
            failed_n += 1
            fail(f"G4-{gid}", detail)

        print(f"  progress: {passed_n} passed, {failed_n} failed, {idx}/{total} done", flush=True)
        sys.stdout.flush()

    print(f"\nG4 summary: {passed_n} passed, {failed_n} failed, {total} total", flush=True)

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
    only = (os.environ.get("NG_GRAPH_ONLY") or "").strip()
    graph_ids = graph_ids_for_testing(from_backup=False)
    if only:
        graph_ids = [only] if only in set(discover_graph_ids(from_backup=False)) else []
        if not graph_ids:
            fail("G0-graph", f"NG_GRAPH_ONLY={only!r} not found under meta/graphs")
    print(
        f"[graph full suite] G4 will run {len(graph_ids)} graph(s) one-by-one "
        f"({len(all_ids)} on disk total)",
        flush=True,
    )

    ensure_backup()
    backup_graphs(force=True)
    target_ids = graph_ids_for_testing(from_backup=True)
    if len(target_ids) < len(graph_ids):
        fail("G0-sync", f"backup {len(target_ids)} < live {len(graph_ids)}")
        target_ids = graph_ids

    skip_ui = os.environ.get("NG_GRAPH_SKIP_UI", "").strip().lower() in ("1", "true", "yes")

    try:
        if skip_ui:
            ok("G1-G3-skip", "NG_GRAPH_SKIP_UI set — G4 only")
        else:
            _run_backup_and_clear(page, base, screenshots_dir, target_ids)
            _run_roundtrip(page, base, screenshots_dir, target_ids)
            _run_branch_checks(page, base, screenshots_dir, target_ids)
        # G4 runs canonical JSON from backup (G2 UI save may add empty agentVersions/flowNodes).
        restore_all_graphs()
        print("[graph full suite] restored meta/graphs from backup before G4")
        if not _ping_server(base):
            fail("G4-preflight", "Flask not reachable after G2/G3")
        _run_stream_tests(page, base, screenshots_dir, graph_ids)
    finally:
        restore_all_graphs()
        print("[graph full suite] restored meta/graphs from backup")
        try:
            from ui_tests.utils.graph_suite_report import write_graph_suite_report

            report_path = write_graph_suite_report(screenshots_dir)
            print(f"[graph full suite] report: {report_path}")
        except Exception as ex:
            print(f"[graph full suite] report write failed: {ex}")
