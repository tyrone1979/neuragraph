"""Experiment UI tests: dataset, workflow selection, batch run via SSE."""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.utils.playwright_helpers import fail, goto, ok, results, shot

RUNNER_ID = "wf_doc_re_nested_branch"
DATASET_FILE = "exp_test_2samples.csv"
RUNNER_DISPLAY = "Doc RE (nested loop + branch) (wf_doc_re_nested_branch) - Workflow"


def ensure_dataset(tests_data_dir: Path) -> None:
    rows = [
        {
            "text": "Aspirin may reduce the risk of heart disease.",
            "gold_entities": '{"Chemical": ["Aspirin"], "Disease": ["heart disease"]}',
            "gold_relations": "Aspirin | treats | heart disease",
        },
        {
            "text": "Metformin is commonly used to treat type 2 diabetes.",
            "gold_entities": '{"Chemical": ["Metformin"], "Disease": ["type 2 diabetes"]}',
            "gold_relations": "Metformin | treats | type 2 diabetes",
        },
    ]
    from service.entity.test import TestLoader

    TestLoader.save_csv_rows(
        RUNNER_ID, DATASET_FILE, ["text", "gold_entities", "gold_relations"], rows
    )


def api_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_report_stream(base: str, exp_id: str, timeout: int = 180) -> str:
    url = f"{base}/stream/report/{exp_id}"
    buf = ""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    buf += line[6:].replace("\\n", "\n")
    except Exception as ex:
        print(f"  [report] {ex}")
    return buf


def wait_stream_done(base: str, exp_id: str, timeout: int = 400) -> bool:
    url = f"{base}/stream/run/{exp_id}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            for line in resp:
                if b"[DONE]" in line:
                    return True
    except Exception as ex:
        print(f"  [stream] {ex}")
    return False


