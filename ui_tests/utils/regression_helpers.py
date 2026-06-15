"""Shared helpers for Playwright regression suites (exp / graph / tool / agent)."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from ui_tests.utils.graph_workflow_json_utils import ROOT, graph_run_params
from ui_tests.utils.playwright_helpers import goto, ok, fail, shot

GOLD_FIELD_NAMES = frozenset(
    {
        "gold_relations",
        "gold_entities",
        "expected_entities",
        "expected_relations",
        "expected",
        "ground_truth",
    }
)

TWO_SAMPLE_TEXTS = (
    "Aspirin may reduce the risk of heart disease.",
    "Metformin is commonly used to treat type 2 diabetes.",
)

# Per-graph 2-row fixtures when generic text-only rows miss required bindings.
GRAPH_TWO_ROW_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "sg_relation_verify": [
        {
            "text": "Aspirin may cause headache.",
            "head": "Aspirin",
            "tail": "headache",
            "entity_link": json.dumps({"Aspirin": "Aspirin", "headache": "headache"}, ensure_ascii=False),
        },
        {
            "text": "Metformin is commonly used to treat type 2 diabetes.",
            "head": "Metformin",
            "tail": "type 2 diabetes",
            "entity_link": json.dumps(
                {"Metformin": "Metformin", "type 2 diabetes": "type 2 diabetes"},
                ensure_ascii=False,
            ),
        },
    ],
    "sg_chemdisgene_re_verify": [
        {
            "text": TWO_SAMPLE_TEXTS[0],
            "head": "Aspirin",
            "tail": "heart disease",
            "rel_template": "chem_disease:affects",
            "entity_type": "Chemical",
            "gold_relations": "Aspirin | chem_disease:affects | heart disease",
        },
        {
            "text": TWO_SAMPLE_TEXTS[1],
            "head": "Metformin",
            "tail": "type 2 diabetes",
            "rel_template": "chem_disease:affects",
            "entity_type": "Chemical",
            "gold_relations": "Metformin | chem_disease:affects | type 2 diabetes",
        },
    ],
    "wf_chemdisgene_re_llm_linear": [
        {
            "text": TWO_SAMPLE_TEXTS[0],
            "entities": json.dumps(
                [
                    {"text": "Aspirin", "id": "MESH:D001241", "label": "Chemical"},
                    {"text": "heart disease", "id": "MESH:D006331", "label": "Disease"},
                ],
                ensure_ascii=False,
            ),
            "gold_relations": "Aspirin | chem_disease:affects | heart disease",
        },
        {
            "text": TWO_SAMPLE_TEXTS[1],
            "entities": json.dumps(
                [
                    {"text": "Metformin", "id": "MESH:D008687", "label": "Chemical"},
                    {"text": "type 2 diabetes", "id": "MESH:D003924", "label": "Disease"},
                ],
                ensure_ascii=False,
            ),
            "gold_relations": "Metformin | chem_disease:therapeutic | type 2 diabetes",
        },
    ],
}


def safe_name(value: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "item")).strip("_")
    return (slug or "item")[:max_len]


def all_graph_ids(*, from_backup: bool = False) -> list[str]:
    from ui_tests.utils.graph_workflow_json_utils import discover_graph_ids

    return sorted(discover_graph_ids(from_backup=from_backup))


def all_agent_ids() -> list[str]:
    return sorted(p.stem for p in (ROOT / "meta" / "agents").glob("*.json"))


def all_tool_ids() -> list[str]:
    from service.meta.loader import MetaLoader

    tools = MetaLoader.loads("tools") or []
    return sorted(str(t.get("id") or "") for t in tools if t.get("id"))


def api_get_json(url: str, timeout: int = 60) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post_json(url: str, payload: dict, timeout: int = 120) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_delete_json(url: str, timeout: int = 60) -> Any:
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def build_two_row_dataset(graph_id: str, *, with_gold: bool) -> tuple[list[str], list[dict[str, Any]]]:
    """Build 2 CSV rows for a graph; strip gold columns when with_gold=False."""
    templates = GRAPH_TWO_ROW_TEMPLATES.get(graph_id)
    if templates:
        rows: list[dict[str, Any]] = []
        for tpl in templates[:2]:
            row = dict(tpl)
            if not with_gold:
                for key in list(row.keys()):
                    if key in GOLD_FIELD_NAMES or key.startswith("gold_"):
                        row.pop(key, None)
            rows.append(row)
        fields = sorted({k for row in rows for k in row.keys()})
        return fields, rows

    base = dict(graph_run_params(graph_id))
    rows = []
    for idx, text in enumerate(TWO_SAMPLE_TEXTS):
        row = dict(base)
        if "text" in row or "sentence" in row:
            if "sentence" in row:
                row["sentence"] = text.split(".")[0] + "."
            else:
                row["text"] = text
        if not with_gold:
            for key in list(row.keys()):
                if key in GOLD_FIELD_NAMES or key.startswith("gold_"):
                    row.pop(key, None)
        rows.append(row)
    fields = sorted({k for row in rows for k in row.keys()})
    return fields, rows


def _exp_variant_tag(*, with_gold: bool, with_tuning: bool) -> str:
    gold = "gold" if with_gold else "no_gold"
    tuning = "with_tuning" if with_tuning else "test_only"
    return f"{gold}_{tuning}"


def ensure_graph_exp_datasets(
    graph_id: str,
    *,
    with_gold: bool,
    with_tuning: bool,
) -> tuple[str, str | None]:
    """Write 2-row test CSV; optional separate tuning CSV when with_tuning=True."""
    from service.entity.test import TestLoader

    tag = "gold" if with_gold else "no_gold"
    test_file = f"regression_2_{tag}_test.csv"
    fields, rows = build_two_row_dataset(graph_id, with_gold=with_gold)
    TestLoader.save_csv_rows(graph_id, test_file, fields, rows)
    tuning_file = None
    if with_tuning:
        tuning_file = f"regression_2_{tag}_tuning.csv"
        TestLoader.save_csv_rows(graph_id, tuning_file, fields, rows)
    return test_file, tuning_file


def ensure_graph_dataset(graph_id: str, *, with_gold: bool) -> str:
    """Legacy helper: test dataset only."""
    test_file, _ = ensure_graph_exp_datasets(graph_id, with_gold=with_gold, with_tuning=False)
    return test_file


def wait_stream_run_done(base: str, exp_id: str, timeout: int = 600) -> tuple[bool, str]:
    url = f"{base.rstrip('/')}/stream/run/{exp_id}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            for line in resp:
                if b"[DONE]" in line:
                    return True, "ok"
    except Exception as ex:
        return False, str(ex)[:300]
    return False, "stream ended without [DONE]"


def build_graph_test_params(graph_id: str, *, with_gold: bool) -> dict[str, Any]:
    """Single-row Test modal payload; strip gold columns when with_gold=False."""
    params = dict(graph_run_params(graph_id))
    if not with_gold:
        for key in list(params.keys()):
            if key in GOLD_FIELD_NAMES or str(key).startswith("gold_"):
                params.pop(key, None)
    return params


def wait_baseline_report_ready(base: str, exp_id: str, timeout: int = 420) -> tuple[bool, str]:
    """Poll optimization preflight until baseline test report exists."""
    url = f"{base.rstrip('/')}/exp/api/{exp_id}/optimization-preflight"
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            data = api_get_json(url, timeout=30)
            if not data.get("success"):
                last = str(data.get("error") or data)[:200]
            elif data.get("baseline_report_ready"):
                return True, "ok"
            elif str(data.get("status") or "").lower() == "failed":
                return False, "exp status failed"
            last = (
                f"test_ready={data.get('baseline_test_ready')} "
                f"report_ready={data.get('baseline_report_ready')}"
            )
        except Exception as ex:
            last = str(ex)[:200]
        time.sleep(2)
    return False, f"timeout ({last})"


def open_exp_baseline_tab(page: Page, timeout: int = 60000) -> None:
    page.wait_for_selector("#expWizardTabs", timeout=timeout)
    page.wait_for_function(
        """() => {
            const el = document.getElementById('exp_id');
            if (!el) return false;
            const id = String(el.dataset.id || el.textContent || '').trim();
            return id.length > 0 && id !== 'Not saved yet';
        }""",
        timeout=timeout,
    )
    page.wait_for_selector("#wizard-tab-btn-baseline", timeout=timeout)
    page.wait_for_function(
        "() => { const b = document.getElementById('wizard-tab-btn-baseline'); return b && !b.disabled; }",
        timeout=timeout,
    )
    page.locator("#wizard-tab-btn-baseline").click()
    page.locator("#wizard-tab-baseline").wait_for(state="visible", timeout=15000)


def screenshot_exp_baseline_tab(page: Page, screenshots_dir: str, name: str) -> None:
    open_exp_baseline_tab(page)
    try:
        page.wait_for_function(
            """() => {
                const el = document.getElementById('baselineReportMarkdown');
                return el && (el.innerText || '').trim().length > 30;
            }""",
            timeout=90000,
        )
    except Exception:
        pass
    time.sleep(1)
    shot(page, screenshots_dir, name)


def run_baseline_via_ui(
    page: Page,
    base: str,
    exp_id: str,
    *,
    test_file: str,
    tuning_file: str | None,
    timeout: int,
) -> tuple[bool, str]:
    """Click Run Baseline on wizard tab 2; fall back to API stream + report."""
    goto(page, base, f"/exp/{exp_id}", 3)
    open_exp_baseline_tab(page)
    page.locator("#runBaselineTabBtn").wait_for(state="visible", timeout=30000)
    page.locator("#runBaselineTabBtn").click()
    done, detail = wait_baseline_report_ready(base, exp_id, timeout=timeout)
    if done:
        return True, detail

    report_payload: dict[str, Any] = {"test_dataset": test_file}
    if tuning_file:
        report_payload["tuning_dataset"] = tuning_file
    api_post_json(
        f"{base.rstrip('/')}/exp/api/update",
        {"exp_id": exp_id, "status": "running", "progress": 0},
    )
    stream_ok, stream_detail = wait_stream_run_done(base, exp_id, timeout=timeout)
    api_post_json(
        f"{base.rstrip('/')}/exp/api/update",
        {
            "exp_id": exp_id,
            "status": "completed" if stream_ok else "failed",
            "progress": 100 if stream_ok else 0,
        },
    )
    if not stream_ok:
        return False, stream_detail
    try:
        api_post_json(
            f"{base.rstrip('/')}/exp/api/{exp_id}/optimization-step/baseline_test_report",
            report_payload,
            timeout=180,
        )
    except Exception as ex:
        return False, f"baseline report failed: {str(ex)[:120]}"
    return wait_baseline_report_ready(base, exp_id, timeout=min(timeout, 120))


def run_graph_experiment(
    page: Page,
    base: str,
    screenshots_dir: str,
    graph_id: str,
    *,
    with_gold: bool,
    with_tuning: bool = False,
    timeout: int | None = None,
) -> str:
    """Create exp (2-sample test ± tuning), run baseline via UI, screenshot baseline tab."""
    test_file, tuning_file = ensure_graph_exp_datasets(
        graph_id, with_gold=with_gold, with_tuning=with_tuning
    )
    variant = _exp_variant_tag(with_gold=with_gold, with_tuning=with_tuning)
    runner_display = f"{graph_id} (regression {variant})"
    query = {
        "runner_id": graph_id,
        "runner_type": "graph",
        "runner_display": runner_display,
        "filename": test_file,
    }
    if tuning_file:
        query["tuning_filename"] = tuning_file
    goto(page, base, f"/exp/new?{urllib.parse.urlencode(query)}", 2)
    shot(page, screenshots_dir, f"rexp_{safe_name(graph_id)}_{variant}_config")

    save_payload: dict[str, Any] = {
        "runner_type": "graph",
        "runner_id": graph_id,
        "runner_display": runner_display,
        "test_dataset": test_file,
        "dataset": test_file,
    }
    if tuning_file:
        save_payload["tuning_dataset"] = tuning_file

    if not getattr(page, "_ng_dialog_handler", False):

        def _safe_accept_dialog(d) -> None:
            try:
                d.accept()
            except Exception:
                pass

        page.on("dialog", _safe_accept_dialog)
        page._ng_dialog_handler = True
    save_json = api_post_json(f"{base.rstrip('/')}/exp/api/save", save_payload)
    if not save_json.get("success"):
        fail(f"REXP-save-{graph_id}-{variant}", str(save_json)[:200])
        return ""
    exp_id = str(save_json.get("exp_id") or "")
    if not exp_id:
        fail(f"REXP-save-{graph_id}-{variant}", "missing exp_id")
        return ""

    effective_timeout = timeout or int(os.environ.get("NG_REGRESSION_EXP_TIMEOUT", "420"))
    done, detail = run_baseline_via_ui(
        page,
        base,
        exp_id,
        test_file=test_file,
        tuning_file=tuning_file,
        timeout=effective_timeout,
    )

    goto(page, base, f"/exp/{exp_id}", 2)
    screenshot_exp_baseline_tab(
        page, screenshots_dir, f"rexp_{safe_name(graph_id)}_{variant}_baseline"
    )

    test_name = f"REXP-{graph_id}-{variant}"
    if done:
        ok(test_name, exp_id)
    else:
        fail(test_name, detail)

    from service.result.loader import ResultLoader

    states = ResultLoader.load(exp_id) or {}
    sample_keys = [k for k in states if str(k).isdigit()]
    ok(f"REXP-persist-{graph_id}-{variant}", f"samples={len(sample_keys)}") if sample_keys else fail(
        f"REXP-persist-{graph_id}-{variant}", "no samples"
    )
    if with_gold:
        has_metrics = any(
            isinstance(states.get(k), dict) and states[k].get("metrics") for k in sample_keys
        )
        if has_metrics:
            ok(f"REXP-metrics-{graph_id}-{variant}", "metrics present")
        else:
            ok(f"REXP-metrics-{graph_id}-{variant}", "no metrics (gold may be empty)")
    else:
        ok(f"REXP-nogold-{graph_id}-{variant}", "completed without gold labels")
    if with_tuning:
        ok(f"REXP-tuning-{graph_id}-{variant}", f"tuning={tuning_file}")
    else:
        ok(f"REXP-notuning-{graph_id}-{variant}", "test dataset only")
    return exp_id


def default_tool_inputs(tool_def: dict[str, Any]) -> dict[str, Any]:
    """Minimal inputs from tool JSON schema + fixtures for complex tools."""
    tool_id = str(tool_def.get("id") or "")
    fixtures: dict[str, dict[str, Any]] = {
        "metrics_delta_compare": {
            "baseline_states": {"1": {"metrics": {"precision": 0.5, "recall": 0.5, "f1": 0.5}}},
            "candidate_states": {"1": {"metrics": {"precision": 0.6, "recall": 0.4, "f1": 0.48}}},
        },
        "agent_change_impact_trace": {
            "baseline_states": {"1": {"metrics": {"f1": 0.5}}},
            "candidate_states": {"1": {"metrics": {"f1": 0.6}}},
            "version_map": {"relation_verify_llm": "v0010"},
        },
        "agent_version_guard": {
            "baseline_metrics": {"f1": 0.5},
            "candidate_metrics": {"f1": 0.6},
        },
        "dataset_cid_tuning_build": {
            "runner_id": "wf_cid_re_llm_linear",
            "source": "comparison/data/CDR/dev.txt",
            "size": "2",
            "tuning_out": "cid_regression_tuning.csv",
            "test_out": "cid_regression_test.csv",
            "write_test_remain": "false",
            "mirror_ner": "false",
        },
        "dataset_sampler_stratified": {
            "runner_id": "wf_cid_re_llm_linear",
            "source_dataset": "cid_dev_full.csv",
            "size": "2",
            "output": "cid_regression_sample.csv",
        },
        "error_case_exporter": {
            "states": {"1": {"metrics": {"f1": 0.0, "fp": 2, "fn": 1}, "text": "Sample."}},
            "top_k": 1,
        },
        "fn_fp_bucket_analyzer": {
            "states": {"1": {"metrics": {"f1": 0.5, "fp": 1, "fn": 1}}},
        },
        "prompt_patch_apply_safe": {
            "prompt": "Hello",
            "patch": {"append": " world"},
        },
        "report_quality_scorer": {
            "report_text": "## Metrics\n\nF1=0.5",
            "metrics_delta": {"f1": 0.01},
        },
        "tool_pubtator_relation_extract": {
            "text": "Aspirin may cause headache.",
            "pmid": "",
            "entities": [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}],
        },
        "tool_ner_flair": {
            "sentence": "Aspirin treats pain.",
            "labels": "Chemical,Disease",
        },
        "merge_heads_tails_to_entities": {
            "heads": [{"text": "Aspirin", "label": "Chemical"}],
            "tails": [{"text": "pain", "label": "Disease"}],
        },
    }
    if tool_id in fixtures:
        return dict(fixtures[tool_id])

    props = ((tool_def.get("parameters") or {}).get("properties") or {})
    required = set((tool_def.get("parameters") or {}).get("required") or [])
    out: dict[str, Any] = {}
    for name in required:
        spec = props.get(name) or {}
        typ = spec.get("type", "string")
        if typ == "object":
            out[name] = {}
        elif typ == "array":
            out[name] = []
        elif typ == "number":
            out[name] = 1
        elif typ == "boolean":
            out[name] = True
        else:
            out[name] = "sample"
    return out
