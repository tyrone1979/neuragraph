#!/usr/bin/env python3
"""Re-run experiment samples and write result/<exp_id>/states.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.runnables import RunnableConfig

from service.entity.runner import RunnerLoader
from service.entity.test import TestLoader
from service.meta.loader import MetaLoader
from utils.conversion import jsonify_state


def repersist(exp_id: str) -> int:
    cfg = MetaLoader.load("exps", exp_id)
    runner_id = cfg["runner_id"]
    dataset = cfg["dataset"]
    cfg["exp_id"] = exp_id

    _, rows = TestLoader.load_by_id_file(runner_id, dataset)
    runner = RunnerLoader.load(runner_id)
    if runner is None:
        print(f"Runner not found: {runner_id}")
        return 1

    results = {}
    for idx, row in enumerate(rows, start=1):
        params = jsonify_state(dict(row))
        config: RunnableConfig = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
        if hasattr(runner, "compiled_graph"):
            state = runner.compiled_graph.invoke(params, config=config)
        else:
            state = runner.invoke(params) or {}
        if isinstance(state, dict):
            results[str(idx)] = state
            m = state.get("metrics") or {}
            f1 = m.get("f1") or m.get("F1")
            print(f"  sample {idx}: f1={f1} keys={list(state.keys())[:8]}")

    path = ROOT / "result" / exp_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "states.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    MetaLoader.update("exps", exp_id, {"status": "completed", "progress": 100})
    print(f"Wrote {path / 'states.json'} ({len(results)} samples)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/repersist_experiment.py <exp_id>")
        raise SystemExit(1)
    raise SystemExit(repersist(sys.argv[1]))
