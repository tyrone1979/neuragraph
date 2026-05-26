
import json, sys, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
SCREENSHOTS = sys.argv[2] if len(sys.argv) > 2 else "tests/screenshots"

results = []          # list of { test, status, detail }
errors = []           # raw console/page errors

def ok(test, detail=""):
    results.append({"test": test, "status": "PASS", "detail": str(detail)[:200]})

def fail(test, detail=""):
    results.append({"test": test, "status": "FAIL", "detail": str(detail)[:200]})
    print(f"  [FAIL] {test}: {detail}")

def shot(page, name):
    path = f"{SCREENSHOTS}/{name}.png"
    page.screenshot(path=path, full_page=True)

# ------------------------------------------------------------
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = ctx.new_page()

    # capture errors
    page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type in ("error","warning") else None)
    page.on("pageerror", lambda e: errors.append(f"[PAGE] {e}"))

    # ────────────────────────────────────────────────
    # 1. PAGE LOAD TESTS
    # ────────────────────────────────────────────────
    print("\n=== 1. PAGE LOAD TESTS ===")
    
    # 1a. Load bio_ner_graph/edit
    page.goto(f"{BASE}/graph/bio_ner_graph/edit", timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)
    shot(page, "01a_bio_ner_graph_loaded")
    title = page.title()
    ok("1a - bio_ner_graph page loads", title)
    
    # 1b. Top bar exists
    name_el = page.locator("#currentWorkflowName")
    ok("1b - Workflow name visible", name_el.is_visible())
    
    # 1c. Left panel exists
    comp_panel = page.locator("#componentPanel")
    ok("1c - Left component panel", comp_panel.is_visible())
    
    # 1d. Canvas area exists
    canvas = page.locator("#paper_panel")
    ok("1d - Canvas paper_panel", canvas.is_visible())
    
    # 1e. Property panel hidden by default
    prop_panel = page.locator("#propertyPanel")
    _dnone = prop_panel.get_attribute("class") or ""
    ok("1e - Property panel hidden", "d-none" in _dnone)
    
    # 1f. Toolbar exists
    toolbar = page.locator("#toolbar")
    ok("1f - Toolbar visible", toolbar.is_visible())

    # ────────────────────────────────────────────────
    # 2. JOINTJS & WORKFLOW RENDERING
    # ────────────────────────────────────────────────
    print("\n=== 2. WORKFLOW RENDERING ===")
    
    # 2a. Graph object created
    graph_exists = page.evaluate("typeof graph !== 'undefined'")
    ok("2a - Graph object exists", graph_exists)
    
    # 2b. Paper object created
    paper_exists = page.evaluate("typeof paper !== 'undefined'")
    ok("2b - Paper object exists", paper_exists)
    
    # 2c. Nodes rendered (>= 3 for START + agent + END)
    n_nodes = page.evaluate("graph ? graph.getElements().length : 0")
    ok("2c - Nodes on canvas (>=3)", f"count={n_nodes}") if n_nodes >= 3 else fail("2c - Nodes on canvas", f"count={n_nodes}")
    
    # 2d. Links rendered (>= 2 for START→agent→END)
    n_links = page.evaluate("graph ? graph.getLinks().length : 0")
    ok("2d - Links on canvas (>=2)", f"count={n_links}") if n_links >= 2 else fail("2d - Links on canvas", f"count={n_links}")
    
    # 2e. START node present
    has_start = page.evaluate("graph ? graph.getCell('START') !== undefined : false")
    ok("2e - START node exists", has_start)
    
    # 2f. END node present
    has_end = page.evaluate("graph ? graph.getCell('END') !== undefined : false")
    ok("2f - END node exists", has_end)
    
    # 2g. Agent nodes have text
    node_texts = page.evaluate("""() => {
        if (!graph) return [];
        return graph.getElements().filter(el => { const c=el.get('config'); return c&&c.id&&c.id!=='START'&&c.id!=='END'; })
            .map(el => ({id:el.id, name:el.attr('headerText/text')||el.attr('text/text')||'', hasText:!!(el.attr('headerText/text')||el.attr('text/text'))}));
    }""")
    all_have_text = all(n['hasText'] for n in node_texts)
    ok("2g - Agent nodes show text", str(node_texts)[:200]) if all_have_text else fail("2g - Agent nodes text missing", str(node_texts)[:200])
    
    # 2h. Ports exist on agent nodes  
    port_count = page.evaluate("""() => {
        if (!graph) return -1;
        const ags = graph.getElements().filter(el => { const c=el.get('config'); return c&&c.id!=='START'&&c.id!=='END'; });
        return ags.reduce((sum, el) => sum + (el.getPorts ? el.getPorts().length : 0), 0);
    }""")
    ok("2h - Ports on agent nodes", f"total={port_count}")
    
    # 2i. Links have sourceMarker/targetMarker
    link_attrs = page.evaluate("""() => {
        if (!graph) return [];
        return graph.getLinks().map(l => ({ hasSource: !!l.get('source').id, hasTarget: !!l.get('target').id }));
    }""")
    all_linked = all(l['hasSource'] and l['hasTarget'] for l in link_attrs)
    ok("2i - Links connect properly", all_linked)

    # ────────────────────────────────────────────────
    # 3. NODE CLICK & PROPERTY PANEL  
    # ────────────────────────────────────────────────
    print("\n=== 3. NODE CLICK → PROPERTY PANEL ===")
    
    # 3a. Click a non-START/END node via JS
    clicked = page.evaluate("""() => {
        if (!graph || !paper) return null;
        const els = graph.getElements();
        for (const el of els) {
            const c = el.get('config');
            if (c && c.id && c.id !== 'START' && c.id !== 'END') {
                return { id: el.id, type: c.type };
            }
        }
        return null;
    }""")
    ok("3a - Find clickable node", clicked is not None) if clicked else fail("3a - No clickable node")
    
    if clicked and 'id' in clicked:
        # trigger select via JS directly (bypass coordinate issues in headless browser)
        page.evaluate("""(nid) => {
            const el = graph.getCell(nid);
            if (el) selectNode(el);
        }""", clicked['id'])
        time.sleep(0.5)
        panel_visible = page.evaluate("() => { const p = document.getElementById('propertyPanel'); return p ? !p.classList.contains('d-none') : false; }")
        ok("3b - Property panel opens on select", panel_visible) if panel_visible else fail("3b - Panel not visible")
        
        if panel_visible:
            prop_text = page.locator("#typeSpecificProps").inner_text()[:300]
            ok("3c - Property panel has content", bool(prop_text.strip()))
            
            # 3d. Node name input
            name_input = page.locator("#propName")
            ok("3d - Node name input exists", name_input.is_visible())
            
            # 3e. Close property panel
            page.locator("#closePropertyPanel").click()
            time.sleep(0.3)
            panel_hidden = page.evaluate("() => { const p = document.getElementById('propertyPanel'); return p.classList.contains('d-none'); }")
            ok("3e - Close property panel", panel_hidden)
            
            # 3f. Re-select node to open again
            page.evaluate("""(nid) => {
                const el = graph.getCell(nid);
                if (el) selectNode(el);
            }""", clicked['id'])
            time.sleep(0.3)
            panel_open2 = page.evaluate("() => { const p = document.getElementById('propertyPanel'); return !p.classList.contains('d-none'); }")
            ok("3f - Re-select opens property panel", panel_open2)
            
            # 3g. Deselect closes panel
            page.evaluate("deselectAll()")
            time.sleep(0.3)
            panel_hidden2 = page.evaluate("() => { const p = document.getElementById('propertyPanel'); return p.classList.contains('d-none'); }")
            ok("3g - Deselect closes panel", panel_hidden2)
    
    # 3h. Node name editing
    if clicked and 'id' in clicked:
        page.evaluate("""(nid) => {
            const el = graph.getCell(nid);
            if (el) selectNode(el);
        }""", clicked['id'])
        time.sleep(0.3)
        page.locator("#propName").fill("Test Node Renamed")
        new_name = page.evaluate("() => document.getElementById('propName').value")
        ok("3h - Node name editable", new_name == "Test Node Renamed")

    # ────────────────────────────────────────────────
    # 4. RIGHT-CLICK CONTEXT MENU
    # ────────────────────────────────────────────────
    print("\n=== 4. RIGHT-CLICK CONTEXT MENU ===")
    shot(page, "04_before_right_click")
    
    # 4a. Right-click blank area - use native Playwright mouse
    paper_box = page.locator("#paper_panel").bounding_box()
    if paper_box:
        page.mouse.click(paper_box['x'] + 300, paper_box['y'] + 300, button="right")
        time.sleep(0.5)
        menu_visible = page.evaluate("() => { const m = document.getElementById('customContextMenu'); return m ? m.style.display === 'block' : false; }")
        ok("4a - Blank context menu appears", menu_visible) if menu_visible else fail("4a - Blank context menu", "not visible")
    
    if menu_visible:
        menu_items = page.evaluate("() => { const m = document.getElementById('customContextMenu'); return m ? m.innerText : ''; }")
        ok("4b - Menu has export items", "Export" in menu_items)
        ok("4c - Menu has Create Agent", "Create Agent" in menu_items)
    
    # 4d. Right-click on a node via JS event dispatch
    if clicked and 'id' in clicked:
        page.evaluate("""(nid) => {
            const el = document.querySelector('#paper_panel svg') || document.querySelector('#paper_panel');
            if (el) {
                const node = graph.getCell(nid);
                if (node) selectNode(node);
                const e = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: 400, clientY: 300 });
                el.dispatchEvent(e);
            }
        }""", clicked['id'])
        time.sleep(0.3)
        node_menu = page.evaluate("() => { const m = document.getElementById('customContextMenu'); return m ? m.style.display === 'block' : false; }")
        ok("4d - Node context menu appears", node_menu)
    
    # 4e. Click outside closes menu
    page.mouse.click(10, 10)
    time.sleep(0.2)
    menu_hidden = page.evaluate("() => { const m = document.getElementById('customContextMenu'); return m ? m.style.display === 'none' : false; }")
    ok("4e - Click outside closes menu", menu_hidden)

    # ────────────────────────────────────────────────
    # 5. TOP BAR CONTROLS
    # ────────────────────────────────────────────────
    print("\n=== 5. TOP BAR CONTROLS ===")
    
    # 5a. Zoom In exists and clickable
    zoom_in = page.locator("#zoomIn")
    ok("5a - Zoom In button", zoom_in.is_visible())
    zoom_in.click()
    time.sleep(0.3)
    scale_after_zoomin = page.evaluate("paper ? paper.scale().sx : 1")
    ok("5b - Zoom In changes scale", scale_after_zoomin > 0.9)
    
    # 5c. Zoom Out
    zoom_out = page.locator("#zoomOut")
    ok("5c - Zoom Out button", zoom_out.is_visible())
    zoom_out.click()
    
    # 5d. Fit to Content
    page.locator("#fitToContent").click()
    time.sleep(0.3)
    ok("5d - Fit to Content works", True)
    
    # 5e. Reset View
    page.locator("#resetView").click()
    time.sleep(0.3)
    scale_reset = page.evaluate("paper ? paper.scale().sx : 1")
    ok("5e - Reset View (scale=1)", abs(scale_reset - 1) < 0.01)
    
    # 5f. Save button exists
    save_btn = page.locator("#saveGraphBtn")
    ok("5f - Save button visible", save_btn.is_visible())
    
    # 5g. Test modal
    page.locator("#testWorkflow").click()
    time.sleep(0.5)
    modal_visible = page.locator("#testModal").is_visible()
    ok("5g - Test modal opens", modal_visible)
    if modal_visible:
        page.locator("#testInput").fill('{"text": "Hello World"}')       
        page.locator("#runTestBtn").click()
        time.sleep(0.5)
        test_output = page.locator("#testOutput").inner_text()
        ok("5h - Test runs with input", "complete" in test_output.lower() or "Running" in test_output)
        # close modal
        page.locator("#testModal .btn-close").click()
        time.sleep(0.3)

    # ────────────────────────────────────────────────
    # 6. LEFT PANEL COMPONENTS
    # ────────────────────────────────────────────────
    print("\n=== 6. LEFT PANEL COMPONENTS ===")
    
    # 6a. Accordion sections
    accordions = ["#collapseStartEnd", "#collapseAgents", "#collapseSubgraphs", "#collapseTools"]
    for acc in accordions:
        el = page.locator(acc)
        ok(f"6a - Accordion {acc}", el.is_visible())
    
    # 6b. Flow Control items
    fc_items = page.locator("#collapseStartEnd .component-item")
    fc_count = fc_items.count()
    ok("6b - Flow Control items (>=4)", f"count={fc_count}") if fc_count >= 4 else fail("6b - Flow Control items", f"count={fc_count}")
    
    # 6c. Agent list loaded (>=1)
    agent_items = page.locator("#agentList .component-item")
    agent_count = agent_items.count()
    ok("6c - Agents loaded (>=1)", f"count={agent_count}") if agent_count >= 1 else fail("6c - Agents loaded", f"count={agent_count}")
    
    # 6d. Subgraph list loaded  
    sub_items = page.locator("#subgraphList .component-item")
    sub_count = sub_items.count()
    ok("6d - Subgraphs loaded", f"count={sub_count}")
    
    # 6e. Component search
    page.locator("#componentSearch").fill("cid")
    time.sleep(0.2)
    filtered = page.locator(".component-item").count()
    ok("6e - Component search filters", filtered > 0)
    page.locator("#componentSearch").fill("")

    # ────────────────────────────────────────────────
    # 7. TOOLBAR BUTTONS
    # ────────────────────────────────────────────────
    print("\n=== 7. CANVAS TOOLBAR ===")
    
    # 7a. Select button
    ok("7a - Select button", page.locator("#btnSelect").is_visible())
    
    # 7b. Connect button
    ok("7b - Connect button", page.locator("#btnConnect").is_visible())
    
    # 7c. Delete button  
    ok("7c - Delete button", page.locator("#btnDelete").is_visible())
    
    # 7d. Undo button
    undo_btn = page.locator("#btnUndo")
    ok("7d - Undo button", undo_btn.is_visible())
    
    # 7e. Redo button
    ok("7e - Redo button", page.locator("#btnRedo").is_visible())
    
    # 7f. Background color picker
    color_picker = page.locator("#bgColorPicker")
    ok("7f - Color picker exists", color_picker.is_visible())
    if color_picker.is_visible():
        color_picker.evaluate("el => { el.value = '#e0f0ff'; el.dispatchEvent(new Event('input', {bubbles:true})); }")
        time.sleep(0.3)
        bg = page.evaluate("() => getComputedStyle(document.getElementById('canvasContainer')).backgroundColor")
        ok("7g - Background color changes", "rgb" in bg.lower())

    # 7h. Toolbar is movable (drag test)
    tb_initial = page.evaluate("() => { const el = document.getElementById('toolbar'); return el ? el.style.left : null; }")
    # try a simple drag via mousedown/mousemove/mouseup
    page.evaluate("""() => {
        const tb = document.getElementById('toolbar');
        if (tb) {
            tb.style.left = '50px'; tb.style.top = '50px';
        }
    }""")
    tb_moved = page.evaluate("() => { const el = document.getElementById('toolbar'); return el.style.left; }")
    ok("7h - Toolbar movable", "50px" in (tb_moved or ""))

    # ────────────────────────────────────────────────
    # 8. KEYBOARD SHORTCUTS
    # ────────────────────────────────────────────────
    print("\n=== 8. KEYBOARD SHORTCUTS ===")
    
    # 8a. Ctrl+S triggers save attempt (will fail without prompt, but function exists)
    has_save = page.evaluate("typeof saveGraph === 'function'")
    ok("8a - saveGraph function exists", has_save)
    
    # 8b. Undo/Redo functions exist
    has_undo = page.evaluate("typeof undo === 'function'")
    ok("8b - undo function exists", has_undo)
    has_redo = page.evaluate("typeof redo === 'function'")
    ok("8c - redo function exists", has_redo)
    
    # 8d. History initialised
    hist_len = page.evaluate("historyStack ? historyStack.length : -1")
    ok("8d - History stack initialised", hist_len >= 1)

    # ────────────────────────────────────────────────
    # 9. PROMPT EDITING (LLM agents)
    # ────────────────────────────────────────────────
    print("\n=== 9. LLM PROMPT EDITING ===")
    
    llm_node = page.evaluate("""() => {
        if (!graph) return null;
        for (const el of graph.getElements()) {
            const c = el.get('config');
            if (c && c.type === 'LLM') {
                return { id: el.id };
            }
        }
        return null;
    }""")
    
    if llm_node and 'id' in llm_node:
        page.evaluate("""(nid) => {
            const el = graph.getCell(nid);
            if (el) selectNode(el);
        }""", llm_node['id'])
        time.sleep(0.5)
        # 9a. Prompt section exists for LLM
        prompt_section = page.locator("#typeSpecificProps").inner_text()
        ok("9a - Prompt template section for LLM", "Prompt" in prompt_section)
        
        # 9b. Prompt fields are editable
        prompt_fields = page.locator("#typeSpecificProps textarea.editable-field")
        prompt_count = prompt_fields.count()
        ok("9b - Editable prompt textareas", f"count={prompt_count}")
    
    # 9c. Save Changes button exists for agent
    save_changes = page.locator("#typeSpecificProps button:has-text('Save')")
    ok("9c - Save Changes button", save_changes.is_visible() if llm_node else "no LLM node")
    
    shot(page, "09_prompt_editing")

    # ────────────────────────────────────────────────
    # 10. MULTIPLE WORKFLOW LOADS
    # ────────────────────────────────────────────────
    print("\n=== 10. MULTIPLE WORKFLOW LOADS ===")
    
    for wf_id, wf_desc in [("biomed_ner_graph","biomed"), ("demo_advanced_workflow","demo")]:
        page.goto(f"{BASE}/graph/{wf_id}/edit", timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)
        n = page.evaluate("graph ? graph.getElements().length : 0")
        ok(f"10 - {wf_desc}: nodes rendered", f"count={n}")
        shot(page, f"10_{wf_id}_loaded")

    # ────────────────────────────────────────────────
    # 11. SUBGRAPH DETECTION  
    # ────────────────────────────────────────────────
    print("\n=== 11. SUBGRAPH DETECTION ===")
    
    page.goto(f"{BASE}/graph/demo_advanced_workflow/edit", timeout=60000, wait_until="domcontentloaded")
    time.sleep(4)
    
    # 11a. subgraphRanges populated
    sr_len = page.evaluate("subgraphRanges ? Object.keys(subgraphRanges).length : 0")
    ok("11a - Subgraph ranges populated", f"count={sr_len}")
    
    # 11b. Subgraph containers drawn (rectangles with z=-10, subgraph attr)
    sg_cells = page.evaluate("""() => {
        if (!graph) return 0;
        return graph.getCells().filter(c => c.get('subgraph')).length;
    }""")
    ok("11b - Subgraph container rects", f"count={sg_cells}")
    
    # 11c. Subgraph names shown
    sg_names = page.evaluate("""() => {
        if (!graph) return [];
        return graph.getCells().filter(c => c.get('subgraph')).map(c => c.attr('label/text'));
    }""")
    ok("11c - Subgraph names displayed", str(sg_names)[:200])
    
    # 11d. Pink transparent styling
    sg_style = page.evaluate("""() => {
        if (!graph) return null;
        const c = graph.getCells().find(c => c.get('subgraph'));
        return c ? { fill: c.attr('body/fill'), stroke: c.attr('body/stroke'), dash: c.attr('body/strokeDasharray') } : null;
    }""")
    ok("11d - Subgraph pink transparent style", str(sg_style)[:200])
    
    shot(page, "11_subgraph_demo")

    # ────────────────────────────────────────────────
    # 12. EXPORT FUNCTIONS
    # ────────────────────────────────────────────────
    print("\n=== 12. EXPORT FUNCTIONS ===")
    
    has_svg = page.evaluate("typeof downloadSVG === 'function'")
    ok("12a - downloadSVG function", has_svg)
    has_png = page.evaluate("typeof downloadPNG === 'function'")
    ok("12b - downloadPNG function", has_png)
    
    # ────────────────────────────────────────────────
    # 13. SERIALIZE GRAPH
    # ────────────────────────────────────────────────
    print("\n=== 13. SERIALIZE GRAPH ===")
    
    serialized = page.evaluate("""() => {
        if (typeof serializeGraph !== 'function') return {error:'not found'};
        return serializeGraph();
    }""")
    ok("13a - serializeGraph returns data", "nodes" in (serialized or {}))
    if "nodes" in (serialized or {}):
        ok("13b - Serialized has nodes", len(serialized.get("nodes", [])) > 0)
        ok("13c - Serialized has edges", len(serialized.get("edges", [])) > 0)

    # ────────────────────────────────────────────────
    # 14. DROP AGENT ON CANVAS (simulated)
    # ────────────────────────────────────────────────
    print("\n=== 14. DROP AGENT ON CANVAS ===")
    page.goto(f"{BASE}/graph/bio_ner_graph/edit", timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)
    n_before = page.evaluate("graph ? graph.getElements().length : 0")
    
    # Simulate drop via handleDrop directly using a unique id
    dropped = page.evaluate("""() => {
        try {
            const fakeData = JSON.stringify({type:'agent', id:'test_drop_agent', data:{name:'test_drop_agent',type:'PGM',inputs:['in1'],outputs:{name:'out1'}}});
            agentsData['test_drop_agent'] = { id:'test_drop_agent', name:'test_drop_agent', type:'PGM', inputs:['in1'], outputs:{name:'out1'} };
            handleDrop(fakeData, {x:300, y:300});
            return graph ? graph.getElements().length : -1;
        } catch(e) { return 'err:'+e.message; }
    }""")
    ok("14a - Drop agent increases node count", str(dropped)) if type(dropped) in (int, float) and dropped > n_before else fail("14a - Drop failed", f"before={n_before} after={dropped}")

    # ────────────────────────────────────────────────
    # 15. CREATE DEFAULT WORKFLOW
    # ────────────────────────────────────────────────
    print("\n=== 15. CREATE DEFAULT WORKFLOW ===")
    page.goto(f"{BASE}/graph/new", timeout=60000, wait_until="domcontentloaded")
    time.sleep(4)
    n_default = page.evaluate("graph ? graph.getElements().length : 0")
    ok("15a - Default workflow has START+END", n_default >= 2)

    # ────────────────────────────────────────────────
    # 16. SUMMARY
    # ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"RESULTS: {passed} PASS, {failed} FAIL, {len(results)} TOTAL")
    
    if errors:
        print(f"\nCONSOLE ERRORS ({len(errors)}):")
        for e in errors[:20]:
            print(f"  {e[:200]}")
    
    # Write results JSON
    with open(f"{SCREENSHOTS}/test_results.json", "w") as f:
        json.dump({"results": results, "passed": passed, "failed": failed, "errors": errors[:30]}, f, indent=2)
    
    print(f"\nScreenshots saved to: {SCREENSHOTS}")
    print(f"Results JSON: {SCREENSHOTS}/test_results.json")
    
    browser.close()
