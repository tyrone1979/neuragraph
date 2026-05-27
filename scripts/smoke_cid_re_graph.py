#!/usr/bin/env python3
"""Quick smoke test: hypernym → pairs → loop verify (sample 2 only)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.runnables import RunnableConfig  # noqa: E402
from service.entity.runner import RunnerLoader  # noqa: E402
from service.entity.test import TestLoader  # noqa: E402
from utils.conversion import jsonify_state  # noqa: E402
from plugin.plugin_loader import get_plugin  # noqa: E402

RUNNER = "wf_cid_re_llm_linear"
DATASET = "cid_dev_2samples.csv"


def main() -> int:
    sample_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    _, rows = TestLoader.load_by_id_file(RUNNER, DATASET)
    row = jsonify_state(dict(rows[sample_idx - 1]))
    runner = RunnerLoader.load(RUNNER)
    config: RunnableConfig = {"configurable": {"thread_id": f"smoke_{int(time.time())}"}}

    print(f"=== {RUNNER} sample {sample_idx} ===")
    ents = row.get("entities")
    if isinstance(ents, str):
        ents = json.loads(ents)
    print(f"input entities: {len(ents)}")

    t0 = time.perf_counter()
    state = runner.compiled_graph.invoke(row, config=config)
    elapsed = time.perf_counter() - t0

    pairs = state.get("pairs")
    filtered = state.get("filtered_entities")
    rels = state.get("relations")
    print(f"filtered: {len(filtered) if isinstance(filtered, list) else filtered}")
    print(f"pairs: {len(pairs) if isinstance(pairs, list) else pairs}")
    print(f"relations: {rels}")
    print(f"elapsed: {elapsed:.1f}s")

    if row.get("gold_relations") and rels is not None:
        calc = get_plugin("MetricsCalculation")
        m = calc.calculate(
            calc.parse_relation_pairs(row["gold_relations"]),
            calc.parse_relation_pairs(rels),
        )
        print(f"RE F1={m.get('f1', 0):.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
