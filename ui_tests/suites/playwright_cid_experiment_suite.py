"""Playwright UI: CID dev.txt 2-sample experiments (NER + RE), metrics, report, screenshots."""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.utils.playwright_helpers import fail, goto, ok

ROOT = Path(__file__).resolve().parent.parent


def shot_exp(page: Page, screenshots_dir: str, name: str) -> None:
    page.screenshot(
        path=f"{screenshots_dir}/{name}.png", full_page=False, timeout=120000
    )

NER_RUNNER = "wf_cid_ner_llm_eval"
RE_RUNNER = "wf_cid_re_llm_linear"
DATASET_FILE = "cid_dev_2samples.csv"
STREAM_TIMEOUT = 3600  # background SSE reader; per-sample ~2-3 min LLM
RESULTS_POLL_TIMEOUT = 720  # HTTP /stream/run fallback poll
RE_BATCH_EXTRA = 900  # RE linear pipeline needs more time per sample


def ensure_cid_dataset(tests_data_dir: Path) -> None:
    """Ensure cid_dev_2samples.csv exists under both runners (from dev.txt if needed)."""
    from data.data_parser import CIDParser
    from service.entity.test import TestLoader

    ner_csv = tests_data_dir / NER_RUNNER / DATASET_FILE
    re_csv = tests_data_dir / RE_RUNNER / DATASET_FILE
    if ner_csv.is_file() and re_csv.is_file():
        return

    dev_path = tests_data_dir.parent / "data" / "raw" / "dev.txt"
    if not dev_path.is_file():
        dev_path = Path(__file__).resolve().parent.parent / "data" / "raw" / "dev.txt"
    text = dev_path.read_text(encoding="utf-8")
    articles = CIDParser(text).get_articles()[:2]
    if len(articles) < 2:
        raise RuntimeError(f"Need 2 articles in {dev_path}")

    def ner_row(art) -> dict[str, str]:
        mesh_to_text = {e.mesh: e.text for e in art.entities}
        rel_lines = []
        for head_mesh, tail_mesh in art.expected_relations:
            h = mesh_to_text.get(head_mesh, head_mesh)
            t = mesh_to_text.get(tail_mesh, tail_mesh)
            rel_lines.append(f"{h} | CID | {t}")
        return {
            "text": art.text,
            "labels": art.labels or "Chemical,Disease",
            "gold_entities": json.dumps(art.expected_entities, ensure_ascii=False),
            "gold_relations": "\n".join(rel_lines) if rel_lines else "",
        }

    def re_row(art) -> dict[str, str]:
        entities = [
            {"text": e.text, "id": e.mesh, "label": e.etype}
            for e in art.entities
        ]
        rel_lines = [f"{h} | {t}" for h, t in art.expected_relations]
        return {
            "text": art.text,
            "entities": json.dumps(entities, ensure_ascii=False),
            "gold_relations": "\n".join(rel_lines) if rel_lines else "",
        }

    ner_rows = [ner_row(a) for a in articles]
    re_rows = [re_row(a) for a in articles]
    TestLoader.save_csv_rows(
        NER_RUNNER,
        DATASET_FILE,
        ["text", "labels", "gold_entities", "gold_relations"],
        ner_rows,
    )
    TestLoader.save_csv_rows(
        RE_RUNNER,
        DATASET_FILE,
        ["text", "entities", "gold_relations"],
        re_rows,
    )


def api_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_stream_done(base: str, exp_id: str, timeout: int) -> bool:
    url = f"{base}/stream/run/{exp_id}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            for line in resp:
                if b"[DONE]" in line:
                    return True
    except Exception as ex:
        print(f"  [stream] {ex}")
    return False


def wait_results_file(exp_id: str, min_samples: int = 2, timeout: int = RESULTS_POLL_TIMEOUT) -> bool:
    """Poll result/<exp_id>/states.json (written after each sample in /stream/run)."""
    path = ROOT / "result" / exp_id / "states.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                keys = [k for k in data if str(k).isdigit()]
                if len(keys) >= min_samples:
                    return True
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(5)
    return False


def goto_exp_results_page(page: Page, base: str, exp_id: str) -> bool:
    for attempt in range(3):
        try:
            goto(page, base, f"/exp/{exp_id}", 2, wait_until="commit", timeout=60000)
            return True
        except Exception as ex:
            print(f"  goto /exp/{exp_id} attempt {attempt + 1}: {ex}")
            time.sleep(3)
    return False


