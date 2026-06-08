#!/usr/bin/env python3
"""Compare partial/full RE metrics to Table S17 in doc/SUPPLEMENTARY.md."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Table S17 — oracle-entity test 500 (historical rows in supplementary)
S17_BASELINE = {
    "label": "S17 baseline (wf_cid_re_llm_linear, historical)",
    "micro": (0.427, 0.705, 0.532),
    "macro": (0.482, 0.729, 0.539),
    "tp": 752,
    "fp": 1010,
    "fn": 314,
}
S17_OPTIMIZED = {
    "label": "S17 optimized (wf_cid_re_llm_linear_opt_20260604, historical)",
    "micro": (0.434, 0.726, 0.544),
    "macro": (0.487, 0.725, 0.543),
    "tp": 774,
    "fp": 1008,
    "fn": 292,
}


def _load_aggregate():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "agg", ROOT / "scripts" / "_aggregate_exp_metrics.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def metrics_from_states(states_path: Path) -> dict[str, Any]:
    mod = _load_aggregate()
    data = json.loads(states_path.read_text(encoding="utf-8"))
    n_metrics = 0
    tp = fp = fn = 0
    for k, v in data.items():
        if not str(k).isdigit() or not isinstance(v, dict):
            continue
        m = mod.sample_metrics(v)
        if not m:
            continue
        n_metrics += 1
        tp += int(m.get("rel_tp") or m.get("tp") or 0)
        fp += int(m.get("rel_fp") or m.get("fp") or 0)
        fn += int(m.get("rel_fn") or m.get("fn") or 0)
    agg = mod.aggregate_states(states_path)
    return {
        "n_with_metrics": n_metrics,
        "micro": agg.get("micro"),
        "macro": agg.get("macro"),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _delta(cur: float | None, ref: float) -> str:
    if cur is None:
        return "—"
    d = round(cur - ref, 3)
    return f"{d:+.3f}"


def format_s17_report(
    cur: dict[str, Any],
    *,
    milestone: int | None = None,
    total: int = 500,
    compare_baseline: bool = True,
    compare_optimized: bool = True,
) -> str:
    lines: list[str] = []
    tag = f"@{milestone}/{total}" if milestone else f"n={cur.get('n_with_metrics', '?')}/{total}"
    lines.append(f"=== CID-RE metrics {tag} ===")
    micro = cur.get("micro") or (None, None, None)
    macro = cur.get("macro") or (None, None, None)
    lines.append(
        f"  Current  micro P/R/F1: {micro[0]}/{micro[1]}/{micro[2]}  "
        f"macro P/R/F1: {macro[0]}/{macro[1]}/{macro[2]}  "
        f"TP={cur.get('tp', 0)} FP={cur.get('fp', 0)} FN={cur.get('fn', 0)}"
    )
    for ref, enabled in ((S17_BASELINE, compare_baseline), (S17_OPTIMIZED, compare_optimized)):
        if not enabled:
            continue
        rm, rM = ref["micro"], ref["macro"]
        lines.append(f"  vs {ref['label']}:")
        lines.append(
            f"    micro-F1 diff {_delta(micro[2] if len(micro) > 2 else None, rm[2])} "
            f"(ref {rm[2]}, cur {micro[2]})  "
            f"macro-F1 diff {_delta(macro[2] if len(macro) > 2 else None, rM[2])} "
            f"(ref {rM[2]}, cur {macro[2]})"
        )
        lines.append(
            f"    TP diff {cur.get('tp', 0) - ref['tp']:+d}  "
            f"FP diff {cur.get('fp', 0) - ref['fp']:+d}  "
            f"FN diff {cur.get('fn', 0) - ref['fn']:+d}  "
            f"(ref TP/FP/FN {ref['tp']}/{ref['fp']}/{ref['fn']})"
        )
    if milestone and milestone < total:
        lines.append("  (partial run — F1/TP deltas are not final until n=500)")
    return "\n".join(lines)


def print_checkpoint(
    states_path: Path,
    milestone: int,
    *,
    total: int = 500,
) -> None:
    cur = metrics_from_states(states_path)
    print(format_s17_report(cur, milestone=milestone, total=total), flush=True)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Compare exp metrics to Table S17")
    parser.add_argument("exp_id", help="Experiment id (result/<exp_id>/states.json)")
    parser.add_argument("--total", type=int, default=500)
    args = parser.parse_args()
    states_path = ROOT / "result" / args.exp_id.strip() / "states.json"
    if not states_path.is_file():
        print(f"Missing {states_path}")
        return 1
    cur = metrics_from_states(states_path)
    n = cur["n_with_metrics"]
    print(format_s17_report(cur, milestone=n, total=args.total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
