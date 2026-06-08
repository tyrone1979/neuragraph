#!/usr/bin/env python3
"""Poll result/<exp_id>/states.json and print S17 comparison at each 100-article milestone."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _s17_mod():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "s17", ROOT / "scripts" / "s17_metrics_compare.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exp_id")
    parser.add_argument("--total", type=int, default=500)
    parser.add_argument("--interval", type=float, default=45.0)
    parser.add_argument("--step", type=int, default=100)
    args = parser.parse_args()

    states_path = ROOT / "result" / args.exp_id.strip() / "states.json"
    reported: set[int] = set()
    last_n = 0
    print(f"Watching {states_path} milestones every {args.step} (poll {args.interval}s)")

    while True:
        if not states_path.is_file():
            time.sleep(args.interval)
            continue
        s17 = _s17_mod()
        cur = s17.metrics_from_states(states_path)
        n = int(cur.get("n_with_metrics") or 0)
        for m in range(args.step, args.total + 1, args.step):
            if m in reported:
                continue
            if n >= m:
                print(
                    s17.format_s17_report(cur, milestone=m, total=args.total),
                    flush=True,
                )
                reported.add(m)
        if n >= args.total and args.total in reported:
            print("Done: all milestones reported.", flush=True)
            return 0
        if n != last_n and n % 10 == 0:
            print(f"  ... {n}/{args.total} with metrics", flush=True)
            last_n = n
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
