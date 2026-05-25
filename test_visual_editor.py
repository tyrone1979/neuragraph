"""Test the visual editor page with Playwright"""
from playwright.sync_api import sync_playwright
import time

BASE = "http://127.0.0.1:5001"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    
    # Capture console errors
    errors = []
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
    page.on("pageerror", lambda err: errors.append(f"[PAGE ERROR] {err}"))
    
    # 1. Test bio_ner_graph edit page
    print("=" * 60)
    print("TEST 1: Load bio_ner_graph/edit")
    print("=" * 60)
    page.goto(f"{BASE}/graph/bio_ner_graph/edit", timeout=30000)
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path="d:/projects/agentic_llmre/test_screenshots/bio_ner_load.png", full_page=True)
    
    # Check what nodes exist
    nodes_count = page.evaluate("() => { try { return graph ? graph.getElements().length : 0; } catch(e) { return -1; } }")
    print(f"  Nodes on canvas: {nodes_count}")
    
    links_count = page.evaluate("() => { try { return graph ? graph.getLinks().length : 0; } catch(e) { return -1; } }")
    print(f"  Links on canvas: {links_count}")
    
    # Check if nodes have text
    node_texts = page.evaluate("""() => {
        try {
            if (!graph) return [];
            return graph.getElements().map(el => ({
                id: el.id,
                nameText: el.attr('nameText/text'),
                labelText: el.attr('text/text'),
                nodeType: el.get('nodeData')?.type
            }));
        } catch(e) { return [{error: e.message}]; }
    }""")
    print(f"  Node texts: {node_texts}")
    
    # Check if property panel is hidden by default
    panel_visible = page.evaluate("() => { const p = document.getElementById('propertyPanel'); return p ? !p.classList.contains('d-none') : false; }")
    print(f"  Property panel visible (should be false): {panel_visible}")
    
    # Print JS errors
    if errors:
        print(f"  JS Console issues ({len(errors)}):")
        for e in errors[:10]:
            print(f"    {e[:200]}")
    else:
        print("  No JS console errors!")
    
    # 2. Test right-click on canvas
    print("\n" + "=" * 60)
    print("TEST 2: Right-click context menu")
    print("=" * 60)
    
    # Right-click on canvas
    canvas = page.locator("#paper_panel")
    canvas_box = canvas.bounding_box()
    if canvas_box:
        cx = canvas_box["x"] + canvas_box["width"] // 2
        cy = canvas_box["y"] + canvas_box["height"] // 2
        page.mouse.click(cx, cy, button="right")
        page.wait_for_timeout(1000)
        page.screenshot(path="d:/projects/agentic_llmre/test_screenshots/right_click_menu.png", full_page=True)
        
        menu_exists = page.evaluate("() => { return !!document.getElementById('contextMenu'); }")
        print(f"  Context menu appeared: {menu_exists}")
        
        if menu_exists:
            menu_items = page.evaluate("() => { const m = document.getElementById('contextMenu'); return m ? m.innerText : ''; }")
            print(f"  Menu items: {menu_items[:300]}")
        else:
            # Check the console for errors at the point of right-click
            recent_errors = page.evaluate("() => { return (window.__testErrors || []).slice(-10); }")
            print(f"  Recent errors: {recent_errors}")
            
            # Try to trigger contextmenu manually
            result = page.evaluate("""() => {
                const el = document.querySelector('#paper_panel svg') || document.querySelector('#paper_panel');
                if (!el) return 'No element found';
                const evt = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: 500, clientY: 300 });
                el.dispatchEvent(evt);
                return 'Event dispatched: ' + evt.defaultPrevented;
            }""")
            print(f"  Manual contextmenu dispatch: {result}")
            menu_exists2 = page.evaluate("() => { return !!document.getElementById('contextMenu'); }")
            print(f"  Context menu after manual dispatch: {menu_exists2}")
    
    # 3. Test click on node to show property panel
    print("\n" + "=" * 60)
    print("TEST 3: Click node -> property panel")
    print("=" * 60)
    
    # Find first agent node and click it
    clicked = page.evaluate("""() => {
        if (!graph) return 'no graph';
        const elements = graph.getElements();
        for (const el of elements) {
            const nd = el.get('nodeData');
            if (nd && nd.type !== 'start' && nd.type !== 'end') {
                // Find the element's view and click it
                const view = el.findView(paper);
                if (view) {
                    const bbox = view.getBBox();
                    const localPoint = { x: bbox.x + bbox.width/2, y: bbox.y + bbox.height/2 };
                    const clientPoint = paper.localToClientPoint(localPoint);
                    return { id: el.id, x: clientPoint.x, y: clientPoint.y, nodeType: nd.type };
                }
                return { id: el.id, bbox: el.getBBox() };
            }
        }
        return 'no non-START/END node found';
    }""")
    print(f"  Click target: {clicked}")
    
    if isinstance(clicked, dict) and 'x' in clicked:
        page.mouse.click(clicked['x'], clicked['y'])
        page.wait_for_timeout(1000)
        panel_visible2 = page.evaluate("() => { const p = document.getElementById('propertyPanel'); return p ? !p.classList.contains('d-none') : false; }")
        print(f"  Property panel visible after click: {panel_visible2}")
        if panel_visible2:
            panel_content = page.evaluate("() => { const p = document.getElementById('typeSpecificProps'); return p ? p.innerText.substring(0, 500) : ''; }")
            print(f"  Panel content: {panel_content}")
    else:
        # Try clicking by position
        node_pos = page.evaluate("""() => {
            if (!graph) return null;
            const els = graph.getElements();
            for (const el of els) {
                const nd = el.get('nodeData');
                if (nd && nd.type !== 'start' && nd.type !== 'end') {
                    const bbox = el.getBBox();
                    if (bbox) return { id: el.id, x: bbox.x + bbox.width/2, y: bbox.y + bbox.height/2 };
                }
            }
            return null;
        }""")
        if node_pos:
            # Convert local to client (approximate)
            scale = page.evaluate("() => paper ? paper.scale().sx : 1")
            tx = page.evaluate("() => paper ? paper.translate().tx : 0")
            ty = page.evaluate("() => paper ? paper.translate().ty : 0")
            canvas_rect = page.evaluate("() => { const r = document.querySelector('#paper_panel').getBoundingClientRect(); return { x: r.x, y: r.y }; }")
            cx = canvas_rect['x'] + node_pos['x'] * scale + tx
            cy = canvas_rect['y'] + node_pos['y'] * scale + ty
            page.mouse.click(cx, cy)
            page.wait_for_timeout(1000)
            panel_visible2 = page.evaluate("() => { const p = document.getElementById('propertyPanel'); return p ? !p.classList.contains('d-none') : false; }")
            print(f"  Property panel visible after click (pos method): {panel_visible2}")
    
    page.screenshot(path="d:/projects/agentic_llmre/test_screenshots/after_node_click.png", full_page=True)
    
    # 4. Test demo_advanced_workflow
    print("\n" + "=" * 60)
    print("TEST 4: Load demo_advanced_workflow")
    print("=" * 60)
    page.goto(f"{BASE}/graph/demo_advanced_workflow/edit", timeout=30000)
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path="d:/projects/agentic_llmre/test_screenshots/demo_workflow.png", full_page=True)
    
    nodes_count2 = page.evaluate("() => { try { return graph ? graph.getElements().length : 0; } catch(e) { return -1; } }")
    print(f"  Nodes on canvas: {nodes_count2}")
    
    node_texts2 = page.evaluate("""() => {
        try {
            if (!graph) return [];
            return graph.getElements().map(el => ({
                id: el.id,
                nameText: el.attr('nameText/text'),
                text: el.attr('text/text'),
                nodeType: el.get('nodeData')?.type
            }));
        } catch(e) { return [{error: e.message}]; }
    }""")
    print(f"  Node texts: {JSON.stringify(node_texts2)[:800]}")
    
    links_count2 = page.evaluate("() => { try { return graph ? graph.getLinks().length : 0; } catch(e) { return -1; } }")
    print(f"  Links on canvas: {links_count2}")
    
    # Check for subgraph type nodes
    subgraph_nodes = page.evaluate("""() => {
        if (!graph) return [];
        return graph.getElements().filter(el => el.get('nodeData')?.type === 'subgraph').map(el => ({ id: el.id, name: el.attr('nameText/text') || el.attr('text/text') }));
    }""")
    print(f"  Subgraph nodes found: {subgraph_nodes}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
    
    browser.close()
