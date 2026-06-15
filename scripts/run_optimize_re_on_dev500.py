#!/usr/bin/env python3
"""
Tune RE baseline using ALL 500 dev.txt articles via optimization pipeline.

Flow:
  1) Build cid_dev_all.csv (500 RE rows from dev.txt)  [~1min]
  2) Reuse existing test-500 baseline (c422b97c), set tuning=cid_dev_all.csv
  3) Run pipeline: baseline_tuning → report → agent_refiner → candidate_test → final_report
  4) Backup all results

Usage:
  .\venv\Scripts\python.exe scripts\run_optimize_re_on_dev500.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNNER_ID = "wf_cid_re_llm_linear"
BASE_EXP_ID = "c422b97c-be21-4b6a-968c-c4994229d702"  # completed test-500 baseline
DEV_SOURCE = ROOT / "comparison" / "data" / "CDR" / "dev.txt"
TUNING_CSV = "cid_dev_all.csv"
TEST_CSV = "cdr_test_500.csv"


def step(tag: str, msg: str) -> None:
    print(f"\n[{tag}] {msg}")


def build_tuning_csv() -> None:
    from service.dataset.parsers import load_articles_from_source, row_options_for_source
    from service.dataset.rows import FORMAT_FIELDS, row_re
    from service.entity.test import TestLoader

    opts = row_options_for_source(DEV_SOURCE)
    articles = load_articles_from_source(DEV_SOURCE)
    rows = [row_re(a, **opts) for a in articles]
    path = TestLoader.save_csv_rows(RUNNER_ID, TUNING_CSV, FORMAT_FIELDS["re"], rows)
    step("1/4", f"Built {path} ({len(rows)} articles from dev.txt)")


def update_exp_config() -> None:
    """Set tuning_dataset on the baseline exp so pipeline finds the tuning CSV."""
    from service.meta.loader import MetaLoader

    MetaLoader.update("exps", BASE_EXP_ID, {"tuning_dataset": TUNING_CSV})
    step("2/4", f"Updated {BASE_EXP_ID}: tuning_dataset={TUNING_CSV}")


def run_optimization() -> dict:
    from service.experiment_optimize import run_optimize_loop_by_exp

    step("3/4", "Running full optimization pipeline (may take hours)")
    step("3/4",
         f"  baseline_test  → reuse {BASE_EXP_ID} on {TEST_CSV}\n"
         f"  tuning         → 500 articles from {TUNING_CSV}\n"
         f"  optimize       → agent_refiner → candidate_test → best pick")

    summary = run_optimize_loop_by_exp(
        BASE_EXP_ID,
        max_agent_updates=3,
        tuning_dataset=TUNING_CSV,
        test_dataset=TEST_CSV,
    )
    return summary


def backup_and_report(summary: dict) -> None:
    import shutil
    from service.meta.loader import MetaLoader

    step("4/4", "Saving results and backup")

    candidate_graph = summary.get("final_best_graph_id", "") or summary.get(
        "candidate_graph_id", "")
    final_exp_id = summary.get("final_best_exp_id", "")

    # Backup
    for eid in [BASE_EXP_ID, final_exp_id]:
        src = ROOT / "result" / eid
        if src.is_dir():
            dst = ROOT / "result" / f"{eid}.OPTIMIZED"
            if dst.is_dir():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            step("4/4", f"Backup: {dst}")

    # Print final summary
    print("\n" + "=" * 70)
    print("  OPTIMIZATION COMPLETE")
    print("=" * 70)
    print(f"  Baseline test (test 500): {BASE_EXP_ID}")
    print(f"  Baseline F1 (test 500):   0.532")
    print(f"  Tuning dataset:           {TUNING_CSV} (500 articles)")
    print(f"  Final best exp (test 500): {final_exp_id or 'N/A'}")
    print(f"  Optimized graph:          {candidate_graph or 'N/A'}")
    print(f"  Accepted versions:        {json.dumps(summary.get('accepted_version_map', {}))}")
    print()

    # Compute metrics from final exp if available
    if final_exp_id:
        try:
            from service.result.loader import ResultLoader
            states = ResultLoader.load(final_exp_id) or {}
            ks = [int(k) for k in states if k.isdigit()]
            mtp = mfp = mfn = 0
            for k in ks:
                m = states[str(k)].get("metrics", {})
                mtp += int(m.get("rel_tp", 0))
                mfp += int(m.get("rel_fp", 0))
                mfn += int(m.get("rel_fn", 0))
            if mtp + mfp + mfn:
                p = mtp / (mtp + mfp)
                r = mtp / (mtp + mfn)
                f = 2 * p * r / (p + r) if p + r else 0
                print(f"  Optimized test 500: P={p:.3f}  R={r:.3f}  F1={f:.3f}")
                print(f"    (TP={mtp} FP={mfp} FN={mfn})")
        except Exception as e:
            print(f"  (could not read final metrics: {e})")

    # Save brief summary
    brief = {
        "baseline_exp_id": BASE_EXP_ID,
        "final_best_exp_id": final_exp_id,
        "optimized_graph_id": candidate_graph,
        "accepted_versions": summary.get("accepted_version_map", {}),
    }
    brief_path = ROOT / "result" / "perf34_re_optimize_summary.json"
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Summary: {brief_path}")
    print(f"  Table S17: use optimized graph '{candidate_graph}' on cdr_test_500.csv")


def main() -> int:
    print("=" * 70)
    print("  RE Optimization on dev 500 → test 500")
    print("=" * 70)
    print(f"  Baseline:      {BASE_EXP_ID} (test 500, F1=0.532)")
    print(f"  Tuning source: {DEV_SOURCE} (500 articles)")
    print(f"  Tuning CSV:    {TUNING_CSV}")

    build_tuning_csv()
    update_exp_config()
    summary = run_optimization()
    backup_and_report(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