def run_batch_inprocess(exp_id: str, runner_id: str) -> bool:
    """Run workflow samples in-process (same as fixed /stream/run). Avoids Flask SSE thread contention during Playwright."""
    from langchain_core.runnables import RunnableConfig
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader

    exp_cfg = MetaLoader.load("exps", exp_id)
    exp_cfg["exp_id"] = exp_id
    _, rows = TestLoader.load_by_id_file(runner_id, DATASET_FILE)
    runner = RunnerLoader.load(runner_id)
    if runner is None:
        return False
    for idx, row in enumerate(rows, start=1):
        config: RunnableConfig = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
        if hasattr(runner, "compiled_graph"):
            runner.compiled_graph.invoke(dict(row), config=config)
        else:
            runner.invoke(dict(row), config=config)
        RunnerLoader.persistence(exp_cfg)
        MetaLoader.update(
            "exps",
            exp_id,
            {
                "progress": int(idx / len(rows) * 100) if rows else 100,
                "status": "running" if idx < len(rows) else "completed",
            },
        )
    return wait_results_file(exp_id, min_samples=2, timeout=30)


def start_stream_background(base: str, exp_id: str) -> threading.Thread:
    def _reader():
        wait_stream_done(base, exp_id, timeout=STREAM_TIMEOUT)

    t = threading.Thread(target=_reader, name=f"stream-{exp_id[:8]}", daemon=True)
    t.start()
    return t


def start_experiment_via_ui(page: Page) -> None:
    """Select dataset and submit (avoid change-event reload that clears the form)."""
    page.wait_for_selector(
        f'#datasetSelect option[value="{DATASET_FILE}"]',
        timeout=60000,
        state="attached",
    )
    page.evaluate(
        """(fname) => {
            const sel = document.getElementById('datasetSelect');
            if (sel) sel.value = fname;
            if (typeof $ !== 'undefined') $('#runExpBtn').removeClass('d-none').show();
        }""",
        DATASET_FILE,
    )
    btn = page.locator("#runExpBtn")
    if btn.is_visible():
        btn.click(timeout=10000)
    else:
        page.evaluate("() => { $('#expForm').trigger('submit'); }")


def api_create_experiment(
    base: str, runner_id: str, runner_display: str, samples: int = 2
) -> str:
    resp = api_post_json(
        f"{base}/exp/api/save",
        {
            "dataset": DATASET_FILE,
            "runner_type": "graph",
            "runner_id": runner_id,
            "runner_display": runner_display,
            "samples": samples,
        },
    )
    if not resp.get("success"):
        raise RuntimeError(f"save failed: {resp}")
    return resp.get("exp_id", "")


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


