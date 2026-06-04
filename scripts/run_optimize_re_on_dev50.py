#!/usr/bin/env python3
"""
Tune RE: stratified 50 dev → show report → confirm → optimize.

Two-phase flow:
  Phase 1: tuning(50) + report → pauses for user confirmation
  Phase 2: agent_refiner → optimize rounds → final test(500)

Usage:
  .\venv\Scripts\python.exe scripts\run_optimize_re_on_dev50.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNNER_ID = "wf_cid_re_llm_linear"
TUNING_CSV = "cid_dev_tuning_stratified_50.csv"
TEST_CSV = "cdr_test_500.csv"
DEV_SOURCE = ROOT / "comparison" / "data" / "CDR" / "dev.txt"


def step(tag: str, msg: str) -> None:
    print(f"\n[{tag}] {msg}")


def _progress_bar(current: int, total: int, *, width: int = 50) -> str:
    filled = int(width * current / total) if total else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * current / total) if total else 0
    return f"\r  [{bar}] {current}/{total} ({pct}%)"


def build_stratified_tuning(size: int = 50) -> None:
    from service.dataset_cid import RE_FIELDS, load_source_articles, re_row
    from service.dataset_cid import stratified_pick, summarize_selection
    from service.entity.test import TestLoader

    articles = load_source_articles(DEV_SOURCE)
    picked_arts, picked_idx = stratified_pick(articles, size)
    rows = [re_row(a) for a in picked_arts]
    path = TestLoader.save_csv_rows(RUNNER_ID, TUNING_CSV, RE_FIELDS, rows)
    summary = summarize_selection(articles, picked_idx)
    step("1/5", f"Tuning CSV: {path} ({len(rows)} articles)")
    print(f"  Relation buckets: {summary['relation_buckets']}")
    print(f"  Entity buckets:   {summary['entity_buckets']}")


def phase1_tuning() -> str:
    """Run 50-dev tuning with per-10 persistence + report. Return exp_id."""
    from langchain_core.runnables import RunnableConfig
    from service.chat.commands import create_experiment_record
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader
    from service.result.loader import write_sample_full, write_states_bundle
    from utils.workflow_metrics import compute_workflow_metrics

    exp = create_experiment_record(
        RUNNER_ID, TUNING_CSV, "graph",
        tuning_dataset=TUNING_CSV,
        test_dataset=TEST_CSV,
    )
    exp_id = exp["exp_id"]
    step("2/5", f"Tuning exp: {exp_id} (dataset={TUNING_CSV})")

    _, rows = TestLoader.load_by_id_file(RUNNER_ID, TUNING_CSV)
    total = len(rows)
    runner = RunnerLoader.load(RUNNER_ID)
    if runner is None:
        raise RuntimeError(f"Runner not found: {RUNNER_ID}")

    step("3/5", "Running 50-dev tuning (persisted every 10)")

    store: dict[str, dict] = {}
    for idx, row in enumerate(rows, start=1):
        config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
        if hasattr(runner, "compiled_graph"):
            runner.compiled_graph.invoke(dict(row), config=config)
        else:
            runner.invoke(dict(row), config=config)

        state = runner.get_state(config)
        if state and state.values:
            values = dict(state.values)
            try:
                metrics = compute_workflow_metrics(RUNNER_ID, dict(row), values)
                if metrics:
                    values["metrics"] = metrics
            except Exception:
                pass
            store[str(idx)] = values
            write_sample_full(exp_id, idx, values)

        # Persist every 10 articles
        if idx % 10 == 0 or idx == total:
            write_states_bundle(exp_id, store)

        MetaLoader.update("exps", exp_id, {
            "progress": int(idx / total * 100) if total else 100,
            "status": "running" if idx < total else "completed",
        })
        print(_progress_bar(idx, total), end="", flush=True)
    print()

    step("3/5", f"Tuning done ({total} samples with metrics)")
    return exp_id


def generate_report(exp_id: str) -> Path:
    from service.experiment_optimize import _build_report_payload, _generate_report

    step("4/5", "Generating tuning report")
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    exp_cfg["exp_id"] = exp_id

    payload = _build_report_payload(exp_id, exp_cfg)
    report = _generate_report(payload)
    report_path = ROOT / "result" / exp_id / "report.md"
    report_path.write_text(report, encoding="utf-8")

    # Also write pipeline-expected filenames
    (ROOT / "result" / exp_id / "report_baseline_test.md").write_text(report, encoding="utf-8")
    (ROOT / "result" / exp_id / "report_baseline_tuning.md").write_text(report, encoding="utf-8")

    step("4/5", f"Report: {report_path}")
    return report_path


def print_report(exp_id: str) -> None:
    """Print key metrics from tuning results."""
    from service.result.loader import ResultLoader

    states = ResultLoader.load(exp_id) or {}
    ks = [int(k) for k in states if k.isdigit()]
    mtp = mfp = mfn = 0
    for k in ks:
        m = states[str(k)].get("metrics", {})
        mtp += int(m.get("rel_tp", 0))
        mfp += int(m.get("rel_fp", 0))
        mfn += int(m.get("rel_fn", 0))
    p = mtp / (mtp + mfp) if mtp + mfp else 0
    r = mtp / (mtp + mfn) if mtp + mfn else 0
    f = 2 * p * r / (p + r) if p + r else 0
    print(f"\n  Tuning (50 dev): P={p:.3f}  R={r:.3f}  F1={f:.3f}  (TP={mtp} FP={mfp} FN={mfn})")


def phase2_optimize() -> dict:
    """Run full pipeline from existing baseline test exp (c422b97c)."""
    from service.experiment_optimize import run_optimize_loop_by_exp
    from service.meta.loader import MetaLoader

    base_id = "c422b97c-be21-4b6a-968c-c4994229d702"
    MetaLoader.update("exps", base_id, {"tuning_dataset": TUNING_CSV, "test_dataset": TEST_CSV, "dataset": TEST_CSV})

    step("5/5", "Running optimization pipeline (agent_refiner → candidate → test 500)")
    step("5/5", "  (may take 2-3 hours)")

    summary = run_optimize_loop_by_exp(
        base_id,
        max_agent_updates=3,
        tuning_dataset=TUNING_CSV,
        test_dataset=TEST_CSV,
    )
    return summary


def backup_and_show(summary: dict) -> None:
    import shutil

    print("\n" + "=" * 70)
    print("  OPTIMIZATION COMPLETE")
    print("=" * 70)

    final_id = summary.get("final_best_exp_id", "")
    for eid in list(filter(None, [final_id])):
        src = ROOT / "result" / eid
        if src.is_dir():
            dst = ROOT / "result" / f"{eid}.OPTIMIZED"
            if dst.is_dir():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  Backup: {dst}")

    cand_graph = summary.get("final_best_graph_id", "") or summary.get("candidate_graph_id", "")

    brief = {"final_best_exp": final_id, "optimized_graph": cand_graph,
             "accepted_versions": summary.get("accepted_version_map", {})}
    brief_path = ROOT / "result" / "perf34_re_optimize_summary.json"
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")

    if final_id:
        try:
            from service.result.loader import ResultLoader
            states = ResultLoader.load(final_id) or {}
            ks = [int(k) for k in states if k.isdigit()]
            mtp = mfp = mfn = 0
            for k in ks:
                m = states[str(k)].get("metrics", {})
                mtp += int(m.get("rel_tp", 0))
                mfp += int(m.get("rel_fp", 0))
                mfn += int(m.get("rel_fn", 0))
            if mtp + mfp + mfn:
                p = mtp / (mtp + mfp); r = mtp / (mtp + mfn); f = 2 * p * r / (p + r) if p + r else 0
                print(f"  Optimized test 500: P={p:.3f}  R={r:.3f}  F1={f:.3f}")
        except Exception as e:
            print(f"  (metrics: {e})")

    print(f"  Optimized graph: {cand_graph or 'N/A'}")
    print(f"  Summary: {brief_path}")


def main() -> int:
    from service.meta.loader import MetaLoader

    print("=" * 70)
    print("  RE OPTIMIZATION")
    print("  Tuning: 50 stratified dev  →  Test: 500 CDR")
    print("=" * 70)

    build_stratified_tuning(50)

    exp_id = phase1_tuning()
    print_report(exp_id)
    report_path = generate_report(exp_id)

    # === WAIT FOR USER CONFIRMATION ===
    print("\n" + "=" * 70)
    print("  PHASE 1 COMPLETE — TUNING REPORT READY")
    print("=" * 70)
    print(f"\n  Report: {report_path}")
    print(f"\n  Review the report above. Type 'y' and press Enter to continue")
    print(f"  with agent_refiner + optimization rounds (2-3 hours).")
    print(f"  Type anything else to abort.")
    print()
    answer = input("  Continue? [y/N]: ").strip().lower()
    if answer != "y":
        print("  Aborted by user. Tuning results saved; resume later with --exp-id.")
        return 1

    summary = phase2_optimize()
    backup_and_show(summary)
    return 0


if __name__ == "__main__":
    from service.meta.loader import MetaLoader
    raise SystemExit(main())
