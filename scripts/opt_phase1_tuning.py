#!/usr/bin/env python3
"""
Phase 1: Tuning 50 dev articles with timeout + resume + report.
Resumes from states.json on disk if available.
"""
from __future__ import annotations

import json
import sys
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNNER_ID = "wf_cid_re_llm_linear"
TUNING_CSV = "cid_dev_tuning_stratified_50.csv"
TEST_CSV = "cdr_test_500.csv"
DEV_SOURCE = ROOT / "comparison" / "data" / "CDR" / "dev.txt"
TIMEOUT_SECS = 300  # 5 minutes per article max

def step(tag, msg): print(f"\n[{tag}] {msg}")
def _progress_bar(current, total, width=50):
    filled = int(width * current / total) if total else 0
    pct = int(100 * current / total) if total else 0
    return f"\r  [{'#' * filled}{'.' * (width - filled)}] {current}/{total} ({pct}%)"

def build_csv():
    from service.dataset_cid import RE_FIELDS, load_source_articles, re_row, stratified_pick, summarize_selection
    from service.entity.test import TestLoader
    articles = load_source_articles(DEV_SOURCE)
    picked_arts, picked_idx = stratified_pick(articles, 50)
    rows = [re_row(a) for a in picked_arts]
    path = TestLoader.save_csv_rows(RUNNER_ID, TUNING_CSV, RE_FIELDS, rows)
    summary = summarize_selection(articles, picked_idx)
    step("1/3", f"CSV: {path} ({len(rows)} articles)")
    print(f"  Relation buckets: {summary['relation_buckets']}")
    print(f"  Entity buckets:   {summary['entity_buckets']}")

def run_tuning() -> str:
    from langchain_core.runnables import RunnableConfig
    from service.chat.commands import create_experiment_record
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader
    from service.result.loader import write_sample_full, write_states_bundle
    from utils.workflow_metrics import compute_workflow_metrics

    # Check if experiment already exists from a partial run
    store: dict[str, dict] = {}
    done: set[str] = set()
    exp_id = ""

    # Check for existing experiment meta
    for f in sorted(Path(ROOT / "meta" / "exps").glob("*.json")):
        try:
            cfg = json.loads(f.read_text(encoding="utf-8"))
            if cfg.get("tuning_dataset") == TUNING_CSV and cfg.get("runner_id") == RUNNER_ID:
                eid = cfg.get("exp_id", "")
                states_path = ROOT / "result" / eid / "states.json"
                if states_path.is_file():
                    prev = json.loads(states_path.read_text(encoding="utf-8"))
                    done = {k for k in prev if k.isdigit() and prev[k].get("metrics")}
                    if done:
                        store = dict(prev)
                        exp_id = eid
                        step("2/3", f"Resuming exp {exp_id}: {len(done)} samples already done")
                        break
        except: pass

    if not exp_id:
        exp = create_experiment_record(RUNNER_ID, TUNING_CSV, "graph", tuning_dataset=TUNING_CSV, test_dataset=TEST_CSV)
        exp_id = exp["exp_id"]
        step("2/3", f"New tuning exp: {exp_id}")

    _, rows = TestLoader.load_by_id_file(RUNNER_ID, TUNING_CSV)
    total = len(rows)
    runner = RunnerLoader.load(RUNNER_ID)

    for idx, row in enumerate(rows, start=1):
        if str(idx) in done:
            continue

        config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
        payload = dict(row)

        # Run with timeout
        try:
            def _run():
                (runner.compiled_graph if hasattr(runner,"compiled_graph") else runner).invoke(payload, config=config)
            if TIMEOUT_SECS > 0:
                import threading
                t = threading.Thread(target=_run, daemon=True)
                t.start()
                t.join(timeout=TIMEOUT_SECS)
                if t.is_alive():
                    raise TimeoutError(f"Article {idx} timed out after {TIMEOUT_SECS}s")
            else:
                _run()
        except Exception as e:
            print(f"\n  [WARN] Article {idx} failed: {e} — skipping")
            store[str(idx)] = {"error": str(e)[:300], "metrics": {"precision": 0,"recall": 0,"f1": 0,"rel_tp": 0,"rel_fp": 0,"rel_fn": 0}}
            continue

        state = runner.get_state(config)
        if state and state.values:
            values = dict(state.values)
            try:
                m = compute_workflow_metrics(RUNNER_ID, payload, values)
                if m: values["metrics"] = m
            except Exception: pass
            store[str(idx)] = values
            write_sample_full(exp_id, idx, values)

        if idx % 10 == 0 or idx == total:
            write_states_bundle(exp_id, store)
        MetaLoader.update("exps", exp_id, {"progress": int(idx/total*100), "status": "running" if idx<total else "completed"})
        print(_progress_bar(idx, total), end="", flush=True)
    print()
    write_states_bundle(exp_id, store)

    # Generate report
    step("3/3", "Generating report")
    from service.experiment_optimize import _build_report_payload, _generate_report
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    exp_cfg["exp_id"] = exp_id
    payload = _build_report_payload(exp_id, exp_cfg)
    report = _generate_report(payload)
    for fn in ["report.md", "report_baseline_test.md", "report_baseline_tuning.md"]:
        (ROOT / "result" / exp_id / fn).write_text(report, encoding="utf-8")

    # Print metrics
    from service.result.loader import ResultLoader
    states = ResultLoader.load(exp_id) or {}
    ks = [int(k) for k in states if k.isdigit()]
    mtp=mfp=mfn=0
    for k in ks:
        m = states[str(k)].get("metrics",{})
        mtp+=int(m.get("rel_tp",0)); mfp+=int(m.get("rel_fp",0)); mfn+=int(m.get("rel_fn",0))
    p=mtp/(mtp+mfp) if mtp+mfp else 0; r=mtp/(mtp+mfn) if mtp+mfn else 0; f=2*p*r/(p+r) if p+r else 0
    print(f"  Tuning F1: P={p:.3f}  R={r:.3f}  F1={f:.3f}  (TP={mtp} FP={mfp} FN={mfn})")
    return exp_id

if __name__ == "__main__":
    print("="*70)
    print("  PHASE 1: Build + Tuning(50) + Report (timeout+resume)")
    print("="*70)
    build_csv()
    run_tuning()
    print("\n" + "="*70)
    print("  PHASE 1 DONE. Tell the agent: \"Continue to Phase 2\"")
    print("="*70)
