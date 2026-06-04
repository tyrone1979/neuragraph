#!/usr/bin/env python3
"""
Phase 2a: Use Phase 1 tuning results → agent_refiner → show suggestions.
Only runs refiner (no candidate tests). User decides next step.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE1_EXP_ID = "b47e0d53-aee9-4f3d-b7df-3ef18616a93a"  # 50-dev tuning done in Phase 1
TUNING_CSV = "cid_dev_tuning_stratified_50.csv"
TEST_CSV = "cdr_test_500.csv"


def main():
    from service.meta.loader import MetaLoader
    from service.experiment_optimize import (
        _build_report_payload,
        _generate_report,
        _run_refiner,
        filter_disallowed_modifications,
        _apply_modifications,
    )

    print("=" * 70)
    print("  AGENT REFINER (using Phase 1 tuning results)")
    print("=" * 70)
    print(f"  Phase 1 exp: {PHASE1_EXP_ID} (50 dev, F1=0.553)")
    print(f"  Step: tuning report → agent_refiner → show suggestions")

    # Step 1: Build payload from Phase 1 results
    exp_cfg = MetaLoader.load("exps", PHASE1_EXP_ID) or {}
    exp_cfg["exp_id"] = PHASE1_EXP_ID
    print("\n  Building report payload from Phase 1...")
    payload = _build_report_payload(PHASE1_EXP_ID, exp_cfg)

    # Step 2: Generate report
    print("  Generating tuning report...")
    report = _generate_report(payload)
    report_path = ROOT / "result" / PHASE1_EXP_ID / "report_refiner_input.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  Report: {report_path}")

    # Step 3: Call agent_refiner
    print("  Calling agent_refiner...")
    raw_mods = _run_refiner(report, payload, max_updates=10)
    mods, filtered = filter_disallowed_modifications([
        m for m in raw_mods
        if isinstance(m, dict) and str(m.get("target_agent_id") or "").strip()
    ])

    print(f"\n  Refiner returned {len(mods)} valid suggestions "
          f"({len(filtered)} filtered out)")

    # Step 4: Show each suggestion
    for i, mod in enumerate(mods, 1):
        print(f"\n{'─'*70}")
        print(f"  SUGGESTION {i}/{len(mods)}")
        print(f"{'─'*70}")
        print(f"  Target:       {mod.get('target_agent_id', '?')}")
        print(f"  Rationale:    {mod.get('rationale', '')[:300]}")
        if mod.get("prompt_system_append"):
            print(f"  System append: {mod['prompt_system_append'][:200]}")
        if mod.get("prompt_human_append"):
            print(f"  Human append:  {mod['prompt_human_append'][:200]}")
        if mod.get("prompt_system_replace"):
            print(f"  System replace: {mod['prompt_system_replace'][:200]}")
        if mod.get("prompt_human_replace"):
            print(f"  Human replace:  {mod['prompt_human_replace'][:200]}")
        if mod.get("process_append"):
            print(f"  Process append: {mod['process_append'][:200]}")
        if mod.get("process_replace"):
            print(f"  Process replace: {mod['process_replace'][:200]}")

    # Step 5: Save suggestions for later use
    suggestions_path = ROOT / "result" / PHASE1_EXP_ID / "refiner_suggestions.json"
    suggestions_path.write_text(
        json.dumps({"modifications": mods, "filtered_count": len(filtered)},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  Suggestions saved: {suggestions_path}")
    print(f"\n{'='*70}")
    print(f"  REFINER DONE. Review suggestions above.")
    print(f"  Say: 'Apply suggestions and test' to continue.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