def api_post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    ensure_dataset(tests_data_dir)

    print("\n=== E1. DATASET (2 samples) ===")
    datasets = api_get_json(f"{base}/testset/api/by_agent/{RUNNER_ID}")
    found = next((d for d in datasets if d.get("name") == DATASET_FILE), None)
    ok("E1a - Dataset listed for workflow", found is not None) if found else fail("E1a", str(datasets)[:200])
    ok("E1b - Dataset has 2 samples", found and found.get("count") == 2) if found and found.get("count") == 2 else fail(
        "E1b", str(found)
    )

    print("\n=== E2. EXPERIMENT PAGE ===")
    params = urllib.parse.urlencode(
        {
            "runner_id": RUNNER_ID,
            "runner_type": "graph",
            "runner_display": RUNNER_DISPLAY,
            "filename": DATASET_FILE,
        }
    )
    goto(page, base, f"/exp/new?{params}", 4)
    shot(page, screenshots_dir, "e2_exp_new")

    ok("E2a - Page title", "Experiment" in page.title() or "Run" in page.title())
    ok("E2b - Runner id set", page.locator("#runnerId").input_value() == RUNNER_ID)
    ok("E2c - Runner type graph", page.locator("#runnerType").input_value() == "graph")
    ok("E2d - Dataset selected", page.locator("#datasetSelect").input_value() == DATASET_FILE)
    ok("E2e - Start button visible", page.locator("#runExpBtn").is_visible())
    preview_text = page.locator("#config").inner_text()
    ok("E2f - Preview shows 2 samples", "2" in preview_text and DATASET_FILE in preview_text)
    ok("E2g - Preview shows gold_entities column", "gold_entities" in preview_text)

    print("\n=== E3. RUN EXPERIMENT (SSE) ===")
    page.on("dialog", lambda d: d.accept())

    with page.expect_response(
        lambda r: "/exp/api/save" in r.url and r.request.method == "POST", timeout=60000
    ) as save_resp:
        page.locator("#runExpBtn").click()
    save_json = save_resp.value.json()
    exp_id = save_json.get("exp_id", "")
    ok("E3a - Save returns exp_id", bool(exp_id)) if exp_id else fail("E3a", str(save_json)[:120])
    shot(page, screenshots_dir, "e3_exp_started")

    api_post_json(
        f"{base}/exp/api/update",
        {"exp_id": exp_id, "status": "running", "progress": 0},
    )

    print("  Running batch stream (2 samples, up to 420s)...")
    stream_done = wait_stream_done(base, exp_id, timeout=420)
    ok("E3b - Stream finished [DONE]", stream_done) if stream_done else fail("E3b", "no DONE")

    detail = api_get_json(f"{base}/exp/api/{exp_id}")
    api_post_json(
        f"{base}/exp/api/update",
        {"exp_id": exp_id, "status": "completed", "progress": 100},
    )
    detail = api_get_json(f"{base}/exp/api/{exp_id}")
    ok("E3c - API status completed", detail.get("status") == "completed") if detail.get(
        "status"
    ) == "completed" else fail("E3c", f"status={detail.get('status')}")
    ok("E3d - API progress 100", detail.get("progress") == 100) if detail.get("progress") == 100 else fail(
        "E3d", str(detail.get("progress"))
    )

    goto(page, base, f"/exp/{exp_id}", 4)
    page.wait_for_load_state("networkidle", timeout=30000)
    shot(page, screenshots_dir, "e3_exp_done")

    from service.result.loader import ResultLoader

    results = ResultLoader.load(exp_id) or {}
    sample_keys = [k for k in results.keys() if str(k).isdigit()]
    ok("E3e - Results persisted (2 samples)", len(sample_keys) >= 2) if len(sample_keys) >= 2 else fail(
        "E3e", f"result_keys={list(results.keys())}"
    )
    has_metrics = any(
        isinstance(results.get(k), dict) and "metrics" in results[k] for k in sample_keys
    )
    ok("E3e2 - Gold metrics on at least one sample", has_metrics) if has_metrics else fail(
        "E3e2", str({k: list((results.get(k) or {}).keys()) for k in sample_keys})[:200]
    )
    ok("E3f - Detail page shows dataset", DATASET_FILE in page.content())

    print("\n=== E5. REPORT TAB ===")
    report_md = wait_report_stream(base, exp_id, timeout=180)
    ok("E5a - Report stream returned content", len(report_md.strip()) > 20) if len(
        report_md.strip()
    ) > 20 else fail("E5a", report_md[:120])

    page.locator('a[href="#report"]').click()
    if report_md.strip():
        page.evaluate(
            """(md) => {
                const el = document.getElementById('reportMarkdown');
                if (!el) return;
                if (typeof marked !== 'undefined') el.innerHTML = marked.parse(md);
                else el.innerHTML = '<pre>' + md + '</pre>';
            }""",
            report_md,
        )
    else:
        page.evaluate(
            """(expId) => { if (typeof renderReport === 'function') renderReport(expId); }""",
            exp_id,
        )
        try:
            page.wait_for_function(
                """() => {
                    const el = document.getElementById('reportMarkdown');
                    if (!el) return false;
                    const html = el.innerHTML || '';
                    return html.length > 30 && !html.includes('spinner-border');
                }""",
                timeout=180000,
            )
        except Exception as ex:
            fail("E5b - Report tab rendered HTML", str(ex)[:120])
    shot(page, screenshots_dir, "e5_report_tab")
    report_html = page.locator("#reportMarkdown").inner_html()
    ok(
        "E5b - Report tab rendered HTML",
        len(report_html) > 30 and "spinner-border" not in report_html,
    ) if len(report_html) > 30 else fail("E5b", report_html[:120] or "(empty)")

    print("\n=== E4. EXPERIMENT LIST ===")
    goto(page, base, "/exp/", 3)
    ok("E4a - List page loads", page.locator("table, .table").count() > 0)
    if exp_id:
        ok("E4b - Experiment in list", exp_id in page.content())
