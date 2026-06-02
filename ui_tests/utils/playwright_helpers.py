"""Shared helpers for Playwright UI tests."""
import json
import sys
import time

from playwright.sync_api import Page

results: list = []
page_errors: list = []


def ok(test: str, detail: str = ""):
    results.append({"test": test, "status": "PASS", "detail": str(detail)[:200]})


def fail(test: str, detail: str = ""):
    detail = str(detail)[:200].encode("ascii", errors="replace").decode("ascii")
    results.append({"test": test, "status": "FAIL", "detail": detail})
    print(f"  [FAIL] {test}: {detail}")


def shot(page: Page, screenshots_dir: str, name: str):
    page.screenshot(path=f"{screenshots_dir}/{name}.png", full_page=True)


def goto(page: Page, base: str, path: str, sleep: float = 3, wait_until: str = "commit", timeout: int = 90000):
    page.goto(f"{base}{path}", timeout=timeout, wait_until=wait_until)
    time.sleep(sleep)


def paper_scale(page: Page):
    return page.evaluate("() => (typeof paper !== 'undefined' && paper) ? paper.scale().sx : 1")


def wf_nodes(page: Page):
    return page.evaluate("""() => {
        if (typeof graph === 'undefined' || !graph) return [];
        const out = [];
        graph.getElements().forEach(e => {
            if (e.get('subgraph')) return;
            const c = e.get('config');
            if (!c) return;
            out.push({
                id: c.id,
                cellType: e.get('type') || '',
                w: e.get('size').width,
                h: e.get('size').height,
                html: e.attr('content/html') || '',
                name: c.name || '',
                type: c.type || '',
                flowKind: c.flowKind || '',
                inputs: c.inputs || [],
                outputs: c.outputs || null,
                portCount: e.getPorts ? e.getPorts().length : 0
            });
        });
        return out;
    }""")


def canvas_center(page: Page):
    pb = page.locator("#paper_panel").bounding_box()
    if not pb:
        return None
    return pb["x"] + pb["width"] / 2, pb["y"] + pb["height"] / 2


def write_results(screenshots_dir: str) -> int:
    p = sum(1 for r in results if r["status"] == "PASS")
    f = sum(1 for r in results if r["status"] == "FAIL")
    print(f"RESULTS: {p} PASS, {f} FAIL, {len(results)} TOTAL")
    if page_errors:
        print(f"PAGE ERRORS: {page_errors[:5]}")
    with open(f"{screenshots_dir}/test_results.json", "w", encoding="utf-8") as fp:
        json.dump(
            {"results": results, "passed": p, "failed": f, "errors": page_errors[:10]},
            fp,
            indent=2,
        )
    return 1 if f else 0


def reset_results():
    results.clear()
    page_errors.clear()