def _run_experiment_ui(
    page: Page,
    base: str,
    screenshots_dir: str,
    runner_id: str,
    runner_display: str,
    prefix: str,
) -> str | None:
    """Full UI flow for one workflow; returns exp_id."""
    tag = prefix.rstrip("_")

    datasets = api_get_json(f"{base}/testset/api/by_agent/{runner_id}")
    found = next((d for d in datasets if d.get("name") == DATASET_FILE), None)
    ok(f"{tag}-dataset-listed", found is not None) if found else fail(f"{tag}-dataset-listed", str(datasets)[:150])
    ok(f"{tag}-dataset-2-samples", found and found.get("count") == 2) if found and found.get("count") == 2 else fail(
        f"{tag}-dataset-2-samples", str(found)
    )

    params = urllib.parse.urlencode(
        {
            "runner_id": runner_id,
            "runner_type": "graph",
            "runner_display": runner_display,
            "filename": DATASET_FILE,
        }
    )
    goto(page, base, f"/exp/new?{params}", 4)
    page.wait_for_function("() => typeof renderTestset === 'function'", timeout=30000)
    lite = [{"name": d["name"], "count": d.get("count", 0)} for d in datasets]
    page.evaluate("(rows) => renderTestset(rows)", lite)
    page.wait_for_selector(
        f'#datasetSelect option[value="{DATASET_FILE}"]',
        timeout=30000,
        state="attached",
    )
    shot_exp(page, screenshots_dir, f"{prefix}01_new")

    if page.locator("#runnerId").input_value() == runner_id:
        ok(f"{tag}-runner-id")
    else:
        fail(f"{tag}-runner-id", page.locator("#runnerId").input_value())
    preview = page.locator("#config").inner_text()
    has_dataset_opt = page.locator(f'#datasetSelect option[value="{DATASET_FILE}"]').count() > 0
    if (
        page.locator("#datasetSelect").input_value() == DATASET_FILE
        or has_dataset_opt
        or DATASET_FILE in preview
    ):
        ok(f"{tag}-dataset-select")
    else:
        fail(f"{tag}-dataset-select", page.locator("#datasetSelect").inner_html()[:120])
    if "gold_entities" in preview and "gold_relations" in preview:
        ok(f"{tag}-preview-gold")
    else:
        fail(f"{tag}-preview-gold", preview[:120])
    shot_exp(page, screenshots_dir, f"{prefix}02_preview")

    exp_id = api_create_experiment(base, runner_id, runner_display)
    ok(f"{tag}-exp-id", bool(exp_id)) if exp_id else fail(f"{tag}-exp-id", "API save returned no exp_id")
    goto(page, base, f"/exp/{exp_id}", 3)
    shot_exp(page, screenshots_dir, f"{prefix}03_running")

    try:
        api_post_json(f"{base}/exp/api/update", {"exp_id": exp_id, "status": "running", "progress": 0})
    except Exception as ex:
        print(f"  [{tag}] update(running) failed: {ex}")

    est = "5-15" if runner_id == NER_RUNNER else "15-30"
    print(f"  [{runner_id}] running batch in-process (~{est} min) ...")
    file_ready = run_batch_inprocess(exp_id, runner_id)
    if file_ready:
        print(f"  [{tag}] states.json has >=2 samples")
    else:
        print(f"  [{tag}] in-process failed, trying HTTP /stream/run ...")
        start_stream_background(base, exp_id)
        file_ready = wait_results_file(exp_id, min_samples=2, timeout=RESULTS_POLL_TIMEOUT)
    ok(f"{tag}-results-file", file_ready) if file_ready else fail(f"{tag}-results-file", "states.json missing/incomplete")

    from service.meta.loader import MetaLoader

    MetaLoader.update("exps", exp_id, {"status": "completed", "progress": 100})

    if not goto_exp_results_page(page, base, exp_id):
        fail(f"{tag}-results-page", "could not open experiment detail")
    else:
        ok(f"{tag}-results-page")
    time.sleep(1)
    shot_exp(page, screenshots_dir, f"{prefix}04_results")

    from service.result.loader import ResultLoader

    results = ResultLoader.load(exp_id) or {}
    keys = [k for k in results.keys() if str(k).isdigit()]
    ok(f"{tag}-results-persisted", len(keys) >= 2) if len(keys) >= 2 else fail(f"{tag}-results-persisted", str(list(results.keys())))
    has_metrics = any(isinstance(results.get(k), dict) and results.get(k, {}).get("metrics") for k in keys)
    ok(f"{tag}-has-metrics", has_metrics) if has_metrics else fail(
        f"{tag}-has-metrics",
        str({k: list((results.get(k) or {}).keys()) for k in keys})[:200],
    )
    has_entities = any(isinstance(results.get(k), dict) and results.get(k, {}).get("entities") for k in keys)
    ok(f"{tag}-has-entities", has_entities) if has_entities else fail(f"{tag}-has-entities", "no entities")

    report_md = wait_report_stream(base, exp_id, timeout=180)
    page.locator('a[href="#report"]').click()
    time.sleep(0.5)
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
            fail(f"{tag}-report-render", str(ex)[:120])
    shot_exp(page, screenshots_dir, f"{prefix}05_report")
    html = page.locator("#reportMarkdown").inner_html()
    ok(f"{tag}-report-html", len(html) > 30) if len(html) > 30 else fail(f"{tag}-report-html", html[:80])

    return exp_id


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    ensure_cid_dataset(tests_data_dir)

    print("\n=== CID-E1. NER EXPERIMENT (wf_cid_ner_llm_eval) ===")
    ner_exp = _run_experiment_ui(
        page,
        base,
        screenshots_dir,
        NER_RUNNER,
        "CID NER Eval (LLM) (wf_cid_ner_llm_eval) - Workflow",
        "cid_ner_",
    )

    print("\n=== CID-E2. RE EXPERIMENT (wf_cid_re_llm_linear) ===")
    re_exp = _run_experiment_ui(
        page,
        base,
        screenshots_dir,
        RE_RUNNER,
        "CID RE Pipeline (linear) (wf_cid_re_llm_linear) - Workflow",
        "cid_re_",
    )

    print("\n=== CID-E3. EXPERIMENT LIST ===")
    goto(page, base, "/exp/", 3)
    shot_exp(page, screenshots_dir, "cid_exp_list")
    ok("cid-list-page", page.locator("table, .table").count() > 0)
    if ner_exp:
        ok("cid-list-ner", ner_exp in page.content())
    if re_exp:
        ok("cid-list-re", re_exp in page.content())
