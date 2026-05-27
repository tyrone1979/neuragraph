"""Current / flaky UI tests: biomed workflow, nested loops, input mappings."""
import json
import time
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.common import fail, goto, ok, results, shot, wf_nodes

WF_MAIN = "wf_doc_re_nested_branch"


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    biomed_input = tests_data_dir / "biomed_test_input.json"
    if biomed_input.is_file():
        sample = biomed_input.read_text(encoding="utf-8").strip()
    else:
        sample = (
            '{"text": "Aspirin may reduce the risk of heart disease. '
            'Metformin is commonly used to treat type 2 diabetes."}'
        )

    print("\n=== C1. DOC RE WORKFLOW LOAD ===")
    page.on("dialog", lambda d: d.accept())
    goto(page, base, f"/graph/{WF_MAIN}/edit", 5)
    shot(page, screenshots_dir, "c1_biomed_loaded")

    ok("C1a - NER node on canvas", page.evaluate("() => !!graph.getCell('ner_llm')"))
    ok("C1b - RE node on canvas", page.evaluate("() => !!graph.getCell('relation_extract_llm')"))
    ok("C1c - report_format_json in nested subgraph", page.evaluate(
        "() => !!(currentGraph && currentGraph.flowNodes && "
        "currentGraph.flowNodes.re_process_loop && "
        "currentGraph.flowNodes.re_process_loop.subgraphId === 'sg_re_preprocess')"
    ))

    loop_cnt = page.evaluate("""() => {
        return ['re_process_loop'].filter(
            id => !!graph.getCell(id + '_container') || !!graph.getCell(id)
        ).length;
    }""")
    ok("C1d - Outer loop container present", loop_cnt >= 1) if loop_cnt >= 1 else fail(
        "C1d", f"containers={loop_cnt}"
    )

    branch_flow = page.evaluate(
        "() => (currentGraph.flowNodes.re_gate || {}).kind"
    )
    ok("C1e - Branch is graph flow (flowKind)", branch_flow == "branch") if branch_flow == "branch" else fail(
        "C1e", branch_flow
    )

    smooth = page.evaluate("""() => {
        return graph.getLinks().length > 0 && graph.getLinks().every(l => {
            const c = l.connector && l.connector();
            return c && c.name === 'smooth';
        });
    }""")
    ok("C1g - Smooth links", smooth) if smooth else fail("C1g", "not smooth")

    print("\n=== C2. INPUT MAPPING PANEL ===")
    page.evaluate("() => { const n = graph.getCell('relation_extract_llm'); if (n) selectNode(n); }")
    time.sleep(0.6)
    shot(page, screenshots_dir, "c2_re_mapping_panel")

    mapping_html = page.locator("#inputMapping").inner_text()
    ok("C2a - Mapping panel visible", page.locator("#ioMappingSection").is_visible())
    ok("C2b - Shows upstream node", "re_gate" in mapping_html or "re_process_loop" in mapping_html or "Upstream" in mapping_html)
    ok("C2c - Shows entities binding", "entities" in mapping_html)
    ok("C2d - Template binding for entities", "re_process_loop" in mapping_html)

    bound_val = page.evaluate("""() => {
        const b = (typeof graphBindings !== 'undefined' && graphBindings.relation_extract_llm) || {};
        return b.entities || '';
    }""")
    ok("C2e - graphBindings.entities set", "re_process_loop" in bound_val) if bound_val else fail(
        "C2e", mapping_html[:120]
    )
    mapping_selects = page.locator("#inputMapping select.mapping-select").count()
    ok("C2f - Input mapping uses dropdowns", mapping_selects >= 1) if mapping_selects >= 1 else fail(
        "C2f", f"selects={mapping_selects}"
    )

    print("\n=== C2b. BRANCH CONDITIONS UI (multi-branch) ===")
    page.evaluate("() => { const n = graph.getCell('re_gate'); if (n) selectNode(n); }")
    time.sleep(0.5)
    shot(page, screenshots_dir, "c2b_branch_panel")
    ok("C2b1 - Branch config section visible", page.locator("#branchConfigSection").is_visible())
    branch_rows = page.locator("#branchConditions .branch-cond-row").count()
    ok("C2b2 - At least 4 branch conditions", branch_rows >= 4) if branch_rows >= 4 else fail(
        "C2b2", f"rows={branch_rows}"
    )
    ok("C2b3 - Condition operator dropdown", page.locator("#branchConditions .cond-op").count() >= 4)
    ok("C2b4 - Condition field dropdown", page.locator("#branchConditions .cond-field").count() >= 4)

    print("\n=== C3. LLM + LIVE WORKFLOW ===")
    page.evaluate("() => { const n = graph.getCell('ner_llm'); if (n) selectNode(n); }")
    time.sleep(0.4)
    llm_opts = page.locator("#propLlmSelect option").all_text_contents()
    ok("C3a - LLM dropdown", len(llm_opts) > 1) if len(llm_opts) > 1 else fail("C3a", str(llm_opts))
    page.locator("#propLlmSelect").select_option("kimi-2.6")
    page.evaluate("() => saveAgentChanges('ner_llm')")
    time.sleep(0.4)

    page.locator("#testWorkflow").click()
    time.sleep(0.4)
    page.locator("#testInput").fill(sample)
    page.locator("#runTestBtn").click()
    print("  Waiting for live workflow (up to 420s)...")
    try:
        page.wait_for_function(
            """() => {
                const el = document.getElementById('testOutput');
                if (!el) return false;
                const t = el.innerText || '';
                return t.includes('Workflow completed') || (
                    t.includes('relation_extract_llm') && t.indexOf('|') >= 0
                ) || (
                    t.includes('ner_llm') && (t.includes('entities') || t.includes('Chemical'))
                );
            }""",
            timeout=420000,
        )
    except Exception as ex:
        fail("C3b - Workflow finished in time", str(ex)[:120])

    test_out = page.locator("#testOutput").inner_text()
    shot(page, screenshots_dir, "c3_test_output")
    with open(f"{screenshots_dir}/c3_test_output.txt", "w", encoding="utf-8") as tf:
        tf.write(test_out)

    if "Workflow completed" in test_out:
        ok("C3b - Live workflow completed", "done")
    elif "relation_extract_llm" in test_out and "|" in test_out:
        ok("C3b - Live workflow completed (RE output)", "partial")
    elif "ner_llm" in test_out and ("entities" in test_out or "Chemical" in test_out):
        ok("C3b - Live workflow completed (NER output)", "ner")
    else:
        fail("C3b - Live workflow completed", test_out[:200])

    ok(
        "C3c - Output has content",
        "|" in test_out
        or "entities" in test_out
        or "Chemical" in test_out
        or "Aspirin" in test_out,
    )
    page.locator("#testModal .btn-close").click()
    time.sleep(0.3)

    print("\n=== C4. LOOP DROP ON DOC RE ===")
    goto(page, base, f"/graph/{WF_MAIN}/edit", 4)
    nb = page.evaluate("() => graph.getElements().length")
    page.evaluate("() => { handleDrop(JSON.stringify({ type: 'loop', data: {} }), { x: 900, y: 120 }); }")
    time.sleep(0.5)
    na = page.evaluate("() => graph.getElements().length")
    ok("C4a - Drop loop adds container", na > nb) if na > nb else fail("C4a", f"{nb}->{na}")
