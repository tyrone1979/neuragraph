#!/usr/bin/env python3
"""
Phase 2: Refiner + Optimize Rounds (resumes from Round 2 if Round 1 done).
"""
from __future__ import annotations

import json, shutil, uuid, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PHASE1_EXP_ID = "b47e0d53-aee9-4f3d-b7df-3ef18616a93a"
RUNNER_ID = "wf_cid_re_llm_linear"
TUNING_CSV = "cid_dev_tuning_stratified_50.csv"
TEST_CSV = "cdr_test_500.csv"

def bar(cur, tot, w=40):
    f = int(w * cur / tot) if tot else 0
    pct = int(100 * cur / tot) if tot else 0
    return f"\r  [{'#' * f}{'.' * (w - f)}] {cur}/{tot} ({pct}%)"

def main():
    from service.meta.loader import MetaLoader
    from service.experiment_optimize import (
        _build_report_payload, _build_exp_cfg, _generate_report, _run_refiner,
        _run_experiment, _avg_metrics, _create_candidate_graph,
        _apply_modifications, _restore_agents_after_negative_delta,
        _snapshot_accepted_modifications,
    )
    from service.optimize_suggestion_filter import filter_disallowed_modifications

    tag = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Step 1 + 2: Report + Refiner
    print("[1] Report + refiner...")
    exp_cfg = MetaLoader.load("exps", PHASE1_EXP_ID) or {}
    exp_cfg["exp_id"] = PHASE1_EXP_ID
    payload = _build_report_payload(PHASE1_EXP_ID, exp_cfg)
    baseline_report = _generate_report(payload)
    raw_mods = _run_refiner(baseline_report, payload, max_updates=10)
    mods, _ = filter_disallowed_modifications([
        m for m in raw_mods if isinstance(m, dict) and str(m.get("target_agent_id") or "").strip()
    ])
    print(f"  {len(mods)} suggestions")

    if not mods:
        print("  No modifications. Done.")
        return

    cumulative_version_map: dict[str, str] = {}
    current_best_metrics = _avg_metrics(PHASE1_EXP_ID)

    for idx, mod in enumerate(mods, start=1):
        target = str(mod.get("target_agent_id") or "").strip()
        print(f"\n  Round {idx}/{len(mods)}: {target}  [{bar(idx, len(mods))}]")
        print(f"    {mod.get('rationale', '')[:150]}...")

        _vmap, originals, applied = _apply_modifications(
            [mod], max_updates=1, change_note_prefix=f"opt_loop {tag} r{idx}",
        )
        if not applied:
            print(f"    skipped (no effective change)")
            continue

        cand_id = f"opt_cand_{tag}_r{idx}_{uuid.uuid4().hex[:8]}"
        cand_cfg = _build_exp_cfg(
            exp_id=cand_id, runner_id=RUNNER_ID,
            dataset=TUNING_CSV, tuning_dataset=TUNING_CSV, test_dataset=TEST_CSV,
            runner_type="graph",
        )
        MetaLoader.dump("exps", cand_id, cand_cfg)
        print(f"    running {cand_id} on 50-dev...")
        _run_experiment(cand_cfg)

        cand = _avg_metrics(cand_id)
        base_f1 = current_best_metrics.get("f1", 0)
        cand_f1 = cand.get("f1", 0)
        delta = cand_f1 - base_f1
        print(f"    base F1={base_f1:.4f}  cand F1={cand_f1:.4f}  d={delta:+.4f}")

        if delta > 0:
            print(f"    + ACCEPTED")
            vm = _snapshot_accepted_modifications(
                applied, [mod], max_updates=1, change_note_prefix=f"opt_loop {tag} r{idx}",
            )
            cumulative_version_map.update(vm)
            current_best_metrics = cand
        else:
            print(f"    - REVERTED")
            _restore_agents_after_negative_delta(
                originals, reason=f"non-positive f1 delta ({delta:.4f})",
            )

    # Done — show results
    print("\n" + "=" * 70)
    print("  DONE. Optimized graph info:")
    print("=" * 70)
    print(f"  Baseline tuning F1: {_avg_metrics(PHASE1_EXP_ID).get('f1', 0):.4f}")
    print(f"  Best candidate F1:  {current_best_metrics.get('f1', 0):.4f}")

    final_graph = ""
    if cumulative_version_map:
        final_graph = f"{RUNNER_ID}_opt_{tag}"
        try:
            final_graph = _create_candidate_graph(
                RUNNER_ID, cumulative_version_map, final_graph,
                datasets=[TUNING_CSV, TEST_CSV],
            )
        except Exception as e:
            print(f"  Graph creation failed: {e}")

    print(f"\n  Optimized graph: {final_graph or 'none'}")
    print(f"  Accepted versions: {json.dumps(cumulative_version_map)}")

    summary = {
        "phase1_exp_id": PHASE1_EXP_ID,
        "optimized_graph_id": final_graph,
        "accepted_versions": cumulative_version_map,
    }
    Path(ROOT / "result" / PHASE1_EXP_ID / "optimize_rounds_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    print(f"\n  Next: 'Run optimized test on 500'")

if __name__ == "__main__":
    main()
