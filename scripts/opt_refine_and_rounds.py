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

PHASE1_EXP_ID = "c422b97c-be21-4b6a-968c-c4994229d702"
RUNNER_ID = "wf_cid_re_llm_linear"
TUNING_CSV = "cid_dev_tuning_stratified_50.csv"
TEST_CSV = "cid_dev_tuning_stratified_50.csv"  # evaluate optimized on same dev50 split

def bar(cur, tot, w=40):
    f = int(w * cur / tot) if tot else 0
    pct = int(100 * cur / tot) if tot else 0
    return f"\r  [{'#' * f}{'.' * (w - f)}] {cur}/{tot} ({pct}%)"

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2: report → refiner → optimize rounds")
    parser.add_argument("--phase1-exp-id", default=PHASE1_EXP_ID)
    parser.add_argument("--tuning-csv", default=TUNING_CSV)
    parser.add_argument("--test-csv", default=TEST_CSV, help="Final eval dataset (default: dev50)")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    phase1_exp_id = args.phase1_exp_id.strip()
    tuning_csv = args.tuning_csv.strip()
    test_csv = args.test_csv.strip()

    from service.meta.loader import MetaLoader
    from service.experiment_optimize import (
        _build_report_payload, _build_exp_cfg, _generate_report, _run_refiner,
        _run_experiment, _avg_metrics, _create_candidate_graph,
        _apply_modifications, _restore_agents_after_negative_delta,
        _snapshot_accepted_modifications,
    )
    from service.optimize_suggestion_filter import filter_disallowed_modifications

    tag = datetime.now().strftime("%Y%m%d_%H%M%S")

    result_dir = ROOT / "result" / phase1_exp_id
    result_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Report
    print(f"[1] Report (phase1={phase1_exp_id})...")
    exp_cfg = MetaLoader.load("exps", phase1_exp_id) or {}
    exp_cfg["exp_id"] = phase1_exp_id
    payload = _build_report_payload(phase1_exp_id, exp_cfg)
    baseline_report = _generate_report(payload)
    for fn in ("report.md", "report_baseline_tuning.md", "report_refiner_input.md"):
        (result_dir / fn).write_text(baseline_report, encoding="utf-8")
    print(f"  saved: {result_dir / 'report.md'}")

    if args.report_only:
        print("  --report-only: stopping before refiner.")
        return

    # Step 2: Refiner
    print("[2] agent_refiner...")
    raw_mods = _run_refiner(baseline_report, payload, max_updates=10)
    mods, _ = filter_disallowed_modifications([
        m for m in raw_mods if isinstance(m, dict) and str(m.get("target_agent_id") or "").strip()
    ])
    print(f"  {len(mods)} suggestions")

    if not mods:
        print("  No modifications. Done.")
        return

    (result_dir / "refiner_suggestions.json").write_text(
        json.dumps({"modifications": mods}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    cumulative_version_map: dict[str, str] = {}
    current_best_metrics = _avg_metrics(phase1_exp_id)

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
            dataset=tuning_csv, tuning_dataset=tuning_csv, test_dataset=test_csv,
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
    print(f"  Baseline tuning F1: {_avg_metrics(phase1_exp_id).get('f1', 0):.4f}")
    print(f"  Best candidate F1:  {current_best_metrics.get('f1', 0):.4f}")

    final_graph = ""
    final_exp_id = ""
    if cumulative_version_map:
        final_graph = f"{RUNNER_ID}_opt_{tag}"
        try:
            final_graph = _create_candidate_graph(
                RUNNER_ID, cumulative_version_map, final_graph,
                datasets=[tuning_csv, test_csv],
            )
        except Exception as e:
            print(f"  Graph creation failed: {e}")

        if final_graph:
            print(f"\n[3] Final optimized run on {test_csv}...")
            final_exp_id = f"opt_best_{tag}_{uuid.uuid4().hex[:8]}"
            final_cfg = _build_exp_cfg(
                exp_id=final_exp_id,
                runner_id=final_graph,
                dataset=test_csv,
                tuning_dataset=tuning_csv,
                test_dataset=test_csv,
                runner_type="graph",
            )
            MetaLoader.dump("exps", final_exp_id, final_cfg)
            _run_experiment(final_cfg)
            final_metrics = _avg_metrics(final_exp_id)
            print(f"  Optimized dev50 F1: {final_metrics.get('f1', 0):.4f}")
            current_best_metrics = final_metrics

    print(f"\n  Optimized graph: {final_graph or 'none'}")
    print(f"  Final exp: {final_exp_id or 'none'}")
    print(f"  Accepted versions: {json.dumps(cumulative_version_map)}")

    summary = {
        "phase1_exp_id": phase1_exp_id,
        "optimized_graph_id": final_graph,
        "final_exp_id": final_exp_id,
        "accepted_versions": cumulative_version_map,
        "baseline_f1": _avg_metrics(phase1_exp_id).get("f1", 0),
        "best_f1": current_best_metrics.get("f1", 0),
        "test_csv": test_csv,
    }
    (result_dir / "optimize_rounds_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8",
    )

if __name__ == "__main__":
    main()
