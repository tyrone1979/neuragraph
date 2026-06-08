#!/usr/bin/env python3
"""Quick smoke test: Flair NER → synonym/hypernym filter → CID RE (sample index argv)."""
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

RUNNER = "wf_e2e_flair_opt_re"
DATASET = "cdr_test_500.csv"


def main() -> int:
    sample_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    _, rows = TestLoader.load_by_id_file(RUNNER, DATASET)
    if sample_idx < 1 or sample_idx > len(rows):
        print(f"sample_idx must be 1..{len(rows)}")
        return 1

    row = jsonify_state(dict(rows[sample_idx - 1]))
    runner = RunnerLoader.load(RUNNER)
    config: RunnableConfig = {"configurable": {"thread_id": f"smoke_e2e_{sample_idx}_{int(time.time())}"}}

    print(f"=== {RUNNER} sample {sample_idx} ===")
    text = row.get("text", "")
    print(f"text preview: {text[:120]}...")
    print(f"gold relations: {row.get('gold_relations')}")

    t0 = time.perf_counter()
    state = runner.compiled_graph.invoke(row, config=config)
    elapsed = time.perf_counter() - t0

    ents = state.get("entities")
    filtered = state.get("filtered_entities")
    pairs = state.get("pairs")
    rels = state.get("relations")
    metrics = state.get("metrics")

    print(f"\nNER entities ({len(ents) if isinstance(ents, list) else ents}):")
    print(json.dumps(ents, ensure_ascii=False, indent=2)[:2000])
    print(f"\nFiltered entities ({len(filtered) if isinstance(filtered, list) else filtered}):")
    print(json.dumps(filtered, ensure_ascii=False, indent=2)[:2000])
    print(f"\npairs: {len(pairs) if isinstance(pairs, list) else pairs}")
    if isinstance(pairs, list):
        for p in pairs:
            print(" ", p)
    print(f"\nrelations: {rels}")
    print(f"elapsed: {elapsed:.1f}s")

    if metrics:
        print(
            f"metrics: F1={metrics.get('f1', 0):.3f}  "
            f"P={metrics.get('precision', 0):.3f}  "
            f"R={metrics.get('recall', 0):.3f}  "
            f"tp={metrics.get('tp')} fp={metrics.get('fp')} fn={metrics.get('fn')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
