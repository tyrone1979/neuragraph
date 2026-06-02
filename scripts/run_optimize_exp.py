"""Run optimization pipeline for a baseline experiment."""
from __future__ import annotations

import json
import sys

from service.experiment_optimize import run_optimize_loop_by_exp_with_progress


def main() -> int:
    exp_id = sys.argv[1] if len(sys.argv) > 1 else "20997f06-fa44-4cad-a725-8ed2ec84e4d3"
    max_updates = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    def progress_cb(ev: dict) -> None:
        print(
            f"[{ev.get('progress')}%] {ev.get('stage')}: {ev.get('message')}",
            flush=True,
        )

    summary = run_optimize_loop_by_exp_with_progress(
        exp_id,
        max_agent_updates=max_updates,
        progress_cb=progress_cb,
    )
    print("SUMMARY:", json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
