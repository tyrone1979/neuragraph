"""Graph tests: delete meta/graphs, recreate via UI editor, compare to backup, screenshots."""
import time
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.common import fail, goto, ok, shot
from ui_tests.graph_utils import (
    ALL_GRAPH_IDS,
    delete_all_graphs,
    ensure_backup,
    graph_diff,
    graph_diff_canvas,
    list_graph_ids,
    load_graph_json,
)


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
    """Populate graphsById from backups (needed after G1 clears meta/graphs)."""
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


def _max_branch_conditions(graph_data: dict) -> int:
    flow = graph_data.get("flowNodes") or {}
    best = 0
    for fn in flow.values():
        if fn.get("kind") == "branch":
            best = max(best, len(fn.get("conditions") or []))
    return best


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    page.on("dialog", lambda d: d.accept())

    print("\n=== G1. BACKUP VERIFICATION ===")
    ensure_backup()
    backed = list_graph_ids(from_backup=True)
    ok("G1a - Backup present", len(backed) >= len(ALL_GRAPH_IDS)) if len(backed) >= len(
        ALL_GRAPH_IDS
    ) else fail("G1a", f"backup count={len(backed)}")

    removed = delete_all_graphs()
    live = list_graph_ids(from_backup=False)
    ok("G1b - meta/graphs cleared", len(live) == 0) if len(live) == 0 else fail(
        "G1b", f"still {len(live)} files ({removed} removed)"
    )
    try:
        shot(page, screenshots_dir, "g1_graphs_cleared")
    except Exception:
        pass

    print("\n=== G2. RECREATE VIA UI EDITOR + JSON DIFF ===")
    goto(page, base, "/graph/new", 3, wait_until="domcontentloaded")
    if not _wait_editor_ready(page):
        fail("G2-setup", "visual editor not ready on /graph/new")
        return

    try:
        _seed_graphs_registry(page, backed)
    except Exception as ex:
        fail("G2-setup", f"seed graphsById failed: {ex}")
        return

    for gid in ALL_GRAPH_IDS:
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
            try:
                shot(page, screenshots_dir, f"g2_fail_canvas_{gid}")
            except Exception:
                pass
        else:
            ok(f"G2d-{gid}", "canvas matches backup (WYSIWYG)")

        try:
            shot(page, screenshots_dir, f"g2_editor_{gid}")
        except Exception:
            pass

        with page.expect_response(
            lambda r: "/graph/api/save" in r.url and r.request.method == "POST",
            timeout=60000,
        ) as resp:
            page.evaluate("() => saveGraph()")
        save_json = resp.value.json()
        if not save_json.get("success"):
            fail(f"G2b-{gid}", str(save_json)[:200])
            try:
                shot(page, screenshots_dir, f"g2_fail_save_{gid}")
            except Exception:
                pass
            continue

        time.sleep(0.5)
        graphs_path = Path(__file__).resolve().parent.parent / "meta" / "graphs" / f"{gid}.json"
        if not graphs_path.is_file():
            fail(f"G2b-{gid}", "file not written after save")
            continue

        saved = load_graph_json(gid, from_backup=False)
        diff = graph_diff(backup, saved)
        if diff:
            fail(f"G2c-{gid}", diff[:300])
            try:
                shot(page, screenshots_dir, f"g2_fail_diff_{gid}")
            except Exception:
                pass
        else:
            ok(f"G2c-{gid}", "matches backup (excl. created_at, id)")

    try:
        shot(page, screenshots_dir, "g2_all_recreated")
    except Exception:
        pass

    print("\n=== G3. BRANCH GRAPHS (>=3 CONDITIONS) ===")
    branch_map = {
        "wf_cid_re_branch": "cid_re_gate",
        "wf_doc_ner_loop_branch": "ner_route",
        "wf_doc_re_nested_branch": "re_gate",
    }
    for gid, branch_id in branch_map.items():
        data = load_graph_json(gid, from_backup=False)
        n_conds = _max_branch_conditions(data)
        if n_conds >= 3:
            ok(f"G3-{gid}", f"branch_conds={n_conds} (json)")
        else:
            fail(f"G3-{gid}", f"conds={n_conds} (json)")

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
                    branch_id,
                )
                time.sleep(0.5)
                shot(page, screenshots_dir, f"g3_branch_{gid}")
        except Exception as ex:
            fail(f"G3-ui-{gid}", f"snapshot skipped: {str(ex)[:80]}")
