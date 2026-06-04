#!/usr/bin/env python3
"""Phase 2: Run full optimization pipeline (agent_refiner → candidate → test 500)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_EXP_ID = "c422b97c-be21-4b6a-968c-c4994229d702"
TUNING_CSV = "cid_dev_tuning_stratified_50.csv"
TEST_CSV = "cdr_test_500.csv"
RUNNER_ID = "wf_cid_re_llm_linear"


def main():
    from service.meta.loader import MetaLoader
    from service.experiment_optimize import run_optimize_loop_by_exp

    print("=" * 70)
    print("  PHASE 2: Optimization Pipeline")
    print("=" * 70)
    print(f"  Baseline:      {BASE_EXP_ID} (test 500, F1=0.532)")
    print(f"  Tuning:        {TUNING_CSV} (50 stratified dev)")
    print(f"  Test:          {TEST_CSV} (500 CDR)")

    # Ensure experiment config points to the right datasets
    MetaLoader.update("exps", BASE_EXP_ID, {
        "tuning_dataset": TUNING_CSV,
        "test_dataset": TEST_CSV,
        "dataset": TEST_CSV,
    })

    print("\n  Pipeline stages:")
    print("    - Baseline test (reuse c422b97c, no re-run)")
    print("    - Baseline tuning (50 dev) — will re-run")
    print("    - Report → agent_refiner → optimize rounds → test 500")
    print("    - May take 2-3 hours")
    print()

    summary = run_optimize_loop_by_exp(
        BASE_EXP_ID,
        max_agent_updates=3,
        tuning_dataset=TUNING_CSV,
        test_dataset=TEST_CSV,
    )

    # Print results
    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETE")
    print("=" * 70)
    print(json.dumps(summary, indent=2, default=str))

    # Backup
    import shutil
    final_id = summary.get("final_best_exp_id", "")
    for eid in list(filter(None, [final_id])):
        src = ROOT / "result" / eid
        if src.is_dir():
            dst = ROOT / "result" / f"{eid}.OPTIMIZED"
            if dst.is_dir(): shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"\n  Backup: {dst}")

    if final_id:
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
            p = mtp / (mtp + mfp)
            r = mtp / (mtp + mfn)
            f = 2 * p * r / (p + r) if p + r else 0
            print(f"\n  OPTIMIZED TEST 500:  P={p:.3f}  R={r:.3f}  F1={f:.3f}")
            print(f"    (TP={mtp}  FP={mfp}  FN={mfn})")

    cand_graph = summary.get("final_best_graph_id", "") or summary.get("candidate_graph_id", "")
    print(f"\n  Optimized graph: {cand_graph}")
    print("  Use for Table S17.")


if __name__ == "__main__":
    main()
